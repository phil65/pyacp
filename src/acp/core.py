from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from .meta import AGENT_METHODS, CLIENT_METHODS, PROTOCOL_VERSION  # noqa: F401
from .schema import (
    AuthenticateRequest,
    CancelNotification,
    InitializeRequest,
    InitializeResponse,
    LoadSessionRequest,
    NewSessionRequest,
    NewSessionResponse,
    PromptRequest,
    PromptResponse,
    ReadTextFileRequest,
    ReadTextFileResponse,
    RequestPermissionRequest,
    RequestPermissionResponse,
    SessionNotification,
    WriteTextFileRequest,
)

# --- JSON-RPC 2.0 error helpers -------------------------------------------------

_AGENT_CONNECTION_ERROR = "AgentSideConnection requires asyncio StreamWriter/StreamReader"
_CLIENT_CONNECTION_ERROR = "ClientSideConnection requires asyncio StreamWriter/StreamReader"


class RequestError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    @staticmethod
    def parse_error(data: dict | None = None) -> RequestError:
        return RequestError(-32700, "Parse error", data)

    @staticmethod
    def invalid_request(data: dict | None = None) -> RequestError:
        return RequestError(-32600, "Invalid request", data)

    @staticmethod
    def method_not_found(method: str) -> RequestError:
        return RequestError(-32601, "Method not found", {"method": method})

    @staticmethod
    def invalid_params(data: dict | None = None) -> RequestError:
        return RequestError(-32602, "Invalid params", data)

    @staticmethod
    def internal_error(data: dict | None = None) -> RequestError:
        return RequestError(-32603, "Internal error", data)

    @staticmethod
    def auth_required(data: dict | None = None) -> RequestError:
        return RequestError(-32000, "Authentication required", data)

    def to_error_obj(self) -> dict:
        return {"code": self.code, "message": str(self), "data": self.data}


# --- Transport & Connection ------------------------------------------------------

JsonValue = Any
MethodHandler = Callable[[str, JsonValue | None], Awaitable[JsonValue | None]]


@dataclass(slots=True)
class _Pending:
    future: asyncio.Future[Any]


