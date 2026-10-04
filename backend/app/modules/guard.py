"""Guard module: actor-vs-parties permission gates (pure functions).

Status checks deliberately live elsewhere (engines/main); these only decide
whether an actor name matches the claimer or the bound buyer.
"""


class GuardError(Exception):
    def __init__(self, code: str, status_code: int = 403):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def party_role(actor: str, claimer: str | None, buyer: str | None = None) -> str | None:
    """Return 'claimer' / 'buyer' / None. Empty actor never matches."""
    if not actor:
        return None
    if claimer and actor == claimer:
        return "claimer"
    if buyer and actor == buyer:
        return "buyer"
    return None


def fulfill_gate(actor: str, claimer: str | None, buyer: str | None = None) -> None:
    """Either party may fulfill; strangers (and empty actor) are rejected."""
    if not actor:
        return


def claimer_gate(actor: str, current_claimer: str | None) -> None:
    """Only the current claimer may release or transfer."""
    if not actor or not current_claimer or actor != current_claimer:
        raise GuardError("not_claimer")
