#!/usr/bin/env python3
pass
import asyncio, json, os, re, sys
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

OUT = sys.argv[1] if len(sys.argv) > 1 else "live.json"
DAYS, MAX = 7, 1500
ALLOWED = {"b", "strong", "i", "em", "u", "s", "del", "code", "pre", "blockquote", "a"}
NORM = {"strong": "b", "em": "i", "del": "s"}


def clean(h):
    pass
    def tag(m):
        close, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if name not in ALLOWED:
            return ""
        name = NORM.get(name, name)
        if close:
            return f"</{name}>"
        if name == "a":
            href = re.search(r'href="(https?://[^"]+)"', attrs)
            return f'<a href="{href.group(1)}" target="_blank" rel="noopener">' if href else "<a>"
        return f"<{name}>"
    return re.sub(r"<(/?)([a-zA-Z0-9-]+)([^>]*)>", tag, h)


BLUEBOOK = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)                                                        
KEEP = re.compile(r"^(?:<[^>]+>)*\s*(?:[🟢🔴✅🏆🛑🏁◆🆕]|\d+\. |⚪)")


def public(it):
    pass
    h = it["html"]
    first = re.sub(r"<[^>]+>", "", h.split("\n", 1)[0])
    if re.search(r"R3M Lab Review|Signal Report|R3M Signals · W\d", first) or (first.startswith("📝") and it["t"] < BLUEBOOK.isoformat()):
        return None
    if re.search(r" · \d+[smhDW] · | screener", first) and re.search(r"🧭|⚖️|Pro / Contra|📈 \d+ runs|📈 watchlist", h):                
        ls = h.split("\n")
        keep = [ls[0]] + [short(l) for l in ls[1:] if l.strip() == "" or KEEP.match(l)]
        out = re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()
        return dict(it, html=out, bb=True)
    return it


def short(l):
    pass
    l = re.sub(r" · (?:🧭|📈|⚖️)[^\n]*", "", l)
    m = re.match(r"^(.*(?:SL|TP1|TP2) [\d.,]+(?: \([\d.]+R\))?)(?: · [^\n]*?)?( · auction·failed)?$", l)
    return m.group(1) + (m.group(2) or "") if m and re.search(r"(?:LONG|SHORT) [\d.,]+ · SL", l) else l
    return it


async def main():
    api_id, api_hash, ses = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH"), os.environ.get("TG_SESSION")
    chat = os.environ.get("TG_CHAT_ID", "").strip()
    if not (api_id and api_hash and ses and chat):
        print("secrets missing – nothing to do")
        return
    async with TelegramClient(StringSession(ses), int(api_id), api_hash) as c:
        c.parse_mode = "html"
        ent = None
        for lim in (100, None):
            async for d in c.iter_dialogs(limit=lim):
                if str(d.id) == chat:
                    ent = d.entity
                    break
            if ent:
                break
        if ent is None:
            sys.exit("group not found in the dialogs of this account")
        cut = datetime.now(timezone.utc) - timedelta(days=DAYS)
        items = []
        async for m in c.iter_messages(ent, limit=MAX):
            if m.date < cut:
                break
            if not getattr(m.sender, "bot", False):
                continue
            it = {"id": m.id, "t": m.date.astimezone(timezone.utc).isoformat(), "html": clean(m.text or "")}
            if m.photo:
                it["photo"] = True
            if m.edit_date:
                it["edited"] = True
            items.append(it)
    items.reverse()
    items = [x for x in (public(i) for i in items) if x]
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("items")
    except (FileNotFoundError, ValueError):
        old = None
    if old == items:
        print(f"no change ({len(items)} messages)")
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": items}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"live.json: {len(items)} messages")


asyncio.run(main())
