"""
reset_streak.py — Manually reset an ETF's concentration streak counter.
Usage:
    python reset_streak.py HUTL.TO
    python reset_streak.py --manager Hamilton
"""
import json, sys, os

LOG_PATH = "deployment_log.json"

def reset_etf(ticker):
    ticker = ticker.upper()
    if not os.path.exists(LOG_PATH):
        print("No log file found.")
        return
    with open(LOG_PATH) as f:
        log = json.load(f)
    es = log.setdefault("etf_streaks", {})
    if ticker in es:
        es[ticker]["streak"] = 0
        with open(LOG_PATH, "w") as f:
            json.dump(log, f, indent=2, default=str)
        print(f"✅  ETF streak reset to 0 for {ticker}.")
    else:
        print(f"{ticker} not in streak log. Keys: {list(es.keys())}")

def reset_manager(manager):
    if not os.path.exists(LOG_PATH):
        print("No log file found.")
        return
    with open(LOG_PATH) as f:
        log = json.load(f)
    ms = log.setdefault("manager_streaks", {})
    ms[manager] = {"streak": 0}
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)
    print(f"✅  Manager streak reset to 0 for {manager}.")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python reset_streak.py TICKER")
        print("       python reset_streak.py --manager Hamilton")
    elif args[0] == "--manager" and len(args) > 1:
        reset_manager(args[1])
    else:
        reset_etf(args[0])
