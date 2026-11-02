// Back-end adapters: the collector is agnostic of the platform. Choose one in config.json under "api".
//
//   "api": { "type": "openai_chat_sse" | "json_http" | "command", ... }
//
//   openai_chat_sse (default)  POST <base><route>, body {model, messages, stream:true, ...api.body}, answer as SSE "chat.completion.chunk".
//                              Works with any OpenAI-compatible endpoint (gateways, RAG platforms, local servers).
//   json_http                  POST <base><route>, one JSON reply. Body from api.body_template ("{{question}}", "{{model}}" are replaced
//                              in every string) or the chat shape. Answer, finish reason and request id are read with dotted paths
//                              (api.answer_path, api.finish_path, api.finish_ok, api.id_path). Fits message-style APIs and custom services.
//   command                    api.command = ["prog", "arg", ...] run WITHOUT a shell; the question on stdin, the answer on stdout,
//                              exit code 0 = finished. HARNESS_MODEL carries the model label. Fits any CLI agent or local script.
//
// Common: api.base_url_env (variable holding the base URL), api.route (placeholders {x} read the variable named by profile.x_env),
// api.auth {header, prefix} (default Authorization: "Bearer "), api.headers, profile.api_key_env.
// Every adapter returns the same record shape, so journals, statuses and comparisons do not depend on the platform.
const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");

const SYSTEM_ENV = globalThis.process.env;

// Variables come from a git-ignored .env next to the config, overridden by the real environment.
function loadEnv(cfgPath) {
  const envFile = path.join(path.dirname(path.resolve(cfgPath)), ".env");
  const lines = fs.existsSync(envFile) ? fs.readFileSync(envFile, "utf8").split("\n") : [];
  const fromFile = Object.fromEntries(lines.map((l) => l.match(/^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)).filter(Boolean).map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")]));
  return { ...fromFile, ...SYSTEM_ENV };
}

function apiConf(cfg) {
  const a = cfg.api || {};
  return {
    type: a.type || "openai_chat_sse",
    base_url_env: a.base_url_env || cfg.base_url_env || "RAG_BASE_URL",
    route: a.route || cfg.route || "/v1/chat/completions",
    auth: { header: "Authorization", prefix: "Bearer ", ...(a.auth || {}) },
    headers: a.headers || {},
    body: a.body || {},
    body_template: a.body_template || null,
    answer_path: a.answer_path || "choices.0.message.content",
    finish_path: a.finish_path || "choices.0.finish_reason",
    finish_ok: a.finish_ok || ["stop"],
    id_path: a.id_path || "id",
    command: a.command || null,
  };
}

const getPath = (o, p) => String(p).split(".").reduce((x, k) => (x == null ? undefined : x[k]), o);
const fill = (v, vars) => {
  if (typeof v === "string") return v.replace(/\{\{(\w+)\}\}/g, (m, k) => (k in vars ? vars[k] : m));
  if (Array.isArray(v)) return v.map((x) => fill(x, vars));
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, fill(x, vars)]));
  return v;
};

// Resolves URL, headers and key for one profile. Throws a readable error naming the missing variable.
function endpoint(cfg, env, P) {
  const api = apiConf(cfg);
  if (api.type === "command") return { api, url: null, headers: {}, key: env[P.api_key_env] || "" };
  const base = env[api.base_url_env];
  if (!base) throw new Error(`Missing ${api.base_url_env} in the environment`);
  const route = api.route.replace(/\{(\w+)\}/g, (m, k) => {
    const v = env[P[k + "_env"]];
    if (v === undefined) throw new Error(`Missing ${P[k + "_env"] || "profile." + k + "_env"} in the environment (route placeholder {${k}})`);
    return v;
  });
  const key = env[P.api_key_env];
  if (P.api_key_env && !key) throw new Error(`Missing ${P.api_key_env} in the environment`);
  const headers = { "Content-Type": "application/json", ...api.headers };
  if (key) headers[api.auth.header] = api.auth.prefix + key;
  return { api, url: base.replace(/\/$/, "") + route, headers, key: key || "" };
}

const blank = () => ({ text: "", ttft: null, ms: 0, finish: null, nbChunks: 0, streamError: null, runId: null, httpStatus: null, errorBody: null, timeout: false, unknownFields: [], seenModels: [] });

