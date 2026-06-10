# Demo script — monitoring-agent

Скрипт для записи 90-секундного demo-видео (Loom / QuickTime + Loom share).
Цель — за полторы минуты показать ревьюеру, что проект **реально работает end-to-end** и **демонстрирует инженерные акценты**, а не только зелёные тесты.

> **Формат:** screen capture в полноэкранном режиме, один терминал + один браузер (или `jq` в терминале). Голос за кадром — спокойный, по делу, без воды.

---

## Чек-лист подготовки (5 минут до записи)

- [ ] Терминал: открыт в `~/Documents/Work/Sber/monitoring-agent`, шрифт ≥ 16pt, тема светлая или контрастная тёмная.
- [ ] Браузер: открыта вкладка GitHub репо.
- [ ] `.env` заполнен боевыми GigaChat credentials (НЕ показывать в кадре содержимое).
- [ ] `docker compose down -v` сделан → чистое состояние (нет `audit.db`/`tickets.db`/`outbox/`/`data/kb/`).
- [ ] Команды зарепетированы — без опечаток в кадре.
- [ ] Скрытие приватной информации: закрыть Slack/почту, закрыть лишние табы.
- [ ] Запись звука проверена.

---

## Сценарий (90 секунд, 5 актов)

### Акт 1 — Контекст (15 сек)

**Действие:** показать GitHub README в браузере, проскроллить до раздела «Что демонстрирует проект».

**За кадром:**
> «monitoring-agent — тестовое для Сбера. Сквозной AI-агент мониторинга IT-инцидентов: фид → триаж GigaChat → RAG → mock-заявка → письмо. Стэк: Python 3.12, LangGraph, FAISS, FastAPI. Дисциплина — pipeline + Behavioral defaults по Karpathy. 62 теста, CI зелёный, mypy strict».

---

### Акт 2 — Запуск (15 сек)

**Действие:** в терминале:

```bash
docker compose up -d
docker compose ps
```

**За кадром:**
> «`docker compose up` поднимает два сервиса: agent на 8000 и embedding-service на 8001. Healthcheck ждёт E5 — это нормально, обычно занимает 30 секунд на cold-start».

> *(вырезать паузу здоровья компоновкой видео — или дождаться `(healthy)` в `ps`)*

---

### Акт 3 — Сборка базы знаний (15 сек)

**Действие:**

```bash
docker compose exec agent python -m app.rag.build_kb
```

**За кадром:**
> «Собираем FAISS-индекс из `data/knowledge/` — 5 runbook'ов и past_incidents. Префикс `passage:` для E5, чанки 512 символов с overlap 50. После этого RAG будет находить релевантные документы».

---

### Акт 4 — Главное (30 сек) — e2e прогон

**Действие:**

```bash
# Прогон
curl -s -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"entry_id": "demo-001"}' | jq

# Артефакты
ls outbox/
cat outbox/demo-001.eml | head -25
curl -s localhost:8000/audit | jq
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select ticket_id,severity,summary from tickets').fetchall())"
```

**За кадром:**
> «POST /trigger с записью из fake_feed. За секунды — `status=DONE`, `ticket_id=DEMO-001`. В `outbox/` появилось письмо владельцу из owners.yaml с темой, summary, рекомендациями и ссылкой на тикет. В `audit.db` — строка с timing'ами и токенами. В `tickets.db` — заявка».

---

### Акт 5 — Идемпотентность + closing (15 сек)

**Действие:**

```bash
# Повторный прогон
curl -s -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"entry_id": "demo-001"}' | jq

# Артефактов не прибавилось
ls outbox/ | wc -l
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select count(*) from tickets').fetchone()[0])"
```

**За кадром:**
> «Повтор того же event_id. API возвращает тот же event_hash, но *новой* заявки и письма НЕТ — idempotency через `sha256(source+entry)` проверяется и в audit, и в адаптере. Defense-in-depth».

> «Полная документация — README + `docs/`. Спасибо».

---

## Скрипт-команды одним блоком (для рестрима)

```bash
# подготовка (вне записи)
docker compose down -v
rm -rf outbox audit.db tickets.db data/kb

# запись начинается
docker compose up -d && sleep 30 && docker compose ps
docker compose exec agent python -m app.rag.build_kb
curl -s -X POST localhost:8000/trigger -H "Content-Type: application/json" \
  -d '{"entry_id": "demo-001"}' | jq
ls outbox/
cat outbox/demo-001.eml | head -25
curl -s localhost:8000/audit | jq
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select ticket_id,severity,summary from tickets').fetchall())"

# идемпотентность
curl -s -X POST localhost:8000/trigger -H "Content-Type: application/json" \
  -d '{"entry_id": "demo-001"}' | jq
ls outbox/ | wc -l
docker compose exec agent python -c "import sqlite3; print(sqlite3.connect('tickets.db').execute('select count(*) from tickets').fetchone()[0])"
```

---

## Что НЕ показывать

- Содержимое `.env` (GigaChat creds на экране — security issue).
- Полные docker logs (там может быть лишний шум).
- Реальный live RSS (он не работает в iteration-1 — anti-scope).
- Unit-тесты (упомянуть числом «62» — не запускать в видео).

---

## Что добавить в README после записи

В строку под `Status` поставить ссылку на видео:

```markdown
> 🎥 **Demo (90 сек):** https://www.loom.com/share/<id> — docker compose up → build_kb → POST /trigger → outbox/demo-001.eml + audit.db.
```

---

## Альтернатива — GIF вместо видео

Если Loom неудобен:

```bash
brew install asciinema agg  # one-time
asciinema rec demo.cast --command="bash demo_script.sh"
agg demo.cast demo.gif --speed 2 --theme monokai
```

Положить `demo.gif` в `docs/assets/` и вставить в README как `![demo](docs/assets/demo.gif)`.

GIF тяжелее загружается, но **не требует клика** и виден прямо на странице репо. Для тестового задания — отличный вариант.
