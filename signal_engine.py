"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       THE DIVIDEND LAGGARD SYSTEM — v2.6 Signal Engine                     ║
║       Runs Mon–Fri at 2:55 PM EST via GitHub Actions                       ║
║       Writes signal_output.json and deployment_log.json                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
import time, json, os, sys

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

CAD_UNIVERSE = ["HUTL.TO", "RMAX.TO", "SDAY.TO", "QDAY.TO", "AMAX.TO", "HHL.TO"]
USD_UNIVERSE = ["HYLD-U.TO", "HBND-U.TO"]

HAMILTON_ETFS = {"HUTL.TO", "RMAX.TO", "SDAY.TO", "QDAY.TO", "AMAX.TO"}
HARVEST_ETFS  = {"HHL.TO"}

# ── Step 0 ────────────────────────────────────────────────────────────────────
S5TH_FLOOR         = 50
NYMO_ROUTINE_FLOOR = -40

# ── Step 0.5 — Fund Quality Vetoes ────────────────────────────────────────────
AUM_FLOOR_CAD      = 50_000_000   # $50M CAD
AUM_FLOOR_USD      = 40_000_000   # $40M USD
DIST_CUT_THRESHOLD = 0.10         # >10% below 3-month avg = cut
VOLUME_FLOOR       = 50_000       # 20-day avg daily volume
PEER_LOOKBACK_DAYS = 63           # ~3 months of trading days

# ── Step 1 ────────────────────────────────────────────────────────────────────
SMA_FAST           = 50
SMA_SLOW           = 200
ATR_MULTIPLIER     = 0.5          # Price must be >= ATR*0.5 below 50 SMA

# ── Step 2 ────────────────────────────────────────────────────────────────────
RSI_FAST_PASS      = 25
ADX_PASS           = 30
ADX_PASS_SL        = 25           # Structural laggard tighter threshold
RSI_OVERRIDE       = 40
RSI_OVERRIDE_SL    = 35
RSI_PERIOD         = 14
ADX_PERIOD         = 14
ATR_PERIOD         = 14
DATA_DAYS          = 300

LOG_PATH    = "deployment_log.json"
OUTPUT_PATH = "signal_output.json"

# ══════════════════════════════════════════════════════════════════════════════
# CONSOLE COLOURS (for GitHub Actions logs)
# ══════════════════════════════════════════════════════════════════════════════
RESET  = "\033[0m";  BOLD   = "\033[1m";  GREEN  = "\033[92m"
RED    = "\033[91m"; YELLOW = "\033[93m"; CYAN   = "\033[96m"
GOLD   = "\033[33m"; GREY   = "\033[90m"

def hdr(t):  print(f"\n{GOLD}{'═'*70}\n  {BOLD}{t.upper()}{RESET}\n{GOLD}{'═'*70}{RESET}")
def ok(t):   print(f"  {GREEN}✅  {t}{RESET}")
def fail(t): print(f"  {RED}❌  {t}{RESET}")
def warn(t): print(f"  {YELLOW}⚠️   {t}{RESET}")
def info(t): print(f"  {GREY}     {t}{RESET}")
def fire(t): print(f"  {GOLD}{BOLD}🔥  {t}{RESET}")

# ══════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATIONS  (Wilder smoothing — matches TradingView defaults)
# ══════════════════════════════════════════════════════════════════════════════

def flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns returned by newer yfinance single-ticker downloads."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def calc_rsi(s: pd.Series, p: int = 14) -> float:
    d  = s.diff()
    ag = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return round(float((100 - 100/(1+rs)).iloc[-1]), 2)

def calc_adx(h: pd.Series, l: pd.Series, c: pd.Series, p: int = 14) -> float:
    tr   = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    up   = h - h.shift(); dn = l.shift() - l
    pdm  = np.where((up > dn) & (up > 0), up, 0.0)
    mdm  = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr  = tr.ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    pdi  = 100*pd.Series(pdm).ewm(alpha=1/p, min_periods=p, adjust=False).mean()/atr
    mdi  = 100*pd.Series(mdm).ewm(alpha=1/p, min_periods=p, adjust=False).mean()/atr
    dx   = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan))
    return round(float(dx.ewm(alpha=1/p, min_periods=p, adjust=False).mean().iloc[-1]), 2)

