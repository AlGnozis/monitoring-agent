# monitoring-agent

Standalone AI-агент мониторинга IT-инцидентов. RSS-фид → триаж GigaChat → RAG-обогащение → resolve owner → mock-заявка + mock-письмо → SQLite-аудит. Тестовое задание на позицию Python-разработчик (AI-агент) в Сбере.

Подробности продукта — `docs/product-vision.md`. Текущая итерация — `docs/iteration-1.md`. Архитектурный план — `docs/ARCHITECTURE.md` (создаётся в Шаге 3 pipeline).

---

## Stack

- **Python 3.12**, FastAPI, Pydantic v2
- **LangGraph** — оркестрация (state-machine с явными узлами)
- **GigaChat** через `langchain_gigachat` — LLM (триаж + plan_action со structured output)
- **FAISS + E5** (`intfloat/e5-small-v2`) — RAG retriever, встраиваниям через отдельный `embedding-service`
- **SQLite** (`sqlite3` / `SQLModel`) — аудит-store (`EventRecord`) + mock-Jira
- **Docker Compose** — `agent` + `embedding-service` (+ опц. `mailhog`)

## Architecture (5–10 строк)

```
app/
  api/        — FastAPI: POST /trigger, GET /health, /audit
  graph/      — LangGraph: ingest → triage → enrich_rag → resolve_owner → plan_action → act_ticket → act_notify → persist_audit
  llm/        — GigaChat client (token cache) + structured-output schemas
  rag/        — E5 embeddings, vectorize (chunk 512/overlap 50), FAISS retriever
  ingest/     — RSS poller (daemon thread) + FakeSource из fake_feed.json
  adapters/   — TicketAdapter / NotifyAdapter (Protocol + mock + factory)
  store/      — audit (EventRecord, идемпотентность через event_hash)
data/         — knowledge/, owners.yaml, fake_feed.json
evals/        — agent_eval (core), ragas_eval (bonus за флагом)
```

Связь: всё в одном Python-процессе; внешний только `embedding-service` (HTTP).

## Invariants (нельзя нарушать никогда)

1. **API всегда возвращает JSON.** Ошибки — единый формат: `{"error": "<code>", "message": "<msg>"}`.
2. **Идемпотентность по `event_hash`** = `sha256(source_id + entry_id)`. Проверка в `store/audit.py` **перед каждым внешним действием** (`act_ticket`, `act_notify`).
3. **`ai-factory/` НЕ импортируется напрямую** — только копирование/адаптация паттернов с комментарием-источником. `core/__init__.py` тянет Kafka/Redis.
4. **Реальных интеграций Jira / SMTP / Slack нет.** Только `Protocol` + mock-реализации.
5. **GigaChat schema constraints:** нет `anyOf`, нет `type:object` без `properties`, нет `type:array` без `items`. Все schema-Pydantic — плоские.
6. **LangGraph `recursion_limit >= 10`** — задаётся в одном месте (`graph/build.py`).
7. **FAISS deserialization:** `allow_dangerous_deserialization=True` только для **нашего** артефакта `vectorize.py`. Не загружаем чужие индексы.
8. **Loguru:** `{}` и `<...>` в message → экранировать `{{ }}` и `\<` `\>`. Использовать обёртку `_safe()`.
9. **E5 префиксы:** документы — `passage:`, запросы — `query:`. Единообразно во всём RAG.
10. **GigaChat token:** кэш под `Lock`, буфер ≥ 60s, refresh ПЕРЕД запросом (не после 401).

## Rules (правила работы над проектом)

1. **Git с первого commit.** Conventional commits: `feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`. Линейная история (rebase, не merge).
2. **Каждое переиспользование паттерна AI-Factory** — комментарий в коде: `# Adapted from ai-factory/<path>` + одна строка причины. Реестр — `docs/REUSED-FROM-AI-FACTORY.md`.
3. **Тесты обязательны** для: триажа (фикстуры incident / шум / маркетинг), идемпотентности (повторный прогон не плодит дубликатов), e2e-сценария по `fake_feed.json`.
4. **Публичные сигнатуры Protocol-адаптеров** (`TicketAdapter`, `NotifyAdapter`) не меняются без RFC в `docs/iteration-N.md`.
5. **Mock через factory + Protocol**, никаких `if mode == "mock"` веток в бизнес-логике.
6. **PR / commit message — на русском.** Code, identifiers, docstrings — на английском.
7. **README, документы — на русском** (по решению пользователя).

## Style (предпочтения)

- `snake_case` в Python, PEP-8, проверка через **ruff**.
- **Pydantic v2** для всех data-классов: `MonitorState`, `EventRecord`, structured-output schemas.
- Импорты группами: stdlib / third-party / local (ruff isort).
- **Type hints обязательны** для публичных функций.
- Логирование через **loguru-обёртку** `log_info(msg, component, action, ctx)`. Никаких `print`.
- Pydantic-модели и enums — в `app/state.py` (общие) или рядом с пользователем (доменные).

## Commands

```bash
# Развёртывание
docker-compose up                    # agent + embedding-service
docker-compose up -d                 # detached режим

# Локальная разработка (без docker)
uv venv && uv pip install -e ".[dev]"
uvicorn app.api.server:app --reload

# Качество кода
ruff check .                         # lint
ruff format .                        # auto-format
mypy app/                            # типы

# Тесты
pytest -q                            # все тесты
pytest tests/test_triage.py -q       # точечный
pytest -q --cov=app --cov-report=term-missing  # с покрытием

# RAG
python -m app.rag.build_kb           # пересборка KB из data/knowledge/

# Демо
curl -X POST localhost:8000/trigger -d '{"entry_id": "demo-001"}'
curl localhost:8000/audit | jq

# Eval (bonus)
pip install -r requirements-eval.txt
python evals/ragas_eval.py
```

