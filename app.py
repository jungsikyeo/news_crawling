import streamlit as st
import pandas as pd
import base64
import os
from streamlit_echarts import st_echarts
from datetime import datetime, date

from db.database import (
    init_db, get_connection, get_news_list, get_news_count,
    save_search_history, get_search_history, delete_search_history,
    get_stats_by_date, get_stats_by_publisher, get_stats_by_portal,
    get_stats_by_keyword, get_stats_hourly,
)
from utils.scheduler import CrawlScheduler

# --- Page Config ---
st.set_page_config(
    page_title="NEWSDESK",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- DB ---
init_db()

# --- Session State ---
if "scheduler" not in st.session_state:
    st.session_state.scheduler = CrawlScheduler()
if "crawling_active" not in st.session_state:
    st.session_state.crawling_active = False
if "keywords_list" not in st.session_state:
    st.session_state.keywords_list = []

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _load_icon_b64(filename: str) -> str:
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = filename.rsplit(".", 1)[-1].lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "svg": "svg+xml"}.get(ext, "png")
    return f"data:image/{mime};base64,{data}"


PORTAL_OPTIONS = {
    "naver": {"name": "네이버", "color": "#03C75A", "emoji": "N", "icon": _load_icon_b64("naver.jpg")},
    "daum": {"name": "다음", "color": "#3D6AFE", "emoji": "D", "icon": _load_icon_b64("daum.jpeg")},
    "nate": {"name": "네이트", "color": "#EF4444", "emoji": "T", "icon": _load_icon_b64("nate.png")},
}

INTERVAL_OPTIONS = {
    "5분": 5, "10분": 10, "15분": 15, "30분": 30,
    "1시간": 60, "2시간": 120, "6시간": 360, "12시간": 720, "24시간": 1440,
}


# ──────────────────────────────────────────────
# Custom Theme CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #12121a;
    --bg-card: #181822;
    --bg-card-hover: #1e1e2e;
    --border: #2a2a3a;
    --border-light: #333348;
    --text-primary: #e8e8f0;
    --text-secondary: #8888a0;
    --text-muted: #55556a;
    --accent: #6366f1;
    --accent-dim: #4f46e5;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
}

/* ── Hide Streamlit toolbar (Deploy button area) ── */
header[data-testid="stHeader"] {
    display: none !important;
}
#MainMenu { display: none !important; }
footer { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--text-primary) !important;
}

.stApp {
    background: var(--bg-primary) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] label {
    color: var(--text-primary) !important;
}

/* ── Inputs ── */
.stTextArea textarea,
.stTextInput input {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
    font-family: 'Pretendard', sans-serif !important;
    transition: border-color 0.2s ease;
}
.stTextArea textarea:focus,
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}
.stTextInput input::placeholder {
    color: #6a6a80 !important;
    opacity: 1 !important;
}

.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
}

/* ── Date Input ── */
.stDateInput > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
}
.stDateInput input {
    color: var(--text-primary) !important;
}

/* ── Checkbox hidden, custom portal toggle ── */
.stCheckbox label span {
    color: var(--text-primary) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-family: 'Pretendard', sans-serif !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em;
}
.stButton > button:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--accent-dim) !important;
    color: #fff !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: transparent;
    border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 12px 24px !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-family: 'Pretendard', sans-serif !important;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: var(--accent) !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none;
}

/* ── Metric ── */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 16px;
}
div[data-testid="stMetric"] label {
    color: var(--text-muted) !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
}

/* ── Alerts ── */
.stAlert > div {
    border-radius: 8px !important;
    border: none !important;
    font-family: 'Pretendard', sans-serif !important;
}

/* ── Divider ── */
hr {
    border-color: var(--border) !important;
    opacity: 0.5;
}

/* ── Download Button ── */
.stDownloadButton > button {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* ── Custom Components ── */
.nd-header {
    padding: 8px 0 24px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.nd-logo {
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-primary);
    line-height: 1;
}
.nd-logo-accent {
    color: var(--accent);
}
.nd-subtitle {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-top: 4px;
}

.nd-section-label {
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 600;
    margin-bottom: 8px;
    margin-top: 20px;
}

/* ── Multiselect (keyword tags) ── */
div[data-testid="stMultiSelect"] > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(99, 102, 241, 0.15) !important;
    border-radius: 6px !important;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
    color: #a5b4fc !important;
}

