"""Google Calendar and Gmail for the model, with the user's own Google account (optional).

Setup, once (the phone app's Google screen walks through it):
  1. In Google Cloud Console create an OAuth client of type "Desktop app" (and enable the Gmail and Calendar APIs).
  2. Paste its client ID and secret in the app.  3. Tap Connect: the consent page opens in the PC's browser.
Tokens stay on this PC (server/data/google_token.json). Reading mail and calendars and writing drafts need no
approval; sending an email or adding a Google Calendar event always waits for the user's OK on the phone.
"""
import base64
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import secrets
import time
import urllib.parse
import webbrowser
from email.mime.text import MIMEText

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import DATA_DIR, config

SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/userinfo.email", "openid"]
CLIENT = DATA_DIR / "google_client.json"
TOKEN = DATA_DIR / "google_token.json"
AUTH_URL, TOKEN_URL = "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token"
GMAIL, CAL = "https://gmail.googleapis.com/gmail/v1/users/me", "https://www.googleapis.com/calendar/v3"

router = APIRouter(prefix="/api/google")     # app-only (mounted with the app token)
public = APIRouter()                         # the OAuth redirect, reached by the PC's own browser
_pending: dict[str, str] = {}                # state -> PKCE verifier


# ---------------------------------------------------------------- OAuth
def _client() -> dict:
    return json.loads(CLIENT.read_text(encoding="utf-8")) if CLIENT.exists() else {}


def _token() -> dict:
    return json.loads(TOKEN.read_text(encoding="utf-8")) if TOKEN.exists() else {}


def connected() -> bool:
    return bool(_token().get("refresh_token"))


def _redirect() -> str:
    return f"http://127.0.0.1:{config['port']}/google/callback"


def _access() -> str:
    t = _token()
    if not t.get("refresh_token"):
        raise RuntimeError("Google is not connected. Connect it in the phone app (menu -> Google).")
    if t.get("access_token") and t.get("expires_at", 0) > time.time() + 60:
        return t["access_token"]
    c = _client()
    r = httpx.post(TOKEN_URL, data={"client_id": c["client_id"], "client_secret": c["client_secret"],
                                    "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Google refused the saved login ({r.status_code}). Connect again in the app.")
    d = r.json()
    t.update(access_token=d["access_token"], expires_at=time.time() + d.get("expires_in", 3600))
    TOKEN.write_text(json.dumps(t), encoding="utf-8")
    return t["access_token"]


def _api(method: str, url: str, **kw):
    r = httpx.request(method, url, headers={"Authorization": "Bearer " + _access()}, timeout=60, **kw)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:300])
        except ValueError:
            msg = r.text[:300]
        raise RuntimeError(f"Google API error {r.status_code}: {msg}")
    return r.json() if r.content else {}


class ClientIn(BaseModel):
    client_id: str
    client_secret: str


@router.get("/status")
async def status():
    c, t = _client(), _token()
    return {"configured": bool(c.get("client_id")), "connected": connected(), "email": t.get("email", ""),
            "redirect_uri": _redirect()}


@router.post("/client")
async def set_client(b: ClientIn):
    if not b.client_id.strip().endswith(".apps.googleusercontent.com"):
        raise HTTPException(400, "That does not look like a Google OAuth client ID (…apps.googleusercontent.com)")
    CLIENT.write_text(json.dumps({"client_id": b.client_id.strip(), "client_secret": b.client_secret.strip()}), encoding="utf-8")
    return await status()


@router.post("/connect")
async def connect():
    """Opens Google's consent page in the PC's browser (the redirect comes back to this PC)."""
    c = _client()
    if not c.get("client_id"):
        raise HTTPException(400, "Add the Google OAuth client ID and secret first")
    state, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    _pending[state] = verifier
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": _redirect(), "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    opened = False
    try:
        opened = webbrowser.open(url)
    except Exception:
        pass
    return {"url": url, "opened_on_pc": opened}


@router.post("/disconnect")
async def disconnect():
    t = _token()
    if t.get("refresh_token"):
        try:
            httpx.post("https://oauth2.googleapis.com/revoke", params={"token": t["refresh_token"]}, timeout=15)
        except httpx.HTTPError:
            pass
    TOKEN.unlink(missing_ok=True)
    return await status()


@public.get("/google/callback", response_class=HTMLResponse)
async def callback(req: Request, code: str = "", state: str = "", error: str = ""):
    page = lambda msg: f"<html><body style='font:16px sans-serif;padding:40px'><h2>LocalAI Bridge</h2><p>{html.escape(msg)}</p></body></html>"
    verifier = _pending.pop(state, None)
    if error or not code or not verifier:
        return page(f"Google sign-in was not completed ({error or 'invalid or expired request'}). Try Connect again in the app.")
    c = _client()
    async with httpx.AsyncClient(timeout=30) as h:
        r = await h.post(TOKEN_URL, data={"client_id": c["client_id"], "client_secret": c["client_secret"], "code": code,
                                          "code_verifier": verifier, "grant_type": "authorization_code",
                                          "redirect_uri": _redirect()})
        if r.status_code != 200:
            return page(f"Google did not accept the sign-in ({r.status_code}): {r.text[:200]}")
        d = r.json()
        who = ""
        try:
            who = (await h.get("https://openidconnect.googleapis.com/v1/userinfo",
                               headers={"Authorization": "Bearer " + d["access_token"]})).json().get("email", "")
        except Exception:
            pass
    TOKEN.write_text(json.dumps({"refresh_token": d.get("refresh_token", ""), "access_token": d["access_token"],
                                 "expires_at": time.time() + d.get("expires_in", 3600), "email": who}), encoding="utf-8")
    return page(f"Connected{(' as ' + who) if who else ''}. You can close this page and go back to the phone app.")


