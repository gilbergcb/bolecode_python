# BOLECODE — Setup do Schema Oracle (Winthor)

> Substitui o PostgreSQL por um schema dedicado no mesmo banco Oracle do Winthor.
> O usuario `BOLECODE` tem acesso apenas ao proprio schema + SELECT em tabelas do Winthor.

---

## 1. Criar Usuario/Schema

```sql
-- Conectar como SYSDBA ou DBA do Winthor
-- Ajustar DATAFILE e tamanhos conforme ambiente

-- Tablespace dedicada (opcional, recomendado)
CREATE TABLESPACE TBS_BOLECODE
  DATAFILE '/oracle/oradata/LOCAL/tbs_bolecode01.dbf'
  SIZE 100M
  AUTOEXTEND ON NEXT 50M MAXSIZE 2G
  LOGGING
  EXTENT MANAGEMENT LOCAL
  SEGMENT SPACE MANAGEMENT AUTO;

-- Usuario
CREATE USER BOLECODE
  IDENTIFIED BY "SenhaForte#2026"
  DEFAULT TABLESPACE TBS_BOLECODE
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON TBS_BOLECODE;
```

---

## 2. Grants

```sql
-- Permissoes basicas
GRANT CREATE SESSION   TO BOLECODE;
GRANT CREATE TABLE     TO BOLECODE;
GRANT CREATE SEQUENCE  TO BOLECODE;
GRANT CREATE TRIGGER   TO BOLECODE;
GRANT CREATE PROCEDURE TO BOLECODE;

-- Leitura nas tabelas do Winthor (schema do Winthor, ex: LOCAL)
GRANT SELECT ON LOCAL.PCPREST   TO BOLECODE;
GRANT SELECT ON LOCAL.PCCLIENT  TO BOLECODE;

-- Writeback: UPDATE no PCPREST (apenas coluna QRCODE_PIX)
GRANT UPDATE ON LOCAL.PCPREST   TO BOLECODE;
```

---

## 3. Tabela BOLETOS

```sql
-- Conectar como BOLECODE

CREATE TABLE BOLECODE.BOLETOS (
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
    DADOS_ORACLE          CLOB,                         -- JSON stringificado
    NOSSO_NUMERO          VARCHAR2(11)   UNIQUE,
    STATUS                VARCHAR2(20)   DEFAULT 'PENDENTE' NOT NULL,
    TX_ID                 VARCHAR2(200),
    QRCODE_EMV            CLOB,
    LINHA_DIGITAVEL       VARCHAR2(100),
    COD_BARRAS            VARCHAR2(100),
    DT_REGISTRO_BRADESCO  TIMESTAMP WITH TIME ZONE,
    ORACLE_ATUALIZADO     NUMBER(1)      DEFAULT 0 NOT NULL,  -- 0=false, 1=true
    TENTATIVAS            NUMBER(3)      DEFAULT 0 NOT NULL,
    ULTIMO_ERRO           VARCHAR2(4000),
    PAYLOAD_ENVIADO       CLOB,                         -- JSON
    PAYLOAD_RECEBIDO      CLOB,                         -- JSON
    CREATED_AT            TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    UPDATED_AT            TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    --
    CONSTRAINT UK_BOLETOS_VENDA_PREST UNIQUE (NUMTRANSVENDA, PREST)
);

-- Indice por status (queries frequentes)
CREATE INDEX IDX_BOLETOS_STATUS ON BOLECODE.BOLETOS (STATUS);

-- Indice por filial
CREATE INDEX IDX_BOLETOS_FILIAL ON BOLECODE.BOLETOS (CODFILIAL);

-- Indice por nosso_numero (consultas de liquidacao)
CREATE INDEX IDX_BOLETOS_NOSSONR ON BOLECODE.BOLETOS (NOSSO_NUMERO);

-- Indice por created_at (ordenacao dashboard)
CREATE INDEX IDX_BOLETOS_CREATED ON BOLECODE.BOLETOS (CREATED_AT DESC);

COMMENT ON TABLE BOLECODE.BOLETOS IS 'Fila de boletos: Oracle PCPREST → Bradesco API → Writeback';
COMMENT ON COLUMN BOLECODE.BOLETOS.PREST IS 'VARCHAR2(2) — NUNCA converter para NUMBER';
COMMENT ON COLUMN BOLECODE.BOLETOS.ORACLE_ATUALIZADO IS '0=pendente writeback, 1=ja atualizado no PCPREST';
COMMENT ON COLUMN BOLECODE.BOLETOS.STATUS IS 'PENDENTE|PROCESSANDO|REGISTRADO|ERRO|CANCELADO|BAIXADO';
```

---

## 4. Sequence NOSSO_NUMERO

```sql
CREATE SEQUENCE BOLECODE.SEQ_NOSSO_NUMERO
    START WITH 1
    INCREMENT BY 1
    MAXVALUE 99999999999
    NOCACHE
    NOCYCLE;

-- Uso no Python: LPAD(TO_CHAR(SEQ_NOSSO_NUMERO.NEXTVAL), 11, '0')
```

---

## 5. Trigger UPDATED_AT

```sql
CREATE OR REPLACE TRIGGER BOLECODE.TRG_BOLETOS_UPDATED_AT
    BEFORE UPDATE ON BOLECODE.BOLETOS
    FOR EACH ROW
BEGIN
    :NEW.UPDATED_AT := SYSTIMESTAMP;
END;
/
```

---

## 6. Tabela SERVICE_LOG

