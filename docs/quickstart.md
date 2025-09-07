# Quickstart

Use the published package to build an ACP agent, or run the included example.

## Install the SDK

```bash
pip install agent-client-protocol
```

## Minimal agent

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

Run this program from your ACP-capable client.

## Run the Mini SWE Agent bridge in Zed

Install `mini-swe-agent` (or at least its core dependencies) into the same environment that will run the example:

```bash
pip install mini-swe-agent
```

Add an agent server to Zed’s `settings.json`:

```json
{
  "agent_servers": {
    "Mini SWE Agent (Python)": {
      "command": "/abs/path/to/python",
      "args": [
        "/abs/path/to/agent-client-protocol-python/examples/mini_swe_agent/agent.py"
      ],
      "env": {
        "MINI_SWE_MODEL": "openrouter/openai/gpt-4o-mini",
        "MINI_SWE_MODEL_KWARGS": "{\"api_base\":\"https://openrouter.ai/api/v1\"}",
        "OPENROUTER_API_KEY": "sk-or-..."
      }
    }
  }
}
```

In Zed, open the Agents panel and select "Mini SWE Agent (Python)".

See [mini-swe-agent.md](mini-swe-agent.md) for behavior and message mapping details.
