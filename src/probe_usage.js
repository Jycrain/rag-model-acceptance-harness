// Usage probe: does the back end return a token count?
//
//   node src/probe_model_label.js is for routing; this one is for cost:
//   node src/probe_usage.js --config config.json --profile member --model model-a
//
// Four trivial requests (non-stream and stream, with and without stream_options.include_usage) on an OpenAI-compatible endpoint.
// Prints only the top-level keys of the reply and the value of `usage`, never the key. If `usage` is absent or null on your back end
// (some back ends return null), cost can only be estimated (src/cost_estimate.py) or read from the
// platform / provider console. For other API shapes, check the reply of your back end by hand.
const fs = require("fs");
const { loadEnv, endpoint } = require("./adapters");

const arg = (k) => { const i = process.argv.indexOf("--" + k); return i > -1 ? process.argv[i + 1] : null; };
const cfgPath = arg("config") || globalThis.process.env.HARNESS_CONFIG || "config.json";
const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
const P = cfg.profiles && cfg.profiles[arg("profile")];
const label = cfg.models && cfg.models[arg("model")] && cfg.models[arg("model")].label;
if (!P || !label) { console.error("Usage: node src/probe_usage.js --config <file> --profile <name> --model <key>"); process.exit(2); }

let ep;
try { ep = endpoint(cfg, loadEnv(cfgPath), P); } catch (e) { console.error(e.message); process.exit(2); }
if (ep.api.type !== "openai_chat_sse") { console.error("probe_usage.js supports the openai_chat_sse adapter only; inspect other back ends by hand."); process.exit(2); }

(async () => {
  for (const [stream, include] of [[false, false], [true, false], [false, true], [true, true]]) {
    const body = { model: label, messages: [{ role: "user", content: "Answer in one sentence: what is this service for?" }], stream, ...ep.api.body };
    if (include) body.stream_options = { include_usage: true };
    const res = await fetch(ep.url, { signal: AbortSignal.timeout(60000), method: "POST", headers: ep.headers, body: JSON.stringify(body) });
    const txt = await res.text();
    const keys = new Set();
    let usage = "absent";
    const pieces = stream ? txt.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()) : [txt];
    for (const piece of pieces) {
      try {
        const j = JSON.parse(piece);
        Object.keys(j).forEach((k) => keys.add(k));
        if ("usage" in j && j.usage) usage = JSON.stringify(j.usage);
        else if ("usage" in j && usage === "absent") usage = "null";
      } catch { /* not JSON: ignore */ }
    }
    console.log(`stream=${stream} include_usage=${include} HTTP ${res.status} keys=[${[...keys]}] usage=${usage}`);
  }
})();
