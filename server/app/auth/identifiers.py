"""Account identifier policy and normalization.

The account identifier is a **username**, not an email address. Reasons,
recorded so the choice is reviewable:

* Email addresses are personal data the system does not otherwise need
  (`PRIVACY-001` - minimize collection).
* A trustworthy email identifier requires verification infrastructure this
  project does not have, and an unverified email is a weaker identifier than
  a username while carrying more privacy risk.
* Password recovery is out of scope for v1 (see docs/AUTHENTICATION.md), so
  the usual argument for collecting email does not apply.

Normalization is NFKC + casefold, so `Alice`, `alice`, and a full-width
variant of the same letters all resolve to one account and cannot be
registered separately. The permitted
character set is deliberately narrow, which rules out the mixed-script
homograph tricks that make lookalike impersonation possible.
"""

from __future__ import annotations

import re
import unicodedata

#: Post-normalization identifier shape: lowercase ASCII alphanumerics plus
#: dash, underscore and dot, starting with an alphanumeric.
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32


class InvalidUsernameError(Exception):
    """Raised when a candidate identifier violates policy.

    The reason describes the policy, never anything sensitive.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalize_username(raw: str) -> str:
    """Normalize an identifier to its canonical, comparable form.

    NFKC folds compatibility variants (full-width characters, ligatures) and
    casefold handles case beyond simple ASCII lowering. Both run before
    validation so the pattern check applies to the form actually stored.
    """
    return unicodedata.normalize("NFKC", raw).strip().casefold()


def validate_username(raw: str) -> str:
    """Validate and normalize an identifier, or raise `InvalidUsernameError`."""
    if not raw or not raw.strip():
        msg = "username must not be empty"
        raise InvalidUsernameError(msg)

    normalized = normalize_username(raw)

    if len(normalized) < MIN_USERNAME_LENGTH:
        msg = f"username must be at least {MIN_USERNAME_LENGTH} characters"
        raise InvalidUsernameError(msg)
    if len(normalized) > MAX_USERNAME_LENGTH:
        msg = f"username must be at most {MAX_USERNAME_LENGTH} characters"
        raise InvalidUsernameError(msg)

    if not USERNAME_PATTERN.fullmatch(normalized):
        msg = (
            "username may contain only lowercase letters, digits, dot, dash and "
            "underscore, and must start with a letter or digit"
        )
        raise InvalidUsernameError(msg)

    return normalized


def is_valid_username(raw: str) -> bool:
    """Whether an identifier satisfies policy."""
    try:
        validate_username(raw)
    except InvalidUsernameError:
        return False
    return True
