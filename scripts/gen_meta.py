#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()


def main() -> None:
    meta_json = ROOT / "schema" / "meta.json"
    out_py = ROOT / "src" / "acp" / "meta.py"
    data = json.loads(meta_json.read_text())
    agent_methods = data.get("agentMethods", {})
    client_methods = data.get("clientMethods", {})
    version = data.get("version", 1)
    out_py.write_text(
        "# This file is generated from schema/meta.json. Do not edit by hand.\n"
        f"AGENT_METHODS = {agent_methods!r}\n"
        f"CLIENT_METHODS = {client_methods!r}\n"
        f"PROTOCOL_VERSION = {int(version)}\n"
    )


if __name__ == "__main__":
    main()
