// Label probe: finds which `model` string a back end really accepts.
//
//   node src/probe_model_label.js --config config.json --profile member label-1 label-2 ...
//
// Why: an API rarely says which model served an answer. The only machine-checkable evidence of routing is that the
// back end ACCEPTS a label. A back end that rejects unknown labels (an HTTP 4xx) makes this probe discriminating:
// an unknown control label MUST fail, otherwise the probe proves nothing.
// One trivial question per label, so the cost is a few tokens. The key is never printed.
// Works with the HTTP adapters (openai_chat_sse, json_http); the command adapter has no label to probe.
const fs = require("fs");
const { loadEnv, endpoint, makeCaller } = require("./adapters");

const arg = (k) => { const i = process.argv.indexOf("--" + k); return i > -1 ? process.argv[i + 1] : null; };
const cfgPath = arg("config") || globalThis.process.env.HARNESS_CONFIG || "config.json";
const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
const profile = arg("profile");
const labels = process.argv.slice(2).filter((a, i, v) => !a.startsWith("--") && !(v[i - 1] || "").startsWith("--"));
const P = cfg.profiles && cfg.profiles[profile];
if (!P) { console.error("Usage: node src/probe_model_label.js --config <file> --profile <name> <label>..."); process.exit(2); }

let ep;
try { ep = endpoint(cfg, loadEnv(cfgPath), P); } catch (e) { console.error(e.message); process.exit(2); }
if (ep.api.type === "command") { console.error("The command adapter has no model label to probe."); process.exit(2); }
const redact = (s) => (ep.key ? String(s).split(ep.key).join("<key>") : String(s));

(async () => {
  let controlAccepted = false;
  const control = "definitely-not-a-model-" + labels.length;
  for (const label of [...labels, control]) {
    const call = makeCaller(ep, label, { timeoutMs: 60000 }, redact);
    const t0 = Date.now();
    const r = await call("Say OK.");
    const accepted = r.httpStatus !== null && r.httpStatus < 400 && !r.streamError && !r.errorBody;
    const why = accepted ? "" : (r.errorBody || r.streamError || "").slice(0, 160);
    globalThis.process.stdout.write(`${String(r.httpStatus).padEnd(4)} ${((Date.now() - t0) / 1000).toFixed(1).padStart(5)} s  ${label}  ${why}\n`);
    if (label === control && accepted) controlAccepted = true;
  }
  if (controlAccepted) {
    console.error("WARNING: the unknown control label was ACCEPTED: this back end ignores the model field, the probe proves nothing.");
    process.exit(1);
  }
})();
