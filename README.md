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
# agent_main.py
import asyncio
from acp import Agent, AgentSideConnection, Client, InitializeRequest, InitializeResponse, PromptRequest, PromptResponse, SessionNotification, stdio_streams, PROTOCOL_VERSION
from acp.schema import ContentBlock1, SessionUpdate2

class EchoAgent(Agent):
    def __init__(self, client: Client) -> None:
        self.client = client

    async def initialize(self, _p: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(protocolVersion=PROTOCOL_VERSION)

    async def prompt(self, p: PromptRequest) -> PromptResponse:
        text = "".join([getattr(b, "text", "") for b in p.prompt if getattr(b, "type", None) == "text"]) or "(empty)"
        await self.client.sessionUpdate(SessionNotification(
            sessionId=p.sessionId,
            update=SessionUpdate2(sessionUpdate="agent_message_chunk", content=ContentBlock1(type="text", text=f"Echo: {text}")),
        ))
        return PromptResponse(stopReason="end_turn")

async def main() -> None:
    reader, writer = await stdio_streams()
    AgentSideConnection(lambda c: EchoAgent(c), writer, reader)
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
