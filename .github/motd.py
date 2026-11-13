pass
import json, os, random, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BER = ZoneInfo("Europe/Berlin")
MOTD = (7, 30)                                           
LATE = 60                                                   
WIN = (7 * 60, 22 * 60)                                                              
GAP = (0.5, 1.5)                                        
LINES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "motd_lines.json"), encoding="utf-8"))


def out(**kv):
    p = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if p:
            open(p, "a").write(f"{k}={v}\n")


def deal(st, rng):
    deck = [i for i in st.get("deck", []) if 0 <= i < len(LINES)]
    if not deck:
        deck = list(range(len(LINES)))
        rng.shuffle(deck)
    i = deck.pop()
    st["deck"] = deck
    return i


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def plan(state_path, msg_path, dry):
    try:
        st = json.load(open(state_path, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    before = json.dumps(st, sort_keys=True)
    rng = random.Random()
    now = datetime.now(BER)
    ts = int(now.timestamp())
    m = now.hour * 60 + now.minute
    wk = now.weekday() < 5
    gap = lambda: ts + int(rng.uniform(*GAP) * 3600)
    head = None
    mt = MOTD[0] * 60 + MOTD[1]
    today = now.strftime("%Y-%m-%d")
    if st.get("motd") != today and m >= mt:
        st["motd"] = today                                                                                      
        if wk and m < mt + LATE:
            head = "☕ Message of the Day"
    nxt = st.get("next")
    if head:
        st["next"] = gap()
    elif wk and WIN[0] <= m < WIN[1]:
        if nxt is None:
            st["next"] = gap()                                                                
        elif ts >= nxt:
            head = "🎱 Trading Wisdom"
            st["next"] = gap()
    elif nxt is not None and ts >= nxt:
        st["next"] = None                                                                                
    if head:
        e, line = LINES[deal(st, rng)]
        if e == "🎬" and head == "🎱 Trading Wisdom":
            head = "🎬 Trading Floor"
        text = f"<b>{esc(head)}</b>\n\n{e} <i>{esc('“' + line + '”')}</i>"
        st["last"] = {"t": now.strftime("%Y-%m-%d %H:%M"), "head": head, "line": line}
        st["sent"] = st.get("sent", 0) + 1
        open(msg_path, "w", encoding="utf-8").write(text)
    st["lines"] = len(LINES)
    st["left"] = len(st.get("deck", [])) or len(LINES)
    nx = st.get("next")
    print(f"now {now:%a %d.%m %H:%M} Berlin · {'send ' + head if head else 'nothing due'} · next "
          f"{datetime.fromtimestamp(nx, BER):%a %H:%M}" if nx else f"now {now:%a %d.%m %H:%M} Berlin · "
          f"{'send ' + head if head else 'nothing due'} · next: inside the window")
    if dry:
        print(open(msg_path, encoding="utf-8").read() if head else "")
        out(write=0, send=0)
        return
    changed = json.dumps(st, sort_keys=True) != before
    if changed:
        json.dump(st, open(state_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out(write=int(changed), send=int(bool(head)))


def send(msg_path):
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not tok or not chat:
        sys.exit("TG_BOT_TOKEN / TG_CHAT_ID missing")
    body = json.dumps({"chat_id": chat, "parse_mode": "HTML", "disable_web_page_preview": True,
                       "text": open(msg_path, encoding="utf-8").read()}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ok = json.loads(r.read()).get("ok")
    print("sent" if ok else "Telegram said no")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        plan(sys.argv[2], sys.argv[3], "--dry" in sys.argv)
    elif sys.argv[1] == "send":
        send(sys.argv[2])
