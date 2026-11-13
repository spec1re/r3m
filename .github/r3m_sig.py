pass
import io, json, os, subprocess, sys, tarfile, tempfile, time, traceback, urllib.request
from datetime import datetime, timezone

STEP = 300
STALE = 1800                                                                  
KEEP = 9 * 86400                       
LOG = 8 * 86400                          
TRIES = 3                                                             
HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.environ.get("LIVE", "false") == "true"


def out(**kv):
    p = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if p:
            open(p, "a").write(f"{k}={v}\n")


def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def closed_market(now):
    d = datetime.fromtimestamp(now, timezone.utc)
    wd, h = d.weekday(), d.hour
    return wd == 5 or (wd == 6 and h < 21) or (wd == 4 and h >= 22)


def due(state):
    st = load(state)
    now = int(time.time())
    slot = now // STEP * STEP
    out(due=int(not closed_market(now) and st.get("slot", 0) < slot))


def engine():
    key = os.environ.get("R3M_ENGINE_KEY", "")
    if not key:
        sys.exit("R3M_ENGINE_KEY missing")
    raw = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-pass", "env:R3M_ENGINE_KEY",
                          "-in", os.path.join(HERE, "r3m-engine.enc")], capture_output=True)
    if raw.returncode:
        sys.exit("the engine did not open (key?)")
    d = tempfile.mkdtemp(dir=os.environ.get("RUNNER_TEMP"))
    with tarfile.open(fileobj=io.BytesIO(raw.stdout), mode="r:gz") as tf:
        tf.extractall(d, filter="data")
    sys.path.insert(0, d)
    import r3m_live
    return r3m_live, d


def plan(state, msg_path, cache, dry):
    st = load(state)
    now = int(time.time())
    slot = now // STEP * STEP
    miss = [k for k in ("R3M_ENGINE_KEY", "CTRADER_MCP_TOKEN") if not os.environ.get(k, "").strip()]
    if miss or not os.path.exists(os.path.join(HERE, "r3m-engine.enc")):
        print("not set up yet: " + ", ".join(miss or ["r3m-engine.enc"]))
        out(write=0, send=0)
        return
    try:
        L, d = engine()
        res = L.run(cache, now)
    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = " · ".join(f"{os.path.basename(f.filename)}:{f.lineno}" for f in tb[-3:])
        sys.exit(f"engine error: {type(e).__name__} at {where}")
    sent = st.setdefault("sent", {})
    since = st.setdefault("since", slot)
    new, stale = [], 0
    for e in sorted(res["events"], key=lambda e: (e["t"], e["sym"], e["rank"])):
        if e["key"] in sent:
            continue
        sent[e["key"]] = e["t"]
        if e["t"] < since:
            continue
        if e["t"] < now - STALE:
            stale += 1
            continue
        new.append(e)
    msgs = []
    for e in new:
        k = (e["sym"], e["t"], e["eng"])
        if msgs and msgs[-1]["k"] == k:
            msgs[-1]["lines"].append(e["text"])
            msgs[-1]["ring"] |= e["ring"]
        else:
            msgs.append({"k": k, "sym": e["sym"], "t": e["t"], "eng": e["eng"], "head": L.header(e["sym"], e["sess"], e["eng"]),
                         "lines": [e["text"]], "ring": e["ring"]})
    for m in msgs:
        m["text"] = m["head"] + L.esc("\n\n".join(m["lines"]))
                                                                                                             
    lag = [s for s, i in res["syms"].items() if i["err"] or (i["last"] is not None and i["last"] + STEP < slot
                                                             and slot - (i["last"] + STEP) <= 900)]
    tries = st.get("tries", 0) + 1 if st.get("tslot") == slot else 1
    st["tslot"], st["tries"] = slot, tries
    if not lag or tries >= TRIES:
        st["slot"] = slot
    cut = now - KEEP
    st["sent"] = {k: t for k, t in sent.items() if t >= cut}
    log = [x for x in st.get("log", []) if x["t"] >= now - LOG]
    log += [{"t": m["t"], "seen": now, "sym": m["sym"], "eng": m["eng"], "ring": m["ring"], "text": m["text"],
             "sent": LIVE and not dry} for m in msgs]
    st["log"] = log
    st["last"] = {"t": now, "new": len(msgs), "stale": stale, "lag": lag, "live": LIVE,
                  "syms": {s: {k: i[k] for k in ("bars", "new", "err")} for s, i in res["syms"].items()}}
    st["runs"] = st.get("runs", 0) + 1
    lab_note = lab(L, st, cache, now, dry)
    print(f"{datetime.fromtimestamp(now, timezone.utc):%a %H:%M} UTC · {sum(1 for i in res['syms'].values() if not i['err'])}"
          f"/{len(res['syms'])} symbols · {len(msgs)} new · {stale} stale" + (f" · waiting for {', '.join(lag)}" if lag else "")
          + ("" if LIVE else " · shadow") + lab_note)
    for s, i in res["syms"].items():
        if i["err"]:
            print(f"  {s}: {i['err']}")
    if dry:
        for m in msgs:
            print("\n" + m["text"])
        out(write=0, send=0)
        return
    json.dump([{"text": m["text"], "quiet": not m["ring"]} for m in msgs], open(msg_path, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(st, open(state, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    out(write=1, send=int(LIVE and bool(msgs)))


def lab_env():
    pass
    return dict(os.environ, R3M_LAB_KEY=os.environ.get("R3M_LAB_KEY", "").strip())


def opens(path):
    pass
    if not os.path.exists(path):
        return False
    r = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-md", "sha256",
                        "-pass", "env:R3M_LAB_KEY", "-in", path], capture_output=True, env=lab_env())
    return r.returncode == 0 and r.stdout[:2] == b"\x1f\x8b"


def lab(L, st, cache, now, dry):
    pass
    key = os.environ.get("R3M_LAB_KEY", "").strip()
    if not key or not hasattr(L, "lab"):
        return " · lab: no key"
    hr = now // 3600
    if st.get("labH") == hr:
        return ""
    import gzip, hashlib
    try:
        raw = json.dumps(L.lab(cache, now), separators=(",", ":")).encode()
    except Exception as e:
        return f" · lab: {type(e).__name__}"
    st["labH"] = hr
    sha = "k2" + hashlib.sha256(raw[raw.index(b'"cols"'):]).hexdigest()
    if (sha == st.get("labSha") and opens("r3m-lab.enc")) or dry:
        return " · lab unchanged"
    enc = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-md", "sha256", "-salt",
                          "-pass", "env:R3M_LAB_KEY"], input=gzip.compress(raw, mtime=0), capture_output=True, env=lab_env())
    if enc.returncode:
        return " · lab: encryption failed"
    open("r3m-lab.enc", "wb").write(enc.stdout)
    st["labSha"] = sha
    return f" · lab {len(enc.stdout):,} bytes"