def calc_atr(h: pd.Series, l: pd.Series, c: pd.Series, p: int = 14) -> float:
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return round(float(tr.ewm(alpha=1/p, min_periods=p, adjust=False).mean().iloc[-1]), 4)

def calc_macd(s: pd.Series) -> dict:
    """Returns PRIOR closed candle values to avoid intraday repainting."""
    m  = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    sig = m.ewm(span=9, adjust=False).mean()
    hist_prev2 = float((m - sig).iloc[-3])   # two candles ago
    hist_prev1 = float((m - sig).iloc[-2])   # prior closed candle
    return {
        "macd":          round(float(m.iloc[-2]), 4),
        "signal":        round(float(sig.iloc[-2]), 4),
        "bullish_cross": float(m.iloc[-2]) > float(sig.iloc[-2]),
        "hist_improving": hist_prev1 > hist_prev2,   # for fast-pass confirmation
    }

def calc_sma(s: pd.Series, p: int) -> float:
    return round(float(s.rolling(p).mean().iloc[-1]), 4)

def calc_roc_2day(s: pd.Series) -> float:
    """2-day Rate of Change: positive means price is rising."""
    return float(s.iloc[-1]) - float(s.iloc[-3])

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 — MACRO
# ══════════════════════════════════════════════════════════════════════════════

def get_sp500_tickers() -> list:
    print(f"  {GREY}Fetching S&P 500 tickers from Wikipedia...{RESET}", end="", flush=True)
    try:
        url  = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        soup = BeautifulSoup(requests.get(url, timeout=15).text, "html.parser")
        tickers = [r.find_all("td")[0].text.strip().replace(".", "-")
                   for r in soup.find("table", {"id":"constituents"}).find_all("tr")[1:]
                   if r.find_all("td")]
        print(f"  {GREEN}{len(tickers)} tickers found.{RESET}")
        return tickers
    except Exception as e:
        print(f"  {RED}FAILED: {e}{RESET}")
        return []

def calculate_s5th(tickers: list, retries: int = 2) -> float:
    if not tickers:
        return None
    for attempt in range(1, retries + 2):
        try:
            print(f"  {GREY}Bulk S5TH download (attempt {attempt})...{RESET}", end="\r", flush=True)
            data = yf.download(" ".join(tickers), period="1y", interval="1d",
                               progress=False, auto_adjust=True,
                               group_by="ticker", threads=True)
            above, valid = 0, 0
            for t in tickers:
                try:
                    cl = data["Close"][t].dropna()
                    if len(cl) >= 200:
                        if float(cl.iloc[-1]) > float(cl.rolling(200).mean().iloc[-1]):
                            above += 1
                        valid += 1
                except Exception:
                    pass
            print(f"  {GREY}S5TH processed {valid} tickers.          {RESET}")
            return round((above/valid)*100, 1) if valid else None
        except Exception as e:
            if attempt <= retries:
                wait = 15 * attempt
                print(f"\n  {YELLOW}S5TH attempt {attempt} failed ({e}). Retrying in {wait}s...{RESET}")
                time.sleep(wait)
            else:
                print(f"\n  {RED}S5TH failed after {retries+1} attempts.{RESET}")
                print(f"  {YELLOW}Override manually: python signal_engine.py --s5th <value>{RESET}")
                return None

def get_nymo() -> float:
    try:
        data = yf.download("^NYMO", period="5d", progress=False, auto_adjust=True)
        if not data.empty:
            return round(float(data["Close"].dropna().iloc[-1]), 2)
    except Exception:
        pass
    try:
        nyad = yf.download("^NYAD", period="120d", progress=False, auto_adjust=True)
        if not nyad.empty and len(nyad) >= 60:
            net = nyad["Close"].dropna().diff().dropna()
            return round(float((net.ewm(span=19,adjust=False).mean()
                                - net.ewm(span=39,adjust=False).mean()).iloc[-1]), 2)
    except Exception:
        pass
    return None

