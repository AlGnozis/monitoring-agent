# Iteration 1 — MVP: полный e2e до зелёного demo

> Продуктовый контекст — `docs/product-vision.md`. Архитектура — `docs/ARCHITECTURE.md`. Операционка — `CLAUDE.md`.

## Цель итерации

Реализовать **полный e2e-сценарий** монитор-агента от ingest до письма в `outbox/`, чтобы `docker compose up` + один `POST /trigger` приводил к зелёному прогону за ≤ 30 секунд **с идемпотентной обработкой повторов**. После этой итерации проект готов к публикации на GitHub и demo-видео.

## Метрика успеха

> **Единственный observable factum «итерация-1 готова»:**
>
> На чистой машине после `docker compose up`:
> ```bash
> curl -X POST localhost:8000/trigger -d '{"entry_id": "demo-001"}'
> # Ожидаем: HTTP 200, {"status": "DONE", "ticket_id": "DEMO-001", "event_hash": "..."}
> ```
> приводит к:
> 1. **1 строка** в `audit.db` (`EventRecord.status = DONE`),
> 2. **1 ticket** `DEMO-001` в `tickets.db` (mock-Jira; схема `DEMO-{seq:03d}`, первый = `DEMO-001`),
> 3. **1 файл** `outbox/demo-001.eml` с письмом владельцу из `owners.yaml`,
> 4. Повторный тот же `POST` возвращает 200 с тем же `event_hash` и **не создаёт** новых ticket/eml.
>
> Время от `POST` до DONE — **≤ 30 секунд** на cold-cache, **≤ 5 секунд** на warm-cache.

## Scope (что входит в итерацию)

> **Status:** ✅ **iteration-1 complete** — все 13 задач выполнены, CI green, 62 теста зелёных. Сводка коммитов — в § Done ниже.

| Модуль | Что реализовано | Status |
|---|---|---|
| `app/config.py` | pydantic-settings: GigaChat creds, scope, ADAPTERS, SOURCE, KB_PATH, embedding URL | ✅ |
| `app/state.py` | `MonitorState`, `EventRecord`, enums `Severity` (5), `Status`, `compute_event_hash` | ✅ |
| `app/llm/` | `gigachat_client.py` (тонкая фабрика, встроенный refresh), `prompts.py`, `schemas.py` (re-export + parse_model fallback) | ✅ |
| `app/rag/` | `embeddings.py` (E5 + `passage:/query:`), `vectorize.py` (chunk 512/50), `retriever.py`, `build_kb.py` (CLI) | ✅ |
| `app/ingest/` | `sources.py` (`FakeSource` + `RssSource`), `rss_poller.py` (daemon-ready, не auto-start) | ✅ |
| `app/adapters/` | `TicketAdapter`/`NotifyAdapter` (Protocol), `MockTicketAdapter` + `MockNotifyAdapter`, `factory.py` | ✅ |
| `app/store/audit.py` | SQLite-аудит + `is_processed(event_hash)` + `save/get/list_records` | ✅ |
| `app/graph/` | 8 узлов + `build.py` (`recursion_limit=10`, conditional edges) + `deps.py` (DI) + `wiring.py` | ✅ |
| `app/api/server.py` | FastAPI: `POST /trigger`, `GET /health`, `GET /audit`, `GET /audit/{event_hash}` + единый JSON-формат ошибок | ✅ |
| `app/logger.py` | loguru-обёртка `log_info/warn/error(msg, component, action, ctx)` + escape `{{}}` | ✅ |
| `data/owners.yaml` | 5 систем «Сбер-like» с владельцами | ✅ |
| `data/fake_feed.json` | детерминированный фид (3 инцидента + шум + маркетинг) | ✅ |
| `data/knowledge/` | 5 markdown (4 runbooks + 1 past_incident) для KB | ✅ |
| `docker-compose.yml` + `Dockerfile` + `embedding-service/` | `agent` + `embedding-service` (FastAPI на E5), healthcheck, volumes | ✅ |
| **Инфраструктура GitHub** | `LICENSE` (MIT), `.gitignore`, `README.md` (RU + бейджи), `.github/workflows/ci.yml` (ruff + format + mypy + pytest) | ✅ |
| **Тесты** | 62 теста в 16 файлах: контракты (18), хранилища/адаптеры (11), LLM/RAG (14), ingest (4), граф (4), API (6), прочее (5) | ✅ |

