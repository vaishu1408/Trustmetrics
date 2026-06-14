# TrustMetrics

**An AI data analyst that answers only from governed metric definitions — and scores how much you can trust every answer.**

Live demo: _(add your Streamlit link here)_

---

## The problem

Companies are connecting AI to their data, but AI answers can't be trusted — because the AI is guessing what business terms mean.

Ask an AI "what was our revenue last month?" and it writes SQL against raw tables. But "revenue" isn't stored anywhere — it's a *decision*: gross or net of returns? ordered date or delivered date? The AI picks one interpretation silently, returns a confident number, and the user has no way to know which definition it used or whether it matches the business's agreed-upon logic.

This isn't a hypothetical. Testing on real data, the same question produced materially different answers depending on unstated assumptions:

| Question | AI's unguided answer | Governed answer | Why they differ |
|---|---|---|---|
| "What's our return rate?" | a raw count of `18,294` | **11.83%** | AI returned an unlabeled multi-column blob; governed used the reviewed denominator (non-cancelled items) |
| "How many active customers?" | `66,572` | **72,373** | AI silently excluded customers who returned something; the business counts them as active |
| "Revenue in January 2025?" | `147,995.24` | `147,995.24` | Unambiguous question — both converge |

Same questions. All valid SQL. None of it errored. Yet the answers diverged by up to ~8% — and the AI never flagged that it was making a choice.

## The solution

TrustMetrics runs every question down two paths and compares them:

- **Raw path** — Claude writes SQL with only the table schema. It guesses business definitions.
- **Governed path** — Claude is constrained to approved metric definitions (the semantic layer). It must map the question to a reviewed metric or decline.

It then produces a **0–100 trust score** from four weighted signals, with a human-readable breakdown so the trust is *legible* to a non-technical user:

| Signal | Weight | What it proves |
|---|---|---|
| Mapped to an approved metric | 40 | The answer is grounded in reviewed business logic, not a guess |
| Raw and governed agree | 30 | Independent corroboration; divergence flags a definition that matters |
| Governed query executed | 15 | Necessary gate |
| Answer is a clean scalar | 15 | Catches mis-shaped, un-interpretable results |

The result: a score of **70** says "the right metric was used, but the AI's unguided guess differed — look closer." A score of **100** says "even the unguided model converged — safe to trust." The danger isn't any single number; it's not knowing which one you're looking at.

## Architecture

```
BigQuery (TheLook eCommerce public data)
        │
        ▼
dbt staging models + semantic layer   ← metric definitions, version-controlled
        │
        ▼
Claude agent (raw path  +  governed path)
        │
        ▼
Trust score engine  →  Streamlit UI
```

- **Data**: `bigquery-public-data.thelook_ecommerce`
- **Modeling / governance**: dbt (staging → fact table → semantic layer with MetricFlow metric definitions)
- **Agent**: Anthropic Claude (Sonnet) via API
- **App**: Streamlit

## Metric definitions (the semantic layer)

| Metric | Definition |
|---|---|
| `net_revenue` | Sum of `sale_price`, excluding Cancelled and Returned, anchored to order date |
| `gross_revenue` | Sum of `sale_price`, excluding Cancelled only (returns still included) |
| `return_rate` | Returned items ÷ non-cancelled items, as a percentage |
| `active_customers` | Distinct customers with ≥1 non-cancelled order |

Each definition encodes the edge-case decisions (which statuses count, which date to anchor to) that an ungoverned AI would otherwise make silently.

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires two secrets (configured in `.streamlit/secrets.toml` locally, or the Streamlit Cloud secrets manager):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
GCP_SERVICE_ACCOUNT_JSON = '''{ ...service account json... }'''
```

> Credentials are never committed — see `.gitignore`.

## Roadmap

- Bring-your-own-warehouse: point the agent at any dbt project
- Multi-metric questions and time-series breakdowns
- As-of trust scoring (the same query run a week apart returns different numbers as returns settle — definitions need timestamps)

---

Built as a hands-on exploration of the semantic layer — the governance layer that's becoming essential as data teams shift from dashboards to AI agents.
