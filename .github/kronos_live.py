#!/usr/bin/env python3
pass
import argparse, html, json, math, os, random, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PATHS, HORIZON, CTX, MIN_CTX = 24, 36, 192, 96
STEP = 300                                                                                         
FRESH = timedelta(minutes=90)                                                                            
GIVE_UP = timedelta(minutes=45)                                     
GROUPS = 16                                                                                                              
KEEP = timedelta(days=150)                                                                           
RW_PATHS, MOM, BASE_AGE, BASE_TRIES = 200, 12, timedelta(days=50), 3                                                   
BER = ZoneInfo("Europe/Berlin")
OV_TS = "https://api.onvista.de/api/v1/instruments/{t}/{e}/times_and_sales"                                                        
UBS_PAGES = 8                                                         
                                                                                                  
UBS = {"^GDAXI": ("INDEX", 20735, 60557091, "UBS"),                                                       
       "ES=F": ("INDEX", 4359526, 126161736, "UBS"),                                                                                  
                                                                                                                         
                                                                                         
       "CL=F": ("COMMODITY", 92945782, 134412504, "L&S"),
       "BZ=F": ("COMMODITY", 88547951, 125750230, "L&S")}
                                                                                                                        
                                                                                                                                                                                                                                            
                                                                                                             
TURBO = {"NQ=F": "NAS100", "YM=F": "US30", "GC=F": "XAUUSD", "SI=F": "XAGUSD", "^FTSE": "UK100", "^STOXX50E": "EUSTX50",
         "^FCHI": "FRA40"}
MODEL, TOKZ = "NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base"

PROXY = {"NAS100": "NQ=F", "US500": "ES=F", "US30": "YM=F", "US2000": "RTY=F",
         "GER40": "^GDAXI", "UK100": "^FTSE", "EUSTX50": "^STOXX50E", "FRA40": "^FCHI", "JPN225": "NIY=F", "HK50": "^HSI",
         "AUS200": "^AXJO", "XAUUSD": "GC=F", "XAGUSD": "SI=F", "XPTUSD": "PL=F", "XPDUSD": "PA=F", "SPOTCRUDE": "CL=F", "SPOTBRENT": "BZ=F", "USOIL": "CL=F",
         "UKOIL": "BZ=F", "NATGAS": "NG=F", "COPPER": "HG=F"}
CCY = {"EUR": "🇪🇺", "USD": "🇺🇸", "GBP": "🇬🇧", "JPY": "🇯🇵", "CHF": "🇨🇭", "AUD": "🇦🇺", "NZD": "🇳🇿", "CAD": "🇨🇦"}
FLAG = {"NAS100": "🇺🇸", "US500": "🇺🇸", "US30": "🇺🇸", "US2000": "🇺🇸", "GER40": "🇩🇪", "UK100": "🇬🇧", "EUSTX50": "🇪🇺",
        "FRA40": "🇫🇷", "JPN225": "🇯🇵", "HK50": "🇭🇰", "AUS200": "🇦🇺", "XAUUSD": "🥇", "XAGUSD": "🥈", "SPOTCRUDE": "🛢️",
        "SPOTBRENT": "🛢️", "USOIL": "🛢️", "UKOIL": "🛢️"}
ICON = {"equinox": "🌗", "climax": "⚡️", "lava": "🌋", "dvi": "📈"}
CRYPTO = re.compile(r"USDT$|USDC$|BUSD$|\.P$|^(BTC|ETH|SOL|XRP|DOGE|BNB|ADA|AVAX|LINK|LTC)USD$")
CX_VENUE = {"BINANCE", "BINANCEUS", "BYBIT", "OKX", "COINBASE", "BITGET", "KRAKEN", "BITSTAMP", "MEXC", "KUCOIN", "CRYPTO", "CRYPTOCAP"}
CX_ICON = {"BTC": "🟠", "ETH": "🔷", "SOL": "🟣"}


def is_crypto(exch, sym):
    pass
    return exch in CX_VENUE or bool(CRYPTO.search(sym))


def cx_base(sym):
    return re.sub(r"(USDT|USDC|BUSD|FDUSD|USD)$", "", re.sub(r"\.P$", "", sym))

                                                                                                     
