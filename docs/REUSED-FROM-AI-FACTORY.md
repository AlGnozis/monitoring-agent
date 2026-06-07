# Реестр переиспользования из AI-Factory

Каждая адаптация паттерна из AI-Factory фиксируется здесь (см. `CLAUDE.md` § Rules #2).

**Правила:**
- `ai-factory/` напрямую **не импортируется** (инвариант #3) — переносим только паттерны.
- В коде у места адаптации — комментарий `# Adapted from ai-factory/<path>` + одна строка «зачем».
- Эта таблица — сводный индекс; деталь и причина — в комментарии у кода.

| Модуль проекта | Источник в AI-Factory | Что взято | Что НЕ взято / отличия |
|---|---|---|---|
| `app/llm/gigachat_client.py` | `ai-factory/core/routes/agent/entrypoint.py` | init-параметры GigaChat: `credentials` + `scope` + `verify_ssl_certs=False` | ручной Lock-cache токена отброшен — `langchain_gigachat` рефрешит токен сам (инвариант #10, Karpathy «Simplicity first») |
| `app/logger.py` | `core/logger.py` | сигнатура `log_*(message, component, action, ctx)` + экранирование скобок `{{ }}` (инвариант #8) | — |
| `app/rag/embeddings.py` | `backend modules/knowledge_base/embeddings.py` | HTTP-клиент E5 (батчинг + префиксы `passage:`/`query:`, инвариант #9) | endpoint указывает на наш `embedding-service` |
| `app/rag/vectorize.py` | `backend modules/knowledge_base/vectorization.py` | чанкинг `RecursiveCharacterTextSplitter` 512/overlap 50 + loader с encoding-fallback | урезано до `.md/.txt` (без PDF/DOCX — лишние тяжёлые зависимости не нужны) |
| `app/rag/retriever.py` | `backend modules/knowledge_base/entrypoint.py` (`/search`) | `similarity_search` по локальному FAISS + `allow_dangerous_deserialization=True` (инвариант #7) | graceful degradation: нет индекса → пустой `RagContext` |