## Key Files (карта; обновляется по мере роста)

| Путь | Назначение |
|---|---|
| `app/api/server.py` | FastAPI entrypoint, `/trigger`, `/health`, `/audit` |
| `app/graph/build.py` | `StateGraph`, conditional edges, recursion limit |
| `app/state.py` | `MonitorState`, `EventRecord`, enums (`Severity`, `Status`) |
| `app/llm/gigachat_client.py` | GigaChat-клиент + token-кэш под Lock |
| `app/llm/prompts.py` | `TRIAGE_PROMPT`, `PLAN_PROMPT` (+ few-shot) |
| `app/llm/schemas.py` | Pydantic-схемы structured-output (плоские, GigaChat-совместимые) |
| `app/rag/retriever.py` | FAISS similarity_search + STRONG/WEAK режимы |
| `app/store/audit.py` | SQLite audit, `is_processed(event_hash)`, идемпотентность |
| `app/adapters/factory.py` | Выбор реализации по `MODE`; сейчас всегда mock |
| `data/owners.yaml` | `affected_system → {owner_name, owner_email, team}` |
| `data/fake_feed.json` | Детерминированный синтетический фид «Сбер-like» |
| `docs/product-vision.md` | Продуктовая постановка |
| `docs/iteration-1.md` | Текущая итерация (создаётся в Шаге 3) |
| `docs/ARCHITECTURE.md` | Архитектурный план (Шаг 3) |

## Don't Touch без явной просьбы

- `data/knowledge/` — пользовательские документы базы знаний
- `data/owners.yaml` — бизнес-маппинг (правится осознанно)
- `.env`, `.env.local` — секреты (только через `.env.example` без значений)
- `evals/fixtures/` — золотой набор для оценки качества
- `LICENSE`, `README.md` — обновляются только при явных изменениях продукта

## Anti-patterns проекта (горький опыт + предупреждения)

- **НЕ ИМПОРТИРУЙ `ai-factory/core/__init__.py`** — тянет Kafka/Redis при импорте, ломает unit-тесты.
- **НЕ ИСПОЛЬЗУЙ `if mode == "mock"`** в бизнес-логике — только factory + Protocol.
- **НЕ ВКЛЮЧАЙ RAGAS в основные dependencies** — отдельный `requirements-eval.txt` за флагом.
- **НЕ МОКАЙ `gigachat_client` в e2e-тестах** — только в `tests/test_triage.py` с явной маркировкой `@pytest.mark.mock_llm`.
- **НЕ ПИШИ `print`** — loguru или `log_info` обёртка.
- **НЕ ПОВТОРЯЙ `recursion_limit=10`** в каждом вызове графа — задаётся один раз в `build.py`.
- **НЕ МЕНЯЙ публичные Protocol-методы** адаптеров (`create_ticket`, `send_notification`) — это контракт для будущих реальных реализаций.

## License

MIT. Файл `LICENSE` в корне репозитория.

---

## Behavioral defaults (поведение «по умолчанию», всегда-на)

Адаптация behavioral CLAUDE.md от Andrej Karpathy. Эти правила работают на ВСЕХ задачах проекта и закрывают типовые «болезни» LLM при кодинге.

1. **Think before coding.** Не предполагай молча. Озвучивай assumptions явно. Если есть две интерпретации — покажи обе, не выбирай за пользователя. Если что-то непонятно — STOP и спроси. Не прячь confusion за догадкой.

2. **Simplicity first.** Минимум кода, который решает задачу. Никаких «гибких» абстракций для одного использования. Никакого error handling для невозможных сценариев. Если 200 строк могут быть 50 — перепиши.

3. **Surgical changes.** Каждая изменённая строка должна обосновываться запросом пользователя. Не «улучшай» соседний код, не переформатируй, не рефактори то, что не сломано. Match existing style, даже если сам сделал бы иначе. Замеченный dead code — упомяни, не удаляй сам.

4. **Goal-driven execution.** Превращай задачу в проверяемые критерии. «Добавь валидацию» → «напиши тесты на невалидные входы, потом сделай так, чтобы они проходили». Сильные критерии успеха позволяют тебе loop'иться независимо, слабые («сделай чтобы работало») требуют постоянных уточнений.

**Эти правила работают, если:** в diff меньше «лишних» изменений, реже переписывание из-за переусложнения, уточняющие вопросы появляются ДО ошибок, а не после.

**Trade-off:** правила склоняют к caution > speed. На тривиальных задачах — используй здравый смысл, не превращай каждый микро-фикс в discovery.

---

> [!note] Эволюция этого файла
> `CLAUDE.md` — живой документ. По мере работы над итерациями:
> - **системные ошибки** (повторившиеся дважды) — переезжают в `Anti-patterns проекта`;
> - **новые стабильные команды** — в `Commands`;
> - **новые ключевые файлы** — в `Key Files`;
> - если файл вырастет > 200 строк — выделяем локальные `app/llm/CLAUDE.md`, `app/rag/CLAUDE.md` и т.п.
>
> Источник методики — интегральный Guide курса Vibecoding (раздел 9 «Шаблоны проектных артефактов»).
