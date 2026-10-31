#!/usr/bin/env python3
"""🔮 Kronos signal check (2026-10-31, the user: "fast live over proxy prices")

Runs in the public repo spec1re/r3m (.github/workflows/kronos-live.yml, after every "Live feed" run), free minutes there.
Source of truth: r3m-digest/site-ci/ (build_site.py copies this file into the site's .github/, the workflow file is
pushed by hand: site-ci/kronos-live.yml is the reference copy).

For every new r3m· entry and AF entry in live.json (the chart alerts, v10.26+): the 5m bars of a free proxy feed (Yahoo:
the index future, the cash index, the FX pair, the stock) up to the entry bar · Kronos samples PATHS continuations of the
next HORIZON bars · each path is walked like the trade: TP1 by touch, the stop on a close beyond it (as r3m·), the TP /
SL levels mapped onto the proxy as ratios of the entry (a future's basis drops out) · counts TP1 first / stop first /
neither / TP2 before the stop · edge = (TP1 first × TP1's R − stop first) / paths · a silent reply under the alert
(Telegram, disable_notification) · the trade's first word later (TP1 Hit / Stopped / Closed before TP1) scores it.

    python3 kronos_live.py plan  live.json kronos-live.json   → prints need_model=1 when a forecast is due ($GITHUB_OUTPUT)
    python3 kronos_live.py run   live.json kronos-live.json [--kronos /tmp/kronos] [--dry]
Secrets: TG_BOT_TOKEN, TG_CHAT_ID (the bot that sends the alerts).
"""
import argparse, html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PATHS, HORIZON, CTX, MIN_CTX = 24, 36, 192, 96
STEP = 300                          # 5m bars (r3m· alerts on 5m since 2026-10-27; 3m reads 5m too)
FRESH = timedelta(minutes=90)       # older alerts are not picked up (a restart does not flood the group)
GIVE_UP = timedelta(minutes=45)     # no proxy bar by then → skipped
KEEP = timedelta(days=21)
BER = ZoneInfo("Europe/Berlin")
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
CRYPTO = re.compile(r"BTC|ETH|SOL|XRP|DOGE|TOTAL|USDT$|USDC$|\.P$")

HEAD = re.compile(r"symbol=([A-Z0-9_]+):([A-Z0-9_.!]+)\"[^>]*><b>[^<]+</b></a><b> · (\d+)m · ([^·<]+) · (\w+) (v10\.2[6-9]\w*)")
ENTRY = re.compile(r"^(🟢|🔴) · (LONG|SHORT) ([\d.]+) · SL ([\d.]+) · TP1 ([\d.]+) \(([\d.]+)R\)(?: · TP2 ([\d.]+) \(([\d.]+)R\))?")
RESULT = re.compile(r"^(?:✅|🏆|🛑|🏁) · (LONG|SHORT) ([\d.]+) (AF TP1 Hit|AF Target|AF Stopped at|AF Closed|TP1 Hit|TP2 Hit|Stopped at|Runner Closed|Closed)"
                    r"[^(]*\(([+\-−]?[\d.]+)R")


def plain(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h.replace("<br>", "\n")))


def parse(items):
    """entries and results of the r3m· chart alerts in live.json"""
    ent, res = [], []
    for m in items:
        h = HEAD.search(m["html"])
        if not h:
            continue
        exch, sym, tf, ses, script, ver = h.groups()
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
                            "r1": float(r1), "tp2": t2, "r2": float(r2) if r2 else None, "read": rd[:160]})
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
    if CRYPTO.search(sym) or sym in ("USDX", "DXY"):
        return None
    if re.fullmatch(r"[A-Z]{6}", sym) and sym[:3] in CCY and sym[3:] in CCY:
        return sym + "=X"
    if exch in ("XETR", "XETRA", "FWB"):
        return sym + ".DE"
    if exch in ("NASDAQ", "NYSE", "AMEX", "BATS"):
        return sym.replace(".", "-")
    return None


def yahoo(tk):
    """5m bars of the last 5 days · [(t, o, h, l, c, v)] sorted, the forming bar included (the caller decides)"""
    for host in ("query1", "query2"):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(tk)}?interval=5m&range=5d&includePrePost=false"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) r3m-arena"})
            d = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]
            q = d["indicators"]["quote"][0]
            rows = [(t, o, h, l, c, v or 0) for t, o, h, l, c, v in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"])
                    if None not in (o, h, l, c)]
            return rows, d["meta"].get("exchangeTimezoneName") or "UTC"
        except Exception as ex:
            err = ex
    print(f"  {tk}: no bars ({err})")
    return None, None



def bars_for(e, now):
    """the proxy context up to the entry bar, or (None, why) · why 'wait' = try again later"""
    tk = proxy_of(e["exch"], e["sym"])
    if not tk:
        return None, "no proxy for this symbol"
    rows, tz = yahoo(tk)
    if not rows:
        return None, "wait"
    t = int(datetime.fromisoformat(e["t"]).timestamp())
    close_t = t // STEP * STEP                  # the alert fires on the entry bar's close
    ent_start = close_t - STEP
    if not any(r[0] >= close_t for r in rows):  # the entry bar is complete only once a later bar exists (delayed feeds)
        return None, "wait"
    ctx = [r for r in rows if r[0] <= ent_start]
    if not ctx or ctx[-1][0] < ent_start - 3 * STEP:
        return None, f"{tk} had no bars at the entry (market closed)"
    ctx = ctx[-CTX:]
    if len(ctx) < MIN_CTX:
        return None, f"{tk}: only {len(ctx)} bars before the entry"
    return {"tk": tk, "tz": tz, "rows": ctx}, ""


