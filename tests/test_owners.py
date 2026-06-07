"""Unit tests for app.graph.owners (owner resolution + fallback)."""

from pathlib import Path

from app.graph.owners import make_owner_resolver

_YAML = """
payment-gateway:
  owner_name: Иван Петров
  owner_email: ivan@bank.local
  team: payments
default:
  owner_name: Дежурный
  owner_email: duty@bank.local
  team: ops
"""


def _owners_file(tmp_path: Path) -> Path:
    path = tmp_path / "owners.yaml"
    path.write_text(_YAML, encoding="utf-8")
    return path


def test_exact_match(tmp_path: Path) -> None:
    resolve = make_owner_resolver(_owners_file(tmp_path))
    owner = resolve("payment-gateway")
    assert owner.owner_email == "ivan@bank.local"
    assert owner.team == "payments"


def test_unknown_system_falls_back_to_default(tmp_path: Path) -> None:
    resolve = make_owner_resolver(_owners_file(tmp_path))
    owner = resolve("some-unknown-system")
    assert owner.owner_email == "duty@bank.local"
    assert owner.affected_system == "some-unknown-system"


def test_no_default_uses_builtin_fallback(tmp_path: Path) -> None:
    path = tmp_path / "owners.yaml"
    path.write_text("payment-gateway:\n  owner_email: x@y\n", encoding="utf-8")
    resolve = make_owner_resolver(path)
    owner = resolve("nope")
    assert owner.owner_email == "unassigned@monitoring.local"
