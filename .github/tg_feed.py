#!/usr/bin/env python3
"""Live feed for the R3M Arena website: reads the R3M Signals group with a Telegram user session
and writes the bot messages of the last 7 days to live.json (only bot messages, never what people write).

Runs in the public repo spec1re/r3m (.github/workflows/live.yml, every ~5 min).
Secrets: TG_API_ID, TG_API_HASH (my.telegram.org), TG_SESSION (from scripts/tg_login.py), TG_CHAT_ID.
Source of truth: r3m-digest/site-ci/ (copied into the site by build_site.py).
"""
import asyncio, json, os, re, sys
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession

OUT = sys.argv[1] if len(sys.argv) > 1 else "live.json"
DAYS, MAX = 7, 1500
ALLOWED = {"b", "strong", "i", "em", "u", "s", "del", "code", "pre", "blockquote", "a"}
NORM = {"strong": "b", "em": "i", "del": "s"}


def clean(h):
    """Keep only simple formatting tags; links only http(s)."""
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
