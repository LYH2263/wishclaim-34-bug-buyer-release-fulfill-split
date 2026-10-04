"""Party-split acceptance tests: fulfill permission, buyer cleanup, projections.

Decisions under test (see /api/rules):
- fulfill_gate: only the claimer or the bound buyer may fulfill; strangers 403.
- release / transfer / TTL-sweep all clear the buyer column in the same write.
- wall list, detail, mine and done all project the same pair of names.
- a dirty buyer fails the whole claim; nothing is written as a placeholder.
- a failed transfer changes nothing: no double booking of fulfill rights.
"""

ZERO_WIDTH = "​"  # zero-width space: renders as an empty name


def mk_wish(client, title="T"):
    return client.post("/api/wishes", json={"title": title, "note": ""}).json()["id"]


def claim(client, wid, claimer="alice", buyer="bob"):
    return client.post(f"/api/wishes/{wid}/claim", json={"claimer": claimer, "buyer": buyer})


def detail(client, wid):
    return client.get(f"/api/wishes/{wid}").json()


def wall_row(client, wid):
    return next(w for w in client.get("/api/wishes").json() if w["id"] == wid)


# --- fulfill permission: claimer + buyer, nobody else ------------------------

def test_stranger_cannot_fulfill(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "mallory"})
    assert r.status_code == 403 and r.json()["detail"] == "not_party"
    w = detail(client, wid)
    assert w["status"] == "claimed"  # stranger's attempt changed nothing


def test_empty_actor_cannot_fulfill(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "  "})
    assert r.status_code == 403 and r.json()["detail"] == "not_party"


def test_claimer_can_fulfill_and_done_pins_pair(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "alice"})
    assert r.status_code == 200
    done = client.get("/api/done").json()
    row = next(w for w in done if w["id"] == wid)
    # The pinned pair is the executor's pair — the same names the gate checked.
    assert row["parties"] == {"claimer": "alice", "buyer": "bob", "dual": True}


def test_buyer_can_fulfill(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert r.status_code == 200
    assert detail(client, wid)["status"] == "fulfilled"


# --- release clears the buyer everywhere at once -----------------------------

def test_release_clears_buyer_in_all_projections(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "alice"})
    assert r.status_code == 200
    for proj in (detail(client, wid), wall_row(client, wid)):
        assert proj["status"] == "released"
        assert proj["claimer"] is None and proj["buyer"] is None
        assert proj["parties"] == {"claimer": None, "buyer": None, "dual": False}
    # Mine no longer lists it for either party.
    assert all(w["id"] != wid for w in client.get("/api/mine", params={"actor": "alice"}).json())


def test_reclaim_after_release_has_no_zombie_buyer(client):
    wid = mk_wish(client)
    claim(client, wid)
    client.post("/api/wishes/{}/release".format(wid), json={"actor": "alice"})
    claim(client, wid, claimer="carol", buyer=None)
    w = detail(client, wid)
    assert w["claimer"] == "carol" and w["buyer"] is None
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"})
    assert r.status_code == 403  # the released buyer holds no rights


def test_release_requires_claimer(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/release", json={"actor": "bob"})
    assert r.status_code == 403 and r.json()["detail"] == "not_claimer"


# --- transfer: atomic swap, buyer cleared, no double booking -----------------

def test_transfer_swaps_claimer_and_clears_buyer(client):
    wid = mk_wish(client)
    claim(client, wid)
    r = client.post(f"/api/wishes/{wid}/transfer", json={"actor": "alice", "new_claimer": "carol"})
    assert r.status_code == 200
    for proj in (detail(client, wid), wall_row(client, wid)):
        assert proj["claimer"] == "carol" and proj["buyer"] is None
        assert proj["parties"] == {"claimer": "carol", "buyer": None, "dual": False}
    mine_carol = client.get("/api/mine", params={"actor": "carol"}).json()
    assert [w["id"] for w in mine_carol] == [wid]
    assert mine_carol[0]["buyer"] is None
    assert all(w["id"] != wid for w in client.get("/api/mine", params={"actor": "alice"}).json())


def test_transfer_revokes_old_parties(client):
    wid = mk_wish(client)
    claim(client, wid)
    client.post(f"/api/wishes/{wid}/transfer", json={"actor": "alice", "new_claimer": "carol"})
    for actor in ("alice", "bob"):  # old claimer and old buyer both lost fulfill rights
        r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": actor})
        assert r.status_code == 403 and r.json()["detail"] == "not_party"
    assert detail(client, wid)["status"] == "claimed"
    r = client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "carol"})
    assert r.status_code == 200


