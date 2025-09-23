from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from acp import (
    Agent,
    AgentSideConnection,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    SessionNotification,
    stdio_streams,
)
from acp.schema import AgentMessageChunk, TextContentBlock


if TYPE_CHECKING:
    from acp import (
        InitializeRequest,
        NewSessionRequest,
        PromptRequest,
    )


class EchoAgent(Agent):
    def __init__(self, conn):
        self._conn = conn

    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(protocol_version=params.protocol_version)

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        return NewSessionResponse(session_id="sess-1")

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        for block in params.prompt:
            text = (
                block.get("text", "")
                if isinstance(block, dict)
                else getattr(block, "text", "")
            )
            await self._conn.sessionUpdate(
                SessionNotification(
                    session_id=params.session_id,
                    update=AgentMessageChunk(
                        content=TextContentBlock(text=text),
                    ),
                )
            )
        return PromptResponse(stop_reason="end_turn")


async def main() -> None:
    reader, writer = await stdio_streams()
    AgentSideConnection(lambda conn: EchoAgent(conn), writer, reader)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
