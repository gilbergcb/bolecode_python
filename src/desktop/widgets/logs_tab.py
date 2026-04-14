"""LogsTab — tabela de logs do service_log."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QHeaderView, QPushButton,
)

from src.desktop.models.logs_model import LogsTableModel


class LogsTab(QWidget):
    """Tab com os ultimos logs do sistema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        from src.desktop.theme import COLORS
        title = QLabel("Logs do Sistema")
        title.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 16px; font-weight: bold;"
        )
        header.addWidget(title)

        self._lbl_count = QLabel("0 registros")
        self._lbl_count.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        header.addWidget(self._lbl_count)

        header.addStretch()

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; border: none;
                padding: 8px 18px; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_refresh.clicked.connect(self._manual_refresh)
        header.addWidget(btn_refresh)

        layout.addLayout(header)

        # Tabela
        self._model = LogsTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self._table, 1)

    def update_data(self, logs: list) -> None:
        """Atualiza a tabela com novos logs."""
        self._model.set_data(logs)
        self._lbl_count.setText(f"{len(logs)} registros")

    def _manual_refresh(self) -> None:
        from src.desktop.services.data_service import DataService
        data = DataService.get_dashboard_data()
        self.update_data(data.get("logs", []))
