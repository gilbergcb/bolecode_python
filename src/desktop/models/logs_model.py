"""LogsTableModel — QAbstractTableModel para a tabela de logs."""

from __future__ import annotations

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor


COLUMNS = [
    ("created_at", "Data/Hora"),
    ("nivel", "Nivel"),
    ("mensagem", "Mensagem"),
]

NIVEL_COLORS = {
    "INFO": "#60a5fa",
    "WARNING": "#eab308",
    "ERROR": "#ef4444",
    "CRITICAL": "#ef4444",
    "DEBUG": "#64748b",
}


class LogsTableModel(QAbstractTableModel):
    """Model para QTableView de logs do service_log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_data(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None

        row = self._rows[index.row()]
        key = COLUMNS[index.column()][0]
        value = row.get(key, "")

        if role == Qt.ItemDataRole.DisplayRole:
            return str(value) if value is not None else ""

        if role == Qt.ItemDataRole.ForegroundRole and key == "nivel":
            return QColor(NIVEL_COLORS.get(str(value), "#e2e8f0"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key == "mensagem":
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter

        return None
