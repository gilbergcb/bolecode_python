"""BolecodeApp — orquestracao do aplicativo desktop PySide6."""

from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from src.desktop.theme import LIGHT_THEME, DARK_THEME
from src.desktop.signals import SignalHub
from src.desktop.main_window import MainWindow
from src.desktop.tray import SystemTray
from src.desktop.services.refresh_worker import RefreshWorker


class BolecodeApp:
    """Orquestra criacao de widgets, signals/slots e lifecycle."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("BOLECODE")
        self.app.setStyleSheet(LIGHT_THEME)
        self.app.setQuitOnLastWindowClosed(False)

        # Signal hub
        self.hub = SignalHub()

        # Main window
        self.window = MainWindow()

        # System tray
        self.tray = SystemTray(parent=None)

        # Refresh worker
        self.worker = RefreshWorker(self.hub, interval_ms=15_000)

        self._connect_signals()

    def _connect_signals(self) -> None:
        # Hub → Dashboard tab
        self.hub.kpis_updated.connect(self.window.dashboard_tab.update_all)

        # Hub → Logs tab
        self.hub.logs_updated.connect(self.window.logs_tab.update_data)

        # Hub → Status bar timestamp
        self.hub.kpis_updated.connect(self._on_data_refreshed)

        # Hub → Connection status
        self.hub.service_status_changed.connect(self.window.set_connection_status)
        self.hub.service_status_changed.connect(self.tray.update_status)

        # Hub → Toast notifications
        self.hub.boleto_registered.connect(self._on_boleto_registered)
        self.hub.payment_received.connect(self._on_payment_received)
        self.hub.error_occurred.connect(self._on_error)

        # Tray → Window
        self.tray.show_requested.connect(self._show_window)
        self.tray.quit_requested.connect(self._quit)
        self.tray.pause_toggled.connect(self._on_pause_toggled)

    def _on_data_refreshed(self, data: dict) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.window.set_last_update(f"Ultima atualizacao: {now}")

    def _on_boleto_registered(self, numtransvenda: str, prest: str) -> None:
        self.tray.notify(
            "Boleto Registrado",
            f"Venda {numtransvenda} / {prest} registrado com sucesso.",
        )

    def _on_payment_received(self, nosso_numero: str, valor: float) -> None:
        self.tray.notify(
            "Pagamento Recebido",
            f"Nosso numero {nosso_numero} — R$ {valor:,.2f}",
            QSystemTrayIcon.MessageIcon.Information,
        )

    def _on_error(self, context: str, message: str) -> None:
        self.tray.notify(
            f"Erro: {context}",
            message,
            QSystemTrayIcon.MessageIcon.Warning,
        )

    def _on_pause_toggled(self, paused: bool) -> None:
        if paused:
            self.worker.stop()
        else:
            self.worker.start()

    def _show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit(self) -> None:
        self.worker.stop()
        self.window.set_close_to_tray(False)
        self.tray.hide()
        self.app.quit()

    def run(self, environment: str = "SANDBOX") -> int:
        """Inicia o app. Retorna exit code."""
        self.window.set_environment(environment)
        self.tray.show()
        self.window.show()
        self.worker.start()
        return self.app.exec()
