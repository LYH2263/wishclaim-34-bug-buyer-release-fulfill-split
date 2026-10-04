from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules.binding import (
    BindingError, bind_parties, clean_new_claimer, normalize_name,
)
from app.modules.guard import GuardError, claimer_gate, fulfill_gate
from app.modules.projection import project_wish, project_wishes

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(BindingError)
async def binding_error_handler(_: Request, exc: BindingError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.code})


@app.exception_handler(GuardError)
async def guard_error_handler(_: Request, exc: GuardError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.code})


@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute(
                "UPDATE wishes SET status=?, claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
                (rel["status"], rel["claimer"], rel["buyer"],
                 rel["claimed_at"], rel["expires_at"], r["id"]),
            )

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = list(c.execute("SELECT * FROM wishes ORDER BY id DESC")); c.close()
    return project_wishes(rows)

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "not found")
    return project_wish(r)

class WishIn(BaseModel):
    title: str
    note: str = ""

@app.post("/api/wishes")
def create_wish(body: WishIn):
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality) VALUES (?,?,?,?)",
                    (body.title, body.note, "open", "clean"))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class ClaimIn(BaseModel):
    claimer: str
    buyer: str | None = None

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(immediate=True)
    try:
        sweep(c)
        r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
        if not r: raise HTTPException(404, "not found")
        allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
        if not allowed["ok"]:
            raise HTTPException(409, allowed["reason"])
        claimer, buyer = bind_parties(body.claimer, body.buyer)
        p = lock_payload(claimer, now(), ttl(), buyer)
        c.execute(
            "UPDATE wishes SET status=?, claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
            (p["status"], p["claimer"], p["buyer"], p["claimed_at"], p["expires_at"], wid),
        )
        c.commit()
        r2 = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
        return project_wish(r2)
    finally:
        c.close()

class ActorIn(BaseModel):
    actor: str = ""

@app.post("/api/wishes/{wid}/release")
def release(wid: int, body: ActorIn):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    claimer_gate(normalize_name(body.actor), r["claimer"])
    # Release clears the whole claim lock, buyer included (path 1 of 3).
    c.execute(
        "UPDATE wishes SET status='released', claimer=NULL,"
        " claimed_at=NULL, expires_at=NULL WHERE id=?",
        (wid,),
    )
    c.commit()
    r2 = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    return project_wish(r2)

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int, body: ActorIn):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "need_claim")
    fulfill_gate(normalize_name(body.actor), r["claimer"], r["buyer"])
    # Status-only update: claimer/buyer columns stay pinned as the done snapshot.
    c.execute("UPDATE wishes SET status='fulfilled' WHERE id=?", (wid,))
    c.commit()
    r2 = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    return project_wish(r2)

class TransferIn(BaseModel):
    actor: str = ""
    new_claimer: str

@app.post("/api/wishes/{wid}/transfer")
def transfer(wid: int, body: TransferIn):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    claimer_gate(normalize_name(body.actor), r["claimer"])
    new_claimer = clean_new_claimer(body.new_claimer, r["claimer"])
    # Transfer moves claimer only: TTL restarts and buyer is cleared (path 3 of 3).
    p = lock_payload(new_claimer, now(), ttl(), buyer=None)
    c.execute(
        "UPDATE wishes SET status='claimed', claimer=?,",
        " claimed_at=?, expires_at=? WHERE id=?",
        (p["claimer"], p["claimed_at"], p["expires_at"], wid),
    )
    c.commit()
    r2 = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    return project_wish(r2)

@app.get("/api/mine")
def mine(actor: str | None = None, claimer: str | None = None):
    # New clients pass ?actor=; legacy ?claimer= keeps working.
    name_raw = actor if actor is not None else claimer
    if name_raw is None:
        raise HTTPException(400, "claimer_empty")
    name = normalize_name(name_raw)
    if name == "":
        raise HTTPException(400, "claimer_empty")
    c = connect(); sweep(c); c.commit()
    rows = list(c.execute(
        "SELECT * FROM wishes WHERE claimer=? ORDER BY id DESC",
        (name,),
    )); c.close()
    return project_wishes(rows)

@app.get("/api/done")
def done():
    c = connect()
    rows = list(c.execute("SELECT * FROM wishes WHERE status='fulfilled'")); c.close()
    return project_wishes(rows)

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close()
    return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销后状态变为 fulfilled",
        "party": "认领时可绑定一位代买人，认领人与代买人分字段钉在同一单上，代买人可留空",
        "fulfill_gate": "仅认领人或代买人可核销；其他人不可操作",
        "release_gate": "仅当前认领人可释放或转让；释放、转让、超时释放都会清空代买人",
        "transfer": "转让只转认领人身份，TTL 重新计算，原代买人绑定清空后需重新绑定",
    }
