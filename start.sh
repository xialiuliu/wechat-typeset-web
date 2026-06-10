#!/bin/bash
# 公众号排版 Web 工具 - 启动脚本

PORT=8765
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "启动公众号排版工具..."
echo "访问地址：http://localhost:$PORT"
echo "按 Ctrl+C 停止服务"
echo ""

cd "$SCRIPT_DIR"
python -c "import uvicorn; uvicorn.run('server:app', host='0.0.0.0', port=$PORT)"
