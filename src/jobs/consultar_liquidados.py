"""
jobs/consultar_liquidados.py — Consulta boletos pagos na API Bradesco.

Usado como alternativa/complemento ao webhook para detectar pagamentos
e fazer a baixa automatica no Winthor.

Executa uma vez por hora (configuravel).
"""
from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from src.db.oracle import stg_query, stg_execute, execute_oracle, log_service_event
from src.api.bradesco_client import _post
from src import config


def run_consultar_liquidados() -> int:
    """Consulta boletos registrados e marca os pagos. Retorna qtd baixados."""

    registrados = stg_query(
        """
        SELECT id, numtransvenda, prest, nosso_numero, valor, dtvenc
        FROM boletos
        WHERE status = 'REGISTRADO'
          AND dtvenc >= SYSDATE - 90
          AND ROWNUM <= 100
        """
    )

    if not registrados:
        return 0

    hoje = date.today()
    data_ini = (hoje - timedelta(days=1)).strftime("%d%m%Y")
    data_fim = hoje.strftime("%d%m%Y")

    try:
        payload = {
            "nroCpfCnpjBenef": config.BRADESCO_NRO_CPF_CNPJ_BENEF,
            "filCpfCnpjBenef": config.BRADESCO_FIL_CPF_CNPJ_BENEF,
            "digCpfCnpjBenef": config.BRADESCO_DIG_CPF_CNPJ_BENEF,
            "cidtfdProdCobr": config.BRADESCO_CIDTFD_PROD_COBR,
            "codUsuario": "APISERVIC",
            "dataInicio": data_ini,
            "dataFim": data_fim,
            "nroPagina": 0,
        }
        resp = _post("/boleto-hibrido/cobranca-lista/v1/listar", payload)
    except Exception as exc:
        logger.warning(f"consultar_liquidados: erro na API: {exc}")
        return 0

    titulos_pagos = resp.get("titulos") or resp.get("listaTitulos") or []
    nossos_pagos = {
        str(t.get("nossoNumero") or t.get("ctitloCobrCdent", ""))
        for t in titulos_pagos
    }

    baixados = 0
    for b in registrados:
        nn = str(b["nosso_numero"] or "")
        if nn in nossos_pagos:
            _marcar_baixado(b)
            baixados += 1

    if baixados:
        logger.info(f"consultar_liquidados: {baixados} boleto(s) baixado(s).")
        log_service_event("INFO", f"Liquidados detectados: {baixados}", {
            "data_ini": data_ini, "data_fim": data_fim
        })

    return baixados


def _marcar_baixado(b: dict) -> None:
    stg_execute(
        "UPDATE boletos SET status = 'BAIXADO' WHERE id = :bid",
        {"bid": b["id"]},
    )
    try:
        execute_oracle(
            """
            UPDATE PCPREST
               SET DTPAG = TRUNC(SYSDATE)
            WHERE NUMTRANSVENDA = :n AND PREST = :p AND DTPAG IS NULL
            """,
            {"n": b["numtransvenda"], "p": str(b["prest"])},
        )
    except Exception as exc:
        logger.warning(f"Nao foi possivel marcar DTPAG no Oracle: {exc}")
