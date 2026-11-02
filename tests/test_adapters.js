// Tests of the three back-end adapters against a local mock server (no network, no secrets).
// Run: node tests/test_adapters.js   (exit code 1 on any failure)
const http = require("http");
const assert = require("assert");
const { endpoint, makeCaller, getPath, fill } = require("../src/adapters");

const T = { timeoutMs: 5000 };
const redact = (s) => String(s);

function server(handler) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => handler(req, res, body ? JSON.parse(body) : null));
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("openai_chat_sse: streams text, finish reason and chunk count", async () => {
  const srv = await server((req, res, body) => {
    assert.strictEqual(req.headers.authorization, "Bearer k-test");
    assert.strictEqual(body.stream, true);
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    const chunk = (delta, finish) => `data: ${JSON.stringify({ id: "r1", model: "m", choices: [{ delta, finish_reason: finish || null }] })}\n\n`;
    res.write(chunk({ content: "Hello " }));
    res.write(chunk({ content: "[src: kb-1]" }, "stop"));
    res.end("data: [DONE]\n\n");
  });
  const cfg = { api: { type: "openai_chat_sse", base_url_env: "T_BASE", route: "/v1/chat/completions" } };
  const env = { T_BASE: `http://127.0.0.1:${srv.address().port}`, T_KEY: "k-test" };
  const ep = endpoint(cfg, env, { api_key_env: "T_KEY" });
  const r = await makeCaller(ep, "label-x", T, redact)("hi");
  srv.close();
  assert.strictEqual(r.text, "Hello [src: kb-1]");
  assert.strictEqual(r.finish, "stop");
  assert.strictEqual(r.runId, "r1");
  assert.strictEqual(r.nbChunks, 2);
});

test("openai_chat_sse: HTTP error is reported, not thrown", async () => {
  const srv = await server((req, res) => { res.writeHead(400); res.end("model not available"); });
  const cfg = { api: { type: "openai_chat_sse", base_url_env: "T_BASE" } };
  const ep = endpoint(cfg, { T_BASE: `http://127.0.0.1:${srv.address().port}`, T_KEY: "k" }, { api_key_env: "T_KEY" });
  const r = await makeCaller(ep, "bad", T, redact)("hi");
  srv.close();
  assert.strictEqual(r.httpStatus, 400);
  assert.match(r.errorBody, /not available/);
  assert.strictEqual(r.text, "");
});

test("json_http: body template, custom auth header, dotted answer path, finish mapping", async () => {
  const srv = await server((req, res, body) => {
    assert.strictEqual(req.headers["x-api-key"], "k-json");
    assert.strictEqual(body.input, "what?");
    assert.strictEqual(body.model_name, "lbl");
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ id: "m1", content: [{ text: "Answer [3]" }], stop_reason: "end_turn" }));
  });
  const cfg = { api: { type: "json_http", base_url_env: "T_BASE", route: "/ask/{tenant}", auth: { header: "x-api-key", prefix: "" },
    body_template: { input: "{{question}}", model_name: "{{model}}" }, answer_path: "content.0.text", finish_path: "stop_reason", finish_ok: ["end_turn"] } };
  const env = { T_BASE: `http://127.0.0.1:${srv.address().port}`, T_KEY: "k-json", T_TENANT: "acme" };
  const ep = endpoint(cfg, env, { api_key_env: "T_KEY", tenant_env: "T_TENANT" });
  assert.ok(ep.url.endsWith("/ask/acme"));
  const r = await makeCaller(ep, "lbl", T, redact)("what?");
  srv.close();
  assert.strictEqual(r.text, "Answer [3]");
  assert.strictEqual(r.finish, "stop");
  assert.strictEqual(r.runId, "m1");
});

test("json_http: unfinished reason is kept so the status rule can rank it Ko", async () => {
  const srv = await server((req, res) => { res.writeHead(200); res.end(JSON.stringify({ choices: [{ message: { content: "cut" }, finish_reason: "length" }] })); });
  const ep = endpoint({ api: { type: "json_http", base_url_env: "T_BASE" } }, { T_BASE: `http://127.0.0.1:${srv.address().port}`, T_KEY: "k" }, { api_key_env: "T_KEY" });
  const r = await makeCaller(ep, "m", T, redact)("q");
  srv.close();
  assert.strictEqual(r.finish, "length");
});

test("command: question on stdin, answer on stdout, no shell", async () => {
  const cfg = { api: { type: "command", command: [process.execPath, "-e", "process.stdin.on('data',d=>process.stdout.write('echo:'+d+' ['+process.env.HARNESS_MODEL+']'))"] } };
  const ep = endpoint(cfg, {}, {});
  const r = await makeCaller(ep, "lab", T, redact)("ping");
  assert.strictEqual(r.text, "echo:ping [lab]");
  assert.strictEqual(r.finish, "stop");
});

test("command: non-zero exit is an error, not a finished answer", async () => {
  const ep = endpoint({ api: { type: "command", command: [process.execPath, "-e", "process.exit(3)"] } }, {}, {});
  const r = await makeCaller(ep, "m", T, redact)("q");
  assert.strictEqual(r.finish, null);
  assert.match(r.streamError, /exit 3/);
});

test("endpoint: missing variable gives a readable error naming it", () => {
  assert.throws(() => endpoint({ api: { type: "openai_chat_sse", base_url_env: "T_BASE" } }, {}, { api_key_env: "T_KEY" }), /T_BASE/);
  assert.throws(() => endpoint({ api: { type: "openai_chat_sse", base_url_env: "T_BASE" } }, { T_BASE: "http://x" }, { api_key_env: "T_KEY" }), /T_KEY/);
});

test("unknown adapter type fails loudly", () => {
  assert.throws(() => makeCaller({ api: { type: "nope" } }, "m", T, redact), /unknown api.type/);
});

test("helpers: getPath and fill", () => {
  assert.strictEqual(getPath({ a: [{ b: 5 }] }, "a.0.b"), 5);
  assert.deepStrictEqual(fill({ x: ["{{q}}", 1] }, { q: "v" }), { x: ["v", 1] });
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log("ok  ", name); } catch (e) { failed++; console.log("FAIL", name, "-", e.message); }
  }
  console.log(failed ? `${failed} failed` : `${tests.length} passed`);
  globalThis.process.exit(failed ? 1 : 0);
})();
