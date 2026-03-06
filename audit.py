"""
audit.py — Monthly Audit Loop for The Dividend Laggard System v2.6
Run on the first trading day of each month.
Fills in forward returns and generates a plain-English report.
"""

import yfinance as yf
import json, os
from datetime import date, timedelta
from collections import defaultdict

LOG_PATH    = "deployment_log.json"
REPORT_PATH = "audit_report.json"

def load_log():
    if not os.path.exists(LOG_PATH):
        print("No deployment log found. Run signal_engine.py first.")
        return None
    with open(LOG_PATH) as f:
        return json.load(f)

def save_log(log):
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)

def get_price_on_date(ticker: str, target_date: date) -> float:
    """Fetch closest available closing price on or after target_date."""
    try:
        end  = target_date + timedelta(days=7)
        data = yf.download(ticker, start=str(target_date), end=str(end),
                           interval="1d", progress=False, auto_adjust=True)
        if not data.empty:
            return float(data["Close"].dropna().iloc[0])
    except Exception:
        pass
    return None

def fill_forward_returns(log: dict) -> dict:
    """Fill in 1M and 3M forward returns for completed deployments."""
    today   = date.today()
    updated = 0

    for entry in log["deployments"]:
        dep_date = date.fromisoformat(entry["date"])
        ticker   = entry["ticker"]

        # 1-month forward return
        if entry.get("forward_1m") is None:
            target_1m = dep_date + timedelta(days=30)
            if today >= target_1m:
                p = get_price_on_date(ticker, target_1m)
                if p and entry.get("entry_price"):
                    entry["forward_1m"] = round((p - entry["entry_price"]) / entry["entry_price"] * 100, 2)
                    updated += 1

        # 3-month forward return
        if entry.get("forward_3m") is None:
            target_3m = dep_date + timedelta(days=90)
            if today >= target_3m:
                p = get_price_on_date(ticker, target_3m)
                if p and entry.get("entry_price"):
                    entry["forward_3m"] = round((p - entry["entry_price"]) / entry["entry_price"] * 100, 2)
                    updated += 1

        # Distributions received (sum dividends paid between entry and 3m)
        if entry.get("distributions") is None:
            target_3m = dep_date + timedelta(days=90)
            if today >= target_3m:
                try:
                    divs = yf.Ticker(ticker).dividends
                    divs.index = divs.index.date
                    mask = (divs.index >= dep_date) & (divs.index <= target_3m)
                    entry["distributions"] = round(float(divs[mask].sum()), 4)
                    updated += 1
                except Exception:
                    pass

    if updated:
        save_log(log)
        print(f"  Updated {updated} forward return values.")
    return log

def generate_report(log: dict) -> dict:
    """Calculate win rates, pass-type performance, and veto effectiveness."""
    deployments = log.get("deployments", [])
    if not deployments:
        return {"error": "No deployments recorded yet."}

    completed_1m = [d for d in deployments if d.get("forward_1m") is not None]
    completed_3m = [d for d in deployments if d.get("forward_3m") is not None]

    def win_rate(entries, key):
        wins = sum(1 for e in entries if (e.get(key) or 0) > 0)
        return round(wins / len(entries) * 100, 1) if entries else None

    def avg_return(entries, key):
        vals = [e[key] for e in entries if e.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    # By pass type
    by_pass_type = defaultdict(list)
    for d in completed_3m:
        by_pass_type[d.get("pass_type", "unknown")].append(d.get("forward_3m", 0))

    pass_type_performance = {
        pt: {"count": len(v), "avg_3m_return": round(sum(v)/len(v), 2), "win_rate": round(sum(1 for x in v if x > 0)/len(v)*100, 1)}
        for pt, v in by_pass_type.items() if v
    }

    # By macro signal
    by_macro = defaultdict(list)
    for d in completed_3m:
        by_macro[d.get("macro_emoji", "?")].append(d.get("forward_3m", 0))

    macro_performance = {
        sig: {"count": len(v), "avg_3m_return": round(sum(v)/len(v), 2)}
        for sig, v in by_macro.items() if v
    }

    # Total distributions received
    total_distributions = sum(
        d.get("distributions") or 0 for d in deployments
        if d.get("distributions") is not None
    )

    report = {
        "generated": str(date.today()),
        "total_deployments": len(deployments),
        "completed_1m": len(completed_1m),
        "completed_3m": len(completed_3m),
        "win_rate_1m":  win_rate(completed_1m, "forward_1m"),
        "win_rate_3m":  win_rate(completed_3m, "forward_3m"),
        "avg_return_1m": avg_return(completed_1m, "forward_1m"),
        "avg_return_3m": avg_return(completed_3m, "forward_3m"),
        "total_distributions": round(total_distributions, 2),
        "by_pass_type": pass_type_performance,
        "by_macro_signal": macro_performance,
        "benchmark_flags": {
            "3m_win_rate_ok":     (win_rate(completed_3m, "forward_3m") or 0) >= 55,
            "fast_pass_beats_override": (
                pass_type_performance.get("clean", {}).get("avg_3m_return", 0) >
                pass_type_performance.get("override_rsi", {}).get("avg_3m_return", 0)
            ) if "clean" in pass_type_performance and "override_rsi" in pass_type_performance else None,
        },
        "recent_deployments": deployments[-6:],
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report

def print_report(report: dict):
    if "error" in report:
        print(f"\n  {report['error']}")
        return

    print(f"\n{'═'*60}")
    print(f"  DIVIDEND LAGGARD — MONTHLY AUDIT REPORT")
    print(f"  {report['generated']}")
    print(f"{'═'*60}")
    print(f"  Total deployments logged:  {report['total_deployments']}")
    print(f"  With 1M forward return:    {report['completed_1m']}")
    print(f"  With 3M forward return:    {report['completed_3m']}")
    if report.get("win_rate_1m"):
        print(f"\n  1M win rate:    {report['win_rate_1m']}%  (avg: {report['avg_return_1m']}%)")
    if report.get("win_rate_3m"):
        wr = report['win_rate_3m']
        flag = "✅" if wr >= 55 else "⚠️ "
        print(f"  3M win rate:    {wr}%  (avg: {report['avg_return_3m']}%)  {flag} (target ≥55%)")
    if report.get("total_distributions"):
        print(f"  Total distributions received: ${report['total_distributions']:.2f}/unit")
    if report.get("by_pass_type"):
        print(f"\n  Performance by pass type:")
        for pt, v in report["by_pass_type"].items():
            print(f"    {pt:25s}  n={v['count']}  3M avg: {v['avg_3m_return']:+.2f}%  win: {v['win_rate']}%")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    log = load_log()
    if log:
        log    = fill_forward_returns(log)
        report = generate_report(log)
        print_report(report)
        print(f"  Report saved to {REPORT_PATH}")
