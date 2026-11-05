#!/usr/bin/env python3
pass
import json, math, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kronos_live as kl                                                                  

SYMS = ["GER40", "UK100", "EUSTX50", "US500", "NAS100", "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "XAGUSD", "SPOTCRUDE"]
FOCUS = {"NAS100", "GER40", "US500", "XAUUSD", "EURUSD"}                                                                    
ORACLE = [s for s in SYMS if s not in FOCUS]
LON = ZoneInfo("Europe/London")
SES = {"session": "London", "tz": "Europe/London", "open": "08:00", "close": "16:30"}
DUE_FROM, DUE_TO = (7, 25), (12, 0)                                                       
KEEP_DAYS = 30
PATHS, CTX = 24, 192
UA = kl.UA


def tk_of(sym):
    return kl.proxy_of("PEPPERSTONE", sym)


def yahoo_iv(tk, iv, rng):
    for host in ("query1", "query2"):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(tk)}?interval={iv}&range={rng}&includePrePost=false"
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 r3m-reef"}), timeout=20))["chart"]["result"][0]
            q = d["indicators"]["quote"][0]
            return [(t, o, h, l, c) for t, o, h, l, c in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
        except Exception as ex:
            err = ex
    print(f"  {tk} {iv}: no bars ({err})")
    return []


def bars5(sym, rng="5d"):
    pass
    tk = tk_of(sym)
    rows, _ = kl.yahoo(tk, rng)
    if not rows:
        return None, tk
    lab = tk
    if tk in kl.UBS or tk in kl.TURBO:
        try:
            rows, src = kl.live_fill(rows, tk, sym)
            if src:
                lab += " + " + src
        except Exception as ex:
            print(f"  {sym}: live fill failed ({ex})")
    return rows, lab


def agg(rows, step):
    pass
    out = {}
    for r in rows:
        t, o, h, l, c = r[:5]
        v = r[5] if len(r) > 5 else 0
        b = t // step * step
        if b in out:
            oo, hh, ll, _c, vv = out[b]
            out[b] = (oo, max(hh, h), min(ll, l), c, vv + v)
        else:
            out[b] = (o, h, l, c, v)
    return [(b, *x) for b, x in sorted(out.items())]


def at(rows, t, tol=600):
    pass
    best = None
    for r in rows:
        if r[0] <= t < r[0] + 300 + tol:
            best = r
    return best[4] if best else None


def asof_utc(M):
    pass
    m = re.search(r"(\d{1,2}):(\d{2})", M.get("asof") or "")
    if not m or not M.get("date"):
        return None
    d = datetime.strptime(M["date"], "%Y-%m-%d").replace(hour=int(m[1]), minute=int(m[2]), tzinfo=ZoneInfo("Europe/Berlin"))
    return int(d.timestamp())


def factor(sym, rows, M, ent):
    pass
    cands = [(int(datetime.fromisoformat(e["t"]).timestamp()) - 300, float(e["px"])) for e in ent if e["sym"] == sym]
    p = next((x for x in M.get("pepper", []) if x["sym"] == sym), None)
    ta = asof_utc(M)
    if p and ta:
        cands.append((ta, float(p["price"])))
    for t, px in sorted(cands, reverse=True):
        y = at(rows, t)
        if y:
            return px / y, t
    return 1.0, None


def trades_of(sym, ent, res, day):
    pass
    out = []
    for e in ent:
        if e["sym"] != sym or datetime.fromisoformat(e["t"]).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat() != day:
            continue
        rr = [r for r in res if r["sym"] == sym and r["tf"] == e["tf"] and r["side"] == e["side"] and r["px"] == e["px"] and r["t"] >= e["t"]]
        x = {"t": e["t"], "script": ("af" if e["script"] == "lava" else e["script"] + " af") if e["af"] else e["script"], "side": e["side"],
             "entry": float(e["px"]), "sl": float(e["sl"]), "tp1": float(e["tp1"]), "tp2": float(e["tp2"]) if e["tp2"] else None,
             "r1": e["r1"], "res": "open", "rg": None, "tx": None}
        for r in rr:                                                                                                                 
            k = r["kind"]                                                                                     
            x["tx"] = r["t"]
            if x["res"] in ("TP1 Hit", "TP2 Hit") and k not in ("TP2 Hit", "AF Target"):
                continue
            x["rg"] = r["r"]
            x["res"] = ("Stopped" if "Stopped" in k else "TP2 Hit" if k in ("TP2 Hit", "AF Target") else
                        "TP1 Hit" if k in ("TP1 Hit", "AF TP1 Hit", "Runner Closed") else "Closed")
        out.append(x)
    return out


def rnd(x, ref):
    d = 1 if abs(ref) >= 1000 else 2 if abs(ref) >= 10 else 5
    return round(x, d)


FF_URLS = ["https://nfs.faireconomy.media/ff_calendar_thisweek.json", "https://nfs.faireconomy.media/ff_calendar_nextweek.json"]
FF_EVERY = 30 * 60                                                                                                           
FF_IMP = {"High": 1, "Medium": 0, "Low": -1}


def ff_calendar(old):
    pass
    if old and time.time() - (old.get("t") or 0) < FF_EVERY:
        return old
    ev, ok = [], 0
    for u in FF_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            rows = json.load(urllib.request.urlopen(req, timeout=20))
            ok += 1
        except Exception as e:
            print(f"ff: {u.rsplit('/', 1)[-1]} {e}")
            continue
        for r in rows:
            if r.get("impact") not in FF_IMP:
                continue
            try:
                t = int(datetime.fromisoformat(r["date"]).timestamp())
            except Exception:
                continue
            ev.append({"t": t, "c": r.get("country", ""), "title": r.get("title", ""), "imp": FF_IMP[r["impact"]],
                       "fc": r.get("forecast", ""), "pv": r.get("previous", "")})
    if not ok:
        return old or {"t": 0, "ev": []}
    ev = sorted({(e["t"], e["c"], e["title"]): e for e in ev}.values(), key=lambda e: (e["t"], e["c"]))
    print(f"ff: {len(ev)} events")
    return {"t": int(time.time()), "ev": ev}


def live(out_path, data_path, live_path, oracle_path):
    now = time.time()
    M = (json.load(open(data_path, encoding="utf-8")).get("market") or {}) if os.path.exists(data_path) else {}
    L = json.load(open(live_path, encoding="utf-8")) if os.path.exists(live_path) else {"items": []}
    ent, res = kl.parse(L.get("items", []))
    day = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    S = {}
    for sym in SYMS:
        t1 = time.time()
        rows, lab = bars5(sym)
        if not rows:
            continue
        k, kt = factor(sym, rows, M, ent)
        p = next((x for x in M.get("pepper", []) if x["sym"] == sym), None)
        last = rows[-1]
        px = last[4] * k
        base = p["price"] / (1 + p["chg"] / 100) if p and p.get("chg") is not None else None
        m15 = [[t, rnd(c * k, px)] for t, o, h, l, c, v in agg(rows, 900) if t >= now - 36 * 3600]
        h1r = yahoo_iv(tk_of(sym), "60m", "1mo")
                                                                                          
        h5 = {t: (t, o, h, l, c) for t, o, h, l, c, v in agg(rows, 3600)}
        hh = {r[0]: r for r in h1r}
        hh.update({t: v for t, v in h5.items() if t >= (max(hh) if hh else 0) - 3600})
        h1 = [[t, rnd(o * k, px), rnd(h * k, px), rnd(l * k, px), rnd(c * k, px)] for t, (_t, o, h, l, c) in sorted(hh.items())][-72:]
                                                               
        wk = lambda t: datetime.fromtimestamp(t, timezone.utc).isocalendar()[:2]
        this = wk(now)
        prev = [r for r in h1r if wk(r[0]) < this]
        pw = [r for r in prev if wk(r[0]) == wk(prev[-1][0])] if prev else []
        S[sym] = {"tk": lab, "k": round(k, 6), "kt": kt, "px": rnd(px, px), "chg": round((px / base - 1) * 100, 2) if base else None,
                  "t": last[0], "m15": m15, "h1": h1,
                  "pwh": rnd(max(r[2] for r in pw) * k, px) if pw else None, "pwl": rnd(min(r[3] for r in pw) * k, px) if pw else None,
                  "trades": trades_of(sym, ent, res, day)}
        print(f"{sym}: {lab} · k {k:.5f} · {S[sym]['px']} · {len(m15)} × 15m · {len(h1)} × 1h · {len(S[sym]['trades'])} trades · {time.time() - t1:.1f}s")
    old = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    keep = {s: v for s, v in (old.get("symbols") or {}).items() if s not in S}                                                   
    ff = ff_calendar(old.get("ff"))
    json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "symbols": {**keep, **S}, "ff": ff},
              open(out_path, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"→ {out_path}: {len(S)} fresh, {len(keep)} kept")
    return due(oracle_path)


