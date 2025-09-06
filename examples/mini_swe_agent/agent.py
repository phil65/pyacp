import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from acp import (
    Agent,
    AgentSideConnection,
    AuthenticateRequest,
    CancelNotification,
    Client,
    InitializeRequest,
    InitializeResponse,
    NewSessionRequest,
    NewSessionResponse,
    PromptRequest,
    PromptResponse,
    SessionNotification,
    stdio_streams,
    PROTOCOL_VERSION,
)
from acp.schema import (
    ContentBlock1,
    SessionUpdate2,
    SessionUpdate4,
    SessionUpdate5,
    ToolCallContent1,
)

# Lazily import mini-swe-agent to avoid hard dependency for users who don't need this example


def _create_streaming_mini_agent(
    *,
    client: Client,
    session_id: str,
    cwd: str,
    model_name: str,
    model_kwargs: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
):
    """Create a DefaultAgent that emits ACP session/update events during execution.

    Returns (agent, error_message_if_any).
    """
    try:
        try:
            from minisweagent.agents.default import (
                DefaultAgent,
                NonTerminatingException,
                Submitted,
                LimitsExceeded,
            )  # type: ignore
            from minisweagent.environments.local import LocalEnvironment  # type: ignore
            from minisweagent.models.litellm_model import LitellmModel  # type: ignore
        except Exception:
            # Fallback to vendored reference copy if available
            REF_SRC = Path(__file__).resolve().parents[2] / "reference" / "mini-swe-agent" / "src"
            if REF_SRC.is_dir():
                if str(REF_SRC) not in sys.path:
                    sys.path.insert(0, str(REF_SRC))
                from minisweagent.agents.default import (
                    DefaultAgent,
                    NonTerminatingException,
                    Submitted,
                    LimitsExceeded,
                )  # type: ignore
                from minisweagent.environments.local import LocalEnvironment  # type: ignore
                from minisweagent.models.litellm_model import LitellmModel  # type: ignore
            else:
                raise

        class _StreamingMiniAgent(DefaultAgent):  # type: ignore[misc]
            def __init__(self) -> None:
                self._acp_client = client
                self._session_id = session_id
                self._tool_seq = 0
                self._loop = loop
                # expose mini-swe-agent exception types for outer loop
                self._Submitted = Submitted
                self._NonTerminatingException = NonTerminatingException
                self._LimitsExceeded = LimitsExceeded
                model = LitellmModel(model_name=model_name, model_kwargs=model_kwargs)
                env = LocalEnvironment(cwd=cwd)
                super().__init__(model=model, env=env)

            def _schedule(self, coro):
                import asyncio as _asyncio

                _asyncio.run_coroutine_threadsafe(coro, self._loop)

            async def _send(self, update_model) -> None:
                await self._acp_client.sessionUpdate(
                    SessionNotification(sessionId=self._session_id, update=update_model)
                )

            async def on_tool_start(self, title: str, command: str, tool_call_id: str) -> None:
                update = SessionUpdate4(
                    sessionUpdate="tool_call",
                    toolCallId=tool_call_id,
                    title=title,
                    kind="execute",
                    status="pending",
                    content=[
                        ToolCallContent1(
                            type="content",
                            content=ContentBlock1(type="text", text=f"```bash\n{command}\n```"),
                        )
                    ],
                    rawInput={"command": command},
                )
                await self._send(update)

            async def on_tool_complete(
                self,
                tool_call_id: str,
                output: str,
                returncode: int,
                *,
                status: str = "completed",
            ) -> None:
                update = SessionUpdate5(
                    sessionUpdate="tool_call_update",
                    toolCallId=tool_call_id,
                    status=status,
                    content=[
                        ToolCallContent1(
                            type="content",
                            content=ContentBlock1(type="text", text=output),
                        )
                    ],
                    rawOutput={"output": output, "returncode": returncode},
                )
                await self._send(update)

            def execute_action(self, action: dict) -> dict:  # type: ignore[override]
                self._tool_seq += 1
                tool_id = f"mini-bash-{self._tool_seq}-{uuid.uuid4().hex[:8]}"
                command = action.get("action", "")
                self._schedule(self.on_tool_start("bash", command, tool_id))
                try:
                    result = super().execute_action(action)
                    output = result.get("output", "")
                    returncode = int(result.get("returncode", 0) or 0)
                    self._schedule(self.on_tool_complete(tool_id, output, returncode, status="completed"))
                    return result
                except Submitted as e:
                    # Finished successfully; e contains the final output without the marker line
                    final_text = str(e)
                    self._schedule(self.on_tool_complete(tool_id, final_text, 0, status="completed"))
                    raise
                except NonTerminatingException as e:
                    # Non-terminating cases: timeouts or user-driven re-plans in interactive flows.
                    # Map likely user cancellations to a softer status for better UX.
                    msg = str(e)
                    status = (
                        "cancelled"
                        if any(
                            key in msg
                            for key in (
                                "Command not executed",
                                "Switching to human mode",
                                "switched to manual mode",
                                "Interrupted by user",
                            )
                        )
                        else "failed"
                    )
                    self._schedule(
                        self.on_tool_complete(tool_id, msg, 124 if status != "cancelled" else 0, status=status)
                    )
                    raise
                except Exception as e:  # include other failures
                    msg = str(e) or "execution failed"
                    self._schedule(self.on_tool_complete(tool_id, msg, 124, status="failed"))
                    raise

        return _StreamingMiniAgent(), None
    except Exception as e:
        return None, f"Failed to load mini-swe-agent: {e}"


