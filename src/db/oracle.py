"""
db/oracle.py — Pool Oracle 19c (thick mode) + funcoes de staging.

Conexao unica ao Oracle Winthor. O schema BOLECODE contem as tabelas
de staging (boletos, service_log, configuracoes) e sinonimos para
PCPREST/PCCLIENT do Winthor.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import oracledb
from loguru import logger

from src.config import (
    ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE,
    ORACLE_USER, ORACLE_PASSWORD, ORACLE_INSTANT_CLIENT_DIR,
)

_pool: oracledb.ConnectionPool | None = None


# ── Pool lifecycle ────────────────────────────────────────────────────────────

def init_oracle() -> None:
    global _pool

    if ORACLE_INSTANT_CLIENT_DIR:
        try:
            oracledb.init_oracle_client(lib_dir=ORACLE_INSTANT_CLIENT_DIR)
            logger.info(f"Oracle Instant Client carregado: {ORACLE_INSTANT_CLIENT_DIR}")
        except Exception as exc:
            logger.debug(f"init_oracle_client: {exc}")

    dsn = oracledb.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
    _pool = oracledb.create_pool(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=dsn,
        min=2,
        max=10,
        increment=1,
    )
    _run_migrations()
    logger.info(f"Pool Oracle criado -> {ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}")


def get_pool() -> oracledb.ConnectionPool:
    if _pool is None:
        raise RuntimeError("Pool Oracle nao inicializado. Chame init_oracle() primeiro.")
    return _pool


@contextmanager
def get_conn():
    """Context manager: adquire conexao do pool, commit/rollback automatico."""
    pool = get_pool()
    conn = pool.acquire()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.release(conn)


def close_oracle() -> None:
    global _pool
    if _pool:
        _pool.close()
        _pool = None
        logger.info("Pool Oracle encerrado.")


# ── Query helpers ─────────────────────────────────────────────────────────────

def query_oracle(sql: str, params: dict | None = None) -> list[dict]:
    """Executa SELECT e retorna lista de dicts com chaves em minusculas."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c[0].lower() for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute_oracle(sql: str, params: dict | None = None) -> int:
    """Executa DML (INSERT/UPDATE/DELETE) e retorna rowcount."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            rowcount = cur.rowcount
            conn.commit()
            return rowcount


def insert_returning(sql: str, params: dict | None = None, returning_into: str = "id") -> Any:
    """Executa INSERT com RETURNING INTO e retorna o valor."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            var = cur.var(oracledb.STRING)
            p = dict(params or {})
            p[f"out_{returning_into}"] = var
            cur.execute(sql, p)
            conn.commit()
            return var.getvalue()[0] if var.getvalue() else None


def next_nosso_numero() -> str:
    """Retorna proximo valor da sequence como string de 11 digitos."""
    rows = query_oracle("SELECT SEQ_NOSSO_NUMERO.NEXTVAL AS val FROM DUAL")
    return str(int(rows[0]["val"])).zfill(11)


# ── Staging helpers (substituem pg_query/pg_execute) ──────────────────────────

def stg_query(sql: str, params: dict | None = None) -> list[dict]:
    """Alias de query_oracle para queries no schema BOLECODE."""
    return query_oracle(sql, params)


def stg_execute(sql: str, params: dict | None = None) -> int:
    """Alias de execute_oracle para DML no schema BOLECODE."""
    return execute_oracle(sql, params)


def log_service_event(nivel: str, mensagem: str, detalhe: dict | None = None) -> None:
    """Insere log no service_log. Nunca levanta excecao."""
    try:
        execute_oracle(
            """INSERT INTO service_log (nivel, mensagem, detalhe)
               VALUES (:nivel, :mensagem, :detalhe)""",
            {
                "nivel": nivel,
                "mensagem": mensagem[:4000],
                "detalhe": json.dumps(detalhe) if detalhe else None,
            },
        )
    except Exception:
        pass  # log de log nao pode travar o fluxo


