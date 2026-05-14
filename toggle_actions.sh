#!/bin/bash
# Script para pausar/resumir sincronização automática do GitHub Actions
# Uso: ./toggle_actions.sh [pause|resume|status]

ACTION_FILE=".actions_paused"

case "$1" in
  pause)
    if [ -f "$ACTION_FILE" ]; then
      echo "⚠️ Actions já estão pausadas"
    else
      echo "⏸️ Pausando sincronização automática..."
      echo "$(date -u +'%Y-%m-%d %H:%M UTC') - Pausado por desenvolvedor" > "$ACTION_FILE"
      echo "✅ Actions pausadas. Criado arquivo: $ACTION_FILE"
    fi
    ;;
  resume)
    if [ -f "$ACTION_FILE" ]; then
      rm "$ACTION_FILE"
      echo "▶️ Sincronização automática retomada!"
    else
      echo "ℹ️ Actions já estavam ativas"
    fi
    ;;
  status)
    if [ -f "$ACTION_FILE" ]; then
      echo "⏸️ Status: PAUSADA"
      echo "Motivo:"
      cat "$ACTION_FILE"
    else
      echo "▶️ Status: ATIVA"
    fi
    ;;
  *)
    echo "Uso: ./toggle_actions.sh [pause|resume|status]"
    echo ""
    echo "  pause   - Pausa a sincronização automática (útil durante trabalho local)"
    echo "  resume  - Retoma a sincronização automática"
    echo "  status  - Mostra o status atual"
    ;;
esac