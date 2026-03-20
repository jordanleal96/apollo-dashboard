#!/bin/bash
# run.sh — Pipeline completo Apollo + Claude Dashboard
# Uso: ./run.sh
# Cron: 0 7 * * * /Users/jordanleal/apollo-dashboard/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV="$HOME/.local/bin/uv"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "========================================" | tee -a "$LOG_FILE"
echo "Apollo Dashboard — $(date '+%d/%m/%Y %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Carrega .env
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -o allexport
  source "$SCRIPT_DIR/.env"
  set +o allexport
  echo "[OK] .env carregado" | tee -a "$LOG_FILE"
else
  echo "[ERRO] Arquivo .env não encontrado em $SCRIPT_DIR" | tee -a "$LOG_FILE"
  exit 1
fi

# Verifica chaves
if [ -z "${APOLLO_API_KEY:-}" ] || [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[ERRO] APOLLO_API_KEY ou ANTHROPIC_API_KEY não definidos no .env" | tee -a "$LOG_FILE"
  exit 1
fi

echo "[OK] Chaves de API verificadas" | tee -a "$LOG_FILE"

# ── 1. Roda pipeline ──────────────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "[1/3] Rodando pipeline completo..." | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

DASHBOARD_PATH=$("$UV" run python -c "
from dashboard_generator import run
path = run()
print(path)
" 2>&1 | tee -a "$LOG_FILE" | tail -1)

if [ ! -f "$DASHBOARD_PATH" ]; then
  echo "[ERRO] Dashboard não foi gerado em: $DASHBOARD_PATH" | tee -a "$LOG_FILE"
  exit 1
fi

echo "[OK] Dashboard gerado: $DASHBOARD_PATH" | tee -a "$LOG_FILE"

# ── 2. Atualiza index.html ────────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "[2/3] Atualizando index.html..." | tee -a "$LOG_FILE"

cp "$DASHBOARD_PATH" "$SCRIPT_DIR/index.html"
echo "[OK] index.html atualizado" | tee -a "$LOG_FILE"

# ── 3. Publica no GitHub Pages ────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "[3/3] Publicando no GitHub Pages..." | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

git add index.html
git commit -m "dashboard: atualização automática $(date '+%d/%m/%Y %H:%M')" 2>&1 | tee -a "$LOG_FILE"
git push origin main 2>&1 | tee -a "$LOG_FILE"

echo "[OK] Publicado em https://jordanleal96.github.io/apollo-dashboard/" | tee -a "$LOG_FILE"

# ── Finalização ───────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG_FILE"
echo "[CONCLUÍDO] $(date '+%d/%m/%Y %H:%M:%S')" | tee -a "$LOG_FILE"

# Mantém apenas os últimos 30 logs
ls -t "$LOG_DIR"/run_*.log 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true
