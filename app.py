"""
TrustMetrics — an AI data analyst that answers only from governed metric
definitions and scores how much you can trust each answer.

Built on the BigQuery TheLook eCommerce public dataset.
"""

import re
import json
import html
import numbers
import streamlit as st
import anthropic
from google.cloud import bigquery
from google.oauth2 import service_account

# ----------------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="TrustMetrics",
    page_icon="◆",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ----------------------------------------------------------------------------
# Styling — deep slate canvas, single cyan accent, trust score as hero
# ----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp {
        background: #0c1018;
        color: #e2e8f0;
    }
    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        max-width: 760px;
        padding-top: 3rem;
        padding-bottom: 4rem;
    }

    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: #f8fafc; }
    p, div, span, label { font-family: 'Inter', sans-serif; }

    .tm-eyebrow {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #38bdf8;
        margin-bottom: 0.4rem;
    }
    .tm-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.6rem;
        font-weight: 700;
        line-height: 1.05;
        margin: 0 0 0.6rem 0;
        color: #f8fafc;
    }
    .tm-sub {
        font-size: 1.02rem;
        color: #94a3b8;
        line-height: 1.5;
        margin-bottom: 2rem;
    }

    /* Input */
    .stTextInput > div > div > input {
        background: #141b27;
        border: 1px solid #1e293b;
        border-radius: 10px;
        color: #f1f5f9;
        font-size: 1rem;
        padding: 0.85rem 1rem;
    }
    .stTextInput > div > div > input:focus {
        border-color: #38bdf8;
        box-shadow: 0 0 0 1px #38bdf8;
    }

    .stButton > button {
        background: #38bdf8;
        color: #0c1018;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        padding: 0.55rem 1.1rem;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        background: #7dd3fc;
        color: #0c1018;
    }

    /* Trust badge */
    .trust-badge {
        text-align: center;
        padding: 1.8rem 1rem 1.4rem 1rem;
        border-radius: 16px;
        margin: 1.5rem 0;
        border: 1px solid;
    }
    .trust-score-num {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 4rem;
        font-weight: 700;
        line-height: 1;
    }
    .trust-score-max { font-size: 1.5rem; color: #64748b; font-weight: 500; }
    .trust-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        margin-top: 0.5rem;
    }

    .answer-card {
        background: #141b27;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 1.3rem 1.5rem;
        margin: 1rem 0;
    }
    .answer-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #64748b;
        margin-bottom: 0.3rem;
    }
    .answer-value {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2rem;
        font-weight: 600;
        color: #f8fafc;
    }
    .metric-pill {
        display: inline-block;
        background: #0e2a3a;
        color: #38bdf8;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        padding: 0.25rem 0.7rem;
        border-radius: 6px;
        border: 1px solid #1e4a5f;
        margin-top: 0.5rem;
    }

    .reason-row {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        padding: 0.5rem 0;
        font-size: 0.92rem;
        color: #cbd5e1;
        border-bottom: 1px solid #161e2b;
    }
    .reason-pass { color: #34d399; font-weight: 600; }
    .reason-fail { color: #64748b; font-weight: 600; }
    .reason-weight {
        margin-left: auto;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #475569;
    }

    .evidence-card {
        background: #141b27;
        border: 1px solid #1e293b;
        border-left: 3px solid #f59e0b;
        border-radius: 10px;
        padding: 1rem 1.3rem;
        margin: 1rem 0;
    }
    .evidence-head {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #f59e0b;
        margin-bottom: 0.4rem;
    }
    .evidence-text {
        font-size: 0.92rem;
        color: #cbd5e1;
        line-height: 1.55;
    }
    .evidence-text b { color: #f1f5f9; }
    .sql-block {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        color: #94a3b8;
        background: #0a0e15;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-top: 0.5rem;
        white-space: pre-wrap;
        line-height: 1.45;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Clients (cached)
# ----------------------------------------------------------------------------
@st.cache_resource
def get_bq_client():
    info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info)
    return bigquery.Client(credentials=creds, project=info["project_id"])

@st.cache_resource
def get_claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# ----------------------------------------------------------------------------
# The semantic layer — approved metric definitions
# ----------------------------------------------------------------------------
RAW_SCHEMA = """
Table: `bigquery-public-data.thelook_ecommerce.order_items`
Columns:
- id (int), order_id (int), user_id (int), product_id (int)
- status (string): Complete, Shipped, Processing, Cancelled, Returned
- sale_price (float): price paid for the item
- created_at (timestamp): when the order was placed
- shipped_at, delivered_at, returned_at (timestamp)
"""

METRIC_DEFINITIONS = """
You are a data analyst for an e-commerce company. Answer using ONLY these approved
metric definitions. Do not invent your own logic. If the question does not match one
of these metrics, set METRIC_USED to NONE.

Tables:
- `bigquery-public-data.thelook_ecommerce.order_items` (alias oi): one row per item.
  Columns: order_id, user_id, product_id, status (Complete/Shipped/Processing/Cancelled/Returned),
  sale_price, created_at.
- `bigquery-public-data.thelook_ecommerce.products` (alias p): join oi.product_id = p.id; p.cost = item cost.

APPROVED METRICS (each returns a single scalar as the first column):

1. net_revenue — sales kept, excl. cancelled & returned:
   SUM(CASE WHEN status NOT IN ('Cancelled','Returned') THEN sale_price ELSE 0 END)

2. gross_revenue — sales excl. cancelled only (returns still in):
   SUM(CASE WHEN status != 'Cancelled' THEN sale_price ELSE 0 END)

3. gross_margin — net sales minus product cost (NEEDS products join):
   SELECT SUM(CASE WHEN oi.status NOT IN ('Cancelled','Returned') THEN oi.sale_price - p.cost ELSE 0 END)
   FROM order_items oi JOIN products p ON oi.product_id = p.id

4. aov — average order value (net revenue / distinct non-cancelled orders):
   SUM(CASE WHEN status NOT IN ('Cancelled','Returned') THEN sale_price ELSE 0 END)
   / COUNT(DISTINCT CASE WHEN status != 'Cancelled' THEN order_id END)

5. total_orders — distinct non-cancelled orders:
   COUNT(DISTINCT CASE WHEN status != 'Cancelled' THEN order_id END)

6. total_items — non-cancelled items sold:
   COUNTIF(status != 'Cancelled')

7. active_customers — distinct customers with >=1 non-cancelled order:
   COUNT(DISTINCT CASE WHEN status != 'Cancelled' THEN user_id END)

8. new_customers — customers whose FIRST EVER order falls in the requested period.
   Use a subquery: SELECT COUNT(*) FROM (
     SELECT user_id, MIN(created_at) AS first_order
     FROM order_items WHERE status != 'Cancelled' GROUP BY user_id
   ) WHERE first_order >= <start> AND first_order < <end>
   (If no period given, count all customers' first orders = all-time distinct buyers.)

9. repeat_rate — % of buyers with 2+ non-cancelled orders:
   SELECT COUNTIF(order_ct >= 2) / COUNT(*) * 100 FROM (
     SELECT user_id, COUNT(DISTINCT order_id) AS order_ct
     FROM order_items WHERE status != 'Cancelled' GROUP BY user_id )

10. return_rate — returned items / non-cancelled items * 100:
    COUNTIF(status='Returned') / COUNTIF(status != 'Cancelled') * 100

11. cancel_rate — cancelled items / all items * 100:
    COUNTIF(status='Cancelled') / COUNT(*) * 100

12. returned_count — number of returned items:
    COUNTIF(status='Returned')

DATE RULE: anchor to created_at; half-open ranges (>= start AND < end); never BETWEEN;
never CURRENT_DATE() unless the user explicitly says "today". Return ONE scalar, first column.
"""

# ----------------------------------------------------------------------------
# Agent paths
# ----------------------------------------------------------------------------
def ask_raw(claude, question):
    prompt = f"""You are a data analyst. Write a BigQuery SQL query to answer the question.
Use ONLY this schema:
{RAW_SCHEMA}

Question: {question}

Return ONLY the SQL query, no explanation, no markdown fences."""
    r = claude.messages.create(
        model="claude-sonnet-4-6", max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text.strip()

def ask_governed(claude, question):
    prompt = f"""{METRIC_DEFINITIONS}

Question: {question}

Respond in this exact format:
METRIC_USED: <name of the approved metric, or NONE>
SQL: <BigQuery SQL using the approved definition>

No markdown fences, no extra explanation."""
    r = claude.messages.create(
        model="claude-sonnet-4-6", max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text.strip()

def parse_governed(text):
    metric = re.search(r'METRIC_USED:\s*(.+)', text)
    sql = re.search(r'SQL:\s*(.+)', text, re.DOTALL)
    metric = metric.group(1).strip() if metric else "UNKNOWN"
    sql = sql.group(1).strip() if sql else text
    return metric, sql

def clean_sql(sql):
    if not sql:
        return ""
    s = sql.strip()
    # strip ```sql ... ``` fences if the model added them
    s = re.sub(r'^```(?:sql)?', '', s).strip()
    s = re.sub(r'```$', '', s).strip()
    return s

def run_sql(bq, sql):
    sql = clean_sql(sql)
    if not sql or sql.lower().startswith(("none", "null")):
        return "ERROR: no query produced"
    try:
        df = bq.query(sql).to_dataframe()
        if df.empty:
            return None
        return df.iloc[0, 0]
    except Exception as e:
        return f"ERROR: {e}"

# ----------------------------------------------------------------------------
# Trust scoring  (40 / 30 / 15 / 15)
# ----------------------------------------------------------------------------
def is_num(v):
    return isinstance(v, numbers.Number) and not isinstance(v, bool)

def evaluate(bq, claude, question):
    raw_sql = ask_raw(claude, question)
    raw_val = run_sql(bq, raw_sql)

    gov_resp = ask_governed(claude, question)
    metric, gov_sql = parse_governed(gov_resp)
    mapped = bool(metric) and metric.upper() not in ("NONE", "UNKNOWN")

    reasons = []

    if mapped:
        # ---- GOVERNED PATH ----
        gov_val = run_sql(bq, gov_sql)
        answer = gov_val
        score = 0

        score += 40
        reasons.append((True, f"Mapped to approved metric: {metric}", "+40"))

        agree = False
        if is_num(raw_val) and is_num(gov_val) and gov_val != 0:
            agree = abs(raw_val - gov_val) / abs(gov_val) <= 0.01
        if agree:
            score += 30
            reasons.append((True, "Raw and governed answers agree", "+30"))
        else:
            reasons.append((False, "Raw and governed disagree — definition matters here", "+0"))

        executed = not (isinstance(gov_val, str) and gov_val.startswith("ERROR"))
        if executed:
            score += 15
            reasons.append((True, "Governed query executed without error", "+15"))
        else:
            reasons.append((False, "Governed query failed to execute", "+0"))

        if is_num(gov_val):
            score += 15
            reasons.append((True, "Governed answer is a clean single value", "+15"))
        else:
            reasons.append((False, "Governed answer is not a clean scalar", "+0"))

        mode = "governed"

    else:
        # ---- UNGOVERNED FALLBACK ----
        # No approved metric. Answer with the raw path, but cap trust low and be honest.
        answer = raw_val
        reasons.append((False, "No approved metric — answered with an ungoverned AI best-effort", "+0"))

        if is_num(raw_val):
            # ungoverned but at least produced a clean number → small credit, capped
            score = 20
            reasons.append((True, "AI produced a clean value (ungoverned, unverified)", "+20"))
            mode = "fallback"
        else:
            # couldn't even produce a usable answer
            score = 0
            reasons.append((False, "AI could not produce a usable answer", "+0"))
            mode = "failed"

    return {
        "score": score, "reasons": reasons, "mode": mode, "mapped": mapped,
        "metric": metric, "answer": answer, "gov_sql": gov_sql,
        "raw_val": raw_val, "raw_sql": raw_sql,
    }

def fmt(v):
    if is_num(v):
        if isinstance(v, float):
            return f"{v:,.2f}"
        return f"{v:,}"
    # Non-numeric (e.g. an error string) — escape so it can't break the HTML layout
    return html.escape(str(v))

# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.markdown('<div class="tm-eyebrow">Governed AI Analyst</div>', unsafe_allow_html=True)
st.markdown('<div class="tm-title">TrustMetrics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="tm-sub">Ask a business question. The answer comes from reviewed metric '
    'definitions — and every answer is scored on how much you can trust it. '
    'No silent guessing about what "revenue" means.</div>',
    unsafe_allow_html=True,
)

examples = {
    "Gross margin": "What's our gross margin?",
    "Avg order value": "What is our average order value?",
    "Cancel rate": "What is the cancel rate?",
}
cols = st.columns(len(examples))
clicked = None
for col, (label, q) in zip(cols, examples.items()):
    if col.button(label, use_container_width=True):
        clicked = q

question = st.text_input("Your question", value=clicked or "", placeholder="e.g. What's our return rate?", label_visibility="collapsed")
go = st.button("Ask", type="primary")

if (go or clicked) and question:
    try:
        bq = get_bq_client()
        claude = get_claude()
    except Exception as e:
        st.error(f"Setup issue — check that secrets are configured. ({e})")
        st.stop()

    with st.spinner("Running governed and ungoverned paths…"):
        res = evaluate(bq, claude, question)

    score = res["score"]
    mode = res["mode"]
    if score >= 90:
        color, bg, border, tier = "#34d399", "#0d2a1f", "#1c4d38", "High trust"
    elif score >= 60:
        color, bg, border, tier = "#fbbf24", "#2a230d", "#4d401c", "Review advised"
    elif score >= 15:
        color, bg, border, tier = "#fb923c", "#2a190d", "#4d301c", "Ungoverned"
    else:
        color, bg, border, tier = "#f87171", "#2a0d0d", "#4d1c1c", "Low trust"

    st.markdown(f"""
    <div class="trust-badge" style="background:{bg};border-color:{border};">
        <div class="trust-score-num" style="color:{color};">{score}<span class="trust-score-max">/100</span></div>
        <div class="trust-label" style="color:{color};">{tier}</div>
    </div>
    """, unsafe_allow_html=True)

    if mode == "failed":
        # Couldn't produce a usable answer — clean message, no stack trace
        st.markdown("""
        <div class="answer-card">
            <div class="answer-label">Answer</div>
            <div class="answer-value" style="font-size:1.3rem;color:#94a3b8;">Couldn't answer this one</div>
        </div>
        <div class="evidence-card" style="border-left-color:#f87171;">
            <div class="evidence-head" style="color:#f87171;">What happened</div>
            <div class="evidence-text">This question doesn't map to a governed metric, and the
            ungoverned attempt didn't produce a usable result. Try rephrasing, or ask about revenue,
            margin, orders, customers, returns, or cancellations.</div>
        </div>
        """, unsafe_allow_html=True)

    elif mode == "fallback":
        # Ungoverned best-effort answer
        st.markdown(f"""
        <div class="answer-card">
            <div class="answer-label">Answer · ungoverned</div>
            <div class="answer-value">{fmt(res["answer"])}</div>
        </div>
        <div class="evidence-card">
            <div class="evidence-head">Heads up — not a governed metric</div>
            <div class="evidence-text">No reviewed definition exists for this question yet, so this is an
            <b>AI best-effort answer</b> using assumptions no one has approved. Treat it as a starting point,
            not a verified number. To make it trustworthy, add it as a governed metric.</div>
        </div>
        """, unsafe_allow_html=True)

    else:
        # Governed answer
        pill = f'<div class="metric-pill">{res["metric"]}</div>'
        st.markdown(f"""
        <div class="answer-card">
            <div class="answer-label">Answer</div>
            <div class="answer-value">{fmt(res["answer"])}</div>
            {pill}
        </div>
        """, unsafe_allow_html=True)

        raw_differs = True
        if is_num(res["raw_val"]) and is_num(res["answer"]) and res["answer"] != 0:
            raw_differs = abs(res["raw_val"] - res["answer"]) / abs(res["answer"]) > 0.01

        if raw_differs:
            st.markdown(f"""
            <div class="evidence-card">
                <div class="evidence-head">How we checked this</div>
                <div class="evidence-text">An ungoverned AI, left to guess the definition, would have returned
                <b>{fmt(res["raw_val"])}</b> here — a different number using assumptions no one approved.
                That gap is why this is flagged for review rather than fully trusted.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="evidence-card" style="border-left-color:#34d399;">
                <div class="evidence-head" style="color:#34d399;">How we checked this</div>
                <div class="evidence-text">An ungoverned AI independently arrived at the same value
                (<b>{fmt(res["raw_val"])}</b>). When even an unguided model converges on the governed
                definition, confidence is high.</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="answer-label" style="margin-top:1.5rem;">Why this score</div>', unsafe_allow_html=True)
    rows_html = ""
    for passed, text, weight in res["reasons"]:
        mark = "✓" if passed else "✕"
        cls = "reason-pass" if passed else "reason-fail"
        rows_html += f'<div class="reason-row"><span class="{cls}">{mark}</span><span>{text}</span><span class="reason-weight">{weight}</span></div>'
    st.markdown(rows_html, unsafe_allow_html=True)

    with st.expander("View generated SQL"):
        st.markdown(f'<div class="answer-label">Raw path</div><div class="sql-block">{html.escape(str(res["raw_sql"]))}</div>', unsafe_allow_html=True)
        if res["mode"] == "governed":
            st.markdown(f'<div class="answer-label" style="margin-top:0.8rem;">Governed path</div><div class="sql-block">{html.escape(str(res["gov_sql"]))}</div>', unsafe_allow_html=True)

st.markdown(
    '<div style="margin-top:3rem;color:#475569;font-size:0.8rem;font-family:JetBrains Mono,monospace;">'
    'Data: BigQuery TheLook eCommerce · Definitions governed via dbt semantic layer</div>',
    unsafe_allow_html=True,
)
