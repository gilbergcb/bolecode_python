"""
setup_bolecode_schema.py — Cria usuario BOLECODE e objetos no Oracle Winthor.

Conecta como LOCAL (DBA) e executa:
1. CREATE USER BOLECODE
2. GRANTs
3. Sinonimos para PCPREST/PCCLIENT
4. Tabelas, sequences, triggers, indexes

Uso:
    python scripts/setup_bolecode_schema.py
"""
from __future__ import annotations

import sys
import os

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oracledb

# ── Configuracao (usa dados do .env.example como default) ─────────────────────
ORACLE_HOST = os.getenv("ORACLE_HOST", "192.168.1.253")
ORACLE_PORT = int(os.getenv("ORACLE_PORT", "1521"))
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE", "LOCAL")

# Conecta como DBA (usuario Winthor existente)
DBA_USER = os.getenv("ORACLE_USER", "LOCAL")
DBA_PASSWORD = os.getenv("ORACLE_PASSWORD", "LOCAL")

# Novo usuario a ser criado
BOLECODE_USER = "BOLECODE"
BOLECODE_PASSWORD = os.getenv("BOLECODE_PASSWORD", "Bolecode#2026")

# Schema do Winthor (para sinonimos e grants)
WINTHOR_SCHEMA = DBA_USER  # geralmente LOCAL

INSTANT_CLIENT = os.getenv("ORACLE_INSTANT_CLIENT_DIR", "")


