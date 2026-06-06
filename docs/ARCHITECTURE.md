# Архитектурный план: AI-агент мониторинга (RSS → инцидент → заявка → оповещение)

> Продуктовый контекст и метрика успеха — `docs/product-vision.md`.
> Текущая итерация (scope/acceptance) — `docs/iteration-1.md`.
> Этот файл — **технический архитектурный план**, к которому возвращаются за «как устроено».

## Context

Тестовое задание на позицию **Python-разработчик (AI-агент)** в Сбере. Цель — продемонстрировать навыки LLM-инженера, построив агента мониторинга по эталонному сценарию лида:

> «Пошёл в блог/ленту → нашёл ошибку → подтянул в RAG → посмотрел описание → завёл заявку → определил владельца ошибочной системы → написал письмо с рекомендациями».

Проект строится **на отлаженных паттернах AI-Factory** (RAG/FAISS/E5, GigaChat, MCP-тулзы, polling-loop, subprocess-деплой), но как **отдельный запускаемый сервис**, а не форк всего Django+Kafka стека.

## Зафиксированные решения по развилкам

- **Масштаб:** запускаемое демо «под жюри» — один standalone-сервис, запуск одной командой, продакшен-уровень архитектуры без полного Django+Kafka.
- **Домен:** синтетическая лента IT-инцидентов «Сбер-like» (внутренние микросервисы: платёжный шлюз, КБ, АБС, KYC...) на русском — детерминированно, идеально под GigaChat, осмысленный owner-маппинг. **Фид:** основной режим — `fake_feed.json` (воспроизводимо, для демо + e2e); адаптер источника позволяет переключиться на **живой RSS (feedparser) как bonus**.
- **Интеграции:** **mock-only** (реальных Jira/SMTP нет). Интерфейс `Protocol` сохраняем (production-ready): `MockTicketAdapter` → SQLite + синтетический ключ `DEMO-{seq:03d}` (первый = `DEMO-001`); `MockNotifyAdapter` → рендер письма в `outbox/*.eml` + лог. Опц. **Mailhog** как локальный визуальный SMTP-сток (без внешней инфры).
- **Оркестрация:** явный **LangGraph** state-machine с именованными узлами и условными рёбрами.
- **Данные:** лёгкий стек без Django ORM — `MonitorState` (Pydantic, протекает через граф) + `EventRecord` в SQLite-аудите (`sqlite3`/SQLModel).
- **Eval:** core — unit для узлов + e2e на фейковом фиде + agent-eval. **RAGAS — опциональная bonus-фича за флагом**, не в ядре.
- **Git:** обязателен с первого commit, проект публикуется на GitHub (см. `CLAUDE.md` § Rules).

---

## Целевой результат

Запускаемое демо `monitoring-agent/`, которое по фейковому (или реальному) RSS-фиду:
1. находит релевантное событие об IT-инциденте,
2. обогащает его знанием из RAG (runbooks + прошлые инциденты),
3. определяет владельца затронутой системы,
4. идемпотентно заводит заявку (mock/Jira),
5. отправляет владельцу письмо с описанием и рекомендациями (mock/SMTP),
6. логирует и сохраняет аудит каждого шага.

Демонстрируемые инженерные акценты: явный наблюдаемый граф, structured output GigaChat с учётом ограничений схемы, идемпотентность (нет дублей заявок/писем), graceful degradation (пустой RAG), human-in-the-loop gate перед действиями наружу, eval-метрики (RAGAS + agent-eval).

---

## Архитектура (узлы LangGraph)

Состояние `MonitorState` (Pydantic/TypedDict) протекает через граф:

