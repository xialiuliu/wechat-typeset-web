"""
公众号排版 Web 工具 - 后端 API
技术栈：FastAPI + Python 直接调用 edit.shiker.tech API（无需 Node.js）
启动：python server.py
"""

import re
import json
import os
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Request
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

# 访问记录中间件（过滤机器人，只记录真实访问）
@app.middleware("http")
async def track_visits(request: Request, call_next):
    # 只记录 GET 页面的访问（API 调用在各自端点内记录）
    if request.method == "GET" and not request.url.path.startswith("/api/"):
        ua = request.headers.get("user-agent", "")
        if not _is_bot(ua):
            ip = request.client.host if request.client else "-"
            referer = request.headers.get("referer", "")
            try:
                conn = sqlite3.connect(STATS_DB)
                conn.execute(
                    "INSERT INTO visits (ts, ip, path, ua, referer) VALUES (?,?,?,?,?)",
                    (datetime.now().isoformat(), ip, request.url.path, ua[:200], referer[:200]),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass  # 统计失败不影响主流程
    response = await call_next(request)
    return response

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


# ── 访问统计（SQLite，零依赖） ──

STATS_DB = PROJECT_DIR / "stats.db"
_BOT_KEYWORDS = ["bot", "crawl", "spider", "scan", "zgrab", "curl", "python", "go-http", "visionheight", "palo alto"]


def _init_stats_db():
    """初始化统计数据库"""
    conn = sqlite3.connect(STATS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT    NOT NULL,
            ip       TEXT    NOT NULL,
            path     TEXT    NOT NULL,
            ua       TEXT,
            referer  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_calls (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT    NOT NULL,
            ip       TEXT    NOT NULL,
            endpoint TEXT    NOT NULL,
            style    TEXT,
            has_ai  INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_ts ON visits(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_ts ON api_calls(ts)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT    NOT NULL,
            ip       TEXT    NOT NULL,
            content  TEXT    NOT NULL,
            contact  TEXT
        )
    """)
    conn.commit()
    conn.close()


def _is_bot(ua: str) -> bool:
    """判断是否为机器人（根据 User-Agent）"""
    if not ua:
        return True
    ua_lower = ua.lower()
    return any(kw in ua_lower for kw in _BOT_KEYWORDS)


def record_visit(request: Request, path: str = "/"):
    """记录页面访问（过滤机器人）"""
    ua = request.headers.get("user-agent", "")
    if _is_bot(ua):
        return
    ip = request.client.host if request.client else "-"
    referer = request.headers.get("referer", "")
    conn = sqlite3.connect(STATS_DB)
    conn.execute(
        "INSERT INTO visits (ts, ip, path, ua, referer) VALUES (?,?,?,?,?)",
        (datetime.now().isoformat(), ip, path, ua[:200], referer[:200]),
    )
    conn.commit()
    conn.close()


def record_api_call(request: Request, endpoint: str, style: str = "", has_ai: bool = False):
    """记录 API 调用"""
    ip = request.client.host if request.client else "-"
    conn = sqlite3.connect(STATS_DB)
    conn.execute(
        "INSERT INTO api_calls (ts, ip, endpoint, style, has_ai) VALUES (?,?,?,?,?)",
        (datetime.now().isoformat(), ip, endpoint, style, 1 if has_ai else 0),
    )
    conn.commit()
    conn.close()


def get_stats_summary() -> dict:
    """获取统计数据汇总"""
    conn = sqlite3.connect(STATS_DB)
    cur = conn.cursor()

    # 总访问量
    cur.execute("SELECT COUNT(*) FROM visits")
    total_visits = cur.fetchone()[0]

    # 今日访问量
    today = date.today().isoformat()
    cur.execute("SELECT COUNT(*) FROM visits WHERE ts >= ?", (today,))
    today_visits = cur.fetchone()[0]

    # 独立访客数（UV）
    cur.execute("SELECT COUNT(DISTINCT ip) FROM visits")
    total_uv = cur.fetchone()[0]

    # 今日独立访客
    cur.execute("SELECT COUNT(DISTINCT ip) FROM visits WHERE ts >= ?", (today,))
    today_uv = cur.fetchone()[0]

    # API 调用次数
    cur.execute("SELECT COUNT(*) FROM api_calls")
    total_api = cur.fetchone()[0]

    # 今日 API 调用
    cur.execute("SELECT COUNT(*) FROM api_calls WHERE ts >= ?", (today,))
    today_api = cur.fetchone()[0]

    # 按风格统计
    cur.execute("""
        SELECT style, COUNT(*) as cnt
        FROM api_calls
        WHERE style != ''
        GROUP BY style
        ORDER BY cnt DESC
    """)
    style_stats = [{"style": r[0], "count": r[1]} for r in cur.fetchall()]

    # 最近7天访问趋势
    cur.execute("""
        SELECT DATE(ts) as day, COUNT(*) as cnt
        FROM visits
        WHERE ts >= datetime('now', '-7 days')
        GROUP BY day
        ORDER BY day
    """)
    daily_trend = [{"date": r[0], "count": r[1]} for r in cur.fetchall()]

    # 访问来源
    cur.execute("""
        SELECT referer, COUNT(*) as cnt
        FROM visits
        WHERE referer != '' AND referer NOT LIKE '%110.40.186.71%'
        GROUP BY referer
        ORDER BY cnt DESC
        LIMIT 10
    """)
    referer_stats = [{"referer": r[0][:80], "count": r[1]} for r in cur.fetchall()]

    conn.close()

    return {
        "total_visits": total_visits,
        "today_visits": today_visits,
        "total_uv": total_uv,
        "today_uv": today_uv,
        "total_api_calls": total_api,
        "today_api_calls": today_api,
        "style_stats": style_stats,
        "daily_trend": daily_trend,
        "referer_stats": referer_stats,
    }


_init_stats_db()


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


# ── 段落内分块：识别大段文字中的章节标题并切分 ──

# 章节标题在段落中的模式（用于切分大段文字）
# 匹配：一、xxx 或 第一章 xxx 或 第x节 xxx 或 结语 等
INLINE_SECTION_RE = re.compile(
    r'(?<=[。！？\n])\s*'
    r'(?:'
    r'[一二三四五六七八九十百]+[、．.．]\s*[^，。！？\n]{2,20}'  # 一、修行从觉知自己开始
    r'|第[一二三四五六七八九十百]+[章节篇]\s*[^，。！？\n]{2,20}'  # 第一章 修行从觉知自己开始
    r'|(?:结语|结语：|结束语|后记|写在最后|总结)\s*[^，。！？\n]{0,20}'  # 结语
    r')'
    r'(?=[，。！？：；]|$|\n)'
)

# 结语/总结等结尾标记
CONCLUSION_RE = re.compile(r'(?:结语|结语：|结束语|后记|写在最后|总结语?)')

# 章节标题前缀模式（用于在段落中查找标题位置）
SECTION_PREFIX_RE = re.compile(r'[一二三四五六七八九十百]+[、．.．]')
SECTION_NUM_PREFIX_RE = re.compile(r'第[一二三四五六七八九十百]+[章节篇]')


def extract_heading(text: str, start: int, prefix_len: int) -> tuple:
    """
    从标题前缀位置提取完整的标题文本。
    策略：
    1. 先尝试找到标题的"自然结尾"——标点后紧跟正文指示词
    2. 中文标题中逗号/冒号可保留（如"既不迷失，也不紧盯"）
    3. 句号/感叹号/问号一定截断
    4. 逗号后如果紧跟正文指示词则截断，否则保留（属于标题一部分）
    返回 (heading_text, end_pos)
    """
    # 标题内容从前缀后开始
    content_start = start + prefix_len
    content = text[content_start:]

    # ── 正文指示词（出现在标题后，明确标志正文开始） ──
    # 短词：1-2字，紧跟标题后
    body_starters_short = [
        '我们', '他们', '她们', '大家', '人们', '人们',
        '有些', '许多', '很多', '还有', '但是', '然而', '因此', '所以',
        '如果', '因为', '虽然', '不过', '而且', '并且', '而是',
        '这样', '那样', '这些', '那些', '这个', '那个',
        '其实', '首先', '最初', '最终', '最后', '进一步',
        '甚至', '只是', '如此', '当心', '就像', '对于',
        '真正', '往往', '始终', '一直', '渐渐', '慢慢',
        '如果', '可以', '应该', '必须', '需要', '能够',
        '不再', '还是', '也是', '又是', '也不是',
    ]
    # 短语：3+字，紧跟标题后
    body_starters_phrase = [
        '在日常生活中', '很多人', '修行人', '修行时', '修行路上',
        '开示说', '隆波说', '师父说', '老师说',
        '当我们', '们看到', '还有一个', '也是如此',
        '最重要的是', '关键是', '核心是',
        '最常见的', '最容易', '最常见',
    ]
    # 人名/称谓（可能出现在标题和正文之间，如"七、xxx隆波开示说"）
    name_stoppers = ['隆波', '师父', '老师', '尊者', '法师', '大师', '禅师', '仁波切']

    # ── 策略：逐步扫描，判断每个标点是否是标题边界 ──
    # 找到所有候选截断点（标点位置）
    max_heading_len = 22  # 标题最大长度（含前缀内容）

    best_cut = len(content)  # 默认截到末尾

    # 先检查句号/感叹号/问号/分号——这些一定是截断点
    for punct in '。！？；':
        pos = content.find(punct)
        if pos != -1 and pos < best_cut and pos > 0:
            best_cut = pos

    # 检查正文指示词（短语优先，因为更精确）
    for phrase in body_starters_phrase:
        pos = content.find(phrase)
        if pos != -1 and pos < best_cut and pos > 0:
            best_cut = pos

    # 检查人名/称谓
    for name in name_stoppers:
        pos = content.find(name)
        if pos != -1 and pos < best_cut and pos > 0:
            best_cut = pos

    # 检查短词指示词（但需要更谨慎——短词可能在标题内部）
    for word in body_starters_short:
        pos = content.find(word)
        if pos != -1 and pos < best_cut and pos > 0:
            # 短词只有在标题已经足够长(>6字)时才截断
            # 或者短词紧跟在标点后面
            if pos > 6 or (pos > 0 and content[pos - 1] in '，,：:、'):
                best_cut = pos

    # ── 逗号特殊处理 ──
    # 逗号可能是标题内部分隔（如"既不迷失，也不紧盯"）也可能是标题-正文边界
    # 规则：如果逗号后紧跟正文指示词，则在此逗号处截断；否则保留
    for m in re.finditer('，', content):
        comma_pos = m.start()
        if comma_pos >= best_cut or comma_pos == 0:
            continue
        after_comma = content[comma_pos + 1:]
        # 检查逗号后是否紧跟正文指示词
        is_boundary = False
        for phrase in body_starters_phrase:
            if after_comma.startswith(phrase):
                is_boundary = True
                break
        if not is_boundary:
            for name in name_stoppers:
                if after_comma.startswith(name):
                    is_boundary = True
                    break
        if not is_boundary:
            for word in body_starters_short:
                if after_comma.startswith(word) and comma_pos > 6:
                    is_boundary = True
                    break
        if is_boundary and comma_pos < best_cut:
            best_cut = comma_pos

    # ── 最终截取 ──
    heading_content = content[:best_cut].strip()

    # 限制最大长度
    if len(heading_content) > max_heading_len:
        heading_content = heading_content[:max_heading_len]

    end_pos = content_start + len(heading_content)
    heading_text = text[start:start + prefix_len] + heading_content

    return heading_text.strip(), end_pos


def split_long_paragraph(text: str) -> list:
    """
    把大段文字按章节标题切分成多个块。
    返回 [(type, content), ...]，type 为 'heading' 或 'paragraph'
    """
    parts = []
    last_end = 0

    # 收集所有标题位置
    headings = []

    # 匹配 "一、xxx" 模式
    for m in SECTION_PREFIX_RE.finditer(text):
        heading_text, end_pos = extract_heading(text, m.start(), len(m.group(0)))
        # 验证：标题后面应该跟着正文
        if end_pos < len(text) - 1 and len(heading_text) > 2:
            headings.append((m.start(), end_pos, heading_text))

    # 匹配 "第一章 xxx" 模式
    for m in SECTION_NUM_PREFIX_RE.finditer(text):
        heading_text, end_pos = extract_heading(text, m.start(), len(m.group(0)))
        if end_pos < len(text) - 1 and len(heading_text) > 2:
            headings.append((m.start(), end_pos, heading_text))

    # 匹配 "结语" 等结尾标记
    for m in CONCLUSION_RE.finditer(text):
        heading_text = m.group(0).strip()
        headings.append((m.start(), m.end(), heading_text))

    # 按位置排序
    headings.sort(key=lambda x: x[0])

    # 去重：移除重叠的标题（保留前面的）
    filtered = []
    for h in headings:
        if not filtered or h[0] >= filtered[-1][1]:
            filtered.append(h)
    headings = filtered

    # 切分
    for start, end, heading_text in headings:
        # 标题前的内容 → 普通段落
        if start > last_end:
            prev_text = text[last_end:start].strip()
            if prev_text:
                parts.append(("paragraph", prev_text))
        # 标题本身
        parts.append(("heading", heading_text))
        last_end = end

    # 剩余内容
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            parts.append(("paragraph", remaining))

    # 如果没有切分出任何标题，返回整段
    if not parts:
        parts.append(("paragraph", text))

    return parts


def smart_preprocess(raw_text: str) -> str:
    """
    智能预处理：把纯文本 / 半结构化文本转成结构化 Markdown。

    处理规则：
    1. 大段无换行文字 → 按章节标题智能切分
    2. "标题：xxx" / "标题:xxx" → 主标题
    3. "一、xxx" / "第一章 xxx" → 二级标题
    4. 语义标签（感悟/实践/原文等）→ 引用块（卡片）
    5. 短行可能是标题 → 自动提升
    6. 第一行自动作为文章标题
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

        # ── 规则2：超长单行（>200字且无换行）→ 段落内智能分块 ──
        if len(line) > 200 and "\n" not in line:
            chunks = split_long_paragraph(line)
            for chunk_type, chunk_text in chunks:
                if chunk_type == "heading":
                    result.append(f"## {chunk_text}")
                else:
                    # 对段落内容进一步处理语义标签
                    result.extend(_process_paragraph(chunk_text))
            i += 1
            continue

        # ── 规则3：匹配 "标题：内容" 或 "标签：内容" ──
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
                if not next_l or SEMANTIC_LABEL_RE.match(next_l) or next_l.startswith("#") or next_l.startswith(">"):
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
                result.append(line)
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

            # 其他"xxx：yyy" → 原样输出
            result.append(line)
            i += 1
            continue

        # ── 规则4a：有序列表行 "1. xxx" / "1、xxx" → 不转标题 ──
        if re.match(r'^[1-9][、．.．\)]\s*', line) and len(line) < 60:
            result.append(line)
            i += 1
            continue

        # ── 规则4b：章节标题模式 "一、xxx" / "第一章 xxx" ──
        section_match = SECTION_TITLE_RE.match(line)
        if section_match:
            result.append(f"## {line}")
            i += 1
            continue

        # ── 规则5：短行可能是标题 ──
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if is_short_heading(line, prev_line, next_line):
            result.append(f"## {line}")
            i += 1
            continue

        # ── 规则6：普通段落，检查是否包含内联语义标签 ──
        result.extend(_process_paragraph(line))
        i += 1

    # 如果没有找到标题，把第一行非空内容作为标题
    if not title_found:
        for idx, r in enumerate(result):
            if r.strip() and not r.startswith("#") and not r.startswith(">"):
                # 如果段落过长，提取短标题并保留完整段落作为引言
                if len(r) > 40:
                    # 尝试在第一个句号/逗号处截取
                    for punct_pos, ch in enumerate(r):
                        if ch in '。！？' and punct_pos > 4:
                            short_title = r[:punct_pos]
                            result[idx] = f"# {short_title}"
                            # 在标题后插入完整段落作为引言
                            result.insert(idx + 1, f"> {r}")
                            break
                    else:
                        # 没有找到合适截断点，取前15字
                        result[idx] = f"# {r[:15]}…"
                        result.insert(idx + 1, r)
                else:
                    result[idx] = f"# {r}"
                break

    return "\n".join(result)


def _process_paragraph(text: str) -> list:
    """
    处理段落内容：检测内联语义标签（感悟/实践/原文等），转成引用块。
    返回行列表。
    """
    result = []
    # 检测段落中是否包含语义标签模式（如"感悟：xxx"）
    # 策略：找所有语义标签位置，切分段落
    last_end = 0
    found_label = False

    for m in SEMANTIC_LABEL_RE.finditer(text):
        # 标签前的内容 → 普通段落
        if m.start() > last_end:
            prev = text[last_end:m.start()].strip()
            if prev:
                result.append(prev)

        # 提取标签和后续内容
        label = m.group(1)
        rest = text[m.end():].strip()

        # 找到下一个标签或段落结束的位置
        next_label_pos = len(text)
        for nm in SEMANTIC_LABEL_RE.finditer(text, m.end()):
            next_label_pos = nm.start()
            break

        content = text[m.end():next_label_pos].strip()
        if content:
            result.append(f"> {label}：{content}")
            found_label = True

        last_end = next_label_pos

    # 剩余内容
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            result.append(remaining)

    # 如果没有发现任何语义标签，返回整段
    if not found_label and not result:
        result.append(text)

    return result


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


# ── DeepSeek AI 配置 ──

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

# 从 .env 文件加载 API Key（服务器部署时使用）
_env_path = PROJECT_DIR / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key == "DEEPSEEK_API_KEY" and not DEEPSEEK_API_KEY:
                DEEPSEEK_API_KEY = val

# AI 写作系统提示词
AI_SYSTEM_PROMPT = """你是一位资深公众号写手，擅长将话题写成有深度、有温度的文章。

请按以下规则输出：

1. 第一行必须是文章标题，用 # 标题 格式
2. 用中文序号划分章节：## 一、xxx、## 二、xxx、## 三、xxx ...
3. 每个章节下面有 2-3 段正文
4. 适当使用语义标签来突出重点内容：
   - 感悟：xxx （会渲染为绿色卡片，适合心得体会）
   - 实践：xxx （会渲染为橙色卡片，适合可操作的建议）
   - 原文：xxx （会渲染为米色卡片，适合引用经典原文）
   - 注意：xxx （会渲染为金边卡片，适合提醒要点）
5. 每个语义标签独占一行，不要和其他内容混在一行
6. 语言真诚自然，不要有AI味，避免使用"让我们""总的来说""值得注意的是"等套话
7. 文章结尾要有结语章节
8. 总字数控制在 800-1500 字

输出示例格式：
# 文章标题

引言段落...

## 一、第一个章节

正文内容...

感悟：这里是感悟内容，会显示为绿色卡片

更多正文...

实践：这里是可以操作的建议，会显示为橙色卡片

## 二、第二个章节
...

## 结语

总结段落..."""


def call_deepseek_api(user_prompt: str, article_style: str = "") -> str:
    """
    调用 DeepSeek API 生成文章内容。
    返回生成的 Markdown 文本。
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError("DeepSeek API Key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY")

    # 根据排版风格调整写作提示
    style_hints = {
        "zen": "文章风格：禅意、古朴、沉稳，适合修行/哲学/传统文化主题",
        "minimal": "文章风格：简洁、留白、清爽，适合生活随笔/个人成长主题",
        "tech": "文章风格：理性、数据驱动、专业，适合技术/商业/职场主题",
    }
    style_hint = style_hints.get(article_style, "")

    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": f"{style_hint}\n\n{user_prompt}" if style_hint else user_prompt},
    ]

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": 3000,
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_BASE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return content.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"DeepSeek API 返回 HTTP {e.code}：{body}")
    except urllib.error.URLError as e:
        raise ValueError(f"DeepSeek API 网络请求失败：{e.reason}")
    except KeyError:
        raise ValueError(f"DeepSeek API 返回格式异常：{json.dumps(data, ensure_ascii=False)[:300]}")


# ── API 接口 ──

class TypesetRequest(BaseModel):
    markdown: str
    style: str = "zen"  # zen | minimal | tech


class TypesetResponse(BaseModel):
    preview_url: str
    style: str
    style_label: str


@app.post("/api/typeset", response_model=TypesetResponse)
async def typeset(req: TypesetRequest, request: Request):
    if req.style not in STYLE_MAP:
        raise HTTPException(400, f"style 必须是 zen / minimal / tech，收到：{req.style}")
    if not req.markdown.strip():
        raise HTTPException(400, "markdown 内容不能为空")

    try:
        html = build_html(req.markdown, req.style)
        url = call_shiker_api(html)
        record_api_call(request, "/api/typeset", style=req.style)
        return TypesetResponse(
            preview_url=url,
            style=req.style,
            style_label=STYLE_LABELS[req.style],
        )
    except Exception as e:
        raise HTTPException(500, f"排版失败：{str(e)}")


# ── AI 写作 + 排版 ──

class AiWriteRequest(BaseModel):
    prompt: str           # 用户指令/话题
    style: str = "zen"    # 排版风格
    reference: str = ""   # 可选：参考资料/素材


class AiWriteResponse(BaseModel):
    preview_url: str
    style: str
    style_label: str
    article: str          # AI 生成的文章内容（Markdown）


@app.post("/api/ai-write", response_model=AiWriteResponse)
async def ai_write(req: AiWriteRequest, request: Request):
    if req.style not in STYLE_MAP:
        raise HTTPException(400, f"style 必须是 zen / minimal / tech，收到：{req.style}")
    if not req.prompt.strip():
        raise HTTPException(400, "请输入写作指令或话题")

    try:
        # 构建用户提示
        user_prompt = req.prompt.strip()
        if req.reference.strip():
            user_prompt += f"\n\n参考资料/素材：\n{req.reference.strip()}"

        # 调用 DeepSeek 生成文章
        article = call_deepseek_api(user_prompt, req.style)

        # 排版
        html = build_html(article, req.style)
        url = call_shiker_api(html)

        record_api_call(request, "/api/ai-write", style=req.style, has_ai=True)
        return AiWriteResponse(
            preview_url=url,
            style=req.style,
            style_label=STYLE_LABELS[req.style],
            article=article,
        )
    except ValueError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI 写作失败：{str(e)}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "styles": list(STYLE_LABELS.keys())}


@app.get("/api/stats")
async def stats():
    """返回访问统计数据（JSON）"""
    return get_stats_summary()


@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    """简单的统计页面"""
    s = get_stats_summary()
    today = date.today().isoformat()

    # 构建风格统计表格行
    style_rows = ""
    for item in s["style_stats"]:
        label = STYLE_LABELS.get(item["style"], item["style"])
        style_rows += f"<tr><td>{label}</td><td>{item['count']}</td></tr>"

    # 构建每日趋势表格行
    trend_rows = ""
    for item in s["daily_trend"]:
        trend_rows += f"<tr><td>{item['date']}</td><td>{item['count']}</td></tr>"

    # 构建来源表格行
    referer_rows = ""
    for item in s["referer_stats"]:
        referer_rows += f"<tr><td>{item['referer']}</td><td>{item['count']}</td></tr>"

    if not style_rows:
        style_rows = "<tr><td colspan='2'>暂无数据</td></tr>"
    if not trend_rows:
        trend_rows = "<tr><td colspan='2'>暂无数据</td></tr>"
    if not referer_rows:
        referer_rows = "<tr><td colspan='2'>暂无数据</td></tr>"

    # 反馈列表
    feedback_html = ""
    try:
        conn = sqlite3.connect(STATS_DB)
        cur = conn.cursor()
        cur.execute("SELECT id, ts, content, contact FROM feedbacks ORDER BY id DESC LIMIT 30")
        feedbacks = cur.fetchall()
        conn.close()
        for fb in feedbacks:
            fb_ts = fb[1][:16].replace("T", " ")
            fb_content = fb[2].replace("<", "&lt;").replace(">", "&gt;")
            fb_contact = fb[3] or ""
            feedback_html += f'<div style="padding:12px;border-bottom:1px solid #f0f0f0;"><div style="font-size:12px;color:#999;margin-bottom:4px;">{fb_ts}</div><div style="font-size:14px;color:#333;line-height:1.6;">{fb_content}</div>'
            if fb_contact:
                feedback_html += f'<div style="font-size:12px;color:#1890ff;margin-top:4px;">联系方式: {fb_contact}</div>'
            feedback_html += '</div>'
    except Exception:
        feedback_html = "<p>暂无反馈数据</p>"

    if not feedback_html:
        feedback_html = "<p style='color:#999;text-align:center;padding:20px;'>暂无反馈数据</p>"

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>访问统计 - 公众号排版工具</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
  h1 {{ color: #333; }}
  .card {{ background: white; border-radius: 8px; padding: 20px; margin: 16px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
  .metric {{ text-align: center; padding: 16px; background: #f0f7ff; border-radius: 8px; }}
  .metric .num {{ font-size: 28px; font-weight: bold; color: #1890ff; }}
  .metric .label {{ font-size: 13px; color: #666; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; color: #666; font-size: 13px; }}
  .updated {{ color: #999; font-size: 13px; margin-top: 20px; }}
  a {{ color: #1890ff; text-decoration: none; }}
</style>
</head>
<body>
<h1>📊 访问统计</h1>
<p class="updated">更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<div class="card">
  <h3>核心指标</h3>
  <div class="metrics">
    <div class="metric"><div class="num">{s["today_visits"]}</div><div class="label">今日访问</div></div>
    <div class="metric"><div class="num">{s["today_uv"]}</div><div class="label">今日独立访客</div></div>
    <div class="metric"><div class="num">{s["today_api_calls"]}</div><div class="label">今日排版次数</div></div>
    <div class="metric"><div class="num">{s["total_visits"]}</div><div class="label">累计访问</div></div>
    <div class="metric"><div class="num">{s["total_uv"]}</div><div class="label">累计独立访客</div></div>
    <div class="metric"><div class="num">{s["total_api_calls"]}</div><div class="label">累计排版次数</div></div>
  </div>
</div>

<div class="card">
  <h3>风格使用统计</h3>
  <table><tr><th>风格</th><th>使用次数</th></tr>{style_rows}</table>
</div>

<div class="card">
  <h3>最近7天访问趋势</h3>
  <table><tr><th>日期</th><th>访问次数</th></tr>{trend_rows}</table>
</div>

<div class="card">
  <h3>访问来源</h3>
  <table><tr><th>来源</th><th>次数</th></tr>{referer_rows}</table>
</div>

<div class="card">
  <h3>用户反馈</h3>
  {feedback_html}
</div>

<p><a href="/">← 返回首页</a></p>
</body>
</html>"""
    return HTMLResponse(html)


# ── 用户反馈 ──

class FeedbackRequest(BaseModel):
    content: str           # 反馈内容
    contact: str = ""      # 可选：联系方式


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest, request: Request):
    """接收用户反馈意见"""
    content = req.content.strip()
    if not content:
        raise HTTPException(400, "反馈内容不能为空")
    if len(content) > 2000:
        raise HTTPException(400, "反馈内容不能超过2000字")

    ip = request.client.host if request.client else "-"
    contact = req.contact.strip()[:200] if req.contact else ""

    try:
        conn = sqlite3.connect(STATS_DB)
        conn.execute(
            "INSERT INTO feedbacks (ts, ip, content, contact) VALUES (?,?,?,?)",
            (datetime.now().isoformat(), ip, content, contact),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(500, f"反馈提交失败：{str(e)}")

    return {"success": True, "message": "感谢你的反馈！"}


@app.get("/api/feedbacks")
async def list_feedbacks():
    """获取反馈列表（用于统计页展示）"""
    conn = sqlite3.connect(STATS_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, ts, content, contact FROM feedbacks ORDER BY id DESC LIMIT 50")
    rows = [{"id": r[0], "ts": r[1], "content": r[2], "contact": r[3]} for r in cur.fetchall()]
    conn.close()
    return {"count": len(rows), "items": rows}


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