def run():
    # Thick mode se necessario
    if INSTANT_CLIENT:
        try:
            oracledb.init_oracle_client(lib_dir=INSTANT_CLIENT)
            print(f"[OK] Oracle Instant Client: {INSTANT_CLIENT}")
        except Exception as e:
            print(f"[WARN] init_oracle_client: {e}")

    dsn = oracledb.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
    print(f"\nConectando como {DBA_USER}@{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}...")

    conn = oracledb.connect(user=DBA_USER, password=DBA_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    print("[OK] Conectado ao Oracle.\n")

    # ── 1. Verificar/Criar usuario BOLECODE ───────────────────────────────────
    cur.execute(
        "SELECT COUNT(*) FROM all_users WHERE username = :u",
        {"u": BOLECODE_USER},
    )
    user_exists = cur.fetchone()[0] > 0

    if user_exists:
        print(f"[SKIP] Usuario {BOLECODE_USER} ja existe.")
    else:
        print(f"[CREATE] Criando usuario {BOLECODE_USER}...")
        _exec(cur, f"""
            CREATE USER {BOLECODE_USER}
            IDENTIFIED BY "{BOLECODE_PASSWORD}"
            DEFAULT TABLESPACE USERS
            TEMPORARY TABLESPACE TEMP
            QUOTA UNLIMITED ON USERS
        """)
        print(f"[OK] Usuario {BOLECODE_USER} criado.")

    # ── 2. Grants ─────────────────────────────────────────────────────────────
    print("\n[GRANTS] Aplicando permissoes...")
    grants = [
        f"GRANT CREATE SESSION TO {BOLECODE_USER}",
        f"GRANT CREATE TABLE TO {BOLECODE_USER}",
        f"GRANT CREATE SEQUENCE TO {BOLECODE_USER}",
        f"GRANT CREATE TRIGGER TO {BOLECODE_USER}",
        f"GRANT CREATE PROCEDURE TO {BOLECODE_USER}",
        f"GRANT CREATE SYNONYM TO {BOLECODE_USER}",
        f"GRANT SELECT ON {WINTHOR_SCHEMA}.PCPREST TO {BOLECODE_USER}",
        f"GRANT SELECT ON {WINTHOR_SCHEMA}.PCCLIENT TO {BOLECODE_USER}",
        f"GRANT UPDATE ON {WINTHOR_SCHEMA}.PCPREST TO {BOLECODE_USER}",
    ]
    for g in grants:
        _exec(cur, g, ignore_errors=True)
        print(f"  [OK] {g}")

    conn.commit()
    cur.close()
    conn.close()
    print("\n[OK] Fase 1 concluida (usuario + grants).")

    # ── 3. Conectar como BOLECODE e criar objetos ─────────────────────────────
    print(f"\nConectando como {BOLECODE_USER}...")
    conn2 = oracledb.connect(user=BOLECODE_USER, password=BOLECODE_PASSWORD, dsn=dsn)
    cur2 = conn2.cursor()
    print("[OK] Conectado como BOLECODE.\n")

    # Sinonimos
    print("[SYNONYMS] Criando sinonimos...")
    _exec(cur2, f"CREATE OR REPLACE SYNONYM PCPREST FOR {WINTHOR_SCHEMA}.PCPREST",
          ignore_errors=True)
    print(f"  [OK] PCPREST -> {WINTHOR_SCHEMA}.PCPREST")
    _exec(cur2, f"CREATE OR REPLACE SYNONYM PCCLIENT FOR {WINTHOR_SCHEMA}.PCCLIENT",
          ignore_errors=True)
    print(f"  [OK] PCCLIENT -> {WINTHOR_SCHEMA}.PCCLIENT")

    # Tabela BOLETOS
    if not _table_exists(cur2, "BOLETOS"):
        print("\n[CREATE] Tabela BOLETOS...")
        _exec(cur2, """
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
                STATUS                VARCHAR2(20)   DEFAULT 'PENDENTE' NOT NULL,
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
            )
        """)
        _exec(cur2, "CREATE INDEX IDX_BOLETOS_STATUS ON BOLETOS (STATUS)")
        _exec(cur2, "CREATE INDEX IDX_BOLETOS_FILIAL ON BOLETOS (CODFILIAL)")
        _exec(cur2, "CREATE INDEX IDX_BOLETOS_CREATED ON BOLETOS (CREATED_AT DESC)")
        print("  [OK] BOLETOS + indexes criados.")
    else:
        print("[SKIP] Tabela BOLETOS ja existe.")

    # Sequence NOSSO_NUMERO
    if not _sequence_exists(cur2, "SEQ_NOSSO_NUMERO"):
        print("\n[CREATE] Sequence SEQ_NOSSO_NUMERO...")
        _exec(cur2, """
            CREATE SEQUENCE SEQ_NOSSO_NUMERO
                START WITH 1 INCREMENT BY 1
                MAXVALUE 99999999999 NOCACHE NOCYCLE
        """)
        print("  [OK] SEQ_NOSSO_NUMERO criada.")
    else:
        print("[SKIP] Sequence SEQ_NOSSO_NUMERO ja existe.")

    # Trigger UPDATED_AT
    if not _trigger_exists(cur2, "TRG_BOLETOS_UPDATED_AT"):
        print("\n[CREATE] Trigger TRG_BOLETOS_UPDATED_AT...")
        _exec(cur2, """
            CREATE OR REPLACE TRIGGER TRG_BOLETOS_UPDATED_AT
                BEFORE UPDATE ON BOLETOS
                FOR EACH ROW
            BEGIN
                :NEW.UPDATED_AT := SYSTIMESTAMP;
            END;
        """)
        print("  [OK] Trigger criada.")
    else:
        print("[SKIP] Trigger TRG_BOLETOS_UPDATED_AT ja existe.")

    # Tabela SERVICE_LOG (sequence + trigger para ID, compativel Oracle 19c)
    if not _table_exists(cur2, "SERVICE_LOG"):
        print("\n[CREATE] Tabela SERVICE_LOG...")
        _exec(cur2, """
            CREATE TABLE SERVICE_LOG (
                ID         NUMBER(15)    PRIMARY KEY,
                NIVEL      VARCHAR2(10)  DEFAULT 'INFO' NOT NULL,
                MENSAGEM   VARCHAR2(4000) NOT NULL,
                DETALHE    CLOB,
                CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
            )
        """)
        if not _sequence_exists(cur2, "SEQ_SERVICE_LOG"):
            _exec(cur2, "CREATE SEQUENCE SEQ_SERVICE_LOG START WITH 1 INCREMENT BY 1 NOCACHE")
        _exec(cur2, """
            CREATE OR REPLACE TRIGGER TRG_SERVICE_LOG_ID
                BEFORE INSERT ON SERVICE_LOG
                FOR EACH ROW
                WHEN (NEW.ID IS NULL)
            BEGIN
                :NEW.ID := SEQ_SERVICE_LOG.NEXTVAL;
            END;
        """)
        _exec(cur2, "CREATE INDEX IDX_SLOG_CREATED ON SERVICE_LOG (CREATED_AT DESC)")
        print("  [OK] SERVICE_LOG + sequence + trigger + index criados.")
    else:
        print("[SKIP] Tabela SERVICE_LOG ja existe.")

    # Tabela CONFIGURACOES (sequence + trigger para ID, compativel Oracle 19c)
    if not _table_exists(cur2, "CONFIGURACOES"):
        print("\n[CREATE] Tabela CONFIGURACOES...")
        if not _sequence_exists(cur2, "SEQ_CONFIGURACOES"):
            _exec(cur2, "CREATE SEQUENCE SEQ_CONFIGURACOES START WITH 1 INCREMENT BY 1 NOCACHE")
        _exec(cur2, """
            CREATE TABLE CONFIGURACOES (
                ID        NUMBER(10)    PRIMARY KEY,
                CHAVE     VARCHAR2(100) NOT NULL,
                VALOR     VARCHAR2(4000),
                DESCRICAO VARCHAR2(255),
                CONSTRAINT UK_CONFIG_CHAVE UNIQUE (CHAVE)
            )
        """)
        _exec(cur2, """
            CREATE OR REPLACE TRIGGER TRG_CONFIGURACOES_ID
                BEFORE INSERT ON CONFIGURACOES
                FOR EACH ROW
                WHEN (NEW.ID IS NULL)
            BEGIN
                :NEW.ID := SEQ_CONFIGURACOES.NEXTVAL;
            END;
        """)
        print("  [OK] CONFIGURACOES + sequence + trigger criados.")
    else:
        print("[SKIP] Tabela CONFIGURACOES ja existe.")

    conn2.commit()

    # ── 4. Verificacao final ──────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("  VERIFICACAO FINAL")
    print("=" * 50)

    cur2.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    tables = [r[0] for r in cur2.fetchall()]
    print(f"\nTabelas: {', '.join(tables)}")

    cur2.execute("SELECT sequence_name FROM user_sequences ORDER BY sequence_name")
    seqs = [r[0] for r in cur2.fetchall()]
    print(f"Sequences: {', '.join(seqs)}")

    cur2.execute("SELECT trigger_name FROM user_triggers ORDER BY trigger_name")
    trigs = [r[0] for r in cur2.fetchall()]
    print(f"Triggers: {', '.join(trigs)}")

    cur2.execute("SELECT synonym_name, table_owner, table_name FROM user_synonyms ORDER BY synonym_name")
    syns = cur2.fetchall()
    for s in syns:
        print(f"Synonym: {s[0]} -> {s[1]}.{s[2]}")

    # Teste de acesso ao Winthor
    try:
        cur2.execute("SELECT COUNT(*) FROM PCPREST WHERE ROWNUM <= 1")
        print(f"\n[OK] Acesso PCPREST: OK")
    except Exception as e:
        print(f"\n[ERRO] Acesso PCPREST: {e}")

    try:
        cur2.execute("SELECT COUNT(*) FROM PCCLIENT WHERE ROWNUM <= 1")
        print(f"[OK] Acesso PCCLIENT: OK")
    except Exception as e:
        print(f"[ERRO] Acesso PCCLIENT: {e}")

    # Teste insert/delete
    print("\n[TEST] Insert/delete de teste...")
    try:
        cur2.execute("""
            INSERT INTO BOLETOS (NUMTRANSVENDA, PREST, VALOR, CODFILIAL, STATUS)
            VALUES (999999999, '99', 0.01, '1', 'PENDENTE')
        """)
        cur2.execute("SELECT COUNT(*) FROM BOLETOS WHERE NUMTRANSVENDA = 999999999")
        cnt = cur2.fetchone()[0]
        cur2.execute("DELETE FROM BOLETOS WHERE NUMTRANSVENDA = 999999999")
        conn2.commit()
        print(f"  [OK] Insert={cnt}, delete OK.")
    except Exception as e:
        print(f"  [ERRO] {e}")
        conn2.rollback()

    cur2.close()
    conn2.close()

    print("\n" + "=" * 50)
    print("  SETUP CONCLUIDO COM SUCESSO!")
    print("=" * 50)
    print(f"\nAtualize seu .env:")
    print(f"  ORACLE_USER={BOLECODE_USER}")
    print(f"  ORACLE_PASSWORD={BOLECODE_PASSWORD}")
    print()


def _exec(cur, sql, ignore_errors=False):
    try:
        cur.execute(sql)
    except Exception as e:
        if ignore_errors:
            pass  # grant duplicado, objeto ja existe, etc.
        else:
            raise


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = :n", {"n": name})
    return cur.fetchone()[0] > 0


def _sequence_exists(cur, name: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM user_sequences WHERE sequence_name = :n", {"n": name})
    return cur.fetchone()[0] > 0


def _trigger_exists(cur, name: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM user_triggers WHERE trigger_name = :n", {"n": name})
    return cur.fetchone()[0] > 0


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        sys.exit(1)
