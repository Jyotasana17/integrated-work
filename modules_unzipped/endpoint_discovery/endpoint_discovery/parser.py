import json
import logging
import re
from typing import Any, Dict, List, Optional, Set
import httpx
from .models import DiscoveredEndpoint

# Attempt to import yaml for stretch goal
try:
    import yaml
except ImportError:
    yaml = None

# Set up logging
logger = logging.getLogger(__name__)


class OpenAPIParser:
    """Parses OpenAPI 3.0 or Swagger 2.0 specifications with high resilience."""
    
    VALID_METHODS = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD', 'TRACE'}

    def __init__(self, spec_data: Dict[str, Any]):
        self.spec = spec_data if isinstance(spec_data, dict) else {}
        self.endpoints: List[DiscoveredEndpoint] = []
        self.errors_encountered: List[str] = []
        self.seen_endpoints: Set[tuple] = set()


    @classmethod
    def from_file(cls, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        
            return cls.from_content(
                content,
                source_name=filepath
                )
        
        except Exception as e:
            parser = cls({})
            parser.errors_encountered.append(
                f"Could not load file {filepath}: {str(e)}"
            )
            return parser

    @classmethod
    def from_url(cls, url: str) -> "OpenAPIParser":
        """Fetches a specification from a URL (JSON or YAML)."""
        try:
            with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            verify=True
            ) as client:
                response = client.get(
                    url,
                    follow_redirects=True
                )
                logger.info(f"Fetching {url}")
                logger.info(f"Status Code : {response.status_code}")
                logger.info(response.text[:500])
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "yaml" in content_type or "yml" in content_type:
                    return cls.from_content(
                        response.text,
                        source_name="remote_yaml"
                    )
                else:
                    return cls.from_content(
                        response.text,
                        source_name="remote_json"
                    )
                
        except Exception as e:
            logger.exception(e)
        
            parser = cls({})
            parser.errors_encountered.append(
                f"Could not fetch URL {url}: {e}"
            )
            return parser
    
    @classmethod
    def from_content(cls, content: str, source_name: str = "content") -> "OpenAPIParser":
        """Parses specification from a string content."""
        # Try JSON first
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Specification root must be an object")
        except json.JSONDecodeError as e:
            if yaml:
                try:
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid YAML specification")
                except Exception as ye:
                    parser = cls({})
                    parser.errors_encountered.append(f"Failed to parse {source_name} as JSON or YAML: {e}, {ye}")
                    return parser
            else:
                parser = cls({})
                parser.errors_encountered.append(f"Failed to parse {source_name} as JSON and YAML support is missing: {e}")
                return parser
        return cls(data)

    def _normalize_path(self, path: str) -> str:
        """
        Normalizes paths:
        - Remove duplicate slashes
        - Strip trailing slashes
        - Preserve parameters
        """
        if not path:
            return "/"

        # Remove duplicate slashes (e.g., //api///users -> /api/users)
        normalized = re.sub(r'/+', '/', path)

        # Strip trailing slash unless it's just "/"
        if len(normalized) > 1 and normalized.endswith('/'):
            normalized = normalized.rstrip('/')

        if not normalized.startswith('/'):
            normalized = '/' + normalized

        return normalized

    def _check_auth(self, method_details: Dict[str, Any]) -> bool:
        """Determines if the endpoint has authentication required."""
        # Check endpoint-specific security
        if "security" in method_details:
            security = method_details["security"]
            # If security is an empty list [], it means auth is explicitly disabled
            return isinstance(security, list) and len(security) > 0

        # Check global security
        global_security = self.spec.get("security", [])
        return isinstance(global_security, list) and len(global_security) > 0

    def _resolve_ref(self, schema: Any) -> Any:
        """Resolves internal JSON references ($ref)."""
        if not isinstance(schema, dict) or "$ref" not in schema:
            return schema

        ref_path = schema["$ref"]
        if not ref_path.startswith("#/"):
            # External refs not supported in this version
            return schema

        parts = ref_path.split("/")[1:]
        current = self.spec
        try:
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            self.errors_encountered.append(f"Could not resolve reference: {ref_path}")
            return schema

    def _extract_body_schema(self, method: str, method_details: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], bool]:
        """Extracts JSON request body schema and whether it is required."""
        schema = None
        required = False

        # OpenAPI 3.x structure
        if "requestBody" in method_details:
            rb = method_details["requestBody"]
            # Resolve ref for requestBody itself
            rb = self._resolve_ref(rb)

            required = rb.get("required", False)
            content = rb.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema")

        # Swagger 2.0 structure
        if not schema:
            for param in method_details.get("parameters", []):
                param = self._resolve_ref(param)
                if param.get("in") == "body":
                    schema = param.get("schema")
                    required = param.get("required", False)
                    break

        if schema:
            schema = self._resolve_ref(schema)

        # Schema Fallback Logic:
        # "When request body schema is missing: Default to empty object {} for POST/PUT/PATCH"
        if schema is None and method in ['POST', 'PUT', 'PATCH']:
            schema = {}
            logger.warning(f"Missing request body schema for {method}. Defaulting to empty object.")

        return schema, required

    def _process_parameters(self, method_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts and processes parameters with fallback logic."""
        params = method_details.get("parameters", [])
        if not isinstance(params, list):
            return []

        processed = []
        for param in params:
            param = self._resolve_ref(param)
            if not isinstance(param, dict):
                continue

            p = param.copy()
            # Parameter Schema Fallback: "Assume type string, Assume not required"
            if "schema" not in p:
                p["schema"] = {"type": "string"}

            if "required" not in p:
                p["required"] = False

            processed.append(p)
        return processed

    def parse(self) -> Dict[str, Any]:
        """
        Main entry point to extract endpoints. Handles malformed specs gracefully.
        Returns a dictionary matching the required output format.
        """
        if not self.spec:
            logger.warning("Specification is empty or was not loaded correctly.")
            return self._build_result()

        paths_obj = self.spec.get("paths")
        if paths_obj is None:
            self.errors_encountered.append("Missing 'paths' section in specification.")
            return self._build_result()

        if not isinstance(paths_obj, dict):
            self.errors_encountered.append("'paths' section is not a valid object.")
            return self._build_result()

        for path, methods in paths_obj.items():
            if not isinstance(methods, dict):
                self.errors_encountered.append(f"Invalid methods definition for path '{path}'. Expected object.")
                continue

            normalized_path = self._normalize_path(path)

            for method_name, details in methods.items():
                upper_method = method_name.upper()

                # Validation: Invalid HTTP method
                if upper_method not in self.VALID_METHODS:
                    self.errors_encountered.append(f"Invalid HTTP method '{method_name}' for path '{path}'. Skipping.")
                    continue

                if not isinstance(details, dict):
                    self.errors_encountered.append(f"Missing or invalid details for {upper_method} {path}.")
                    continue

                # De-duplication Logic
                endpoint_key = (upper_method, normalized_path)
                if endpoint_key in self.seen_endpoints:
                    self.errors_encountered.append(f"Duplicate endpoint detected: {upper_method} {normalized_path}. Keeping first occurrence.")
                    continue

                # Validation: Missing responses field
                if "responses" not in details:
                    self.errors_encountered.append(f"Missing 'responses' field for {upper_method} {path}.")

                # Extract schema and requirement
                body_schema, body_required = self._extract_body_schema(upper_method, details)

                # Create endpoint object
                endpoint = DiscoveredEndpoint(
                    method=upper_method,
                    path=normalized_path,
                    request_body_required=body_required,
                    has_auth=self._check_auth(details),
                    parameters=self._process_parameters(details),
                    request_body_schema=body_schema
                )

                self.endpoints.append(endpoint)
                self.seen_endpoints.add(endpoint_key)

        result = self._build_result()
        logger.info(f"Discovery complete. Found {len(self.endpoints)} endpoints with {len(self.errors_encountered)} errors/warnings.")
        return result

    def _build_result(self) -> Dict[str, Any]:
        """Constructs the final output dictionary."""
        return {
            "endpoints": [e.to_dict() for e in self.endpoints],
            "errors_encountered": self.errors_encountered,
            "total_endpoints": len(self.endpoints)
        }
