"""Themes — Light e Dark para o BOLECODE Desktop."""

COLORS_DARK = {
    "bg": "#0d0f14",
    "surface": "#141720",
    "card": "#1a1e2e",
    "border": "#252a3a",
    "accent": "#2563eb",
    "green": "#22c55e",
    "yellow": "#eab308",
    "red": "#ef4444",
    "orange": "#f97316",
    "text": "#e2e8f0",
    "text_dim": "#94a3b8",
    "muted": "#64748b",
}

COLORS_LIGHT = {
    "bg": "#f8fafc",
    "surface": "#ffffff",
    "card": "#ffffff",
    "border": "#e2e8f0",
    "accent": "#2563eb",
    "green": "#16a34a",
    "yellow": "#ca8a04",
    "red": "#dc2626",
    "orange": "#ea580c",
    "text": "#1e293b",
    "text_dim": "#64748b",
    "muted": "#64748b",
}

# Alias ativo (pode ser trocado em runtime)
COLORS = COLORS_LIGHT

LIGHT_THEME = """
/* ── Global ─────────────────────────────── */
QWidget {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow { background-color: #f8fafc; }

/* ── Tabs ───────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    border-top: none;
}
QTabBar::tab {
    background: #ffffff;
    color: #64748b;
    padding: 10px 24px;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    font-size: 12px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #f8fafc;
    color: #2563eb;
    border-bottom: 2px solid #2563eb;
}
QTabBar::tab:hover { color: #1e293b; }

/* ── Tables ─────────────────────────────── */
QTableView {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    gridline-color: #f1f5f9;
    selection-background-color: rgba(37, 99, 235, 0.1);
    selection-color: #1e293b;
    alternate-background-color: #f8fafc;
}
QTableView::item { padding: 6px 12px; }
QHeaderView::section {
    background: #f1f5f9;
    color: #475569;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-size: 11px;
    font-weight: bold;
}

/* ── Buttons ────────────────────────────── */
QPushButton {
    background: #ffffff;
    color: #475569;
    border: 1px solid #e2e8f0;
    padding: 8px 18px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton:hover { background: #f1f5f9; color: #1e293b; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #cbd5e1; }

/* ── Inputs ─────────────────────────────── */
QComboBox, QLineEdit {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
}
QComboBox:focus, QLineEdit:focus { border-color: #2563eb; }
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    selection-background-color: #dbeafe;
    selection-color: #1e40af;
}

/* ── ScrollBars ─────────────────────────── */
QScrollBar:vertical {
    background: #f1f5f9;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #f1f5f9;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 4px;
    min-width: 20px;
}

/* ── StatusBar ──────────────────────────── */
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 12px;
}

/* ── ToolTip ────────────────────────────── */
QToolTip {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #64748b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

/* ── Label ──────────────────────────────── */
QLabel[class="muted"] { color: #64748b; font-size: 11px; }
QLabel[class="value"] { font-size: 28px; font-weight: bold; font-family: "Consolas", monospace; }
"""

DARK_THEME = """
/* ── Global ─────────────────────────────── */
QWidget {
    background-color: #0d0f14;
    color: #e2e8f0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow { background-color: #0d0f14; }

/* ── Tabs ───────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #252a3a;
    background: #0d0f14;
    border-top: none;
}
QTabBar::tab {
    background: #141720;
    color: #64748b;
    padding: 10px 24px;
    border: 1px solid #252a3a;
    border-bottom: none;
    font-size: 12px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #0d0f14;
    color: #2563eb;
    border-bottom: 2px solid #2563eb;
}
QTabBar::tab:hover { color: #e2e8f0; }

/* ── Tables ─────────────────────────────── */
QTableView {
    background-color: #1a1e2e;
    border: 1px solid #252a3a;
    gridline-color: rgba(255, 255, 255, 0.03);
    selection-background-color: rgba(37, 99, 235, 0.15);
    selection-color: #e2e8f0;
    alternate-background-color: #141720;
}
QTableView::item { padding: 6px 12px; }
QHeaderView::section {
    background: #141720;
    color: #64748b;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #252a3a;
    font-size: 11px;
    font-weight: bold;
}

/* ── Buttons ────────────────────────────── */
QPushButton {
    background: #1a1e2e;
    color: #94a3b8;
    border: 1px solid #252a3a;
    padding: 8px 18px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton:hover { background: #252a3a; color: #e2e8f0; }
QPushButton:pressed { background: #334155; }
QPushButton:disabled { color: #475569; }

/* ── Inputs ─────────────────────────────── */
QComboBox, QLineEdit {
    background: #1a1e2e;
    border: 1px solid #252a3a;
    color: #e2e8f0;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
}
QComboBox:focus, QLineEdit:focus { border-color: #2563eb; }
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #1a1e2e;
    border: 1px solid #252a3a;
    color: #e2e8f0;
    selection-background-color: #2563eb;
}

/* ── ScrollBars ─────────────────────────── */
QScrollBar:vertical {
    background: #141720;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #252a3a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #334155; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #141720;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #252a3a;
    border-radius: 4px;
    min-width: 20px;
}

/* ── StatusBar ──────────────────────────── */
QStatusBar {
    background: #141720;
    border-top: 1px solid #252a3a;
    color: #64748b;
    font-size: 12px;
}

/* ── ToolTip ────────────────────────────── */
QToolTip {
    background: #1a1e2e;
    color: #e2e8f0;
    border: 1px solid #252a3a;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1px solid #252a3a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #64748b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

/* ── Label ──────────────────────────────── */
QLabel[class="muted"] { color: #64748b; font-size: 11px; }
QLabel[class="value"] { font-size: 28px; font-weight: bold; font-family: "Consolas", monospace; }
"""
