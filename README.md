# monitoring-agent

[![CI](https://github.com/AlGnozis/monitoring-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/AlGnozis/monitoring-agent/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> **Status:** ✅ iteration-1 complete · готов к ревью · **License:** MIT · **Python:** 3.12 · **62 теста**

AI-агент мониторинга IT-инцидентов. Читает RSS-фид (или синтетический), триажит через **GigaChat** с structured output, обогащает через **RAG (E5 + FAISS)**, определяет владельца затронутой системы по `owners.yaml`, идемпотентно заводит mock-заявку и отправляет mock-письмо в `outbox/*.eml`. Полная observability через `loguru` + SQLite-аудит каждого шага.

Тестовое задание на позицию **Python-разработчик (AI-агент)** в Сбере.

> 🎥 **Demo (90 сек):** _ссылка добавится после записи_ — `docker compose up` → `build_kb` → `POST /trigger` → `outbox/demo-001.eml` + `audit.db`.

---

## Что демонстрирует проект

Сквозной сценарий, реализованный как `StateGraph` LangGraph — каждый узел наблюдаем в логе и аудите:

```
[пост в ленте] → [триаж: инцидент?] → [RAG: похожие случаи + runbook]
                                  ↓
[аудит в SQLite] ← [письмо владельцу] ← [mock-заявка] ← [определить владельца]
```

**Инженерные акценты, по которым проект отличается от типового pet-MVP:**

| Аспект | Где смотреть |
|---|---|
| **Идемпотентность (defense-in-depth)** | `event_hash = sha256(source_id + entry_id)` — проверяется и в `app/store/audit.py:is_processed`, и в `MockTicketAdapter` (unique constraint). Тест: `tests/test_graph.py::test_idempotent_repeat_does_not_duplicate`. |
| **Структурированный вывод GigaChat с учётом ограничений схемы** | Плоские Pydantic-модели в `app/state.py` (нет `anyOf`, всегда `items`/`properties`), плюс robust JSON fallback parser в `app/llm/schemas.py:parse_model`. |
| **Graceful degradation** | Пустой RAG → `context_empty=True` → `plan_action` формирует «недостаточно данных, требуется ручная проверка», граф доходит до DONE. Тест: `test_graceful_empty_context_still_completes`. |
| **Dependency Injection для тестируемости** | `app/graph/deps.py` + `wiring.py` позволяет в тестах подменять LLM/RAG/adapters callable-функциями. Граф запускается **реальный**, а не замоканный. |
| **Production-ready форма адаптеров (Protocol)** | `TicketAdapter` / `NotifyAdapter` — PEP 544 структурные протоколы. Real-реализация добавляется в iteration-2 без рефакторинга. |
| **Переиспользование боевых паттернов AI-Factory с обоснованием каждого** | См. [`docs/REUSED-FROM-AI-FACTORY.md`](docs/REUSED-FROM-AI-FACTORY.md) — таблица с явным «что взяли» / «что НЕ взяли и почему». |
| **Унифицированный JSON-формат ошибок** | `{"error": "<code>", "message": "<msg>"}` через единый `_error()` helper + global exception handlers в `app/api/server.py`. |
| **Поведенческая дисциплина в коде** | См. [`CLAUDE.md`](CLAUDE.md) § Behavioral defaults — 4 принципа Karpathy применяются на каждой задаче. Пример: `gigachat_client.py` — 30 строк без ручного Lock-кэша, потому что `langchain_gigachat` сам рефрешит токен. |

---

## Быстрый старт (3 минуты)

```bash
# 1. Клонировать
git clone https://github.com/AlGnozis/monitoring-agent.git
cd monitoring-agent

# 2. Скопировать env и заполнить GigaChat credentials
cp .env.example .env
# отредактировать .env: GIGACHAT_AUTH_KEY=..., GIGACHAT_SCOPE=GIGACHAT_API_PERS

# 3. Поднять (agent + embedding-service)
docker compose up -d

# 4. Собрать базу знаний (runbooks + past_incidents → FAISS index)
docker compose exec agent python -m app.rag.build_kb
# ожидаем: data/kb/index.faiss создан, N документов проиндексировано

# 5. Прогнать e2e (детерминированный fake-feed)
curl -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"entry_id": "demo-001"}'

# 6. Проверить артефакты (audit.db/tickets.db — ВНУТРИ контейнера, не в volume; смотрим через API/exec)
ls outbox/                                    # demo-001.eml на хосте (volume смонтирован)
curl -s localhost:8000/audit | jq             # аудит: status, ticket_id, owner_email, tokens_total
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select ticket_id,severity from tickets').fetchall())"

# 7. Идемпотентность — повтор не плодит дублей
curl -X POST localhost:8000/trigger -d '{"entry_id": "demo-001"}'
ls outbox/ | wc -l                                    # = 1
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select count(*) from tickets').fetchone()[0])"   # = 1
```

**Ожидаемый результат шага 5:** `{"status": "DONE", "event_hash": "<hash>", "ticket_id": "DEMO-001"}` за ≤ 30 секунд. Письмо в `outbox/demo-001.eml`, заявка в `tickets.db`, аудит-строка в `audit.db`.

Подробные acceptance criteria — [`docs/iteration-1.md` § Acceptance criteria](docs/iteration-1.md).

---

## Тесты

```bash
pytest -q              # 62 теста, ~5–10 сек на CI
ruff check . && ruff format --check .
mypy app/
```

Покрытие по слоям:

| Уровень | Тесты | Файлы |
|---|---|---|
| **Контракты данных** | 18 | `test_state.py`, `test_schemas.py`, `test_config.py`, `test_owners.py` |
| **Хранилища / адаптеры** | 11 | `test_audit.py`, `test_adapters.py` |
| **LLM / RAG** | 14 | `test_gigachat_client.py`, `test_prompts.py`, `test_embeddings.py`, `test_rag.py` |
| **Ingest** | 4 | `test_sources.py`, `test_poller.py` |
| **Граф (полный e2e через DI)** | 4 | `test_graph.py` — happy path / drop / **idempotency** / **graceful empty context** |
| **API + интеграция** | 6 | `test_api.py` (TestClient + monkeypatched deps) |
| **Прочее** | 5 | `test_data.py`, `test_logger.py` |
| **ИТОГО** | **62** | mypy strict, ruff clean, CI green |

**LLM-уровень в тестах** — `@pytest.mark.mock_llm`: реальный GigaChat не вызывается (нет секретов в CI). E2E против реального GigaChat — на стороне ревьюера: `docker compose up` + `.env` с креденшалами.

---

## Документация

| Файл | О чём |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Операционка проекта: стек, инварианты, команды, anti-patterns, **Behavioral defaults** (Karpathy) |
| [`docs/product-vision.md`](docs/product-vision.md) | Продуктовая постановка: проблема, метрика успеха, anti-goals, риски |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Полный архитектурный план: узлы графа, переиспользование из AI-Factory, контракты данных |
| [`docs/iteration-1.md`](docs/iteration-1.md) | Текущая итерация: scope, acceptance criteria, anti-scope |
| [`docs/REUSED-FROM-AI-FACTORY.md`](docs/REUSED-FROM-AI-FACTORY.md) | Реестр адаптированных паттернов: что взято, что НЕ взято и почему |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Onboarding-документ для AI-агента разработки (универсальный стартовый промпт) |

---

## Стек

- **Python 3.12** · **FastAPI** · **Pydantic v2** · **SQLModel**
- **LangGraph** — оркестрация state-machine с явными узлами и conditional edges
- **GigaChat** (`langchain_gigachat`) — LLM (триаж + plan со structured output)
- **FAISS + E5** (`intfloat/e5-small-v2`) — RAG retriever через standalone `embedding-service`
- **SQLite** — аудит (`audit.db`) + mock-Jira (`tickets.db`)
- **Docker Compose** — `agent` + `embedding-service` (+ опц. `mailhog` для iteration-2)
- **loguru** + единая обёртка `log_info(msg, component, action, ctx)` — observability

---

## Структура

```
monitoring-agent/
├── app/                       # код агента
│   ├── api/server.py          # FastAPI: /trigger /health /audit
│   ├── graph/                 # LangGraph: 8 узлов + build + DI
│   ├── llm/                   # GigaChat фабрика + schemas + prompts
│   ├── rag/                   # E5 embeddings + FAISS vectorize/retriever
│   ├── ingest/                # FakeSource + RSS poller
│   ├── adapters/              # Protocol + MockTicket / MockNotify
│   ├── store/audit.py         # SQLite + идемпотентность
│   ├── state.py               # MonitorState + EventRecord + enums
│   ├── config.py              # pydantic-settings
│   └── logger.py              # loguru-обёртка
├── data/
│   ├── knowledge/             # 5 runbooks/past_incidents → KB
│   ├── owners.yaml            # affected_system → owner mapping
│   └── fake_feed.json         # детерминированный фид «Сбер-like»
├── embedding-service/         # standalone E5 (FastAPI, Docker)
├── docs/                      # vision, architecture, iteration, reused, handoff
├── tests/                     # 62 теста
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml             # ruff / mypy / pytest конфиги
└── CLAUDE.md                  # ← операционка проекта (читается AI-агентами)
```

---

## Roadmap — iteration-2 (опционально, после ревью)

Из anti-scope iteration-1 — что можно добавить в следующей итерации:

- 🔌 **Реальный Jira-адаптер** через `ADAPTERS=real` (jira-python + WebHook)
- 📧 **Реальный SMTP** или **Mailhog** в `docker-compose.yml`
- 📡 **Живой RSS** через `SOURCE=rss` + `feedparser` (адаптер уже готов)
- 🚦 **`human_gate`** для high-severity (insertion point в графе уже есть)
- 📊 **RAGAS eval** через extra `[eval]` — `python evals/ragas_eval.py`
- 🎯 **Agent eval** на размеченном наборе — precision триажа + маршрутизация владельцу
- 🔄 **Live RSS auto-start** в daemon-треде (сейчас доступен только через явный вызов)

---

## Разработка

Проект разработан с использованием **AI coding pipeline** (см. [`CLAUDE.md`](CLAUDE.md) § Behavioral defaults — 4 принципа Karpathy). Каждая задача — атомарный conventional commit (`feat:` / `fix:` / `docs:` / `chore:` / `refactor:` / `test:`), линейная git-история.

CI на GitHub Actions: `ruff check` + `ruff format --check` + `mypy` + `pytest -q` на push и PR в `main`. См. [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## License

MIT — см. [`LICENSE`](LICENSE).