def test_failed_transfer_changes_nothing(client):
    wid = mk_wish(client)
    claim(client, wid)
    for body in (
        {"actor": "mallory", "new_claimer": "carol"},  # not the claimer
        {"actor": "alice", "new_claimer": "alice"},    # same as current
        {"actor": "alice", "new_claimer": ZERO_WIDTH},  # dirty name
    ):
        r = client.post(f"/api/wishes/{wid}/transfer", json=body)
        assert r.status_code in (400, 403)
        w = detail(client, wid)
        assert w["claimer"] == "alice" and w["buyer"] == "bob"
    # No half-applied state: old parties keep their rights, new person has none.
    assert client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "carol"}).status_code == 403
    assert client.post(f"/api/wishes/{wid}/fulfill", json={"actor": "bob"}).status_code == 200


# --- dirty buyer: claim fails, no empty-name placeholder ---------------------

def test_dirty_buyer_fails_claim(client):
    for bad in ("   ", ZERO_WIDTH, "a\x01b", "x" * 33, "alice"):
        wid = mk_wish(client)
        r = claim(client, wid, claimer="alice", buyer=bad)
        assert r.status_code == 400, bad
        w = detail(client, wid)
        # The whole claim failed: no lock, and no placeholder buyer written.
        assert w["status"] == "open" and w["claimer"] is None and w["buyer"] is None


def test_blank_buyer_means_no_buyer(client):
    wid = mk_wish(client)
    for body in ({"claimer": "alice"}, {"claimer": "alice", "buyer": ""}, {"claimer": "alice", "buyer": None}):
        r = client.post(f"/api/wishes/{wid}/claim", json=body)
        if r.status_code == 200:
            break
    assert r.status_code == 200
    w = detail(client, wid)
    assert w["buyer"] is None and w["parties"]["dual"] is False


def test_dirty_claimer_fails(client):
    wid = mk_wish(client)
    r = client.post(f"/api/wishes/{wid}/claim", json={"claimer": ZERO_WIDTH})
    assert r.status_code == 400 and r.json()["detail"] == "claimer_dirty"


# --- TTL sweep clears the buyer too (seeded expired lock) --------------------

def test_ttl_sweep_clears_buyer(client):
    # Seed row 4 is an expired lock held by ghost/zombie.
    row = wall_row(client, 4)
    assert row["status"] == "open"
    assert row["claimer"] is None and row["buyer"] is None
    assert row["parties"] == {"claimer": None, "buyer": None, "dual": False}
    assert detail(client, 4)["buyer"] is None


# --- wall and detail never disagree ------------------------------------------

def test_wall_and_detail_project_same_parties(client):
    ids = [mk_wish(client) for _ in range(3)]
    claim(client, ids[0])                                  # claimed, dual
    claim(client, ids[1]); client.post(f"/api/wishes/{ids[1]}/release", json={"actor": "alice"})
    claim(client, ids[2]); client.post(f"/api/wishes/{ids[2]}/fulfill", json={"actor": "bob"})
    wall = {w["id"]: w for w in client.get("/api/wishes").json()}
    for wid in ids:
        assert wall[wid]["parties"] == detail(client, wid)["parties"]
        assert wall[wid]["claimer"] == detail(client, wid)["claimer"]
        assert wall[wid]["buyer"] == detail(client, wid)["buyer"]
