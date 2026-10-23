#!/usr/bin/env python3
"""Builds data.json (news + encrypted calendar) for the morning dashboard.
Runs daily on GitHub Actions; weather and bird-of-the-day load live in the page.

Env (all optional — the script degrades gracefully without them):
  GEMINI_API_KEY  picks and summarises the news (without it: top RSS headlines)
  GEMINI_MODEL    override the model (default: gemini-2.5-flash, then gemini-flash-latest)
  ICAL_URLS       Google Calendar "secret iCal" URLs, comma/newline separated
  CAL_KEY         passphrase used to encrypt the calendar (required with ICAL_URLS)
"""
import base64, datetime as dt, json, os, re, sys
import xml.etree.ElementTree as ET
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
NOW = dt.datetime.now(TZ)
TODAY = NOW.date()
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")
UA = {"User-Agent": "MorningDashboard/2.0 (personal dashboard; GitHub Actions)"}

GN, Q = "https://news.google.com/rss", "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
FEEDS = {
    "intl": f"{GN}/headlines/section/topic/WORLD?{Q}",
    "tw": f"{GN}/headlines/section/topic/NATION?{Q}",
    "kl": f"{GN}/search?q={quote('基隆市政府 OR 基隆市府 OR 謝國樑 when:3d')}&{Q}",
}

PROMPT = """今天是 {date}（台灣時間）。你是基隆市政府官員的晨間簡報編輯。下方是三組新聞候選，每則有 id。
- intl：選 5 則最重大的國際新聞。
- tw：選 5 則最重大的台灣國內新聞。
- kl：選 5 則基隆市政府官員最該注意的新聞（市政決策、首長動向、公共安全、議會、民生權益優先，活動花絮其次）。
同一事件只選一則。每則以繁體中文寫精簡標題（28 字內）與 2–3 句摘要（90 字內）；可用 Google 搜尋查證細節，但只能從候選 id 中挑選。
只輸出 JSON：{{"intl":[{{"id":0,"title":"","summary":""}}],"tw":[...],"kl":[...]}}
候選：
{cands}"""


def log(*a):
    print(*a, file=sys.stderr)


def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r


def feed(url, n=25):
    items = []
    for it in ET.fromstring(get(url).content).iter("item"):
        title, src = (it.findtext("title") or "").strip(), (it.findtext("source") or "").strip()
        if src and title.endswith(f" - {src}"):
            title = title[: -len(src) - 3]
        title = re.sub(r"\s*[|｜]\s*[^|｜]{1,8}$", "", title)  # drop trailing "| 政治" section tags
        items.append({"title": title, "url": it.findtext("link") or "", "source": src})
        if len(items) == n:
            break
    return items


def gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {}
    models = dict.fromkeys(m for m in (os.environ.get("GEMINI_MODEL"), "gemini-2.5-flash", "gemini-flash-latest") if m)
    for model in models:
        for tools in ([{"google_search": {}}], None):  # grounded first, plain as fallback
            body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3}}
            if tools:
                body["tools"] = tools
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": key}, json=body, timeout=180)
                r.raise_for_status()
                text = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
                return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except Exception as e:
                log(f"gemini {model} grounded={bool(tools)}: {e}")
    return {}


def distinct(items, n=5):
    """Without Gemini: skip headlines that share most of their character bigrams with one already kept."""
    out, seen = [], []
    for it in items:
        g = {it["title"][i:i + 2] for i in range(len(it["title"]) - 1)}
        if all(len(g & s) / max(1, min(len(g), len(s))) < 0.35 for s in seen):
            out.append({**it, "summary": ""})
            seen.append(g)
        if len(out) == n:
            break
    return out


def pick(cands, chosen, n=5):
    out = []
    for c in (chosen or [])[:n]:
        try:
            src = cands[int(c["id"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        out.append({**src, "title": c.get("title") or src["title"], "summary": c.get("summary", "")})
    return out or distinct(cands, n)


def encrypt(text, passphrase, iters=200_000):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(hashes.SHA256(), 32, salt, iters).derive(passphrase.encode())
    b64 = lambda b: base64.b64encode(b).decode()
    return {"salt": b64(salt), "iv": b64(iv), "iter": iters, "data": b64(AESGCM(key).encrypt(iv, text.encode(), None))}


def calendar():
    urls = [u for u in re.split(r"[\s,]+", os.environ.get("ICAL_URLS", "")) if u]
    key = os.environ.get("CAL_KEY")
    if not urls or not key:
        return None  # never publish an unencrypted calendar
    import icalendar, recurring_ical_events
    start = dt.datetime.combine(TODAY, dt.time(), TZ)
    events = []
    for url in urls:
        try:
            cal = icalendar.Calendar.from_ical(get(url).content)
        except Exception as e:
            log("calendar:", e)
            continue
        name = str(cal.get("X-WR-CALNAME", ""))
        for ev in recurring_ical_events.of(cal).between(start, start + dt.timedelta(days=1)):
            title, s = str(ev.get("SUMMARY", "")).strip(), ev.get("DTSTART").dt
            if not title or str(ev.get("STATUS", "")).upper() == "CANCELLED":
                continue
            if isinstance(s, dt.datetime):
                time = (s if s.tzinfo else s.replace(tzinfo=TZ)).astimezone(TZ).strftime("%H:%M")
            else:
                time = "全天"
            events.append({"time": time, "title": title, "cal": name, "loc": str(ev.get("LOCATION", "") or "")})
    events.sort(key=lambda e: (e["time"] != "全天", e["time"]))
    return encrypt(json.dumps(events, ensure_ascii=False), key)


def main():
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    cands = {}
    for k, url in FEEDS.items():
        try:
            cands[k] = feed(url)
        except Exception as e:
            log(f"feed {k}:", e)
            cands[k] = []
    slim = {k: [{"id": i, "title": c["title"], "source": c["source"]} for i, c in enumerate(v)] for k, v in cands.items()}
    ai = gemini(PROMPT.format(date=TODAY, cands=json.dumps(slim, ensure_ascii=False)))
    news = {k: pick(cands[k], ai.get(k)) if cands[k] else old.get("news", {}).get(k, []) for k in FEEDS}
    data = {
        "date": TODAY.isoformat(),
        "updatedAt": NOW.isoformat(timespec="seconds"),
        "ai": bool(ai),
        "news": news,
        "calendar": calendar(),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    log(f"wrote {OUT} · ai={data['ai']} · " + " ".join(f"{k}={len(v)}" for k, v in news.items()))


if __name__ == "__main__":
    main()
