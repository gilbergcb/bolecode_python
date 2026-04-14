#!/bin/bash
# Hook: Session End (Stop)
# Atualiza journal e wake-up.md no Obsidian ao final da sessão

OBS_URL="https://127.0.0.1:27124"
OBS_KEY="${OBSIDIAN_API_KEY:-6da6cbb21bc33829ca06dbe4064baef385ed663cf9ad8edc8107978c6927dd7c}"
TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M)
JOURNAL_PATH="memory/journal/${TODAY}.md"

# Verifica se Obsidian está acessível
STATUS=$(curl -s -k -H "Authorization: Bearer $OBS_KEY" "$OBS_URL/" 2>/dev/null | grep -o '"OK"')
if [ -z "$STATUS" ]; then
  echo "Obsidian nao acessivel. Journal nao atualizado."
  exit 0
fi

# Lê journal atual (pode não existir ainda)
CURRENT_JOURNAL=$(curl -s -k -H "Authorization: Bearer $OBS_KEY" "$OBS_URL/vault/${JOURNAL_PATH}" 2>/dev/null)

if echo "$CURRENT_JOURNAL" | grep -q "errorCode"; then
  # Journal não existe, criar novo
  CURRENT_JOURNAL="# Journal - ${TODAY}"
fi

# Append nova entrada
NEW_ENTRY="${CURRENT_JOURNAL}

## Sessao encerrada as ${NOW}
- Sessao finalizada automaticamente pelo hook session-end
- Verificar wake-up.md para estado atualizado"

# Salva journal
curl -s -k -X PUT \
  -H "Authorization: Bearer $OBS_KEY" \
  -H "Content-Type: text/markdown" \
  "$OBS_URL/vault/${JOURNAL_PATH}" \
  -d "$NEW_ENTRY" 2>/dev/null

if [ $? -eq 0 ]; then
  echo "Journal atualizado: ${JOURNAL_PATH}"
else
  echo "Erro ao atualizar journal."
fi

# Limpa flag de sessão
rm -f /tmp/claude-session-$(date +%Y%m%d)-loaded 2>/dev/null

exit 0