# ── Migrations ────────────────────────────────────────────────────────────────

_MIGRATIONS = [
    # Tabela boletos (verifica existencia)
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'BOLETOS';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TABLE BOLETOS (
                ID                    RAW(16)        DEFAULT SYS_GUID() PRIMARY KEY,
                NUMTRANSVENDA         NUMBER(15)     NOT NULL,
                PREST                 VARCHAR2(2)    NOT NULL,
                DUPLIC                NUMBER(15),
                CODCLI                NUMBER(10),
                CODFILIAL             VARCHAR2(2),
                NUMCAR                NUMBER(10),
                DTEMISSAO             DATE,
                DTVENC                DATE,
                VALOR                 NUMBER(15,2),
                CODCOB                VARCHAR2(10),
                DADOS_ORACLE          CLOB,
                NOSSO_NUMERO          VARCHAR2(11),
                STATUS                VARCHAR2(20)   DEFAULT ''PENDENTE'' NOT NULL,
                TX_ID                 VARCHAR2(200),
                QRCODE_EMV            CLOB,
                LINHA_DIGITAVEL       VARCHAR2(100),
                COD_BARRAS            VARCHAR2(100),
                DT_REGISTRO_BRADESCO  TIMESTAMP WITH TIME ZONE,
                ORACLE_ATUALIZADO     NUMBER(1)      DEFAULT 0 NOT NULL,
                TENTATIVAS            NUMBER(3)      DEFAULT 0 NOT NULL,
                ULTIMO_ERRO           VARCHAR2(4000),
                PAYLOAD_ENVIADO       CLOB,
                PAYLOAD_RECEBIDO      CLOB,
                CREATED_AT            TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                UPDATED_AT            TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                CONSTRAINT UK_BOLETOS_VENDA_PREST UNIQUE (NUMTRANSVENDA, PREST),
                CONSTRAINT UK_BOLETOS_NOSSONR     UNIQUE (NOSSO_NUMERO)
            )';
            EXECUTE IMMEDIATE 'CREATE INDEX IDX_BOLETOS_STATUS ON BOLETOS (STATUS)';
            EXECUTE IMMEDIATE 'CREATE INDEX IDX_BOLETOS_FILIAL ON BOLETOS (CODFILIAL)';
            EXECUTE IMMEDIATE 'CREATE INDEX IDX_BOLETOS_CREATED ON BOLETOS (CREATED_AT DESC)';
        END IF;
    END;
    """,
    # Sequence nosso_numero
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_sequences WHERE sequence_name = 'SEQ_NOSSO_NUMERO';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_NOSSO_NUMERO START WITH 1 INCREMENT BY 1 MAXVALUE 99999999999 NOCACHE NOCYCLE';
        END IF;
    END;
    """,
    # Trigger updated_at
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_triggers WHERE trigger_name = 'TRG_BOLETOS_UPDATED_AT';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TRIGGER TRG_BOLETOS_UPDATED_AT
                BEFORE UPDATE ON BOLETOS
                FOR EACH ROW
            BEGIN
                :NEW.UPDATED_AT := SYSTIMESTAMP;
            END;';
        END IF;
    END;
    """,
    # Tabela service_log (compativel Oracle 19c — sem IDENTITY)
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'SERVICE_LOG';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TABLE SERVICE_LOG (
                ID         NUMBER(15)    PRIMARY KEY,
                NIVEL      VARCHAR2(10)  DEFAULT ''INFO'' NOT NULL,
                MENSAGEM   VARCHAR2(4000) NOT NULL,
                DETALHE    CLOB,
                CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
            )';
            EXECUTE IMMEDIATE 'CREATE INDEX IDX_SLOG_CREATED ON SERVICE_LOG (CREATED_AT DESC)';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_sequences WHERE sequence_name = 'SEQ_SERVICE_LOG';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_SERVICE_LOG START WITH 1 INCREMENT BY 1 NOCACHE';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_triggers WHERE trigger_name = 'TRG_SERVICE_LOG_ID';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TRIGGER TRG_SERVICE_LOG_ID
                BEFORE INSERT ON SERVICE_LOG
                FOR EACH ROW
                WHEN (NEW.ID IS NULL)
            BEGIN
                SELECT SEQ_SERVICE_LOG.NEXTVAL INTO :NEW.ID FROM DUAL;
            END;';
        END IF;
    END;
    """,
    # Tabela configuracoes (compativel Oracle 19c — sem IDENTITY)
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'CONFIGURACOES';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TABLE CONFIGURACOES (
                ID        NUMBER(10)    PRIMARY KEY,
                CHAVE     VARCHAR2(100) NOT NULL,
                VALOR     VARCHAR2(4000),
                DESCRICAO VARCHAR2(255),
                CONSTRAINT UK_CONFIG_CHAVE UNIQUE (CHAVE)
            )';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_sequences WHERE sequence_name = 'SEQ_CONFIGURACOES';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_CONFIGURACOES START WITH 1 INCREMENT BY 1 NOCACHE';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_triggers WHERE trigger_name = 'TRG_CONFIGURACOES_ID';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
            CREATE TRIGGER TRG_CONFIGURACOES_ID
                BEFORE INSERT ON CONFIGURACOES
                FOR EACH ROW
                WHEN (NEW.ID IS NULL)
            BEGIN
                SELECT SEQ_CONFIGURACOES.NEXTVAL INTO :NEW.ID FROM DUAL;
            END;';
        END IF;
    END;
    """,
    # Reparo: recompila triggers que podem estar INVALID
    """
    BEGIN
        FOR t IN (
            SELECT trigger_name FROM user_triggers
            WHERE status = 'DISABLED' OR trigger_name IN (
                'TRG_CONFIGURACOES_ID', 'TRG_SERVICE_LOG_ID', 'TRG_BOLETOS_UPDATED_AT'
            )
        ) LOOP
            BEGIN
                EXECUTE IMMEDIATE 'ALTER TRIGGER ' || t.trigger_name || ' COMPILE';
            EXCEPTION WHEN OTHERS THEN NULL;
            END;
        END LOOP;
    END;
    """,
    # Migracao: colunas PIX na tabela BOLETOS
    """
    DECLARE
        v_cnt NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
        WHERE table_name = 'BOLETOS' AND column_name = 'MODO_COBRANCA';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE
                'ALTER TABLE BOLETOS ADD MODO_COBRANCA VARCHAR2(20) DEFAULT ''BOLETO_HIBRIDO''';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
        WHERE table_name = 'BOLETOS' AND column_name = 'PIX_COPIA_E_COLA';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE BOLETOS ADD PIX_COPIA_E_COLA CLOB';
        END IF;
        SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
        WHERE table_name = 'BOLETOS' AND column_name = 'QR_IMAGE_BASE64';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE BOLETOS ADD QR_IMAGE_BASE64 CLOB';
        END IF;
        -- Indice por modo
        SELECT COUNT(*) INTO v_cnt FROM user_indexes
        WHERE index_name = 'IDX_BOLETOS_MODO';
        IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE 'CREATE INDEX IDX_BOLETOS_MODO ON BOLETOS(MODO_COBRANCA)';
        END IF;
    END;
    """,
    # Sinonimo PCCOB para consulta de cobrancas do Winthor
    # Descobre o owner por multiplas estrategias
    """
    DECLARE
        v_cnt   NUMBER;
        v_owner VARCHAR2(128) := NULL;
    BEGIN
        -- Ja existe sinonimo? Nada a fazer
        SELECT COUNT(*) INTO v_cnt FROM user_synonyms WHERE synonym_name = 'PCCOB';
        IF v_cnt > 0 THEN RETURN; END IF;

        -- Tabela PCCOB ja existe no schema atual? Nada a fazer
        SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'PCCOB';
        IF v_cnt > 0 THEN RETURN; END IF;

        -- Estrategia 1: mesmo owner do sinonimo PCPREST
        BEGIN
            SELECT table_owner INTO v_owner
            FROM user_synonyms WHERE synonym_name = 'PCPREST' AND ROWNUM = 1;
        EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
        END;

        -- Estrategia 2: mesmo owner do sinonimo PCCLIENT
        IF v_owner IS NULL THEN
            BEGIN
                SELECT table_owner INTO v_owner
                FROM user_synonyms WHERE synonym_name = 'PCCLIENT' AND ROWNUM = 1;
            EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
            END;
        END IF;

        -- Estrategia 3: busca em all_synonyms (sinonimos publicos)
        IF v_owner IS NULL THEN
            BEGIN
                SELECT table_owner INTO v_owner
                FROM all_synonyms WHERE synonym_name = 'PCPREST' AND ROWNUM = 1;
            EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
            END;
        END IF;

        -- Estrategia 4: busca direto em all_tables
        IF v_owner IS NULL THEN
            BEGIN
                SELECT owner INTO v_owner
                FROM all_tables WHERE table_name = 'PCCOB' AND ROWNUM = 1;
            EXCEPTION WHEN NO_DATA_FOUND THEN NULL;
            END;
        END IF;

        -- Cria sinonimo se encontrou o owner
        IF v_owner IS NOT NULL THEN
            EXECUTE IMMEDIATE 'CREATE SYNONYM PCCOB FOR ' || v_owner || '.PCCOB';
        END IF;
    END;
    """,
]


# ── CONFIGURACOES helpers ────────────────────────────────────────────────────

def get_config(chave: str, default: str = "") -> str:
    """Le valor da tabela CONFIGURACOES."""
    rows = stg_query(
        "SELECT valor FROM configuracoes WHERE chave = :chave",
        {"chave": chave},
    )
    return rows[0]["valor"] if rows and rows[0]["valor"] else default


def set_config(chave: str, valor: str, descricao: str = "") -> None:
    """Grava/atualiza valor na tabela CONFIGURACOES (MERGE)."""
    stg_execute("""
        MERGE INTO configuracoes tgt
        USING (SELECT :chave AS chave FROM DUAL) src
        ON (tgt.chave = src.chave)
        WHEN MATCHED THEN UPDATE SET valor = :valor
        WHEN NOT MATCHED THEN INSERT (chave, valor, descricao)
            VALUES (:chave, :valor, :descricao)
    """, {"chave": chave, "valor": valor, "descricao": descricao})


def get_codcobs_boleto() -> list[str]:
    """Retorna lista de CODCOBs configurados para boleto hibrido."""
    from src import config as _cfg
    val = get_config("CODCOB_BOLETO", "")
    if not val:
        return [_cfg.WINTHOR_CODCOB] if _cfg.WINTHOR_CODCOB else []
    return [c.strip() for c in val.split(",") if c.strip()]


def get_codcobs_pix() -> list[str]:
    """Retorna lista de CODCOBs configurados para PIX COBV."""
    val = get_config("CODCOB_PIX", "")
    return [c.strip() for c in val.split(",") if c.strip()]


def get_codfiliais() -> list[str]:
    """Retorna lista de filiais configuradas para monitorar."""
    from src import config as _cfg
    val = get_config("CODFILIAIS", "")
    if not val:
        return [_cfg.WINTHOR_CODFILIAL] if _cfg.WINTHOR_CODFILIAL else []
    return [c.strip() for c in val.split(",") if c.strip()]


def _run_migrations() -> None:
    """Executa DDL idempotente no schema BOLECODE."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            for sql in _MIGRATIONS:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception as exc:
                    logger.debug(f"Migration skip: {exc}")
                    conn.rollback()
    logger.info("Migrations Oracle verificadas.")