# ---------------------------------------------------------------- Calendar
def _iso(s: str, default: dt.datetime) -> str:
    from .organizer import _parse
    d = _parse(s) or default
    return d.astimezone().isoformat()


def calendar_events(start: str = "", end: str = "") -> list[dict]:
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    a = _iso(start, today)
    from .organizer import _parse
    b_dt = _parse(end) or (_parse(start) or today) + dt.timedelta(days=30)
    if end and len(end.strip()) <= 10:
        b_dt += dt.timedelta(days=1)
    d = _api("GET", CAL + "/calendars/primary/events", params={"timeMin": a, "timeMax": b_dt.astimezone().isoformat(),
                                                               "singleEvents": "true", "orderBy": "startTime", "maxResults": 100})
    out = []
    for e in d.get("items", []):
        s, en = e.get("start", {}), e.get("end", {})
        fmt = lambda x: (x.get("dateTime", "")[:16].replace("T", " ") or x.get("date", ""))
        out.append({"id": e.get("id", ""), "title": e.get("summary", "(no title)"), "start": fmt(s), "end": fmt(en),
                    "location": e.get("location", ""), "notes": (e.get("description") or "")[:500], "source": "google"})
    return out


def calendar_add(title: str, start: str, end: str = "", location: str = "", description: str = "") -> dict:
    from .organizer import _parse
    s = _parse(start)
    if not s:
        raise RuntimeError(f"Could not read the start time {start!r}; use YYYY-MM-DD HH:MM")
    all_day = len(start.strip()) <= 10
    if all_day:
        body = {"start": {"date": s.strftime("%Y-%m-%d")},
                "end": {"date": ((_parse(end) or s) + dt.timedelta(days=1)).strftime("%Y-%m-%d")}}
    else:
        e = _parse(end) or s + dt.timedelta(hours=1)
        body = {"start": {"dateTime": s.astimezone().isoformat()}, "end": {"dateTime": e.astimezone().isoformat()}}
    body.update(summary=title, location=location, description=description)
    return _api("POST", CAL + "/calendars/primary/events", json=body)


# ---------------------------------------------------------------- Gmail
def _hdr(m: dict, name: str) -> str:
    return next((h["value"] for h in m.get("payload", {}).get("headers", []) if h["name"].lower() == name.lower()), "")