def walk(paths_ohlc, e, ref):
    """count the paths like r3m· walks the trade: TP by touch, the stop on a close beyond it"""
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
            "med": med, "edge": round(edge, 2)}


def dec(px):
    return len(px.split(".")[1]) if "." in px else 0


def fmt(x, d):
    return f"{x:,.{d}f}"


def flag(sym):
    if sym in FLAG:
        return FLAG[sym] + " "
    if re.fullmatch(r"[A-Z]{6}", sym) and sym[:3] in CCY and sym[3:] in CCY:
        return CCY[sym[:3]] + CCY[sym[3:]] + " "
    return ""


def message(e, k):
    d = dec(e["px"])
    arrow = "▲" if e["side"] == "LONG" else "▼"
    eng = ICON.get(e["script"], "") + " " + e["script"] + (" AF" if e["af"] else "")
    tm = datetime.fromisoformat(e["t"]).astimezone(BER).strftime("%H:%M")
    hrs = HORIZON * STEP // 3600
    lines = [f"🔮 <b>Kronos · {flag(e['sym'])}{html.escape(e['sym'])} · {eng.strip()} {arrow} {tm}</b>",
             f"🎯 TP1 first {k['tp1']} · 🛑 stop first {k['stop']} · ⏸ neither {k['none']} · of {k['n']} paths, next {hrs}h"]
    mid = f"median in {hrs}h {fmt(k['med'], d)} " + ("▲" if k["med"] > float(e["px"]) else "▼")
    lines.append((f"🏆 TP2 before the stop {k['tp2']} · " if k["tp2"] is not None else "") + mid)
    v = "✓" if k["edge"] > 0 else "✗"
    lines.append(f"{v} edge {k['edge']:+.2f}R · " + ("leans with the trade" if k["edge"] > 0 else "leans against the trade"))
    lines.append(f"<i>read on {html.escape(k['tk'])} · Kronos-small · a test, not advice</i>")
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
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"checks": []}


def todo(state, ent, now):
    seen = {c["id"] for c in state["checks"]}
    new = [e for e in ent if e["id"] not in seen and now - datetime.fromisoformat(e["t"]) <= FRESH and not CRYPTO.search(e["sym"])]
    wait = [c for c in state["checks"] if c["status"] == "wait"]
    return new, wait


def score(state, res):
    """the trade's first word: TP1 (TP1 Hit · TP2 Hit · Runner Closed · AF TP1 Hit · AF Target · ½ at TP1) · stop · closed before TP1"""
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
    ap.add_argument("mode", choices=["plan", "run"])
    ap.add_argument("live")
    ap.add_argument("state")
    ap.add_argument("--kronos", default="/tmp/kronos")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--ids", default="", help="dry test: force these message ids (comma list), whatever their age")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    items = load(a.live).get("items", [])
    ent, res = parse(items)
    state = load(a.state)
    before = json.dumps(state["checks"])
    force = {int(x) for x in a.ids.split(",") if x.strip()}
    if force:
        state = {"checks": [c for c in state["checks"] if c["id"] not in force]}
        new, wait = [e for e in ent if e["id"] in force], []
    else:
        new, wait = todo(state, ent, now)
    if a.mode == "plan":
        need = int(bool(new or wait))
        print(f"new {len(new)} · waiting {len(wait)} · need_model={need}")
        if os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write(f"need_model={need}\n")
        return
    jobs = new + [next(e for e in ent if e["id"] == c["id"]) for c in wait if any(e["id"] == c["id"] for e in ent)]
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
                state["checks"].append({**e, "status": "skip", "why": why})
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
            paths = [list(zip(o["open"].values, o["high"].values, o["low"].values, o["close"].values)) for o in out]
            k = walk(paths, e, rows[-1][4])
            k["tk"] = b["tk"]
            mid = send(message(e, k), e["id"], a.dry)
            state["checks"].append({**e, "status": "sent", "k": {x: (round(v, 6) if isinstance(v, float) else v) for x, v in k.items()},
                                    "msg": mid, "made": now.isoformat(timespec="seconds")})
            print(f"{e['sym']} {e['side']} {e['px']}: TP1 {k['tp1']} · stop {k['stop']} · edge {k['edge']:+.2f}R · {time.time() - t1:.0f}s")
    score(state, res)
    state["checks"] = sorted([c for c in state["checks"] if now - datetime.fromisoformat(c["t"]) <= KEEP], key=lambda c: c["t"])
    if json.dumps(state["checks"]) == before:
        print("nothing changed")
        return
    state["updated"] = now.isoformat(timespec="seconds")
    if not a.dry:
        json.dump(state, open(a.state, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
