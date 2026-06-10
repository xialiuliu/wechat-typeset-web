"""
公众号排版 Web 工具 - 后端 API
技术栈：FastAPI + Python 直接调用 edit.shiker.tech API（无需 Node.js）
启动：python server.py
"""

import re
import json
import urllib.request
import urllib.error
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="公众号排版工具 API")

# CORS 允许所有来源（生产环境可限定域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路径配置（项目内相对路径，不依赖外部 ~/.workbuddy）
PROJECT_DIR = Path(__file__).parent.resolve()
TEMPLATES_DIR = PROJECT_DIR / "templates"

STYLE_MAP = {
    "zen":     TEMPLATES_DIR / "zen-classic.html",
    "minimal": TEMPLATES_DIR / "minimal-modern.html",
    "tech":    TEMPLATES_DIR / "tech-biz.html",
}

STYLE_LABELS = {
    "zen":     "禅意古朴",
    "minimal": "极简现代",
    "tech":    "科技商务",
}

# ── 各风格配色与样式配置 ──

STYLE_CONFIG = {
    "zen": {
        "title_color": "#5c4a2a",
        "text_color": "#3a2e1e",
        "h2_color": "#5c4a2a",
        "h3_color": "#5c4a2a",
        "line_height": "1.9",
        "font_size": "15px",
        "cards": {
            "intro":    {"bg": "#fdf8f0", "border": "#c8a96e", "label_color": "#5c4a2a"},   # 引言 - 暖米黄+金边
            "quote":    {"bg": "#f5f0e8", "border": "#ddd0b0", "label_color": "#5c4a2a"},   # 原文 - 古纸米色
            "insight":  {"bg": "#f0f5ee", "border": "#7aad72", "label_color": "#5c8a52"},   # 感悟 - 竹绿
            "practice": {"bg": "#fdf6f0", "border": "#e8916a", "label_color": "#c47044"},   # 实践 - 暖橙
            "tip":      {"bg": "#fdf8f0", "border": "#c8a96e", "label_color": "#5c4a2a"},   # 提示 - 金边
            "summary":  {"bg": "#f5f0e8", "border": "#ddd0b0", "label_color": "#5c4a2a"},   # 小结 - 古纸米色
        },
        "blockquote_bg": "#fdf8f0",
        "blockquote_border": "#c8a96e",
        "ul_color": "#5c4a2a",
        "table_header_bg": "#f5f0e8",
        "table_header_color": "#5c4a2a",
        "table_border": "#ddd0b0",
    },
    "minimal": {
        "title_color": "#1a1a1a",
        "text_color": "#333",
        "h2_color": "#1a1a1a",
        "h3_color": "#1a1a1a",
        "line_height": "2.0",
        "font_size": "15px",
        "cards": {
            "intro":    {"bg": "#f8f9fa", "border": "#e1e4e8", "label_color": "#1a1a1a"},   # 引言
            "quote":    {"bg": "#f8f9fa", "border": "#ddd",     "label_color": "#555"},     # 引用
            "insight":  {"bg": "#eef6ff", "border": "#6cb4ee", "label_color": "#1a1a1a"},   # 重点
            "practice": {"bg": "#f0faf4", "border": "#7ec8a0", "label_color": "#1a1a1a"},   # 提示
            "tip":      {"bg": "#f8f9fa", "border": "#aaa",     "label_color": "#555"},     # 备注
            "summary":  {"bg": "#f8f9fa", "border": "#ddd",     "label_color": "#555"},     # 引用
        },
        "blockquote_bg": "#f8f9fa",
        "blockquote_border": "#ddd",
        "ul_color": "#1a1a1a",
        "table_header_bg": "#f8f9fa",
        "table_header_color": "#1a1a1a",
        "table_border": "#e1e4e8",
    },
    "tech": {
        "title_color": "#0d1b3e",
        "text_color": "#2c3e50",
        "h2_color": "#0d1b3e",
        "h3_color": "#0d1b3e",
        "line_height": "1.85",
        "font_size": "15px",
        "cards": {
            "intro":    {"bg": "#eef3fb", "border": "#3b82f6", "label_color": "#0d1b3e"},   # 引言
            "quote":    {"bg": "#f1f5f9", "border": "#94a3b8", "label_color": "#64748b"},   # 技术
            "insight":  {"bg": "#fff7ed", "border": "#f97316", "label_color": "#c2410c"},   # 数据
            "practice": {"bg": "#eef3fb", "border": "#3b82f6", "label_color": "#0d1b3e"},   # 信息
            "tip":      {"bg": "#f1f5f9", "border": "#94a3b8", "label_color": "#64748b"},   # 技术
            "summary":  {"bg": "#0d1b3e", "border": "#3b82f6", "label_color": "#e2e8f0"},   # 总结 - 深蓝底白字
        },
        "blockquote_bg": "#f1f5f9",
        "blockquote_border": "#94a3b8",
        "ul_color": "#0d1b3e",
        "table_header_bg": "#1e40af",
        "table_header_color": "#fff",
        "table_border": "#e2e8f0",
    },
}


