# Agent Client Protocol - Python SDK

A Python implementation of the Agent Client Protocol (ACP) used by editors like Zed to talk to external agents over stdio.

- Repository: https://github.com/psiace/agent-client-protocol-python
- Docs: https://psiace.github.io/agent-client-protocol-python/

## What this provides

- Typed ACP client/agent primitives (`acp` package under `src/`)
- A runnable example: a bridge that wraps mini-swe-agent as an ACP agent
- Reference implementations under `reference/` for learning and comparison

## Quick start

Install the development environment:

```bash
make install
```

Run quality checks:

```bash
make check
```

Run tests:

```bash
make test
```

## Example: Mini SWE Agent bridge

A minimal ACP bridge for mini-swe-agent is provided under [`examples/mini_swe_agent`](file:///Users/psiace/OSS/agent-client-protocol-python/examples/mini_swe_agent/README.md). It shows how to:

- Parse a prompt from ACP content blocks
- Stream agent output to the client with `session/update`
- Map command execution to `tool_call` and `tool_call_update`

See the example’s README or the docs quickstart for Zed configuration.

## Documentation

- Getting started: [docs/index.md](docs/index.md)
- Quickstart: [docs/quickstart.md](docs/quickstart.md)
- Mini SWE Agent example details: [docs/mini-swe-agent.md](docs/mini-swe-agent.md)

## Notes

- The `reference/` directory contains educational examples and may include optional dependencies. These are not required to use the example bridge.