## Done — сводка ключевых коммитов

| Task | Commit | Описание |
|---|---|---|
| 1 | `2f5d4d9` | `chore: project skeleton (pyproject, package structure, .env.example)` |
| 2 | `418d3a4` | `feat(state): MonitorState + EventRecord + enums` |
| 3 | `5cf7b1f` | `feat(config): pydantic-settings` |
| 4 | `89be97f` | `feat(llm): фабрика GigaChat (refresh на стороне библиотеки)` |
| 5 | `f18bee8` | `feat(llm): structured output schemas + prompts` |
| 6 | `57ce537` | `feat(rag): E5 embeddings + vectorize + retriever + build_kb` |
| 7 | `8953f75` | `feat(store): SQLite audit + идемпотентность по event_hash` |
| 8 | `5352904` | `feat(adapters): Protocol + mock ticket/notify + factory` |
| 9 | `ed1302e` | `feat(ingest): FakeSource + RSS-адаптер + feed poller` |
| 10 | `078f936` | `feat(graph): LangGraph 8 узлов + сборка + идемпотентность` |
| 11 | `2f171eb` | `feat(api): FastAPI /trigger /health /audit` |
| 12 | `1ec4684` | `feat(data): owners.yaml + fake_feed.json + база знаний` |
| 13 | `ceba3cf` | `feat(docker): compose + Dockerfile агента + embedding-service` |

Плюс docs-sweep `034cfee` (token-cache + cleanup, см. retrospective). Всего по iteration-1 — 14 feat/chore commits + 4 docs/fix. История линейная, conventional.

## Anti-scope (что НЕ входит — отложено или никогда)

> Базовый anti-scope — в `docs/product-vision.md`. Здесь — уточнения уровня итерации.

**Отложено в iteration-2+:**
- `human_gate` для high-severity (узел в графе предусмотрен, но всегда `False` в этой итерации)
- Живой RSS-источник через `feedparser` (есть только адаптер, активного использования нет)
- `agent_eval.py` (полноценный eval-набор) — задел на itera-2
- `ragas_eval.py` (BONUS-фича) — в `evals/` создаём заглушку с TODO
- Mailhog — `docker-compose.yml` оставляет как закомментированный профиль

**Никогда в этом проекте:**
- Реальные интеграции (Jira REST, SMTP)
- UI / админка
- Multi-tenant / auth
- Реальные данные Сбера

## Архитектурный набросок

Подробно — `docs/ARCHITECTURE.md`. Здесь — пятистрочная сводка:

- **Граф**: `ingest → triage → enrich_rag → resolve_owner → plan_action → act_ticket → act_notify → persist_audit`.
- **Внешний сервис**: `embedding-service` (E5) поднимается рядом в `docker-compose.yml`.
- **Идемпотентность**: проверка `event_hash` в `audit.db` перед `act_ticket` и `act_notify`.
- **Mock через `Protocol`**: реальная Jira/SMTP — не реализуется, но интерфейс готов.
- **Структуры данных**: `MonitorState` (Pydantic) протекает через граф; `EventRecord` фиксируется в SQLite в конце.

## Сущности (минимум для итерации)

| Сущность | Поля | Источник данных |
|---|---|---|
| `MonitorState` | `raw_entry`, `event_hash`, `triage`, `rag_context`, `owner`, `action_plan`, `ticket_id`, `notified`, `status`, `timings`, `tokens` | runtime (in-memory через граф) |
| `EventRecord` | `event_hash` (PK), `status` (Status enum), `ticket_id`, `owner_email`, `notified_at`, `created_at`, `timings_json`, `tokens_total` | `audit.db` (SQLite) |
| `TriageOutput` | `is_incident: bool`, `severity: Severity`, `topic: str`, `affected_system: str` | GigaChat structured output |
| `PlanOutput` | `summary: str`, `recommendations: list[str]`, `escalate_to: str` | GigaChat structured output |
| `Owner` | `affected_system → {owner_name, owner_email, team}` | `data/owners.yaml` (static) |
| `Ticket` (mock) | `ticket_id`, `event_hash`, `summary`, `severity`, `created_at` | `tickets.db` (SQLite через `MockTicketAdapter`) |
| `FeedEntry` | `entry_id`, `title`, `body`, `published_at`, `source` | `data/fake_feed.json` |

