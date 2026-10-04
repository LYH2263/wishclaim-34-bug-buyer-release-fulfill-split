"""Party split: fulfill permission, buyer clearing, executor pinning.

The decisions pinned down by these tests:
- Only the claimer OR the bound buyer may fulfill; outsiders and empty
  actors get 403 not_party and can never be pinned as executor.
- release / transfer / TTL expiry NULL the old buyer in the same UPDATE that
  changes status, so wall / detail / mine never disagree.
- A failed transfer changes nothing: the new claimer never co-holds fulfill
  rights with the old buyer.
- A dirty buyer rejects the whole claim instead of becoming an empty name.
"""
from app.db import connect


def _create(client, title="x"):
    return client.post("/api/wishes", json={"title": title}).json()["id"]


def _claim(client, wid, claimer, buyer=None):
    body = {"claimer": claimer}
    if buyer is not None:
        body["buyer"] = buyer
    return client.post(f"/api/wishes/{wid}/claim", json=body)


# ---------- binding ------------------------------------------------------

def test_dirty_buyer_rejects_claim_and_leaves_open(client):
    wid = _create(client)
    r = _claim(client, wid, "alice", "   ")
    assert r.status_code == 400
    assert r.json()["detail"] == "buyer_dirty"
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "open"
    assert w["claimer"] is None and w["buyer"] is None
    assert w["parties"] == {"claimer": None, "buyer": None, "dual": False}


def test_buyer_equal_claimer_rejected(client):
    wid = _create(client)
    r = _claim(client, wid, "alice", "alice")
    assert r.status_code == 400
    assert r.json()["detail"] == "buyer_equal_claimer"


# ---------- fulfill gate -------------------------------------------------

def test_outsider_cannot_fulfill(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "carol"})
    assert r.status_code == 403
    assert r.json()["detail"] == "not_party"
    # Still claimed by the original parties; carol pinned nowhere.
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "claimed"
    assert w["claimer"] == "alice" and w["buyer"] == "bob"


def test_empty_actor_cannot_fulfill(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    for payload in ({"actor": ""}, {}):
        r = client.post(f"/api/wishes/{wid}/fulfill", json=payload)
        assert r.status_code == 403
        assert r.json()["detail"] == "not_party"


def test_claimer_fulfill_pins_claimer_as_executor(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "alice"})
    assert r.status_code == 200
    w = r.json()
    assert w["status"] == "fulfilled"
    assert w["fulfilled_by"] == "alice"


def test_buyer_fulfill_pins_buyer_as_executor(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert r.status_code == 200
    w = r.json()
    assert w["status"] == "fulfilled"
    assert w["fulfilled_by"] == "bob"
    # Done page and wall carry the same pinned names via the same projection.
    done = client.get("/api/done").json()
    row = next(x for x in done if x["id"] == wid)
    assert row["fulfilled_by"] == "bob"
    assert row["parties"] == {"claimer": "alice", "buyer": "bob", "dual": True}
    wall = next(x for x in client.get("/api/wishes").json() if x["id"] == wid)
    assert wall["fulfilled_by"] == "bob"


# ---------- release clears buyer ----------------------------------------

def test_release_clears_claimer_and_buyer_everywhere(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "alice"})
    assert r.status_code == 200
    w = r.json()
    assert w["status"] == "released"
    assert w["claimer"] is None and w["buyer"] is None
    assert w["parties"]["dual"] is False
    # Wall projection agrees.
    wall = next(x for x in client.get("/api/wishes").json() if x["id"] == wid)
    assert wall["claimer"] is None and wall["buyer"] is None
    # Neither party sees it in mine.
    assert all(x["id"] != wid for x in client.get("/api/mine?actor=alice").json())
    assert all(x["id"] != wid for x in client.get("/api/mine?actor=bob").json())


def test_buyer_cannot_release(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "bob"})
    assert r.status_code == 403
    assert r.json()["detail"] == "not_claimer"


# ---------- transfer -----------------------------------------------------

def test_transfer_swaps_claimer_and_clears_buyer_atomically(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")
    r = client.post(
        f"/api/wishes/{wid}/transfer",
        json={"actor": "alice", "new_claimer": "carol"},
    )
    assert r.status_code == 200
    w = r.json()
    assert w["claimer"] == "carol"
    assert w["buyer"] is None
    assert w["parties"] == {"claimer": "carol", "buyer": None, "dual": False}

    # Old buyer no longer holds fulfill rights; new claimer does.
    old = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert old.status_code == 403 and old.json()["detail"] == "not_party"
    new = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "carol"})
    assert new.status_code == 200
    assert new.json()["fulfilled_by"] == "carol"


def test_failed_transfer_changes_nothing(client):
    wid = _create(client)
    _claim(client, wid, "alice", "bob")

    # Buyer can't transfer.
    r = client.post(
        f"/api/wishes/{wid}/transfer",
        json={"actor": "bob", "new_claimer": "carol"},
    )
    assert r.status_code == 403
    # Same-name transfer is rejected too.
    r2 = client.post(
        f"/api/wishes/{wid}/transfer",
        json={"actor": "alice", "new_claimer": "alice"},
    )
    assert r2.status_code == 400 and r2.json()["detail"] == "same_claimer"

    # Row untouched: alice + bob remain the single binding, bob can fulfill.
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["claimer"] == "alice" and w["buyer"] == "bob"
    ok = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert ok.status_code == 200 and ok.json()["fulfilled_by"] == "bob"


# ---------- mine + TTL ---------------------------------------------------

def test_mine_includes_claims_and_buyer_orders(client):
    mine_claim = _create(client, "a")
    mine_buy = _create(client, "b")
    _claim(client, mine_claim, "zoe", "yip")
    _claim(client, mine_buy, "xan", "zoe")
    rows = client.get("/api/mine?actor=zoe").json()
    ids = {x["id"] for x in rows}
    assert mine_claim in ids and mine_buy in ids


def test_ttl_sweep_clears_stale_buyer(client):
    c = connect()
    cur = c.execute(
        "INSERT INTO wishes(title,note,status,claimer,buyer,claimed_at,"
        "expires_at,data_quality) VALUES (?,?,?,?,?,?,?,?)",
        ("stale", "", "claimed", "ghost", "zombie",
         "2020-01-01T00:00:00+00:00", "2020-01-01T01:00:00+00:00", "dirty"),
    )
    wid = cur.lastrowid
    c.commit(); c.close()
    # Any read runs the lazy sweep.
    w = client.get(f"/api/wishes/{wid}").json()
    assert w["status"] == "open"
    assert w["claimer"] is None and w["buyer"] is None