HEAD = re.compile(r"symbol=([A-Z0-9_]+):([A-Z0-9_.!]+)(?:#(2[6-9]\w*))?\"[^>]*><b>[^<]+</b></a><b> · (\d+)m · ([^·<]+) · (\w+)(?: (v10\.2[6-9]\w*|(?<=badger )v0\.\d+\w*))?</b>")
ENTRY = re.compile(r"^(🟢|🔴) · (LONG|SHORT) ([\d.]+) · SL ([\d.]+) · TP1 ([\d.]+) \(([\d.]+)R\)(?: · TP2 ([\d.]+) \(([\d.]+)R\))?")
RESULT = re.compile(r"^(?:(?:🌗|⚡️?) (?:equinox|climax) · )?(?:✅|🏆|🛑|🏁) · (LONG|SHORT) ([\d.]+) (AF TP1 Hit|AF Target|AF Stopped at|AF Closed|TP1 Hit|TP2 Hit|Stopped at|Runner Closed|Closed)"
                    r"[^(]*\(([+\-−]?[\d.]+)R")


def plain(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h.replace("<br>", "\n")))


def parse(items):
    pass
    ent, res = [], []
    for m in items:
        h = HEAD.search(m["html"])
        if not h:
            continue
        exch, sym, frag, tf, ses, script, ver = h.groups()
        ver = ver or ("v10." + frag if frag else None)
        if not ver:
            continue
        txt = plain(m["html"])
        rd = ""
        for ln in txt.split("\n"):
            ln = ln.strip()
            if ln.startswith("🧭"):
                rd = ln
            e = ENTRY.match(ln)
            if e:
                _, side, px, sl, t1, r1, t2, r2 = e.groups()
                af = "auction·failed" in ln
                ent.append({"id": m["id"], "t": m["t"], "exch": exch, "sym": sym, "tf": int(tf), "ses": ses.strip(),
                            "script": script, "ver": ver, "af": af, "side": side, "px": px, "sl": sl, "tp1": t1,
                            "r1": float(r1), "tp2": t2, "r2": float(r2) if r2 else None})                                   
            r = RESULT.match(ln)
            if r:
                side, px, kind, rr = r.groups()
                res.append({"id": m["id"], "t": m["t"], "sym": sym, "tf": int(tf), "side": side, "px": px, "kind": kind,
                            "r": float(rr.replace("−", "-"))})
    return ent, res


def key(x):
    return f"{x['sym']}|{x['tf']}|{x['side']}|{x['px']}"


def proxy_of(exch, sym):
    if sym in PROXY:
        return PROXY[sym]
    if sym in ("USDX", "DXY") or exch == "CRYPTOCAP":
        return None
    if is_crypto(exch, sym):
        b = cx_base(sym)
        return b + "-USD" if b else None
    if re.fullmatch(r"[A-Z]{6}", sym) and sym[:3] in CCY and sym[3:] in CCY:
        return sym + "=X"
    if exch in ("XETR", "XETRA", "FWB"):
        return sym + ".DE"
    if exch in ("NASDAQ", "NYSE", "AMEX", "BATS"):
        return sym.replace(".", "-")
    return None


def yahoo(tk, rng="5d"):
    pass
    for host in ("query1", "query2"):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(tk)}?interval=5m&range={rng}&includePrePost=false"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) r3m-reef"})
            d = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]
            q = d["indicators"]["quote"][0]
            rows = [(t, o, h, l, c, v or 0) for t, o, h, l, c, v in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"])
                    if None not in (o, h, l, c)]
            return rows, d["meta"].get("exchangeTimezoneName") or "UTC"
        except Exception as ex:
            err = ex
    print(f"  {tk}: no bars ({err})")
    return None, None



def ov_ticks(typ, ent, nota, since):
    pass
    out, t0 = [], since
    for _ in range(UBS_PAGES):
        q = datetime.fromtimestamp(t0, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{OV_TS.format(t=typ, e=ent)}?idNotation={nota}&startDate={q}"
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20))
        except Exception as ex:
            print(f"  onvista {nota}: no ticks ({ex})")
            return out or None
        ts, ps = d.get("datetimePrice") or [], d.get("price") or []
        new = sorted((int(t), float(p)) for t, p in zip(ts, ps) if p is not None and int(t) >= t0)
        out += [x for x in new if not out or x[0] > out[-1][0]]
        if len(ts) < 10000 or not new:
            break
        t0 = new[-1][0] + 1
    return out


