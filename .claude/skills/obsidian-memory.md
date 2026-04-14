# Skill: Obsidian Memory

## Quando usar
Quando precisar persistir informação entre sessões, registrar decisões, ou carregar contexto detalhado.

## API
```
URL: https://127.0.0.1:27124
Header: Authorization: Bearer $OBSIDIAN_API_KEY
```

## Operações
```bash
# Ler nota
curl -s -k -H "Authorization: Bearer $KEY" "$URL/vault/{path}"

# Criar/substituir nota
curl -s -k -X PUT -H "Authorization: Bearer $KEY" -H "Content-Type: text/markdown" "$URL/vault/{path}" -d "$CONTENT"

# Listar pasta
curl -s -k -H "Authorization: Bearer $KEY" "$URL/vault/"

# Append (GET + concat + PUT)
CURRENT=$(curl -s -k -H "Authorization: Bearer $KEY" "$URL/vault/{path}")
curl -s -k -X PUT -H "Authorization: Bearer $KEY" -H "Content-Type: text/markdown" "$URL/vault/{path}" -d "${CURRENT}\n\n${NEW_CONTENT}"
```

## Estrutura do Vault
- `memory/wake-up.md` — Estado atual (ler no início da sessão)
- `memory/inbox.md` — Tasks pendentes
- `memory/journal/YYYY-MM-DD.md` — Log diário
- `decisions/DEC-NNNN-slug.md` — Decisões arquiteturais
- `project-context/*` — Referência detalhada (sob demanda)

## Regra de Ouro
Contexto grande → salvar no Obsidian, manter apenas ponteiro no chat. Economiza tokens.
