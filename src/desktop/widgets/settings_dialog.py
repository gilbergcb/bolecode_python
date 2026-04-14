"""SettingsDialog — dialog para configurar conexao e parametros do BOLECODE."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QWidget,
    QMessageBox, QFileDialog, QComboBox, QSpinBox,
)

from src.desktop.theme import COLORS
from src.desktop.widgets.cobranca_tab import CobrancaTab


def _env_path() -> Path:
    """Retorna caminho do .env na raiz do projeto."""
    # Sobe a partir de src/desktop/widgets ate a raiz
    return Path(__file__).resolve().parents[3] / ".env"


def _load_env_dict() -> dict:
    """Le o .env e retorna como dict."""
    env = {}
    path = _env_path()
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def _save_env_dict(env: dict) -> None:
    """Salva dict como .env preservando comentarios e ordem."""
    path = _env_path()
    lines = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
        seen = set()
        for line in existing:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in env:
                    lines.append(f"{key}={env[key]}")
                    seen.add(key)
                else:
                    lines.append(line)
            else:
                lines.append(line)
        # Adiciona chaves novas
        for key, val in env.items():
            if key not in seen:
                lines.append(f"{key}={val}")
    else:
        for key, val in env.items():
            lines.append(f"{key}={val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class SettingsDialog(QDialog):
    """Dialog de configuracao com tabs: Oracle, Bradesco, Winthor, Cobranca, Jobs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuracoes — BOLECODE")
        self.setMinimumWidth(580)
        self.setMinimumHeight(520)

        self._fields: dict[str, QLineEdit | QComboBox | QSpinBox] = {}
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        tabs = QTabWidget()

        # ── Tab Oracle ─────────────────────────
        oracle_tab = QWidget()
        oracle_form = QFormLayout(oracle_tab)
        oracle_form.setSpacing(10)

        self._add_field(oracle_form, "ORACLE_HOST", "Host", "192.168.56.102")
        self._add_field(oracle_form, "ORACLE_PORT", "Porta", "1521")
        self._add_field(oracle_form, "ORACLE_SERVICE", "Service Name", "LOCAL")
        self._add_field(oracle_form, "ORACLE_USER", "Usuario", "BOLECODE")
        self._add_field(oracle_form, "ORACLE_PASSWORD", "Senha", "", password=True)
        self._add_field_with_browse(oracle_form, "ORACLE_INSTANT_CLIENT_DIR",
                                     "Instant Client Dir")

        tabs.addTab(oracle_tab, "Oracle")

        # ── Tab Bradesco ───────────────────────
        bradesco_tab = QWidget()
        bradesco_form = QFormLayout(bradesco_tab)
        bradesco_form.setSpacing(10)

        env_combo = QComboBox()
        env_combo.addItems(["sandbox", "producao"])
        self._fields["BRADESCO_ENV"] = env_combo
        bradesco_form.addRow("Ambiente:", env_combo)

        self._add_field(bradesco_form, "BRADESCO_CLIENT_ID", "Client ID")
        self._add_field(bradesco_form, "BRADESCO_CLIENT_SECRET", "Client Secret", password=True)
        self._add_field_with_browse(bradesco_form, "BRADESCO_CERT_PEM", "Certificado PEM",
                                     filter_str="PEM (*.pem);;All (*)")
        self._add_field_with_browse(bradesco_form, "BRADESCO_KEY_PEM", "Chave PEM",
                                     filter_str="PEM (*.pem *.key);;All (*)")
        self._add_field(bradesco_form, "BRADESCO_CERT_PASSPHRASE", "Passphrase Cert",
                        password=True)

        tabs.addTab(bradesco_tab, "Bradesco")

        # ── Tab Beneficiario ───────────────────
        benef_tab = QWidget()
        benef_form = QFormLayout(benef_tab)
        benef_form.setSpacing(10)

        self._add_field(benef_form, "BRADESCO_NRO_CPF_CNPJ_BENEF", "CNPJ Raiz (8 dig)")
        self._add_field(benef_form, "BRADESCO_FIL_CPF_CNPJ_BENEF", "Filial CNPJ (4 dig)")
        self._add_field(benef_form, "BRADESCO_DIG_CPF_CNPJ_BENEF", "DV CNPJ (2 dig)")
        self._add_field(benef_form, "BRADESCO_CIDTFD_PROD_COBR", "Produto Cobranca", "09")
        self._add_field(benef_form, "BRADESCO_CNEGOC_COBR", "Ag+Conta (18 dig)")
        self._add_field(benef_form, "BRADESCO_CESSPE_TITULO_COBR", "Especie Titulo", "25")
        self._add_field(benef_form, "BRADESCO_ALIAS_PIX", "Chave PIX")

        tabs.addTab(benef_tab, "Beneficiario")

        # ── Tab Cobranca ───────────────────────
        self._cobranca_tab = CobrancaTab()
        tabs.addTab(self._cobranca_tab, "Cobranca")

        # ── Tab Winthor / Jobs ─────────────────
        jobs_tab = QWidget()
        jobs_form = QFormLayout(jobs_tab)
        jobs_form.setSpacing(10)

        self._add_field(jobs_form, "WINTHOR_CODCOB", "Cod Cobranca", "237")
        self._add_field(jobs_form, "WINTHOR_CODFILIAL", "Cod Filial", "1")

        jobs_form.addRow(QLabel(""))  # spacer

        sync_spin = QSpinBox()
        sync_spin.setRange(5, 300)
        sync_spin.setSuffix(" seg")
        sync_spin.setValue(30)
        self._fields["SYNC_INTERVAL_SECONDS"] = sync_spin
        jobs_form.addRow("Intervalo Sync:", sync_spin)

        tent_spin = QSpinBox()
        tent_spin.setRange(1, 10)
        tent_spin.setValue(3)
        self._fields["MAX_TENTATIVAS"] = tent_spin
        jobs_form.addRow("Max Tentativas:", tent_spin)

        self._add_field(jobs_form, "DASHBOARD_HOST", "Webhook Host", "127.0.0.1")
        self._add_field(jobs_form, "DASHBOARD_PORT", "Webhook Porta", "8765")

        tabs.addTab(jobs_tab, "Winthor / Jobs")

        layout.addWidget(tabs)

        # ── Botoes ─────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_test = QPushButton("Testar Conexao")
        btn_test.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white; border: none;
                padding: 10px 20px; border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #1d4ed8; }}
        """)
        btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(btn_test)

        btn_save = QPushButton("Salvar")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['green']};
                color: white; border: none;
                padding: 10px 20px; border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #15803d; }}
        """)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def _add_field(self, form: QFormLayout, key: str, label: str,
                   default: str = "", password: bool = False) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(default)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self._fields[key] = field
        form.addRow(f"{label}:", field)
        return field

    def _add_field_with_browse(self, form: QFormLayout, key: str, label: str,
                                filter_str: str = "") -> None:
        row = QHBoxLayout()
        field = QLineEdit()
        self._fields[key] = field
        row.addWidget(field, 1)

        btn = QPushButton("...")
        btn.setFixedWidth(36)

        def browse():
            if filter_str:
                path, _ = QFileDialog.getOpenFileName(self, label, "", filter_str)
            else:
                path = QFileDialog.getExistingDirectory(self, label)
            if path:
                field.setText(path)

        btn.clicked.connect(browse)
        row.addWidget(btn)

        form.addRow(f"{label}:", row)

    def _load_values(self) -> None:
        env = _load_env_dict()
        for key, widget in self._fields.items():
            val = env.get(key, "")
            if isinstance(widget, QComboBox):
                idx = widget.findText(val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(val))
                except (ValueError, TypeError):
                    pass
            else:
                widget.setText(val)

    def _collect_values(self) -> dict:
        env = _load_env_dict()
        for key, widget in self._fields.items():
            if isinstance(widget, QComboBox):
                env[key] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                env[key] = str(widget.value())
            else:
                text = widget.text().strip()
                if text:
                    env[key] = text
        return env

    def _test_connection(self) -> None:
        host = self._fields["ORACLE_HOST"].text() or "192.168.56.102"
        port = self._fields["ORACLE_PORT"].text() or "1521"
        service = self._fields["ORACLE_SERVICE"].text() or "LOCAL"
        user = self._fields["ORACLE_USER"].text() or "BOLECODE"
        password = self._fields["ORACLE_PASSWORD"].text()
        ic_dir = self._fields["ORACLE_INSTANT_CLIENT_DIR"].text()

        try:
            import oracledb
            if ic_dir:
                try:
                    oracledb.init_oracle_client(lib_dir=ic_dir)
                except Exception:
                    pass
            dsn = oracledb.makedsn(host, int(port), service_name=service)
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
            cur = conn.cursor()
            cur.execute("SELECT 'OK' FROM DUAL")
            result = cur.fetchone()[0]
            cur.close()
            conn.close()
            QMessageBox.information(self, "Conexao OK",
                                    f"Conectado com sucesso!\n{user}@{host}:{port}/{service}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Conexao", str(e))

    def _save(self) -> None:
        # Salva tab Cobranca (Oracle CONFIGURACOES)
        if not self._cobranca_tab.save():
            return  # erro ou conflito na tab Cobranca

        # Salva .env
        env = self._collect_values()
        try:
            _save_env_dict(env)
            QMessageBox.information(
                self, "Salvo",
                f"Configuracoes salvas em:\n{_env_path()}\n\n"
                "Parametros de cobranca salvos no Oracle.\n"
                "Reinicie o app para aplicar as mudancas."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Nao foi possivel salvar:\n{e}")
