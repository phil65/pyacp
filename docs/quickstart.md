# Quickstart

This repository provides a Python implementation of the Agent Client Protocol (ACP) and a minimal example that bridges mini-swe-agent into an ACP agent.

## Prerequisites

- Python 3.10+
- A virtual environment for this repo (`make install` will create one with uv)
- Zed editor (for running the example agent)

## Install

```bash
make install
```

Run checks:

```bash
make check
```

## Run the Mini SWE Agent bridge in Zed

Install mini-swe-agent into this repo’s venv.

```bash
./.venv/bin/pip install mini-swe-agent
```

Add an agent server to Zed’s `settings.json`:

```json
{
  "agent_servers": {
    "Mini SWE Agent (Python)": {
      "command": "/absolute/path/to/agent-client-protocol-python/.venv/bin/python",
      "args": [
        "/absolute/path/to/agent-client-protocol-python/examples/mini_swe_agent/agent.py"
      ],
      "env": {
        "PYTHONPATH": "/absolute/path/to/agent-client-protocol-python/src",
        "MINI_SWE_MODEL": "openrouter/openai/gpt-4o-mini",
        "MINI_SWE_MODEL_KWARGS": "{\"api_base\":\"https://openrouter.ai/api/v1\"}",
        "OPENROUTER_API_KEY": "sk-or-..."
      }
    }
  }
}
```

In Zed, open the Agents panel and select "Mini SWE Agent (Python)".

For details on behavior and message mapping, see [mini-swe-agent.md](mini-swe-agent.md).
