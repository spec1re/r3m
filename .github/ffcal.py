pass
import json, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BER = ZoneInfo("Europe/Berlin")
NY = ZoneInfo("America/New_York")
FF_JSON = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_URL = "https://www.forexfactory.com/calendar"
UA = "Mozilla/5.0 r3m-reef"
EVERY = 3600                                                   
CUR = ("EUR", "GBP", "JPY", "USD")
LEAD = 5                                        
LATE = 10                                                     
NEWS_LEAD = 30                                                   
NEWS_LATE = 10
NFLAG = {"US": "🇺🇸", "DE": "🇩🇪", "EU": "🇪🇺", "GB": "🇬🇧", "JP": "🇯🇵", "CH": "🇨🇭", "CN": "🇨🇳", "FR": "🇫🇷", "IT": "🇮🇹",
         "ES": "🇪🇸", "CA": "🇨🇦", "AU": "🇦🇺", "NZ": "🇳🇿"}
HOL_AT = (6, 40)                           
DIG_AT = (6, 45)                           
SILENT = {2, 1}                                                  
LVL = {"High": 4, "Medium": 3, "Low": 2, "Holiday": 1}
TAG = {4: "🔴 High", 3: "🟠 Medium", 2: "🟡 Low", 1: "⚪ Holiday"}
FLAG = {"AUD": "🇦🇺", "CAD": "🇨🇦", "CHF": "🇨🇭", "CNY": "🇨🇳", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "NZD": "🇳🇿", "USD": "🇺🇸"}


