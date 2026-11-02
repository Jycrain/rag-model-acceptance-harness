# Adapters: reaching any back end

The collector (`src/run_api.js`) never knows your platform. It calls an **adapter** chosen in `config.json`, and every adapter returns
the same record, so journals, statuses, comparisons and audits are identical whatever sits behind.

## Choosing one

| Your back end | `api.type` | Notes |
|---|---|---|
| OpenAI-compatible chat endpoint (gateways, many RAG platforms, local model servers) | `openai_chat_sse` (default) | streams `chat.completion.chunk` events; gives time-to-first-token |
| Any other HTTP API returning one JSON reply (message-style APIs, custom services) | `json_http` | body template + dotted paths for answer, finish reason, request id |
| A CLI agent, a script, a library you can only call locally | `command` | no shell; question on stdin, answer on stdout, exit 0 = finished |
| Something else | write one (30 lines, see `makeCaller` in `src/adapters.js`) | return the common record shape |

## Common settings (`api` block)

```json
{
  "api": {
    "type": "openai_chat_sse",
    "base_url_env": "RAG_BASE_URL",
    "route": "/v1/chat/completions",
    "auth": { "header": "Authorization", "prefix": "Bearer " },
    "headers": {},
    "body": {}
  }
}
```
- Secrets and endpoints only in the environment or a git-ignored `.env`; the config holds the **names** of the variables.
- `route` may hold placeholders such as `{tenant}`: they read the variable named by `profile.tenant_env`.
- `profile.api_key_env` names the key variable; the key is sent in `auth.header` and never logged (`meta.json` keeps its last 4 characters).
- `api.body` adds fixed fields to the request (temperature, retrieval options, a system prompt reference…). Keep them identical across series.

## `json_http` example (message-style API)

```json
{
  "api": {
    "type": "json_http", "base_url_env": "RAG_BASE_URL", "route": "/v1/messages",
    "auth": { "header": "x-api-key", "prefix": "" },
    "headers": { "version": "2024-01-01" },
    "body_template": { "model": "{{model}}", "max_tokens": 1024, "messages": [{ "role": "user", "content": "{{question}}" }] },
    "answer_path": "content.0.text", "finish_path": "stop_reason", "finish_ok": ["end_turn"], "id_path": "id"
  }
}
```
A finish reason outside `finish_ok` is kept as-is, so the status rule ranks the pass Ko (truncated). With no finish field, a non-empty reply counts as finished.

## `command` example (local agent or script)

```json
{ "api": { "type": "command", "command": ["./my-agent.sh", "--model", "{{model}}"] } }
```
The program receives the question on stdin and must print the answer on stdout; `HARNESS_MODEL` also carries the label. A non-zero exit or a timeout is a failed pass.
For a CLI agent that needs a working directory or flags, wrap it in a small script and point `command` at it.

## Minimal configs, paths, environment

| `api.type` | Required | Optional |
|---|---|---|
| `openai_chat_sse` | `base_url_env`, profile `api_key_env` | `route` (default `/v1/chat/completions`), `auth`, `headers`, `body` |
| `json_http` | `base_url_env`, `route`, `answer_path` (default `choices.0.message.content`) | `body_template` (default: chat shape), `finish_path`, `finish_ok` (any JSON values, e.g. `[true]` for a `done` flag), `id_path`, `auth`, `headers`; omit `api_key_env` for an unauthenticated API |
| `command` | `command` (an array) | `api_key_env` is ignored; the program must be executable (`chmod +x`) |

`body_template` accepts `{{question}}` and `{{model}}` in any string. Always required in the config: `profiles`, `models`, `series`, `questions`; `prices_per_mtok` and `cost_assumptions` only for `cost_estimate.py`.

- **Paths**: `questions`, series `dir` and `validated_conflicts` resolve relative to the config file, not to the current directory. `compare.py` writes `stats.json` to the current directory unless you pass `--out`.
- **Environment**: variables are read from a `.env` file next to the config (loaded by the collector and the probes) and from the real environment, which wins.
- **A failed first run is journaled** like any other. After a configuration error, delete `runs/<series>/` (or use a new `--out`) before re-running, otherwise the failed lines stay in the journal.
- **Comparing two different back ends**: one config per back end only works for side-by-side tables if they share the question set; simplest is ONE config with one shared `api` block and several `models`/`series`. For genuinely different APIs, run one config each (separate directories, `--out stats-<name>.json`) and compare the stats files by hand: `compare.py` does not merge configs.

## What every adapter guarantees
Every attempt is journaled (failed ones too: they may be billed); the requested label is recorded on every line and in `meta.json`; resume skips ids already `ok`;
3 consecutive failures stop the run; the question-set fingerprint is stored. Tested by `node tests/test_adapters.js` (mock server) and `python tests/test_collect_e2e.py`.
