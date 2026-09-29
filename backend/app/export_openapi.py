"""Write the OpenAPI document the frontend's typed client is generated from.

    python -m app.export_openapi openapi.json      (any OS, writes UTF-8 + LF)
    python -m app.export_openapi > openapi.json    (bash)

No database or Redis is needed: the schema is derived from the routes alone.
"""

from __future__ import annotations

import json
import sys

from app.config import Settings
from app.main import create_app


def main() -> None:
    app = create_app(Settings())
    text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        # Explicit path: avoids Windows PowerShell 5.1 redirection writing UTF-16.
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
