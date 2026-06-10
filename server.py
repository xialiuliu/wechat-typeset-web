"""
公众号排版 Web 工具 - 后端 API
技术栈：FastAPI + 调用现有 Node.js 脚本
启动：python server.py
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
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
TYPESET_SCRIPT = PROJECT_DIR / "html-to-wechat-copy.js"

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

def build_html(markdown_text: str, style: str) -> str:
    """
    把用户输入的 Markdown / 纯文本，按照选定风格模板渲染为完整 HTML。
    使用 Node.js 通过已有排版脚本处理。
    如果没有 Node，则直接套模板包裹段落。
    """
    template_path = STYLE_MAP[style]
    template_html = template_path.read_text(encoding="utf-8")

    # 将 markdown 段落转换为 <p> 标签（简单处理）
    paragraphs = []
    current_section_title = None

    for line in markdown_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            # 替换模板中的主标题
            template_html = template_html.replace("文章主标题", title, 1)
        elif line.startswith("## "):
            current_section_title = line[3:].strip()
            paragraphs.append(f'<h2 style="font-size:17px;font-weight:500;margin:24px 0 12px;">{current_section_title}</h2>')
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

    # 将段落内容注入到模板 body 的合适位置（追加到已有内容后）
    insert_marker = "</div>\n</body>"
    if insert_marker in template_html:
        content_block = f'\n  <!-- 用户内容 -->\n  {content_html}\n'
        template_html = template_html.replace(insert_marker, content_block + insert_marker, 1)
    else:
        # fallback：直接包裹
        template_html = template_html.replace("</body>", f"\n{content_html}\n</body>")

    return template_html


def call_shiker_api(html_content: str) -> str:
    """
    调用 edit.shiker.tech API 获取预览链接。
    直接写临时文件 → node html-to-wechat-copy.js → 解析输出 URL。
    """
    # 检查脚本是否存在（服务器上可能没有 Node 环境或脚本）
    if not TYPESET_SCRIPT.exists():
        # 降级：直接返回 HTML 内容（用户可手动复制到 edit.shiker.tech）
        return f"data:text/html;base64,{html_content.encode('utf-8').hex()}"

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f:
        f.write(html_content)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["node", str(TYPESET_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "NODE_OPTIONS": ""}
        )
        output = result.stdout + result.stderr
        # 解析 URL（格式：https://edit.shiker.tech/copy.html?id=xxx）
        import re
        match = re.search(r"https://edit\.shiker\.tech/copy\.html\?id=[\w_]+", output)
        if match:
            return match.group(0)
        raise ValueError(f"未找到预览URL，脚本输出：{output[:300]}")
    finally:
        os.unlink(tmp_path)


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
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "排版超时，请重试")
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
