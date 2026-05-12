#!/bin/bash
CONDA_UVICORN="$HOME/miniconda3/envs/openclaw_env/bin/uvicorn"
cd "$(dirname "$0")"

echo "=== 啟動 Mock 服務 ==="

pkill -f "mock_rag:app" 2>/dev/null
pkill -f "mock_robot:app" 2>/dev/null
sleep 1

echo "[1/2] 啟動 Mock RAG（port 8001）..."
"$CONDA_UVICORN" mock_rag:app --host 0.0.0.0 --port 8001 &
sleep 2

echo "[2/2] 啟動 Mock Robot（port 8002）..."
"$CONDA_UVICORN" mock_robot:app --host 0.0.0.0 --port 8002 &
sleep 2

echo ""
echo "Mock RAG   → http://localhost:8001"
echo "Mock Robot → http://localhost:8002"
echo ""
echo "按 Ctrl+C 停止"
trap "pkill -f 'mock_rag:app'; pkill -f 'mock_robot:app'; exit 0" INT
wait
