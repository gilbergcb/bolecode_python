"""
main.py — Entry point do BOLECODE Desktop.

Ordem de boot:
  1. Configura loguru
  2. Valida configuracao (.env)
  3. Inicia pool Oracle (obrigatorio — staging + Winthor no mesmo banco)
  4. Cria QApplication (PySide6) com light theme
  5. Inicia APScheduler + registra callback → SignalHub
  6. Sobe FastAPI webhook-only em daemon thread
  7. Cria MainWindow, SystemTray, RefreshWorker
  8. app.exec() — bloqueia main thread

Uso:
  python main.py
"""
from __future__ import annotations

import sys
import signal
import threading
import time

import uvicorn
from loguru import logger

# ── Configura logger ──────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
    colorize=True,
)
logger.add(
    "logs/bolecode.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="DEBUG",
    encoding="utf-8",
)

# ── Importa modulos (apos logger) ────────────────────────────────────────────
from src import config
from src.db.oracle import init_oracle, close_oracle
from src.monitor.scheduler import (
    start_scheduler, stop_scheduler, set_job_callback,
)
from src.ui.api_routes import app as fastapi_app


def _start_webhook_server() -> threading.Thread:
    """Sobe FastAPI webhook-only em daemon thread."""
    cfg = uvicorn.Config(
        fastapi_app,
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True, name="webhook")
    t.start()
    logger.info(
        f"Webhook server em http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}"
    )
    return t


def _graceful_shutdown():
    logger.info("Iniciando shutdown gracioso...")
    stop_scheduler()
    close_oracle()
    logger.info("BOLECODE encerrado.")


def main():
    logger.info("=" * 50)
    logger.info("  BOLECODE — Desktop Monitor de Cobranca")
    logger.info(f"  Ambiente: {config.BRADESCO_ENV.upper()}")
    logger.info(f"  Oracle:   {config.ORACLE_HOST}:{config.ORACLE_PORT}/{config.ORACLE_SERVICE}")
    logger.info("=" * 50)

    # 1. Oracle (obrigatorio — staging + Winthor no mesmo banco)
    try:
        init_oracle()
    except Exception as e:
        logger.critical(f"Falha ao conectar Oracle: {e}")
        sys.exit(1)

    # 2. PySide6 app (importa aqui pra nao falhar se PySide6 ausente)
    from src.desktop.app import BolecodeApp

    bolecode = BolecodeApp()

    # Permite Ctrl+C matar o Qt event loop
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # 3. Scheduler + callback → SignalHub
    def _job_cb(name: str, status: str, count: int):
        bolecode.hub.job_completed.emit(name, status, count)

    set_job_callback(_job_cb)
    start_scheduler()

    # 4. Webhook server
    _start_webhook_server()
    time.sleep(0.5)

    # 5. Run desktop app (bloqueia main thread)
    logger.info("Iniciando desktop PySide6...")
    exit_code = bolecode.run(environment=config.BRADESCO_ENV)

    # 6. Shutdown
    _graceful_shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
