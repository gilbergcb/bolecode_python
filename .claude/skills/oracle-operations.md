# Skill: Oracle Operations

## Setup Obrigatório
```python
import oracledb
oracledb.init_oracle_client(lib_dir=config.ORACLE_INSTANT_CLIENT_DIR)
```
Sem isso: "DPI-1047: Cannot locate a 64-bit Oracle Client library"

## Regras PCPREST
- `PREST` é VARCHAR2(2) — NUNCA `int(prest)`, sempre `str`
- `QRCODE_PIX` é VARCHAR2(500) — campo de writeback
- `VLPREST` é NUMBER(12,2) — valor em reais (converter para centavos no payload Bradesco)
- Filtro sync: `WHERE CODCOB = '237' AND QRCODE_PIX IS NULL AND DTVENC >= SYSDATE`

## Operações Seguras
- SELECT: livre, usar pool com `with connection.cursor() as cursor`
- UPDATE: apenas `QRCODE_PIX` via writeback — NUNCA alterar `VLPREST` ou `DTVENC`
- DELETE: PROIBIDO em PCPREST
- INSERT: PROIBIDO — dados vêm do Winthor

## Writeback Pattern
```python
cursor.execute("""
    UPDATE PCPREST 
    SET QRCODE_PIX = :emv 
    WHERE NUMTRANSVENDA = :id AND PREST = :prest
""", {"emv": emv_code, "id": trans_id, "prest": prest_str})
connection.commit()
```

## Troubleshooting
- Pool esgotado → aumentar `max` em oracle.py ou verificar leak de connections
- TNS error → verificar `tnsnames.ora` ou usar connection string direto
- Referência completa: `project-context/oracle-winthor` no Obsidian
