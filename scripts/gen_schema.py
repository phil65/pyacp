from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]

SCHEMA_URL = "https://raw.githubusercontent.com/zed-industries/agent-client-protocol/refs/heads/main/schema/schema.json"
META_URL = "https://raw.githubusercontent.com/zed-industries/agent-client-protocol/refs/heads/main/schema/meta.json"


def fetch_json(url: str) -> dict:
    """Fetch JSON data from a URL."""
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"Failed to fetch {url}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Generate schema.py
    schema_out = ROOT / "src" / "acp" / "schema.py"

    # Create a temporary file for the schema JSON
    temp_dir = Path(tempfile.gettempdir())
    temp_schema_path = temp_dir / "schema.json"
    schema_data = fetch_json(SCHEMA_URL)
    temp_schema_path.write_text(json.dumps(schema_data, indent=2))

    try:
        cmd = [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(temp_schema_path),
            "--input-file-type",
            "jsonschema",
            "--output",
            str(schema_out),
            "--target-python-version",
            "3.12",
            "--collapse-root-models",
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--use-annotated",
            "--use-one-literal-as-default",
            "--enum-field-as-literal",
            "all",
            "--use-double-quotes",
            "--use-union-operator",
            "--use-standard-collections",
            "--use-schema-description",
            "--allow-population-by-field-name",
            "--snake-case-field",
            "--use-generic-container-types",
        ]
        subprocess.check_call(cmd)

        # Post-process to rename numbered classes
        _rename_numbered_classes(schema_out)
    finally:
        # Clean up temporary file
        temp_schema_path.unlink(missing_ok=True)

    # Generate meta.py
    meta_out = ROOT / "src" / "acp" / "meta.py"
    meta_data = fetch_json(META_URL)
    agent_methods = meta_data.get("agentMethods", {})
    client_methods = meta_data.get("clientMethods", {})
    version = meta_data.get("version", 1)

    meta_out.write_text(
        f"# This file is generated from {META_URL}.\n# Do not edit by hand.\n"
        f"AGENT_METHODS = {agent_methods!r}\n"
        f"CLIENT_METHODS = {client_methods!r}\n"
        f"PROTOCOL_VERSION = {int(version)}\n"
    )

    # Format generated files with ruff
    _format_with_ruff(schema_out)
    _format_with_ruff(meta_out)


def _format_with_ruff(file_path: Path) -> None:
    """Format a Python file with ruff."""
    try:
        cmd = ["uv", "run", "ruff", "format", str(file_path)]
        subprocess.check_call(cmd)
        print(f"Formatted {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to format {file_path}: {e}", file=sys.stderr)


def _rename_numbered_classes(file_path: Path) -> None:
    """Rename numbered classes to more meaningful names."""
    rename_map = {
        # Rename the numbered ones that don't have proper names
        "SessionUpdate1": "UserMessageChunk",
        "SessionUpdate2": "AgentMessageChunk",
        "SessionUpdate3": "AgentThoughtChunk",
        "SessionUpdate4": "ToolCallStart",
        "SessionUpdate5": "ToolCallProgress",
        "SessionUpdate6": "AgentPlan",
        "SessionUpdate7": "AvailableCommandsUpdate",
        "SessionUpdate8": "CurrentModeUpdate",
        # ContentBlock variants - use different names to avoid conflicts
        "ContentBlock1": "TextContentBlock",
        "ContentBlock2": "ImageContentBlock",
        "ContentBlock3": "AudioContentBlock",
        "ContentBlock4": "ResourceContentBlock",
        "ContentBlock5": "EmbeddedResourceContentBlock",
        # ToolCallContent variants - use different names to avoid conflicts
        "ToolCallContent1": "ContentToolCallContent",
        "ToolCallContent2": "FileEditToolCallContent",
        "ToolCallContent3": "TerminalToolCallContent",
        # RequestPermissionOutcome variants
        "RequestPermissionOutcome1": "DeniedOutcome",
        "RequestPermissionOutcome2": "AllowedOutcome",
        # McpServer variants
        "McpServer1": "HttpMcpServer",
        "McpServer2": "SseMcpServer",
        "McpServer3": "StdioMcpServer",
        # Other numbered classes
        "AvailableCommandInput1": "CommandInputHint",
    }

    content = file_path.read_text("utf-8")

    # Replace class definitions and all references
    # Sort by length descending to avoid partial matches (e.g., avoid replacing
    # "SessionUpdate1" before "SessionUpdate10")
    for old_name, new_name in sorted(
        rename_map.items(), key=lambda x: len(x[0]), reverse=True
    ):
        # Replace class definition
        content = content.replace(f"class {old_name}(", f"class {new_name}(")

        # Replace type annotations and references
        # Handle standalone usage
        content = content.replace(f"{old_name} |", f"{new_name} |")
        content = content.replace(f"| {old_name}", f"| {new_name}")
        content = content.replace(f": {old_name}", f": {new_name}")
        content = content.replace(f"[{old_name}]", f"[{new_name}]")
        content = content.replace(f"List[{old_name}]", f"List[{new_name}]")
        content = content.replace(f"Optional[{old_name}]", f"Optional[{new_name}]")
        content = content.replace(f"Union[{old_name}", f"Union[{new_name}")
        content = content.replace(f", {old_name}]", f", {new_name}]")
        content = content.replace(f"({old_name},", f"({new_name},")
        content = content.replace(f"({old_name})", f"({new_name})")

        # Handle line beginnings and isolated references
        content = content.replace(f"\n        {old_name}", f"\n        {new_name}")
        content = content.replace(
            f"\n            {old_name}", f"\n            {new_name}"
        )
        content = content.replace(f" {old_name}(", f" {new_name}(")
        content = content.replace(f"={old_name}(", f"={new_name}(")
        content = content.replace(f"return {old_name}(", f"return {new_name}(")

        # Handle imports and root model references
        content = content.replace(f"[{old_name}])", f"[{new_name}])")
        content = content.replace(
            f"root: Annotated[\n        {old_name},",
            f"root: Annotated[\n        {new_name},",
        )

        # Handle type union patterns in annotated types
        content = content.replace(
            f"Annotated[\n        {old_name}", f"Annotated[\n        {new_name}"
        )

    file_path.write_text(content)


if __name__ == "__main__":
    main()
