from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from acp import (
    PROTOCOL_VERSION,
    Client,
    ClientSideConnection,
    InitializeRequest,
    NewSessionRequest,
    PromptRequest,
)
from acp.schema import TextContentBlock


if TYPE_CHECKING:
    from acp import SessionNotification


class ExampleClient(Client):
    async def sessionUpdate(self, params: SessionNotification) -> None:
        update = params.update
        kind = (
            getattr(update, "sessionUpdate", None)
            if not isinstance(update, dict)
            else update.get("sessionUpdate")
        )
        if kind == "agent_message_chunk":
            # Handle both dict and model shapes
            content = (
                update["content"]
                if isinstance(update, dict)
                else getattr(update, "content", None)
            )

            text = (
                content.get("text")
                if isinstance(content, dict)
                else getattr(content, "text", "<content>")
            )
            print(f"| Agent: {text}")


async def interactive_loop(conn: ClientSideConnection, session_id: str) -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, lambda: input("> "))
        except EOFError:
            break
        if not line:
            continue
        try:
            block = TextContentBlock(text=line)
            await conn.prompt(PromptRequest(session_id=session_id, prompt=[block]))
        except Exception as e:  # noqa: BLE001
            print(f"error: {e}", file=sys.stderr)


async def main(argv: list[str]) -> int:
    if len(argv) < 2:  # noqa: PLR2004
        print("Usage: python examples/client.py AGENT_PROGRAM [ARGS...]", file=sys.stderr)
        return 2

    # Spawn agent subprocess
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        *argv[1:],
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    assert proc.stdin
    assert proc.stdout

    # Connect to agent stdio
    conn = ClientSideConnection(lambda _agent: ExampleClient(), proc.stdin, proc.stdout)  # pyright: ignore[reportAbstractUsage]

    # Initialize and create session
    init_request = InitializeRequest(
        protocol_version=PROTOCOL_VERSION, client_capabilities=None
    )
    await conn.initialize(init_request)
    request = NewSessionRequest(mcp_servers=[], cwd=str(Path.cwd().resolve()))
    new_sess = await conn.newSession(request)

    # Run REPL until EOF
    await interactive_loop(conn, new_sess.session_id)

    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv)))
