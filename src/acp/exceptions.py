from __future__ import annotations

from typing import Any


class RequestError(Exception):
    """Raised when a JSON-RPC request fails."""

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    @staticmethod
    def parse_error(data: dict[str, Any] | None = None) -> RequestError:
        return RequestError(-32700, "Parse error", data)

    @staticmethod
    def invalid_request(data: dict[str, Any] | None = None) -> RequestError:
        return RequestError(-32600, "Invalid request", data)

    @staticmethod
    def method_not_found(method: str) -> RequestError:
        return RequestError(-32601, "Method not found", {"method": method})

    @staticmethod
    def invalid_params(data: dict[str, Any] | None = None) -> RequestError:
        return RequestError(-32602, "Invalid params", data)

    @staticmethod
    def internal_error(data: dict[str, Any] | None = None) -> RequestError:
        return RequestError(-32603, "Internal error", data)

    @staticmethod
    def auth_required(data: dict[str, Any] | None = None) -> RequestError:
        return RequestError(-32000, "Authentication required", data)

    def to_error_obj(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "data": self.data}
