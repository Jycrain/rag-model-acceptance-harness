export const meta = {
  name: 'blind-audit',
  description: 'Blind audit of campaign statuses: N reviewers per batch, retry on missed canary, adversary after the barrier',
  phases: [
    { title: 'Review', detail: 'each batch is read blind by every reviewer model' },
    { title: 'Challenge', detail: 'one adversary per batch receives the verdict matrix' },
  ],
}
// args: { batches: [{ id: "01", pack: {citation_convention, cases:[{case,question,answer}]},
//                      canaries: {"<case id>": "Ok" | "Ok - partial"} }],   // expected verdict per canary, from key.json (batch-level only)
//         models: ["sonnet","opus","fable"]  (optional; one reviewer per entry), mechanical: {"<case id>": status} (optional, adversary only) }
// Returns { reviewers: {"<model>": {...merged verdicts}}, objections: {...}, suspected_canaries: [...], retries: [...] }.
// The script reads no file: write the result to audit/reviewer-<k>.json and audit/objections.json, then run src/audit_consensus.py.
const models = args.models || ['sonnet', 'opus', 'fable']
const batches = args.batches
const MAX_AGENTS = 10
const planned = batches.length * (models.length + 1)
if (planned > MAX_AGENTS) log(`WARNING: ${planned} agents planned (> ${MAX_AGENTS}). The owner must have approved this budget.`)

const REVIEW = {
  type: 'object',
  properties: { verdicts: { type: 'object' } },
  required: ['verdicts'],
}
const CHALLENGE = {
  type: 'object',
  properties: {
    objections: { type: 'object' },
    suspected_canaries: { type: 'array', items: { type: 'string' } },
    patterns: { type: 'array', items: { type: 'string' } },
  },
  required: ['objections', 'suspected_canaries', 'patterns'],
}
const verdictOf = v => (v.has_source && v.complete_answer ? 'Ok' : (!v.complete_answer ? 'Ko' : 'Ok - partial'))
const retries = []

function reviewPrompt(b) {
  return 'Review this audit batch as the blind-reviewer. Citation convention (regex): ' + b.pack.citation_convention +
    '\nReturn {"verdicts": {"<case id>": {"has_source":bool,"complete_answer":bool,"quotes":[...],"remark":"..."}}} for EVERY case.\n\nCASES:\n' +
    JSON.stringify(b.pack.cases)
}

async function reviewOnce(b, model, attempt) {
  const r = await agent(reviewPrompt(b), { label: `review:${b.id}:${model}:${attempt}`, phase: 'Review', model, agentType: 'blind-reviewer', schema: REVIEW })
  if (!r) return null
  const v = r.verdicts
  const missing = b.pack.cases.filter(c => !v[c.case]).length
  const badCanary = Object.entries(b.canaries || {}).filter(([id, exp]) => v[id] && verdictOf(v[id]) !== exp).length
  const nonLiteral = b.pack.cases.some(c => (v[c.case]?.quotes || []).some(q => !c.answer.includes(q)))
  return { v, ok: missing === 0 && badCanary === 0 && !nonLiteral, why: { missing, badCanary, nonLiteral } }
}

const perBatch = await pipeline(
  batches,
  async b => {
    const out = {}
    for (const model of models) {
      let res = await reviewOnce(b, model, 1)
      if (!res || !res.ok) {            // one retry only: a reviewer that misses a canary or invents a quote did not read
        retries.push({ batch: b.id, model, why: res ? res.why : 'agent failed' })
        res = await reviewOnce(b, model, 2)
      }
      if (res) out[model] = { verdicts: res.v, clean: res.ok }
      else log(`batch ${b.id}: no usable review from ${model}`)
    }
    return { b, out }
  },
  async ({ b, out }) => {
    const matrix = {}
    for (const c of b.pack.cases) {
      matrix[c.case] = { mechanical: (args.mechanical || {})[c.case] || null }
      for (const [m, r] of Object.entries(out)) if (r.verdicts[c.case]) matrix[c.case][m] = verdictOf(r.verdicts[c.case])
    }
    const adv = await agent('Challenge this consensus as the adversary. Verdict matrix: ' + JSON.stringify(matrix) +
      '\n\nCASES:\n' + JSON.stringify(b.pack.cases), { label: `challenge:${b.id}`, phase: 'Challenge', agentType: 'adversary', schema: CHALLENGE })
    return { id: b.id, out, adv }
  },
)

const result = { reviewers: {}, objections: {}, suspected_canaries: [], patterns: [], retries }
for (const r of perBatch.filter(Boolean)) {
  for (const [m, x] of Object.entries(r.out)) result.reviewers[m] = Object.assign(result.reviewers[m] || {}, x.verdicts)
  if (r.adv) {
    Object.assign(result.objections, r.adv.objections)
    result.suspected_canaries.push(...r.adv.suspected_canaries)
    result.patterns.push(...r.adv.patterns)
  }
}
log(`batches ${perBatch.filter(Boolean).length}/${batches.length}, retries ${retries.length}, objections ${Object.keys(result.objections).length}`)
return result
