# Estimating what a campaign cost

Goal: answer "how many euros did these runs cost, per model?" with a low / central / high range, every assumption written down.

## Step 0: can you measure instead of estimate?

1. Run `src/probe_usage.js`. If the API returns `usage`, sum it from the journals and you are done (add the field to the collector).
2. If not (a back end may return `usage: null`), read **real token totals** from, in order of reliability:
   (a) the platform's own consumption table or logs per credential/model, filtered on the time windows of each series
   (`meta.json` gives `started`, journals give first and last `start/end`);
   (b) the provider console (billed tokens per model per period);
   (c) nothing: estimate.
   Ask for: input tokens, output tokens, reasoning tokens if separate, **and the number of requests the platform saw** in the
   window. If that count is greater than your number of requests, there are intermediate calls (query rewriting, routing,
   re-ranking) and the estimate must account for them.
3. Pass measured totals to `src/cost_estimate.py --measured measured.json`: only the price stays uncertain.

## The estimate (when nothing is measurable)

Per request, scenario `s ∈ {low, central, high}`:

```
input_tokens  = question_chars / chars_per_token + rag_context_tokens[s]
output_tokens = answer_chars / chars_per_token × reasoning_multiplier[model][s]
cost          = calls[s] × (input_tokens × price_in + output_tokens × price_out) / 1e6 × price_factor[s]
```

| Quantity | Known from logs? | Treatment |
|---|---|---|
| number of requests incl. retries and timeouts | yes (journals) | fact; failed attempts counted (they may be billed) |
| question and answer length in characters | yes | fact; converted with `chars_per_token` (3.2-4.2 for prose) |
| retrieved context injected by the RAG | **no** | dominant unknown: low 2 000 / central 6 000 / high 15 000 tokens per request by default, override per model |
| hidden reasoning tokens (billed as output) | **no** | multiplier per model; ≥ 1 for reasoning models, tune high scenario |
| intermediate calls per question | **no** | factor 1 / 1 / 2 by default |
| list price | partly | price table in config with source and date; `price_factor` covers tier changes, tax, currency |

The defaults are *placeholders for method*, not facts about any platform. Replace them with what you can justify.

## Prices: pitfalls

- Use the provider's own price page; aggregators disagree with each other (differences of 10 % to 50 % on the same model were seen).
- Introductory prices expire: record the date and any announced change, and run the high scenario with the future price.
- Currency: providers may bill in one currency while your client pays in another; say which conversion you used (or give both).
- A hosted catalogue (a cloud provider reselling an open model) is a different price from the model author's own API.
- Prices of a *very recent* model found only on third-party sites are provisional: label them so.
- State explicitly whether prices include tax.

## What the deliverable should contain

One note + one workbook: inputs (requests, characters), assumptions with ranges, price table with sources/dates, per-series
low/central/high, total, and a "what would tighten this" list (platform logs, provider console). **Models only**: do not
mix in the cost of the assistant that ran the campaign unless asked.

## Placeholder prices

`examples/demo/config.json` carries placeholder prices, clearly marked: replace them with sourced, dated prices before quoting any figure.
