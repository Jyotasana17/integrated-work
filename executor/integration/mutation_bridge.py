import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from executor.api.schemas import TaskSubmit
from executor.integration.sys_path_setup import BASE_DIR, MODULES_DIR

logger = logging.getLogger(__name__)

# Path to the node CLI wrapper
CLI_JS_PATH = MODULES_DIR / "Mutation-engine" / "src" / "cli.js"

class MutationBridge:
    """
    Bridges the JavaScript Mutation Engine with the Async Execution System.
    Passes endpoints to the Node script via stdin and parses mutated payloads.
    """
    
    @staticmethod
    def generate_mutations(endpoints: List[Dict], base_url: str = "") -> List[TaskSubmit]:
        """
        Takes a list of endpoint dicts (from discovery), passes them to Node.js,
        and translates the mutated requests back to TaskSubmit objects for fuzzing.
        """
        logger.info(f"Generating mutations for {len(endpoints)} endpoints")
        
        # Prepare input for the Mutation Engine
        requests_for_node = []
        for ep in endpoints:
            path = ep["path"]
            target_url = base_url.rstrip("/") + "/" + path.lstrip("/") if base_url else path
            
            # The JS MutationEngine expects an object with: method, path, params, headers, body
            # We don't have rich params extracted perfectly in discovery_bridge without mapping,
            # but we can pass the path and body if we have one.
            req = {
                "method": ep["method"],
                "path": target_url,
                "headers": {"Content-Type": "application/json"},
                "params": {},
                "body": {"dummy": "value"} if ep.get("request_body_required") else {}
            }
            requests_for_node.append(req)
            
        if not requests_for_node:
            return []
            
        # Run node process
        try:
            input_json = json.dumps(requests_for_node)
            process = subprocess.run(
                ["node", str(CLI_JS_PATH)],
                input=input_json,
                capture_output=True,
                text=True,
                check=True
            )
            results = json.loads(process.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Mutation engine failed with error: {e.stderr}")
            return []
        except Exception as e:
            logger.error(f"Failed to execute mutation engine: {e}")
            return []
            
        tasks = []
        total_mutations = 0
        for res in results:
            mutations = res.get("mutations", [])
            for m in mutations:
                total_mutations += 1
                task = TaskSubmit(
                    method=m.get("method", "GET"),
                    url=m.get("path", ""),
                    headers=m.get("headers", {}),
                    payload=m.get("body", {}),
                    retry_count=1, # Fuzzing tasks shouldn't retry much
                    priority_level="P4" # Fuzzing tasks run on lowest priority
                )
                tasks.append(task)
                
        logger.info(f"Generated {total_mutations} fuzzed tasks from mutation engine.")
        return tasks