```
[ingest]        RSS poll → нормализация записи → дедуп по content-hash
   ↓
[triage]        GigaChat structured output: is_incident? severity? topic? affected_system?
   ↓  conditional: not incident / low-noise → [drop]
[enrich_rag]    retrieve из KB (FAISS+E5): похожие инциденты, runbook, описание ошибки
   ↓
[resolve_owner] определить владельца системы: RAG/справочник owners.yaml → email
   ↓
[plan_action]   GigaChat structured output: summary, severity, recommendations[], escalate_to
   ↓  conditional: human_gate (если severity>=HIGH и включён gate → пауза/подтверждение)
[act_ticket]    TicketAdapter.create(idempotency_key=event_hash) → ticket_id
   ↓
[act_notify]    NotifyAdapter.send(to=owner_email, body=summary+recs+ticket_link)
   ↓
[persist_audit] записать EventRecord: статус, ticket_id, отправленное письмо, тайминги, токены
```

**Ключевые свойства узлов:**
- **Идемпотентность:** `idempotency_key = sha256(source_id + entry_id)`. Перед `act_ticket`/`act_notify` проверка в audit-store — если событие уже обработано, узлы — no-op.
- **Структурированный вывод GigaChat:** через `with_structured_output` / function-call, схемы — плоские (учёт ограничений GigaChat: нет `anyOf`, нет `type:object` без `properties`, нет `type:array` без `items`). Fallback-парсер если модель вернула невалидный JSON.
- **Ретраи/лимиты:** `recursion_limit>=10`; ретраи на сетевых узлах (RAG/LLM/адаптеры) с backoff; таймауты.
- **Graceful degradation:** пустой RAG → `enrich_rag` помечает `context_empty=True`, `plan_action` честно формирует письмо «недостаточно данных, требуется ручная проверка».
- **Observability:** каждый узел логирует через loguru-обёртку (паттерн `log_info(msg, component, action, ctx)`, экранирование `{{ }}`), плюс трейс в audit.

---

## Структура проекта

```
monitoring-agent/
  pyproject.toml / requirements.txt
  docker-compose.yml          # agent + embedding-service (+ опц. mailhog для real-SMTP демо)
  .env.example                # GIGACHAT creds, scope, источники, режим адаптеров
  README.md                   # как запустить демо за 1 команду

  app/
    config.py                 # pydantic-settings: токены, scope, ADAPTERS=mock|real, feed urls
    state.py                  # MonitorState (Pydantic), EventRecord, enums (Severity, Status)

    graph/
      build.py                # StateGraph: узлы, рёбра, условные переходы, recursion_limit
      nodes/
        ingest.py
        triage.py             # GigaChat structured output (классификация)
        enrich_rag.py         # вызов RAG-клиента
        resolve_owner.py      # owners.yaml / RAG lookup
        plan_action.py        # GigaChat structured output (рекомендации)
        act_ticket.py
        act_notify.py
        persist_audit.py

    llm/
      gigachat_client.py      # ПЕРЕИСПОЛЬЗОВАТЬ паттерн: GigaChat + кэш токена (буфер −60с, lock)
      prompts.py              # system prompts: TRIAGE_PROMPT, PLAN_PROMPT + few-shot
      schemas.py              # Pydantic-схемы structured output (GigaChat-совместимые)

    rag/                      # ПЕРЕИСПОЛЬЗОВАТЬ из AI-Factory (адаптировать)
      embeddings.py           # E5RemoteEmbeddings (copy)
      vectorize.py            # VectorizationService: load → chunk(512/overlap50) → FAISS
      retriever.py            # FAISS.similarity_search_with_score, режимы NECC/STRONG/WEAK
      build_kb.py             # CLI: набить KB из data/knowledge/*

    ingest/
      rss_poller.py           # ПЕРЕИСПОЛЬЗОВАТЬ паттерн _polling_loop + threading.Event + дедуп
      sources.py              # feedparser; FakeSource для детерминированного демо

    adapters/                 # pluggable: Protocol + mock (real — задел на будущее)
      ticket.py               # TicketAdapter(Protocol); MockTicketAdapter → SQLite + DEMO-{seq:03d}
      notify.py               # NotifyAdapter(Protocol); MockNotifyAdapter → outbox/*.eml + log
      factory.py              # выбор реализации по ADAPTERS (сейчас всегда mock; real — стаб)

    store/
      audit.py                # SQLite (sqlite3/SQLModel): EventRecord, idempotency-проверка, статусы

    api/
      server.py               # FastAPI: POST /trigger (ручной прогон по entry), GET /health, /audit

  data/
    knowledge/                # runbooks*.md, past_incidents*.md → KB
    owners.yaml               # system → {owner_name, owner_email, team}
    fake_feed.json            # детерминированный синтетический фид «Сбер-like» для демо/тестов

  outbox/                     # рендеренные письма (.eml) от MockNotifyAdapter

  evals/
    agent_eval.py             # e2e на fake_feed: precision триажа, корректность маршрутизации владельцу
    ragas_eval.py             # BONUS (за флагом): паттерн evaluate_kb.py, RAGAS-метрики
    fixtures/

  tests/
    test_triage.py, test_idempotency.py, test_graph_e2e.py, test_adapters.py
```

