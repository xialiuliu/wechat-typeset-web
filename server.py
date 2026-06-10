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

# ── 公众号兼容：section → blockquote 转换 ──

SECTION_STYLE = (
    "margin:0;padding:16px 14px;"
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Microsoft YaHei',sans-serif;"
    "font-size:16px;color:#333;line-height:1.6;word-break:break-word;"
    "background:#f5f5f5;box-sizing:border-box"
)


def convert_to_wechat_html(raw_html: str) -> str:
    """
    将 HTML 中的 <section> 替换为 <blockquote>，
    公众号仅对 blockquote 保留背景色与边框。
    """
    # section → blockquote
    out = raw_html.replace("<section ", "<blockquote ").replace("</section>", "</blockquote>")
    # 外层包裹一个 section 作为整篇统一背景
    return f'<section data-tool="公众号排版" style="{SECTION_STYLE}">\n{out}\n</section>'


def call_shiker_api(html_content: str) -> str:
    """
    直接用 Python urllib 调用 edit.shiker.tech API 获取预览链接。
    不依赖 Node.js。
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

def build_html(markdown_text: str, style: str) -> str:
    """
    把用户输入的 Markdown / 纯文本，按照选定风格模板渲染为完整 HTML。
    """
    template_path = STYLE_MAP[style]
    template_html = template_path.read_text(encoding="utf-8")

    # 将 markdown 段落转换为 HTML 标签
    paragraphs = []

    for line in markdown_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            # 替换模板中的主标题
            template_html = template_html.replace("文章主标题", title, 1)
        elif line.startswith("## "):
            section_title = line[3:].strip()
            paragraphs.append(f'<h2 style="font-size:17px;font-weight:500;margin:24px 0 12px;">{section_title}</h2>')
        elif line.startswith("### "):
            sub = line[4:].strip()
            paragraphs.append(f'<h3 style="font-size:15px;font-weight:500;margin:18px 0 8px;">{sub}</h3>')
        elif line.startswith("> "):
            quote = line[2:].strip()
            paragraphs.append(f'<blockquote style="border-left:4px solid #c8a96e;margin:12px 0;padding:10px 16px;background:#fdf8f0;">{quote}</blockquote>')
        elif line.startswith("- ") or line.startswith("* "):
            item = line[2:].strip()
            paragraphs.append(f'<li style="margin:6px 0;">{item}</li>')
        else:
            paragraphs.append(f'<p style="font-size:15px;line-height:1.9;margin:0 0 12px;">{line}</p>')

    content_html = "\n".join(paragraphs)

    # 将段落内容注入到模板 body 的合适位置
    insert_marker = "</div>\n</body>"
    if insert_marker in template_html:
        content_block = f'\n  <!-- 用户内容 -->\n  {content_html}\n'
        template_html = template_html.replace(insert_marker, content_block + insert_marker, 1)
    else:
        # fallback：直接包裹
        template_html = template_html.replace("</body>", f"\n{content_html}\n</body>")

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