class MiniSweACPAgent(Agent):
    def __init__(self, client: Client) -> None:
        self._client = client
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def initialize(self, _params: InitializeRequest) -> InitializeResponse:
        from acp.schema import AgentCapabilities, PromptCapabilities

        return InitializeResponse(
            protocolVersion=PROTOCOL_VERSION,
            agentCapabilities=AgentCapabilities(
                loadSession=True,
                promptCapabilities=PromptCapabilities(audio=False, image=False, embeddedContext=True),
            ),
            authMethods=[],
        )

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = {
            "cwd": params.cwd,
            "agent": None,
        }
        return NewSessionResponse(sessionId=session_id)

    async def loadSession(self, params) -> None:  # type: ignore[override]
        # Update/initialize session storage for externally provided sessionId
        try:
            session_id = params.sessionId  # type: ignore[attr-defined]
            cwd = params.cwd  # type: ignore[attr-defined]
        except Exception:
            session_id = getattr(params, "sessionId", "sess-unknown")
            cwd = getattr(params, "cwd", os.getcwd())
        self._sessions.setdefault(session_id, {"cwd": cwd, "agent": None})
        return None

    async def authenticate(self, _params: AuthenticateRequest) -> None:
        # mini-swe-agent reads credentials from environment (e.g., OpenAI/OpenRouter)
        return None

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        sess = self._sessions.get(params.sessionId)
        if not sess:
            # Create a volatile session if missing
            self._sessions[params.sessionId] = {"cwd": os.getcwd(), "agent": None}
            sess = self._sessions[params.sessionId]

        # Build the task string from content blocks
        task_parts: list[str] = []
        for block in params.prompt:
            btype = getattr(block, "type", None)
            if btype == "text":
                text = getattr(block, "text", "")
                if text:
                    task_parts.append(str(text))
            elif btype in ("resource", "resource_link"):
                # Represent referenced resources as hints
                uri = None
                if btype == "resource_link":
                    uri = getattr(block, "uri", None)
                else:  # resource with embedded contents
                    res = getattr(block, "resource", None)
                    uri = getattr(res, "uri", None)
                if uri:
                    task_parts.append(f"\nReference: {uri}\n")
        task = "".join(task_parts).strip() or "Help me with the current repository."

        # Create the backing mini-swe-agent on first use per session
        agent = sess.get("agent")
        if agent is None:
            model_name = os.getenv("MINI_SWE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
            model_kwargs_env = os.getenv("MINI_SWE_MODEL_KWARGS", "{}")
            try:
                import json

                model_kwargs = json.loads(model_kwargs_env)
                if not isinstance(model_kwargs, dict):
                    model_kwargs = {}
            except Exception:
                model_kwargs = {}

            loop = asyncio.get_running_loop()
            agent, err = _create_streaming_mini_agent(
                client=self._client,
                session_id=params.sessionId,
                cwd=sess.get("cwd") or os.getcwd(),
                model_name=model_name,
                model_kwargs=model_kwargs,
                loop=loop,
            )
            if err:
                await self._client.sessionUpdate(
                    SessionNotification(
                        sessionId=params.sessionId,
                        update=SessionUpdate2(
                            sessionUpdate="agent_message_chunk",
                            content=ContentBlock1(
                                type="text",
                                text=(
                                    "mini-swe-agent load error: "
                                    + err
                                    + "\nPlease install mini-swe-agent or its dependencies in the configured venv."
                                ),
                            ),
                        ),
                    )
                )
                return PromptResponse(stopReason="end_turn")
            sess["agent"] = agent

        # Initialize the mini-swe-agent conversation like DefaultAgent.run does
        agent.extra_template_vars |= {"task": task}
        agent.messages = []
        agent.add_message("system", agent.render_template(agent.config.system_template))
        agent.add_message("user", agent.render_template(agent.config.instance_template))

        # Immediate UX feedback
        await self._client.sessionUpdate(
            SessionNotification(
                sessionId=params.sessionId,
                update=SessionUpdate2(
                    sessionUpdate="agent_message_chunk",
                    content=ContentBlock1(
                        type="text",
                        text=f"Starting mini-swe-agent…\nTask: {task[:200]}",
                    ),
                ),
            )
        )

        # Step until completion, surfacing updates
        final_message = ""
        SubmittedT = getattr(agent, "_Submitted", Exception)
        NonTerminatingT = getattr(agent, "_NonTerminatingException", Exception)
        LimitsExceededT = getattr(agent, "_LimitsExceeded", Exception)

        while True:
            try:
                await asyncio.to_thread(agent.step)
            except NonTerminatingT as e:  # type: ignore[misc]
                # Feed observation back into the agent state and show to user
                note = str(e)
                agent.add_message("user", note)
                await self._client.sessionUpdate(
                    SessionNotification(
                        sessionId=params.sessionId,
                        update=SessionUpdate2(
                            sessionUpdate="agent_message_chunk",
                            content=ContentBlock1(type="text", text=note),
                        ),
                    )
                )
                continue
            except SubmittedT as e:  # type: ignore[misc]
                final_message = str(e)
                # Mirror what DefaultAgent.run does for completion bookkeeping
                agent.add_message("user", final_message)
                break
            except LimitsExceededT as e:  # type: ignore[misc]
                final_message = f"Limits exceeded: {e}"
                agent.add_message("user", final_message)
                break

        # Send the final result text to the client
        await self._client.sessionUpdate(
            SessionNotification(
                sessionId=params.sessionId,
                update=SessionUpdate2(
                    sessionUpdate="agent_message_chunk",
                    content=ContentBlock1(type="text", text=final_message or "(no final output)"),
                ),
            )
        )

        return PromptResponse(stopReason="end_turn")

    async def cancel(self, _params: CancelNotification) -> None:
        # DefaultAgent is synchronous per step; nothing to cancel mid-step here
        return None


async def main() -> None:
    reader, writer = await stdio_streams()
    AgentSideConnection(lambda client: MiniSweACPAgent(client), writer, reader)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
