"""Binding module: normalize/validate claimer & buyer names (pure functions)."""
import unicodedata

MAX_NAME_LEN = 32


class BindingError(Exception):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def normalize_name(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.strip()


def has_control_char(s: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in s)


def clean_claimer(raw: str | None) -> str:
    """Validate the claimer name; pure whitespace counts as 'not provided'."""
    norm = normalize_name(raw)
    if norm == "":
        raise BindingError("claimer_empty")
    if has_control_char(norm) or len(norm) > MAX_NAME_LEN:
        raise BindingError("claimer_dirty")
    return norm


def clean_buyer(raw: str | None, claimer: str) -> str | None:
    """Validate the optional buyer name.

    Missing field or empty string means 'no buyer' (degrade to claimer-only).
    A non-empty value that strips to empty is dirty. Must differ from claimer.
    """
    if raw is None or raw == "":
        return None
    norm = raw.strip()
    if norm == "":
        raise BindingError("buyer_dirty")
    if has_control_char(norm) or len(norm) > MAX_NAME_LEN:
        raise BindingError("buyer_dirty")
    if norm == claimer:
        raise BindingError("buyer_equal_claimer")
    return norm


def bind_parties(claimer_raw: str | None, buyer_raw: str | None) -> tuple[str, str | None]:
    claimer = clean_claimer(claimer_raw)
    buyer = clean_buyer(buyer_raw, claimer)
    return claimer, buyer


def clean_new_claimer(raw: str | None, current_claimer: str) -> str:
    """Validate the incoming claimer for a transfer."""
    new_one = clean_claimer(raw)
    if new_one == current_claimer:
        raise BindingError("same_claimer")
    return new_one
