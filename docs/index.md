# Agent Client Protocol (Python)

A Python implementation of the Agent Client Protocol (ACP). Build agents that communicate with ACP-capable clients (e.g. Zed) over stdio.

## Install

```bash
pip install agent-client-protocol
```

## Minimal usage

```python
from acp import Agent, AgentSideConnection, Client, stdio_streams, PROTOCOL_VERSION, InitializeRequest, InitializeResponse, PromptRequest, PromptResponse
from acp.schema import ContentBlock1, SessionUpdate2, SessionNotification

class MyAgent(Agent):
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
```

- Quickstart: [quickstart.md](quickstart.md)
- Mini SWE Agent example: [mini-swe-agent.md](mini-swe-agent.md)