## Эндпоинты (контракты API)

| Method | Path | Запрос | Ответ (200) | Ответ (ошибка) |
|---|---|---|---|---|
| POST | `/trigger` | `{"entry_id": "demo-001"}` | `{"status": "DONE", "event_hash": "...", "ticket_id": "DEMO-001"}` | 404 `{"error": "entry_not_found"}`, 422 `{"error": "validation"}` |
| GET | `/health` | — | `{"status": "ok", "embedding_service": "ok"}` | 503 `{"error": "embedding_service_down"}` |
| GET | `/audit?limit=20` | query | `{"records": [...], "total": N}` | — |
| GET | `/audit/{event_hash}` | — | `{"event_hash":..., "status":..., "ticket_id":..., "owner_email":..., "timings":...}` | 404 `{"error": "not_found"}` |

> Все ответы — JSON. Ошибки — формат `{"error": "<code>", "message": "<msg>"}` (см. CLAUDE.md § Invariants).

## Acceptance criteria

> Каждый пункт — **исполняемая команда** или **observable behavior**. Критерий итерации = все 8 зелёные.

1. **Контейнеры поднимаются:**
   ```bash
   docker compose up -d && sleep 10 && docker compose ps
   # ожидаем: agent + embedding-service оба "Up"
   ```
2. **Healthcheck зелёный:**
   ```bash
   curl -fsS localhost:8000/health  # 200 + {"status":"ok","embedding_service":"ok"}
   ```
3. **KB собирается:**
   ```bash
   docker compose exec agent python -m app.rag.build_kb
   # ожидаем: создан data/kb/index.faiss + nonzero N документов в логе
   ```
4. **`POST /trigger` зелёный e2e:**
   ```bash
   curl -X POST localhost:8000/trigger -d '{"entry_id":"demo-001"}'
   # 200 + status=DONE, ticket_id присвоен
   ```
5. **Артефакты на диске:**
   ```bash
   ls outbox/demo-001.eml && curl -s localhost:8000/audit | jq '.records[0] | {status, ticket_id}'
   # ожидаем: файл существует, в audit ровно 1 строка DONE
   ```
6. **Идемпотентность:**
   ```bash
   curl -X POST localhost:8000/trigger -d '{"entry_id":"demo-001"}'  # повторно
   docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select count(*) from tickets').fetchone()[0])"  # ожидаем: 1, не 2
   ls outbox/ | wc -l  # ожидаем: 1
   ```
7. **Юнит-тесты:**
   ```bash
   pytest -q
   # ожидаем: все тесты зелёные, среди них test_triage / test_idempotency / test_adapters / test_graph_e2e
   ```
8. **Качество кода:**
   ```bash
   ruff check . && ruff format --check . && mypy app/
   # ожидаем: каждая команда exit 0
   ```

> **Готово итерации = (1) → (8) все зелёные на чистой машине.**

## Открытые вопросы

- [ ] **Размер KB:** 4–6 markdown — достаточно? Если ревьюер захочет «понажимать» — может оказаться мало. Решим перед demo-видео.
- [ ] **Mailhog в demo:** включать в `docker-compose.yml` по умолчанию или оставить закомментированным как «bonus профиль»? Влияет на сложность запуска на чистой машине.
- [ ] **Поллер в MVP:** запускать в daemon-треде сразу или только активировать через переменную окружения? (Безопаснее: только через env, чтобы `docker compose up` не «жил» в фоне фейковыми тиками.)
- [ ] **CI на push vs на PR:** `ci.yml` сейчас триггерится на `push` **и** `pull_request` в `main` (удобно и для одиночной разработки, и для PR). Менять при необходимости.
- [ ] **README структура:** «быстрый старт» в начале (1 команда) или развёрнутый «как это работает» сразу? Решим, когда увидим работающий MVP.

---

> [!note] Эволюция этого файла
> После каждой завершённой задачи итерации — отмечается `[x]` в Scope и добавляется одна строка в раздел «Done» (пока отсутствует — добавится при первой реализации).
> При обнаружении расхождений с архитектурой — фиксируем здесь, перед правкой `ARCHITECTURE.md`.