def replay(frm, out_path):
    pass
    import gzip
    for k in ("R3M_ENGINE_KEY", "R3M_LAB_KEY", "CTRADER_MCP_TOKEN"):
        if not os.environ.get(k, "").strip():
            sys.exit(k + " missing")
    try:
        L, d = engine()
        start = int(datetime.strptime(frm, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        p = L.replay(start, log=lambda m: print(m, flush=True))
        raw = json.dumps(p, separators=(",", ":")).encode()
    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        sys.exit(f"engine error: {type(e).__name__} at " + " · ".join(f"{os.path.basename(f.filename)}:{f.lineno}" for f in tb[-3:]))
    enc = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "100000", "-md", "sha256", "-salt",
                          "-pass", "env:R3M_LAB_KEY"], input=gzip.compress(raw, mtime=0), capture_output=True, env=lab_env())
    if enc.returncode:
        sys.exit("encryption failed")
    open(out_path, "wb").write(enc.stdout)
    print(f"{len(p['rows']):,} trades · {len(enc.stdout):,} bytes → {out_path}")


def send(msg_path):
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not tok or not chat:
        sys.exit("TG_BOT_TOKEN / TG_CHAT_ID missing")
    bad = 0
    for m in json.load(open(msg_path, encoding="utf-8")):
        body = {"chat_id": chat, "parse_mode": "HTML", "disable_web_page_preview": True, "text": m["text"]}
        if m.get("quiet"):
            body["disable_notification"] = True
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = json.loads(r.read()).get("ok")
        except Exception as e:
            ok = False
            print(type(e).__name__)
        bad += not ok
        time.sleep(1)
    print("sent" if not bad else f"{bad} not sent")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1] == "due":
        due(sys.argv[2])
    elif sys.argv[1] == "plan":
        plan(sys.argv[2], sys.argv[3], sys.argv[4], "--dry" in sys.argv)
    elif sys.argv[1] == "replay":
        replay(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "send":
        send(sys.argv[2])
