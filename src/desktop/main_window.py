"""MainWindow — janela principal com tabs, toolbar e status bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QWidget,
    QToolBar, QPushButton, QSizePolicy, QMessageBox,
)

from src.desktop.theme import COLORS
from src.desktop.tray import _make_icon
from src.desktop.widgets.dashboard_tab import DashboardTab
from src.desktop.widgets.boletos_tab import BoletosTab
from src.desktop.widgets.erros_tab import ErrosTab
from src.desktop.widgets.logs_tab import LogsTab


class MainWindow(QMainWindow):
    """Janela principal do BOLECODE Desktop."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BOLECODE \u2014 Monitor de Cobranca")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setWindowIcon(_make_icon("#2563eb", "B"))

        self._close_to_tray = True
        self._build_ui()

    def _build_ui(self) -> None:
        # ── Toolbar ────────────────────────────
        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border']};
                spacing: 8px;
                padding: 4px 8px;
            }}
        """)

        toolbar.addWidget(QLabel("  BOLECODE  "))

        spacer = QWidget()
        spacer.setFixedWidth(1)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        # Spacer para empurrar botao para a direita
        stretch = QWidget()
        stretch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        stretch.setStyleSheet("background: transparent;")
        toolbar.addWidget(stretch)

        btn_settings = QPushButton("\u2699  Configuracoes")
        btn_settings.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {COLORS['border']};
            }}
        """)
        btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(btn_settings)

        self.addToolBar(toolbar)

        # ── Tabs ───────────────────────────────
        self.tabs = QTabWidget()

        self.dashboard_tab = DashboardTab()
        self.boletos_tab = BoletosTab()
        self.erros_tab = ErrosTab()
        self.logs_tab = LogsTab()

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.boletos_tab, "Boletos")
        self.tabs.addTab(self.erros_tab, "Erros")
        self.tabs.addTab(self.logs_tab, "Logs")

        self.setCentralWidget(self.tabs)

        # ── Status Bar ─────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._lbl_update = QLabel("Aguardando...")
        self._lbl_update.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")

        self._lbl_env = QLabel("")
        self._lbl_env.setStyleSheet("font-size: 12px; font-weight: bold;")

        self._lbl_conn = QLabel("")
        self._lbl_conn.setStyleSheet("font-size: 12px;")

        self._status_bar.addWidget(self._lbl_update, 1)
        self._status_bar.addPermanentWidget(self._lbl_env)
        self._status_bar.addPermanentWidget(self._lbl_conn)

    @Slot()
    def _open_settings(self) -> None:
        try:
            from src.desktop.widgets.settings_dialog import SettingsDialog
            dlg = SettingsDialog(parent=self)
            dlg.exec()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erro", f"Erro ao abrir configuracoes:\n{exc}")

    def set_environment(self, env: str) -> None:
        """Exibe ambiente (SANDBOX/PRODUCAO) na status bar."""
        if env.upper() in ("PRODUCAO", "PRODUCTION", "PROD"):
            self._lbl_env.setText("PRODUCAO")
            self._lbl_env.setStyleSheet(
                f"color: {COLORS['red']}; font-size: 12px; font-weight: bold;"
            )
        else:
            self._lbl_env.setText("SANDBOX")
            self._lbl_env.setStyleSheet(
                f"color: {COLORS['yellow']}; font-size: 12px; font-weight: bold;"
            )

    def set_connection_status(self, ok: bool) -> None:
        if ok:
            self._lbl_conn.setText("DB OK")
            self._lbl_conn.setStyleSheet(f"color: {COLORS['green']}; font-size: 12px;")
        else:
            self._lbl_conn.setText("DB ERRO")
            self._lbl_conn.setStyleSheet(f"color: {COLORS['red']}; font-size: 12px;")

    def set_last_update(self, text: str) -> None:
        self._lbl_update.setText(text)

    def set_close_to_tray(self, enabled: bool) -> None:
        self._close_to_tray = enabled

    def closeEvent(self, event) -> None:
        """Minimiza para tray ao inves de fechar."""
        if self._close_to_tray:
            event.ignore()
            self.hide()
        else:
            event.accept()
