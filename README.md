# 公众号排版 Web 工具

粘贴文案 → 选择风格 → 一键生成 → 复制到公众号。

支持 **禅意古朴 / 极简现代 / 科技商务** 三种专业排版风格，3 秒出效果。

---

## 功能特性

- **三种风格** - 禅意古朴（棕金/古纸/暖橙）、极简现代（黑白/留白/清冽）、科技商务（深蓝/橙红/理性）
- **Markdown 支持** - 粘贴 Markdown 或纯文本即可
- **一键预览** - 自动生成 edit.shiker.tech 预览链接，复制即用
- **快捷键** - `Ctrl/Cmd + Enter` 快速生成
- **API 接口** - 支持程序化调用，可接入其他系统

---

## 技术栈

- **Python 3.10+** - FastAPI 后端
- **Tailwind CSS** - 前端样式
- **nginx** - 反向代理
- **systemd** - 服务常驻
- **Node.js** - 调用排版脚本（服务器需安装）

---

## 快速部署（腾讯云）

### 方式一：一键部署脚本（推荐）

```bash
# 1. 将项目文件上传到服务器（如 /home/ubuntu/wechat-typeset-web/）
# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

部署完成后，访问 `http://服务器IP` 即可使用。

### 方式二：手动部署

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx nodejs npm

# 2. 创建项目目录
sudo mkdir -p /opt/wechat-typeset-web
sudo chown $USER:$USER /opt/wechat-typeset-web

# 3. 复制项目文件
cp -r . /opt/wechat-typeset-web/

# 4. 创建虚拟环境并安装依赖
cd /opt/wechat-typeset-web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. 配置 nginx
sudo cp nginx.conf /etc/nginx/sites-available/wechat-typeset
sudo ln -sf /etc/nginx/sites-available/wechat-typeset /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 6. 配置 systemd 服务
sudo cp wechat-typeset.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wechat-typeset
sudo systemctl start wechat-typeset

# 7. 验证
curl http://localhost/api/health
```

---

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
./start.sh
# 或：python -c "import uvicorn; uvicorn.run('server:app', host='0.0.0.0', port=8765, reload=True)"

# 访问 http://localhost:8765
```

---

## API 文档

### 排版接口

```
POST /api/typeset
Content-Type: application/json

{
  "markdown": "# 文章标题\n正文内容...",
  "style": "zen"      // zen | minimal | tech
}
```

响应：
```json
{
  "preview_url": "https://edit.shiker.tech/copy.html?id=xxx",
  "style": "zen",
  "style_label": "禅意古朴"
}
```

### 健康检查

```
GET /api/health
```

响应：
```json
{
  "status": "ok",
  "styles": ["zen", "minimal", "tech"]
}
```

---

## 项目结构

```
wechat-typeset-web/
├── server.py               # FastAPI 后端
├── static/
│   └── index.html          # 前端单页
├── deploy.sh               # 一键部署脚本
├── start.sh                # 本地启动脚本
├── wechat-typeset.service  # systemd 服务配置
├── nginx.conf              # nginx 反向代理配置
├── requirements.txt        # Python 依赖
└── README.md               # 项目说明
```

---

## 管理命令

```bash
# 查看服务状态
sudo systemctl status wechat-typeset

# 查看实时日志
sudo journalctl -u wechat-typeset -f

# 重启服务
sudo systemctl restart wechat-typeset

# 停止服务
sudo systemctl stop wechat-typeset

# nginx 配置检查
sudo nginx -t
sudo systemctl restart nginx
```

---

## 绑定域名

```bash
# 修改 nginx 配置
sudo nano /etc/nginx/sites-available/wechat-typeset

# 将 server_name _; 改为：
server_name your-domain.com;

# 重启 nginx
sudo systemctl restart nginx
```

---

## 依赖说明

本项目依赖以下 WorkBuddy Skill 资源（服务器上需存在）：

- `~/.workbuddy/skills/wechat-article-typeset/html-to-wechat-copy.js` - 排版脚本
- `~/.workbuddy/skills/wechat-typeset-pro/templates/` - 三种风格模板

部署前确保服务器上有 Node.js 环境（`apt install nodejs npm`）。

---

## 更新日志

- **2026-06-10** - 项目初始化，支持三种排版风格，腾讯云一键部署