def evaluate_macro(s5th, nymo) -> dict:
    if s5th is None or nymo is None:
        return {"signal":"DATA ERROR","emoji":"⚠️","deploy":False,"heavy":False,
                "fast_pass_active":False,"action":"Cannot evaluate macro. Do not deploy.",
                "s5th":s5th,"nymo":nymo}
    if s5th > S5TH_FLOOR and nymo >= NYMO_ROUTINE_FLOOR:
        return {"signal":"MACRO HEALTHY / ROUTINE PULLBACK","emoji":"🟢","deploy":True,"heavy":False,
                "fast_pass_active":True,
                "action":"Standard Deploy. Run matrix. Fast-Pass ACTIVE.",
                "s5th":s5th,"nymo":nymo}
    if s5th > S5TH_FLOOR and nymo < NYMO_ROUTINE_FLOOR:
        return {"signal":"SCREAMING BUY","emoji":"🔥","deploy":True,"heavy":True,
                "fast_pass_active":False,
                "action":"Heavy Deploy. 100% distributions + 10% reserve tap (max 3/cycle). Fast-Pass DISABLED.",
                "s5th":s5th,"nymo":nymo}
    if s5th <= S5TH_FLOOR and nymo > 0:
        return {"signal":"DEAD CAT BOUNCE","emoji":"🟡","deploy":False,"heavy":False,
                "fast_pass_active":False,
                "action":"Hold / Watch. Park in Safe Havens. Re-evaluate next session.",
                "s5th":s5th,"nymo":nymo}
    return {"signal":"SYSTEM ABORT","emoji":"🔴","deploy":False,"heavy":False,
            "fast_pass_active":False,
            "action":"Total Pause. Park 100% in Safe Havens until S5TH > 50.",
            "s5th":s5th,"nymo":nymo}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0.5 — FUND QUALITY VETOES
# ══════════════════════════════════════════════════════════════════════════════

def veto_check(ticker: str, aum_floor: float, all_returns: dict) -> dict:
    """
    Run all four fund quality vetoes. Returns per-veto pass/fail and reasons.
    all_returns: dict of {ticker: 3m_return} for peer comparison.
    """
    vetoes = {
        "aum":      {"pass": None, "value": None, "reason": ""},
        "dist_cut": {"pass": None, "value": None, "reason": ""},
        "liquidity":{"pass": None, "value": None, "reason": ""},
        "peer_nav": {"pass": None, "value": None, "reason": ""},
    }
    disqualified = False

    try:
        info = yf.Ticker(ticker).info
        # ── Veto 1: AUM ────────────────────────────────────────────────────────
        aum = info.get("totalAssets", None)
        if aum is not None:
            vetoes["aum"]["value"] = aum
            if aum < aum_floor:
                vetoes["aum"]["pass"]   = False
                vetoes["aum"]["reason"] = f"AUM ${aum/1e6:.1f}M below ${aum_floor/1e6:.0f}M floor"
                disqualified = True
            else:
                vetoes["aum"]["pass"]   = True
                vetoes["aum"]["reason"] = f"AUM ${aum/1e6:.1f}M ✓"
        else:
            vetoes["aum"]["pass"]   = True   # Data unavailable — don't penalise
            vetoes["aum"]["reason"] = "AUM data unavailable — skipped"
    except Exception:
        vetoes["aum"]["pass"]   = True
        vetoes["aum"]["reason"] = "AUM data error — skipped"

    try:
        hist = yf.Ticker(ticker).dividends
        if len(hist) >= 4:
            recent     = float(hist.iloc[-1])
            avg_prior3 = float(hist.iloc[-4:-1].mean())
            cut_pct    = (avg_prior3 - recent) / avg_prior3 if avg_prior3 > 0 else 0
            vetoes["dist_cut"]["value"]  = round(cut_pct * 100, 2)
            if cut_pct > DIST_CUT_THRESHOLD:
                vetoes["dist_cut"]["pass"]   = False
                vetoes["dist_cut"]["reason"] = f"Distribution cut {cut_pct*100:.1f}% vs 3-month avg"
                disqualified = True
            else:
                vetoes["dist_cut"]["pass"]   = True
                vetoes["dist_cut"]["reason"] = f"Distribution stable ({cut_pct*100:.1f}% change) ✓"
        else:
            vetoes["dist_cut"]["pass"]   = True
            vetoes["dist_cut"]["reason"] = "Insufficient distribution history — skipped"
    except Exception:
        vetoes["dist_cut"]["pass"]   = True
        vetoes["dist_cut"]["reason"] = "Distribution data error — skipped"

    try:
        raw   = flatten(yf.download(ticker, period=f"{DATA_DAYS}d", interval="1d",
                            progress=False, auto_adjust=True))
        vol20 = float(raw["Volume"].dropna().tail(20).mean()) if not raw.empty else 0
        vetoes["liquidity"]["value"] = int(vol20)
        if vol20 < VOLUME_FLOOR:
            vetoes["liquidity"]["pass"]   = False
            vetoes["liquidity"]["reason"] = f"20-day avg volume {int(vol20):,} below {VOLUME_FLOOR:,} floor"
            disqualified = True
        else:
            vetoes["liquidity"]["pass"]   = True
            vetoes["liquidity"]["reason"] = f"Volume {int(vol20):,}/day ✓"
    except Exception:
        vetoes["liquidity"]["pass"]   = True
        vetoes["liquidity"]["reason"] = "Volume data error — skipped"

    # ── Veto 4: Peer NAV underperformance ──────────────────────────────────────
    my_return = all_returns.get(ticker, None)
    if my_return is not None and len(all_returns) > 1:
        other_returns = [v for k, v in all_returns.items() if k != ticker and v is not None]
        is_last    = all(my_return >= r for r in other_returns) == False and \
                     my_return <= min(other_returns) if other_returns else False
        is_negative = my_return < 0
        vetoes["peer_nav"]["value"] = round(my_return * 100, 2)
        if is_negative and is_last:
            vetoes["peer_nav"]["pass"]   = False
            vetoes["peer_nav"]["reason"] = f"3M return {my_return*100:.1f}% — negative AND bottom of peer group"
            disqualified = True
        else:
            vetoes["peer_nav"]["pass"]   = True
            vetoes["peer_nav"]["reason"] = f"3M return {my_return*100:.1f}% — peer check passed ✓"
    else:
        vetoes["peer_nav"]["pass"]   = True
        vetoes["peer_nav"]["reason"] = "Peer data insufficient — skipped"

    return {"vetoes": vetoes, "disqualified": disqualified}


