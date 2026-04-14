# BOLECODE — Monitor Boletos Winthor↔Bradesco

## STACK
Python 3.11 | Oracle 19c (thick mode) | PostgreSQL 14 | FastAPI | APScheduler | httpx (mTLS) | pydantic

## ARCHITECTURE
Oracle PCPREST → PG staging (PENDENTE→PROCESSANDO→REGISTRADO) → Bradesco API → PG → Oracle writeback (QRCODE_PIX)
Jobs: sync_pcprest(30s), registrar_boletos(15s), writeback_oracle(20s), consultar_liquidados(60min)
Dashboard: FastAPI :8765 | Tray: pystray (Windows)

## FILE MAP
- Entry: main.py | Config: src/config.py
- DB: src/db/{oracle,postgres}.py | API: src/api/bradesco_client.py
- Jobs: src/jobs/{sync_pcprest,registrar_boletos,writeback_oracle,consultar_liquidados}.py
- UI: src/ui/{api_routes,webhook_receiver,tray}.py

## CRITICAL RULES
- PREST é VARCHAR2(2) — NUNCA converter para int
- vnmnalTitloCobr é centavos sem decimal: R$50.00 → "5000"
- nosso_numero: string 11 dígitos, gerado por sequence PG, UNIQUE
- ON CONFLICT (numtransvenda, prest) DO NOTHING — idempotência
- Oracle thick mode obrigatório — requer ORACLE_INSTANT_CLIENT_DIR
- mTLS: sandbox aceita self-signed; produção exige cert AC com CN=razao_social+CNPJ
- Bearer token TTL 1h, auto-renovado 5min antes do vencimento

## FORBIDDEN
- NEVER commit .env, certs/, logs/, *.pem, *.key
- NEVER log passwords, tokens, CNPJ completo, ou API keys
- NEVER usar `any` sem justificativa em type hints
- NEVER modificar Oracle sem testar em sandbox primeiro
- NEVER fazer DELETE em PCPREST
- NEVER alterar VLPREST ou DTVENC via aplicação

## ROUTING TABLE
| Trigger | Action |
|---------|--------|
| Bug na API Bradesco | Checar token→payload→cert→logs. Skill: debug-bradesco |
| Novo campo PCPREST | Atualizar oracle.py + postgres.py + migração PG |
| Erro Oracle connection | Verificar Instant Client + thick mode + TNS |
| Performance lenta | Checar pool connections, N+1 queries, APScheduler overlap |
| Novo job agendado | Criar em src/jobs/, registrar no scheduler.py |
| Erro de certificado | Verificar chain SSL, CN, validade. Ver project-context/api-bradesco no Obsidian |

## MEMORY (Obsidian REST API)
- Endpoint: https://127.0.0.1:27124
- Auth: Bearer token (variável OBSIDIAN_API_KEY no .env)
- Sessão start → GET memory/wake-up.md
- Sessão end → PUT memory/journal/YYYY-MM-DD.md + atualizar wake-up.md
- Decisões → PUT decisions/DEC-NNNN-slug.md
- Referência detalhada → GET project-context/* (sob demanda, NÃO carregar automaticamente)

## QUALITY GATES
□ python -m py_compile em todos os .py — 0 errors
□ Testar endpoint Bradesco em sandbox antes de produção
□ Verificar .env.example atualizado com novas vars
□ Nenhum secret hardcoded no código
