from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    schema_json = ROOT / "schema" / "schema.json"
    out_py = ROOT / "src" / "acp" / "schema.py"
    if not schema_json.exists():
        print(f"Schema not found at {schema_json}.", file=sys.stderr)
        sys.exit(1)
    cmd = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(schema_json),
        "--input-file-type",
        "jsonschema",
        "--output",
        str(out_py),
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
    _rename_numbered_classes(out_py)


def _rename_numbered_classes(file_path: Path) -> None:
    """Rename numbered classes to more meaningful names."""
    rename_map = {
        # ename the numbered ones that don't have proper names
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

    content = file_path.read_text()

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