def get_universe_returns(tickers: list) -> dict:
    """Calculate 3-month total return for all universe tickers (adjusted price)."""
    returns = {}
    try:
        data = yf.download(" ".join(tickers), period="6mo", interval="1d",
                           progress=False, auto_adjust=True,
                           group_by="ticker", threads=True)
        for t in tickers:
            try:
                cl = data["Close"][t].dropna() if len(tickers) > 1 else data["Close"].dropna()
                if len(cl) >= PEER_LOOKBACK_DAYS:
                    returns[t] = float((cl.iloc[-1] - cl.iloc[-PEER_LOOKBACK_DAYS]) / cl.iloc[-PEER_LOOKBACK_DAYS])
            except Exception:
                pass
    except Exception:
        pass
    return returns

# ══════════════════════════════════════════════════════════════════════════════
# STEPS 1 & 2 — ETF ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyse_etf(ticker: str, fast_pass_active: bool, veto_result: dict) -> dict:
    result = {
        "ticker": ticker, "veto_result": veto_result,
        "disqualified": veto_result["disqualified"],
        "step1_pass": False, "step2_pass": False, "final_pass": False,
        "structural_laggard": False, "pass_type": None,
        "price": None, "sma50": None, "sma200": None,
        "atr": None, "atr_discount": None, "discount_pct": None,
        "rsi": None, "adx": None, "macd": None,
        "prev_green": None, "roc_2day": None,
        "error": None,
    }

    if veto_result["disqualified"]:
        return result

    try:
        raw = flatten(yf.download(ticker, period=f"{DATA_DAYS}d", interval="1d",
                          progress=False, auto_adjust=True))
        if raw.empty or len(raw) < 220:
            result["error"] = f"Insufficient data ({len(raw)} rows)"
            return result

        cl = raw["Close"].dropna()
        hi = raw["High"].dropna()
        lo = raw["Low"].dropna()
        op = raw["Open"].dropna()

        price  = float(cl.iloc[-1])
        sma50  = calc_sma(cl, SMA_FAST)
        sma200 = calc_sma(cl, SMA_SLOW)
        atr    = calc_atr(hi, lo, cl, ATR_PERIOD)
        rsi    = calc_rsi(cl, RSI_PERIOD)
        adx    = calc_adx(hi, lo, cl, ADX_PERIOD)
        macd   = calc_macd(cl)

        atr_discount   = round(sma50 - price, 4)
        atr_threshold  = round(atr * ATR_MULTIPLIER, 4)
        discount_pct   = round((atr_discount / sma50) * 100, 2) if sma50 > 0 else 0
        structural_lag = sma50 < sma200

        # Fast-pass confirming signals (prior closed candle)
        prev_green   = float(cl.iloc[-2]) > float(op.iloc[-2])
        roc_2day     = calc_roc_2day(cl) > 0

        result.update({
            "price": round(price, 4), "sma50": sma50, "sma200": sma200,
            "atr": atr, "atr_discount": atr_discount, "atr_threshold": atr_threshold,
            "discount_pct": discount_pct, "structural_laggard": structural_lag,
            "rsi": rsi, "adx": adx, "macd": macd,
            "prev_green": prev_green, "roc_2day": roc_2day,
        })

        # ── STEP 1 ─────────────────────────────────────────────────────────────
        step1_pass = atr_discount >= atr_threshold
        result["step1_pass"] = step1_pass
        if not step1_pass:
            return result

        # ── STEP 2 ─────────────────────────────────────────────────────────────
        adx_thr = ADX_PASS_SL if structural_lag else ADX_PASS
        rsi_ov  = RSI_OVERRIDE_SL if structural_lag else RSI_OVERRIDE

        # Capitulation fast-pass: RSI < 25 + macro green + one confirming signal
        if fast_pass_active and rsi < RSI_FAST_PASS:
            confirming = prev_green or roc_2day or macd["hist_improving"]
            if confirming:
                result["step2_pass"] = True
                signals = []
                if prev_green:       signals.append("prior green candle")
                if roc_2day:         signals.append("positive 2-day ROC")
                if macd["hist_improving"]: signals.append("MACD histogram improving")
                result["pass_type"] = f"fast_pass ({signals[0]})"
            else:
                # RSI < 25 but no confirmation — falls through to normal checks
                pass

        if not result["step2_pass"]:
            if adx < adx_thr:
                result["step2_pass"] = True
                result["pass_type"]  = "clean"
            elif rsi < rsi_ov:
                result["step2_pass"] = True
                result["pass_type"]  = "override_rsi"
            elif macd["bullish_cross"]:
                result["step2_pass"] = True
                result["pass_type"]  = "override_macd"
            else:
                result["pass_type"]  = "fail"

        result["final_pass"] = result["step1_pass"] and result["step2_pass"]

    except Exception as e:
        result["error"] = str(e)

    return result

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — COMPOSITE RANKING & CONCENTRATION
# ══════════════════════════════════════════════════════════════════════════════

