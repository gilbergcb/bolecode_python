"""
monitor/scheduler.py — Orquestra os jobs com APScheduler.

Jobs:
  - sync_pcprest      : a cada SYNC_INTERVAL_SECONDS (default 30s)
  - registrar_boletos : a cada 15s (após sync)
  - registrar_pix     : a cada 15s (PIX COBV)
  - writeback_oracle  : a cada 20s
  - consultar_pix     : a cada 60min (polling pagamentos PIX)
"""
from __future__ import annotations

import threading
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from loguru import logger

from src.config import SYNC_INTERVAL_SECONDS
from src.jobs.sync_pcprest import run_sync
from src.jobs.registrar_boletos import run_registrar
from src.jobs.writeback_oracle import run_writeback
from src.jobs.consultar_liquidados import run_consultar_liquidados
from src.jobs.registrar_pix import run_registrar_pix
from src.jobs.consultar_pix import run_consultar_pix

_scheduler: BackgroundScheduler | None = None
_status_lock = threading.Lock()
_last_status: dict = {
    "sync": "aguardando",
    "registrar": "aguardando",
    "registrar_pix": "aguardando",
    "writeback": "aguardando",
    "consultar_pix": "aguardando",
    "sync_count": 0,
    "registrar_count": 0,
    "registrar_pix_count": 0,
    "writeback_count": 0,
    "consultar_pix_count": 0,
}
_job_callback: Callable[[str, str, int], None] | None = None


def set_job_callback(cb: Callable[[str, str, int], None]) -> None:
    """Registra callback (job_name, status, count) chamado ao fim de cada job."""
    global _job_callback
    _job_callback = cb


def _wrap(name: str, fn: Callable) -> Callable:
    """Envolve um job para atualizar status e logar erros."""
    def wrapper():
        with _status_lock:
            _last_status[name] = "executando"
        try:
            result = fn()
            count = result or 0
            with _status_lock:
                _last_status[name] = "ok"
                _last_status[f"{name}_count"] = count
            if _job_callback:
                _job_callback(name, "ok", count)
        except Exception as exc:
            with _status_lock:
                _last_status[name] = f"erro: {exc}"
            logger.error(f"Job '{name}' falhou: {exc}")
            if _job_callback:
                _job_callback(name, f"erro: {exc}", 0)
    return wrapper


def get_status() -> dict:
    with _status_lock:
        return dict(_last_status)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True, timezone="UTC")

    _scheduler.add_job(
        _wrap("sync", run_sync),
        "interval",
        seconds=SYNC_INTERVAL_SECONDS,
        id="sync_pcprest",
        next_run_time=None,  # primeira execução imediata abaixo
    )
    _scheduler.add_job(
        _wrap("registrar", run_registrar),
        "interval",
        seconds=15,
        id="registrar_boletos",
        next_run_time=None,
    )
    _scheduler.add_job(
        _wrap("registrar_pix", run_registrar_pix),
        "interval",
        seconds=15,
        id="registrar_pix",
        next_run_time=None,
    )
    _scheduler.add_job(
        _wrap("writeback", run_writeback),
        "interval",
        seconds=20,
        id="writeback_oracle",
        next_run_time=None,
    )
    _scheduler.add_job(
        _wrap("liquidados", run_consultar_liquidados),
        "interval",
        minutes=60,
        id="consultar_liquidados",
        next_run_time=None,
    )
    _scheduler.add_job(
        _wrap("consultar_pix", run_consultar_pix),
        "interval",
        minutes=60,
        id="consultar_pix",
        next_run_time=None,
    )

    _scheduler.start()
    logger.info("Scheduler iniciado.")

    # Dispara primeira execução imediatamente em thread separada
    threading.Thread(target=_initial_run, daemon=True).start()


def _initial_run():
    import time
    time.sleep(2)  # aguarda bancos iniciarem
    _wrap("sync", run_sync)()
    time.sleep(3)
    _wrap("registrar", run_registrar)()
    time.sleep(1)
    _wrap("registrar_pix", run_registrar_pix)()
    time.sleep(3)
    _wrap("writeback", run_writeback)()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler parado.")
