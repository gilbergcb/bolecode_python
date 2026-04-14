"""
jobs/sync_pcprest.py — Monitora PCPREST no Winthor (Oracle 19c).

Query: busca titulos com CODCOBs configurados (PCCOB.BOLETO='S' ou
PCCOB.DEPOSITOBANCARIO='S'), sem QR Code, nao pagos, vencimento
futuro ou ate 30 dias atras, e insere na tabela BOLETOS do schema
BOLECODE (mesmo Oracle).

A parametrizacao dos CODCOBs vem da tabela CONFIGURACOES,
gerenciada pelo Settings Dialog > tab Cobranca.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from loguru import logger

from src.db.oracle import (
    query_oracle, stg_execute, log_service_event,
    get_codcobs_boleto, get_codcobs_pix, get_codfiliais,
)
from src import config


# MERGE para idempotencia com MODO_COBRANCA
MERGE_BOLETO = """
MERGE INTO boletos tgt
USING (SELECT :numtransvenda AS ntv, :prest AS prest FROM DUAL) src
ON (tgt.numtransvenda = src.ntv AND tgt.prest = src.prest)
WHEN NOT MATCHED THEN INSERT
    (numtransvenda, prest, duplic, codcli, codfilial, numcar,
     dtemissao, dtvenc, valor, codcob, dados_oracle, status, modo_cobranca)
VALUES
    (:numtransvenda, :prest, :duplic, :codcli, :codfilial, :numcar,
     :dtemissao, :dtvenc, :valor, :codcob, :dados_oracle, 'PENDENTE', :modo_cobranca)
"""


def _serialize(val) -> object:
    """Torna qualquer valor Oracle JSON-serializavel."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, date):
        return val.isoformat()
    return val


def _build_in_binds(prefix: str, values: list[str]) -> tuple[str, dict]:
    """Gera placeholders bind para IN clause. Ex: ':c0,:c1' + {'c0':'237','c1':'BK'}."""
    binds = {}
    names = []
    for i, v in enumerate(values):
        key = f"{prefix}{i}"
        binds[key] = v
        names.append(f":{key}")
    return ",".join(names), binds


def _build_query(codcobs: list[str], filiais: list[str]) -> tuple[str, dict]:
    """Monta query com bind variables para IN clauses (sem SQL injection)."""
    in_codcob, binds_codcob = _build_in_binds("c", codcobs)
    in_filial, binds_filial = _build_in_binds("f", filiais)
    params = {**binds_codcob, **binds_filial}
    sql = f"""
        SELECT
            p.NUMTRANSVENDA,
            p.PREST,
            p.DUPLIC,
            p.CODCLI,
            p.CODFILIAL,
            p.NUMCAR,
            p.DTEMISSAO,
            p.DTVENC,
            p.VALOR,
            p.CODCOB,
            c.CLIENTE      AS NOME_CLIENTE,
            c.ENDERCOB     AS ENDERECO,
            c.CEPCOB       AS CEP,
            c.MUNICCOB     AS MUNICIPIO,
            c.ESTCOB       AS UF,
            c.CGCENT       AS CPF_CNPJ,
            c.TELCOB       AS TELEFONE
        FROM PCPREST p
        JOIN PCCLIENT c ON c.CODCLI = p.CODCLI
        WHERE p.CODCOB IN ({in_codcob})
          AND p.CODFILIAL IN ({in_filial})
          AND p.QRCODE_PIX IS NULL
          AND p.DTPAG IS NULL
          AND p.DTVENC >= TRUNC(SYSDATE) - 30
    """
    return sql, params


def run_sync() -> int:
    """Sincroniza novos titulos Winthor -> BOLECODE.BOLETOS. Retorna qtd inserida."""
    # Le CODCOBs configurados (CONFIGURACOES ou fallback .env)
    codcobs_boleto = get_codcobs_boleto()
    codcobs_pix = get_codcobs_pix()
    filiais = get_codfiliais()

    all_codcobs = codcobs_boleto + codcobs_pix
    if not all_codcobs:
        return 0

    # Set para lookup rapido de modo
    pix_set = set(codcobs_pix)

    try:
        query, params = _build_query(all_codcobs, filiais)
        rows = query_oracle(query, params)
    except Exception as exc:
        logger.error(f"Erro ao consultar Oracle: {exc}")
        log_service_event("ERROR", "Falha na consulta Oracle PCPREST", {"erro": str(exc)})
        return 0

    inserted = 0
    for row in rows:
        dados_oracle = {k: _serialize(v) for k, v in row.items()}
        codcob = str(row.get("codcob", ""))
        modo = "PIX_COBV" if codcob in pix_set else "BOLETO_HIBRIDO"

        try:
            affected = stg_execute(
                MERGE_BOLETO,
                {
                    "numtransvenda": row["numtransvenda"],
                    "prest": str(row["prest"]),
                    "duplic": row.get("duplic"),
                    "codcli": row.get("codcli"),
                    "codfilial": str(row.get("codfilial", "")),
                    "numcar": row.get("numcar"),
                    "dtemissao": row.get("dtemissao"),
                    "dtvenc": row.get("dtvenc"),
                    "valor": row.get("valor"),
                    "codcob": codcob,
                    "dados_oracle": json.dumps(dados_oracle),
                    "modo_cobranca": modo,
                },
            )
            if affected:
                inserted += 1
        except Exception as exc:
            logger.warning(f"Erro ao inserir boleto {row.get('numtransvenda')}: {exc}")

    if inserted:
        logger.info(f"sync_pcprest: {inserted} novo(s) titulo(s) enfileirado(s).")
        log_service_event("INFO", f"Sync PCPREST: {inserted} novos titulos", {
            "total_oracle": len(rows),
            "codcobs_boleto": codcobs_boleto,
            "codcobs_pix": codcobs_pix,
        })

    return inserted
