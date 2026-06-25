import sys
import os
from pathlib import Path

# Add project root and unzipped module folders to sys.path during test execution
BASE_DIR = Path(__file__).resolve().parent
MODULES_DIR = BASE_DIR / "modules_unzipped"

PATHS_TO_ADD = [
    str(BASE_DIR),
    str(MODULES_DIR / "endpoint_discovery"),
    str(MODULES_DIR / "api-crawler-module"),
    str(MODULES_DIR / "TLL-alpha" / "TLL-alpha-b4d22e2ae8d804a9767ba8bf13dcac18cf77be8e"),
]

for path in PATHS_TO_ADD:
    if path not in sys.path:
        sys.path.insert(0, path)
