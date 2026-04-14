"""
jobs/registrar_pix.py — Consome fila PIX_COBV e registra no Bradesco.

Fluxo por titulo:
1. Reserva o registro (status -> PROCESSANDO)
2. Gera txid unico (35 chars alfanumerico)
3. Monta payload com dados do Oracle (dados_oracle CLOB)
4. Chama API PIX Bradesco (criar_cobv_emv)
5. Salva retorno (txid, pixCopiaECola, imagemQrcode)
6. Status -> REGISTRADO (ou ERRO se falhar)
"""
from __future__ import annotations

import json
from datetime import datetime

from loguru import logger

from src.db.oracle import stg_query, stg_execute, log_service_event
from src.config import MAX_TENTATIVAS

from pathlib import Path
from src import config as _cfg


def _pix_ready() -> bool:
    """Verifica se certificados e chave PIX existem antes de tentar registrar."""
    try:
        cert = Path(_cfg.BRADESCO_CERT_PEM)
        key = Path(_cfg.BRADESCO_KEY_PEM)
        alias_pix = _cfg.BRADESCO_ALIAS_PIX
        if not cert.exists() or not key.exists():
            return False
        if not alias_pix:
            return False
        return True
    except Exception:
        return False


def _parse_dados(dados_oracle) -> dict:
    if isinstance(dados_oracle, str):
        return json.loads(dados_oracle)
    if dados_oracle is None:
        return {}
    if hasattr(dados_oracle, "read"):
        return json.loads(dados_oracle.read())
    return dados_oracle


def run_registrar_pix() -> int:
    """Processa titulos PIX_COBV pendentes. Retorna qtd processada."""
    if not _pix_ready():
        return 0

    pendentes = stg_query(
        """
        SELECT * FROM (
            SELECT id, numtransvenda, prest, duplic, codfilial, numcar,
                   dtemissao, dtvenc, valor, codcob, dados_oracle,
                   tx_id, tentativas
            FROM boletos
            WHERE status IN ('PENDENTE', 'ERRO')
              AND NVL(modo_cobranca, 'BOLETO_HIBRIDO') = 'PIX_COBV'
              AND tentativas < :max_tent
            ORDER BY dtvenc ASC
        ) WHERE ROWNUM <= 20
        """,
        {"max_tent": MAX_TENTATIVAS},
    )

    if not pendentes:
        return 0

    processados = 0
    for b in pendentes:
        _processar_pix(b)
        processados += 1

    return processados


def _processar_pix(b: dict) -> None:
    from src.api.pix_client import criar_cobv_emv, gerar_txid, PixAPIError

    bid = b["id"]
    dados = _parse_dados(b["dados_oracle"])

    # Marca como PROCESSANDO
    affected = stg_execute(
        """
        UPDATE boletos SET status='PROCESSANDO', tentativas = tentativas + 1
        WHERE id = :bid AND status IN ('PENDENTE', 'ERRO')
        """,
        {"bid": bid},
    )
    if not affected:
        return

    # Gera txid se nao existe
    txid = b["tx_id"] or gerar_txid()
    if not b["tx_id"]:
        stg_execute(
            "UPDATE boletos SET tx_id = :txid WHERE id = :bid",
            {"txid": txid, "bid": bid},
        )

    # Dados do devedor vindos do Oracle
    nome = dados.get("nome_cliente", "CLIENTE")
    cpf_cnpj_raw = str(dados.get("cpf_cnpj", "00000000000")).replace(".", "").replace("/", "").replace("-", "")
    logradouro = dados.get("endereco", "")
    municipio = dados.get("municipio", "")
    uf = str(dados.get("uf", ""))[:2]
    cep = str(dados.get("cep", "")).replace("-", "").replace(".", "")

    seu_numero = f"{b['duplic'] or b['numtransvenda']}-{b['prest']}"
    data_vencimento = b["dtvenc"]
    valor = float(b["valor"])

    payload_enviado = {
        "txid": txid,
        "seu_numero": seu_numero,
        "data_vencimento": str(data_vencimento),
        "valor": valor,
        "modo": "PIX_COBV",
    }

    try:
        resp = criar_cobv_emv(
            txid=txid,
            data_vencimento=data_vencimento,
            valor=valor,
            nome_devedor=nome,
            cpf_cnpj_devedor=cpf_cnpj_raw,
            logradouro=logradouro,
            cidade=municipio,
            uf=uf,
            cep=cep,
            solicitacao_pagador=f"Ref: {seu_numero}",
        )

        pix_copia_e_cola = resp.get("pixCopiaECola", "")
        qr_image = resp.get("imagemQrcode", "")
        loc_location = ""
        if resp.get("loc"):
            loc_location = resp["loc"].get("location", "")
        status_cobv = resp.get("status", "")

        stg_execute(
            """
            UPDATE boletos SET
                status              = 'REGISTRADO',
                tx_id               = :txid,
                pix_copia_e_cola    = :pix_copia_e_cola,
                qrcode_emv          = :qrcode_emv,
                qr_image_base64     = :qr_image,
                dt_registro_bradesco = :dt_reg,
                payload_enviado     = :payload_env,
                payload_recebido    = :payload_rec,
                ultimo_erro         = NULL
            WHERE id = :bid
            """,
            {
                "txid": txid,
                "pix_copia_e_cola": pix_copia_e_cola,
                "qrcode_emv": pix_copia_e_cola,  # compativel com QR dialog
                "qr_image": qr_image if qr_image else None,
                "dt_reg": datetime.utcnow(),
                "payload_env": json.dumps(payload_enviado),
                "payload_rec": json.dumps(resp),
                "bid": bid,
            },
        )
        logger.success(
            f"PIX COBV registrado: {b['numtransvenda']}/{b['prest']} "
            f"txid={txid} emv={'sim' if pix_copia_e_cola else 'nao'}"
        )
        log_service_event("INFO", "PIX COBV registrado no Bradesco", {
            "numtransvenda": b["numtransvenda"],
            "txid": txid,
            "pix_copia_e_cola": bool(pix_copia_e_cola),
        })

    except PixAPIError as exc:
        _marcar_erro(bid, f"PIX API {exc.status_code}: {exc.body}", payload_enviado)
    except Exception as exc:
        _marcar_erro(bid, str(exc), payload_enviado)


def _marcar_erro(bid, msg: str, payload: dict) -> None:
    logger.error(f"Erro ao registrar PIX COBV {bid}: {msg}")
    stg_execute(
        """
        UPDATE boletos SET
            status          = 'ERRO',
            ultimo_erro     = :erro,
            payload_enviado = :payload
        WHERE id = :bid
        """,
        {"erro": msg[:4000], "payload": json.dumps(payload), "bid": bid},
    )
    log_service_event("ERROR", "Falha ao registrar PIX COBV", {"id": str(bid), "erro": msg[:500]})
