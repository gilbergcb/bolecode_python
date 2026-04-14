"""SchedulerCard — widget para status de um job do APScheduler."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel

from src.desktop.theme import COLORS


class SchedulerCard(QFrame):
    """Card com nome do job, status com dot colorido e contagem."""

    STATUS_COLORS = {
        "ok": "green",
        "executando": "yellow",
        "aguardando": "muted",
        "erro": "red",
    }

    def __init__(self, job_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self._job_name = job_name
        self.setObjectName("SchedulerCard")
        self.setStyleSheet(f"""
            QFrame#SchedulerCard {{
                background: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px;
                min-width: 180px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._name_label = QLabel(display_name)
        self._name_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 13px; font-weight: bold;"
        )

        # Status row: dot + text
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        self._dot = QLabel("\u2B24")  # filled circle
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color: {COLORS['muted']}; font-size: 10px;")

        self._status_label = QLabel("aguardando")
        self._status_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")

        status_row.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self._status_label, 1)

        # Count
        self._count_label = QLabel("0 processados")
        self._count_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px;")

        layout.addWidget(self._name_label)
        layout.addLayout(status_row)
        layout.addWidget(self._count_label)

    def update_status(self, status: str, count: int) -> None:
        """Atualiza status e contagem do job."""
        if status.startswith("erro"):
            color_key = "erro"
        else:
            color_key = status if status in self.STATUS_COLORS else "aguardando"

        color = COLORS.get(self.STATUS_COLORS[color_key], COLORS["muted"])
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._count_label.setText(f"{count} processados")
