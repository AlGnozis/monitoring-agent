# monitoring-agent

> **Status:** in development (iteration-1 — реализация MVP) · **License:** MIT · **Python:** 3.12

AI-агент мониторинга IT-инцидентов. Читает RSS-фид (или синтетический), триажит через GigaChat, обогащает через RAG, определяет владельца затронутой системы, заводит mock-заявку и отправляет mock-письмо. Идемпотентно, observability через loguru + SQLite-аудит.

Тестовое задание на позицию **Python-разработчик (AI-агент)** в Сбере.

## Что внутри

Сквозной сценарий лида:

```
[пост в ленте] → [триаж: инцидент?] → [RAG: похожие случаи + runbook]
                                  ↓
[аудит в SQLite] ← [письмо владельцу] ← [mock-заявка] ← [определить владельца]
```

Реализовано как `StateGraph` (LangGraph) — каждый узел наблюдаем в логе и аудите.

## Быстрый старт

> **Status:** код в разработке. Команды ниже — целевые для iteration-1.

```bash
# 1. Клонировать
git clone https://github.com/AlGnozis/monitoring-agent.git
cd monitoring-agent

# 2. Скопировать env-шаблон и заполнить GIGACHAT credentials
cp .env.example .env
# отредактировать: GIGACHAT_AUTH_KEY=..., GIGACHAT_SCOPE=...

# 3. Поднять
docker-compose up -d

# 4. Собрать базу знаний из data/knowledge/
docker-compose exec agent python -m app.rag.build_kb

# 5. Прогнать e2e
curl -X POST localhost:8000/trigger -d '{"entry_id": "demo-001"}'

# 6. Проверить артефакты
sqlite3 audit.db "select status, ticket_id from records;"
ls outbox/
```

Ожидаемый результат: `status=DONE`, ticket_id присвоен, письмо в `outbox/demo-001.eml`. Подробнее — `docs/iteration-1.md` § Acceptance criteria.

## Документация

| Файл | О чём |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Операционка проекта: стек, инварианты, команды, anti-patterns, Behavioral defaults |
| [`docs/product-vision.md`](docs/product-vision.md) | Продуктовая постановка: проблема, метрика успеха, anti-goals, риски |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Полный архитектурный план: узлы графа, переиспользование из AI-Factory, контракты |
| [`docs/iteration-1.md`](docs/iteration-1.md) | Текущая итерация: scope, acceptance criteria, открытые вопросы |

## Стек

- **Python 3.12** · **FastAPI** · **Pydantic v2**
- **LangGraph** — оркестрация state-machine
- **GigaChat** (`langchain_gigachat`) — LLM (триаж + plan со structured output)
- **FAISS + E5** (`intfloat/e5-small-v2`) — RAG retriever через standalone `embedding-service`
- **SQLite** — аудит + mock-Jira
- **Docker Compose** — agent + embedding-service

## Структура папок

```
monitoring-agent/
├── app/                    # код агента (graph, llm, rag, ingest, adapters, store, api)
├── data/                   # knowledge/ (RAG-источники), owners.yaml, fake_feed.json
├── docs/                   # vision, architecture, iteration plans
├── evals/                  # agent-eval (core) + ragas-eval (bonus)
├── tests/                  # unit + e2e
├── outbox/                 # рендеренные письма (.gitignored)
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── CLAUDE.md               # ← операционка проекта, читается агентами разработки
```

## Разработка

Проект разрабатывается с использованием **AI coding pipeline** (см. `CLAUDE.md` § Behavioral defaults, Karpathy 4 принципа). История коммитов — conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`).

CI: GitHub Actions — `ruff check` + `pytest -q` на push в `main` (см. `.github/workflows/ci.yml`).

## License

MIT — см. [`LICENSE`](LICENSE).