def make_card(html: str, card_type: str, style: str) -> str:
    """用 table 包裹卡片，保留背景色和边框（公众号兼容）"""
    cfg = STYLE_CONFIG[style]["cards"][card_type]
    bg, border, label_color = cfg["bg"], cfg["border"], cfg["label_color"]
    # 使用 table + td 来保留背景色和左边框
    return (
        f'<table style="width:100%;border-collapse:collapse;margin:16px 0;background:{bg};">'
        f'<tr><td style="border-left:4px solid {border};padding:16px 20px;">'
        f'{html}'
        f'</td></tr></table>'
    )


def convert_to_wechat_html(raw_html: str) -> str:
    """
    外层包裹 section 作为整篇统一背景，保留原有样式。
    不再把 section 转 blockquote（会破坏样式）。
    """
    SECTION_STYLE = (
        "margin:0;padding:16px 14px;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Microsoft YaHei',sans-serif;"
        "font-size:16px;color:#333;line-height:1.6;word-break:break-word;"
        "background:#f5f5f5;box-sizing:border-box"
    )
    return f'<section data-tool="公众号排版" style="{SECTION_STYLE}">\n{raw_html}\n</section>'


def call_shiker_api(html_content: str) -> str:
    """
    直接用 Python urllib 调用 edit.shiker.tech API 获取预览链接。
    """
    wechat_html = convert_to_wechat_html(html_content)
    payload = json.dumps({"html": wechat_html}).encode("utf-8")

    req = urllib.request.Request(
        "https://edit.shiker.tech/api/copy",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success") and data.get("data", {}).get("url"):
                return data["data"]["url"]
            raise ValueError(f"API 返回失败：{data.get('message', json.dumps(data, ensure_ascii=False)[:200])}")
    except urllib.error.URLError as e:
        raise ValueError(f"网络请求失败：{e.reason}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        raise ValueError(f"API 返回 HTTP {e.code}：{body}")


# ── Markdown → HTML 渲染 ──

def detect_card_type(text: str) -> str:
    """根据文本内容语义检测卡片类型"""
    t = text.lower()
    if any(k in t for k in ["感悟", "心得", "体会", "思考", "领悟", "启发"]):
        return "insight"
    if any(k in t for k in ["实践", "案例", "应用", "操作", "步骤", "方法", "练习", "体验"]):
        return "practice"
    if any(k in t for k in ["原文", "经文", "经典", "引用", "子曰", "道德经", "论语", "金刚"]):
        return "quote"
    if any(k in t for k in ["总结", "小结", "结语", "寄语", "结语", "总而言之"]):
        return "summary"
    if any(k in t for k in ["提示", "注意", "提醒", "建议", "补充", "说明"]):
        return "tip"
    if any(k in t for k in ["引言", "前言", "导语", "开篇", "写在前面"]):
        return "intro"
    return "intro"  # 默认引言样式


def build_html(markdown_text: str, style: str) -> str:
    """
    把用户输入的 Markdown / 纯文本，按照选定风格模板渲染为完整 HTML。
    """
    template_path = STYLE_MAP[style]
    template_html = template_path.read_text(encoding="utf-8")
    cfg = STYLE_CONFIG[style]

    lines = markdown_text.strip().split("\n")
    title = ""
    subtitle = ""
    content_parts = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 一级标题 → 文章主标题
        if line.startswith("# "):
            title = line[2:].strip()
            i += 1
            continue

        # 二级标题 → 章节标题
        if line.startswith("## "):
            section_title = line[3:].strip()
            content_parts.append(
                f'<h2 style="font-size:17px;font-weight:500;color:{cfg["h2_color"]};'
                f'margin:28px 0 12px;letter-spacing:1px;">{section_title}</h2>'
            )
            i += 1
            continue

        # 三级标题 → 小节标题
        if line.startswith("### "):
            sub = line[4:].strip()
            content_parts.append(
                f'<h3 style="font-size:15px;font-weight:500;color:{cfg["h3_color"]};'
                f'margin:18px 0 8px;">{sub}</h3>'
            )
            i += 1
            continue

        # Markdown 引用块 > → 卡片
        if line.startswith("> "):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:])
                i += 1
            quote_text = "<br>".join(quote_lines)
            # 解析 **粗体**
            quote_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', quote_text)
            card_type = detect_card_type(quote_text)
            card_html = f'<p style="font-size:{cfg["font_size"]};color:{cfg["text_color"]};line-height:{cfg["line_height"]};margin:0;">{quote_text}</p>'
            content_parts.append(make_card(card_html, card_type, style))
            continue

        # 无序列表
        if line.startswith("- ") or line.startswith("* "):
            list_items = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                item = lines[i].strip()[2:]
                # 支持 **粗体** 标记
                item = re.sub(r'\*\*(.+?)\*\*', rf'<strong style="color:{cfg["ul_color"]}">\1</strong>', item)
                list_items.append(f'<li style="margin-bottom:6px;">{item}</li>')
                i += 1
            content_parts.append(
                f'<ul style="font-size:{cfg["font_size"]};color:{cfg["text_color"]};'
                f'line-height:{cfg["line_height"]};padding-left:20px;margin:12px 0;">'
                f'{"".join(list_items)}</ul>'
            )
            continue

        # 有序列表
        if re.match(r'^\d+\.\s', line):
            list_items = []
            while i < len(lines) and re.match(r'^\d+\.\s', lines[i].strip()):
                item = re.sub(r'^\d+\.\s', '', lines[i].strip())
                item = re.sub(r'\*\*(.+?)\*\*', rf'<strong style="color:{cfg["ul_color"]}">\1</strong>', item)
                list_items.append(f'<li style="margin-bottom:6px;">{item}</li>')
                i += 1
            content_parts.append(
                f'<ol style="font-size:{cfg["font_size"]};color:{cfg["text_color"]};'
                f'line-height:{cfg["line_height"]};padding-left:20px;margin:12px 0;">'
                f'{"".join(list_items)}</ol>'
            )
            continue

        # 普通段落
        # 支持 **粗体**
        para = line
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
        content_parts.append(
            f'<p style="font-size:{cfg["font_size"]};color:{cfg["text_color"]};'
            f'line-height:{cfg["line_height"]};margin:0 0 12px;">{para}</p>'
        )
        i += 1

    # 如果没找到标题，用第一行非空内容作为标题
    if not title:
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#"):
                title = s[:30]
                break

    # 如果没找到副标题，尝试用日期或空
    if not subtitle:
        # 检查是否有日期格式的行
        for line in lines:
            s = line.strip()
            if re.match(r'^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', s) or re.match(r'^\d{1,2}[-/月]\d{1,2}', s):
                subtitle = s
                break
        if not subtitle:
            subtitle = ""

    content_html = "\n".join(content_parts)

    # 注入到模板
    template_html = template_html.replace("{{TITLE}}", title or "文章标题")
    template_html = template_html.replace("{{SUBTITLE}}", subtitle)
    template_html = template_html.replace("{{CONTENT}}", content_html)

    return template_html


# ── API 接口 ──

class TypesetRequest(BaseModel):
    markdown: str
    style: str = "zen"  # zen | minimal | tech


class TypesetResponse(BaseModel):
    preview_url: str
    style: str
    style_label: str


@app.post("/api/typeset", response_model=TypesetResponse)
async def typeset(req: TypesetRequest):
    if req.style not in STYLE_MAP:
        raise HTTPException(400, f"style 必须是 zen / minimal / tech，收到：{req.style}")
    if not req.markdown.strip():
        raise HTTPException(400, "markdown 内容不能为空")

    try:
        html = build_html(req.markdown, req.style)
        url = call_shiker_api(html)
        return TypesetResponse(
            preview_url=url,
            style=req.style,
            style_label=STYLE_LABELS[req.style],
        )
    except Exception as e:
        raise HTTPException(500, f"排版失败：{str(e)}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "styles": list(STYLE_LABELS.keys())}


# 静态文件服务（前端）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
else:
    @app.get("/")
    async def root():
        return HTMLResponse("<h1>前端文件未找到，请确保 static/ 目录存在</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=True)
