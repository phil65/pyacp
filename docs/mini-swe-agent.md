# Mini SWE Agent bridge

This example wraps mini-swe-agent behind ACP so Zed can run it as an external agent over stdio.

## Behavior

- Prompts: text blocks are concatenated into a single task string; referenced resources (`resource_link` / `resource`) are surfaced as hints in the task.
- Streaming: incremental text is sent via `session/update` with `agent_message_chunk`.
- Tool calls: when the agent executes a shell command, the bridge sends:
  - `tool_call` with `kind=execute`, pending status, and a bash code block containing the command
  - `tool_call_update` upon completion, including output and a `rawOutput` object with `output` and `returncode`
- Final result: on task submission (mini-swe-agent prints `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` as the first line), a final `agent_message_chunk` with the submission content is sent.

Non-terminating events (e.g. user rejection or timeouts) are surfaced both as a `tool_call_update` with `status=cancelled|failed` and as a text chunk so the session can continue.

## Configuration

Environment variables set in the Zed server config control the model:

- `MINI_SWE_MODEL`: model ID (e.g. `openrouter/openai/gpt-4o-mini`)
- `MINI_SWE_MODEL_KWARGS`: JSON string of extra parameters (e.g. `{ "api_base": "https://openrouter.ai/api/v1" }`)
- Vendor API keys (e.g. `OPENROUTER_API_KEY`) must be present in the environment

If `mini-swe-agent` is not installed in the venv, the bridge attempts to import a vendored reference copy under `reference/mini-swe-agent/src`.

## Files

- Example entry: [`examples/mini_swe_agent/agent.py`](https://github.com/psiace/agent-client-protocol-python/blob/main/examples/mini_swe_agent/agent.py)