def composite_rank(results: list) -> list:
    """
    Rank green-light ETFs by composite score: RSI rank + ATR discount rank.
    Lower composite score = better candidate.
    """
    green = [r for r in results if r["final_pass"]]
    if not green:
        return green

    # Rank by RSI ascending (lowest RSI = rank 1)
    rsi_sorted = sorted(green, key=lambda x: x["rsi"])
    for i, r in enumerate(rsi_sorted):
        r["rsi_rank"] = i + 1

    # Rank by ATR discount descending (largest discount = rank 1)
    atr_sorted = sorted(green, key=lambda x: x["atr_discount"], reverse=True)
    for i, r in enumerate(atr_sorted):
        r["atr_rank"] = i + 1

    # Composite score
    for r in green:
        r["composite_score"] = r["rsi_rank"] + r["atr_rank"]

    # Sort by composite (ties broken by RSI)
    return sorted(green, key=lambda x: (x["composite_score"], x["rsi"]))


def load_log() -> dict:
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            return json.load(f)
    return {"deployments": [], "etf_streaks": {}, "manager_streaks": {}}


def save_log(log: dict):
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)


def check_concentration(ranked: list, log: dict) -> dict:
    """Apply ETF + manager concentration caps. Returns final deployment target."""
    if not ranked:
        return {"target": None, "reason": "No ETFs passed the matrix.", "ranked": []}

    etf_streaks  = log.get("etf_streaks", {})
    mgr_streaks  = log.get("manager_streaks", {})

    for candidate in ranked:
        ticker  = candidate["ticker"]
        manager = "Hamilton" if ticker in HAMILTON_ETFS else "Harvest"

        etf_streak = etf_streaks.get(ticker, {}).get("streak", 0)
        mgr_streak = mgr_streaks.get(manager, {}).get("streak", 0)

        etf_blocked = etf_streak >= 3
        mgr_blocked = mgr_streak >= 3 and manager == "Hamilton"

        if not etf_blocked and not mgr_blocked:
            return {
                "target": candidate,
                "reason": f"#{ranked.index(candidate)+1} composite rank. ETF streak: {etf_streak}/3. Manager streak: {mgr_streak}/3.",
                "ranked": ranked,
                "etf_blocked": False,
                "mgr_blocked": False,
            }

        reasons = []
        if etf_blocked: reasons.append(f"{ticker} at 3-month ETF streak")
        if mgr_blocked: reasons.append(f"{manager} at 3-month manager streak")

    # All candidates blocked — deploy into top ranked anyway to keep cash working
    return {
        "target": ranked[0],
        "reason": "All candidates blocked by concentration rules. Deploying #1 to keep cash working.",
        "ranked": ranked,
        "all_blocked": True,
    }


