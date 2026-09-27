"""Write the OpenAPI document the frontend's typed client is generated from.

    python -m app.export_openapi > openapi.json

No database or Redis is needed: the schema is derived from the routes alone.
"""

from __future__ import annotations

import json
import sys

from app.config import Settings
from app.main import create_app


def main() -> None:
    app = create_app(Settings())
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