```sql
CREATE SEQUENCE BOLECODE.SEQ_SERVICE_LOG START WITH 1 INCREMENT BY 1 NOCACHE;

CREATE TABLE BOLECODE.SERVICE_LOG (
    ID         NUMBER(15)    PRIMARY KEY,
    NIVEL      VARCHAR2(10)  DEFAULT 'INFO' NOT NULL,
    MENSAGEM   VARCHAR2(4000) NOT NULL,
    DETALHE    CLOB,                          -- JSON
    CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE OR REPLACE TRIGGER BOLECODE.TRG_SERVICE_LOG_ID
    BEFORE INSERT ON BOLECODE.SERVICE_LOG
    FOR EACH ROW
    WHEN (NEW.ID IS NULL)
BEGIN
    :NEW.ID := BOLECODE.SEQ_SERVICE_LOG.NEXTVAL;
END;
/

CREATE INDEX IDX_SLOG_CREATED ON BOLECODE.SERVICE_LOG (CREATED_AT DESC);

COMMENT ON TABLE BOLECODE.SERVICE_LOG IS 'Log de eventos do servico BOLECODE';
```

---

## 7. Tabela CONFIGURACOES

```sql
CREATE TABLE BOLECODE.CONFIGURACOES (
    ID        NUMBER(10) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    CHAVE     VARCHAR2(100) NOT NULL UNIQUE,
    VALOR     VARCHAR2(4000),
    DESCRICAO VARCHAR2(255)
);

COMMENT ON TABLE BOLECODE.CONFIGURACOES IS 'Configuracoes chave-valor do servico';
```

---

## 8. Sinonimos (acesso simplificado ao Winthor)

```sql
-- Conectar como BOLECODE
CREATE SYNONYM BOLECODE.PCPREST  FOR LOCAL.PCPREST;
CREATE SYNONYM BOLECODE.PCCLIENT FOR LOCAL.PCCLIENT;
```

> Ajustar `LOCAL` para o schema real do Winthor no seu ambiente.

---

## 9. Verificacao Pos-Setup

```sql
-- Conectar como BOLECODE e validar:

-- Tabelas proprias
SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME;
-- Esperado: BOLETOS, CONFIGURACOES, SERVICE_LOG

-- Sequences
SELECT SEQUENCE_NAME FROM USER_SEQUENCES ORDER BY SEQUENCE_NAME;
-- Esperado: SEQ_NOSSO_NUMERO, SEQ_SERVICE_LOG

-- Triggers
SELECT TRIGGER_NAME, TABLE_NAME FROM USER_TRIGGERS ORDER BY TRIGGER_NAME;
-- Esperado: TRG_BOLETOS_UPDATED_AT, TRG_SERVICE_LOG_ID

-- Acesso ao Winthor
SELECT COUNT(*) FROM PCPREST WHERE ROWNUM <= 1;
SELECT COUNT(*) FROM PCCLIENT WHERE ROWNUM <= 1;

-- Teste de insert
INSERT INTO BOLETOS (NUMTRANSVENDA, PREST, VALOR, CODFILIAL)
VALUES (999999, '01', 100.00, '1');
SELECT * FROM BOLETOS WHERE NUMTRANSVENDA = 999999;
DELETE FROM BOLETOS WHERE NUMTRANSVENDA = 999999;
COMMIT;
```

---

## 10. Variaveis .env (atualizar)

```ini
# Remover variaveis PG_* (nao usa mais PostgreSQL)
# PG_HOST=...       ← REMOVER
# PG_PORT=...       ← REMOVER
# PG_DATABASE=...   ← REMOVER
# PG_USER=...       ← REMOVER
# PG_PASSWORD=...   ← REMOVER

# Oracle — mesmo host do Winthor, usuario novo
ORACLE_HOST=192.168.1.253
ORACLE_PORT=1521
ORACLE_SERVICE=LOCAL
ORACLE_USER=BOLECODE
ORACLE_PASSWORD=SenhaForte#2026
ORACLE_INSTANT_CLIENT_DIR=C:\oracle\instantclient_21_9

# Usuario Winthor (read-only, para sync_pcprest)
# Manter se o sync usa conexao separada, ou remover se BOLECODE
# ja tem grants de SELECT no PCPREST/PCCLIENT via sinonimos
```

---

## Mapeamento de Tipos PG → Oracle

| PostgreSQL | Oracle | Nota |
|---|---|---|
| `UUID` | `RAW(16)` + `SYS_GUID()` | 16 bytes binario |
| `BIGINT` | `NUMBER(15)` | |
| `SERIAL/BIGSERIAL` | `IDENTITY` ou `SEQUENCE + TRIGGER` | |
| `VARCHAR(n)` | `VARCHAR2(n)` | |
| `NUMERIC(15,2)` | `NUMBER(15,2)` | |
| `BOOLEAN` | `NUMBER(1)` | 0=false, 1=true |
| `SMALLINT` | `NUMBER(3)` | |
| `TEXT` | `VARCHAR2(4000)` ou `CLOB` | CLOB para payloads grandes |
| `JSONB` | `CLOB` | JSON como string, parse no Python |
| `TIMESTAMPTZ` | `TIMESTAMP WITH TIME ZONE` | |
| `NOW()` | `SYSTIMESTAMP` | |
| `gen_random_uuid()` | `SYS_GUID()` | |

---

## Impacto no Codigo Python

Arquivos que precisam ser adaptados ao remover PostgreSQL:

| Arquivo | Mudanca |
|---|---|
| `src/db/postgres.py` | **REMOVER** ou refatorar para Oracle |
| `src/config.py` | Remover vars `PG_*`, usar apenas `ORACLE_*` |
| `src/desktop/services/data_service.py` | Trocar `pg_query`/`pg_execute` por `query_oracle`/`execute_oracle` |
| `src/db/oracle.py` | Adicionar `log_service_event()`, migrations |
| `src/jobs/*.py` | Revisar imports e chamadas |
| `requirements.txt` | Remover `psycopg2-binary` |
