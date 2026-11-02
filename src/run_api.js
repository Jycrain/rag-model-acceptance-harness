// Collector: replays a frozen question set against an LLM-backed system (RAG assistant, agent, chat endpoint, CLI) and journals every pass.
// Platform-agnostic: the back end is reached through an adapter chosen in config.json ("api.type": openai_chat_sse | json_http | command),
// see src/adapters.js. No front end, no LLM agent involved.
//
//   node src/run_api.js --config config.json --profile member --model model-a [--only 01,02] [--limit N] [--out runs]
//
// Secrets: base URL, ids and keys come ONLY from the environment (or a git-ignored .env); the names of the variables
//        are declared in the config. Keys are never written to logs (only the last 4 characters, in meta.json).
// Resume: ids already logged with status "ok" are not replayed.
const crypto = require("crypto"), fs = require("fs"), path = require("path");
const { loadEnv, endpoint, makeCaller } = require("./adapters");

const arg = (k) => { const i = process.argv.indexOf("--" + k); return i > -1 ? process.argv[i + 1] : null; };
const cfgPath = arg("config") || process.env.HARNESS_CONFIG || "config.json";
const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
const cfgDir = path.dirname(path.resolve(cfgPath));
const profile = arg("profile"), modelKey = arg("model"), only = arg("only")?.split(","), limit = +arg("limit") || 0, OUT = arg("out") || "runs";
if (!cfg.profiles?.[profile] || !cfg.models?.[modelKey]) {
  console.error(`Usage: node src/run_api.js --config <file> --profile ${Object.keys(cfg.profiles || {}).join("|")} --model ${Object.keys(cfg.models || {}).join("|")} [--only ids] [--limit N] [--out dir]`);
  process.exit(2);
}

const env = loadEnv(cfgPath);
const P = cfg.profiles[profile];
let EP;
try { EP = endpoint(cfg, env, P); } catch (e) { console.error(e.message); process.exit(2); }
const KEY = EP.key || "";
const MODEL_LABEL = arg("model-label") || cfg.models[modelKey].label;   // exact label the back end accepts (see probe_model_label.js)
const T = { pauseMs: 1000, timeoutMs: 120000, retries: 1, consecErrMax: 3, ...(cfg.timing || {}) };

const questionsRaw = fs.readFileSync(path.join(cfgDir, cfg.questions || "questions.json"), "utf8");
const allQuestions = JSON.parse(questionsRaw);
const QHASH = crypto.createHash("sha256").update(allQuestions.map((x) => x.id + "\t" + x.q).join("\n")).digest("hex");
let questions = allQuestions;
if (only) questions = questions.filter((q) => only.includes(q.id));
if (limit) questions = questions.slice(0, limit);

const dir = path.join(cfgDir, OUT, modelKey); fs.mkdirSync(dir, { recursive: true });
const logFile = path.join(dir, `${profile}.jsonl`);
const done = new Set(fs.existsSync(logFile) ? fs.readFileSync(logFile, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)).filter((r) => r.status === "ok").map((r) => r.id) : []);
const metaFile = path.join(dir, "meta.json"), prevMeta = fs.existsSync(metaFile) ? JSON.parse(fs.readFileSync(metaFile, "utf8")) : {};
if (prevMeta.requested_model && prevMeta.requested_model !== MODEL_LABEL) { console.error(`meta.json already records label ${prevMeta.requested_model}; refusing to mix labels in ${dir}`); process.exit(2); }
fs.writeFileSync(metaFile, JSON.stringify({ model: modelKey, requested_model: MODEL_LABEL, channel: EP.api.type, profiles: [...new Set([...(prevMeta.profiles || []), profile])], key_tail: KEY ? "…" + KEY.slice(-4) : null, questions_sha256: QHASH, n_questions: allQuestions.length, timing: T,
  started: prevMeta.started || new Date().toISOString(), invocations: [...(prevMeta.invocations || []), { profile, at: new Date().toISOString(), only: only || null, limit: limit || null }] }, null, 1));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const redact = (s) => (KEY ? String(s).split(KEY).join("<key>") : String(s));

const call = makeCaller(EP, MODEL_LABEL, T, redact);   // adapter chosen by config.api.type (see adapters.js)

(async () => {
  console.log(`Adapter: ${EP.api.type} | profile: ${profile} | requested model: ${MODEL_LABEL}${KEY ? " | key …" + KEY.slice(-4) : ""}`);
  let ok = 0, ko = 0, consecErr = 0;
  for (const q of questions) {
    if (done.has(q.id)) { console.log(q.id, "already done"); continue; }
    let rec = null;
    for (let attempt = 0; attempt <= T.retries && !(rec && rec.status === "ok"); attempt++) {
      if (attempt > 0) await sleep(5000);
      const start = new Date().toISOString(), r = await call(q.q);
      const status = r.httpStatus !== 200 && r.httpStatus !== null ? "api_error" : r.streamError ? "api_error" : r.timeout ? "timeout" : !r.text.trim() ? "empty_response"
        : r.finish !== "stop" ? "abnormal_end" : "ok";
      rec = { channel: EP.api.type, id: q.id, n: q.n, theme: q.theme, question: q.q, profile, model: modelKey, requested_model: MODEL_LABEL, start, end: new Date().toISOString(),
        duration_s: Math.round(r.ms / 100) / 10, ttft_s: r.ttft === null ? null : Math.round(r.ttft / 100) / 10, response: r.text, finish_reason: r.finish, n_chunks: r.nbChunks,
        http_status: r.httpStatus, error_shown: r.errorBody || r.streamError || null, request_id: r.runId, returned_model: r.seenModels || [], unknown_fields: r.unknownFields, attempts: attempt + 1, status };
      fs.appendFileSync(logFile, JSON.stringify(rec) + "\n");   // every attempt is journaled (a failed attempt may be billed)
    }
    rec.status === "ok" ? ok++ : ko++;
    consecErr = rec.status === "ok" ? 0 : consecErr + 1;
    console.log(q.id, rec.status, rec.duration_s + " s", "TTFT " + rec.ttft_s + " s", "(attempt " + rec.attempts + ")");
    if (consecErr >= T.consecErrMax) { console.error(`STOP: ${T.consecErrMax} consecutive failures (last: ${rec.status} ${rec.http_status || ""} ${rec.error_shown || ""}).`); process.exit(4); }
    await sleep(T.pauseMs);
  }
  console.log(`Done: ${ok} ok, ${ko} to review. Log: ${path.relative(process.cwd(), logFile)}`);
})().catch((e) => { console.error(redact(e.message)); process.exit(1); });