---

## Переиспользование из AI-Factory (конкретно)

| Новый модуль | Источник-паттерн | Что берём |
|---|---|---|
| `llm/gigachat_client.py` | `ai-factory/core/routes/agent/entrypoint.py` (init token, refresh) | `langchain_gigachat.GigaChat`, кэш токена с буфером −60с под `Lock`, refresh перед запросом |
| `rag/embeddings.py` | `backend/ai_factory/modules/knowledge_base/embeddings.py` | `E5RemoteEmbeddings` (copy as-is, сменить endpoint) |
| `rag/vectorize.py` | `backend/.../knowledge_base/vectorization.py` | loader (PDF/DOCX/TXT, encoding-fallback), `RecursiveCharacterTextSplitter(512, overlap=50)`, префикс `passage:`, `FAISS.from_documents` |
| `rag/retriever.py` | `ai-factory/core/routes/knowledge_base/entrypoint.py` `/search/` | `similarity_search_with_score(k, threshold)`, режимы NECC/STRONG/WEAK, `form_prompt_for_mode` |
| embedding-service | `add_soft/embedding-service-develop/main.py` | standalone E5 (`intfloat/e5-small-v2`), `POST /embedding`, в docker-compose |
| `ingest/rss_poller.py` | `backend/.../integrations/email_service_entrypoint.py` `_polling_loop()` | daemon-тред, `threading.Event`, `POLL_INTERVAL`, дедуп по id, graceful `/close/` |
| `adapters/ticket.py` | `backend/.../integrations/jira_mcp_server.py` | контракт `create_issue`/`search_issues` как форма `Protocol` (mock-реализация в демо) |
| `adapters/notify.py` | `email_service_entrypoint.py` (SMTP-часть) | формат письма владельцу (mock рендерит в `.eml`) |
| `evals/ragas_eval.py` (BONUS) | `ai-factory/core/routes/knowledge_base/evaluate_kb.py` | `TestsetGenerator`, метрики Faithfulness/AnswerRelevancy/ContextPrecision/Recall, адаптация промптов на русский |
| логирование | `backend/ai_factory/core/logger.py` | loguru-обёртка, экранирование `{{ }}` |

**Жёсткое правило:** `ai-factory/` НЕ трогаем — копируем паттерны в новый репозиторий, не импортируем напрямую (там Kafka/Redis в `core/__init__.py`). Реестр копий — `docs/REUSED-FROM-AI-FACTORY.md` (заполняется по мере переноса).

---

## Контракты данных

- **`MonitorState`**: `raw_entry`, `event_hash`, `triage` (is_incident, severity, topic, affected_system), `rag_context` (chunks, context_empty), `owner` (name, email, team), `action_plan` (summary, recommendations[], escalate_to), `ticket_id`, `notified`, `status`, `timings/tokens`.
- **`owners.yaml`**: `affected_system → {owner_name, owner_email, team}`. `resolve_owner` сначала точное совпадение, затем RAG/LLM-маппинг по описанию.
- **Structured-output схемы** (`llm/schemas.py`): плоские Pydantic-модели, совместимые с GigaChat (enum severity = строка из фикс. набора; recommendations = `array{items:string}`).