def record_deployment(ticker: str, result: dict, macro: dict, log: dict):
    """Log the deployment and update streak counters."""
    today    = date.today()
    manager  = "Hamilton" if ticker in HAMILTON_ETFS else "Harvest"

    entry = {
        "date":            str(today),
        "ticker":          ticker,
        "macro_signal":    macro["signal"],
        "macro_emoji":     macro["emoji"],
        "composite_score": result.get("composite_score"),
        "rsi_rank":        result.get("rsi_rank"),
        "atr_rank":        result.get("atr_rank"),
        "rsi":             result.get("rsi"),
        "adx":             result.get("adx"),
        "atr_discount":    result.get("atr_discount"),
        "pass_type":       result.get("pass_type"),
        "entry_price":     result.get("price"),
        "manager":         manager,
        "forward_1m":      None,  # filled by audit.py
        "forward_3m":      None,
        "distributions":   None,
    }
    log["deployments"].append(entry)

    # Update ETF streak
    es = log.setdefault("etf_streaks", {})
    for t in list(es.keys()):
        if t != ticker:
            es[t]["streak"] = 0
    if ticker not in es:
        es[ticker] = {"streak": 0, "last_month": None, "last_year": None}
    es[ticker]["streak"] += 1
    es[ticker]["last_month"] = today.month
    es[ticker]["last_year"]  = today.year

    # Update manager streak
    ms = log.setdefault("manager_streaks", {})
    for m in list(ms.keys()):
        if m != manager:
            ms[m] = {"streak": 0}
    if manager not in ms:
        ms[manager] = {"streak": 0}
    ms[manager]["streak"] += 1

    save_log(log)


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT — Write JSON for dashboard
# ══════════════════════════════════════════════════════════════════════════════

