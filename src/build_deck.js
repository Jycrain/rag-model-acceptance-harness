// Builds a short results deck from stats.json ONLY (no number is typed here). Requires: npm install (pptxgenjs).
//   node src/build_deck.js --stats stats.json --config examples/demo/config.json --out deck.pptx --title "Model comparison"
// Slides: 1 title, 2 results table (3 columns per profile: Ok / partial / Ko) + column legend, 3 sources-vs-no-source bars, 4 method and limits.
// Guards: refuses to build if stats.controls_ok is false or if a series total does not equal the sum of its profiles.
const fs = require("fs"), path = require("path");
const PptxGenJS = require("pptxgenjs");
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > -1 ? process.argv[i + 1] : d; };
const stats = JSON.parse(fs.readFileSync(arg("stats", "stats.json"), "utf8"));
const cfg = JSON.parse(fs.readFileSync(arg("config", process.env.HARNESS_CONFIG || "config.json"), "utf8"));
const title = arg("title", "Model comparison"), out = arg("out", "deck.pptx");
if (!stats.controls_ok) { console.error("stats.controls_ok is false: refusing to build"); process.exit(1); }
const names = Object.keys(stats.series), profiles = Object.keys(cfg.profiles);
for (const n of names) {
  const s = stats.series[n];
  const sum = (k) => profiles.reduce((a, p) => a + s.by_profile[p][k], 0);
  if (["ok", "partial", "ko", "n"].some((k) => sum(k) !== s.total[k])) { console.error(`${n}: total != sum of profiles`); process.exit(1); }
}
const label = (n) => cfg.models[cfg.series[n].model]?.name || n;
const C = { ok: ["C8F5D6", "0D5A2E"], partial: ["FFB95C", "3D2100"], ko: ["FFDAD6", "BA1A1A"], ink: "1F1F1F", muted: "6B6B6B" };

const pptx = new PptxGenJS(); pptx.layout = "LAYOUT_WIDE"; pptx.title = title;
const base = (heading) => { const s = pptx.addSlide(); s.addText(heading, { x: 0.5, y: 0.3, w: 12.3, h: 0.7, fontSize: 26, bold: true, color: C.ink }); return s; };

let s = pptx.addSlide();
s.addText(title, { x: 0.8, y: 2.3, w: 11.5, h: 1.2, fontSize: 40, bold: true, color: C.ink });
s.addText(`${stats.series[names[0]].total.n} passes per series · ${names.length} series`, { x: 0.8, y: 3.6, w: 11.5, h: 0.6, fontSize: 20, color: C.muted });

s = base("Results by model and profile");
const head = [{ text: "Model", options: { bold: true } }];
for (const p of profiles) for (const k of ["Ok", "Ok - partial", "Ko"]) head.push({ text: `${p}: ${k}`, options: { bold: true, fontSize: 10 } });
const rows = [head];
for (const n of names) {
  const row = [{ text: label(n) }];
  for (const p of profiles) for (const k of ["ok", "partial", "ko"]) { const v = stats.series[n].by_profile[p][k]; row.push({ text: String(v), options: { fill: { color: C[k][0] }, color: C[k][1], bold: true, align: "center" } }); }
  rows.push(row);
}
s.addTable(rows, { x: 0.5, y: 1.2, w: 12.3, fontSize: 12, border: { type: "solid", color: "DDDDDD", pt: 0.5 } });
s.addText([
  { text: "Legend. ", options: { bold: true } },
  { text: "Ok: complete answer with at least one cited source. Ok - partial: complete answer, no cited source. Ko: no usable answer (error, empty, truncated). " },
  { text: "Statuses measure the presence of a source, not the relevance of the answer.", options: { italic: true } },
], { x: 0.5, y: 5.6, w: 12.3, h: 1.2, fontSize: 12, color: C.ink });

s = base("Answers with a cited source");
const chart = [{ name: "Ok", labels: names.map(label), values: names.map((n) => stats.series[n].total.ok) }, { name: "Ok - partial", labels: names.map(label), values: names.map((n) => stats.series[n].total.partial) }];
s.addChart(pptx.charts.BAR, chart, { x: 0.5, y: 1.2, w: 12.3, h: 5.3, barDir: "bar", barGrouping: "stacked", chartColors: [C.ok[0], C.partial[0]], showLegend: true, legendPos: "b", showValue: true });

s = base("Method and limits");
s.addText([
  "Same frozen question set for every model (SHA-256 fingerprint checked).",
  "Answers collected through the application's own API with the agent key; scripts only, no LLM agent.",
  "One status rule, no exceptions; every cell re-derived by an independent check; blind audit on a stratified sample.",
  "Not measured: relevance of answers, correctness of the cited documents, served model (only label acceptance), clean timings.",
].map((t) => ({ text: t, options: { bullet: true, breakLine: true } })), { x: 0.7, y: 1.3, w: 12, h: 4.5, fontSize: 18, color: C.ink, valign: "top" });

pptx.writeFile({ fileName: out }).then((f) => console.log("written", f));
