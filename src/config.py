"""
config.py — Carrega e valida todas as variáveis de ambiente.
Falha rápido no boot se algo obrigatório estiver faltando.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _req(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(f"Variável obrigatória ausente: {key}")
    return val


def _opt(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Oracle ────────────────────────────────────────────────────────────────────
ORACLE_HOST = _req("ORACLE_HOST")
ORACLE_PORT = int(_opt("ORACLE_PORT", "1521"))
ORACLE_SERVICE = _req("ORACLE_SERVICE")
ORACLE_USER = _req("ORACLE_USER")
ORACLE_PASSWORD = _req("ORACLE_PASSWORD")
ORACLE_INSTANT_CLIENT_DIR = _opt("ORACLE_INSTANT_CLIENT_DIR", "")

# ── PostgreSQL removido — staging migrado para Oracle schema BOLECODE ─────────

# ── Bradesco ──────────────────────────────────────────────────────────────────
BRADESCO_ENV = _opt("BRADESCO_ENV", "sandbox")
_BASE_URLS = {
    "sandbox": "https://openapisandbox.prebanco.com.br",
    "producao": "https://openapi.bradesco.com.br",
}
BRADESCO_BASE_URL = _BASE_URLS.get(BRADESCO_ENV, _BASE_URLS["sandbox"])

BRADESCO_CLIENT_ID = _req("BRADESCO_CLIENT_ID")
BRADESCO_CLIENT_SECRET = _req("BRADESCO_CLIENT_SECRET")
BRADESCO_CERT_PEM = Path(_req("BRADESCO_CERT_PEM"))
BRADESCO_KEY_PEM = Path(_req("BRADESCO_KEY_PEM"))
BRADESCO_CERT_PASSPHRASE = _opt("BRADESCO_CERT_PASSPHRASE")

# Dados do beneficiário
BRADESCO_NRO_CPF_CNPJ_BENEF = _req("BRADESCO_NRO_CPF_CNPJ_BENEF")
BRADESCO_FIL_CPF_CNPJ_BENEF = _req("BRADESCO_FIL_CPF_CNPJ_BENEF")
BRADESCO_DIG_CPF_CNPJ_BENEF = _req("BRADESCO_DIG_CPF_CNPJ_BENEF")
BRADESCO_CIDTFD_PROD_COBR = _opt("BRADESCO_CIDTFD_PROD_COBR", "09")
BRADESCO_CNEGOC_COBR = _req("BRADESCO_CNEGOC_COBR")
BRADESCO_CESSPE_TITULO_COBR = _opt("BRADESCO_CESSPE_TITULO_COBR", "25")
BRADESCO_ALIAS_PIX = _opt("BRADESCO_ALIAS_PIX", "")

# ── Winthor ───────────────────────────────────────────────────────────────────
WINTHOR_CODCOB = _opt("WINTHOR_CODCOB", "237")
WINTHOR_CODFILIAL = _opt("WINTHOR_CODFILIAL", "1")

# ── PIX Cobranca (COBV) ─────────────────────────────────────────────────────
PIX_BASE_URL = (
    "https://openapisandbox.prebanco.com.br"
    if BRADESCO_ENV == "sandbox"
    else "https://qrpix.bradesco.com.br"
)
PIX_TOKEN_URL = (
    "https://openapisandbox.prebanco.com.br/auth/server/oauth/token"
    if BRADESCO_ENV == "sandbox"
    else "https://qrpix.bradesco.com.br/auth/server/oauth/token"
)
PIX_VALIDADE_APOS_VENCIMENTO = int(_opt("PIX_VALIDADE_APOS_VENCIMENTO", "30"))

# ── Jobs ──────────────────────────────────────────────────────────────────────
SYNC_INTERVAL_SECONDS = int(_opt("SYNC_INTERVAL_SECONDS", "30"))
MAX_TENTATIVAS = int(_opt("MAX_TENTATIVAS", "3"))

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_HOST = _opt("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(_opt("DASHBOARD_PORT", "8765"))
DASHBOARD_SECRET = _opt("DASHBOARD_SECRET", "bolecode-dev-secret")

# ── Segurança ─────────────────────────────────────────────────────────────────
ENCRYPTION_KEY = _opt("ENCRYPTION_KEY", "dev-key-32-chars-nao-usar-prod!!")
