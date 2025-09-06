# Quickstart

Use the published package to build an ACP agent, or run the included example.

## Install the SDK

```bash
pip install agent-client-protocol
```

## Minimal agent

```python
import asyncio
from acp import Agent, AgentSideConnection, Client, InitializeRequest, InitializeResponse, PromptRequest, PromptResponse, SessionNotification, stdio_streams, PROTOCOL_VERSION
from acp.schema import ContentBlock1, SessionUpdate2

class EchoAgent(Agent):
    def __init__(self, client: Client):
        self.client = client
    async def initialize(self, _p: InitializeRequest) -> InitializeResponse:
        return InitializeResponse(protocolVersion=PROTOCOL_VERSION)
    async def prompt(self, p: PromptRequest) -> PromptResponse:
        await self.client.sessionUpdate(SessionNotification(
            sessionId=p.sessionId,
            update=SessionUpdate2(sessionUpdate="agent_message_chunk", content=ContentBlock1(type="text", text="Hello from ACP")),
        ))
        return PromptResponse(stopReason="end_turn")

async def main() -> None:
    reader, writer = await stdio_streams()
    AgentSideConnection(lambda c: EchoAgent(c), writer, reader)
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
