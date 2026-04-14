"""RefreshWorker — QTimer + QRunnable para refresh periodico dos dados."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, QRunnable, QThreadPool, Slot

from src.desktop.services.data_service import DataService
from src.desktop.signals import SignalHub


class _FetchTask(QRunnable):
    """Executa DataService.get_dashboard_data() em thread do pool."""

    def __init__(self, hub: SignalHub):
        super().__init__()
        self._hub = hub
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            data = DataService.get_dashboard_data()
            self._hub.kpis_updated.emit(data)
            self._hub.scheduler_updated.emit(data.get("scheduler", {}))
            self._hub.logs_updated.emit(data.get("logs", []))
            self._hub.service_status_changed.emit(True)
        except Exception as exc:
            self._hub.error_occurred.emit("refresh", str(exc))
            self._hub.service_status_changed.emit(False)


class RefreshWorker:
    """Gerencia QTimer que dispara refresh a cada N segundos."""

    def __init__(self, hub: SignalHub, interval_ms: int = 15_000):
        self._hub = hub
        self._pool = QThreadPool.globalInstance()
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._tick()  # refresh imediato
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_interval(self, ms: int) -> None:
        self._timer.setInterval(ms)

    def _tick(self) -> None:
        task = _FetchTask(self._hub)
        self._pool.start(task)
