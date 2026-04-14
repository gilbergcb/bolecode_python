"""BoletosTableModel — QAbstractTableModel para a tabela de boletos."""

from __future__ import annotations

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


COLUMNS = [
    ("numtransvenda", "Venda"),
    ("prest", "Prest"),
    ("codfilial", "Filial"),
    ("valor", "Valor"),
    ("status", "Status"),
    ("nosso_numero", "Nosso Numero"),
    ("dtvenc", "Vencimento"),
    ("created_at", "Criado em"),
]

STATUS_COLORS = {
    "PENDENTE": "#94a3b8",
    "PROCESSANDO": "#eab308",
    "REGISTRADO": "#22c55e",
    "ERRO": "#ef4444",
    "CANCELADO": "#64748b",
    "BAIXADO": "#60a5fa",
}


class BoletosTableModel(QAbstractTableModel):
    """Model para QTableView de boletos."""

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
            if key == "valor" and value is not None:
                return f"R$ {float(value):,.2f}"
            return str(value) if value is not None else ""

        if role == Qt.ItemDataRole.ForegroundRole and key == "status":
            from PySide6.QtGui import QColor
            return QColor(STATUS_COLORS.get(str(value), "#e2e8f0"))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key == "valor":
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def get_row(self, row_index: int) -> dict | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None
