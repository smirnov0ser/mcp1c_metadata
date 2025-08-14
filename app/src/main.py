"""
Main entry point for the MCP server using FastMCP.
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from dotenv import load_dotenv
from fastmcp import FastMCP
from metadata_returner import MetadataReturner

# Load environment variables early
load_dotenv()


# --- Logging configuration (env-driven) ---
def _configure_logging_from_env() -> logging.Logger:
    """
    Конфигурирует логирование на основе переменных окружения.

    Переменные окружения:
    - LOG_LEVEL: Уровень логирования (DEBUG, INFO, WARNING, ERROR). По умолчанию INFO
    - LOG_TO_FILE: Включить запись в файл (true/false). По умолчанию true
    - LOG_DIR: Каталог для логов. По умолчанию /app/logs
    - LOG_ROTATION: Вид ротации (size|daily). По умолчанию size
    - LOG_MAX_BYTES: Размер файла для size-ротации (в байтах). По умолчанию 10485760 (~10MB)
    - LOG_BACKUP_COUNT: Количество резервных файлов. По умолчанию 5
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_to_file = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    log_dir = os.getenv("LOG_DIR", "/app/logs")
    rotation_mode = os.getenv("LOG_ROTATION", "size").lower()
    max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_to_file:
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "app.log")
            if rotation_mode == "daily":
                file_handler = TimedRotatingFileHandler(
                    log_path,
                    when="D",
                    interval=1,
                    backupCount=backup_count,
                    encoding="utf-8",
                )
            else:
                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(
                f"Не удалось инициализировать файловое логирование: {e}"
            )

    return logging.getLogger(__name__)


logger = _configure_logging_from_env()
logger.info("Environment loaded and logging configured")

# --- Configuration from Environment Variables ---
USESSE = os.getenv("USESSE", "false").lower() == "true"

# Initialize MetadataReturner with split input/dist directories
metadata_returner = MetadataReturner(
    metadata_input_dir=os.getenv("INPUT_METADATA_DIR"),
    metadata_dist_dir=os.getenv("DIST_METADATA_DIR"),
)


# Initialize FastMCP server at module level
mcp = FastMCP()
logger.info("FastMCP server initialized...")


# Register tools
@mcp.tool()
def metadatasearch(
    query: str, find_usages: bool = False, limit: int = 5, config: str = None
):
    """
    Search metadata files of 1C configuration. Example: 'Справочники.Номенклатура'.

    :param query: Search string, e.g. `Документ.Счет`. Use singular type when possible
    :param find_usages: Reserved for future feature (find usages). Currently unused
    :param limit: Max number of results (default 5)
    :param config: Configuration identifier. Base filename without extension, filename with extension,
                   or values of `Имя`/`Синоним` from metadata index
    :return: Dict with status and result payload
    """
    result = metadata_returner.search_metadata(
        query, find_usages=find_usages, limit=limit, config=config
    )
    return result


if __name__ == "__main__":
    transport = "sse" if USESSE else "streamable-http"
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")

    logger.info(
        f"Starting MCP server with transport={transport}, host={host}, port={port}, path={path}"
    )
    mcp.run(transport=transport, host=host, port=port, path=path)
