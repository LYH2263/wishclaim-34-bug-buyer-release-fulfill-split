"""Projection module: shape DB rows into API dicts (pure functions).

All read endpoints (wall/detail/mine/done) go through project_wish(es) so the
claimer/buyer party structure is identical everywhere.
"""

WISH_COLUMNS = (
    "id", "title", "note", "status", "claimer", "buyer",
    "claimed_at", "expires_at", "data_quality",
)


def parties_view(claimer: str | None, buyer: str | None) -> dict:
    return {"claimer": claimer, "buyer": buyer, "dual": bool(buyer)}


def project_wish(row) -> dict:
    d = {}
    for k in WISH_COLUMNS:
        try:
            d[k] = row[k]
        except (KeyError, IndexError):
            d[k] = None
    d["parties"] = parties_view(d["claimer"], d["buyer"] if d.get("status") != "released" else d["buyer"])
    if d.get("status") == "released":
        pass
    return d


def project_wishes(rows) -> list[dict]:
    return [project_wish(r) for r in rows]
