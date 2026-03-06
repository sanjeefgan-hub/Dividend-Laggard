"""
app.py — The Dividend Laggard System v2.6 — Public Dashboard
Reads signal_output.json and deployment_log.json.
Hosted on Streamlit Community Cloud.
"""

import streamlit as st
import json, os
from datetime import datetime, date

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="The Dividend Laggard System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS — Navy / Gold theme ────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .main { background: #0D1B2A; }
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }

  /* ── Header ── */
  .hdr-box {
    background: linear-gradient(135deg, #0D1B2A 0%, #1A3A52 100%);
    border: 1px solid #C9A84C;
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
  }
  .hdr-title { color: #C9A84C; font-size: 2rem; font-weight: 700;
               letter-spacing: 0.06em; text-transform: uppercase; margin: 0; }
  .hdr-sub   { color: #D0D7E2; font-size: 0.95rem; margin-top: 0.3rem; }
  .hdr-ts    { color: #4A5568; font-size: 0.8rem; margin-top: 0.5rem; }

  /* ── Signal cards ── */
  .sig-card {
    border-radius: 10px; padding: 1.2rem 1.5rem;
    border-left: 5px solid;
    margin-bottom: 0.8rem;
  }
  .sig-green  { background: #0A2016; border-color: #1B6B3A; }
  .sig-fire   { background: #1F0A00; border-color: #C9A84C; }
  .sig-yellow { background: #1F1400; border-color: #92400E; }
  .sig-red    { background: #1F0000; border-color: #9B1C1C; }
  .sig-grey   { background: #111827; border-color: #4A5568; }
  .sig-emoji  { font-size: 2rem; }
  .sig-label  { color: #C9A84C; font-size: 0.75rem; font-weight: 700;
                letter-spacing: 0.1em; text-transform: uppercase; }
  .sig-name   { color: #F9FAFB; font-size: 1.2rem; font-weight: 700; }
  .sig-action { color: #D0D7E2; font-size: 0.9rem; margin-top: 0.4rem; }
  .sig-metric { color: #C9A84C; font-size: 0.85rem; }

  /* ── Deploy target ── */
  .deploy-box {
    background: linear-gradient(135deg, #0A2016, #0D2E1E);
    border: 2px solid #1B6B3A; border-radius: 10px;
    padding: 1.4rem 1.8rem; margin-bottom: 1rem;
  }
  .deploy-label { color: #C9A84C; font-size: 0.75rem; font-weight: 700;
                  letter-spacing: 0.1em; text-transform: uppercase; }
  .deploy-ticker { color: #C9A84C; font-size: 2.2rem; font-weight: 700; }
  .deploy-detail { color: #D0D7E2; font-size: 0.9rem; margin-top: 0.4rem; }
  .deploy-reason { color: #4A5568; font-size: 0.8rem; margin-top: 0.5rem;
                   font-style: italic; }

  .park-box {
    background: #111827; border: 2px solid #4A5568;
    border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;
  }
  .park-text { color: #9CA3AF; font-size: 1rem; }

  /* ── ETF table ── */
  .etf-row {
    display: grid;
    grid-template-columns: 110px 60px 70px 70px 70px 70px 1fr 120px;
    gap: 0.4rem;
    align-items: center;
    padding: 0.55rem 0.8rem;
    border-radius: 7px;
    margin-bottom: 0.3rem;
    font-size: 0.85rem;
  }
  .etf-hdr   { background: #0D1B2A; color: #C9A84C; font-weight: 700;
               font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; }
  .etf-pass  { background: #0A1E13; }
  .etf-fail  { background: #100B0B; }
  .etf-veto  { background: #12100A; }
  .etf-halt  { background: #0D1117; }
  .etf-ticker { font-weight: 700; color: #F9FAFB; }
  .etf-pass  .etf-ticker { color: #34D399; }
  .badge {
    display: inline-block; padding: 0.15rem 0.55rem;
    border-radius: 4px; font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .badge-pass    { background: #064E3B; color: #34D399; }
  .badge-fail    { background: #7F1D1D; color: #FCA5A5; }
  .badge-veto    { background: #451A03; color: #FCD34D; }
  .badge-halt    { background: #1F2937; color: #6B7280; }
  .badge-fastpass{ background: #1E3A5F; color: #93C5FD; }
  .badge-override{ background: #2D1B69; color: #C4B5FD; }
  .badge-sl      { background: #78350F; color: #FCD34D; font-size: 0.65rem; }
  .val-green { color: #34D399; }
  .val-red   { color: #F87171; }
  .val-gold  { color: #C9A84C; }
  .val-grey  { color: #6B7280; }

  /* ── Section titles ── */
  .sec-title {
    color: #C9A84C; font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase;
    border-bottom: 1px solid #1F2937; padding-bottom: 0.4rem;
    margin-bottom: 0.8rem; margin-top: 1.2rem;
  }

  /* ── Audit table ── */
  .audit-row {
    display: grid; grid-template-columns: 90px 110px 80px 80px 90px 90px 1fr;
    gap: 0.4rem; padding: 0.5rem 0.8rem;
    border-radius: 6px; margin-bottom: 0.25rem; font-size: 0.82rem;
  }
  .audit-hdr { background: #0D1B2A; color: #C9A84C; font-weight: 700;
               font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; }
  .audit-row-data { background: #0F1923; color: #D0D7E2; }
  .audit-row-data:nth-child(even) { background: #111F2D; }

  /* ── Metric pill ── */
  .metric-pill {
    background: #111F2D; border: 1px solid #1F2937;
    border-radius: 8px; padding: 0.8rem 1rem; text-align: center;
  }
  .metric-label { color: #4A5568; font-size: 0.7rem; text-transform: uppercase;
                  letter-spacing: 0.08em; }
  .metric-value { color: #C9A84C; font-size: 1.5rem; font-weight: 700; }
  .metric-sub   { color: #6B7280; font-size: 0.75rem; }

  /* ── Veto detail ── */
  .veto-item { font-size: 0.78rem; padding: 0.2rem 0; }
  .veto-ok   { color: #34D399; }
  .veto-fail { color: #F87171; }
  .veto-skip { color: #6B7280; }

  /* Hide Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
  .stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_signal():
    if not os.path.exists("signal_output.json"):
        return None
    with open("signal_output.json") as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_log():
    if not os.path.exists("deployment_log.json"):
        return None
    with open("deployment_log.json") as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_audit():
    if not os.path.exists("audit_report.json"):
        return None
    with open("audit_report.json") as f:
        return json.load(f)

signal = load_signal()
log    = load_log()
audit  = load_audit()


# ── Header ────────────────────────────────────────────────────────────────────

ts_str = signal["generated_at"] if signal else "No data yet"
st.markdown(f"""
<div class="hdr-box">
  <div class="hdr-title">The Dividend Laggard System</div>
  <div class="hdr-sub">v2.6 — Rules-Based Passive Income Deployment</div>
  <div class="hdr-ts">Last updated: {ts_str} &nbsp;·&nbsp; Refreshes daily at 2:55 PM EST (Mon–Fri)</div>
</div>
""", unsafe_allow_html=True)

if signal is None:
    st.warning("Signal engine hasn't run yet. Results will appear after the first scheduled run.")
    st.stop()


# ── MACRO SIGNAL ─────────────────────────────────────────────────────────────

macro   = signal.get("macro", {})
emoji   = macro.get("emoji", "❓")
sig_name = macro.get("signal", "UNKNOWN")
s5th    = macro.get("s5th")
nymo    = macro.get("nymo")
deploy  = macro.get("deploy", False)
heavy   = macro.get("heavy", False)
action  = macro.get("action", "")

sig_class = {
    "🟢": "sig-green", "🔥": "sig-fire",
    "🟡": "sig-yellow", "🔴": "sig-red",
}.get(emoji, "sig-grey")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown(f"""
    <div class="sig-card {sig_class}">
      <div class="sig-label">Step 0 — Macro Circuit Breaker</div>
      <div style="display:flex; align-items:center; gap:0.8rem; margin:0.5rem 0;">
        <span class="sig-emoji">{emoji}</span>
        <span class="sig-name">{sig_name}</span>
      </div>
      <div class="sig-action">{action}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    s5th_color = "val-green" if s5th and s5th > 50 else "val-red"
    st.markdown(f"""
    <div class="metric-pill">
      <div class="metric-label">S5TH</div>
      <div class="metric-value <{s5th_color}>">{f'{s5th:.1f}%' if s5th else 'N/A'}</div>
      <div class="metric-sub">Target &gt; 50%</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    nymo_color = "val-green" if nymo and nymo >= -40 else "val-red"
    st.markdown(f"""
    <div class="metric-pill">
      <div class="metric-label">NYMO</div>
      <div class="metric-value">{f'{nymo:.1f}' if nymo else 'N/A'}</div>
      <div class="metric-sub">Routine ≥ −40</div>
    </div>
    """, unsafe_allow_html=True)


# ── DEPLOYMENT TARGETS ───────────────────────────────────────────────────────

st.markdown('<div class="sec-title">Today\'s Deployment Orders</div>', unsafe_allow_html=True)

dcol1, dcol2 = st.columns(2)

def render_decision(decision, label, safe_haven):
    target = decision.get("target") if decision else None
    reason = decision.get("reason", "") if decision else ""

    if not deploy:
        st.markdown(f"""
        <div class="park-box">
          <div class="sig-label">{label}</div>
          <div class="park-text">🅿️  System halted — park all cash in {safe_haven}</div>
        </div>
        """, unsafe_allow_html=True)
    elif target:
        score  = target.get("composite_score", "—")
        rsi    = target.get("rsi", "—")
        disc   = target.get("discount_pct", 0) or 0
        ptype  = target.get("pass_type", "—")
        st.markdown(f"""
        <div class="deploy-box">
          <div class="deploy-label">{'🔥 Heavy Deploy — ' if heavy else ''}{label}</div>
          <div class="deploy-ticker">{target['ticker']}</div>
          <div class="deploy-detail">
            Score: <b>{score}</b> &nbsp;·&nbsp;
            RSI: <b>{rsi}</b> &nbsp;·&nbsp;
            Discount: <b>{disc:+.2f}%</b> &nbsp;·&nbsp;
            Pass: <b>{ptype}</b>
          </div>
          <div class="deploy-reason">{reason}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="park-box">
          <div class="sig-label">{label}</div>
          <div class="park-text">🅿️  No qualified target — park in {safe_haven}</div>
          <div class="deploy-reason">{reason}</div>
        </div>
        """, unsafe_allow_html=True)

with dcol1:
    render_decision(signal.get("cad", {}).get("decision"), "CAD Universe", "CASH.TO")
with dcol2:
    render_decision(signal.get("usd", {}).get("decision"), "USD Universe", "PSU.U.TO")


# ── ETF MATRIX ───────────────────────────────────────────────────────────────

def render_etf_table(results: list, title: str):
    st.markdown(f'<div class="sec-title">{title}</div>', unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="etf-row etf-hdr">
      <span>Ticker</span><span>RSI</span><span>ADX</span>
      <span>Discount</span><span>ATR×0.5</span><span>Score</span>
      <span>Step 2 Pass Type</span><span>Status</span>
    </div>
    """, unsafe_allow_html=True)

    for r in results:
        ticker = r.get("ticker", "")
        sl_badge = '<span class="badge badge-sl">SL</span> ' if r.get("structural_laggard") else ""

        if r.get("pass_type") == "system_halt":
            st.markdown(f"""
            <div class="etf-row etf-halt">
              <span class="etf-ticker">{ticker}</span>
              <span class="val-grey">—</span><span class="val-grey">—</span>
              <span class="val-grey">—</span><span class="val-grey">—</span><span class="val-grey">—</span>
              <span class="val-grey">System halted</span>
              <span><span class="badge badge-halt">Halted</span></span>
            </div>
            """, unsafe_allow_html=True)
            continue

        if r.get("disqualified"):
            vetoes = r.get("veto_result", {}).get("vetoes", {})
            failed = [v["reason"] for v in vetoes.values() if v.get("pass") is False]
            reason = failed[0] if failed else "Vetoed"
            st.markdown(f"""
            <div class="etf-row etf-veto">
              <span class="etf-ticker">{ticker}</span>
              <span class="val-grey">—</span><span class="val-grey">—</span>
              <span class="val-grey">—</span><span class="val-grey">—</span><span class="val-grey">—</span>
              <span class="val-gold" style="font-size:0.78rem">{reason}</span>
              <span><span class="badge badge-veto">Vetoed</span></span>
            </div>
            """, unsafe_allow_html=True)
            continue

        rsi   = r.get("rsi")
        adx   = r.get("adx")
        disc  = r.get("discount_pct") or 0
        atrthr= r.get("atr_threshold") or 0
        score = r.get("composite_score", "—")
        ptype = r.get("pass_type", "—") or "—"

        rsi_str   = f"{rsi:.1f}" if rsi is not None else "—"
        adx_str   = f"{adx:.1f}" if adx is not None else "—"
        disc_str  = f"{disc:+.2f}%" if disc else "—"
        atrthr_str= f"{atrthr:.3f}" if atrthr else "—"

        rsi_color  = "val-green" if rsi and rsi < 40 else "val-gold" if rsi and rsi < 50 else "val-grey"
        adx_color  = "val-green" if adx and adx < 30 else "val-red"
        disc_color = "val-green" if disc and disc > 0 else "val-red"

        if r.get("final_pass"):
            row_class = "etf-pass"
            if "fast_pass" in ptype:
                badge = '<span class="badge badge-fastpass">Fast-Pass ✓</span>'
            elif "override" in ptype:
                badge = '<span class="badge badge-override">Override ✓</span>'
            else:
                badge = '<span class="badge badge-pass">Pass ✓</span>'
        else:
            row_class = "etf-fail"
            badge = '<span class="badge badge-fail">Fail ✗</span>'

        st.markdown(f"""
        <div class="etf-row {row_class}">
          <span class="etf-ticker">{ticker} {sl_badge}</span>
          <span class="{rsi_color}">{rsi_str}</span>
          <span class="{adx_color}">{adx_str}</span>
          <span class="{disc_color}">{disc_str}</span>
          <span class="val-grey">{atrthr_str}</span>
          <span class="val-gold">{score}</span>
          <span class="val-grey">{ptype}</span>
          <span>{badge}</span>
        </div>
        """, unsafe_allow_html=True)


cad_results = signal.get("cad", {}).get("results", [])
usd_results = signal.get("usd", {}).get("results", [])

tcol1, tcol2 = st.columns([3, 2])
with tcol1:
    render_etf_table(cad_results, "CAD Universe — Steps 0.5 → 1 → 2")
with tcol2:
    render_etf_table(usd_results, "USD Universe — Steps 0.5 → 1 → 2")


# ── VETO DETAIL EXPANDER ─────────────────────────────────────────────────────

with st.expander("Fund Quality Veto Detail (Step 0.5)"):
    all_results = cad_results + usd_results
    vcols = st.columns(4)
    for i, r in enumerate(all_results):
        with vcols[i % 4]:
            ticker = r.get("ticker", "")
            vetoes = r.get("veto_result", {}).get("vetoes", {})
            st.markdown(f"**{ticker}**")
            for vname, vdata in vetoes.items():
                p = vdata.get("pass")
                reason = vdata.get("reason", "—")
                css = "veto-ok" if p else ("veto-fail" if p is False else "veto-skip")
                icon = "✓" if p else ("✗" if p is False else "·")
                st.markdown(f'<div class="veto-item {css}">{icon} {reason}</div>',
                            unsafe_allow_html=True)


# ── DEPLOYMENT HISTORY ───────────────────────────────────────────────────────

st.markdown('<div class="sec-title">Deployment History</div>', unsafe_allow_html=True)

if log and log.get("deployments"):
    deployments = list(reversed(log["deployments"]))

    st.markdown("""
    <div class="audit-row audit-hdr">
      <span>Date</span><span>Ticker</span><span>Macro</span>
      <span>Score</span><span>1M Return</span><span>3M Return</span><span>Pass Type</span>
    </div>
    """, unsafe_allow_html=True)

    for d in deployments[:20]:
        r1m = d.get("forward_1m")
        r3m = d.get("forward_3m")
        r1m_str = f"{r1m:+.2f}%" if r1m is not None else "Pending"
        r3m_str = f"{r3m:+.2f}%" if r3m is not None else "Pending"
        r1m_col = "val-green" if r1m and r1m > 0 else "val-red" if r1m is not None else "val-grey"
        r3m_col = "val-green" if r3m and r3m > 0 else "val-red" if r3m is not None else "val-grey"
        score   = d.get("composite_score", "—")
        ptype   = d.get("pass_type", "—") or "—"

        st.markdown(f"""
        <div class="audit-row audit-row-data">
          <span class="val-grey">{d.get('date','')}</span>
          <span style="font-weight:700;color:#F9FAFB">{d.get('ticker','')}</span>
          <span>{d.get('macro_emoji','')}</span>
          <span class="val-gold">{score}</span>
          <span class="{r1m_col}">{r1m_str}</span>
          <span class="{r3m_col}">{r3m_str}</span>
          <span class="val-grey" style="font-size:0.78rem">{ptype}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown('<div class="val-grey" style="font-size:0.9rem;padding:1rem">No deployments recorded yet.</div>',
                unsafe_allow_html=True)


# ── AUDIT REPORT ─────────────────────────────────────────────────────────────

if audit and "error" not in audit:
    st.markdown('<div class="sec-title">Monthly Audit Report</div>', unsafe_allow_html=True)

    a1, a2, a3, a4, a5 = st.columns(5)
    with a1:
        wr3m = audit.get("win_rate_3m")
        flag = "✅" if wr3m and wr3m >= 55 else "⚠️"
        st.markdown(f"""<div class="metric-pill">
          <div class="metric-label">3M Win Rate</div>
          <div class="metric-value">{f'{wr3m}%' if wr3m else 'N/A'} {flag}</div>
          <div class="metric-sub">Target ≥ 55%</div>
        </div>""", unsafe_allow_html=True)
    with a2:
        st.markdown(f"""<div class="metric-pill">
          <div class="metric-label">1M Win Rate</div>
          <div class="metric-value">{f'{audit.get("win_rate_1m")}%' if audit.get("win_rate_1m") else 'N/A'}</div>
          <div class="metric-sub">Avg: {audit.get("avg_return_1m","N/A")}%</div>
        </div>""", unsafe_allow_html=True)
    with a3:
        st.markdown(f"""<div class="metric-pill">
          <div class="metric-label">Avg 3M Return</div>
          <div class="metric-value">{f'{audit.get("avg_return_3m")}%' if audit.get("avg_return_3m") else 'N/A'}</div>
          <div class="metric-sub">&nbsp;</div>
        </div>""", unsafe_allow_html=True)
    with a4:
        st.markdown(f"""<div class="metric-pill">
          <div class="metric-label">Distributions</div>
          <div class="metric-value">${audit.get('total_distributions', 0):.2f}</div>
          <div class="metric-sub">Per unit received</div>
        </div>""", unsafe_allow_html=True)
    with a5:
        st.markdown(f"""<div class="metric-pill">
          <div class="metric-label">Total Deployments</div>
          <div class="metric-value">{audit.get('total_deployments', 0)}</div>
          <div class="metric-sub">{audit.get('completed_3m', 0)} with 3M data</div>
        </div>""", unsafe_allow_html=True)

    if audit.get("by_pass_type"):
        with st.expander("Performance by Pass Type"):
            for pt, v in audit["by_pass_type"].items():
                wr  = v.get("win_rate", 0)
                avg = v.get("avg_3m_return", 0)
                col = "val-green" if avg > 0 else "val-red"
                st.markdown(f"""
                <div style="display:flex;gap:2rem;padding:0.4rem 0.8rem;
                            background:#0F1923;border-radius:6px;margin-bottom:0.3rem;
                            font-size:0.85rem;">
                  <span style="color:#F9FAFB;font-weight:700;width:200px">{pt}</span>
                  <span class="val-grey">n={v.get('count')}</span>
                  <span class="{col}">Avg 3M: {avg:+.2f}%</span>
                  <span class="val-grey">Win rate: {wr}%</span>
                </div>
                """, unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:2.5rem;padding-top:1rem;border-top:1px solid #1F2937;
            color:#374151;font-size:0.75rem;text-align:center;">
  The Dividend Laggard System v2.6 &nbsp;·&nbsp;
  Signal engine runs Mon–Fri at 2:55 PM EST via GitHub Actions &nbsp;·&nbsp;
  This dashboard is for informational purposes only and does not constitute financial advice.
</div>
""", unsafe_allow_html=True)