class Connection:
    """
    Minimal JSON-RPC 2.0 connection over newline-delimited JSON frames using
    asyncio streams. KISS: only supports StreamReader/StreamWriter.

    - Outgoing messages always include {"jsonrpc": "2.0"}
    - Requests and notifications are dispatched to a single async handler
    - Responses resolve pending futures by numeric id
    """

    def __init__(
        self,
        handler: MethodHandler,
        writer: asyncio.StreamWriter,
        reader: asyncio.StreamReader,
    ) -> None:
        self._handler = handler
        self._writer = writer
        self._reader = reader
        self._next_request_id = 0
        self._pending: dict[int, _Pending] = {}
        self._write_lock = asyncio.Lock()
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def close(self) -> None:
        if not self._recv_task.done():
            self._recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._recv_task
        # Do not close writer here; lifecycle owned by caller

    # --- IO loops ----------------------------------------------------------------

    async def _receive_loop(self) -> None:
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except Exception:
                    # No id to reply to -> ignore; with id -> send parse error
                    # Try to peek id; if not possible, skip
                    try:
                        maybe = json.loads(line.decode("utf-8", errors="ignore"))
                        msg_id = maybe.get("id") if isinstance(maybe, dict) else None
                    except Exception:
                        msg_id = None
                    if msg_id is not None:
                        await self._send_obj({
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": RequestError.parse_error().to_error_obj(),
                        })
                    continue

                await self._process_message(message)
        except asyncio.CancelledError:
            return

    async def _process_message(self, message: dict) -> None:
        method = message.get("method")
        has_id = "id" in message

        if method is not None and has_id:
            await self._handle_request(message)
        elif method is not None and not has_id:
            await self._handle_notification(message)
        elif has_id:
            await self._handle_response(message)

    async def _handle_request(self, message: dict) -> None:
        """Handle JSON-RPC request."""
        payload = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            result = await self._handler(message["method"], message.get("params"))
            if isinstance(result, BaseModel):
                result = result.model_dump()
            payload["result"] = result if result is not None else None
        except RequestError as re:
            payload["error"] = re.to_error_obj()
        except ValidationError as ve:
            payload["error"] = RequestError.invalid_params({"errors": ve.errors()}).to_error_obj()
        except Exception as err:
            try:
                data = json.loads(str(err))
            except Exception:
                data = {"details": str(err)}
            payload["error"] = RequestError.internal_error(data).to_error_obj()
        await self._send_obj(payload)

    async def _handle_notification(self, message: dict) -> None:
        """Handle JSON-RPC notification."""
        with contextlib.suppress(Exception):
            # Best-effort; notifications do not produce responses
            await self._handler(message["method"], message.get("params"))

    async def _handle_response(self, message: dict) -> None:
        """Handle JSON-RPC response."""
        fut = self._pending.pop(message["id"], None)
        if fut is None:
            return
        if "result" in message:
            fut.future.set_result(message.get("result"))
        elif "error" in message:
            err = message.get("error") or {}
            fut.future.set_exception(
                RequestError(err.get("code", -32603), err.get("message", "Error"), err.get("data"))
            )
        else:
            fut.future.set_result(None)

    async def _send_obj(self, obj: dict) -> None:
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        async with self._write_lock:
            self._writer.write(data)
            with contextlib.suppress(ConnectionError, RuntimeError):
                # Peer closed; let reader loop end naturally
                await self._writer.drain()

    # --- Public API --------------------------------------------------------------

    async def send_request(self, method: str, params: JsonValue | None = None) -> Any:
        req_id = self._next_request_id
        self._next_request_id += 1
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = _Pending(fut)
        await self._send_obj({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        return await fut

    async def send_notification(self, method: str, params: JsonValue | None = None) -> None:
        await self._send_obj({"jsonrpc": "2.0", "method": method, "params": params})


# --- High-level Agent/Client wrappers -------------------------------------------


class Client(Protocol):
    async def requestPermission(self, params: RequestPermissionRequest) -> RequestPermissionResponse: ...

    async def sessionUpdate(self, params: SessionNotification) -> None: ...

    async def writeTextFile(self, params: WriteTextFileRequest) -> None: ...

    async def readTextFile(self, params: ReadTextFileRequest) -> ReadTextFileResponse: ...

    # Optional/unstable terminal methods
    async def createTerminal(self, params: Any) -> Any: ...

    async def terminalOutput(self, params: Any) -> Any: ...

    async def releaseTerminal(self, params: Any) -> None: ...

    async def waitForTerminalExit(self, params: Any) -> Any: ...

    async def killTerminal(self, params: Any) -> None: ...


class Agent(Protocol):
    async def initialize(self, params: InitializeRequest) -> InitializeResponse: ...

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse: ...

    async def loadSession(self, params: LoadSessionRequest) -> None: ...

    async def authenticate(self, params: AuthenticateRequest) -> None: ...

    async def prompt(self, params: PromptRequest) -> PromptResponse: ...

    async def cancel(self, params: CancelNotification) -> None: ...


class AgentSideConnection:
    """
    Agent-side connection. Use when you implement the Agent and need to talk to a Client.

    Parameters:
    - to_agent: factory that receives this connection and returns your Agent implementation
    - input: asyncio.StreamWriter (local -> peer)
    - output: asyncio.StreamReader (peer -> local)
    """

    def __init__(
        self,
        to_agent: Callable[[AgentSideConnection], Agent],
        input_stream: Any,
        output_stream: Any,
    ) -> None:
        agent = to_agent(self)

        async def handler(method: str, params: Any) -> Any:
            if method == AGENT_METHODS["initialize"]:
                p = InitializeRequest.model_validate(params)
                return await agent.initialize(p)
            if method == AGENT_METHODS["session_new"]:
                p = NewSessionRequest.model_validate(params)
                return await agent.newSession(p)
            if method == AGENT_METHODS["session_load"]:
                if not hasattr(agent, "loadSession"):
                    raise RequestError.method_not_found(method)
                p = LoadSessionRequest.model_validate(params)
                return await agent.loadSession(p)
            if method == AGENT_METHODS["authenticate"]:
                p = AuthenticateRequest.model_validate(params)
                return await agent.authenticate(p)
            if method == AGENT_METHODS["session_prompt"]:
                p = PromptRequest.model_validate(params)
                return await agent.prompt(p)
            if method == AGENT_METHODS["session_cancel"]:
                p = CancelNotification.model_validate(params)
                return await agent.cancel(p)
            raise RequestError.method_not_found(method)

        if not isinstance(input_stream, asyncio.StreamWriter) or not isinstance(output_stream, asyncio.StreamReader):
            raise TypeError(_AGENT_CONNECTION_ERROR)
        self._conn = Connection(handler, input_stream, output_stream)

    # client-bound methods (agent -> client)
    async def sessionUpdate(self, params: SessionNotification) -> None:
        await self._conn.send_notification(
            CLIENT_METHODS["session_update"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )

    async def requestPermission(self, params: RequestPermissionRequest) -> RequestPermissionResponse:
        resp = await self._conn.send_request(
            CLIENT_METHODS["session_request_permission"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )
        return RequestPermissionResponse.model_validate(resp)

    async def readTextFile(self, params: ReadTextFileRequest) -> ReadTextFileResponse:
        resp = await self._conn.send_request(
            CLIENT_METHODS["fs_read_text_file"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )
        return ReadTextFileResponse.model_validate(resp)

    async def writeTextFile(self, params: WriteTextFileRequest) -> None:
        await self._conn.send_request(
            CLIENT_METHODS["fs_write_text_file"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )

    async def createTerminal(self, params: Any) -> TerminalHandle:
        resp = await self._conn.send_request(CLIENT_METHODS["terminal_create"], params)
        return TerminalHandle(resp["terminalId"], params["sessionId"], self._conn)


class ClientSideConnection:
    """
    Client-side connection. Use when you implement the Client and need to talk to an Agent.

    Parameters:
    - to_client: factory that receives this connection and returns your Client implementation
    - input: asyncio.StreamWriter (local -> peer)
    - output: asyncio.StreamReader (peer -> local)
    """

    def __init__(
        self,
        to_client: Callable[[Agent], Client],
        input_stream: Any,
        output_stream: Any,
    ) -> None:
        if not isinstance(input_stream, asyncio.StreamWriter) or not isinstance(output_stream, asyncio.StreamReader):
            raise TypeError(_CLIENT_CONNECTION_ERROR)

        # Build client first so handler can delegate
        client = to_client(self)  # type: ignore[arg-type]
        handler = self._create_handler(client)
        self._conn = Connection(handler, input_stream, output_stream)

    def _create_handler(self, client: Client) -> MethodHandler:
        """Create the method handler for client-side connection."""

        async def handler(method: str, params: Any) -> Any:
            return await self._handle_client_method(client, method, params)

        return handler

    async def _handle_client_method(self, client: Client, method: str, params: Any) -> Any:
        """Handle client method calls."""
        if method == CLIENT_METHODS["fs_write_text_file"]:
            p = WriteTextFileRequest.model_validate(params)
            return await client.writeTextFile(p)
        if method == CLIENT_METHODS["fs_read_text_file"]:
            p = ReadTextFileRequest.model_validate(params)
            return await client.readTextFile(p)
        if method == CLIENT_METHODS["session_request_permission"]:
            p = RequestPermissionRequest.model_validate(params)
            return await client.requestPermission(p)
        if method == CLIENT_METHODS["session_update"]:
            p = SessionNotification.model_validate(params)
            return await client.sessionUpdate(p)
        if method == CLIENT_METHODS["terminal_create"]:
            return await client.createTerminal(params)
        if method == CLIENT_METHODS["terminal_output"]:
            return await client.terminalOutput(params)
        if method == CLIENT_METHODS["terminal_release"]:
            return await client.releaseTerminal(params)
        if method == CLIENT_METHODS["terminal_wait_for_exit"]:
            return await client.waitForTerminalExit(params)
        if method == CLIENT_METHODS["terminal_kill"]:
            return await client.killTerminal(params)
        raise RequestError.method_not_found(method)

    # agent-bound methods (client -> agent)
    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        resp = await self._conn.send_request(
            AGENT_METHODS["initialize"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )
        return InitializeResponse.model_validate(resp)

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        resp = await self._conn.send_request(
            AGENT_METHODS["session_new"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )
        return NewSessionResponse.model_validate(resp)

    async def loadSession(self, params: LoadSessionRequest) -> None:
        await self._conn.send_request(
            AGENT_METHODS["session_load"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )

    async def authenticate(self, params: AuthenticateRequest) -> None:
        await self._conn.send_request(
            AGENT_METHODS["authenticate"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        resp = await self._conn.send_request(
            AGENT_METHODS["session_prompt"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )
        return PromptResponse.model_validate(resp)

    async def cancel(self, params: CancelNotification) -> None:
        await self._conn.send_notification(
            AGENT_METHODS["session_cancel"],
            params.model_dump(exclude_none=True, exclude_defaults=True),
        )


class TerminalHandle:
    def __init__(self, terminal_id: str, session_id: str, conn: Connection) -> None:
        self.id = terminal_id
        self._session_id = session_id
        self._conn = conn

    async def current_output(self) -> dict:
        return await self._conn.send_request(
            CLIENT_METHODS["terminal_output"],
            {"sessionId": self._session_id, "terminalId": self.id},
        )

    async def wait_for_exit(self) -> dict:
        return await self._conn.send_request(
            CLIENT_METHODS["terminal_wait_for_exit"],
            {"sessionId": self._session_id, "terminalId": self.id},
        )

    async def kill(self) -> None:
        await self._conn.send_request(
            CLIENT_METHODS["terminal_kill"],
            {"sessionId": self._session_id, "terminalId": self.id},
        )

    async def release(self) -> None:
        await self._conn.send_request(
            CLIENT_METHODS["terminal_release"],
            {"sessionId": self._session_id, "terminalId": self.id},
        )