/* ── Pills (st.pills) ── */
div[data-testid="stPills"] button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
    border-radius: 8px !important;
    font-family: 'Pretendard', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
    padding: 6px 14px !important;
}
div[data-testid="stPills"] button:hover {
    border-color: var(--accent) !important;
    color: var(--text-primary) !important;
}
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[data-selected="true"] {
    background: rgba(99, 102, 241, 0.15) !important;
    border-color: var(--accent) !important;
    color: #a5b4fc !important;
}

/* ── Status ── */
.nd-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 8px;
    letter-spacing: 0.03em;
}
.nd-status-active {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.2);
    color: var(--success);
}
.nd-status-idle {
    background: rgba(136, 136, 160, 0.06);
    border: 1px solid var(--border);
    color: var(--text-muted);
}
.nd-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.nd-status-active .nd-status-dot {
    background: var(--success);
    box-shadow: 0 0 6px var(--success);
    animation: pulse-dot 2s infinite;
}
.nd-status-idle .nd-status-dot { background: var(--text-muted); }

@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.nd-stat-row {
    font-size: 0.75rem;
    color: var(--text-secondary);
    padding: 4px 0;
}

/* ── News Card ── */
.nd-news-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.nd-news-card:hover {
    border-color: var(--border-light);
    background: var(--bg-card-hover);
}

.nd-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 5px;
    font-size: 0.65rem;
    font-weight: 800;
    color: #fff;
    margin-right: 5px;
    letter-spacing: -0.02em;
}
.nd-badge-img {
    width: 22px;
    height: 22px;
    border-radius: 5px;
    margin-right: 5px;
    object-fit: cover;
    vertical-align: middle;
}

/* ── Portal selector icons ── */
.nd-portal-selector {
    display: flex;
    gap: 10px;
    margin-top: 4px;
}
.nd-portal-icon-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.nd-portal-icon-wrap img {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    object-fit: cover;
    transition: all 0.2s ease;
}
.nd-portal-icon-wrap.active img {
    box-shadow: 0 0 0 2px var(--accent), 0 0 10px rgba(99,102,241,0.3);
}
.nd-portal-icon-wrap.inactive img {
    opacity: 0.3;
    filter: grayscale(0.5);
}
.nd-portal-icon-label {
    font-size: 0.65rem;
    color: var(--text-muted);
    text-align: center;
}

.nd-news-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.5;
    margin: 8px 0 6px 0;
    letter-spacing: -0.01em;
}
.nd-news-title a {
    color: var(--text-primary) !important;
    text-decoration: none !important;
}
.nd-news-title a:hover {
    color: var(--accent) !important;
}

.nd-news-desc {
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 10px;
}

.nd-news-meta {
    display: flex;
    gap: 16px;
    font-size: 0.72rem;
    color: var(--text-muted);
}
.nd-news-meta span {
    display: flex;
    align-items: center;
    gap: 4px;
}

.nd-keyword-tag {
    display: inline-block;
    background: rgba(99, 102, 241, 0.1);
    color: var(--accent);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 500;
}

.nd-empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}
.nd-empty-icon {
    font-size: 2.5rem;
    margin-bottom: 12px;
    opacity: 0.3;
}
.nd-empty-text {
    font-size: 0.85rem;
    line-height: 1.6;
}

/* ── History ── */
.nd-history-row {
    display: flex;
    align-items: center;
    padding: 14px 18px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 8px;
    gap: 20px;
    transition: border-color 0.2s ease;
}
.nd-history-row:hover {
    border-color: var(--border-light);
}
.nd-history-keywords {
    flex: 3;
    font-weight: 600;
    font-size: 0.88rem;
    color: var(--text-primary);
}
.nd-history-portals {
    flex: 2;
    font-size: 0.8rem;
    color: var(--text-secondary);
}
.nd-history-interval {
    flex: 1;
    font-size: 0.8rem;
    color: var(--text-muted);
    text-align: center;
}
.nd-history-date {
    flex: 2;
    font-size: 0.72rem;
    color: var(--text-muted);
    text-align: right;
}

.nd-page-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    margin-bottom: 4px;
}
.nd-page-count {
    font-size: 0.78rem;
    color: var(--text-muted);
    font-weight: 400;
}

</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# ECharts Theme
# ──────────────────────────────────────────────
ECHART_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316", "#ec4899"]

