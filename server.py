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


# ── 智能文本预处理：纯文本 → 结构化 Markdown ──

# 语义标签 → 对应卡片类型的映射
SEMANTIC_LABELS = {
    # 感悟类
    "感悟": "insight", "心得": "insight", "体会": "insight", "思考": "insight",
    "领悟": "insight", "启发": "insight", "感想": "insight", "反思": "insight",
    # 实践类
    "实践": "practice", "案例": "practice", "应用": "practice", "操作": "practice",
    "步骤": "practice", "方法": "practice", "练习": "practice", "体验": "practice",
    "行动": "practice", "怎么做": "practice", "如何做": "practice",
    # 原文/引用类
    "原文": "quote", "经文": "quote", "经典": "quote", "引用": "quote",
    "子曰": "quote", "道德经": "quote", "论语": "quote", "金刚": "quote",
    "原典": "quote", "古文": "quote",
    # 总结类
    "总结": "summary", "小结": "summary", "结语": "summary", "寄语": "summary",
    "总而言之": "summary", "归纳": "summary", "概要": "summary",
    # 提示类
    "提示": "tip", "注意": "tip", "提醒": "tip", "建议": "tip",
    "补充": "tip", "说明": "tip", "备注": "tip", "注意": "tip",
    "小贴士": "tip", "温馨": "tip",
    # 引言类
    "引言": "intro", "前言": "intro", "导语": "intro", "开篇": "intro",
    "写在前面": "intro", "导读": "intro", "背景": "intro",
}

# 编译语义标签的正则（按长度降序，优先匹配长标签）
_sorted_labels = sorted(SEMANTIC_LABELS.keys(), key=len, reverse=True)
SEMANTIC_LABEL_RE = re.compile(
    r'^(?:【|「|〈|<)?(' + '|'.join(re.escape(k) for k in _sorted_labels) + r')(?:】|」|〉|>)?[\s：:]*',
    re.IGNORECASE
)

# 章节标题模式（中文序号）
SECTION_TITLE_RE = re.compile(
    r'^(?:'
    r'[一二三四五六七八九十百]+[、．.．]'   # 一、二、三、
    r'|第[一二三四五六七八九十百]+[章节篇]'  # 第一章、第二节
    r')\s*(.+)'
)


def is_short_heading(line: str, prev_line: str, next_line: str) -> bool:
    """
    判断一行是否像标题（不是标题语法但语义上是标题）。
    规则：短行(≤20字) + 前后有空行或紧跟内容行。
    """
    stripped = line.strip()
    if len(stripped) > 20 or len(stripped) < 2:
        return False
    # 排除明显是段落的行（含句号且较长）
    if '。' in stripped and len(stripped) > 10:
        return False
    # 排除以标点结尾的行
    if stripped[-1] in '，,；;：:、':
        return False
    # 前面有空行且后面有内容 → 很可能是标题
    if (not prev_line.strip()) and next_line.strip():
        return True
    return False


def smart_preprocess(raw_text: str) -> str:
    """
    智能预处理：把纯文本 / 半结构化文本转成结构化 Markdown。

    处理规则：
    1. "标题：xxx" / "标题:xxx" → 如果是语义标签，转成引用块；否则按标题处理
    2. "一、xxx" / "第一章 xxx" → 二级标题
    3. 短行可能是标题 → 自动提升
    4. 连续短行用顿号/逗号连接 → 可能是列表
    5. 第一行自动作为文章标题
    """
    lines = raw_text.strip().split("\n")
    result = []
    title_found = False
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 空行保留
        if not line:
            result.append("")
            i += 1
            continue

        # ── 规则1：已经是 Markdown 语法的，直接通过 ──
        if line.startswith("#") or line.startswith("> ") or line.startswith("- ") or line.startswith("* "):
            if line.startswith("# ") and not title_found:
                title_found = True
            result.append(line)
            i += 1
            continue

        # ── 规则2：匹配 "标题：内容" 或 "标签：内容" ──
        label_match = SEMANTIC_LABEL_RE.match(line)
        colon_match = re.match(r'^(.{1,6})[：:]\s*(.+)$', line)

        if label_match:
            # 语义标签开头 → 转成引用块（会触发卡片渲染）
            content_after_label = SEMANTIC_LABEL_RE.sub('', line, count=1).strip()
            # 检查后续行是否是同一标签的续行
            block_lines = [content_after_label]
            j = i + 1
            while j < len(lines):
                next_l = lines[j].strip()
                if not next_l or SEMANTIC_LABEL_RE.match(next_l) or next.startswith("#") or next.startswith(">"):
                    break
                block_lines.append(next_l)
                j += 1
            result.append("> " + "\n> ".join(block_lines))
            i = j
            continue

        if colon_match:
            label_text = colon_match.group(1)
            content_text = colon_match.group(2)

            # 标签是"标题"类关键词 → 设为主标题
            if label_text in ("标题", "题目", "主题") and not title_found:
                result.append(f"# {content_text}")
                title_found = True
                i += 1
                continue

            # 标签是"副标题"/"日期" → 记录但不特别处理
            if label_text in ("副标题", "日期", "时间", "作者"):
                result.append(line)  # 保留原样，后面会处理
                i += 1
                continue

            # 其他"xxx：yyy" → 如果label像语义标签，转引用块
            if label_text in SEMANTIC_LABELS:
                block_lines = [content_text]
                j = i + 1
                while j < len(lines):
                    next_l = lines[j].strip()
                    if not next_l or SEMANTIC_LABEL_RE.match(next_l) or next_l.startswith("#") or next_l.startswith(">"):
                        break
                    block_lines.append(next_l)
                    j += 1
                result.append(f"> {label_text}：" + "\n> ".join(block_lines))
                i = j
                continue

            # 其他"xxx：yyy" → 原样输出（可能是"地址：xxx"等普通内容）
            result.append(line)
            i += 1
            continue

        # ── 规则3a：有序列表行 "1. xxx" / "1、xxx" → 不转标题，保持原样 ──
        # 注意：只处理单数字开头（1-9），避免误伤大段列表
        if re.match(r'^[1-9][、．.．\)]\s*', line) and len(line) < 60:
            result.append(line)
            i += 1
            continue

        # ── 规则3b：章节标题模式 "一、xxx" / "第一章 xxx" ──
        section_match = SECTION_TITLE_RE.match(line)
        if section_match:
            section_title = section_match.group(1) if section_match.lastindex else line
            # 提取完整的标题文本
            result.append(f"## {line}")
            i += 1
            continue

        # ── 规则4：短行可能是标题 ──
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if is_short_heading(line, prev_line, next_line):
            result.append(f"## {line}")
            i += 1
            continue

        # ── 规则5：普通段落 ──
        result.append(line)
        i += 1

    # 如果没有找到标题，把第一行非空内容作为标题
    if not title_found:
        for idx, r in enumerate(result):
            if r.strip() and not r.startswith("#") and not r.startswith(">"):
                result[idx] = f"# {r}"
                break

    return "\n".join(result)


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
    支持纯文本、半结构化文本和标准 Markdown。
    """
    # 智能预处理：纯文本 → 结构化 Markdown
    markdown_text = smart_preprocess(markdown_text)

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
        # 处理 "标签：内容" 格式，高亮标签部分
        colon_match = re.match(r'^(.{1,6})([：:])(.+)$', para)
        if colon_match and len(colon_match.group(1)) <= 6:
            label = colon_match.group(1)
            sep = colon_match.group(2)
            rest = colon_match.group(3)
            para = f'<strong style="color:{cfg["title_color"]}">{label}</strong>{sep}{rest}'
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