def turbo_ticks(sym, since, px):
    pass
    ul = ko_ul(sym)
    rows = ko_query(ul, True, px * 0.55, px * 0.75, every=True) if ul else []
    rows = [r for r in rows if (r.get("quote") or {}).get("bid")]
    rows.sort(key=lambda r: (str(r["issuer"]["id"]) == "54283", r["quote"].get("datetimeBid", "")), reverse=True)
    fxc = None
    for r in rows[:3]:
        ev, ko, rt, qu = r["instrument"]["entityValue"], float(r["knockOutAbs"]), float(r["coverRatio"]), bool(r.get("quanto"))
        wkn, iss = r["instrument"].get("wkn"), r["issuer"].get("name")
        nota = ((r["quote"].get("market") or {}).get("idNotation"))
        if not nota:
            try:
                sn = json.load(urllib.request.urlopen(urllib.request.Request(
                    f"https://api.onvista.de/api/v1/instruments/DERIVATIVE/{ev}/snapshot", headers={"User-Agent": UA}), timeout=20))
                nota = sn["quote"]["market"]["idNotation"]
            except Exception as ex:
                print(f"  turbo {wkn}: no snapshot ({ex})")
                continue
        if not qu:
            fxc = fxc or fx_eur(ul[2])
        fx = 1.0 if qu else fxc
        if not fx:
            return None
        tk = ov_ticks("DERIVATIVE", ev, nota, since)
        print(f"  turbo {wkn} {iss} (KO {ko:,.6g}, ratio {rt:g}) for {ul[3]}: {len(tk or [])} ticks")
        if tk:
            return [(t, ko + p * fx / rt) for t, p in tk]
    return None


