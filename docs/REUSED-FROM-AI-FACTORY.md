# Реестр переиспользования из AI-Factory

Каждая адаптация паттерна из AI-Factory фиксируется здесь (см. `CLAUDE.md` § Rules #2).

**Правила:**
- `ai-factory/` напрямую **не импортируется** (инвариант #3) — переносим только паттерны.
- В коде у места адаптации — комментарий `# Adapted from ai-factory/<path>` + одна строка «зачем».
- Эта таблица — сводный индекс; деталь и причина — в комментарии у кода.

| Модуль проекта | Источник в AI-Factory | Что взято | Что НЕ взято / отличия |
|---|---|---|---|
| `app/llm/gigachat_client.py` | `ai-factory/core/routes/agent/entrypoint.py` | init-параметры GigaChat: `credentials` + `scope` + `verify_ssl_certs=False` | ручной Lock-cache токена отброшен — `langchain_gigachat` рефрешит токен сам (инвариант #10, Karpathy «Simplicity first») |
