#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA_PYTHON="$HOME/miniconda3/envs/openclaw_env/bin/python"
CONDA_UVICORN="$HOME/miniconda3/envs/openclaw_env/bin/uvicorn"
NGROK="$HOME/miniconda3/bin/ngrok"
PORT=8000

cd "$SCRIPT_DIR"

echo "=== OpenClaw ASR Service ==="

# 確認必要程式存在
for bin in "$CONDA_UVICORN" "$NGROK"; do
    if [ ! -f "$bin" ]; then
        echo "[ERROR] 找不到：$bin"
        exit 1
    fi
done

# 停掉舊的服務
echo "[1/3] 停止舊服務..."
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "ngrok http" 2>/dev/null
sleep 2

# 啟動 ASR 服務
echo "[2/3] 啟動 ASR 服務（port $PORT）..."
HF_HOME="$SCRIPT_DIR/models" \
    "$CONDA_UVICORN" main:app --host 0.0.0.0 --port $PORT &
ASR_PID=$!

# 等待服務就緒
echo "      等待模型載入..."
for i in $(seq 1 60); do
    sleep 2
    if curl -sf http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "      ASR 服務就緒 (PID $ASR_PID)"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "[ERROR] ASR 服務啟動逾時"
        kill $ASR_PID 2>/dev/null
        exit 1
    fi
done

# 啟動 ngrok
echo "[3/3] 啟動 ngrok 公開 URL..."
"$NGROK" http $PORT > /dev/null 2>&1 &
sleep 4

PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | \
    "$CONDA_PYTHON" -c "import json,sys; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)

echo ""
echo "=== 啟動完成 ==="
echo "內網：http://localhost:$PORT"
echo "外網：$PUBLIC_URL"
echo "LINE Webhook URL：$PUBLIC_URL/line/webhook"
echo ""
echo "提醒：ngrok 免費版每次重啟 URL 會變，請更新 LINE Webhook 設定"
echo ""
echo "按 Ctrl+C 停止所有服務"

# 等待，Ctrl+C 時一起關閉
trap "echo ''; echo '停止服務...'; pkill -f 'uvicorn main:app'; pkill -f 'ngrok http'; exit 0" INT
wait $ASR_PID
