"""
api/pix_client.py — Cliente HTTP para API PIX Cobranca Bradesco (COBV).

Endpoints COBV (Cobranca com Vencimento):
  - PUT   /v2/cobv/{txid}      -> Criar cobranca com vencimento
  - PUT   /v2/cobv-emv/{txid}  -> Criar COBV + EMV + imagem QR base64
  - GET   /v2/cobv/{txid}      -> Consultar cobranca
  - PATCH /v2/cobv/{txid}      -> Revisar cobranca

Host producao: qrpix.bradesco.com.br (diferente do boleto)
Token endpoint: /auth/server/oauth/token (diferente do boleto)
"""
from __future__ import annotations

import time
from datetime import datetime, date
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
import logging

from src import config
from src.db.oracle import next_nosso_numero

# Token cache PIX (separado do token boleto — endpoint diferente em producao)
_pix_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}
PIX_TOKEN_TTL = 55 * 60  # renova 5 min antes da expiracao de 1h


class PixAPIError(Exception):
    """Erro retornado pela API PIX do Bradesco."""
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        super().__init__(f"PIX API {status_code}: {body}")


def _build_mtls_client() -> httpx.Client:
    """Cria client HTTP com mTLS (mesmo certificado do boleto)."""
    cert = (str(config.BRADESCO_CERT_PEM), str(config.BRADESCO_KEY_PEM))
    if config.BRADESCO_CERT_PASSPHRASE:
        cert = (str(config.BRADESCO_CERT_PEM), str(config.BRADESCO_KEY_PEM),
                config.BRADESCO_CERT_PASSPHRASE)
    return httpx.Client(cert=cert, timeout=30.0, http2=True)


def _get_pix_token() -> str:
    """Obtem Bearer Token para API PIX (endpoint dedicado)."""
    now = time.time()
    if _pix_token_cache["token"] and now < _pix_token_cache["expires_at"]:
        return _pix_token_cache["token"]

    url = config.PIX_TOKEN_URL
    with _build_mtls_client() as client:
        resp = client.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": config.BRADESCO_CLIENT_ID,
                "client_secret": config.BRADESCO_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    resp.raise_for_status()
    body = resp.json()
    token = body["access_token"]
    _pix_token_cache["token"] = token
    _pix_token_cache["expires_at"] = now + PIX_TOKEN_TTL
    logger.debug("Bearer Token PIX renovado.")
    return token


