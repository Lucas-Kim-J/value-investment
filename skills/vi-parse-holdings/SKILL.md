---
name: vi-parse-holdings
description: "Parse a brokerage/exchange holdings screenshot or pasted text into structured holdings JSON. Never fabricate numbers."
version: 0.1.0
author: value-investment
metadata:
  hermes:
    tags: [finance, vision, extraction, holdings]
---

# Parse Holdings into structured JSON

You are given an **image file path** and/or **pasted text** (named under INPUT) that contains a
holdings / portfolio / account list — from a broker, crypto exchange, or a screenshot. Extract
every position into the strict JSON schema below.

## Hard rules (no-fabrication — this is non-negotiable)
- **NEVER invent** a ticker, quantity, cost, or value. If a field is unreadable or absent, set it to `null`. Do not guess or interpolate.
- Read numbers exactly as shown (mind thousands separators and decimals). Don't round.
- If the input is **not** a holdings/portfolio list, return `{"holdings": [], "warnings": ["not_a_holdings_list"]}`.
- Output the user's real data only. No examples, no placeholders.

## Extraction
1. One object per position. Capture: `symbol` (ticker/coin, uppercase), `name` (full name if shown, else null),
   `quantity` (units held), `value_usd` (current market value in USD if shown/derivable, else null),
   `market` (one of `美股`/`A股`/`港股`/`加密`/null — infer only when unambiguous from the symbol/context).
2. **Dedup**: merge identical `symbol` rows, summing `quantity`.
3. **Dust**: if `value_usd` is shown and `< 1`, set `"dust": true` (keep the row, don't drop it).
4. Put anything ambiguous or skipped into `warnings`.

## Output — return ONLY this JSON object. No prose. No markdown code fences.
```
{"holdings":[{"symbol":"BTC","name":null,"market":"加密","quantity":0.5,"value_usd":42000,"dust":false}],"warnings":[]}
```
(The fenced block above is the SHAPE only — your actual output must be raw JSON with the user's real values, not this example.)
