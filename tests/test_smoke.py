"""Smoke test: проверяет, что пакет app импортируется и pytest-проект валиден.

Заменяется реальными тестами в следующих задачах iteration-1
(test_triage, test_idempotency, test_adapters, test_graph_e2e).
"""

import importlib


def test_app_package_importable() -> None:
    assert importlib.import_module("app") is not None
