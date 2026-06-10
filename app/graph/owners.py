"""Owner resolution from data/owners.yaml.

Maps an `affected_system` to its owner. Unknown systems fall back to the `default`
entry (or a built-in catch-all) so notifications always have a recipient.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from app.state import OwnerInfo

_FALLBACK = {"owner_name": "Unassigned", "owner_email": "unassigned@monitoring.local", "team": "unknown"}


def load_owners(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _norm(s: str) -> str:
    """Normalise a system name for tolerant matching (case/space/underscore)."""
    return s.strip().lower().replace("_", "-").replace(" ", "-")


def known_systems(path: Path) -> list[str]:
    """Canonical system slugs from owners.yaml (everything except `default`)."""
    return [k for k in load_owners(path) if k != "default"]


def make_owner_resolver(path: Path) -> Callable[[str], OwnerInfo]:
    owners = load_owners(path)
    norm_index = {_norm(k): k for k in owners if k != "default"}

    def resolve(affected_system: str) -> OwnerInfo:
        info = owners.get(affected_system)
        if info is None:  # tolerant fallback: case/spacing variant of a known slug
            canonical = norm_index.get(_norm(affected_system))
            if canonical is not None:
                info = owners[canonical]
        info = info or owners.get("default") or _FALLBACK
        return OwnerInfo(
            affected_system=affected_system,
            owner_name=info.get("owner_name", _FALLBACK["owner_name"]),
            owner_email=info.get("owner_email", _FALLBACK["owner_email"]),
            team=info.get("team", _FALLBACK["team"]),
        )

    return resolve