ECHART_BASE = {
    "backgroundColor": "transparent",
    "textStyle": {"fontFamily": "Pretendard, sans-serif", "color": "#8888a0"},
    "legend": {"textStyle": {"color": "#8888a0"}},
    "tooltip": {
        "trigger": "axis",
        "backgroundColor": "#1e1e2e",
        "borderColor": "#2a2a3a",
        "textStyle": {"color": "#e8e8f0", "fontSize": 12},
    },
}


def render_portal_badges(portals_str: str) -> str:
    if not portals_str:
        return ""
    badges = []
    for portal in portals_str.split(","):
        portal = portal.strip()
        info = PORTAL_OPTIONS.get(portal, {})
        icon = info.get("icon", "")
        name = info.get("name", portal)
        if icon:
            badges.append(f'<img class="nd-badge-img" src="{icon}" alt="{name}" title="{name}">')
        else:
            color = info.get("color", "#555")
            emoji = info.get("emoji", "?")
            badges.append(f'<span class="nd-badge" style="background:{color}">{emoji}</span>')
    return "".join(badges)


def render_news_card(item):
    badges = render_portal_badges(item["portals"])
    title = item["title"]
    url = item["url"]
    desc = item["description"] or ""
    if len(desc) > 120:
        desc = desc[:120] + "..."

    meta_parts = []
    if item["publisher"]:
        meta_parts.append(f"<span>{item['publisher']}</span>")
    if item["published_at"]:
        meta_parts.append(f"<span>{item['published_at']}</span>")
    meta_html = "".join(meta_parts)

    keyword_tag = f'<span class="nd-keyword-tag">{item["keyword"]}</span>'

    return f"""
    <div class="nd-news-card">
        <div>{badges} {keyword_tag}</div>
        <div class="nd-news-title"><a href="{url}" target="_blank">{title}</a></div>
        {"<div class='nd-news-desc'>" + desc + "</div>" if desc else ""}
        <div class="nd-news-meta">{meta_html}</div>
    </div>
    """


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="nd-header">
        <div class="nd-logo">NEWS<span class="nd-logo-accent">DESK</span></div>
        <div class="nd-subtitle">Automated News Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Keywords: input + button to add, multiselect to manage ──
    st.markdown('<div class="nd-section-label">KEYWORDS</div>', unsafe_allow_html=True)
    kw_col1, kw_col2 = st.columns([5, 1])
    with kw_col1:
        new_kw = st.text_input("키워드", placeholder="키워드 입력 후 추가", key="new_kw_input", label_visibility="collapsed")
    with kw_col2:
        add_kw = st.button("+", key="add_kw", use_container_width=True)
    if add_kw and new_kw.strip():
        kw = new_kw.strip()
        if kw not in st.session_state.keywords_list:
            st.session_state.keywords_list.append(kw)
            st.rerun()
    if st.session_state.keywords_list:
        kept = st.multiselect(
            "등록된 키워드",
            options=st.session_state.keywords_list,
            default=st.session_state.keywords_list,
            label_visibility="collapsed",
        )
        if set(kept) != set(st.session_state.keywords_list):
            st.session_state.keywords_list = list(kept)
            st.rerun()

    # ── Portals: image icons via st.image + checkbox ──
    st.markdown('<div class="nd-section-label">PORTALS</div>', unsafe_allow_html=True)
    selected_portals = []
    portal_cols = st.columns(3)
    for i, (key, info) in enumerate(PORTAL_OPTIONS.items()):
        with portal_cols[i]:
            icon_path = os.path.join(ASSETS_DIR, {"naver": "naver.jpg", "daum": "daum.jpeg", "nate": "nate.png"}[key])
            st.image(icon_path, width=40)
            if st.checkbox(info["name"], key=f"portal_{key}"):
                selected_portals.append(key)

    # ── Search date ──
    st.markdown('<div class="nd-section-label">SEARCH FROM</div>', unsafe_allow_html=True)
    search_start_date = st.date_input(
        "검색 시작일",
        value=date.today(),
        label_visibility="collapsed",
    )

    # ── Interval ──
    st.markdown('<div class="nd-section-label">INTERVAL</div>', unsafe_allow_html=True)
    interval_label = st.selectbox(
        "주기",
        options=list(INTERVAL_OPTIONS.keys()),
        index=2,
        label_visibility="collapsed",
    )
    interval_minutes = INTERVAL_OPTIONS[interval_label]

    st.markdown("")

    # ── Action buttons ──
    col1, col2 = st.columns(2)
    with col1:
        start_clicked = st.button("START", use_container_width=True, type="primary")
    with col2:
        stop_clicked = st.button("STOP", use_container_width=True)

    run_now = st.button("즉시 수집", use_container_width=True)

    keywords = st.session_state.keywords_list

    if start_clicked:
        if not keywords:
            st.error("키워드를 입력하세요")
        elif not selected_portals:
            st.error("포탈을 선택하세요")
        else:
            conn = get_connection()
            save_search_history(conn, ",".join(keywords), ",".join(selected_portals), interval_minutes)
            conn.close()
            date_str = search_start_date.strftime("%Y.%m.%d")
            st.session_state.scheduler.start_crawling(keywords, selected_portals, interval_minutes, start_date=date_str)
            st.session_state.crawling_active = True
            st.success(f"{', '.join(keywords)} | {interval_label} | {date_str}~")

    if stop_clicked:
        st.session_state.scheduler.stop_crawling()
        st.session_state.crawling_active = False

    if run_now:
        if keywords and selected_portals:
            date_str = search_start_date.strftime("%Y.%m.%d")
            st.session_state.scheduler.run_once(keywords, selected_portals, start_date=date_str)
            st.info("수집을 시작합니다...")
        else:
            st.warning("키워드와 포탈을 선택하세요")

    # ── Status ──
    scheduler = st.session_state.scheduler
    if st.session_state.crawling_active:
        st.markdown("""
        <div class="nd-status nd-status-active">
            <span class="nd-status-dot"></span> 수집 진행중
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="nd-status nd-status-idle">
            <span class="nd-status-dot"></span> 대기중
        </div>
        """, unsafe_allow_html=True)

    if scheduler.last_run:
        st.markdown(f"""
        <div class="nd-stat-row">마지막 수집: {scheduler.last_run.strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div class="nd-stat-row">수집 {scheduler.total_count}건 / 신규 {scheduler.new_count}건</div>
        """, unsafe_allow_html=True)
    if scheduler.last_error:
        st.error(scheduler.last_error)