def live_fill(rows, tk, sym):
    pass
    last = rows[-2][0] if len(rows) > 1 else rows[-1][0]                                     
    if tk in UBS:
        ticks, src = ov_ticks(UBS[tk][0], UBS[tk][1], UBS[tk][2], last), UBS[tk][3]
    else:
        ticks, src = turbo_ticks(TURBO[tk], last, rows[-1][4]), "turbo"
    if not ticks:
        return rows, ""
    print(f"  {src}: {len(ticks)} ticks, the last {time.time() - ticks[-1][0]:.0f}s old · Yahoo's last bar {(time.time() - rows[-1][0]) / 60:.0f} min old")
    bars = {}
    for t, p in ticks:
        b = t // STEP * STEP
        o, h, l, c, n = bars.get(b, (p, p, p, p, 0))
        bars[b] = (o, max(h, p), min(l, p), p, n + 1)
    k = 1.0
    if last in bars:
        y = next(r for r in rows if r[0] == last)
        k = y[4] / bars[last][3]
    vol = sorted(r[5] for r in rows[-48:])[len(rows[-48:]) // 2]
    keep = [r for r in rows if r[0] <= last]
    add = [(b, o * k, h * k, l * k, c * k, vol) for b, (o, h, l, c, n) in sorted(bars.items()) if b > last]
    return keep + add, (src if add else "")


def bars_for(e, now):
    pass
    tk = proxy_of(e["exch"], e["sym"])
    if not tk:
        return None, "no proxy for this symbol"
    rows, tz = yahoo(tk)
    if not rows:
        return None, "wait"
    if tk in UBS or tk in TURBO:
        rows, src = live_fill(rows, tk, e["sym"])
        if src:
            tk += " + " + src
    return ctx_of(rows, tz, tk, e)


def ctx_of(rows, tz, tk, e):
    pass
    t = int(datetime.fromisoformat(e["t"]).timestamp())
    close_t = t // STEP * STEP                                                            
    ent_start = close_t - STEP
    if not any(r[0] >= close_t for r in rows):                                                                          
        return None, "wait"
    ctx = [r for r in rows if r[0] <= ent_start]
    if not ctx or ctx[-1][0] < ent_start - 3 * STEP:
        return None, f"{tk} had no bars at the entry (market closed)"
    ctx = ctx[-CTX:]
    if len(ctx) < MIN_CTX:
        return None, f"{tk}: only {len(ctx)} bars before the entry"
    return {"tk": tk, "tz": tz, "rows": ctx}, ""


def walk(paths_ohlc, e, ref):
    pass
    long = e["side"] == "LONG"
    k = ref / float(e["px"])
    sl, t1 = float(e["sl"]) * k, float(e["tp1"]) * k
    t2 = float(e["tp2"]) * k if e["tp2"] else None
    n1 = ns = nn = n2 = 0
    ends = []
    for p in paths_ohlc:
        first = None
        got2 = False
        for (o, h, l, c) in p:
            if t2 is not None and first in (None, "tp1") and (h >= t2 if long else l <= t2):
                got2 = True
            if first is None and (h >= t1 if long else l <= t1):
                first = "tp1"
            if (c <= sl if long else c >= sl):
                if first is None:
                    first = "stop"
                break
        n1 += first == "tp1"
        ns += first == "stop"
        nn += first is None
        n2 += got2
        ends.append(p[-1][3])
    ends.sort()
    med = ends[len(ends) // 2] / k
    edge = (n1 * e["r1"] - ns) / len(paths_ohlc)
    return {"n": len(paths_ohlc), "tp1": n1, "stop": ns, "none": nn, "tp2": n2 if t2 is not None else None,
            "med": float(med), "edge": round(float(edge), 2)}


def baselines(rows, e, seed):
    pass
    c = [r[4] for r in rows]
    d = 1 if e["side"] == "LONG" else -1
    tail = rows[-48:]
    rg = sum(r[2] - r[3] for r in tail) / len(tail)
    mom = (c[-1] - c[-1 - MOM]) * d / rg if rg > 0 and len(c) > MOM else 0.0
    steps = [(r[1] / p, r[2] / p, r[3] / p, r[4] / p) for p, r in zip(c[:-1], rows[1:]) if p > 0]
    rnd = random.Random(seed)
    paths = []
    for _ in range(RW_PATHS):
        px, p = c[-1], []
        for _ in range(HORIZON):
            o, h, l, cc = rnd.choice(steps)
            p.append((px * o, px * h, px * l, px * cc))
            px *= cc
        paths.append(p)
    w = walk(paths, e, c[-1])
    return {"mom": round(mom, 2), "rw": w["edge"], "rwTp1": w["tp1"], "rwStop": w["stop"], "rwN": w["n"]}


def backfill(state, now):
    pass
    cache, n = {}, 0
    for c in state["checks"]:
        if c["status"] != "sent" or "base" in c or c.get("baseTry", 0) >= BASE_TRIES or now - datetime.fromisoformat(c["t"]) > BASE_AGE:
            continue
        tk = (c.get("k") or {}).get("tk") or proxy_of(c["exch"], c["sym"])
        if tk not in cache:
            cache[tk] = yahoo(tk, "1mo")
        rows, tz = cache[tk]
        b, why = ctx_of(rows, tz, tk, c) if rows else (None, "no bars")
        if b is None:
            c["baseTry"] = c.get("baseTry", 0) + 1
            print(f"  base {c['sym']} {c['px']}: {why}")
            continue
        c["base"] = baselines(b["rows"], c, c["id"])
        c.pop("baseTry", None)
        n += 1
    if n:
        print(f"controls back-filled for {n} checks")


def dec(px):
    return len(px.split(".")[1]) if "." in px else 0


def fmt(x, d):
    return f"{x:,.{d}f}"


def flag(sym):
    if sym in FLAG:
        return FLAG[sym] + " "
    if CX_ICON.get(cx_base(sym)) and CRYPTO.search(sym):
        return CX_ICON[cx_base(sym)] + " "
    if re.fullmatch(r"[A-Z]{6}", sym) and sym[:3] in CCY and sym[3:] in CCY:
        return CCY[sym[:3]] + CCY[sym[3:]] + " "
    return ""


DAX = {"GER40", "DE40", "GER30", "DE30", "DAX", "GDAXI", "FDAX1!", "FDXM1!"}
KO_URL = "https://www.onvista.de/derivate/Knock-Outs/Knock-Outs-auf-DAX"
                                                                                                                           
                                                                                                                     
KO_UL = {**{s: ("INDEX", "20735", "EUR", "DAX") for s in DAX},
         **{s: ("INDEX", "325104", "USD", "Nasdaq 100") for s in ("NAS100", "US100", "USTEC", "NDX", "NQ1!", "MNQ1!")},
         **{s: ("INDEX", "4359526", "USD", "S&P 500") for s in ("US500", "SPX500", "SPX", "ES1!", "MES1!")},
         **{s: ("INDEX", "324977", "USD", "Dow Jones") for s in ("US30", "DJ30", "YM1!")},
         **{s: ("INDEX", "193736", "EUR", "Euro Stoxx 50") for s in ("EUSTX50", "EU50", "STOXX50", "FESX1!")},
         **{s: ("INDEX", "1918069", "GBP", "FTSE 100") for s in ("UK100", "FTSE100")},
         **{s: ("INDEX", "324965", "EUR", "CAC 40") for s in ("FRA40", "CAC40")},
         **{s: ("INDEX", "60972397", "JPY", "Nikkei") for s in ("JPN225", "JP225")},
         **{s: ("PRECIOUS_METAL", "1326189", "USD", "gold") for s in ("XAUUSD", "GOLD", "GC1!")},
         **{s: ("PRECIOUS_METAL", "1288094", "USD", "silver") for s in ("XAGUSD", "SILVER", "SI1!")}}
KO_FX = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURJPY", "GBPJPY", "AUDUSD", "NZDUSD", "USDCAD", "EURGBP", "EURCHF", "AUDJPY"}


def ko_ul(sym):
    pass
    if sym in KO_UL:
        return KO_UL[sym]
    if sym in KO_FX:
        return ("CURRENCY", sym, sym[3:], sym[:3] + "/" + sym[3:])
    return None


                                                                                                                            
                                                                                                                          
                                                                                                                         
                                                                                                                             
                                                                                                              
OV_API = ("https://api.onvista.de/api/v1/derivatives/finder/configuration_query?application=WEBSITE&device=DESKTOP"
          "&entityTypeUnderlying={t}&entityValueUnderlying={v}&page=0&perPage=100&queryParameters=")
KO_ISS = {"54283": "Morgan Stanley", "53159": "Société Générale", "53881": "BNP Paribas"}
KO_MIN_EUR = 1000                                                                   
KO_SPR = 0.0002                                                                                                            
KO_BUF = 0.001                                                                                    
KO_WIN = (0.0025, 0.01)                                                                                              
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def ko_query(ul, long, lo, hi, every=False):
    pass
    q = (f"entitySubType=KNOCKOUT_CERTIFICATE&idExerciseRight={2 if long else 1}&knockOutAbsRange={lo:.6g};{hi:.6g}"
         + ("" if every else "".join(f"&idIssuer={i}" for i in KO_ISS)) + "&feature=STANDARD&")
    try:
        req = urllib.request.Request(OV_API.format(t=ul[0], v=ul[1]) + urllib.parse.quote(q, safe=""),
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=20)).get("list") or []
    except Exception as ex:
        print(f"  onvista: {ex}")
        return []


def fx_eur(cur):
    pass
    if cur == "EUR":
        return 1.0
    rows, _ = yahoo(f"EUR{cur}=X", "1d")
    return rows[-1][4] if rows else None


def ko_pick(rows, long, bar, risk, fx, px):
    pass
    now = datetime.now(timezone.utc)
    best, why = {}, {"bid": 0, "side": 0, "spread": 0, "old": 0}
    cap = max(KO_SPR * px, 0.15 * risk)                                                                                              
    for r in rows:
        try:
            ko, rt, bid = float(r["knockOutAbs"]), float(r["coverRatio"]), float(r["quote"]["bid"])
            iss = str(r["issuer"]["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if iss not in KO_ISS or rt <= 0 or bid < 0.10:
            why["bid"] += 1
            continue
        if ko > bar if long else ko < bar:
            why["side"] += 1
            continue
        spr = r.get("spread")
        ask = bid + float(spr) if spr is not None else None
        if ask is not None and (ask - bid) * (1.0 if r.get("quanto") else fx) / rt > cap:
            why["spread"] += 1
            continue
        try:
            if now - datetime.fromisoformat(r["quote"]["datetimeBid"]) > timedelta(minutes=20):
                why["old"] += 1
                continue
        except (KeyError, TypeError, ValueError):
            why["old"] += 1
            continue
        p = {"wkn": r["instrument"]["wkn"], "isin": r["instrument"].get("isin", ""), "iss": KO_ISS[iss], "ko": ko, "ratio": rt,
             "bid": bid, "ask": ask, "lev": float(r.get("gearingAsk") or 0), "x": bool(re.search(r"\bX-|XDAX", r.get("shortName", ""))),
             "q": bool(r.get("quanto")), "tq": r["quote"].get("datetimeBid", "")}
        rank = (abs(bar - ko), ask is None, (ask - bid) / ask if ask else 1, p["x"])
        if iss not in best or rank < best[iss][0]:
            best[iss] = (rank, p)
    out = [p for _, p in sorted(best.values(), key=lambda x: x[0])]
    print(f"  onvista: {len(rows)} certificates, {len(out)} picked · dropped {why}")
    for p in out:
        a = p["ask"] or p["bid"]
        p["n"] = math.ceil(KO_MIN_EUR / a)
        p["eurR"] = round(p["n"] * p["ratio"] * risk / (1.0 if p["q"] else fx))
    return out


def ko_find(e, k=None):
    pass
    ul = ko_ul(e["sym"])
    if not ul:
        return "", []
    px, sl = float(e["px"]), float(e["sl"])
    cash = bool(k and k.get("ref") and (k.get("tk", "").startswith("^") or k.get("tk", "").endswith("=X")))
    m = k["ref"] / px if cash else 1.0
    ix, sx = px * m, sl * m
    risk = abs(ix - sx)
    buf = max(risk, KO_BUF * ix)
    long = e["side"] == "LONG"
    st = 10 ** math.floor(math.log10(ix * 0.0004))                                                                       
    bar = math.floor((sx - buf) / st) * st if long else math.ceil((sx + buf) / st) * st
    d = max(0, -int(math.floor(math.log10(st))))
    f = lambda x: fmt(x, d)
    head = (f"🎫 KO {'long' if long else 'short'} · {ul[3]} · barrier {'≤' if long else '≥'} {f(bar)} (stop {f(sx)} "
            f"{'−' if long else '+'} {f(buf)})" + ("" if cash else " · CFD levels"))
    nb = datetime.now(timezone.utc).astimezone(BER)
    live = nb.weekday() < 5 and 8 <= nb.hour < 22
    fx = fx_eur(ul[2]) if live else None
    if ul[0] == "CURRENCY" and ul[2] == "USD" and e["sym"].startswith("EUR"):
        fx = ix                                                                           
    picks = []
    if fx:
        for w in KO_WIN:
            lo, hi = (bar - w * ix, bar) if long else (bar, bar + w * ix)
            picks = ko_pick(ko_query(ul, long, lo, hi), long, bar, risk, fx, ix)
            if picks:
                break
    if not picks:                                                                                                          
        if e["sym"] not in DAX:
            return "", []
        lev = ix / abs(ix - bar) if ix != bar else 0
        return (head + f" · leverage ≈ {lev:,.0f} · 1R ≈ {risk * 0.01:.2f} € a certificate at ratio 0.01 · "
                f"<a href=\"{KO_URL}\">onvista</a>"), []
                                                                                                     
    lines = [head + f" · comdirect 0 € from {KO_MIN_EUR:,} €" + ("" if ul[2] == "EUR" else f" · € at EUR{ul[2]} {fx:,.4g}")]
    for p in picks:
        a = p["ask"]
                                                                                                                              
                                                                                                                                         
        q = 1.0 if p["q"] else fx
        ixq = p["ko"] + p["bid"] * q / p["ratio"] if long else p["ko"] - p["bid"] * q / p["ratio"]
        lev = ixq * p["ratio"] / ((a or p["bid"]) * q)
        spr = f" · spread {f((a - p['bid']) * q / p['ratio'])} ({(a - p['bid']) * q / p['ratio'] / risk:.2f}R)" if a else ""
        p["lev"] = round(lev, 1)                                                                                                            
        p["spr"] = round((a - p["bid"]) * q / p["ratio"], 4) if a else None
        p["sprR"] = round((a - p["bid"]) * q / p["ratio"] / risk, 3) if a else None
        tq = ""
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(p["tq"])
            tq = f" · quote {datetime.fromisoformat(p['tq']).astimezone(BER):%H:%M}" if age > timedelta(minutes=15) else ""
        except ValueError:
            pass
        url = f"https://www.comdirect.de/inf/zertifikate/{p['isin']}" if p["isin"] else KO_URL
        lines.append(f"\n• <a href=\"{url}\">{p['wkn']}</a> {html.escape(p['iss'])}{' · XDAX' if p['x'] else ''}{' · quanto' if p['q'] else ''} · KO {f(p['ko'])} · "
                     + (f"ask {a:,.2f} €" if a else f"bid {p['bid']:,.2f} €") + f" · leverage {lev:,.0f}{spr}{tq} · "
                     f"{KO_MIN_EUR:,} € = {p['n']:,} pcs · 1R ≈ {p['eurR']:,} €")
    return "\n".join(lines), picks


def ko_line(e, k=None):
    return ko_find(e, k)[0]


def ko_keep(picks):
    pass
    return [{x: (round(p[x], 4) if isinstance(p[x], float) else p[x]) for x in ("wkn", "iss", "ko", "ratio", "bid", "ask", "n", "eurR", "lev", "spr", "sprR") if x in p} for p in picks]


def message(e, k, ko=""):
    d = dec(e["px"])
    arrow = "▲" if e["side"] == "LONG" else "▼"
    eng = ICON.get(e["script"], "") + " " + e["script"] + (" AF" if e["af"] else "")
    tm = datetime.fromisoformat(e["t"]).astimezone(BER).strftime("%H:%M")
    hrs = HORIZON * STEP // 3600
                                                                               
    lines = [f"🔮 <b>Kronos · {flag(e['sym'])}{html.escape(e['sym'])} · {eng.strip()} {arrow} {tm}</b>", "",
             f"🎯 TP1 first {k['tp1']} · 🛑 stop first {k['stop']} · ⏸ neither {k['none']} · of {k['n']} paths, next {hrs}h"]
    mid = f"median in {hrs}h {fmt(k['med'], d)} " + ("▲" if k["med"] > float(e["px"]) else "▼")
    if k["tp2"] is not None:
        lines[-1] += f" · 🏆 TP2 before the stop {k['tp2']}"
    lines[-1] += f" · 📍 {mid}"
    if k["edge"] > 0:
        lines[-1] += f" · ✓ edge {k['edge']:+.2f}R · leans with the trade"
    elif k["edge"] < 0:
        lines[-1] += f" · ✗ edge {k['edge']:+.2f}R · leans against the trade"
    else:
        lines[-1] += " · ➖ edge 0R · no lean, the paths stay between the stop and TP1"
    if ko:
        lines += ["", ko]
    lines += ["", f"<i>read on {html.escape(k['tk'])} · Kronos-small · a test, not advice</i>"]
    return "\n".join(lines)


def send(text, reply_to, dry):
    if dry:
        print("DRY ↓\n" + text)
        return None
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not (tok and chat):
        print("TG_BOT_TOKEN / TG_CHAT_ID missing, not sent")
        return None
    body = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_notification": True, "disable_web_page_preview": True,
            "reply_parameters": {"message_id": int(reply_to), "allow_sending_without_reply": True}}
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=20))
        return r.get("result", {}).get("message_id")
    except Exception as ex:
        print("send failed:", str(ex).replace(tok, "***"))
        return None


