"""Unit tests for the pure modules behind the party-split rules."""
import pytest

from app.modules.binding import BindingError, bind_parties, clean_buyer
from app.modules.guard import GuardError, fulfill_gate, party_role
from app.modules.projection import project_wish


# --- guard: the fulfill permission decision ----------------------------------

def test_party_role_matches_claimer_then_buyer():
    assert party_role("alice", "alice", "bob") == "claimer"
    assert party_role("bob", "alice", "bob") == "buyer"
    assert party_role("mallory", "alice", "bob") is None
    assert party_role("", "alice", "bob") is None
    assert party_role("alice", None, None) is None


def test_fulfill_gate_allows_either_party_only():
    fulfill_gate("alice", "alice", "bob")
    fulfill_gate("bob", "alice", "bob")
    for actor in ("mallory", "", None):
        with pytest.raises(GuardError) as e:
            fulfill_gate(actor, "alice", "bob")
        assert e.value.code == "not_party"


# --- binding: dirty buyer never becomes an empty-name placeholder ------------

def test_clean_buyer_rejects_invisible_and_dirty_names():
    for bad in ("   ", "​", "​a", "a\x07", "x" * 33):
        with pytest.raises(BindingError) as e:
            clean_buyer(bad, "alice")
        assert e.value.code == "buyer_dirty"


def test_clean_buyer_blank_means_absent():
    assert clean_buyer(None, "alice") is None
    assert clean_buyer("", "alice") is None


def test_bind_parties_rejects_buyer_equal_claimer():
    with pytest.raises(BindingError) as e:
        bind_parties("alice", "alice")
    assert e.value.code == "buyer_equal_claimer"


# --- projection: names only for claimed/fulfilled ----------------------------

def test_projection_hides_parties_outside_active_statuses():
    row = {"id": 1, "title": "t", "note": "", "status": "released",
           "claimer": "ghost", "buyer": "zombie", "claimed_at": None,
           "expires_at": None, "data_quality": "clean"}
    d = project_wish(row)
    assert d["claimer"] is None and d["buyer"] is None
    assert d["parties"] == {"claimer": None, "buyer": None, "dual": False}


def test_projection_pins_pair_for_claimed_and_fulfilled():
    for status in ("claimed", "fulfilled"):
        row = {"id": 1, "title": "t", "note": "", "status": status,
               "claimer": "alice", "buyer": "bob", "claimed_at": "x",
               "expires_at": "y", "data_quality": "clean"}
        d = project_wish(row)
        assert d["parties"] == {"claimer": "alice", "buyer": "bob", "dual": True}