# ──────────────────────────────────────────────
# Main Content
# ──────────────────────────────────────────────
tab_news, tab_stats, tab_history = st.tabs(["ARTICLES", "ANALYTICS", "HISTORY"])


# ── Articles Tab ──
with tab_news:
    conn = get_connection()
    total = get_news_count(conn)

    st.markdown(f"""
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:20px;">
        <span class="nd-page-title">Articles</span>
        <span class="nd-page-count">{total:,} collected</span>
    </div>
    """, unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 1])
    with filter_col1:
        filter_keyword = st.text_input(
            "키워드 검색",
            key="filter_kw",
            placeholder="키워드로 필터링...",
            label_visibility="collapsed",
        )
    with filter_col2:
        filter_portal = st.selectbox(
            "포탈",
            options=["전체 포탈"] + [v["name"] for v in PORTAL_OPTIONS.values()],
            key="filter_portal",
            label_visibility="collapsed",
        )
    with filter_col3:
        if st.button("새로고침", use_container_width=True):
            st.rerun()

    portal_filter = None
    if filter_portal != "전체 포탈":
        for k, v in PORTAL_OPTIONS.items():
            if v["name"] == filter_portal:
                portal_filter = k
                break

    news_items = get_news_list(
        conn,
        keyword=filter_keyword if filter_keyword else None,
        portal=portal_filter,
        limit=50,
    )

    if not news_items:
        st.markdown("""
        <div class="nd-empty">
            <div class="nd-empty-icon">||</div>
            <div class="nd-empty-text">
                수집된 기사가 없습니다.<br>
                키워드를 추가하고, 포탈을 선택한 뒤 START를 누르세요.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        cards_html = "".join(render_news_card(item) for item in news_items)
        st.markdown(cards_html, unsafe_allow_html=True)

    conn.close()


# ── Analytics Tab ──
with tab_stats:
    conn = get_connection()
    total = get_news_count(conn)

    if total == 0:
        st.markdown("""
        <div class="nd-empty">
            <div class="nd-empty-icon">//</div>
            <div class="nd-empty-text">분석할 데이터가 없습니다.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        stats_keyword = get_stats_by_keyword(conn)
        stats_portal = get_stats_by_portal(conn)
        stats_publisher = get_stats_by_publisher(conn)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("TOTAL ARTICLES", f"{total:,}")
        with col2:
            st.metric("KEYWORDS", f"{len(stats_keyword)}")
        with col3:
            st.metric("PORTALS", f"{len(stats_portal)}")
        with col4:
            st.metric("PUBLISHERS", f"{len(stats_publisher)}")

        st.markdown("")

        # ── Daily collection bar chart ──
        stats_date = get_stats_by_date(conn)
        if stats_date:
            df_date = pd.DataFrame([dict(row) for row in stats_date])
            kw_list = df_date["keyword"].unique().tolist()
            dates = sorted(df_date["date"].unique().tolist())
            series_data = []
            for i, kw in enumerate(kw_list):
                kw_df = df_date[df_date["keyword"] == kw]
                data = []
                for d in dates:
                    row = kw_df[kw_df["date"] == d]
                    data.append(int(row["count"].values[0]) if len(row) > 0 else 0)
                series_data.append({
                    "name": kw,
                    "type": "bar",
                    "data": data,
                    "itemStyle": {"borderRadius": [4, 4, 0, 0], "color": ECHART_COLORS[i % len(ECHART_COLORS)]},
                    "emphasis": {"focus": "series"},
                })
            daily_opt = {
                **ECHART_BASE,
                "title": {"text": "일자별 수집 현황", "textStyle": {"color": "#e8e8f0", "fontSize": 15, "fontWeight": "600"}},
                "grid": {"left": "3%", "right": "3%", "bottom": "10%", "top": "18%", "containLabel": True},
                "xAxis": {"type": "category", "data": dates, "axisLine": {"lineStyle": {"color": "#2a2a3a"}}, "axisLabel": {"color": "#8888a0"}},
                "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#1e1e2e"}}, "axisLabel": {"color": "#8888a0"}},
                "series": series_data,
                "legend": {"data": kw_list, "textStyle": {"color": "#8888a0"}, "bottom": 0},
                "tooltip": {**ECHART_BASE["tooltip"], "trigger": "axis"},
            }
            st_echarts(options=daily_opt, height="380px", theme="dark")

        # ── Keyword & Portal donut charts ──
        col_left, col_right = st.columns(2)

        with col_left:
            if stats_keyword:
                kw_data = [{"name": dict(r)["keyword"], "value": dict(r)["count"]} for r in stats_keyword]
                kw_opt = {
                    **ECHART_BASE,
                    "title": {"text": "키워드 분포", "textStyle": {"color": "#e8e8f0", "fontSize": 15, "fontWeight": "600"}, "left": "center"},
                    "series": [{
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "center": ["50%", "55%"],
                        "data": kw_data,
                        "itemStyle": {"borderRadius": 6, "borderColor": "#0a0a0f", "borderWidth": 2},
                        "label": {"color": "#8888a0", "fontSize": 11},
                        "emphasis": {
                            "label": {"show": True, "fontSize": 14, "fontWeight": "bold"},
                            "itemStyle": {"shadowBlur": 20, "shadowColor": "rgba(99,102,241,0.3)"},
                        },
                        "color": ECHART_COLORS,
                    }],
                    "tooltip": {**ECHART_BASE["tooltip"], "trigger": "item"},
                }
                st_echarts(options=kw_opt, height="350px", theme="dark")

        with col_right:
            if stats_portal:
                portal_colors_map = {"naver": "#03C75A", "daum": "#3D6AFE", "nate": "#EF4444"}
                portal_data = []
                portal_c = []
                for r in stats_portal:
                    d = dict(r)
                    name = PORTAL_OPTIONS.get(d["portal"], {}).get("name", d["portal"])
                    portal_data.append({"name": name, "value": d["count"]})
                    portal_c.append(portal_colors_map.get(d["portal"], "#555"))
                portal_opt = {
                    **ECHART_BASE,
                    "title": {"text": "포탈 분포", "textStyle": {"color": "#e8e8f0", "fontSize": 15, "fontWeight": "600"}, "left": "center"},
                    "series": [{
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "center": ["50%", "55%"],
                        "data": portal_data,
                        "itemStyle": {"borderRadius": 6, "borderColor": "#0a0a0f", "borderWidth": 2},
                        "label": {"color": "#8888a0", "fontSize": 11},
                        "emphasis": {
                            "label": {"show": True, "fontSize": 14, "fontWeight": "bold"},
                            "itemStyle": {"shadowBlur": 20, "shadowColor": "rgba(99,102,241,0.3)"},
                        },
                        "color": portal_c,
                    }],
                    "tooltip": {**ECHART_BASE["tooltip"], "trigger": "item"},
                }
                st_echarts(options=portal_opt, height="350px", theme="dark")

        # ── Publisher horizontal bar ──
        if stats_publisher:
            pub_data = [dict(r) for r in stats_publisher][:15]
            pub_names = [d["publisher"] for d in pub_data][::-1]
            pub_counts = [d["count"] for d in pub_data][::-1]
            pub_opt = {
                **ECHART_BASE,
                "title": {"text": "언론사별 뉴스 건수 (상위 15)", "textStyle": {"color": "#e8e8f0", "fontSize": 15, "fontWeight": "600"}},
                "grid": {"left": "3%", "right": "6%", "bottom": "5%", "top": "14%", "containLabel": True},
                "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#1e1e2e"}}, "axisLabel": {"color": "#8888a0"}},
                "yAxis": {"type": "category", "data": pub_names, "axisLine": {"lineStyle": {"color": "#2a2a3a"}}, "axisLabel": {"color": "#8888a0", "fontSize": 11}},
                "series": [{
                    "type": "bar",
                    "data": pub_counts,
                    "itemStyle": {"borderRadius": [0, 4, 4, 0], "color": {"type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0, "colorStops": [{"offset": 0, "color": "#4f46e5"}, {"offset": 1, "color": "#6366f1"}]}},
                    "emphasis": {"itemStyle": {"color": "#818cf8"}},
                }],
                "tooltip": {**ECHART_BASE["tooltip"], "trigger": "axis"},
            }
            st_echarts(options=pub_opt, height=f"{max(300, len(pub_names) * 32 + 80)}px", theme="dark")

        # ── Hourly area chart ──
        stats_hourly = get_stats_hourly(conn)
        if stats_hourly:
            hourly_data = [dict(r) for r in stats_hourly]
            hours = [d["hour"] for d in hourly_data]
            counts = [d["count"] for d in hourly_data]
            hourly_opt = {
                **ECHART_BASE,
                "title": {"text": "시간대별 수집 현황", "textStyle": {"color": "#e8e8f0", "fontSize": 15, "fontWeight": "600"}},
                "grid": {"left": "3%", "right": "3%", "bottom": "8%", "top": "16%", "containLabel": True},
                "xAxis": {"type": "category", "data": hours, "boundaryGap": False, "axisLine": {"lineStyle": {"color": "#2a2a3a"}}, "axisLabel": {"color": "#8888a0"}},
                "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#1e1e2e"}}, "axisLabel": {"color": "#8888a0"}},
                "series": [{
                    "type": "line",
                    "data": counts,
                    "smooth": True,
                    "symbol": "circle",
                    "symbolSize": 8,
                    "lineStyle": {"color": "#10b981", "width": 2},
                    "itemStyle": {"color": "#10b981"},
                    "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1, "colorStops": [{"offset": 0, "color": "rgba(16,185,129,0.25)"}, {"offset": 1, "color": "rgba(16,185,129,0)"}]}},
                }],
                "tooltip": {**ECHART_BASE["tooltip"]},
            }
            st_echarts(options=hourly_opt, height="320px", theme="dark")

        # Export
        st.markdown("")
        news_all = get_news_list(conn, limit=10000)
        if news_all:
            df_export = pd.DataFrame([dict(row) for row in news_all])
            csv = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="EXPORT CSV",
                data=csv,
                file_name=f"newsdesk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

    conn.close()


# ── History Tab ──
with tab_history:
    st.markdown("""
    <div style="margin-bottom:20px;">
        <span class="nd-page-title">Search History</span>
    </div>
    """, unsafe_allow_html=True)

    conn = get_connection()
    history = get_search_history(conn)

    if not history:
        st.markdown("""
        <div class="nd-empty">
            <div class="nd-empty-icon">[]</div>
            <div class="nd-empty-text">검색 이력이 없습니다.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for item in history:
            keywords_display = item["keywords"].replace(",", " / ")
            portal_names = []
            for p in item["portals"].split(","):
                p = p.strip()
                portal_names.append(PORTAL_OPTIONS.get(p, {}).get("name", p))
            portals_display = " + ".join(portal_names)
            date_display = item["created_at"][:16].replace("T", "  ")

            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"""
                <div class="nd-history-row">
                    <div class="nd-history-keywords">{keywords_display}</div>
                    <div class="nd-history-portals">{portals_display}</div>
                    <div class="nd-history-interval">{item['interval_minutes']}분</div>
                    <div class="nd-history-date">{date_display}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("X", key=f"del_{item['id']}"):
                    delete_search_history(conn, item["id"])
                    st.rerun()

    conn.close()