function makeCaller(ep, label, T, redact) {
  const { api } = ep;
  const chatBody = (q, stream) => ({ model: label, messages: [{ role: "user", content: q }], stream, ...api.body });

  async function sse(question) {
    const ac = new AbortController();
    const kill = setTimeout(() => ac.abort(), T.timeoutMs);
    const t0 = Date.now();
    const r = blank();
    const models = new Set();
    const unknown = new Set();
    let tLast = null;
    try {
      const res = await fetch(ep.url, { method: "POST", signal: ac.signal, headers: { ...ep.headers, Accept: "text/event-stream" }, body: JSON.stringify(chatBody(question, true)) });
      r.httpStatus = res.status;
      if (!res.ok) { r.errorBody = redact((await res.text()).slice(0, 300)); r.ms = Date.now() - t0; return r; }
      const dec = new TextDecoder();
      let buf = "";
      for await (const piece of res.body) {
        buf += dec.decode(piece, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 1);
          if (!line.startsWith("data:")) continue;
          const d = line.slice(5).trim();
          if (!d || d === "[DONE]") continue;
          let j;
          try { j = JSON.parse(d); } catch { continue; }
          if (j.error) { r.streamError = redact(JSON.stringify(j.error)).slice(0, 300); continue; }
          r.runId = r.runId || j.id || null;
          r.nbChunks++;
          if (j.model) models.add(j.model);
          for (const k of Object.keys(j)) if (!["id", "object", "created", "choices", "model"].includes(k)) unknown.add(k);
          for (const c of j.choices || []) {
            const t = c.delta?.content;
            if (t) { r.text += t; tLast = Date.now(); if (r.ttft === null && r.text.trim()) r.ttft = tLast - t0; }
            if (c.finish_reason) r.finish = c.finish_reason;
          }
        }
      }
      r.ms = (tLast || Date.now()) - t0;
    } catch (e) {
      r.ms = Date.now() - t0;
      r.timeout = ac.signal.aborted;
      r.streamError = ac.signal.aborted ? null : redact(e.message).slice(0, 300);
    } finally { clearTimeout(kill); }
    r.unknownFields = [...unknown];
    r.seenModels = [...models];
    return r;
  }

  async function json(question) {
    const ac = new AbortController();
    const kill = setTimeout(() => ac.abort(), T.timeoutMs);
    const t0 = Date.now();
    const r = blank();
    try {
      const body = api.body_template ? fill(api.body_template, { question, model: label }) : chatBody(question, false);
      const res = await fetch(ep.url, { method: "POST", signal: ac.signal, headers: ep.headers, body: JSON.stringify(body) });
      r.httpStatus = res.status;
      const raw = await res.text();
      if (!res.ok) { r.errorBody = redact(raw.slice(0, 300)); return r; }
      let j;
      try { j = JSON.parse(raw); } catch { r.streamError = "reply is not JSON"; return r; }
      const t = getPath(j, api.answer_path);
      r.text = typeof t === "string" ? t : t == null ? "" : JSON.stringify(t);
      const f = getPath(j, api.finish_path);
      // no finish field at all: a non-empty reply counts as finished
      r.finish = f == null ? (r.text.trim() ? "stop" : null) : api.finish_ok.includes(f) ? "stop" : String(f);
      r.runId = getPath(j, api.id_path) ?? null;
      r.nbChunks = 1;
      if (j.model) r.seenModels = [String(j.model)];
    } catch (e) {
      r.timeout = ac.signal.aborted;
      r.streamError = ac.signal.aborted ? null : redact(e.message).slice(0, 300);
    } finally { clearTimeout(kill); r.ms = Date.now() - t0; }
    return r;
  }

  function command(question) {
    return new Promise((resolve) => {
      const t0 = Date.now();
      const r = blank();
      if (!Array.isArray(api.command) || !api.command.length) { r.streamError = "api.command must be a non-empty array"; return resolve(r); }
      const [prog, ...rest] = api.command;
      const opts = { timeout: T.timeoutMs, maxBuffer: 16 * 1024 * 1024, env: { ...SYSTEM_ENV, HARNESS_MODEL: label } };
      const child = execFile(prog, rest.map((a) => fill(a, { model: label })), opts, (err, stdout, stderr) => {
        r.ms = Date.now() - t0;
        r.text = stdout || "";
        r.nbChunks = 1;
        if (err && err.killed) r.timeout = true;
        else if (err) r.streamError = redact(`exit ${err.code}: ${stderr || err.message}`).slice(0, 300);
        else r.finish = "stop";
        resolve(r);
      });
      child.stdin.on("error", () => {});
      child.stdin.end(question);
    });
  }

  const table = { openai_chat_sse: sse, json_http: json, command };
  if (!table[api.type]) throw new Error(`unknown api.type: ${api.type} (expected ${Object.keys(table).join(" | ")})`);
  return table[api.type];
}

module.exports = { loadEnv, apiConf, endpoint, makeCaller, getPath, fill };