---

## Промпт-инжиниринг

- `TRIAGE_PROMPT`: классификатор. Вход — заголовок+тело записи. Выход — строгий JSON по схеме. Few-shot (2-3 примера: инцидент / шум / маркетинг). Жёсткое «верни только JSON».
- `PLAN_PROMPT`: на основе записи + RAG-контекста сформировать summary, severity-обоснование, 2-4 рекомендации, кому эскалировать. Режим RAG STRONG (контекст в приоритете, но можно опереться на общее знание).
- Защита от prompt-injection из ленты: входной текст оборачивается как данные, инструкции из контента игнорируются (system-уровень).

---

## Деплой / запуск (демо)

- `docker-compose up` поднимает: `embedding-service` (E5) + `monitoring-agent` (FastAPI + LangGraph + поллер в daemon-треде). Опц. `mailhog` для наглядного просмотра писем.
- `ADAPTERS=mock` по умолчанию → mock-адаптеры: заявка в SQLite (`DEMO-001`), письмо в `outbox/*.eml` + лог. Полностью без внешних секретов/сервисов.
- Источник: `SOURCE=fake` (по умолчанию, `fake_feed.json`) | `SOURCE=rss` + `FEED_URL=...` (bonus, живой RSS через `feedparser`).
- Сидинг KB: `python -m app.rag.build_kb` из `data/knowledge/`.
- Демо-прогон: `POST /trigger` с записью из `fake_feed.json` (детерминированно) ИЛИ включить живой фид.

---

## Ловушки (учесть в реализации)

> Полный список инвариантов и анти-паттернов — `CLAUDE.md` (§ Invariants, § Anti-patterns).

- **GigaChat token** живёт ~30 мин → кэш с буфером −60с под `Lock`, refresh перед запросом.
- **GigaChat schema**: нет `anyOf`, нет `type:object` без `properties`, нет `type:array` без `items` → схемы плоские, всегда `items`/`properties`.
- **E5 префиксы**: документы `passage:`, запросы `query:` (зафиксировать единообразно).
- **FAISS**: `allow_dangerous_deserialization=True` при загрузке; `chunk_size` — символы, не токены (~3-4 символа/токен для кириллицы).
- **Loguru**: `{}` в сообщении → экранировать `{{ }}`.
- **LangGraph**: обязательно `recursion_limit>=10`.
- **Идемпотентность**: проверка перед каждым внешним действием, иначе дубли заявок/писем при ретраях поллера.
- **RAGAS**: библиотека `ragas` ставится отдельно (не в базовых requirements).

---

## Верификация

1. **Unit:** `test_triage.py` (классификация на фикстурах: инцидент vs шум), `test_idempotency.py` (повторный прогон того же события не плодит заявку/письмо), `test_adapters.py` (mock-адаптеры пишут ожидаемые записи в SQLite/`outbox`).
2. **E2E:** `test_graph_e2e.py` — прогон `fake_feed.json` через весь граф в `ADAPTERS=mock`, проверка: создан 1 EventRecord со статусом DONE, ticket_id присвоен, письмо отрендерено владельцу из `owners.yaml`.
3. **Agent eval:** `evals/agent_eval.py` — precision триажа и доля верной маршрутизации владельцу на размеченном наборе записей.
4. **RAG eval (BONUS, за флагом):** `evals/ragas_eval.py` на тест-сете по `data/knowledge/` — Faithfulness/AnswerRelevancy/ContextPrecision/Recall выше порога.
5. **Ручная демонстрация:** `docker-compose up` → `POST /trigger` → смотрим лог графа поузлово + запись в `/audit` + письмо в `outbox/` (или Mailhog).
