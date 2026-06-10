#!/bin/bash
# 域名绑定 + HTTPS 证书配置脚本
# 在腾讯云服务器上执行：bash setup-domain.sh

set -e

DOMAIN="typeset.shiker.tech"
SERVICE_NAME="wechat-typeset"

echo "=========================================="
echo "  域名绑定 + HTTPS 配置"
echo "  域名: $DOMAIN"
echo "=========================================="
echo ""

# ── 前置检查 ──
echo "[1/5] 检查 DNS 解析..."
DOMAIN_IP=$(dig +short $DOMAIN A 2>/dev/null | tail -1)
PUBLIC_IP=$(curl -s ifconfig.me)

if [ "$DOMAIN_IP" = "$PUBLIC_IP" ]; then
    echo "  ✅ DNS 已解析: $DOMAIN → $PUBLIC_IP"
else
    echo "  ⚠️  DNS 尚未解析到本机"
    echo "  当前解析: ${DOMAIN_IP:-无}"
    echo "  本机 IP: $PUBLIC_IP"
    echo ""
    echo "  请先到阿里云 DNS 后台添加记录："
    echo "  ┌─────────────────────────────────────┐"
    echo "  │ 记录类型: A                          │"
    echo "  │ 主机记录: typeset                    │"
    echo "  │ 记录值:   $PUBLIC_IP          │"
    echo "  │ TTL:      600                        │"
    echo "  └─────────────────────────────────────┘"
    echo ""
    read -p "  DNS 已配置好？继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "退出。配置好 DNS 后重新运行此脚本。"
        exit 1
    fi
fi

# ── 安装 certbot ──
echo "[2/5] 安装 certbot（Let's Encrypt 免费证书）..."
if ! command -v certbot &>/dev/null; then
    sudo apt update -qq
    sudo apt install -y -qq certbot python3-certbot-nginx
    echo "  ✅ certbot 安装完成"
else
    echo "  ✅ certbot 已安装"
fi

# ── 创建临时 nginx 配置（先 HTTP，用于证书验证） ──
echo "[3/5] 配置 nginx（临时 HTTP 模式，用于获取证书）..."
sudo mkdir -p /var/www/certbot

sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << 'NGINX_HTTP'
server {
    listen 80;
    server_name typeset.shiker.tech;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_HTTP

sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
echo "  ✅ nginx 临时配置已生效"

# ── 申请 SSL 证书 ──
echo "[4/5] 申请 SSL 证书..."
sudo certbot certonly --webroot \
    -w /var/www/certbot \
    -d $DOMAIN \
    --email admin@shiker.tech \
    --agree-tos \
    --non-interactive \
    --no-eff-email

echo "  ✅ 证书已获取"

# ── 切换到完整 HTTPS 配置 ──
echo "[5/5] 切换到 HTTPS 配置..."
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << 'NGINX_HTTPS'
# HTTP → HTTPS 重定向
server {
    listen 80;
    server_name typeset.shiker.tech;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 主服务
server {
    listen 443 ssl http2;
    server_name typeset.shiker.tech;

    ssl_certificate /etc/letsencrypt/live/typeset.shiker.tech/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/typeset.shiker.tech/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;

    location /static/ {
        alias /opt/wechat-typeset-web/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

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
NGINX_HTTPS

sudo nginx -t && sudo systemctl reload nginx
echo "  ✅ HTTPS 配置已生效"

# 设置证书自动续期（certbot timer）
sudo systemctl enable certbot.timer 2>/dev/null || true
sudo systemctl start certbot.timer 2>/dev/null || true

echo ""
echo "=========================================="
echo "  ✅ 域名 + HTTPS 配置完成！"
echo "=========================================="
echo ""
echo "访问地址: https://$DOMAIN"
echo ""
echo "证书自动续期: certbot timer 已启用"
echo "手动续期测试: sudo certbot renew --dry-run"
echo ""
echo "=========================================="
