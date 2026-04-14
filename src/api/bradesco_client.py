"""
api/bradesco_client.py — Cliente HTTP para a API de Cobrança Bradesco.

Responsabilidades:
  - Gerenciar o Bearer Token (cache 55 min, renova antes de expirar)
  - mTLS com certificado PEM
  - Registro, consulta, baixa e cancelamento de boletos
  - Retry automático com back-off exponencial (tenacity)
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

# Token cache em memória — suficiente para processo único
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}

TOKEN_TTL_SECONDS = 55 * 60  # renova 5 min antes da expiração de 1h


def _build_mtls_client() -> httpx.Client:
    cert = (str(config.BRADESCO_CERT_PEM), str(config.BRADESCO_KEY_PEM))
    if config.BRADESCO_CERT_PASSPHRASE:
        # httpx aceita tupla (cert, key, password) para PEM com senha
        cert = (str(config.BRADESCO_CERT_PEM), str(config.BRADESCO_KEY_PEM),
                config.BRADESCO_CERT_PASSPHRASE)
    return httpx.Client(cert=cert, timeout=30.0, http2=True)


def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = f"{config.BRADESCO_BASE_URL}/auth/server-mtls/v2/token"
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
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + TOKEN_TTL_SECONDS
    logger.debug("Bearer Token Bradesco renovado.")
    return token


def _headers(extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logging.getLogger("bolecode"), logging.WARNING),
)
def _post(path: str, payload: dict, extra_headers: dict | None = None) -> dict:
    url = f"{config.BRADESCO_BASE_URL}{path}"
    with _build_mtls_client() as client:
        resp = client.post(url, json=payload, headers=_headers(extra_headers))

    if resp.status_code == 200:
        return resp.json()

    # Erros conhecidos do Bradesco
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    raise BradescoAPIError(resp.status_code, body)


class BradescoAPIError(Exception):
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Bradesco API {status_code}: {body}")


# ── Operações ────────────────────────────────────────────────────────────────

def _fmt_date(d: date | str) -> str:
    """Formata para dd.mm.aaaa exigido pela API."""
    if isinstance(d, str):
        return d  # já formatado
    return d.strftime("%d.%m.%Y")


def _valor_centavos(valor: float) -> str:
    """Converte decimal para inteiro em centavos sem separador."""
    return str(int(round(valor * 100)))


def registrar_boleto(
    nosso_numero: str,
    seu_numero: str,
    data_emissao: date,
    data_vencimento: date,
    valor: float,
    nome_sacado: str,
    endereco_sacado: str,
    numero_sacado: str,
    cep_sacado: str,
    complemento_cep: str,
    bairro_sacado: str,
    municipio_sacado: str,
    uf_sacado: str,
    ind_cpf_cnpj_sacado: str,
    cpf_cnpj_sacado: str,
    **kwargs: Any,
) -> dict:
    """
    Registra boleto híbrido (boleto + QR Code PIX).
    Retorna o body completo da resposta Bradesco.
    Campo importante no retorno: wqrcdPdraoMercd (EMV copy-paste).
    """
    payload = {
        "ctitloCobrCdent": nosso_numero,
        "registrarTitulo": "1",
        "codUsuario": "APISERVIC",
        "nroCpfCnpjBenef": config.BRADESCO_NRO_CPF_CNPJ_BENEF,
        "filCpfCnpjBenef": config.BRADESCO_FIL_CPF_CNPJ_BENEF,
        "digCpfCnpjBenef": config.BRADESCO_DIG_CPF_CNPJ_BENEF,
        "tipoAcesso": "2",
        "cidtfdProdCobr": config.BRADESCO_CIDTFD_PROD_COBR,
        "cnegocCobr": config.BRADESCO_CNEGOC_COBR,
        "codigoBanco": "237",
        "tipoRegistro": "001",
        "ctitloCliCdent": seu_numero[:25],
        "demisTitloCobr": _fmt_date(data_emissao),
        "dvctoTitloCobr": _fmt_date(data_vencimento),
        "cidtfdTpoVcto": "0",
        "cindcdEconmMoeda": "6",
        "vnmnalTitloCobr": _valor_centavos(valor),
        "qmoedaNegocTitlo": "0",
        "cespceTitloCobr": config.BRADESCO_CESSPE_TITULO_COBR,
        "cindcdAceitSacdo": "N",
        "cformaEmisPplta": "02",
        "cindcdPgtoParcial": "N",
        "qtdePgtoParcial": "000",
        "ptxJuroVcto": "0",
        "vdiaJuroMora": "00000000000000000",
        "qdiaInicJuro": "00",
        "pmultaAplicVcto": "000000",
        "vmultaAtrsoPgto": "0",
        "qdiaInicMulta": "00",
        "pdescBonifPgto01": "0",
        "vdescBonifPgto01": "0",
        "dlimDescBonif1": "",
        "pdescBonifPgto02": "0",
        "vdescBonifPgto02": "0",
        "dlimDescBonif2": "",
        "pdescBonifPgto03": "0",
        "vdescBonifPgto03": "0",
        "dlimDescBonif3": "",
        "vabtmtTitloCobr": "00000000000000000",
        "isacdoTitloCobr": nome_sacado[:40],
        "elogdrSacdoTitlo": endereco_sacado[:40],
        "enroLogdrSacdo": numero_sacado[:5],
        "ecomplLogdrSacdo": "",
        "ccepSacdoTitlo": cep_sacado[:5],
        "ccomplCepSacdo": complemento_cep[:3],
        "ebairoLogdrSacdo": bairro_sacado[:40],
        "imunSacdoTitlo": municipio_sacado[:20],
        "csglUfSacdo": uf_sacado[:2],
        "indCpfCnpjSacdo": ind_cpf_cnpj_sacado,
        "nroCpfCnpjSacdo": cpf_cnpj_sacado[:14],
        "fase": "1",
        "cindcdCobrMisto": "S",
        "ialiasAdsaoCta": config.BRADESCO_ALIAS_PIX,
        "validadeAposVencimento": "0",
        # Campos opcionais extras aceitos via kwargs
        **{k: v for k, v in kwargs.items()},
    }
    return _post(
        "/boleto-hibrido/cobranca-registro/v1/gerarBoleto",
        payload,
    )


def cancelar_boleto(
    cpf_cnpj: str,
    filial: str,
    controle: str,
    produto: int,
    negociacao: int,
    nosso_numero: str,
    codigo_baixa: int = 57,
) -> dict:
    payload = {
        "cpfCnpj": {
            "cpfCnpj": cpf_cnpj,
            "filial": filial,
            "controle": controle,
        },
        "produto": produto,
        "negociacao": negociacao,
        "nossoNumero": nosso_numero,
        "sequencia": 0,
        "codigoBaixa": codigo_baixa,
    }
    return _post("/boleto/cobranca-baixa/v1/baixar", payload)


def consultar_boleto(
    produto: int,
    cnpj_cpf_bnf: int,
    filial_cnpj: int,
    agencia: int,
    conta: int,
    controle_cnpj: int,
    nosso_numero: str | None = None,
) -> dict:
    payload = {
        "cidtfdProdCobr": produto,
        "cnpjCpfBnf": cnpj_cpf_bnf,
        "codUsuario": "APISERVIC",
        "cflialCnpjCpfBnf": filial_cnpj,
        "agenciaCobr": agencia,
        "contaCobr": conta,
        "cctrlCnpjCpfBnf": controle_cnpj,
    }
    if nosso_numero:
        payload["ctitloCobrCdent"] = nosso_numero
    return _post(
        "/boleto-hibrido/cobranca-consulta-titulo/v1/consultar", payload
    )