def write_output(macro: dict, cad_results: list, usd_results: list,
                 cad_decision: dict, usd_decision: dict):
    """Serialise all results to signal_output.json for the Streamlit dashboard."""

    def serialise_result(r: dict) -> dict:
        """Make a result dict JSON-safe."""
        out = {k: v for k, v in r.items() if k not in ("macd",)}
        if r.get("macd"):
            out["macd_bullish_cross"]  = r["macd"].get("bullish_cross")
            out["macd_hist_improving"] = r["macd"].get("hist_improving")
        # Convert numpy types
        for k, v in out.items():
            if isinstance(v, (np.integer, np.int64)):  out[k] = int(v)
            elif isinstance(v, (np.floating, np.float64)): out[k] = float(v)
            elif isinstance(v, np.bool_): out[k] = bool(v)
        return out

    def serialise_decision(d: dict) -> dict:
        out = {k: v for k, v in d.items() if k not in ("target", "ranked")}
        if d.get("target"):
            out["target"] = serialise_result(d["target"])
        if d.get("ranked"):
            out["ranked"] = [serialise_result(r) for r in d["ranked"]]
        return out

    output = {
        "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M EST"),
        "generated_date": str(date.today()),
        "macro":         macro,
        "cad": {
            "results":  [serialise_result(r) for r in cad_results],
            "decision": serialise_decision(cad_decision),
        },
        "usd": {
            "results":  [serialise_result(r) for r in usd_results],
            "decision": serialise_decision(usd_decision),
        },
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  {GREEN}✅  signal_output.json written.{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    args = {"s5th": None, "nymo": None}
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--s5th" and i+1 < len(argv):
            try: args["s5th"] = float(argv[i+1])
            except ValueError: pass
        if a == "--nymo" and i+1 < len(argv):
            try: args["nymo"] = float(argv[i+1])
            except ValueError: pass
    return args


def run():
    args = parse_args()
    now  = datetime.now()
    print(f"\n{GOLD}{'█'*70}{RESET}")
    print(f"{GOLD}  THE DIVIDEND LAGGARD SYSTEM  —  v2.6")
    print(f"  {now.strftime('%A, %B %d, %Y  |  %H:%M EST')}{RESET}")
    print(f"{GOLD}{'█'*70}{RESET}")

    # ── STEP 0 ────────────────────────────────────────────────────────────────
    hdr("Step 0 — Macro Circuit Breaker")
    if args["s5th"] is not None:
        s5th = args["s5th"]
        warn(f"S5TH MANUAL OVERRIDE: {s5th}%")
    else:
        tickers = get_sp500_tickers()
        s5th    = calculate_s5th(tickers)

    if args["nymo"] is not None:
        nymo = args["nymo"]
        warn(f"NYMO MANUAL OVERRIDE: {nymo}")
    else:
        print(f"  {GREY}Fetching NYMO...{RESET}", end="", flush=True)
        nymo = get_nymo()
        print(f"  {'✓' if nymo else '✗'}  NYMO: {nymo}")

    macro = evaluate_macro(s5th, nymo)
    s5th_str = f"{s5th:.1f}%" if s5th is not None else "N/A"
    print(f"\n  S5TH: {BOLD}{s5th_str}{RESET}   NYMO: {BOLD}{nymo if nymo is not None else 'N/A'}{RESET}")
    print(f"\n  {macro['emoji']}  {BOLD}{macro['signal']}{RESET}")
    print(f"  {GREY}{macro['action']}{RESET}")

    if not macro["deploy"]:
        print(f"\n{RED}  SYSTEM HALTED — Parking all cash in Safe Havens.{RESET}\n")
        cad_results = [{
            "ticker": t, "disqualified": False, "step1_pass": False,
            "step2_pass": False, "final_pass": False, "pass_type": "system_halt",
            "veto_result": {"vetoes": {}, "disqualified": False}
        } for t in CAD_UNIVERSE]
        usd_results = [{
            "ticker": t, "disqualified": False, "step1_pass": False,
            "step2_pass": False, "final_pass": False, "pass_type": "system_halt",
            "veto_result": {"vetoes": {}, "disqualified": False}
        } for t in USD_UNIVERSE]
        write_output(macro, cad_results, usd_results,
                     {"target": None, "reason": "System halted.", "ranked": []},
                     {"target": None, "reason": "System halted.", "ranked": []})
        return

    if macro["heavy"]:
        fire("HEAVY DEPLOY MODE — distributions + 10% reserve tap.")

    # ── STEP 0.5 — FUND QUALITY VETOES ────────────────────────────────────────
    hdr("Step 0.5 — Fund Quality Vetoes")

    cad_returns = get_universe_returns(CAD_UNIVERSE)
    usd_returns = get_universe_returns(USD_UNIVERSE)

    cad_vetoes, usd_vetoes = {}, {}
    for t in CAD_UNIVERSE:
        print(f"  {GREY}Vetting {t}...{RESET}", end="\r", flush=True)
        cad_vetoes[t] = veto_check(t, AUM_FLOOR_CAD, cad_returns)
        if cad_vetoes[t]["disqualified"]:
            fail(f"{t:12s}  DISQUALIFIED — " +
                 " | ".join(v["reason"] for v in cad_vetoes[t]["vetoes"].values()
                            if v["pass"] is False))
        else:
            ok(f"{t:12s}  All vetoes passed")
        time.sleep(0.3)

    for t in USD_UNIVERSE:
        print(f"  {GREY}Vetting {t}...{RESET}", end="\r", flush=True)
        usd_vetoes[t] = veto_check(t, AUM_FLOOR_USD, usd_returns)
        if usd_vetoes[t]["disqualified"]:
            fail(f"{t:12s}  DISQUALIFIED — " +
                 " | ".join(v["reason"] for v in usd_vetoes[t]["vetoes"].values()
                            if v["pass"] is False))
        else:
            ok(f"{t:12s}  All vetoes passed")
        time.sleep(0.3)

    # ── STEPS 1 & 2 ───────────────────────────────────────────────────────────
    hdr("Steps 1 & 2 — Trend, Structure & Risk")
    fp = macro["fast_pass_active"]
    cad_results, usd_results = [], []

    for t in CAD_UNIVERSE:
        print(f"  {GREY}Analysing {t}...{RESET}", end="\r", flush=True)
        r = analyse_etf(t, fp, cad_vetoes[t])
        cad_results.append(r)
        time.sleep(0.2)

    for t in USD_UNIVERSE:
        print(f"  {GREY}Analysing {t}...{RESET}", end="\r", flush=True)
        r = analyse_etf(t, fp, usd_vetoes[t])
        usd_results.append(r)
        time.sleep(0.2)

    print(" " * 50, end="\r")

    for r in cad_results + usd_results:
        t = r["ticker"]
        if r["disqualified"]:
            fail(f"{t:12s}  Vetoed (skipped chart analysis)")
        elif r["error"]:
            fail(f"{t:12s}  ERROR: {r['error']}")
        elif not r["step1_pass"]:
            disc = r.get("atr_discount", 0) or 0
            thr  = r.get("atr_threshold", 0) or 0
            fail(f"{t:12s}  Step 1 FAIL — discount {disc:.4f} < ATR threshold {thr:.4f}")
        elif r["final_pass"]:
            ok(f"{t:12s}  RSI:{r['rsi']:5.1f}  ADX:{r['adx']:5.1f}  "
               f"Discount:{r['discount_pct']:+.2f}%  →  {r['pass_type']}"
               + (" [SL]" if r.get("structural_laggard") else ""))
        else:
            fail(f"{t:12s}  Step 2 FAIL — {r['pass_type']}  "
                 f"RSI:{r['rsi']:5.1f}  ADX:{r['adx']:5.1f}")

    # ── STEP 3 ────────────────────────────────────────────────────────────────
    hdr("Step 3 — Composite Ranking & Deployment")
    log = load_log()

    cad_ranked   = composite_rank(cad_results)
    usd_ranked   = composite_rank(usd_results)
    cad_decision = check_concentration(cad_ranked, log)
    usd_decision = check_concentration(usd_ranked, log)

    # ── FINAL ORDERS ──────────────────────────────────────────────────────────
    print(f"\n{GOLD}{'═'*70}{RESET}")
    print(f"{GOLD}  FINAL ORDERS{RESET}")
    print(f"{GOLD}{'═'*70}{RESET}")

    cad_target = cad_decision.get("target")
    usd_target = usd_decision.get("target")

    if cad_target:
        fire(f"CAD:  Buy {cad_target['ticker']}  "
             f"(Score:{cad_target.get('composite_score','?')}  "
             f"RSI:{cad_target['rsi']:.1f}  Discount:{cad_target['discount_pct']:+.2f}%)")
        record_deployment(cad_target["ticker"], cad_target, macro, log)
    else:
        warn("CAD:  No qualified target. Park in CASH.TO.")

    if usd_target:
        fire(f"USD:  Buy {usd_target['ticker']}  "
             f"(Score:{usd_target.get('composite_score','?')}  "
             f"RSI:{usd_target['rsi']:.1f}  Discount:{usd_target['discount_pct']:+.2f}%)")
        record_deployment(usd_target["ticker"], usd_target, macro, log)
    else:
        warn("USD:  No qualified target. Park in PSU.U.TO.")

    if macro["heavy"]:
        fire("REMEMBER: Tap 10% of Safe Haven reserve in addition to distributions.")

    print(f"\n  {GREY}Execute in Wealthsimple. Close app. Walk away.{RESET}")
    print(f"{GOLD}{'═'*70}{RESET}\n")

    # ── WRITE JSON ────────────────────────────────────────────────────────────
    write_output(macro, cad_results, usd_results, cad_decision, usd_decision)


if __name__ == "__main__":
    run()
