## Назначение

Сервис MCP для поиска по метаданным конфигураций 1С (JSON). Подходит, когда ИИ/агенту нужно быстро найти объекты по имени/синониму, например: состав реквизитов, полные имена объектов, связи и т.п.

**Где используется**

- ИИ-агенты в браузере (расширение MCP SuperAssistant)
- ИИ-агенты в IDE (Cursor, Void и др.)

Сервис разворачивается в Docker или локально (pip/venv).

## Быстрый старт (Docker)

PowerShell (Windows):

```powershell
docker run --rm -it `
  -p 8007:8000 `
  -v "C:\ERP\Report":/app/metadata_src `
  -v "C:\ERP\Report\dist":/app/metadata_dist `
  -v "C:\ERP\Report\logs":/app/logs `
  -e MCP_PORT=8000 -e MCP_PATH=/mcp `
  smirnov0ser/mcp1c_metadata:latest
```

Минимально достаточно пробросить только `metadata_src`. Папки `metadata_dist` и `logs` можно не монтировать — они будут созданы в контейнере.

Пояснения:

- **Внешний порт**: 8007 — ваш порт на хосте; контейнер слушает 8000
- **metadata_src**: каталог с JSON-метаданными конфигураций 1С, полученные обработкой ВыгрузитьМетаданныевJson.epf
- **metadata_dist**: артефакты компиляции (индекс конфигураций)
- **logs**: файлы логов сервиса

Пример без дополнительных томов:

```powershell
docker run --rm -it -p 8007:8000 -v "C:\ERP\Report":/app/metadata_src smirnov0ser/mcp1c_metadata:latest
```

## Локальный запуск (без Docker)

Требуется Python 3.12+.

```powershell
python -m venv venv
.\venv\\Scripts\\Activate.ps1
python -m pip install -r .\requirements.txt
$env:INPUT_METADATA_DIR = "C:\ERP\Report"
$env:MCP_HOST = "0.0.0.0"
$env:MCP_PORT = "8000"
$env:MCP_PATH = "/mcp"
python .\app\src\main.py
```

## Переменные окружения

- **INPUT_METADATA_DIR**: путь к исходным JSON с метаданными (по умолчанию `/app/metadata_src`)
- **DIST_METADATA_DIR**: путь для артефактов/индексов (по умолчанию `/app/metadata_dist`)
- **MCP_HOST**: хост MCP-сервера (по умолчанию `0.0.0.0`)
- **MCP_PORT**: порт MCP-сервера (по умолчанию `8000`)
- **MCP_PATH**: URL-путь MCP (по умолчанию `/mcp`)
- **USE_SSE**: `true|false` — транспорт `sse` или `streamable-http` (по умолчанию `false` → `streamable-http`)
- Логи:
  - **LOG_LEVEL**: `DEBUG|INFO|WARNING|ERROR` (по умолчанию `INFO`)
  - **LOG_TO_FILE**: `true|false` (по умолчанию `true`)
  - **LOG_DIR**: каталог логов (по умолчанию `/app/logs`)
  - **LOG_ROTATION**: `size|daily` (по умолчанию `size`)
  - **LOG_MAX_BYTES**: размер файла для size-ротации (по умолчанию 10 МБ)
  - **LOG_BACKUP_COUNT**: число резервных файлов (по умолчанию 5)

## Метаданные: структура каталогов

- Входные JSON: `INPUT_METADATA_DIR` (по умолчанию `/app/metadata_src`)
- Индекс конфигураций: сохраняется в `DIST_METADATA_DIR/metadata_configs_index.json`

Поддерживается несколько конфигураций одновременно (несколько JSON-файлов). Сервис строит краткий индекс для быстрых подсказок и поиска.

## Инструменты MCP

- **metadatasearch(query, find_usages=False, limit=5, config=None)**
  - **query**: строка запроса. Рекомендуется полное имя, например `Справочники.Номенклатура`
  - **find_usages**: зарезервировано под поиск использований (пока не используется)
  - **limit**: ограничение результатов (по умолчанию 5)
  - **config**: выбор конфигурации. Можно указать базовое имя файла без расширения, имя файла с расширением, или значения полей `Имя`/`Синоним` из индекса

Особенности:

- Типы автоматически нормализуются к единственному числу: `Документы.*` → `Документ.*`, суффикс `Ссылка` обрезается
- Если конфигураций несколько и `config` не указан, вернётся подсказка со списком доступных

Примеры запросов:

```text
query = "Документы.Счет"
query = "Справочники.Номенклатура"
query = "РегистрСведений.НастройкиПользователя"
```

## Инструкции для ИИ-агентов

Рекомендуемый промпт-инструктаж:

```text
If you use configuration metadata, check its existence and structure using 'metadatasearch'.
Use the full name in service, for example 'Справочники.Номенклатура'. Set limit 1 for the first call.
Use find_usages = true only if you need to find where an object is used.
```

Пример `mcp.json` (Cursor/SuperAssistant):

```json
{
  "mcpServers": {
    "mcp1c_metadata": {
      "url": "http://localhost:8007/mcp",
      "connection_id": "mcp1c_metadata_001"
    }
  }
}
```

## Сборка и запуск своего образа

Сборка:

```powershell
cd C:\mcp1c_metadata
docker build -t mcp1c_metadata:latest .
```

Запуск собственного образа:

```powershell
docker run --rm -it -p 8007:8000 -v "C:\ERP\Report":/app/metadata_src mcp1c_metadata:latest
```

> При необходимости используйте тот же синтаксис монтирования `metadata_dist` и `logs`.
## Примечания

- На Windows пути с пробелами заключайте в кавычки: `"C:\\Path With Spaces"`
- Изображение по умолчанию использует Python 3.12-slim; сервер MCP запускается командой `python src/main.py`