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


def make_owner_resolver(path: Path) -> Callable[[str], OwnerInfo]:
    owners = load_owners(path)

    def resolve(affected_system: str) -> OwnerInfo:
        info = owners.get(affected_system) or owners.get("default") or _FALLBACK
        return OwnerInfo(
            affected_system=affected_system,
            owner_name=info.get("owner_name", _FALLBACK["owner_name"]),
            owner_email=info.get("owner_email", _FALLBACK["owner_email"]),
            team=info.get("team", _FALLBACK["team"]),
        )

    return resolve