def _pix_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_pix_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logging.getLogger("bolecode"), logging.WARNING),
)
def _pix_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Executa request generico na API PIX."""
    url = f"{config.PIX_BASE_URL}{path}"
    with _build_mtls_client() as client:
        if method == "PUT":
            resp = client.put(url, json=payload, headers=_pix_headers())
        elif method == "PATCH":
            resp = client.patch(url, json=payload, headers=_pix_headers())
        elif method == "GET":
            resp = client.get(url, headers=_pix_headers())
        else:
            raise ValueError(f"Metodo HTTP nao suportado: {method}")

    if resp.status_code in (200, 201):
        return resp.json()

    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    raise PixAPIError(resp.status_code, body)


# ── Gerar txid ───────────────────────────────────────────────────────────────

def gerar_txid() -> str:
    """
    Gera txid unico para PIX COBV (26-35 chars alfanumerico).
    Formato: YYYYMMDDHHMMSS(14) + CNPJ_RAIZ(8) + SEQ(13) = 35 chars.
    """
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    cnpj = config.BRADESCO_NRO_CPF_CNPJ_BENEF[:8].ljust(8, "0")
    seq = next_nosso_numero().zfill(13)
    return f"{ts}{cnpj}{seq}"


# ── Operacoes COBV ───────────────────────────────────────────────────────────

def criar_cobv(
    txid: str,
    data_vencimento: date,
    valor: float,
    nome_devedor: str,
    cpf_cnpj_devedor: str,
    logradouro: str = "",
    cidade: str = "",
    uf: str = "",
    cep: str = "",
    validade_apos_vencimento: int | None = None,
    solicitacao_pagador: str = "",
) -> dict:
    """PUT /v2/cobv/{txid} — Cria cobranca com vencimento."""
    if validade_apos_vencimento is None:
        validade_apos_vencimento = config.PIX_VALIDADE_APOS_VENCIMENTO

    cpf_cnpj = cpf_cnpj_devedor.replace(".", "").replace("/", "").replace("-", "")
    is_cnpj = len(cpf_cnpj.lstrip("0")) > 11

    devedor = {"nome": nome_devedor[:200]}
    if is_cnpj:
        devedor["cnpj"] = cpf_cnpj[:14]
    else:
        devedor["cpf"] = cpf_cnpj[:11]
    if logradouro:
        devedor["logradouro"] = logradouro[:200]
    if cidade:
        devedor["cidade"] = cidade[:200]
    if uf:
        devedor["uf"] = uf[:2]
    if cep:
        devedor["cep"] = cep.replace("-", "")[:8]

    payload = {
        "calendario": {
            "dataDeVencimento": (
                data_vencimento.strftime("%Y-%m-%d")
                if isinstance(data_vencimento, date) else str(data_vencimento)
            ),
            "validadeAposVencimento": validade_apos_vencimento,
        },
        "devedor": devedor,
        "valor": {
            "original": f"{valor:.2f}",
        },
        "chave": config.BRADESCO_ALIAS_PIX,
        "solicitacaopagador": solicitacao_pagador[:140] if solicitacao_pagador else "",
    }
    return _pix_request("PUT", f"/v2/cobv/{txid}", payload)


def criar_cobv_emv(
    txid: str,
    data_vencimento: date,
    valor: float,
    nome_devedor: str,
    cpf_cnpj_devedor: str,
    logradouro: str = "",
    cidade: str = "",
    uf: str = "",
    cep: str = "",
    validade_apos_vencimento: int | None = None,
    solicitacao_pagador: str = "",
    nome_personalizacao_qr: str = "",
) -> dict:
    """PUT /v2/cobv-emv/{txid} — Cria COBV + retorna EMV + imagem QR base64."""
    if validade_apos_vencimento is None:
        validade_apos_vencimento = config.PIX_VALIDADE_APOS_VENCIMENTO

    cpf_cnpj = cpf_cnpj_devedor.replace(".", "").replace("/", "").replace("-", "")
    is_cnpj = len(cpf_cnpj.lstrip("0")) > 11

    devedor = {"nome": nome_devedor[:200]}
    if is_cnpj:
        devedor["cnpj"] = cpf_cnpj[:14]
    else:
        devedor["cpf"] = cpf_cnpj[:11]
    if logradouro:
        devedor["logradouro"] = logradouro[:200]
    if cidade:
        devedor["cidade"] = cidade[:200]
    if uf:
        devedor["uf"] = uf[:2]
    if cep:
        devedor["cep"] = cep.replace("-", "")[:8]

    payload = {
        "calendario": {
            "dataDeVencimento": (
                data_vencimento.strftime("%Y-%m-%d")
                if isinstance(data_vencimento, date) else str(data_vencimento)
            ),
            "validadeAposVencimento": validade_apos_vencimento,
        },
        "devedor": devedor,
        "valor": {
            "original": f"{valor:.2f}",
        },
        "chave": config.BRADESCO_ALIAS_PIX,
        "solicitacaopagador": solicitacao_pagador[:140] if solicitacao_pagador else "",
    }
    if nome_personalizacao_qr:
        payload["nomePersonalizacaoQr"] = nome_personalizacao_qr[:15]

    return _pix_request("PUT", f"/v2/cobv-emv/{txid}", payload)


def consultar_cobv(txid: str) -> dict:
    """GET /v2/cobv/{txid} — Consulta status da cobranca."""
    return _pix_request("GET", f"/v2/cobv/{txid}")


def revisar_cobv(txid: str, **campos) -> dict:
    """PATCH /v2/cobv/{txid} — Revisa cobranca (ex: cancelar)."""
    return _pix_request("PATCH", f"/v2/cobv/{txid}", campos)