def due(oracle_path):
    t = datetime.now(LON)
    if t.weekday() >= 5 or not (DUE_FROM <= (t.hour, t.minute) < DUE_TO):
        return False
    O = load_o(oracle_path)
    d = next((x for x in O["days"] if x["day"] == t.date().isoformat()), None)
    return not d or any(s not in d["symbols"] and s not in d.get("skip", {}) for s in ORACLE)


def load_o(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"days": []}


def bounds(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    op = d.replace(hour=8, minute=0, tzinfo=LON)
    cl = d.replace(hour=16, minute=30, tzinfo=LON)
    return int(op.timestamp()), int(cl.timestamp())


def dec_of(xs):
    d = 0
    for x in xs[-50:]:
        s = repr(float(x))
        if "." in s and "e" not in s:
            d = max(d, len(s.split(".")[1].rstrip("0")))
    return min(d, 5)


def score(e, b15, k):
    pass
    grid = [e["t0"] + i * e["step"] for i in range(len(e["q50"]))]
    if not b15 or b15[-1][0] < grid[-1] + e["step"] or b15[0][0] > grid[0]:
        return False
    px, last, act = {r[0]: r[4] for r in b15}, None, []
    for g in grid:
        if g in px:
            last = px[g]
        elif last is None:
            prev = [r for r in b15 if r[0] < g]
            last = prev[-1][4] if prev else None
        act.append(last)
    if any(a is None for a in act):
        return False
    d = dec_of(e["q50"])
    e["actual"] = [round(a * k, d) for a in act]
    ref, af = e["ref"], e["actual"][-1]
    e["score"] = {"hit": (e["q50"][-1] - ref) * (af - ref) > 0, "inside": e["q10"][-1] <= af <= e["q90"][-1],
                  "brier": round((e["up"] - (1.0 if af > ref else 0.0)) ** 2, 4), "move": round(af - ref, d)}
    return True


def oracle(oracle_path, data_path, live_path, kronos_dir):
    import numpy as np
    import pandas as pd
    O = load_o(oracle_path)
    M = (json.load(open(data_path, encoding="utf-8")).get("market") or {}) if os.path.exists(data_path) else {}
    L = json.load(open(live_path, encoding="utf-8")) if os.path.exists(live_path) else {"items": []}
    ent, _ = kl.parse(L.get("items", []))
    today = datetime.now(LON).date().isoformat()
    D = next((x for x in O["days"] if x["day"] == today), None)
    if D is None:
        D = {"day": today, "made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "symbols": {}, "skip": {}}
        O["days"].append(D)
    pred = None
    for sym in ORACLE:
        rows, lab = bars5(sym, "1mo")
        if not rows:
            continue
        k, _ = factor(sym, rows, M, ent)
        b15 = agg(rows, 900)
        for od in O["days"]:                                                                     
            e = od["symbols"].get(sym)
            if e and "actual" not in e and od["day"] < today and score(e, b15, e.get("k", k)):
                print(f"scored {od['day']} {sym}: hit {e['score']['hit']} · inside {e['score']['inside']}")
        if sym in D["symbols"] or sym in D["skip"]:
            continue
        op, cl = bounds(today)
        keep = b15[:-1]                                                                 
        if not keep or time.time() - keep[-1][0] > 90 * 60:
            print(f"{sym}: the last bar is {((time.time() - keep[-1][0]) / 60) if keep else 0:.0f} min old, later")
            continue
        t0 = keep[-1][0] + 900
        if cl <= t0:
            D["skip"][sym] = "the session is over"
            continue
        if pred is None:
            sys.path.insert(0, kronos_dir)
            from model import Kronos, KronosTokenizer, KronosPredictor
            pred = KronosPredictor(Kronos.from_pretrained(kl.MODEL), KronosTokenizer.from_pretrained(kl.TOKZ), device="cpu", max_context=512)
        ctx = keep[-CTX:]
        t1 = time.time()
        df = pd.DataFrame({"open": [r[1] for r in ctx], "high": [r[2] for r in ctx], "low": [r[3] for r in ctx],
                           "close": [r[4] for r in ctx], "volume": [r[5] for r in ctx]}, dtype="float64")
        xt = pd.Series([datetime.fromtimestamp(r[0], LON).replace(tzinfo=None) for r in ctx])
        grid = list(range(t0, cl, 900))
        yt = pd.Series([datetime.fromtimestamp(x, LON).replace(tzinfo=None) for x in grid])
        outp = pred.predict_batch([df] * PATHS, [xt] * PATHS, [yt] * PATHS, pred_len=len(grid), T=1.0, top_p=0.9, sample_count=1, verbose=False)
        closes = np.array([o["close"].values for o in outp]) * k
        ref = ctx[-1][4] * k
        d = dec_of([ref, ctx[-2][4] * k]) if len(ctx) > 1 else 2
        d = max(d, 1 if ref >= 1000 else 2 if ref >= 10 else 5)
        q = lambda p: [round(float(v), d) for v in np.percentile(closes, p, axis=0)]
        D["symbols"][sym] = {"session": "London", "tz": "Europe/London", "step": 900, "t0": t0,
                             "open_i": next((i for i, x in enumerate(grid) if x >= op), 0), "close_i": len(grid) - 1,
                             "ref": round(ref, d), "q10": q(10), "q50": q(50), "q90": q(90),
                             "up": round(float((closes[:, -1] > ref).mean()), 3), "paths": PATHS,
                             "ctx_t0": ctx[-48:][0][0], "ctx": [round(r[4] * k, d) for r in ctx[-48:]],
                             "model": kl.MODEL.split("/")[-1], "tk": lab, "k": round(k, 6)}
        print(f"{today} {sym}: {len(grid)} bars · up {D['symbols'][sym]['up']:.0%} · {lab} · {time.time() - t1:.0f}s")
    cut = (datetime.now(LON) - timedelta(days=KEEP_DAYS)).date().isoformat()
    O["days"] = sorted((x for x in O["days"] if x["day"] >= cut), key=lambda x: x["day"])
    json.dump(O, open(oracle_path, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"→ {oracle_path}")


def main():
    a = sys.argv[1:]
    mode = a[0] if a else "live"
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    data, livej, sym, orc = opt("--data", "data.json"), opt("--live", "live.json"), opt("--out", "symbols.json"), opt("--oracle", "oracle.json")
    if mode in ("live", "due"):
        d = live(sym, data, livej, orc) if mode == "live" else due(orc)
        print(f"oracle due: {d}")
        if os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write(f"oracle={1 if d else 0}\n")
    elif mode == "oracle":
        oracle(orc, data, livej, opt("--kronos", "/tmp/kronos"))


if __name__ == "__main__":
    main()