def load(p):
    try:
        d = json.load(open(p, encoding="utf-8"))
        for c in d.get("checks", []):
            c.pop("crypto", None)                                                                       
            c.pop("read", None)                                                                              
        return d
    except (FileNotFoundError, ValueError):
        return {"checks": []}


def todo(state, ent, now):
    seen = {c["id"] for c in state["checks"]}
    new = [e for e in ent if e["id"] not in seen and now - datetime.fromisoformat(e["t"]) <= FRESH]
    wait = [c for c in state["checks"] if c["status"] == "wait"]
    return new, wait


def score(state, res):
    pass
    by = {}
    for r in res:
        by.setdefault(key(r), []).append(r)
    ch = False
    for c in state["checks"]:
        if c.get("out") or c["status"] != "sent":
            continue
        rs = [r for r in by.get(key(c), []) if r["t"] > c["t"]]
        if not rs:
            continue
        r = rs[0]
        if r["kind"] in ("TP1 Hit", "TP2 Hit", "Runner Closed", "AF TP1 Hit", "AF Target"):
            c["out"], c["rOut"] = "tp1", c["r1"]
        elif r["kind"] in ("Stopped at", "AF Stopped at"):
            c["out"], c["rOut"] = "stop", r["r"]
        else:
            c["out"], c["rOut"] = "closed", r["r"]
        c["tOut"] = r["t"]
        ch = True
    return ch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "run", "merge"])
    ap.add_argument("live")
    ap.add_argument("state")
    ap.add_argument("--kronos", default="/tmp/kronos")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--ids", default="", help="dry test: force these message ids (comma list), whatever their age")
    ap.add_argument("--only", default="", help="run: just these message ids (one matrix job's group), no scoring, no state write")
    ap.add_argument("--part", default="", help="run --only: where the job writes its checks (merged by the merge step)")
    ap.add_argument("--parts", default="", help="merge: the folder with the jobs' part files")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    items = load(a.live).get("items", [])
    ent, res = parse(items)
    state = load(a.state)
    before = json.dumps(state["checks"])
                                                                                                                         
                                                                                                 
    rp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kronos_restore.json")
    if os.path.exists(rp):
        have = {c["id"] for c in state["checks"]}
        back = [c for c in load(rp)["checks"] if c["id"] not in have and now - datetime.fromisoformat(c["t"]) <= KEEP]
        if back:
            state["checks"] += back
            print(f"restored {len(back)} checks")
    force = {int(x) for x in a.ids.split(",") if x.strip()}
    if force:
        state = {"checks": [c for c in state["checks"] if c["id"] not in force]}
        new, wait = [e for e in ent if e["id"] in force], []
    else:
        new, wait = todo(state, ent, now)
    jobs = new + [next(e for e in ent if e["id"] == c["id"]) for c in wait if any(e["id"] == c["id"] for e in ent)]
    if a.mode == "plan":                                                                                                                      
        ids = [e["id"] for e in jobs]
        g = [[] for _ in range(min(len(ids), GROUPS))]
        for i, x in enumerate(ids):
            g[i % len(g)].append(str(x))
        need = int(bool(ids))
        print(f"new {len(new)} · waiting {len(wait)} · {len(g)} jobs · need_model={need}")
        if os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write(f"need_model={need}\ngroups={json.dumps([','.join(x) for x in g])}\n")
        return
    if a.mode == "merge":                                                                                                            
        for p in sorted(os.listdir(a.parts)) if a.parts and os.path.isdir(a.parts) else []:
            if not p.endswith(".json"):
                continue
            for c in load(os.path.join(a.parts, p)).get("checks", []):
                state["checks"] = [x for x in state["checks"] if x["id"] != c["id"]] + [c]
                print(f"merged {c['sym']} {c['side']} {c['px']}: {c['status']}")
        jobs = []
    if a.only:
        only = {int(x) for x in a.only.split(",") if x.strip()}
        jobs = [e for e in jobs if e["id"] in only]
        mine = {e["id"] for e in jobs}
    pred = None
    ready = []
    for e in jobs:
        b, why = bars_for(e, now)
        old = next((c for c in state["checks"] if c["id"] == e["id"]), None)
        if b is None:
            if why == "wait" and now - datetime.fromisoformat(e["t"]) < GIVE_UP:
                if not old:
                    state["checks"].append({**e, "status": "wait"})
                print(f"{e['sym']} {e['side']} {e['px']}: waiting for the proxy bars")
            else:
                why = why if why != "wait" else "no proxy bars within 45 min"
                if old:
                    state["checks"].remove(old)
                ko, picks = ko_find(e) if e["script"] != "badger" else ("", [])
                mid = None
                if ko:                                                                                             
                    arrow = "▲" if e["side"] == "LONG" else "▼"
                    mid = send(f"🎫 <b>KO · {flag(e['sym'])}{html.escape(e['sym'])} · {e['script']}{' AF' if e['af'] else ''} {arrow}</b>\n\n{ko}\n\n"
                               f"<i>no Kronos read: {html.escape(why)}</i>", e["id"], a.dry)
                state["checks"].append({**e, "status": "skip", "why": why, "msg": mid, **({"ko": ko_keep(picks)} if picks else {})})
                print(f"{e['sym']} {e['side']} {e['px']}: skipped, {why}")
            continue
        if old:
            state["checks"].remove(old)
        ready.append((e, b))
    if ready:
        sys.path.insert(0, a.kronos)
        import pandas as pd
        from model import Kronos, KronosTokenizer, KronosPredictor
        pred = KronosPredictor(Kronos.from_pretrained(MODEL), KronosTokenizer.from_pretrained(TOKZ), device="cpu", max_context=512)
        for e, b in ready:
            t1 = time.time()
            tz = ZoneInfo(b["tz"])
            rows = b["rows"]
            df = pd.DataFrame({"open": [r[1] for r in rows], "high": [r[2] for r in rows], "low": [r[3] for r in rows],
                               "close": [r[4] for r in rows], "volume": [float(r[5]) for r in rows]}, dtype="float64")
            xt = pd.Series([datetime.fromtimestamp(r[0], tz).replace(tzinfo=None) for r in rows])
            yt = pd.Series([datetime.fromtimestamp(rows[-1][0] + STEP * (i + 1), tz).replace(tzinfo=None) for i in range(HORIZON)])
            out = pred.predict_batch([df] * PATHS, [xt] * PATHS, [yt] * PATHS, pred_len=HORIZON, T=1.0, top_p=0.9,
                                     sample_count=1, verbose=False)
            paths = [[tuple(map(float, b)) for b in zip(o["open"].values, o["high"].values, o["low"].values, o["close"].values)] for o in out]
            k = walk(paths, e, rows[-1][4])
            k["tk"] = b["tk"]
            k["ref"] = rows[-1][4]
            ko, picks = ko_find(e, k) if e["script"] != "badger" else ("", [])                                                           
            mid = send(message(e, k, ko), e["id"], a.dry)
            lag = int(time.time() - datetime.fromisoformat(e["t"]).timestamp())                                        
            state["checks"].append({**e, "status": "sent", "lag": lag, "k": {x: (round(v, 6) if isinstance(v, float) else v) for x, v in k.items()},
                                    "base": baselines(rows, e, e["id"]), "msg": mid, "made": now.isoformat(timespec="seconds"),
                                    **({"ko": ko_keep(picks)} if picks else {})})
            print(f"{e['sym']} {e['side']} {e['px']}: TP1 {k['tp1']} · stop {k['stop']} · edge {k['edge']:+.2f}R · {b['tk']} · forecast {time.time() - t1:.0f}s · alert → reply {lag}s")
    if a.only:
        if a.part:
            json.dump({"checks": [c for c in state["checks"] if c["id"] in mine]}, open(a.part, "w", encoding="utf-8"), ensure_ascii=False)
        return
    score(state, res)
    if not force:
        backfill(state, now)
    state["checks"] = sorted([c for c in state["checks"] if now - datetime.fromisoformat(c["t"]) <= KEEP], key=lambda c: c["t"])
    if json.dumps(state["checks"]) == before:
        print("nothing changed")
        return
    state["updated"] = now.isoformat(timespec="seconds")
    if not a.dry:
        json.dump(state, open(a.state, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
