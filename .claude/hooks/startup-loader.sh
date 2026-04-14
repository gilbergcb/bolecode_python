#!/bin/bash
# Hook: Startup Context Loader (Notification)
# Lê wake-up.md do Obsidian no início da sessão
# Roda apenas 1x por sessão (flag file)

SESSION_FLAG="/tmp/claude-session-$(date +%Y%m%d)-$$"

# Se já rodou nesta sessão, sair silenciosamente
if [ -f "/tmp/claude-session-$(date +%Y%m%d)-loaded" ]; then
  exit 0
fi

OBS_URL="https://127.0.0.1:27124"
OBS_KEY="${OBSIDIAN_API_KEY:-6da6cbb21bc33829ca06dbe4064baef385ed663cf9ad8edc8107978c6927dd7c}"

# Tenta ler wake-up.md
WAKEUP=$(curl -s -k -H "Authorization: Bearer $OBS_KEY" "$OBS_URL/vault/memory/wake-up.md" 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$WAKEUP" ] && ! echo "$WAKEUP" | grep -q "errorCode"; then
  echo "=== OBSIDIAN: Wake-up Context ==="
  echo "$WAKEUP"
  echo "================================="

  # Tenta ler inbox
  INBOX=$(curl -s -k -H "Authorization: Bearer $OBS_KEY" "$OBS_URL/vault/memory/inbox.md" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$INBOX" ] && ! echo "$INBOX" | grep -q "errorCode"; then
    echo ""
    echo "=== OBSIDIAN: Inbox ==="
    echo "$INBOX"
    echo "======================"
  fi

  # Marca como carregado
  touch "/tmp/claude-session-$(date +%Y%m%d)-loaded"
else
  echo "Obsidian não disponível. Verifique se está aberto com Local REST API ativo."
fi

exit 0
