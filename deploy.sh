#!/bin/bash
# 公众号排版 Web 工具 - 腾讯云一键部署脚本
# 技术栈：FastAPI + nginx + systemd

set -e

echo "=========================================="
echo "  公众号排版工具 - 腾讯云部署脚本"
echo "=========================================="
echo ""

# 配置
PROJECT_DIR="/opt/wechat-typeset-web"
SERVER_PORT=8765
SERVICE_NAME="wechat-typeset"

# 获取公网 IP
PUBLIC_IP=$(curl -s ifconfig.me)

echo "[1/8] 更新系统并安装依赖..."
sudo apt update -qq
sudo apt install -y -qq python3 python3-venv python3-pip git curl nginx nodejs npm

echo "[2/8] 创建项目目录..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown $USER:$USER "$PROJECT_DIR"

echo "[3/8] 复制项目文件到服务器..."
# 注意：运行此脚本前，需先将项目文件推送到 GitHub 或 scp 到服务器
# 这里假设项目文件已存在于当前目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
rsync -av --exclude='__pycache__' --exclude='venv' "$SCRIPT_DIR/" "$PROJECT_DIR/"

echo "[4/8] 创建 Python 虚拟环境..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[5/8] 配置 nginx..."
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;  # 接受所有域名/IP访问

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "[6/8] 创建 systemd 服务..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << SYSTEMD
[Unit]
Description=公众号排版 Web 工具
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=NODE_OPTIONS=
ExecStart=$PROJECT_DIR/venv/bin/uvicorn server:app --host 127.0.0.1 --port $SERVER_PORT --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo "[7/8] 创建日志目录..."
mkdir -p "$PROJECT_DIR/logs"

echo "[8/8] 验证服务状态..."
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ 服务运行正常"
else
    echo "❌ 服务启动失败，查看日志: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  http://$PUBLIC_IP"
echo ""
echo "管理命令:"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
echo ""
echo "如需绑定域名，修改 nginx 配置:"
echo "  sudo nano /etc/nginx/sites-available/$SERVICE_NAME"
echo "  将 server_name _; 改为 server_name your-domain.com;"
echo "  sudo systemctl restart nginx"
echo ""
echo "=========================================="
