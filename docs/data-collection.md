# Data collection

## The call

Each question is sent as a **fresh one-message conversation** (no history) unless a question is explicitly a follow-up.
How the call is made depends on the adapter you chose ([adapters.md](adapters.md)); the default is an OpenAI-compatible
streaming chat request. Route, variable names and timeouts are in the config; secrets only in the environment (see `.env.example`).

## What an API often does NOT tell you

Check each point on your back end before relying on it:
- **The served model.** Replies rarely carry a reliable model field, and a model asked "who are you?" may describe another version than the label.
  That is neither proof nor disproof of routing.
- **Structured sources.** In many RAG set-ups sources exist only as text the model wrote; that is why the citation convention is configurable
  ([status-rule.md](status-rule.md)).
- **Token usage.** It may be `null` or absent. Run `src/probe_usage.js` before planning any cost work.

## Label probe (the only routing evidence)

`src/probe_model_label.js` sends one trivial question per candidate label plus an unknown control label.
- A back end that rejects unknown labels makes the probe **discriminating**: an accepted label really exists for that profile, and the control must fail.
  If the control succeeds, the back end ignores the field and the probe proves nothing.
- Two labels can be accepted for one model (e.g. with and without a provider prefix). Decide which one is the truth with the owner of the
  back end (which credential is consumed) and record the choice in `meta.json`. Do not guess.
- A label that does not exist (e.g. a "fast" variant) must be reported as missing, never replaced silently.
- Labels may change between series and a probe can pass or fail after a back-end change: re-probe before each series.

## Journal format (one JSON object per line)

`channel, id, n, theme, question, profile, model, requested_model, start, end, duration_s, ttft_s, response, finish_reason,
n_chunks, http_status, error_shown, request_id, returned_model, unknown_fields, attempts, status`
with `status ∈ {ok, api_error, timeout, empty_response, abnormal_end}`. `channel` is the adapter type. Every attempt is journaled, failed ones included
(they may be billed); the last `ok` line per id is the pass used. `meta.json` records the requested label, the adapter, the question-set fingerprint, the timing
settings and the last 4 characters of the key.

## Operational rules

- Replays resume by skipping ids already `ok`.
- Stop after N consecutive failures (default 3): a systematic failure is a configuration problem, not noise.
- Run long series with sleep prevention (`caffeinate` or equivalent); keep scripts resumable.
- Parallel series are fine for answers, **not for timings**: concurrent load inflates latency. Drop or re-measure timings.
- Never write the key anywhere: redaction in error bodies, `key_tail` only in `meta.json`.
- A provider's own key bypasses retrieval, prompts and guard-rails of the application: never use it for results, only for throw-away diagnostics.
