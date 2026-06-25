import logging
from typing import List, Any
import json

from executor.endpoint_discovery.parser import OpenAPIParser
from executor.api.schemas import TaskSubmit

logger = logging.getLogger(__name__)

class DiscoveryBridge:
    """
    Bridges the endpoint_discovery module with the Async Execution System.
    Parses an OpenAPI spec and generates standard execution tasks (API Crawler tasks).
    """

    # Errors/warnings from the most recent parse, so callers can surface a
    # descriptive validation message to the user instead of a silent no-op.
    last_parse_errors: List[str] = []
    
    @staticmethod
    def generate_tasks_from_spec(spec_source: str, base_url: str = "") -> List[TaskSubmit]:
        """
        Takes a URL or file path to an OpenAPI spec, runs the endpoint_discovery parser,
        and generates a list of base TaskSubmit objects.
        """
        logger.info(f"Running endpoint discovery on {spec_source}")
        
        if spec_source.startswith("http://") or spec_source.startswith("https://"):
            parser = OpenAPIParser.from_url(spec_source)
            result = parser.parse()
            endpoints = result.get("endpoints", [])
            
            # Intelligent Probing Fallback: Try common spec paths if the main URL fails parsing
            if not endpoints and any("paths" in str(e).lower() or "json" in str(e).lower() for e in result.get("errors_encountered", [])):
                logger.info(f"Initial parse failed for {spec_source}, trying common spec paths...")
                from urllib.parse import urlparse
                parsed_url = urlparse(spec_source)
                base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                paths_to_try = [
                    spec_source.rstrip('/') + "/swagger.json",
                    spec_source.rstrip('/') + "/openapi.json",
                    spec_source.rstrip('/') + "/api-docs",
                    base_host + "/swagger.json",
                    base_host + "/openapi.json",
                    base_host + "/api-docs",
                ]
                
                unique_paths = []
                for p in paths_to_try:
                    if p not in unique_paths:
                        unique_paths.append(p)
                        
                for test_url in unique_paths:
                    logger.info(f"Probing fallback URL: {test_url}")
                    try:
                        fallback_parser = OpenAPIParser.from_url(test_url)
                        fallback_result = fallback_parser.parse()
                        if fallback_result.get("endpoints"):
                            logger.info(f"Successfully found spec at {test_url}")
                            parser = fallback_parser
                            result = fallback_result
                            endpoints = result.get("endpoints", [])
                            break
                    except Exception:
                        continue
                        
            # Final Fallback: Treat as a single endpoint if all spec discovery failed
            if not endpoints:
                logger.info(f"All specification probing failed. Treating {spec_source} as a single API endpoint.")
                from urllib.parse import urlparse
                parsed_url = urlparse(spec_source)
                single_ep = {
                    "method": "GET",
                    "path": parsed_url.path or "/",
                    "request_body_required": False,
                    "has_auth": False,
                    "parameters": [],
                    "request_body_schema": None
                }
                result["endpoints"] = [single_ep]
                # Override base_url to ensure the host is correct for this single endpoint
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
        elif spec_source.strip().startswith("{") or spec_source.strip().startswith("openapi"):
            # Raw JSON or YAML content passed as string
            parser = OpenAPIParser.from_content(spec_source, source_name="inline_spec")
            result = parser.parse()
        else:
            parser = OpenAPIParser.from_file(spec_source)
            result = parser.parse()
            
        endpoints = result.get("endpoints", [])
        if not endpoints and result.get("errors_encountered"):
            raise ValueError("Spec discovery failed: " + "; ".join(result["errors_encountered"][:5]))
        
        if len(endpoints) == 0:
            raise ValueError(
                f"No endpoints discovered. Parser errors: {DiscoveryBridge.last_parse_errors}"
            )
        
        tasks = []
        for ep in endpoints:
            # Generate a base url by combining base_url and path
            # Remove trailing slash from base_url if path starts with it
            target_url = base_url.rstrip("/") + "/" + ep["path"].lstrip("/") if base_url else ep["path"]
            
            # Simple payload generation based on schema (can be extended with fuzzing)
            payload = None
            if ep.get("request_body_required") and ep.get("request_body_schema"):
                # Use a dummy JSON if schema is present
                payload = {"_comment": "Auto-generated dummy payload for crawler"}
                
            task = TaskSubmit(
                method=ep["method"],
                url=target_url,
                headers={"Content-Type": "application/json"} if payload else {},
                payload=payload,
                retry_count=3,
                priority_level="P3"  # Base crawler tasks run on medium priority
            )
            
            # Store some metadata in the task if needed (not directly supported by TaskSubmit, 
            # but we can use headers or wrap it)
            # We'll rely on the orchestrator to check `ep["has_auth"]` later, 
            # so we'll just return a tuple of (task, endpoint_dict) if we want to pass it back.
            
            tasks.append((task, ep))
            
        return tasks
