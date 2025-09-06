import asyncio
import os
import sys

from acp import (
    Client,
    PROTOCOL_VERSION,
    ClientSideConnection,
    InitializeRequest,
    NewSessionRequest,
    PromptRequest,
    ReadTextFileRequest,
    ReadTextFileResponse,
    RequestPermissionRequest,
    RequestPermissionResponse,
    SessionNotification,
    WriteTextFileRequest,
    stdio_streams,
)


class MinimalClient(Client):
    async def writeTextFile(self, params: WriteTextFileRequest) -> None:
        print(f"write {params.path}", file=sys.stderr)

    async def readTextFile(self, params: ReadTextFileRequest) -> ReadTextFileResponse:
        return ReadTextFileResponse(content="example")

    async def requestPermission(self, params: RequestPermissionRequest) -> RequestPermissionResponse:
        return RequestPermissionResponse.model_validate({"outcome": {"outcome": "selected", "optionId": "allow"}})

    async def sessionUpdate(self, params: SessionNotification) -> None:
        print(f"session update: {params}", file=sys.stderr)

    # Optional terminal methods (not implemented in this minimal client)
    async def createTerminal(self, params) -> None:
        pass

    async def terminalOutput(self, params) -> None:
        pass

    async def releaseTerminal(self, params) -> None:
        pass

    async def waitForTerminalExit(self, params) -> None:
        pass

    async def killTerminal(self, params) -> None:
        pass


async def main() -> None:
    reader, writer = await stdio_streams()
    client_conn = ClientSideConnection(lambda _agent: MinimalClient(), writer, reader)
    # 1) initialize
    resp = await client_conn.initialize(InitializeRequest(protocolVersion=PROTOCOL_VERSION))
    print(f"Initialized with protocol version: {resp.protocolVersion}", file=sys.stderr)
    # 2) new session
    new_sess = await client_conn.newSession(NewSessionRequest(mcpServers=[], cwd=os.getcwd()))
    # 3) prompt
    await client_conn.prompt(
        PromptRequest(
            sessionId=new_sess.sessionId,
            prompt=[{"type": "text", "text": "Hello from client"}],
        )
    )
    # Small grace period to allow duplex messages to flush
    await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())
