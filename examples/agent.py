from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AgentSideConnection,
    AuthenticateResponse,
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    SessionNotification,
    SetSessionModeResponse,
    stdio_streams,
)
from acp.schema import ContentBlock1, SessionUpdate2


if TYPE_CHECKING:
    from acp import (
        AuthenticateRequest,
        CancelNotification,
        InitializeRequest,
        NewSessionRequest,
        PromptRequest,
        SetSessionModeRequest,
    )


class ExampleAgent(Agent):
    def __init__(self, conn: AgentSideConnection) -> None:
        self._conn = conn
        self._next_session_id = 0

    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION, agent_capabilities=None, auth_methods=[]
        )

    async def authenticate(
        self, params: AuthenticateRequest
    ) -> AuthenticateResponse | None:
        return AuthenticateResponse()

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        session_id = f"sess-{self._next_session_id}"
        self._next_session_id += 1
        return NewSessionResponse(session_id=session_id)

    async def loadSession(self, params):  # type: ignore[override]
        return None

    async def setSessionMode(
        self, params: SetSessionModeRequest
    ) -> SetSessionModeResponse | None:
        return SetSessionModeResponse()

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        # Stream a couple of agent message chunks, then end the turn
        # 1) Prefix
        update = SessionUpdate2(content=ContentBlock1(text="Client sent: "))
        notification = SessionNotification(session_id=params.session_id, update=update)
        await self._conn.sessionUpdate(notification)
        # 2) Echo text blocks
        for block in params.prompt:
            if isinstance(block, dict):
                # tolerate raw dicts
                if block.get("type") == "text":
                    text = str(block.get("text", ""))
                else:
                    text = f"<{block.get('type', 'content')}>"
            else:
                # pydantic model ContentBlock1
                text = getattr(block, "text", "<content>")
            update = SessionUpdate2(content=ContentBlock1(text=text))
            await self._conn.sessionUpdate(
                SessionNotification(session_id=params.session_id, update=update)
            )
        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, params: CancelNotification) -> None:
        return None

    async def extMethod(self, method: str, params: dict) -> dict:
        return {"example": "response"}

    async def extNotification(self, method: str, params: dict) -> None:
        return None


async def main() -> None:
    reader, writer = await stdio_streams()
    # For an agent process, local writes go to client stdin (writer=stdout)
    AgentSideConnection(lambda conn: ExampleAgent(conn), writer, reader)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