def out(**kv):
    p = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if p:
            open(p, "a").write(f"{k}={v}\n")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tz_label(dt):
    off = int(dt.utcoffset().total_seconds() // 60)
    h, m = divmod(abs(off), 60)
    return f"UTC{'-' if off < 0 else '+'}{h}" + (f":{m:02d}" if m else "")


def fetch(st, now):
    if st.get("week") and now - st.get("read", 0) < EVERY:
        return
    try:
        rows = json.load(urllib.request.urlopen(urllib.request.Request(FF_JSON, headers={"User-Agent": UA}), timeout=20))
    except Exception as e:
        print(f"ff: {e}")
        st["read"] = now - EVERY + 600                               
        return
    week = []
    for r in rows:
        lv = LVL.get(r.get("impact"))
        if not lv or r.get("country") not in CUR:
            continue
        try:
            t = int(datetime.fromisoformat(r["date"]).timestamp())
        except Exception:
            continue
        week.append({"t": t, "c": r["country"], "ttl": r.get("title", ""), "lv": lv})
                                                                                             
    loud = {e["t"] for e in week if e["lv"] >= 3}
    seen, keep = set(), []
    for e in sorted(week, key=lambda e: (e["t"], -e["lv"], e["c"])):
        k = f"{e['ttl']}|{e['c']}|{e['t']}"
        if (e["lv"] != 2 or e["t"] in loud) and k not in seen:
            seen.add(k)
            keep.append(e)
    st["week"], st["read"] = keep, now
    print(f"ff: {len(rows)} rows, {len(keep)} kept")


def line(e):
    return f"{TAG[e['lv']]} · {e['ttl']} {FLAG.get(e['c'], e['c'])}"


def news(st, now, data_path):
    try:
        evs = json.load(open(data_path, encoding="utf-8")).get("events") or []
    except (OSError, ValueError):
        evs = []
    first = "nsent" not in st
    sent = set(st.get("nsent", []))
    hits = []
    for e in evs:
        try:
            t = int(datetime.fromisoformat(e["utc"].replace("Z", "+00:00")).timestamp())
        except (KeyError, ValueError):
            continue
        k = f'{e["utc"]}|{e.get("country", "")}|{e.get("title", "")}'
        if k in sent or not (now - NEWS_LATE * 60 <= t <= now + NEWS_LEAD * 60):
            continue
        sent.add(k)
        if not first:
            hits.append((t, e))
    st["nsent"] = sorted(k for k in sent if k.split("|")[0] >= datetime.fromtimestamp(now - 7 * 86400, timezone.utc).isoformat()[:19])
    msgs = []
    for t in sorted({h[0] for h in hits}):
        mins = round((t - now) / 60)
        head = "Now" if mins <= 1 else f"In {mins} min"
        lines = [f"⚠️ <b>{head} · {datetime.fromtimestamp(t, BER):%H:%M}</b>"]
        for _, e in (h for h in hits if h[0] == t):
            ln = f'{NFLAG.get(e.get("country"), "🌐")} {esc(str(e.get("title", "")))}'
            ex = [f'{w} {esc(str(e[k]))}' for k, w in (("forecast", "fcst"), ("previous", "prev")) if e.get(k) not in (None, "")]
            if ex:
                ln += " · " + " · ".join(ex)
            if e.get("note"):
                ln += f'\n   ↳ {esc(str(e["note"]))}'
            lines.append(ln)
        msgs.append({"text": "\n".join(lines), "quiet": False})
    return msgs


def plan(state_path, msg_path, dry, now_iso=None):
    try:
        st = json.load(open(state_path, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    before = json.dumps(st, sort_keys=True)
    now_dt = datetime.fromisoformat(now_iso).astimezone(BER) if now_iso else datetime.now(BER)
    now = int(now_dt.timestamp())
    fetch(st, now)
    week = st.get("week") or []
    sent = set(st.get("sent", []))
    today = now_dt.date()
    wk = now_dt.weekday() < 5
    key = lambda e: f"{e['ttl']}|{e['c']}|{e['t']}"
    hday = lambda e: datetime.fromtimestamp(e["t"], NY).date()                                                 

                                                                            
    drv = []
    for e in week:
        if e["lv"] == 1 or key(e) in sent or now < e["t"] - LEAD * 60:
            continue
        sent.add(key(e))
        if now <= e["t"] + LATE * 60:
            drv.append(e)
                                   
    hol = []
    if wk and st.get("hol") != str(today) and now_dt.hour * 60 + now_dt.minute >= HOL_AT[0] * 60 + HOL_AT[1]:
        st["hol"] = str(today)
        if now_dt.hour * 60 + now_dt.minute < HOL_AT[0] * 60 + HOL_AT[1] + 60:
            hol = [e for e in week if e["lv"] == 1 and hday(e) == today and key(e) not in sent]
            sent.update(key(e) for e in hol)
                                                                    
    dig = None
    mm = now_dt.hour * 60 + now_dt.minute
    dm = DIG_AT[0] * 60 + DIG_AT[1]
    if wk and st.get("dig") != str(today) and mm >= dm and (week or mm >= dm + 180):
        st["dig"] = str(today)
        if mm < dm + 180:
            rows = [f"{datetime.fromtimestamp(e['t'], BER):%H:%M} · {line(e)}" for e in week
                    if e["lv"] > 1 and datetime.fromtimestamp(e["t"], BER).date() == today]
            hrows = [f"All day · {line(e)}" for e in week if e["lv"] == 1 and hday(e) == today]
            for e in week:
                if e["lv"] == 1 and hday(e) == today:
                    sent.add(key(e))
            dig = (rows + hrows, len(rows) + len(hrows))
            if not dig[0]:
                dig = ([f"— nothing today · {len(week)} in the week's schedule —"], 0)

    st["sent"] = sorted(k for k in sent if int(k.rsplit("|", 1)[1]) > now - 8 * 86400)
    nmsg = news(st, now, os.path.join(os.path.dirname(os.path.abspath(state_path)), "data.json"))
    msg = None
    if drv or hol or dig:
        if drv:
            stamps = {e["t"] for e in drv}
            stamp = lambda t: f"{datetime.fromtimestamp(t, BER):%H:%M} {tz_label(datetime.fromtimestamp(t, BER))}"
            mixed = len(stamps) > 1
            head = f"Upcoming in {LEAD} min" + ("" if mixed else f" · {stamp(drv[0]['t'])}")
            body = [line(e) + (f" · {stamp(e['t'])}" if mixed else "") for e in sorted(drv, key=lambda e: (e["t"], -e["lv"]))]
        elif dig:
            head = f"Today · {now_dt:%b} {now_dt.day}" + (f" · {dig[1]} event" + ("s" if dig[1] != 1 else "") if dig[1] else "") \
                   + f" · {tz_label(now_dt)}"
            body = []
        else:
            head = f"Holiday today · {now_dt:%b} {now_dt.day}"
            body = []
        if hol and not dig:
            body += [line(e) for e in hol]
        if dig:
            body += (["— today —"] if body else []) + dig[0]
        loud = max((e["lv"] for e in drv), default=0)
        ring = bool(drv and loud not in SILENT) or (hol and not dig and 1 not in SILENT) or bool(dig)
        msg = {"text": f'<b><a href="{FF_URL}">Forex Factory</a> · {esc(head)}</b>\n' + esc("\n".join(body)),
               "quiet": not ring}
    if nmsg:
        msg = dict(nmsg[0], more=nmsg[1:]) if msg is None else dict(msg, more=nmsg)
    if msg:
        json.dump(msg, open(msg_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"now {now_dt:%a %d.%m %H:%M} Berlin · week {len(week)} · " + ("send" if msg else "nothing due"))
    if dry:
        for m in ([msg] + msg.get("more", [])) if msg else []:
            print(("🔕 " if m["quiet"] else "🔔 ") + m["text"])
        out(write=0, send=0)
        return
    changed = json.dumps(st, sort_keys=True) != before
    if changed:
        json.dump(st, open(state_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    out(write=int(changed), send=int(bool(msg)))


def send(msg_path):
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not tok or not chat:
        sys.exit("TG_BOT_TOKEN / TG_CHAT_ID missing")
    m0 = json.load(open(msg_path, encoding="utf-8"))
    bad = 0
    for m in [m0] + m0.get("more", []):
        body = {"chat_id": chat, "parse_mode": "HTML", "disable_web_page_preview": True, "text": m["text"]}
        if m.get("quiet"):
            body["disable_notification"] = True
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = json.loads(r.read()).get("ok")
        except Exception as e:
            print(f"Telegram: {e}")
            ok = False
        print("sent" if ok else "Telegram said no")
        bad += not ok
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "plan":
        plan(a[2], a[3], "--dry" in a, a[a.index("--now") + 1] if "--now" in a else None)
    elif a[1] == "send":
        send(a[2])
