#!/usr/bin/env bash
# ============================================================
# PaperMate 停止所有容器
# 用法: chmod +x stop.sh && ./stop.sh
# ============================================================
set -euo pipefail

echo "Stopping PaperMate API/Worker containers..."

# 仅停止 API/Worker 容器，PG 和 Redis 由你手动管理
containers=(
  papermate-api
  papermate-worker-analysis
  papermate-worker-arxiv
  papermate-beat
)

for c in "${containers[@]}"; do
  if docker ps -q -f "name=^${c}$" | grep -q .; then
    echo "  Stopping ${c}..."
    docker stop "${c}"
  else
    echo "  ${c} not running, skip"
  fi
done

echo "Done."
