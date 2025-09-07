# Agent Client Protocol (Python)

A Python implementation of the Agent Client Protocol (ACP). Use it to build agents that communicate with ACP-capable clients (e.g. Zed) over stdio.

- Package name: `agent-client-protocol` (import as `acp`)
- Repository: https://github.com/psiace/agent-client-protocol-python
- Docs: https://psiace.github.io/agent-client-protocol-python/

## Install

```bash
pip install agent-client-protocol
# or
uv add agent-client-protocol
```

## Development (contributors)

```bash
make install   # set up venv
make check     # lint + typecheck
make test      # run tests
```

## Minimal agent example

```python
import asyncio

from acp import (
    Agent,
    AgentSideConnection,
    AuthenticateRequest,
    CancelNotification,
    InitializeRequest,
    InitializeResponse,
    LoadSessionRequest,
    NewSessionRequest,
    NewSessionResponse,
    PromptRequest,
    PromptResponse,
    stdio_streams,
)


class EchoAgent(Agent):
    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(protocolVersion=params.protocolVersion)

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        return NewSessionResponse(sessionId="sess-1")

    async def loadSession(self, params: LoadSessionRequest) -> None:
        return None

    async def authenticate(self, params: AuthenticateRequest) -> None:
        return None

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        # Normally you'd stream updates via sessionUpdate
        return PromptResponse(stopReason="end_turn")

    async def cancel(self, params: CancelNotification) -> None:
        return None


async def main() -> None:
    reader, writer = await stdio_streams()
    # For an agent process, local writes go to client stdin (writer=stdout)
    AgentSideConnection(lambda _conn: EchoAgent(), writer, reader)
    # Keep running; in a real agent you would await tasks or add your own loop
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
```

Run this executable from your ACP-capable client (e.g. configure Zed to launch it). The library takes care of the stdio JSON-RPC transport.

## Example: Mini SWE Agent bridge

A minimal ACP bridge for mini-swe-agent is provided under [`examples/mini_swe_agent`](examples/mini_swe_agent/README.md). It demonstrates:

- Parsing a prompt from ACP content blocks
- Streaming agent output via `session/update`
- Mapping command execution to `tool_call` and `tool_call_update`

## Documentation

- Quickstart: [docs/quickstart.md](docs/quickstart.md)
- Mini SWE Agent example: [docs/mini-swe-agent.md](docs/mini-swe-agent.md)