def _text_of(part: dict) -> str:
    """Plain text of a message (falls back to HTML with the tags removed)."""
    mt, body = part.get("mimeType", ""), part.get("body", {}).get("data")
    if mt == "text/plain" and body:
        return base64.urlsafe_b64decode(body + "==").decode("utf-8", "replace")
    texts = [_text_of(p) for p in part.get("parts", []) or []]
    plain = next((t for t, p in zip(texts, part.get("parts", []) or []) if t and p.get("mimeType") == "text/plain"), "")
    if plain or any(texts):
        return plain or next(t for t in texts if t)
    if mt == "text/html" and body:
        h = base64.urlsafe_b64decode(body + "==").decode("utf-8", "replace")
        return html.unescape(re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", h))
    return ""


def gmail_list(query: str = "in:inbox", max_results: int = 10) -> list[dict]:
    d = _api("GET", GMAIL + "/messages", params={"q": query or "in:inbox", "maxResults": max(1, min(int(max_results or 10), 25))})
    out = []
    for it in d.get("messages", []):
        m = _api("GET", GMAIL + f"/messages/{it['id']}", params={"format": "metadata",
                                                                  "metadataHeaders": ["From", "Subject", "Date"]})
        out.append({"id": m["id"], "thread": m.get("threadId", ""), "from": _hdr(m, "From"), "subject": _hdr(m, "Subject"),
                    "date": _hdr(m, "Date"), "snippet": html.unescape(m.get("snippet", "")),
                    "unread": "UNREAD" in m.get("labelIds", [])})
    return out


def gmail_read(mid: str) -> dict:
    m = _api("GET", GMAIL + f"/messages/{mid}", params={"format": "full"})
    return {"id": m["id"], "thread": m.get("threadId", ""), "from": _hdr(m, "From"), "to": _hdr(m, "To"),
            "subject": _hdr(m, "Subject"), "date": _hdr(m, "Date"), "message_id": _hdr(m, "Message-ID"),
            "body": re.sub(r"\n{3,}", "\n\n", _text_of(m.get("payload", {}))).strip()[:12000]}


def _raw(to: str, subject: str, body: str, reply_to_id: str = "") -> dict:
    msg = MIMEText(body, "plain", "utf-8")
    thread = ""
    if reply_to_id:
        o = gmail_read(reply_to_id)
        to = to or email.utils.parseaddr(o["from"])[1]
        subject = subject or (o["subject"] if o["subject"].lower().startswith("re:") else "Re: " + o["subject"])
        if o["message_id"]:
            msg["In-Reply-To"] = msg["References"] = o["message_id"]
        thread = o["thread"]
    if not to:
        raise RuntimeError("No recipient: give 'to' or reply_to_id")
    msg["To"], msg["Subject"] = to, subject
    d = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
    if thread:
        d["threadId"] = thread
    return d


def gmail_draft(to: str, subject: str, body: str, reply_to_id: str = "") -> dict:
    return _api("POST", GMAIL + "/drafts", json={"message": _raw(to, subject, body, reply_to_id)})


def gmail_send(to: str, subject: str, body: str, reply_to_id: str = "") -> dict:
    return _api("POST", GMAIL + "/messages/send", json=_raw(to, subject, body, reply_to_id))


def gmail_send_draft(draft_id: str) -> dict:
    return _api("POST", GMAIL + "/drafts/send", json={"id": draft_id})


# ---------------------------------------------------------------- model tools
def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


TOOL_NAMES = {"gmail_list", "gmail_read", "gmail_draft", "gmail_send", "gmail_send_draft", "google_calendar_add"}


def tool_schemas() -> list[dict]:
    if not connected():
        return []
    mail = {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string", "description": "plain text"},
            "reply_to_id": {"type": "string", "description": "message id when replying (keeps the thread; to/subject optional)"}}
    return [
        _fn("gmail_list", "List the user's emails (Gmail search syntax: 'in:inbox', 'is:unread', 'from:sara', 'newer_than:2d').",
            {"query": {"type": "string"}, "max_results": {"type": "integer"}}, []),
        _fn("gmail_read", "Read one email in full by its id (from gmail_list).", {"id": {"type": "string"}}, ["id"]),
        _fn("gmail_draft", "Write a draft email or a draft reply (saved in Gmail Drafts, NOT sent). Prefer this, then "
            "show the draft to the user and ask whether to send it.", mail, ["body"]),
        _fn("gmail_send", "Send an email or a reply now. The user must approve it on the phone first.", mail, ["body"]),
        _fn("gmail_send_draft", "Send a draft created with gmail_draft. The user must approve it on the phone first.",
            {"draft_id": {"type": "string"}}, ["draft_id"]),
        _fn("google_calendar_add", "Add an event to the user's Google Calendar (needs the user's approval).",
            {"title": {"type": "string"}, "start": {"type": "string", "description": "YYYY-MM-DD HH:MM or YYYY-MM-DD"},
             "end": {"type": "string"}, "location": {"type": "string"}, "description": {"type": "string"}}, ["title", "start"]),
    ]


def execute(name: str, a: dict) -> str:
    if name == "gmail_list":
        rows = gmail_list(a.get("query") or "in:inbox", a.get("max_results") or 10)
        return "\n".join(f"{'* ' if m['unread'] else '  '}id={m['id']}  {m['date'][:25]}  From: {m['from']}\n"
                         f"    Subject: {m['subject']}\n    {m['snippet'][:160]}" for m in rows) or "No emails found."
    if name == "gmail_read":
        m = gmail_read(a["id"])
        return f"From: {m['from']}\nTo: {m['to']}\nDate: {m['date']}\nSubject: {m['subject']}\n\n{m['body']}"
    if name == "gmail_draft":
        d = gmail_draft(a.get("to", ""), a.get("subject", ""), a.get("body", ""), a.get("reply_to_id", ""))
        return f"Draft saved in Gmail (draft_id={d.get('id')}). It was NOT sent. Show it to the user and ask before sending."
    if name == "gmail_send":
        m = gmail_send(a.get("to", ""), a.get("subject", ""), a.get("body", ""), a.get("reply_to_id", ""))
        return f"Email sent (id={m.get('id')})."
    if name == "gmail_send_draft":
        m = gmail_send_draft(a["draft_id"])
        return f"Draft sent (message id={m.get('id')})."
    if name == "google_calendar_add":
        e = calendar_add(a.get("title", "Event"), a.get("start", ""), a.get("end", ""), a.get("location", ""), a.get("description", ""))
        return f"Added to Google Calendar: {e.get('summary')} ({e.get('htmlLink', '')})"
    raise KeyError(name)


# ---------------------------------------------------------------- REST for the phone app (mail view)
@router.get("/mail")
async def r_mail(q: str = "in:inbox", n: int = 15):
    import asyncio
    try:
        return await asyncio.to_thread(gmail_list, q, n)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/mail/{mid}")
async def r_mail_one(mid: str):
    import asyncio
    try:
        return await asyncio.to_thread(gmail_read, mid)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
