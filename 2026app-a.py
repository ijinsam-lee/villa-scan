import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import altair as alt
import datetime

st.set_page_config(page_title="동적 자산배분 대시보드", layout="centered", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# 🔒 접속 비밀번호 잠금 (선택 기능)
#  - 비밀번호는 코드/GitHub에 쓰지 않고 Streamlit Secrets에 둡니다.
#  - 켜기: Secrets에  APP_PASSWORD = "원하는비밀번호"  를 넣으면 잠금이 켜집니다.
#  - 끄기: APP_PASSWORD 줄을 지우거나  PASSWORD_ENABLED = false  를 추가하면 잠금이 꺼집니다.
#  - 켜져 있는데 비밀번호가 비어 있으면(실수 방지) 앱을 열지 않고 안내만 보여줍니다.
#  - 로컬 실행처럼 Secrets가 전혀 없으면 잠금 없이 열립니다.
# ---------------------------------------------------------------------------
def _password_gate():
    import hmac
    import time

    try:
        _pw = st.secrets.get("APP_PASSWORD", None)
        _flag = st.secrets.get("PASSWORD_ENABLED", None)
    except Exception:
        _pw, _flag = None, None
    if _flag is None:
        _enabled = bool(_pw)
    else:
        _enabled = str(_flag).strip().lower() not in ("false", "0", "no", "off", "")
    if not _enabled:
        return
    if not _pw:
        st.error("🔒 비밀번호 잠금이 켜져 있지만 비밀번호(APP_PASSWORD)가 설정되지 않았습니다. "
                 "Streamlit 앱 설정의 Secrets에 APP_PASSWORD를 추가하거나, 잠금을 끄려면 PASSWORD_ENABLED = false 를 넣어주세요.")
        st.stop()
    if st.session_state.get("_pw_ok", False):
        return

    st.markdown("### 🔒 접속 비밀번호")
    with st.form("pw_form"):
        _typed = st.text_input("비밀번호를 입력하세요", type="password")
        _go = st.form_submit_button("접속")
    if _go:
        try:
            _own = st.secrets.get("OWNER_PASSWORD", None)     # 내 비밀번호: 들어가는 건 같고, 방문자 수에서만 빠짐
        except Exception:
            _own = None
        if _own and hmac.compare_digest(str(_typed).encode("utf-8"), str(_own).encode("utf-8")):
            st.session_state["_pw_ok"] = True
            st.session_state["_is_owner"] = True
            (getattr(st, "rerun", None) or st.experimental_rerun)()
        elif hmac.compare_digest(str(_typed).encode("utf-8"), str(_pw).encode("utf-8")):
            st.session_state["_pw_ok"] = True
            (getattr(st, "rerun", None) or st.experimental_rerun)()
        else:
            time.sleep(1)  # 무차별 대입 속도 늦추기
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_password_gate()

# 프리미엄 그레이/슬레이트 톤 스타일 및 탭 선택바 강조 스타일 주입
st.markdown("""
<style>
/* 글로벌 배경화면 및 메인 톤 조정 */
.stApp {
    background-color: #f8fafc;
}

/* 중제목·소제목(##·###·####·#####) 위에 여백: 앞 내용과 다른 단락이라는 게 보이게 (숫자를 키우면 여백이 커짐) */
[data-testid="stMain"] h2 { padding-top: 2.2rem !important; }
[data-testid="stMain"] h3 { padding-top: 1.8rem !important; }
[data-testid="stMain"] h4 { padding-top: 1.8rem !important; }
[data-testid="stMain"] h5 { padding-top: 1.8rem !important; }

/* 굵은 글씨로 시작하는 '작은 제목' 줄 위에 여백 (예: **매매 시점 정리**, **사이클 구간별 할 일** …) — 2026-10-22
   · 여백 크기는 아래 숫자 하나로 조절 (0rem이면 원래대로, 이 블록을 지워도 원래대로)
   ① 글 중간: 굵은 글씨 줄 바로 다음에 목록·표가 오는 경우
   ② 따로 쓴 한 줄: st.markdown("**제목** …")처럼 그 줄만 있는 경우 */
:root { --bold-title-gap: 1.2rem; }
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] p:has(> strong:only-child):has(+ ul, + ol, + table, + div),
[data-testid="stMain"] .stMarkdown [data-testid="stMarkdownContainer"] > p:only-child:has(> strong:only-child) {
    padding-top: var(--bold-title-gap) !important; }
/* 알림 상자(st.info 등)·작은 설명(st.caption)·버튼/입력칸 이름표 안에는 적용하지 않음 */
[data-testid="stAlert"] p, [data-testid="stCaptionContainer"] p, label p, [data-testid="stTooltipContent"] p { padding-top: 0 !important; }

/* ── 상단 탭 메뉴: 2줄 구성 ──
   위줄 = 영문 그룹 라벨(STRATEGY / INSIGHTS), 아래줄 = 탭. 탭 사이 틈 없이 색으로만 구분합니다.
   (그룹 라벨·data-grp 속성은 아래 탭 고정용 JS가 만들어 줍니다. 앞 5개 탭 = 전략, 나머지 = 정보) */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    box-shadow: none !important;
    margin-bottom: 20px !important;
}
.stTabs div.tab-grid {
    display: grid !important;
    grid-template-columns: repeat(10, minmax(max-content, 1fr)) !important; /* 탭 개수(10)와 맞춰야 합니다 */
    grid-auto-flow: row !important;
    gap: 0 !important;
    column-gap: 0 !important;
    row-gap: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
    padding: 0 !important;
    background-color: transparent !important;
    border: 1px solid #94a3b8 !important;
    border-radius: 0 !important;  /* 모서리 라운드 없음(사각) */
    overflow-x: auto !important;
    overflow-y: hidden !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
}
.stTabs .tab-grp-label {
    grid-row: 1;
    display: block;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.22em;
    line-height: 1.2;
    padding: 6px 0;
    user-select: none;
    pointer-events: none;
    border-bottom: 1px solid #94a3b8;
}
.stTabs .tab-grp-label.s { grid-column: 1 / span 5; background-color: #c3d6f6; color: #1e3a8a; }
.stTabs .tab-grp-label.i { grid-column: 6 / span 5; background-color: #bdeee3; color: #0f766e; border-left: 2px solid #64748b; }

/* 개별 탭: 틈·둥근 모서리 없이 그룹 색으로 이어 붙임 */
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border-radius: 0 !important;
    margin: 0 !important;
    padding: 10px 12px !important;
    font-weight: 800 !important;
    font-size: 0.85rem !important;
    color: #334155 !important;
    border: none !important;
    white-space: nowrap !important;
    transition: background-color 0.2s ease-in-out !important;
    text-align: center !important;
}
.stTabs [role="tab"][data-grp="s"] { background-color: #e1ebfb !important; }
.stTabs [role="tab"][data-grp="i"] { background-color: #dcf6ef !important; }
/* 탭 사이 얇은 구분선 / 그룹 경계는 굵은 선 */
.stTabs [role="tab"][data-grp="s"]:not([data-first="1"]) { border-left: 1px solid rgba(30, 58, 138, 0.28) !important; }
.stTabs [role="tab"][data-grp="i"]:not([data-first="1"]) { border-left: 1px solid rgba(15, 118, 110, 0.28) !important; }
.stTabs [role="tab"][data-grp="i"][data-first="1"] { border-left: 2px solid #64748b !important; }
/* [선택된 탭] 그룹의 진한 색 + 흰 글씨 */
.stTabs [role="tab"][data-grp="s"][aria-selected="true"] { background-color: #1e3a8a !important; color: #ffffff !important; }
.stTabs [role="tab"][data-grp="i"][aria-selected="true"] { background-color: #0f766e !important; color: #ffffff !important; }
.stTabs [aria-selected="true"] { color: #ffffff !important; box-shadow: none !important; }

/* 시뮬레이션 설정 상자도 품격 있는 뉴트럴 그레이 톤 플레이트로 교체 */
[data-testid="stVerticalBlockBorderWrapper"]:has(.control-header),
[data-testid="stVerticalBlockBorderWrapper"]:has(.content-box-marker) {
    background-color: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    margin-bottom: 14px !important;
}
.control-panel {
    background-color: #f1f5f9 !important; /* 부드러운 라이트 그레이 */
    border: 1px solid #cbd5e1 !important;
    border-radius: 12px !important;
    padding: 18px !important;
    margin-bottom: 20px !important;
}
.control-header {
    color: #0f172a !important; /* 차분한 블랙 계열 */
    font-weight: 800 !important;
    font-size: 0.98rem !important;
    margin-bottom: 4px !important;
}
.control-subheader {
    color: #475569 !important; /* 짙은 회색 */
    font-size: 0.8rem !important;
    line-height: 1.45 !important;
}

/* 매크로 시황판 카드 스타일 */
.macro-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.macro-title {
    font-size: 0.78rem;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 2px;
}
.macro-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0f172a;
}
.macro-delta-up {
    font-size: 0.75rem;
    color: #dc2626;
    font-weight: 600;
}
.macro-delta-down {
    font-size: 0.75rem;
    color: #2563eb;
    font-weight: 600;
}
.macro-delta-equal {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 600;
}

/* 🖨️ 인쇄 / PDF 저장용 */
.print-only { display: none; }
[data-testid="stElementContainer"]:has(.content-box-marker) { display: none; }
@page { size: A4 portrait; margin: 10mm; }
@media print {
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stSidebar"], footer, [role="tablist"], #tab-sticky-ph,
    div.stTabs [role="tablist"], div.stTabs div.tab-grid, div.stTabs [data-baseweb="tab-list"],
    [data-testid="stBottom"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"],
    [data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none !important; }
    html, body, .stApp, .main, section.main, [data-testid="stMain"], [data-testid="stAppViewContainer"] {
        height: auto !important; min-height: 0 !important; overflow: visible !important; }
    .block-container { padding-bottom: 0 !important; }
    .stApp, .main, [data-testid="stAppViewContainer"] { background: #ffffff !important; }
    [data-testid="stElementContainer"], .element-container { break-inside: avoid; page-break-inside: avoid; }
    .block-container { max-width: 100% !important; padding-top: 0 !important; }
    .print-only { display: block !important; }
    /* 혼합전략 인쇄 범위: MDD 비교 이후는 제외 (설정 패널·월말 기준 포트폴리오 역사는 아래 인쇄 직전 스크립트가 제외) */
    [data-testid="stElementContainer"]:has(h1, h2, h3, h4, h5) { break-after: avoid; page-break-after: avoid; }
    [role="tabpanel"] [data-testid="stVerticalBlock"] > *:has(.print-end) ~ * { display: none !important; }
    /* Ctrl+P로 바로 인쇄해도 '인쇄 시작 지점(print-marker)' 위쪽 내용은 자동으로 빠짐 */
    [data-testid="stVerticalBlock"] > *:has(~ * .print-marker) { display: none !important; }
    .print-hide, [data-testid="stElementContainer"]:has(.print-hide) { display: none !important; }
    .print-pagebreak { break-before: page; page-break-before: always; height: 1px; }
    [data-testid="stElementContainer"]:has(.print-pagebreak) { break-before: page; page-break-before: always; }
}
</style>
""", unsafe_allow_html=True)

st.title("📈 동적 자산배분 대시보드")
st.caption("야후 파이낸스 실시간 데이터 기반 수시 리밸런싱 가이드 (2026년 전략 및 실시간 미국 ETF 랭킹 포함)")

# ============================================================
# 방문자 카운터 (2026-10-16 개편) — '나 말고 다른 사람' 방문 수
#  · 저장: GitHub 저장소의 별도 브랜치(watchlist-data)의 visits.json → 앱이 재시작돼도 누적 유지, 저장해도 앱 재시작 없음
#  · 1방문 = 브라우저가 앱에 새로 접속한 1회 (새로고침·새 탭도 1회)
#  · 내 접속 제외: 접속 비밀번호 화면에서 지인용(APP_PASSWORD) 대신 내 비밀번호(OWNER_PASSWORD)로 들어오면 집계하지 않음
#  · Secrets: GITHUB_TOKEN · GITHUB_REPO (자료실과 같은 값) + APP_PASSWORD (지인용) + OWNER_PASSWORD (나만)
#  · PC에서 직접 실행(Secrets 없음)은 집계하지 않음
# ============================================================
import os
import json

VISIT_BRANCH, VISIT_PATH = "watchlist-data", "visits.json"


def _v_secret(k):
    try:
        return st.secrets.get(k)
    except Exception:
        return None


def _v_req(method, url, tok, **kw):
    import requests
    return requests.request(method, url, headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                            timeout=15, **kw)


def _visit_read(tok, repo):
    """(data, sha) — 파일이 없으면 ({}, None)."""
    import base64
    r = _v_req("GET", f"https://api.github.com/repos/{repo}/contents/{VISIT_PATH}?ref={VISIT_BRANCH}", tok)
    if r.status_code == 404:
        return {}, None
    r.raise_for_status()
    j = r.json()
    return json.loads(base64.b64decode(j["content"]).decode("utf-8")), j["sha"]


def _visit_add(tok, repo, today):
    """방문 1회 기록 (다른 기기가 동시에 저장하면 다시 읽고 최대 3번 재시도). 화면을 기다리게 하지 않도록 백그라운드에서 실행."""
    import base64
    api = f"https://api.github.com/repos/{repo}"
    for _ in range(3):
        try:
            if _v_req("GET", f"{api}/git/ref/heads/{VISIT_BRANCH}", tok).status_code == 404:
                base = _v_req("GET", api, tok).json().get("default_branch", "main")
                sha0 = _v_req("GET", f"{api}/git/ref/heads/{base}", tok).json()["object"]["sha"]
                _v_req("POST", f"{api}/git/refs", tok, json={"ref": f"refs/heads/{VISIT_BRANCH}", "sha": sha0})
            data, sha = _visit_read(tok, repo)
            days = dict(data.get("days", {}))
            days[today] = int(days.get(today, 0)) + 1
            data = {"total": int(data.get("total", 0)) + 1, "days": dict(sorted(days.items())[-120:])}
            body = {"message": "visit", "branch": VISIT_BRANCH,
                    "content": base64.b64encode(json.dumps(data).encode("utf-8")).decode("ascii")}
            if sha:
                body["sha"] = sha
            r = _v_req("PUT", f"{api}/contents/{VISIT_PATH}", tok, json=body)
            if r.status_code in (200, 201):
                return
        except Exception:
            pass


def register_visit():
    """세션당 1번: (누적, 오늘, 상태) — 상태: 'ok' 집계함 · 'me' 내 접속(집계 안 함) · 'off' 집계 안 함(PC 등)."""
    if "_visit_stats" not in st.session_state:
        kst = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
        today = kst.strftime("%Y%m%d")
        tok, repo = _v_secret("GITHUB_TOKEN"), _v_secret("GITHUB_REPO")
        if not (tok and repo):
            st.session_state["_visit_stats"] = (None, None, "off")
            return st.session_state["_visit_stats"]
        is_me = bool(st.session_state.get("_is_owner"))
        try:
            data, _ = _visit_read(tok, repo)
        except Exception:
            data = {}
        total = int(data.get("total", 0))
        day = int(data.get("days", {}).get(today, 0))
        if not is_me:
            import threading
            threading.Thread(target=_visit_add, args=(tok, repo, today), daemon=True).start()
            total, day = total + 1, day + 1
        st.session_state["_visit_stats"] = (total, day, "me" if is_me else "ok")
    return st.session_state["_visit_stats"]


_v_total, _v_today, _v_src = register_visit()
# (방문자 수 표시는 '자산 계산기' 탭 맨 아래에 있습니다)


# ============================================================
# 백테스트 비용·세금 반영 설정 (슬리피지 / 미국주식 양도소득세) — 선택 반영
# ============================================================
def render_cost_quick_switch(key):
    """연도별·월별 수익률 바로 위: 비용·세금 반영 켜기/끄기 (맨 위 설정과 같은 값을 바꿈 → 바로 다시 계산)."""
    _on_now = bool(st.session_state.get("cost_slip_on", True) or st.session_state.get("cost_tax_on", True))
    _k = f"quick_cost_{key}"
    st.session_state[_k] = "반영 (슬리피지·양도세)" if _on_now else "미반영 (비용·세금 없이)"

    def _apply():
        _v = st.session_state.get(_k, "").startswith("반영")
        st.session_state["cost_slip_on"] = _v
        st.session_state["cost_tax_on"] = _v
    st.radio("💸 수수료·세금", ["반영 (슬리피지·양도세)", "미반영 (비용·세금 없이)"], horizontal=True, key=_k, on_change=_apply,
             help="맨 위 '⚙️ 백테스트 비용·세금 반영 설정'의 ② 슬리피지·③ 양도세를 한 번에 켜고 끕니다. 세율·투자금 같은 세부 값은 맨 위에서 바꿉니다.")


def money_man_input(label, key, default_man, min_man=0, max_man=10_000_000, help=None, disabled=False):
    """만원 단위 정수 입력칸. 천단위 콤마를 넣어 표시합니다 (예: 5억원 → 50,000).
    입력 중 콤마는 브라우저 JS가 즉시 넣고, 입력을 마치면 파이썬 콜백이 범위를 맞춰 다시 정리합니다."""
    import re

    def _norm():
        d = re.sub(r"[^0-9]", "", str(st.session_state.get(key, "")))
        v = max(min_man, min(max_man, int(d) if d else 0))
        st.session_state[key] = f"{v:,}"

    if key not in st.session_state:
        st.session_state[key] = f"{default_man:,}"
    st.text_input(label, key=key, on_change=_norm, help=help, disabled=disabled)
    d = re.sub(r"[^0-9]", "", str(st.session_state.get(key, "")))
    return max(min_man, min(max_man, int(d) if d else 0))


def fmt_krw(x):
    """원화를 읽기 쉬운 단위(억원/만원/원)로 표시."""
    x = float(x)
    a = abs(x)
    if a >= 1e8:
        return f"{x / 1e8:,.2f}억원"
    if a >= 1e4:
        return f"{x / 1e4:,.0f}만원"
    return f"{x:,.0f}원"


# 설정 박스를 은은한 노란색으로 강조 (마커 + JS 이중 지정)
st.markdown("""<style>
[data-testid="stExpander"].cost-exp details, [data-testid="stExpander"]:has(.cost-exp-marker) details{
  border:1.5px solid #f2c94c !important;background:#fffdf4 !important;border-radius:12px}
[data-testid="stExpander"].cost-exp summary, [data-testid="stExpander"]:has(.cost-exp-marker) summary{
  background:#fff6d6 !important;font-weight:700;border-radius:10px}
</style>""", unsafe_allow_html=True)

# 비용·세금 설정 기본값 (설정 패널은 '2026 혼합전략' 탭 맨 위에 있으며, 렌더링되면서 아래 값이 갱신됩니다)
COST_CAPITAL = 10_000_000.0
COST_SLIP_ON = True
COST_SLIP_PCT = 0.2
COST_TAX_ON = True
COST_TAX_PCT = 22.0
COST_DEDUCT = 2_500_000


def render_cost_settings_panel():
    global COST_CAPITAL, COST_SLIP_ON, COST_SLIP_PCT, COST_TAX_ON, COST_TAX_PCT, COST_DEDUCT
    with st.expander("⚙️ 백테스트 비용·세금 반영 설정", expanded=False):
        st.markdown('<span class="cost-exp-marker"></span>', unsafe_allow_html=True)
        COST_CAPITAL = 10000 * money_man_input(
            "① 초기 투자금 (만원)", "cost_capital_man", 1000, min_man=10, max_man=10_000_000,
            help="만원 단위로 입력합니다 (예: 5억원 = 50,000). 백테스트 시작 시점에 이 금액을 투자했다고 가정하고, 슬리피지와 양도세를 원화로 환산합니다. 자산 계산기의 초기 투자금에도 함께 반영됩니다.")
        st.caption(f"= ₩{COST_CAPITAL:,.0f} ({fmt_krw(COST_CAPITAL)}) · 백테스트 시작일에 전액 투자한 것으로 가정합니다.")
        _cs1, _cs2 = st.columns(2)
        COST_SLIP_ON = _cs1.checkbox("② 슬리피지 반영", value=True, key="cost_slip_on",
                                     help="종목을 사고팔 때마다 체결가 차이로 손해 보는 비용을 월별 수익에서 차감합니다.")
        COST_SLIP_PCT = _cs1.number_input("슬리피지 (매수·매도 각 1회당 %)", min_value=0.0, max_value=5.0, value=0.2, step=0.1,
                                          key="cost_slip_pct", disabled=not COST_SLIP_ON)
        if COST_SLIP_ON:
            _cs1.caption(f"전량 교체 1회 ≈ ₩{COST_CAPITAL * COST_SLIP_PCT / 100 * 2:,.0f} (매도+매수)")
        COST_TAX_ON = _cs2.checkbox("③ 미국주식 양도소득세 반영", value=True, key="cost_tax_on",
                                    help="매년 12월 말에 그 해의 순이익에서 기본공제를 뺀 금액에 세율을 곱해 세액을 확정하고, 실제 차감은 이듬해 6월 말에 합니다.")
        COST_TAX_PCT = _cs2.number_input("양도소득세율 (%)", min_value=0.0, max_value=50.0, value=22.0, step=0.5,
                                         key="cost_tax_pct", disabled=not COST_TAX_ON)
        COST_DEDUCT = _cs2.number_input("연 기본공제 (원)", min_value=0, max_value=100000000, value=2500000, step=500000,
                                        format="%d", key="cost_deduct", disabled=not COST_TAX_ON,
                                        help="해외주식 양도차익에서 매년 빼주는 금액(기본 250만원). 0으로 두면 공제 없이 계산합니다.")
        st.caption(
            "• 슬리피지: 리밸런싱으로 바뀐 비중만큼 매수·매도 각각에 부과합니다. 한 종목을 전량 교체하면 매도·매수 각각 입력값만큼(기본 0.2% + 0.2% = 약 0.4%) 차감됩니다. "
            "현금 전환 후 재진입도 거래로 계산합니다.\n"
            "• 양도세: 해마다 12월 말 순이익에서 기본공제(기본 250만원)를 뺀 금액으로 세액을 확정하고, 이듬해 6월 말 자산에서 차감합니다(손실 해는 0, 이월공제 없음). "
            "환전 비용은 반영하지 않으며, 마지막 12월 이후 아직 납부 전인 세금은 최종 NAV에 반영되지 않습니다.\n"
            "• 설정은 혼합전략·전략 A·B·C 백테스트 결과(CAGR·MDD·NAV·월별 표·차트)에 모두 적용됩니다."
        )


def _cost_cfg():
    """현재 상단 설정을 (캐시 키로 쓸 수 있는) 튜플로 반환: (슬리피지 on, %, 세금 on, %, 초기 투자금, 연 공제)."""
    return (bool(COST_SLIP_ON), float(COST_SLIP_PCT), bool(COST_TAX_ON), float(COST_TAX_PCT), float(COST_CAPITAL), float(COST_DEDUCT))


def apply_trading_costs(bt, cfg=None):
    """백테스트 결과(월별 DataFrame)에 슬리피지·양도세를 반영한 새 결과를 돌려줍니다.
    - 양도세 변경: 12월 말에 한 해의 수익과 납부할 세금을 '확정'하고, 실제 차감은 '이듬해 6월 말'에 집행합니다."""
    slip_on, slip_pct, tax_on, tax_pct, cap, deduct = cfg if cfg is not None else _cost_cfg()
    if bt is None or len(bt) == 0 or not (slip_on or tax_on):
        return bt
    slip = slip_pct / 100.0 if slip_on else 0.0
    tax = tax_pct / 100.0 if tax_on else 0.0
    krw_per_pt = cap / 100.0
    df = bt.reset_index(drop=True).copy()
    nav, peak, year_start_nav = 100.0, 100.0, 100.0
    prev_alloc = {}
    navs, rets, dds, slip_k, tax_k, gain_k, taxable_k = [], [], [], [], [], [], []
    
    pending_tax_pts = 0.0  # 이듬해 6월에 납부 대기 중인 세금 (포인트)
    last_year_gain_krw = np.nan
    last_year_taxable_krw = np.nan

    for _, row in df.iterrows():
        gross = float(row["monthly_return"]) / 100.0
        alloc = dict(row["alloc"]) if isinstance(row["alloc"], dict) else {}
        stopped = "월중손절" in str(row["mode"])
        keys = (set(alloc) | set(prev_alloc)) - {"CASH (현금)"}
        traded = sum(abs(alloc.get(k, 0.0) - prev_alloc.get(k, 0.0)) for k in keys) / 100.0
        buy_cost = slip * traded
        stop_cost = slip * sum(w for k, w in alloc.items() if k != "CASH (현금)") / 100.0 if stopped else 0.0
        
        nav_before = nav
        nav_after_buy = nav_before * (1 - buy_cost)
        nav_mid = nav_after_buy * (1 + gross)
        nav = nav_mid * (1 - stop_cost)
        slip_pts = nav_before * buy_cost + nav_mid * stop_cost
        
        row_date = pd.Timestamp(row["date"])
        month = row_date.month
        
        tax_deducted_pts = 0.0
        # ① 이듬해 6월 말: 전년도 세금 인출 집행
        if tax > 0 and month == 6 and pending_tax_pts > 0:
            tax_deducted_pts = min(nav * 0.9, pending_tax_pts)  # 파산 방지 리미트
            nav -= tax_deducted_pts
            year_start_nav -= tax_deducted_pts  # 납부한 세금이 올해 손실로 잡혀 내년 과세표준을 깎지 않도록 기준 NAV도 같이 내림
            pending_tax_pts = 0.0

        # ② 12월 말: 해당 연도 순이익 및 다음 해에 낼 양도세 확정 (당월 인출 X)
        cur_gain_krw, cur_taxable_krw = np.nan, np.nan
        if tax > 0 and month == 12:
            cur_gain_krw = (nav - year_start_nav) * krw_per_pt
            cur_taxable_krw = max(0.0, cur_gain_krw - float(deduct))
            pending_tax_pts = cur_taxable_krw * tax / krw_per_pt
            year_start_nav = nav
            last_year_gain_krw = cur_gain_krw
            last_year_taxable_krw = cur_taxable_krw

        peak = max(peak, nav)
        navs.append(nav)
        rets.append((nav / nav_before - 1) * 100.0)
        dds.append((nav / peak - 1) * 100.0)
        slip_k.append(slip_pts * krw_per_pt)
        tax_k.append(tax_deducted_pts * krw_per_pt)
        gain_k.append(cur_gain_krw)
        taxable_k.append(cur_taxable_krw)
        prev_alloc = {} if stopped else alloc
        
    df["nav"], df["monthly_return"], df["drawdown"] = navs, rets, dds
    df["slip_krw"], df["tax_krw"], df["gain_krw"], df["taxable_krw"] = slip_k, tax_k, gain_k, taxable_k
    return df


def benchmark_after_costs(ret_series, cfg=None):
    """벤치마크(QQQ) 월수익률(소수)에 전략과 같은 비용·세금 설정을 반영한 '세후 평가' 월수익률을 돌려줍니다.
    - 슬리피지: 처음 매수할 때 1회만 차감 (전략의 초기 편입 비용과 같은 방식, 보유 중 추가 매매 없음)
    - 양도세: 매도 시 1회 과세. 그 달에 팔았다고 가정한 세후 평가액(수익 - 연 공제 후 세율 적용)으로 월수익률을 계산해,
      마지막 달에 세금 충격이 몰리지 않고 기간 끝에는 '세후 최종 가치'와 일치합니다.
    - 비용·세금 설정이 모두 꺼져 있으면 원본 그대로 반환합니다."""
    slip_on, slip_pct, tax_on, tax_pct, cap, deduct = cfg if cfg is not None else _cost_cfg()
    if ret_series is None or len(ret_series) == 0 or not (slip_on or tax_on):
        return ret_series
    r = pd.Series(ret_series).astype(float).fillna(0.0).values
    krw_per_pt = max(float(cap), 1.0) / 100.0
    entry = 1.0 - (slip_pct / 100.0 if slip_on else 0.0)
    gross = 100.0 * entry
    after_tax = []
    for x in r:
        gross *= (1.0 + x)
        gain_krw = (gross - 100.0) * krw_per_pt
        tax_krw = max(0.0, gain_krw - float(deduct)) * (tax_pct / 100.0) if tax_on else 0.0
        after_tax.append(gross - tax_krw / krw_per_pt)
    v = np.array(after_tax)
    net = v / np.concatenate([[100.0], v[:-1]]) - 1.0
    return pd.Series(net, index=ret_series.index)


def cost_status_caption(bt):
    """현재 비용·세금 반영 상태를 원화 카드와 연도별 표로 표시."""
    if not (COST_SLIP_ON or COST_TAX_ON) or "slip_krw" not in bt:
        st.caption("💸 거래비용·세금 미반영 ('2026 혼합전략' 탭 상단 '⚙️ 백테스트 비용·세금 반영 설정'에서 선택)")
        return
    slip_sum = float(bt["slip_krw"].sum())
    tax_sum = float(bt["tax_krw"].sum())
    final_krw = float(bt["nav"].iloc[-1]) / 100.0 * COST_CAPITAL
    cards = []
    if COST_SLIP_ON:
        cards.append((f"슬리피지 누적 ({COST_SLIP_PCT:g}%/회)", fmt_krw(slip_sum), f"₩{slip_sum:,.0f}", "neg"))
    if COST_TAX_ON:
        cards.append((f"양도세 누적 ({COST_TAX_PCT:g}%)", fmt_krw(tax_sum), f"₩{tax_sum:,.0f} · 연 공제 {fmt_krw(COST_DEDUCT)}", "neg"))
    cards.append(("세후 최종 자산", fmt_krw(final_krw), f"₩{final_krw:,.0f} · 초기 투자금 {fmt_krw(COST_CAPITAL)}", "neutral"))
    st.markdown(
        f"<div style='border:2px solid #16a34a;background:#f0fdf4;border-radius:10px;padding:8px 14px;margin:4px 0 8px'>"
        f"<span style='font-size:1.02rem;font-weight:800;color:#15803d'>✅ 비용·세금 반영 중 · 초기 투자금 &#8361;{COST_CAPITAL:,.0f} 기준</span>"
        f"<div style='font-size:0.82rem;color:#475569;margin-top:2px'>벤치마크 QQQ도 같은 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)으로 계산</div></div>",
        unsafe_allow_html=True)
    hl_cards(cards)
    d = bt.copy()
    d["연도"] = pd.to_datetime(d["date"]).dt.year
    rows = []
    for yr, g in d.groupby("연도"):
        gain = g["gain_krw"].max()
        taxable = g["taxable_krw"].max()
        rows.append({
            "연도": int(yr),
            "연말 자산(세후)": f"₩{g['nav'].iloc[-1] / 100.0 * COST_CAPITAL:,.0f}",
            "순이익(세전)": f"₩{gain:,.0f}" if pd.notna(gain) else "연말 전",
            "과세표준(공제후)": f"₩{taxable:,.0f}" if pd.notna(taxable) else "-",
            "양도세(전년분 6월 납부)": f"₩{g['tax_krw'].sum():,.0f}",
            "슬리피지": f"₩{g['slip_krw'].sum():,.0f}",
        })
    with st.expander("💴 연도별 비용·세금 내역 (원)", expanded=False):
        st.dataframe(pd.DataFrame(rows).iloc[::-1], use_container_width=True, hide_index=True)

# --- 1. 자산군 정의 ---
# 전략A 자산군 (최신 리스트 12개 자산 - 문구 및 데이터 불일치 수정완료)
OFFENSIVE_A = ["QQQ", "FEZ", "GLD", "IBB", "SMH", "EEM", "XLK", "LIT", "XLE", "UBT", "XLV", "QTUM"]
DEFENSIVE_A = ["BIL", "IEF", "AGG", "HYG", "TBF"]

# 전략B 자산군 (레버리지/인버스)
OFFENSIVE_B = ["TYD", "UPRO", "VNQ"]
DEFENSIVE_B = ["DOG", "RWM", "TBF"]

# 전략C (섹터로테이션) 자산군
OFFENSIVE_C = ["FDN", "LIT", "SMH", "XLE", "IGV", "QQQM", "XLU"] # 최신섹터반영
DEFENSIVE_C = ["GLD", "PDBC", "OILK", "SHY", "TLT"] # 3대 원자재 및 채권 방어자산

# 중복 없는 전체 티커 추출 (미국 ETF 랭킹 비교용 인기 자산군 SCHD, JEPI, TQQQ, SOXL, DIA, IWM, XLF 추가)
ALL_TICKERS = list(set(["TIP", "SPY"] + OFFENSIVE_A + DEFENSIVE_A + OFFENSIVE_B + DEFENSIVE_B + OFFENSIVE_C + DEFENSIVE_C + ["SCHD", "QQQM", "IGV", "XLU", "JEPI", "TQQQ", "SOXL", "DIA", "IWM", "XLF"]))

# ============================================================
# 혼합전략 백테스트 요약 지표 (안전장치 전/후 비교표용)
# ============================================================
def summarize_bt_mix(bt):
    """혼합전략 요약: 수익/위험 지표 + 집중도(단일 자산 최대 비중), 안전장치 발동 횟수."""
    if bt is None or len(bt) == 0:
        return None
    r = bt["monthly_return"].values / 100.0
    n = len(r)
    nav = bt["nav"].values
    sd = r.std(ddof=1) if n > 1 else np.nan
    allocs = list(bt["alloc"])
    max_w = [max([w for t, w in a.items() if t != "CASH (현금)"] or [0.0]) for a in allocs]
    cash_w = [a.get("CASH (현금)", 0.0) for a in allocs]
    turn = []
    for prev, cur in zip(allocs[:-1], allocs[1:]):
        keys = set(prev) | set(cur)
        turn.append(0.5 * sum(abs(cur.get(k, 0.0) - prev.get(k, 0.0)) for k in keys))
    modes = bt["mode"].astype(str)
    return {
        "CAGR (%)": ((nav[-1] / 100.0) ** (12.0 / n) - 1) * 100,
        "MDD (%)": float(bt["drawdown"].min()),
        "연변동성 (%)": sd * np.sqrt(12) * 100 if pd.notna(sd) else np.nan,
        "샤프": (r.mean() * 12) / (sd * np.sqrt(12)) if pd.notna(sd) and sd > 0 else np.nan,
        "최악 월 (%)": float(r.min() * 100),
        "단일자산 최대비중 (%)": float(np.max(max_w)),
        "평균 현금 (%)": float(np.mean(cash_w)),
        "연 턴오버 (%)": float(np.mean(turn) * 12) if turn else 0.0,
        "Cap 발동 (월)": int(modes.str.contains("Cap적용").sum()),
        "손절 발동 (월)": int(modes.str.contains("월중손절").sum()),
        "개월 수": n,
    }

# ============================================================
# 전략 A 실시간 백테스트 엔진 (TIP 11M 이동평균 카나리아 + 공격 Top4/방어 Top1 로테이션)
# ============================================================
PRICE_PARQUET = "historical_daily_prices_2000_2026.parquet"


def _download_close(tickers, start):
    """야후에서 수정종가를 내려받아 (날짜 x 티커) DataFrame으로 반환."""
    tickers = list(tickers)
    df = yf.download(tickers, start=start, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.levels[0]:
            close = df["Close"]
        else:
            close = df.iloc[:, :len(tickers)]
    else:
        close = df[["Close"]] if "Close" in df.columns else df
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close.dropna(how="all")


def _splice_recent_prices(old, new):
    """파일(old) 마지막 날짜 이후의 새 가격을 이어붙임. 수정종가는 배당 때마다 과거가 재계산되므로
    겹치는 마지막 날짜에서 비율로 맞춰(scale) 이어붙인다."""
    if new is None or new.empty:
        return old
    adds = {}
    for t in old.columns:
        if t not in new.columns:
            continue
        o, n = old[t].dropna(), new[t].dropna()
        if o.empty or n.empty:
            continue
        common = o.index.intersection(n.index)
        if len(common) == 0:
            continue
        d = common[-1]
        if not (o.loc[d] > 0 and n.loc[d] > 0):
            continue
        adds[t] = n[n.index > o.index[-1]] * (o.loc[d] / n.loc[d])
    if not adds:
        return old
    return old.combine_first(pd.DataFrame(adds)).sort_index()


@st.cache_data(ttl=3600)
def get_daily_price_history_a(tickers, start="2000-01-01"):
    """백필 파일(2000~)을 기본으로 쓰되, 파일 이후의 최신 구간은 야후에서 자동으로 이어붙입니다.
    (파일에 없는 티커는 야후에서 직접 받습니다. 파일이 없으면 기존처럼 전부 야후에서 받습니다.)"""
    tickers = list(tickers)
    base = pd.DataFrame()
    if os.path.exists(PRICE_PARQUET):
        try:
            base = pd.read_parquet(PRICE_PARQUET)
        except Exception:
            base = pd.DataFrame()
    have = [t for t in tickers if t in base.columns]
    missing = [t for t in tickers if t not in base.columns]
    parts = []
    if have:
        old = base[have].dropna(how="all")
        try:
            recent_start = (old.index[-1] - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
            old = _splice_recent_prices(old, _download_close(have, recent_start))
        except Exception:
            pass  # 인터넷 오류 시 파일 데이터만 사용
        parts.append(old)
    if missing:
        try:
            parts.append(_download_close(missing, start))
        except Exception:
            pass
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, axis=1).sort_index()
    out = out[[t for t in tickers if t in out.columns]]
    return out.loc[start:].dropna(how="all")

def to_monthly_last_a(df):
    return df.resample("ME").last().dropna(how="all")

def calc_momentum_a(px_series, i, months_list):
    curr = px_series.iloc[i]
    rets = {}
    for m in months_list:
        if i - m >= 0:
            past = px_series.iloc[i - m]
            rets[m] = (curr / past - 1) * 100 if pd.notna(past) and past > 0 else np.nan
        else:
            rets[m] = np.nan
    return rets

@st.cache_data(ttl=3600)
def run_backtest_strategy_a_full(monthly_px):
    records = []
    nav = 100.0
    peak = 100.0
    monthly_returns = monthly_px.pct_change().shift(-1)

    for i in range(11, len(monthly_px) - 1):
        tip_window = monthly_px["TIP"].iloc[i - 10:i + 1]  # 최근 11개월 (당월 포함)
        tip_ma11 = tip_window.mean()
        tip_curr = monthly_px["TIP"].iloc[i]
        is_attack = tip_curr > tip_ma11

        alloc = {}
        if is_attack:
            scores = []
            for t in OFFENSIVE_A:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 6, 12])
                    if not np.isnan(rets[1]) and not np.isnan(rets[12]):
                        score = (rets[1] + rets[3] + rets[6] + rets[12]) / 4
                        scores.append((t, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            if scores:
                for t, _ in scores[:4]:
                    alloc[t] = 25.0
            else:
                alloc["CASH (현금)"] = 100.0
        else:
            scores = []
            for t in DEFENSIVE_A:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 6, 9, 12])
                    if not np.isnan(rets[1]) and not np.isnan(rets[12]):
                        score = (rets[1] + rets[3] + rets[6] + rets[9] + rets[12]) / 5
                        scores.append((t, score))
            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                top1, top1_score = scores[0]
                if top1_score > 0:
                    alloc[top1] = 100.0
                else:
                    alloc["CASH (현금)"] = 100.0
            else:
                alloc["CASH (현금)"] = 100.0

        port_ret = 0.0
        for t, w in alloc.items():
            if t != "CASH (현금)":
                nxt_ret = monthly_returns[t].iloc[i]
                if pd.notna(nxt_ret):
                    port_ret += (w / 100.0) * nxt_ret

        nav *= (1 + port_ret)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100

        records.append({
            "date": monthly_px.index[i + 1],  # 수익이 실현되는 월말 시점 기준으로 기록
            "mode": "공격 (Offensive)" if is_attack else "방어 (Defensive)",
            "nav": nav,
            "monthly_return": port_ret * 100,
            "drawdown": dd,
            "weights_str": ", ".join([f"{t} {w}%" for t, w in alloc.items() if w > 0]),
            "alloc": dict(alloc),
        })

    return pd.DataFrame(records)

# ============================================================
# 전략 B 실시간 백테스트 엔진 (TIP 1-3-6-9-12M 모멘텀 카나리아 + 레버리지 몰빵)
# ============================================================
@st.cache_data(ttl=3600)
def run_backtest_strategy_b_full(monthly_px):
    records = []
    nav = 100.0
    peak = 100.0
    monthly_returns = monthly_px.pct_change().shift(-1)

    for i in range(11, len(monthly_px) - 1):
        if "TIP" not in monthly_px.columns:
            break
        tip_rets = calc_momentum_a(monthly_px["TIP"], i, [1, 3, 6, 9, 12])
        if any(np.isnan(v) for v in tip_rets.values()):
            continue
        tip_score_b = sum(tip_rets.values()) / 5
        is_attack = tip_score_b > 0

        alloc = {}
        if is_attack:
            scores = []
            for t in OFFENSIVE_B:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 6, 12])
                    if not np.isnan(rets[12]):
                        score = (12 * rets[1] + 4 * rets[3] + 2 * rets[6] + rets[12]) / 19
                        scores.append((t, score))
            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                alloc[scores[0][0]] = 100.0
            else:
                alloc["CASH (현금)"] = 100.0
        else:
            candidates = []
            for t in DEFENSIVE_B:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 5, 6, 9, 12])
                    if not np.isnan(rets[12]) and not np.isnan(rets[5]):
                        simple_score = (rets[1] + rets[3] + rets[6] + rets[9] + rets[12]) / 5
                        candidates.append((t, rets[5], simple_score))
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                top_t, _, top_simple_score = candidates[0]
                if top_simple_score > 0:
                    alloc[top_t] = 100.0
                else:
                    alloc["CASH (현금)"] = 100.0
            else:
                alloc["CASH (현금)"] = 100.0

        port_ret = 0.0
        for t, w in alloc.items():
            if t != "CASH (현금)":
                nxt_ret = monthly_returns[t].iloc[i]
                if pd.notna(nxt_ret):
                    port_ret += (w / 100.0) * nxt_ret

        nav *= (1 + port_ret)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100

        records.append({
            "date": monthly_px.index[i + 1],
            "mode": "공격 (Offensive)" if is_attack else "방어 (Defensive)",
            "nav": nav,
            "monthly_return": port_ret * 100,
            "drawdown": dd,
            "weights_str": ", ".join([f"{t} {w}%" for t, w in alloc.items() if w > 0]),
            "alloc": dict(alloc),
        })

    return pd.DataFrame(records)

# ============================================================
# 전략 C 실시간 백테스트 엔진 (S&P 500 실시간 배당수익률 카나리아 + 섹터 로테이션)
# ============================================================
@st.cache_data(ttl=3600)
def get_spy_dividend_history():
    div_file = "spy_dividends_2000_2026.csv"
    if os.path.exists(div_file):
        s = pd.read_csv(div_file, index_col=0, parse_dates=True).squeeze("columns")
        return s
    try:
        divs = yf.Ticker("SPY").dividends
        if divs.index.tz is not None:
            divs.index = divs.index.tz_localize(None)
        return divs
    except Exception:
        return pd.Series(dtype=float)

SPY_NOMINAL_CSV = "spy_nominal_close.csv"


@st.cache_data(ttl=3600)
def get_spy_nominal_close():
    """SPY 실제 종가(배당 미조정). 전략 C 배당수익률 계산용.
    수정주가(배당 재투자 반영)로 나누면 과거로 갈수록 가격이 낮아져 배당수익률이 부풀려지므로
    (예: 2000-03 수정주가 기준 1.59% vs 실제 0.99%) 실제 종가로 나눕니다.
    파일(spy_nominal_close.csv)을 기본으로 쓰고, 파일 이후 최신분만 야후에서 이어붙입니다."""
    base = pd.Series(dtype=float)
    if os.path.exists(SPY_NOMINAL_CSV):
        try:
            base = pd.read_csv(SPY_NOMINAL_CSV, index_col=0, parse_dates=True).squeeze("columns").dropna()
        except Exception:
            base = pd.Series(dtype=float)
    start = (base.index[-1] - pd.Timedelta(days=10)).strftime("%Y-%m-%d") if not base.empty else "1999-01-01"
    try:
        df = yf.download("SPY", start=start, interval="1d", auto_adjust=False, progress=False)
        s_new = df["Close"]
        if isinstance(s_new, pd.DataFrame):
            s_new = s_new.iloc[:, 0]
        s_new = s_new.dropna()
        if s_new.index.tz is not None:
            s_new.index = s_new.index.tz_localize(None)
        base = s_new.combine_first(base) if not base.empty else s_new
    except Exception:
        pass  # 인터넷 오류 시 파일 데이터만 사용
    return base.sort_index()


def _spy_nominal_monthly(index):
    """월말 인덱스에 맞춘 SPY 실제 종가 (없으면 None → 기존 수정주가 사용)."""
    nom = get_spy_nominal_close()
    if nom is None or nom.empty:
        return None
    return nom.resample("ME").last().reindex(index)


@st.cache_data(ttl=3600)
def run_backtest_strategy_c_full(monthly_px, spy_divs):
    records = []
    nav = 100.0
    peak = 100.0
    monthly_returns = monthly_px.pct_change().shift(-1)
    spy_nominal_m = _spy_nominal_monthly(monthly_px.index)  # 배당수익률은 실제 종가 기준 (편향 수정)

    for i in range(11, len(monthly_px) - 1):
        if "SPY" not in monthly_px.columns:
            break
        date = monthly_px.index[i]
        window_start = date - pd.Timedelta(days=365)
        div_sum = spy_divs[(spy_divs.index > window_start) & (spy_divs.index <= date)].sum()
        spy_price = monthly_px["SPY"].iloc[i]
        if spy_nominal_m is not None and pd.notna(spy_nominal_m.iloc[i]) and spy_nominal_m.iloc[i] > 0:
            spy_price = spy_nominal_m.iloc[i]
        if pd.isna(spy_price) or spy_price <= 0 or div_sum <= 0:
            continue
        dy = (div_sum / spy_price) * 100
        is_attack = dy > 1.33

        alloc = {}
        if is_attack:
            scores = []
            for t in OFFENSIVE_C:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 6, 12])
                    if not np.isnan(rets[12]):
                        score = (rets[1] + rets[3] + rets[6] + rets[12]) / 4
                        scores.append((t, score))
            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                alloc[scores[0][0]] = 100.0
            else:
                alloc["CASH (현금)"] = 100.0
        else:
            scores = []
            for t in DEFENSIVE_C:
                if t in monthly_px.columns:
                    rets = calc_momentum_a(monthly_px[t], i, [1, 3, 6, 9, 12])
                    if not np.isnan(rets[12]):
                        score = (rets[1] + rets[3] + rets[6] + rets[9] + rets[12]) / 5
                        scores.append((t, score))
            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                top_t, top_score = scores[0]
                if top_score > 0:
                    alloc[top_t] = 100.0
                else:
                    alloc["CASH (현금)"] = 100.0
            else:
                alloc["CASH (현금)"] = 100.0

        port_ret = 0.0
        for t, w in alloc.items():
            if t != "CASH (현금)":
                nxt_ret = monthly_returns[t].iloc[i]
                if pd.notna(nxt_ret):
                    port_ret += (w / 100.0) * nxt_ret

        nav *= (1 + port_ret)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100

        records.append({
            "date": monthly_px.index[i + 1],
            "mode": "공격 (Offensive)" if is_attack else "방어 (Defensive)",
            "nav": nav,
            "monthly_return": port_ret * 100,
            "drawdown": dd,
            "weights_str": ", ".join([f"{t} {w}%" for t, w in alloc.items() if w > 0]),
            "alloc": dict(alloc),
        })

    return pd.DataFrame(records)

# ============================================================
# 2026 혼합전략 백테스트 엔진 (전략A + 전략B + 전략C 각 33.33% 동일비중 혼합)
# ============================================================
@st.cache_data(ttl=3600)
def run_backtest_strategy_mix_full(monthly_px, spy_divs):
    bt_a = run_backtest_strategy_a_full(monthly_px)
    bt_b = run_backtest_strategy_b_full(monthly_px)
    bt_c = run_backtest_strategy_c_full(monthly_px, spy_divs)

    if bt_a.empty or bt_b.empty or bt_c.empty:
        return pd.DataFrame()

    bt_a = bt_a.set_index("date")
    bt_b = bt_b.set_index("date")
    bt_c = bt_c.set_index("date")

    common_dates = sorted(set(bt_a.index) & set(bt_b.index) & set(bt_c.index))
    if not common_dates:
        return pd.DataFrame()

    records = []
    nav = 100.0
    peak = 100.0
    for d in common_dates:
        ret_a = bt_a.loc[d, "monthly_return"] / 100.0
        ret_b = bt_b.loc[d, "monthly_return"] / 100.0
        ret_c = bt_c.loc[d, "monthly_return"] / 100.0
        port_ret = (ret_a + ret_b + ret_c) / 3.0

        nav *= (1 + port_ret)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100

        mode_a_short = bt_a.loc[d, "mode"].split(" ")[0]
        mode_b_short = bt_b.loc[d, "mode"].split(" ")[0]
        mode_c_short = bt_c.loc[d, "mode"].split(" ")[0]
        mode_str = f"A:{mode_a_short} / B:{mode_b_short} / C:{mode_c_short}"
        def _fmt_third(alloc_dict):
            # 각 전략은 전체 자산의 1/3 → 전략 내 100% = 전체 33.3%
            return ", ".join([f"{t} {w / 3.0:.1f}%" for t, w in alloc_dict.items() if w > 0.01])
        weights_str = (
            f"A[{_fmt_third(bt_a.loc[d, 'alloc'])}] + "
            f"B[{_fmt_third(bt_b.loc[d, 'alloc'])}] + "
            f"C[{_fmt_third(bt_c.loc[d, 'alloc'])}]"
        )

        # 세 전략(각 33.33%)의 종목별 비중을 하나로 합산 (턴오버 계산용)
        combined_alloc = {}
        for src_bt in (bt_a, bt_b, bt_c):
            for tkr, w in src_bt.loc[d, "alloc"].items():
                combined_alloc[tkr] = combined_alloc.get(tkr, 0.0) + (w / 100.0) * (1.0 / 3.0) * 100.0

        records.append({
            "date": d,
            "mode": mode_str,
            "nav": nav,
            "monthly_return": port_ret * 100,
            "drawdown": dd,
            "weights_str": weights_str,
            "alloc": combined_alloc,
        })

    return pd.DataFrame(records)

# ============================================================
# 2026 혼합전략 [개선판] 백테스트 엔진
#   - 2019년 5월 무역전쟁 급락(-13.0% MDD) 원인 분석 결과, 특정 자산(SMH 41.66%, UPRO 33.33% 등)에
#     3개 전략의 비중이 중복 쏠리는 현상이 최대 낙폭의 핵심 원인으로 확인되었습니다.
#   - 1단계 개선: 단일 자산군 비중 상한(Cap)
#     3개 전략(각 33.33%)을 합산했을 때 특정 티커의 최종 비중이 상한(기본 35%)을 넘으면
#     초과분을 현금(CASH)으로 자동 전환하여 강제 분산시킵니다.
#   - 2단계 개선: 월중 하드스탑(Intra-month Stop-loss)
#     일별 가격으로 월중 누적 손실을 감시하다가, 포트폴리오가 월초(전월 말 종가) 대비 임계치
#     (기본 -10%)까지 하락하면 그 시점 이후 월말까지 전량 현금화한 것으로 간주해 추가 손실을 차단합니다.
# ============================================================
@st.cache_data(ttl=3600)
def run_backtest_strategy_mix_improved_full(
    monthly_px, spy_divs, daily_px=None,
    apply_cap=False, weight_cap=35.0,
    apply_stop_loss=False, stop_loss_pct=-10.0,
):
    bt_a = run_backtest_strategy_a_full(monthly_px)
    bt_b = run_backtest_strategy_b_full(monthly_px)
    bt_c = run_backtest_strategy_c_full(monthly_px, spy_divs)

    if bt_a.empty or bt_b.empty or bt_c.empty:
        return pd.DataFrame()

    bt_a = bt_a.set_index("date")
    bt_b = bt_b.set_index("date")
    bt_c = bt_c.set_index("date")

    common_dates = sorted(set(bt_a.index) & set(bt_b.index) & set(bt_c.index))
    if not common_dates:
        return pd.DataFrame()

    monthly_returns = monthly_px.pct_change().shift(-1)
    monthly_idx = monthly_px.index
    can_stop_loss = apply_stop_loss and daily_px is not None

    records = []
    nav = 100.0
    peak = 100.0

    for d in common_dates:
        alloc_a = dict(bt_a.loc[d, "alloc"])
        alloc_b = dict(bt_b.loc[d, "alloc"])
        alloc_c = dict(bt_c.loc[d, "alloc"])

        try:
            pos = monthly_idx.get_loc(d)
        except KeyError:
            continue
        # d는 "수익이 실현되는 시점"이므로, 그 직전 월(pos-1)이 리밸런싱 결정 시점
        decision_pos = pos - 1 if pos > 0 else None
        decision_date = monthly_idx[decision_pos] if decision_pos is not None else None

        # --- 3개 전략(각 33.33%) 결합 ---
        combined_alloc = {}
        for src in (alloc_a, alloc_b, alloc_c):
            for t, w in src.items():
                combined_alloc[t] = combined_alloc.get(t, 0.0) + (w / 100.0) * (1.0 / 3.0) * 100.0

        # --- 1단계 개선 로직: 단일 자산군 비중 상한(Cap) ---
        cap_note = ""
        combined_pre_cap = dict(combined_alloc)
        excess_cash = 0.0
        if apply_cap:
            capped_alloc = {}
            excess_cash = 0.0
            for t, w in combined_alloc.items():
                if t == "CASH (현금)":
                    continue
                if w > weight_cap:
                    capped_alloc[t] = weight_cap
                    excess_cash += (w - weight_cap)
                else:
                    capped_alloc[t] = w
            capped_alloc["CASH (현금)"] = combined_alloc.get("CASH (현금)", 0.0) + excess_cash
            if excess_cash > 0.01:
                cap_note = " 📐Cap적용"
            combined_alloc = capped_alloc

        final_alloc = combined_alloc

        # --- 수익률 계산 (기본: 월간 수익률) ---
        port_ret = 0.0
        if decision_pos is not None:
            for t, w in final_alloc.items():
                if t != "CASH (현금)" and t in monthly_returns.columns:
                    r = monthly_returns[t].iloc[decision_pos]
                    if pd.notna(r):
                        port_ret += (w / 100.0) * r

        # --- 2단계 개선 로직: 월중 하드스탑 (일별 가격으로 월중 낙폭 감시) ---
        stop_note = ""
        if can_stop_loss and decision_date is not None:
            tickers_held = [t for t in final_alloc if t != "CASH (현금)" and final_alloc[t] > 0.01 and t in daily_px.columns]
            day_mask = (daily_px.index > decision_date) & (daily_px.index <= d)
            day_slice = daily_px.loc[day_mask]
            prior_prices_df = daily_px.loc[:decision_date]

            if len(day_slice) > 0 and tickers_held and len(prior_prices_df) > 0:
                start_prices = prior_prices_df.iloc[-1]
                cum_val = pd.Series(0.0, index=day_slice.index)
                for t in tickers_held:
                    w = final_alloc[t] / 100.0
                    if pd.isna(start_prices[t]) or start_prices[t] == 0:
                        continue
                    t_ret = day_slice[t] / start_prices[t] - 1.0
                    cum_val = cum_val + (t_ret.fillna(0.0) * w)

                stop_triggered = cum_val[cum_val * 100.0 <= stop_loss_pct]
                if len(stop_triggered) > 0:
                    port_ret = stop_triggered.iloc[0]
                    stop_note = f" 🛑월중손절({stop_triggered.index[0].strftime('%m/%d')})"
                elif len(cum_val) > 0:
                    port_ret = cum_val.iloc[-1]  # 일별 경로 기준 최종 수익률 (월간 수익률과 근사적으로 일치)

        nav *= (1 + port_ret)
        peak = max(peak, nav)
        dd = (nav / peak - 1) * 100

        mode_a_short = bt_a.loc[d, "mode"].split(" ")[0]
        mode_b_short = bt_b.loc[d, "mode"].split(" ")[0]
        mode_c_short = bt_c.loc[d, "mode"].split(" ")[0]
        mode_str = f"A:{mode_a_short} / B:{mode_b_short} / C:{mode_c_short}{cap_note}{stop_note}"
        def _fmt_part(src_alloc):
            # 각 전략은 전체 자산의 1/3 (상한 적용 시 해당 티커 비중만큼 비례 축소)
            items = []
            for t, w in src_alloc.items():
                base = w / 3.0
                if apply_cap and t != "CASH (현금)" and combined_pre_cap.get(t, 0.0) > 0:
                    base *= final_alloc.get(t, 0.0) / combined_pre_cap[t]
                if base > 0.01:
                    items.append(f"{t} {base:.1f}%")
            return ", ".join(items)
        weights_str = f"A[{_fmt_part(alloc_a)}] + B[{_fmt_part(alloc_b)}] + C[{_fmt_part(alloc_c)}]"
        if apply_cap and excess_cash > 0.01:
            weights_str += f" + 상한초과분[CASH (현금) {excess_cash:.1f}%]"

        records.append({
            "date": d,
            "mode": mode_str,
            "nav": nav,
            "monthly_return": port_ret * 100,
            "drawdown": dd,
            "weights_str": weights_str,
            "alloc": dict(final_alloc),
        })

    return pd.DataFrame(records)

# 관심매크로 지표 정의 및 심볼 매핑 (미국 30년물 국채 금리 추가)
MACRO_TICKERS = {
    "미국 10년물 국채 금리": "^TNX",
    "미국 30년물 국채 금리": "^TYX",
    "달러/원": "USDKRW=X",
    "WTI유": "CL=F",
    "미국 물가연동채권": "TIP",
    "미국 달러 지수": "DX-Y.NYB",
    "달러/엔": "USDJPY=X",
    "CBOE VIX": "^VIX",
}

@st.cache_data(ttl=60) # 시황 데이터는 1분 단위 캐싱
def get_macro_market_pulse():
    macro_data = []
    for name, symbol in MACRO_TICKERS.items():
        price_val = "-"
        delta_val = "0.00"
        delta_pct_val = "0.00%"
        raw_delta_val = 0.0
        
        try:
            ticker = yf.Ticker(symbol)
            # 주말 데이터 대응을 위해 넉넉히 5일 데이터를 조회
            hist = ticker.history(period="5d")
            if not hist.empty and 'Close' in hist.columns and len(hist) >= 1:
                closes = hist['Close'].dropna()
                if len(closes) >= 1:
                    current_price = closes.iloc[-1]
                    prev_price = closes.iloc[-2] if len(closes) >= 2 else current_price
                    delta = current_price - prev_price
                    delta_pct = (delta / prev_price) * 100 if prev_price > 0 else 0.0
                    
                    if symbol in ["^TNX", "^TYX"]:
                        price_val = f"{current_price:.3f}%"
                        delta_val = f"{delta:+.3f}"
                    elif "KRW=X" in symbol:
                        price_val = f"{current_price:,.2f}원"
                        delta_val = f"{delta:+.2f}"
                    elif "=X" in symbol:
                        price_val = f"{current_price:,.4f}"
                        delta_val = f"{delta:+.4f}"
                    else:
                        price_val = f"{current_price:,.2f}"
                        delta_val = f"{delta:+.2f}"
                    
                    delta_pct_val = f"{delta_pct:+.2f}%"
                    raw_delta_val = delta
        except Exception:
            pass
        
        macro_data.append({
            "name": name,
            "symbol": symbol,
            "price": price_val,
            "delta": delta_val,
            "delta_pct": delta_pct_val,
            "raw_delta": raw_delta_val
        })
    return macro_data

with st.spinner("관심 시황판 실시간 매크로 지표 동기화 중..."):
    macro_pulse = get_macro_market_pulse()

# ===================== 🌍 글로벌 마켓 & 매크로 시황판 (2026-10-23 개편) =====================
# 구성: ① 주요 지수 띠 → ② 매크로 시황판(표) + ③ 시장 위험 신호판·종합 → ④ 오늘 브리핑 인포그래픽(자료실) 바로가기
# 위험 신호판은 금리·VIX·채권 2년치를 받아야 해서, 시황판을 '펼쳤을 때만' 불러옴 (expander on_change="rerun" + .open)
INDEX_STRIP = [("S&P500", "^GSPC", ""), ("나스닥", "^IXIC", ""), ("다우", "^DJI", ""), ("코스피", "^KS11", ""), ("브렌트유", "BZ=F", "$")]
MACRO_SHORT = {   # 시황판 표에 쓰는 짧은 이름
    "^TNX": ("美 10년물 금리", "국채 10년"), "^TYX": ("美 30년물 금리", "국채 30년"), "USDKRW=X": ("원/달러", "환율"),
    "CL=F": ("WTI 유가", "근월물 · 배럴당"), "TIP": ("TIP", "물가연동채 ETF"), "DX-Y.NYB": ("달러지수", "DXY"),
    "USDJPY=X": ("달러/엔", "환율"), "^VIX": ("VIX", "공포지수"),
}
_macro_seq = [0]          # 한 화면에 시황판이 여러 번(탭마다) 나와서, 펼침 상태를 따로 기억하도록 번호를 붙임 (매 실행마다 0부터)


@st.cache_data(ttl=300, show_spinner=False)
def get_index_strip():
    """주요 지수 5개: [(이름, 값 문자열, 등락률 %, 등락)] — 5분 저장."""
    out = []
    try:
        df = yf.download([t for _, t, _ in INDEX_STRIP], period="7d", interval="1d", progress=False, auto_adjust=False)
        c = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
    except Exception:
        c = pd.DataFrame()
    for nm, t, pre in INDEX_STRIP:
        try:
            s = c[t].dropna()
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            out.append((nm, f"{pre}{last:,.2f}", (last / prev - 1) * 100, s.index[-1]))
        except Exception:
            out.append((nm, "-", None, None))
    return out


def _chg_color(v):
    """한국식: 오르면 빨강, 내리면 파랑 (앱 전체와 같게)."""
    return "#dc2626" if v > 0 else ("#2563eb" if v < 0 else "#64748b")


def _macro_index_strip_html():
    cards = []
    for nm, val, pct, _d in get_index_strip():
        chg = (f"<div style='color:{_chg_color(pct)};font-weight:700;font-size:0.85rem'>{pct:+.2f}%</div>" if pct is not None else "")
        cards.append(f"<div style='box-sizing:border-box;flex:1 1 115px;min-width:110px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:8px 10px'>"
                     f"<div style='font-size:0.78rem;color:#475569;font-weight:700'>{nm}</div>"
                     f"<div style='font-size:1.08rem;font-weight:800;color:#0f172a;white-space:nowrap'>{val}</div>{chg}</div>")
    return "<div style='display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 12px'>" + "".join(cards) + "</div>"


def _macro_table_html():
    rows = []
    for it in macro_pulse:
        sym, raw = it["symbol"], float(it.get("raw_delta") or 0)
        nm, sub = MACRO_SHORT.get(sym, (it["name"], sym))
        val = it["price"]
        if sym in ("^TNX", "^TYX"):          # 금리: 소수 둘째 자리 % + bp 변화
            try:
                val = f"{float(str(val).rstrip('%')):.2f}%"
            except Exception:
                pass
            d1, d2 = f"{raw * 100:+.0f}bp", ""
        else:
            d1, d2 = it["delta"], it["delta_pct"]
        col = _chg_color(raw)
        rows.append("<tr>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid #eef2f7'><div style='font-weight:700;color:#0f172a'>{nm}</div>"
                    f"<div style='font-size:0.72rem;color:#94a3b8'>{sub} · {sym}</div></td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;font-size:1.02rem;white-space:nowrap'>{val}</td>"
                    f"<td style='padding:8px 10px;border-bottom:1px solid #eef2f7;text-align:right;white-space:nowrap'>"
                    f"<div style='color:{col};font-weight:700'>{d1}</div><div style='color:{col};font-size:0.75rem'>{d2}</div></td></tr>")
    return ("<div style='font-weight:800;color:#0f2747;border-left:4px solid #0f2747;padding-left:8px;margin-bottom:6px'>매크로 시황판 "
            "<span style='font-weight:400;color:#94a3b8;font-size:0.8rem'>전일 대비</span></div>"
            "<div style='background:#fff;border:1px solid #e2e8f0;border-radius:10px;overflow-x:auto'>"
            "<table style='border-collapse:collapse;width:100%;font-size:0.88rem'>" + "".join(rows) + "</table></div>")


def _macro_risk_html():
    c = get_risk_signal_data()
    rc = _risk_cards(c) if (c is not None and not c.empty) else []
    head = ("<div style='font-weight:800;color:#0f2747;border-left:4px solid #0f2747;padding-left:8px;margin-bottom:6px'>시장 위험 신호판</div>")
    if not rc:
        return head + "<div style='color:#64748b;font-size:0.85rem'>위험 신호 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</div>"
    badge = {"🟢": ("양호", "#15803d"), "🟡": ("주의", "#c98500"), "⚠️": ("경고", "#d1453b")}
    rows = []
    for title, val, stt, txt in rc:
        lab, col = badge.get(stt, ("-", "#64748b"))
        import re as _re_m
        short = _re_m.sub(r"\([^)]*\)", "", txt.split(". ")[0]).strip().rstrip(".")   # 첫 문장에서 괄호 안 숫자만 뺌
        rows.append("<div style='display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #eef2f7'>"
                    f"<span style='flex:0 0 auto;background:{col};color:#fff;border-radius:999px;padding:2px 10px;font-size:0.78rem;font-weight:800;margin-top:2px'>{lab}</span>"
                    f"<div><div style='font-weight:700;color:#0f172a;font-size:0.9rem'>{title} <span style='color:#475569;font-weight:600'>{val}</span></div>"
                    f"<div style='font-size:0.78rem;color:#64748b;line-height:1.45'>{short}</div></div></div>")
    nw = sum(1 for x in rc if x[2] == "⚠️"); nc = sum(1 for x in rc if x[2] == "🟡")
    r_i = 2 if nw >= 2 else (1 if (nw == 1 or nc >= 2) else 0)      # 🩺 시장위험진단과 같은 기준
    lab = ["평온", "긴장", "위험"][r_i]; col = ["#15803d", "#c98500", "#d1453b"][r_i]
    total = ("<div style='display:flex;gap:12px;align-items:center;background:#0f2747;border-radius:12px;padding:12px 14px;margin-top:10px'>"
             f"<span style='background:{col};color:#fff;border-radius:10px;padding:8px 12px;font-size:1.2rem;font-weight:900;white-space:nowrap'>{lab}</span>"
             f"<div style='color:#fff'><div style='font-weight:800'>종합: 경고 {nw} · 주의 {nc}</div>"
             "<div style='font-size:0.78rem;color:#cbd5e1'>매매 신호가 아니라 시장 긴장도를 보는 참고 정보입니다</div></div></div>")
    return head + "<div style='background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:2px 14px'>" + "".join(rows) + "</div>" + total


MACRO_RISK_GUIDE = """
**데이터** — 야후 일봉 2년치(1시간 저장, 미국 장중이면 마지막 값은 진행 중인 값): `^TNX` 10년물 금리 · `^IRX` 3개월 국채 금리 · `^VIX` · `^VIX3M` 3개월 VIX · `HYG` 하이일드 회사채 ETF · `IEF` 7\\~10년 국채 ETF · `DX-Y.NYB` 달러지수. 3개월 = 63거래일, 1년 = 252거래일, 50·200일선 = 최근 50·200거래일 평균.

**① 장단기 금리차** = 10년물 − 3개월 금리

| 판정 | 조건 |
|---|---|
| ⚠️ 경고 | 0 미만(역전), 또는 지금은 0 이상이지만 최근 1년 안에 역전됐던 적이 있음 |
| 🟡 주의 | 0 이상 0.5%p 미만 (평탄) |
| 🟢 양호 | 0.5%p 이상 |

역전은 경기침체 신호로 알려져 있고, 실제 침체는 역전이 **풀린 뒤** 시작된 경우가 많아(2001·2008·2020년) 풀린 직후 1년도 경고로 봅니다.

**② VIX 기간구조** = VIX ÷ 3개월 VIX

| 판정 | 조건 |
|---|---|
| ⚠️ 경고 | 1.0 이상 — 당장의 공포가 3개월 뒤 걱정보다 큼 (급락장) |
| 🟡 주의 | 0.9 이상 1.0 미만 |
| 🟢 양호 | 0.9 미만 — 평소의 정상 구조 |

VIX 수준(20 미만 평온 · 20 이상 높음 · 30 이상 매우 높음)은 설명에만 쓰고 판정에는 쓰지 않습니다.

**③ 신용 위험** = HYG ÷ IEF (배당 반영 가격)

| 판정 | 조건 |
|---|---|
| ⚠️ 경고 | 비율이 200일 평균 아래 **이면서** 3개월 변화가 마이너스 |
| 🟡 주의 | 위가 아니고 비율이 50일 평균 아래 |
| 🟢 양호 | 50일 평균 이상 |

하이일드채가 국채보다 약해지면 기업 부도 위험을 걱정하기 시작했다는 뜻이고, 주식보다 먼저 움직이는 경우가 많습니다.

**④ 달러 강도** = 달러지수

| 판정 | 조건 |
|---|---|
| ⚠️ 경고 | 3개월 동안 +5% 넘게 오름 (급격한 강세) |
| 🟡 주의 | 위가 아니고 200일 평균 위 |
| 🟢 양호 | 200일 평균 아래 |

달러가 급하게 강해지면 신흥국·원자재·위험자산에서 돈이 빠지는 경우가 많습니다.

**종합 판정** (🩺 시장위험진단과 같은 기준)

| 종합 | 조건 |
|---|---|
| 🔴 위험 | 경고 2개 이상 |
| 🟡 긴장 | 경고 1개, 또는 주의 2개 이상 |
| 🟢 평온 | 그 밖 (경고 0개, 주의 1개 이하) |

예: 양호 1 · 주의 3 · 경고 0 → 주의가 2개 이상이라 **긴장**.

**한계** — 0.5%p · 0.9 · 5% 같은 기준은 자주 쓰이는 관행값이고 백테스트로 고른 값이 아닙니다. 매매 신호가 아니라 목돈 투입 방식·위성 자산 비중 같은 규칙 밖 결정의 참고이며, 실제 매매는 혼합전략 규칙과 200일선 보유 기준을 따릅니다. 장중 값이 들어가 하루 안에도 판정이 바뀔 수 있어(특히 VIX 비율) 종가 기준으로는 미국 장 마감 뒤에 확인하세요. 아침 브리핑 인포그래픽은 여러 출처·근사값을 써서 판정이 한 칸 정도 다를 수 있습니다.
"""


def render_macro_board():
    """🌍 글로벌 마켓 & 매크로 시황판 (접힘 기본). 각 탭 맨 위에서 호출합니다."""
    _macro_seq[0] += 1
    _n = _macro_seq[0]
    try:      # 펼침 상태 추적(Streamlit 1.55+): 펼쳤을 때만 위험 신호판 데이터를 받음
        exp = st.expander("🌍 글로벌 마켓 & 매크로 시황판", expanded=False, key=f"macro_board_{_n}", on_change="rerun")
    except TypeError:   # 예전 버전: 상태 추적 없이 항상 그림
        exp = st.expander("🌍 글로벌 마켓 & 매크로 시황판", expanded=False)
    with exp:
        _open = getattr(exp, "open", None)
        if _open is False:
            return
        st.markdown(_macro_index_strip_html(), unsafe_allow_html=True)
        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.markdown(_macro_table_html(), unsafe_allow_html=True)
        with c2:
            with st.spinner("위험 신호 데이터를 불러오는 중… (처음엔 5~15초)"):
                st.markdown(_macro_risk_html(), unsafe_allow_html=True)
        b1, b2 = st.columns([1.1, 1])
        with b1:
            st.caption("시세: 야후 파이낸스 최근 종가·실시간 값(지수 5분, 시황판 1분 저장) · 오르면 빨강, 내리면 파랑. "
                       "위험 신호판 자세한 해설은 미국 ETF 탭 → ⚠️ 시장 위험 신호판 · 🩺 시장위험진단.")
        with b2:
            if st.button("📰 오늘 브리핑 인포그래픽 보기 (자료실)", key=f"macro_brief_{_n}", use_container_width=True):
                st.session_state["library_open_doc"] = "인포그래픽"     # 자료실 페이지가 이 문서를 먼저 선택
                st.switch_page("pages/9_library.py")
        # 📖 읽는 법 (시황판 안이라 펼치기 상자를 겹칠 수 없어 접기/펼치기 단추로)
        if tab_toggle("📖 시장 위험 신호판 읽는 법 — 신호 계산 기준", key=f"macro_risk_guide_{_n}_r"):
            st.markdown(MACRO_RISK_GUIDE)


@st.cache_data(ttl=3600, show_spinner=False)
def _usd_krw_live():
    hist = yf.Ticker("USDKRW=X").history(period="5d")
    closes = hist["Close"].dropna() if (not hist.empty and "Close" in hist.columns) else pd.Series(dtype=float)
    if len(closes) < 1:
        raise RuntimeError("환율 없음")          # 실패는 캐시하지 않음
    return float(closes.iloc[-1])


def get_usd_krw_rate():
    """원/달러 환율 (1시간 저장 — 버튼을 누를 때마다 야후에 다시 묻지 않도록)."""
    try:
        return _usd_krw_live()
    except Exception:
        return 1380.0 # 기본 백업 환율

# 배당 히스토리 직접 계산을 1순위 기본으로 사용 (yfinance API 변동에 따른 엣지케이스 완전 방지)
def _sp500_dividend_yield_raw():
    try:
        spy = yf.Ticker("SPY")
        
        # 1. 배당 히스토리 기반 직접 계산 (Primary)
        divs = spy.dividends
        if not divs.empty:
            utc_tz = divs.index.tz
            end_dt = pd.Timestamp.now(tz=utc_tz)
            start_dt = end_dt - pd.Timedelta(days=365)
            last_year_divs = divs.loc[start_dt:end_dt]
            sum_divs = last_year_divs.sum()
            
            hist = spy.history(period="1mo")
            if not hist.empty and 'Close' in hist.columns:
                closes = hist['Close'].dropna()
                if len(closes) >= 1:
                    curr_price = float(closes.iloc[-1])
                    if curr_price > 0:
                        return (sum_divs / curr_price) * 100

        # 2. .info 필드 보조 사용 (Fallback)
        dy = spy.info.get('dividendYield')
        if dy is not None:
            dy_val = float(dy)
            if dy_val < 0.15:
                return dy_val * 100
            return dy_val
    except Exception:
        pass
    return 1.32 # 기본값 백업


@st.cache_data(ttl=3600, show_spinner=False)
def _sp500_dividend_yield_live():
    v = _sp500_dividend_yield_raw()
    if v == 1.32:
        raise RuntimeError("배당수익률 계산 실패")   # 백업값은 캐시하지 않음(전략 C 신호가 1시간 묶이지 않도록)
    return v


def get_sp500_dividend_yield():
    """S&P500 실시간 배당수익률 (1시간 저장). 실패하면 백업값 1.32%."""
    try:
        return _sp500_dividend_yield_live()
    except Exception:
        return 1.32

def _robust_close_download(tickers, start, interval="1d"):
    """야후 일괄 다운로드가 일부 종목만 실패('possibly delisted')할 때 빠진 종목을 다시 받아 채운다."""
    import time as _time
    tickers = list(dict.fromkeys(tickers))
    closes = pd.DataFrame()
    try:
        df = yf.download(tickers, start=start, interval=interval, progress=False, auto_adjust=True)
        c = df["Close"] if "Close" in df.columns else df
        if isinstance(c, pd.Series):
            c = c.to_frame(tickers[0])
        closes = c.copy()
    except Exception:
        pass

    def _missing():
        return [t for t in tickers if t not in closes.columns or closes[t].dropna().empty]

    # 2차: 빠진 종목만 작은 묶음으로 순차 재시도
    miss = _missing()
    for i in range(0, len(miss), 5):
        chunk = miss[i:i + 5]
        _time.sleep(1.0)
        try:
            df = yf.download(chunk, start=start, interval=interval, progress=False,
                             auto_adjust=True, threads=False)
            c = df["Close"] if "Close" in df.columns else df
            if isinstance(c, pd.Series):
                c = c.to_frame(chunk[0])
            for t in chunk:
                if t in c.columns and not c[t].dropna().empty:
                    closes = closes.reindex(closes.index.union(c.index)) if not closes.empty else pd.DataFrame(index=c.index)
                    closes[t] = c[t]
        except Exception:
            pass

    # 3차: 그래도 빠진 종목은 종목별 history로
    for t in _missing():
        for _try in range(2):
            try:
                _time.sleep(0.7 * (_try + 1))
                h = yf.Ticker(t).history(start=start, interval=interval, auto_adjust=True)
                if h is not None and not h.empty and "Close" in h.columns:
                    s = h["Close"].copy()
                    if getattr(s.index, "tz", None) is not None:
                        s.index = s.index.tz_localize(None)
                    s.index = s.index.normalize()
                    closes = closes.reindex(closes.index.union(s.index)) if not closes.empty else pd.DataFrame(index=s.index)
                    closes[t] = s
                    break
            except Exception:
                pass
    return closes.sort_index()

@st.cache_data(ttl=3600) 
def get_all_financial_data_v2(tickers):
    data_list = []
    now = datetime.datetime.now()
    start_date = (now - datetime.timedelta(days=450)).strftime('%Y-%m-%d')
    
    try:
        # 배치 다운로드 + 실패 종목 재시도
        closes_df = _robust_close_download(tickers, start_date, "1mo")
            
        for ticker in tickers:
            try:
                if isinstance(closes_df, pd.DataFrame) and ticker in closes_df.columns:
                    closes = closes_df[ticker].dropna()
                elif isinstance(closes_df, pd.Series):
                    closes = closes_df.dropna()
                else:
                    continue
                    
                if len(closes) < 12:
                    continue
                
                # 가장 최근 종가 및 과거 종가 추출
                current_price = float(closes.iloc[-1])
                p1 = float(closes.iloc[-2]) if len(closes) >= 2 else current_price
                p3 = float(closes.iloc[-4]) if len(closes) >= 4 else current_price
                p5 = float(closes.iloc[-6]) if len(closes) >= 6 else current_price # 전략B/C 방어용 5개월 가격
                p6 = float(closes.iloc[-7]) if len(closes) >= 7 else current_price
                p9 = float(closes.iloc[-10]) if len(closes) >= 10 else current_price
                p12 = float(closes.iloc[-13]) if len(closes) >= 13 else float(closes.iloc[0])
                
                # 수익률 계산 (%)
                r1 = ((current_price - p1) / p1) * 100
                r3 = ((current_price - p3) / p3) * 100
                r5 = ((current_price - p5) / p5) * 100
                r6 = ((current_price - p6) / p6) * 100
                r9 = ((current_price - p9) / p9) * 100
                r12 = ((current_price - p12) / p12) * 100
                
                # 전략 A / C 공격용 스코어 계산 (1, 3, 6, 12 단순평균)
                score_a_off = (r1 + r3 + r6 + r12) / 4
                
                # 전략 A / C 방어용 스코어 계산 (1, 3, 6, 9, 12 단순평균)
                score_a_def = (r1 + r3 + r6 + r9 + r12) / 5
                
                # 전략 B용 스코어 계산 (가중평균 및 단순평균)
                score_b_off = (r1 * 12 + r3 * 4 + r6 * 2 + r12 * 1) / 19
                score_b_def_simple = (r1 + r3 + r6 + r9 + r12) / 5 # 전략B 방어자산 단순 모멘텀
                
                data_list.append({
                    "Ticker": ticker,
                    "현재가": round(current_price, 2),
                    "1M": round(r1, 1), 
                    "3M": round(r3, 1), 
                    "5M": round(r5, 1),
                    "6M": round(r6, 1), 
                    "9M": round(r9, 1), 
                    "12M": round(r12, 1),
                    "A_공격스코어": round(score_a_off, 2),
                    "A_방어스코어": round(score_a_def, 2),
                    "B_공격스코어": round(score_b_off, 2),
                    "B_단순모멘텀": round(score_b_def_simple, 2),
                    "raw_closes": closes.tolist()
                })
            except Exception:
                pass
    except Exception as e:
        st.error(f"금융 데이터 다운로드 중 오류 발생: {e}")
    
    out = pd.DataFrame(data_list)
    # 핵심 종목이 빠진 결과는 캐시에 남기지 않도록 예외 처리 (새로고침 시 다시 받게)
    if out.empty or "TIP" not in out["Ticker"].values or "SPY" not in out["Ticker"].values:
        raise RuntimeError("core data incomplete")
    return out

@st.cache_data(ttl=3600)
def get_historical_simulation_data(tickers):
    prices_dict = {}
    now = datetime.datetime.now()
    start_date = (now - datetime.timedelta(days=800)).strftime('%Y-%m-%d')
    
    try:
        closes_df = _robust_close_download(tickers, start_date, "1d")
            
        for ticker in tickers:
            if isinstance(closes_df, pd.DataFrame) and ticker in closes_df.columns:
                series = closes_df[ticker].dropna()
                if not series.empty:
                    prices_dict[ticker] = series
            elif isinstance(closes_df, pd.Series):
                series = closes_df.dropna()
                if not series.empty:
                    prices_dict[ticker] = series
    except Exception:
        pass
    
    spy_divs = pd.Series(dtype=float)
    try:
        spy_divs = yf.Ticker("SPY").dividends
    except Exception:
        pass
    if spy_divs is None:                       # 야후 접속 실패 시 일부 yfinance 버전은 None을 돌려줌
        spy_divs = pd.Series(dtype=float)
    
    return prices_dict, spy_divs

def compute_historical_portfolio_at_month_end(prices_dict, spy_divs, target_date, OFFENSIVE_A, DEFENSIVE_A, OFFENSIVE_B, DEFENSIVE_B, OFFENSIVE_C, DEFENSIVE_C, return_parts=False):
    monthly_prices = {}
    for t, series in prices_dict.items():
        sub_series = series[series.index <= target_date]
        if sub_series.empty:
            continue
        
        df = sub_series.to_frame()
        df['year'] = df.index.year
        df['month'] = df.index.month
        last_idx = df.groupby(['year', 'month']).apply(lambda x: x.index[-1])
        m_closes = sub_series.loc[last_idx].tolist()
        
        if len(m_closes) < 13:
            continue
        monthly_prices[t] = m_closes

    if "TIP" not in monthly_prices or "SPY" not in monthly_prices:
        if return_parts:
            _cash = {"CASH (현금)": 100.0}
            return {"CASH (현금)": 100.0}, False, False, False, 1.32, {"A": dict(_cash), "B": dict(_cash), "C": dict(_cash)}
        return {"CASH (현금)": 100.0}, False, False, False, 1.32

    def calc_momentum_and_scores(m_closes):
        curr = m_closes[-1]
        p1 = m_closes[-2] if len(m_closes) >= 2 else curr
        p3 = m_closes[-4] if len(m_closes) >= 4 else curr
        p5 = m_closes[-6] if len(m_closes) >= 6 else curr
        p6 = m_closes[-7] if len(m_closes) >= 7 else curr
        p9 = m_closes[-10] if len(m_closes) >= 10 else curr
        p12 = m_closes[-13] if len(m_closes) >= 13 else m_closes[0]

        r1 = ((curr - p1) / p1) * 100
        r3 = ((curr - p3) / p3) * 100
        r5 = ((curr - p5) / p5) * 100
        r6 = ((curr - p6) / p6) * 100
        r9 = ((curr - p9) / p9) * 100
        r12 = ((curr - p12) / p12) * 100

        score_a_off = (r1 + r3 + r6 + r12) / 4
        score_a_def = (r1 + r3 + r6 + r9 + r12) / 5
        score_b_off = (r1 * 12 + r3 * 4 + r6 * 2 + r12 * 1) / 19
        score_b_def_simple = (r1 + r3 + r6 + r9 + r12) / 5

        return {
            "curr": curr,
            "r1": r1, "r3": r3, "r5": r5, "r6": r6, "r9": r9, "r12": r12,
            "A_공격스코어": score_a_off,
            "A_방어스코어": score_a_def,
            "B_공격스코어": score_b_off,
            "B_단순모멘텀": score_b_def_simple
        }

    ticker_metrics = {}
    for t, m_closes in monthly_prices.items():
        ticker_metrics[t] = calc_momentum_and_scores(m_closes)

    # 1. 전략 A 배분
    tip_closes = monthly_prices["TIP"]
    tip_current = tip_closes[-1]
    tip_last11 = tip_closes[-11:]
    tip_ma11 = sum(tip_last11) / len(tip_last11)
    is_attack_a_hist = tip_current > tip_ma11

    alloc_a_hist = {}
    if is_attack_a_hist:
        off_scores = []
        for t in OFFENSIVE_A:
            if t in ticker_metrics:
                off_scores.append((t, ticker_metrics[t]["A_공격스코어"]))
        if off_scores:
            off_scores.sort(key=lambda x: x[1], reverse=True)
            for t, _ in off_scores[:4]:
                alloc_a_hist[t] = 25.0
        else:
            alloc_a_hist["CASH (현금)"] = 100.0
    else:
        def_scores = []
        for t in DEFENSIVE_A:
            if t in ticker_metrics:
                def_scores.append((t, ticker_metrics[t]["A_방어스코어"]))
        if def_scores:
            def_scores.sort(key=lambda x: x[1], reverse=True)
            top_1 = def_scores[0]
            if top_1[1] > 0:
                alloc_a_hist[top_1[0]] = 100.0
            else:
                alloc_a_hist["CASH (현금)"] = 100.0
        else:
            alloc_a_hist["CASH (현금)"] = 100.0

    # 2. 전략 B 배분
    tip_metrics = ticker_metrics["TIP"]
    tip_score_b_hist = (tip_metrics["r1"] + tip_metrics["r3"] + tip_metrics["r6"] + tip_metrics["r9"] + tip_metrics["r12"]) / 5
    is_attack_b_hist = tip_score_b_hist > 0

    alloc_b_hist = {}
    if is_attack_b_hist:
        off_scores = []
        for t in OFFENSIVE_B:
            if t in ticker_metrics:
                off_scores.append((t, ticker_metrics[t]["B_공격스코어"]))
        if off_scores:
            off_scores.sort(key=lambda x: x[1], reverse=True)
            alloc_b_hist[off_scores[0][0]] = 100.0
        else:
            alloc_b_hist["CASH (현금)"] = 100.0
    else:
        def_scores = []
        for t in DEFENSIVE_B:
            if t in ticker_metrics:
                def_scores.append((t, ticker_metrics[t]["r5"], ticker_metrics[t]["B_단순모멘텀"]))
        if def_scores:
            def_scores.sort(key=lambda x: x[1], reverse=True)
            top_1 = def_scores[0]
            if top_1[2] > 0:
                alloc_b_hist[top_1[0]] = 100.0
            else:
                alloc_b_hist["CASH (현금)"] = 100.0
        else:
            alloc_b_hist["CASH (현금)"] = 100.0

    # 3. 전략 C 배분 (이중 스케일링 버그 수정 완료)
    dy_val = 1.32
    if spy_divs is not None and not spy_divs.empty:
        target_date_naive = target_date.tz_localize(None) if target_date.tz is not None else target_date
        start_dt = target_date_naive - pd.Timedelta(days=365)
        
        spy_divs_naive = spy_divs.copy()
        if spy_divs_naive.index.tz is not None:
            spy_divs_naive.index = spy_divs_naive.index.tz_localize(None)
        
        divs_in_range = spy_divs_naive.loc[start_dt:target_date_naive]
        sum_divs = divs_in_range.sum()
        
        spy_price = ticker_metrics.get("SPY", {}).get("curr", None)
        try:  # 배당수익률은 실제 종가 기준 (백테스트와 동일)
            _nom = get_spy_nominal_close().loc[:target_date_naive]
            if not _nom.empty and _nom.iloc[-1] > 0:
                spy_price = float(_nom.iloc[-1])
        except Exception:
            pass
        if spy_price and spy_price > 0:
            dy_val = float((sum_divs / spy_price) * 100)
        
    is_attack_c_hist = dy_val > 1.33

    alloc_c_hist = {}
    if is_attack_c_hist:
        off_scores = []
        for t in OFFENSIVE_C:
            if t in ticker_metrics:
                off_scores.append((t, ticker_metrics[t]["A_공격스코어"]))
        if off_scores:
            off_scores.sort(key=lambda x: x[1], reverse=True)
            alloc_c_hist[off_scores[0][0]] = 100.0
        else:
            alloc_c_hist["CASH (현금)"] = 100.0
    else:
        def_scores = []
        for t in DEFENSIVE_C:
            if t in ticker_metrics:
                def_scores.append((t, ticker_metrics[t]["A_방어스코어"]))
        if def_scores:
            def_scores.sort(key=lambda x: x[1], reverse=True)
            top_1 = def_scores[0]
            if top_1[1] > 0:
                alloc_c_hist[top_1[0]] = 100.0
            else:
                alloc_c_hist["CASH (현금)"] = 100.0
        else:
            alloc_c_hist["CASH (현금)"] = 100.0

    # 혼합 포트폴리오 비중 병합
    mixed_portfolio = {}
    for t, w in alloc_a_hist.items():
        mixed_portfolio[t] = mixed_portfolio.get(t, 0.0) + (w / 100.0) * 33.333
    for t, w in alloc_b_hist.items():
        mixed_portfolio[t] = mixed_portfolio.get(t, 0.0) + (w / 100.0) * 33.333
    for t, w in alloc_c_hist.items():
        mixed_portfolio[t] = mixed_portfolio.get(t, 0.0) + (w / 100.0) * 33.333

    clean_portfolio = {t: round(w, 2) for t, w in mixed_portfolio.items() if w > 0.01}
    if return_parts:
        return clean_portfolio, is_attack_a_hist, is_attack_b_hist, is_attack_c_hist, dy_val, {
            "A": dict(alloc_a_hist), "B": dict(alloc_b_hist), "C": dict(alloc_c_hist),
        }
    return clean_portfolio, is_attack_a_hist, is_attack_b_hist, is_attack_c_hist, dy_val

# ============================================================
# 자산 계산기 퀵 프리셋용: 각 전략 탭의 '초기 설정'과 같은 조건의 실측 CAGR
#   - 초기 설정 = 백테스트 시작일 2015-01-01 (장기 검증), 혼합전략 안전장치(비중 상한·하드스탑) 미적용
#   - 각 전략 탭과 동일한 종목·엔진·CAGR 계산식(일수 ÷ 365.25)을 사용하므로 탭에 표시되는 값과 일치합니다.
# ============================================================
PRESET_START = "2015-01-01"
PRESET_FALLBACK_CAGR = {"mix": 38.7, "A": 27.3, "B": 36.4, "C": 46.7}  # 데이터 로딩 실패 시에만 사용


def _cagr_from_bt(bt):
    days = (bt["date"].iloc[-1] - bt["date"].iloc[0]).days
    years = days / 365.25 if days > 0 else 1.0
    return ((bt["nav"].iloc[-1] / 100.0) ** (1 / years) - 1) * 100


@st.cache_data(ttl=3600)
def get_preset_cagrs(start=PRESET_START, cost_cfg=None, mix_opts=(False, 35.0, False, -10.0)):
    out = {}
    try:
        spy_divs = get_spy_dividend_history()
    except Exception:
        spy_divs = pd.Series(dtype=float)
    _cap_on, _cap_pct, _stop_on, _stop_pct = mix_opts
    specs = {
        "A": (sorted(set(OFFENSIVE_A + DEFENSIVE_A + ["TIP", "QQQ"])), lambda m, d: run_backtest_strategy_a_full(m)),
        "B": (sorted(set(OFFENSIVE_B + DEFENSIVE_B + ["TIP", "QQQ"])), lambda m, d: run_backtest_strategy_b_full(m)),
        "C": (sorted(set(OFFENSIVE_C + DEFENSIVE_C + ["SPY", "QQQ"])), lambda m, d: run_backtest_strategy_c_full(m, spy_divs)),
        "mix": (
            sorted(set(OFFENSIVE_A + DEFENSIVE_A + OFFENSIVE_B + DEFENSIVE_B + OFFENSIVE_C + DEFENSIVE_C + ["TIP", "SPY", "QQQ"])),
            lambda m, d: (
                run_backtest_strategy_mix_improved_full(
                    m, spy_divs, daily_px=d,
                    apply_cap=_cap_on, weight_cap=_cap_pct,
                    apply_stop_loss=_stop_on, stop_loss_pct=_stop_pct,
                ) if (_cap_on or _stop_on) else run_backtest_strategy_mix_full(m, spy_divs)
            ),
        ),
    }
    for key, (tickers, runner) in specs.items():
        try:
            daily = get_daily_price_history_a(tickers, start=start)
            bt = runner(to_monthly_last_a(daily), daily)
            if cost_cfg is not None and len(bt) > 0:
                bt = apply_trading_costs(bt, cost_cfg)  # 상단 슬리피지·세금 설정 반영
            out[key] = round(float(_cagr_from_bt(bt)), 2) if len(bt) > 0 else None
        except Exception:
            out[key] = None
    return out


# ============================================================
INTRAMONTH_REF_PCT = -10.0  # (사용 안 함, 2026-10-17 화면에서 참고 기준선 제거)

# 이번 달 일별 수익률 — 이번 달 일별 수익률 추적
#   - 직전 월말에 확정된 혼합 포트폴리오를 이번 달 보유 포트폴리오로 보고,
#     직전 월말 종가 대비 일별 누적 수익률을 백테스트와 같은 방식(비중 × 종목 누적수익률 합)으로 계산합니다.
# ============================================================
def now_us_eastern():
    """미국 동부 시간 기준 현재 시각 (한국 시간과 날짜가 달라 월말 판정이 어긋나는 문제 방지)."""
    try:
        return pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    except Exception:
        return pd.Timestamp(datetime.datetime.utcnow() - datetime.timedelta(hours=4))


@st.cache_data(ttl=300)
def get_intramonth_daily_prices(tickers, start):
    """보유 종목의 일별 종가 (5분 캐시). tickers는 tuple."""
    tickers = list(tickers)
    if not tickers:
        return pd.DataFrame()
    try:
        df = yf.download(tickers, start=start, interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"] if "Close" in df.columns.levels[0] else df
    else:
        close = df[["Close"]].rename(columns={"Close": tickers[0]}) if "Close" in df.columns else df
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    if getattr(close.index, "tz", None) is not None:
        close.index = close.index.tz_localize(None)
    close = close.dropna(how="all")
    # 배치 다운로드에서 빠졌거나 마지막 날짜가 다른 종목보다 늦은 종목은 하나씩 다시 받아 보완
    try:
        last_all = close.index.max() if len(close) else None
        for t in tickers:
            s_t = close[t].dropna() if t in close.columns else pd.Series(dtype=float)
            if s_t.empty or (last_all is not None and s_t.index.max() < last_all):
                h = yf.Ticker(t).history(start=start, interval="1d", auto_adjust=True)
                if h is not None and len(h) and "Close" in h.columns:
                    c_t = h["Close"].dropna()
                    if getattr(c_t.index, "tz", None) is not None:
                        c_t.index = c_t.index.tz_localize(None)
                    c_t.index = c_t.index.normalize()
                    base_t = close[t] if t in close.columns else pd.Series(dtype=float)
                    merged = c_t.combine_first(base_t)
                    close = close.reindex(close.index.union(merged.index))
                    close[t] = merged.reindex(close.index)
    except Exception:
        pass
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close.dropna(how="all")


def _expected_last_close_date():
    """지금(미국 동부 시간) 기준으로 이미 확정됐어야 할 마지막 정규장 종가 날짜 (공휴일은 고려 안 함)."""
    now = now_us_eastern()
    d = now.normalize()
    if d.weekday() >= 5 or (now.hour * 60 + now.minute) < (16 * 60 + 30):
        d = d - pd.offsets.BDay(1)
    while d.weekday() >= 5:
        d = d - pd.Timedelta(days=1)
    return d


@st.cache_data(ttl=300, show_spinner=False)
def get_latest_close_patch(tickers, expected_str):
    """일별 데이터에 확정 종가(expected_str 날짜)가 빠졌을 때 보완값을 구함.
    1순위: period='5d' 일봉(기간 지정 방식은 최신 봉이 더 빨리 들어오는 경우가 많음)
    2순위: 실시간 시세(last price) — 미국 정규장이 열려 있지 않을 때만 사용(장중 가격이 섞이지 않게)."""
    exp = pd.Timestamp(expected_str)
    out, how = {}, {}
    now = now_us_eastern()
    mins = now.hour * 60 + now.minute
    market_open = now.weekday() < 5 and now.normalize() > exp and 9 * 60 + 30 <= mins < 16 * 60
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d", interval="1d", auto_adjust=True)
            if h is not None and len(h) and "Close" in h.columns:
                c = h["Close"].dropna()
                if getattr(c.index, "tz", None) is not None:
                    c.index = c.index.tz_localize(None)
                c.index = c.index.normalize()
                if exp in c.index:
                    out[t] = float(c.loc[exp])
                    how[t] = "5일 일봉"
                    continue
            if not market_open:
                fi = yf.Ticker(t).fast_info
                lp = fi.get("lastPrice") if hasattr(fi, "get") else getattr(fi, "last_price", None)
                if lp is None:
                    lp = getattr(fi, "last_price", None)
                if lp:
                    out[t] = float(lp)
                    how[t] = "실시간 시세"
        except Exception:
            continue
    return out, how


def render_intramonth_stop_monitor(hist_prices, spy_divs_hist, strategy="mix"):
    """strategy: "mix"(혼합전략) 또는 "A" / "B" / "C"(개별 전략, 전략 자산의 100% 기준).
    제목은 밖에, 내용은 테두리 상자(백테스트 설정 패널과 같은 모양) 안에 표시합니다."""
    if strategy == "mix":
        st.markdown("### 📈 이번 달 일별 수익률")
    else:
        st.markdown(f"### 📈 전략 {strategy} 이번 달 일별 수익률")
    with st.container(border=True):
        st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
        _render_intramonth_body(hist_prices, spy_divs_hist, strategy)


def _render_intramonth_body(hist_prices, spy_divs_hist, strategy="mix"):
    is_mix = strategy == "mix"
    label = "혼합" if is_mix else f"전략 {strategy}"
    st.caption("⚠️ 이 일별 표는 슬리피지·거래비용·세금·환전 비용이 반영되지 않았으며 백테스트 비용·세금 설정과 무관합니다. 실제 체결 가격과 계좌 수익률은 이 값과 다를 수 있습니다.")

    if is_mix:
        stop_pct = INTRAMONTH_REF_PCT  # 월중 하드스탑은 제거됨 → 낙폭 참고 기준선으로만 사용
        cap_on = cap_on_setting()
        cap_pct = float(st.session_state.get("mix_cap_pct", 35.0))
    else:
        stop_pct = None  # 개별 전략은 월중 하드스탑을 운용하지 않음
        cap_on = False
        cap_pct = 100.0

    if not hist_prices or "SPY" not in hist_prices:
        st.warning("일별 가격 데이터를 불러오지 못해 이번 달 일별 수익률을 표시할 수 없습니다.")
        return

    # 1) 직전 완료 월말(= 이번 달 포트폴리오를 확정한 날) 찾기
    spy_idx = hist_prices["SPY"].index
    if getattr(spy_idx, "tz", None) is not None:
        spy_idx = spy_idx.tz_localize(None)
    # 월 판정은 미국 동부 시간 기준 (한국 시간 새벽에는 미국이 아직 전날 장중)
    now = now_us_eastern()
    month_ends = pd.Series(spy_idx, index=spy_idx).groupby([spy_idx.year, spy_idx.month]).max().tolist()
    completed = [pd.Timestamp(d) for d in month_ends if not (d.year == now.year and d.month == now.month)]
    if not completed:
        st.info("직전 월말 데이터가 없습니다.")
        return

    if st.button("🔄 최신 가격으로 새로고침", key=f"intramonth_refresh_{strategy}"):
        get_intramonth_daily_prices.clear()
        try:
            get_latest_close_patch.clear()
            get_historical_simulation_data.clear()
        except Exception:
            pass

    base_date = completed[-1]
    view_end = None      # 지난달 표시 모드일 때 마지막 날짜
    period_word = "이번 달"
    # 새 달 첫 거래일 데이터가 아직 없으면 → 지난달 일별 흐름을 대신 표시
    spy_fresh = get_intramonth_daily_prices(("SPY",), (base_date - pd.Timedelta(days=10)).strftime("%Y-%m-%d"))
    spy_dates = spy_fresh.index if not spy_fresh.empty else spy_idx
    if not (spy_dates > base_date).any() and len(completed) >= 2:
        view_end = base_date
        base_date = completed[-2]
        period_word = f"지난달({view_end.month}월)"
        st.info(
            f"{view_end.strftime('%Y-%m-%d')} 이후 새 달 거래일 데이터가 아직 없어 "
            f"{view_end.month}월 한 달의 일별 흐름을 표시합니다. 새 달 첫 거래일 장 마감 뒤 자동으로 이번 달로 바뀝니다."
        )

    # 2) 그 월말 기준 혼합 포트폴리오 (월말 리밸런싱 역사와 같은 계산)
    held_mix, _, _, _, _, parts = compute_historical_portfolio_at_month_end(
        hist_prices, spy_divs_hist, base_date,
        OFFENSIVE_A, DEFENSIVE_A, OFFENSIVE_B, DEFENSIVE_B, OFFENSIVE_C, DEFENSIVE_C,
        return_parts=True,
    )
    held = held_mix if is_mix else parts.get(strategy, {"CASH (현금)": 100.0})
    held = {t: w for t, w in held.items() if w > 0.01}
    pre_cap = dict(held)  # 상한 적용 전 합산 비중 (전략별 분해용)

    # 비중 상한이 켜져 있으면 백테스트와 동일하게 초과분을 현금으로
    cap_note = ""
    if cap_on:
        excess = 0.0
        capped = {}
        for t, w in held.items():
            if t == "CASH (현금)":
                continue
            if w > cap_pct:
                capped[t] = cap_pct
                excess += w - cap_pct
            else:
                capped[t] = w
        capped["CASH (현금)"] = held.get("CASH (현금)", 0.0) + excess
        held = {t: w for t, w in capped.items() if w > 0.01}
        if excess > 0.01:
            cap_note = f" · 비중 상한 {cap_pct:.0f}% 적용(초과분 {excess:.1f}%p 현금)"

    risky = [t for t in held if t != "CASH (현금)"]
    st.caption(
        f"보유 기준: {base_date.strftime('%Y-%m-%d')} 월말 확정 {label} 포트폴리오{cap_note} · "
        f"기준가: 같은 날 종가 · "
        f"가격은 5분마다 갱신"
    )

    if not risky:
        st.info(f"{period_word} {label} 포트폴리오는 전량 현금 보유라 월중 손실 위험이 없습니다.")
        return

    start = (base_date - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    px = get_intramonth_daily_prices(tuple(sorted(risky)), start)
    src_note = "야후 파이낸스 일별 종가(5분 캐시)"
    missing = [t for t in risky if px.empty or t not in px.columns or px[t].dropna().empty]
    if missing:
        # 실시간으로 못 받은 종목만 1시간 캐시된 일별 데이터로 대체 (나머지는 최신 데이터 유지)
        fb = {}
        for t in missing:
            if t in hist_prices:
                s_t = pd.Series(hist_prices[t]).copy()
                if getattr(s_t.index, "tz", None) is not None:
                    s_t.index = s_t.index.tz_localize(None)
                fb[t] = s_t
        if fb:
            fb_df = pd.DataFrame(fb)
            px = fb_df if px.empty else px.drop(columns=[c for c in fb if c in px.columns]).join(fb_df, how="outer")
        src_note += f" · {', '.join(missing)}는 1시간 캐시 데이터로 대체"
    # 확정됐어야 할 최신 종가가 일별 데이터에 없으면 보완 (클라우드 서버에서 최신 일봉이 늦게 오는 문제 대응)
    patch_note = ""
    if view_end is None and not px.empty:
        _exp0 = _expected_last_close_date()
        _need = [t for t in risky if t in px.columns and (px[t].dropna().empty or px[t].dropna().index.max() < _exp0)]
        if _need:
            _vals, _how = get_latest_close_patch(tuple(sorted(_need)), _exp0.strftime("%Y-%m-%d"))
            if _vals:
                if _exp0 not in px.index:
                    px.loc[_exp0] = np.nan
                for t, v in _vals.items():
                    px.loc[_exp0, t] = v
                patch_note = (f" · {_exp0.strftime('%m/%d')} 종가 보완: "
                              + ", ".join(f"{t}({_how[t]})" for t in _vals))
    src_note += patch_note
    raw_px = px.sort_index().copy()  # 확인용(앞 값 채우기 전 원본)
    px = px.sort_index().ffill()

    base_px = px[px.index <= base_date]
    month_px = px[px.index > base_date]
    if view_end is not None:
        month_px = month_px[month_px.index <= view_end]
    if base_px.empty:
        st.warning("기준일 종가를 찾지 못했습니다.")
        return
    if month_px.empty:
        st.info(f"{base_date.strftime('%Y-%m-%d')} 이후 아직 거래일 데이터가 없습니다. 첫 거래일 장 마감 뒤 다시 확인하세요.")
        return
    base_row = base_px.iloc[-1]

    # 데이터 신선도 확인: 확정됐어야 할 종가가 아직 없거나, 일부 종목만 늦은 경우 알림
    if view_end is None:
        _exp = _expected_last_close_date()
        _last = month_px.index.max()
        _lag = {t: raw_px[t].dropna().index.max() for t in risky if t in raw_px.columns and raw_px[t].notna().any()}
        _late = [t for t, d in _lag.items() if d < _last]
        if _last < _exp:
            st.warning(
                f"⏳ 야후 데이터에 아직 **{_exp.strftime('%m/%d')} 종가**가 없습니다 (현재 마지막 {_last.strftime('%m/%d')}). "
                "보통 미국 장 마감(한국 시간 새벽 5\\~6시) 뒤 1시간 안에 반영되지만, 늦어질 때가 있습니다. "
                "잠시 뒤 위 🔄 버튼으로 다시 받아 보세요."
            )
        if patch_note:
            st.caption("ℹ️ 야후 일별 데이터에 최신 종가가 아직 들어오지 않아 다른 경로로 보완했습니다" + patch_note
                       + ". 일별 데이터가 갱신되면 자동으로 원래 값으로 바뀝니다.")
        if _late:
            st.caption("⚠️ 마지막 날짜가 다른 종목보다 늦은 종목: " + ", ".join(f"{t}({_lag[t].strftime('%m/%d')})" for t in _late)
                       + " — 빠진 날은 직전 종가로 채워 계산했습니다.")

    # 3) 일별 누적 수익률 = Σ 비중 × (종가 / 기준가 − 1)  (백테스트 하드스탑과 동일)
    cum = pd.Series(0.0, index=month_px.index)
    contrib_rows = []
    rets = {}
    for t in risky:
        w = held[t] / 100.0
        b = base_row.get(t, np.nan)
        if t not in month_px.columns or pd.isna(b) or b == 0:
            continue
        t_ret = (month_px[t] / b - 1.0).fillna(0.0)
        rets[t] = t_ret
        cum = cum + w * t_ret
        last_px = month_px[t].dropna().iloc[-1] if month_px[t].notna().any() else np.nan
        contrib_rows.append({
            "자산 (Ticker)": t,
            "비중 (%)": round(held[t], 2),
            "월초 기준가 ($)": round(float(b), 2),
            "최근 종가 ($)": round(float(last_px), 2) if pd.notna(last_px) else None,
            "월초 대비 (%)": round(float(t_ret.iloc[-1] * 100), 2),
            "포트폴리오 기여 (%p)": round(float(w * t_ret.iloc[-1] * 100), 2),
        })
    if "CASH (현금)" in held:
        contrib_rows.append({
            "자산 (Ticker)": "CASH (현금)", "비중 (%)": round(held["CASH (현금)"], 2),
            "월초 기준가 ($)": None, "최근 종가 ($)": None,
            "월초 대비 (%)": 0.0, "포트폴리오 기여 (%p)": 0.0,
        })

    # 혼합전략: 전략 A·B·C별 기여로 분해 (각 전략 비중 × 1/3, 상한 적용 시 티커별 비례 축소)
    part_cum = {}
    if is_mix:
        for X in ("A", "B", "C"):
            c_x = pd.Series(0.0, index=month_px.index)
            for t, w_raw in parts.get(X, {}).items():
                if t == "CASH (현금)" or t not in rets:
                    continue
                scale = held.get(t, 0.0) / pre_cap[t] if (cap_on and pre_cap.get(t, 0.0) > 0) else 1.0
                c_x = c_x + (w_raw / 100.0) * (1.0 / 3.0) * scale * rets[t]
            part_cum[X] = c_x
        cum = part_cum["A"] + part_cum["B"] + part_cum["C"]  # 합계 = A + B + C

    cum_pct = cum * 100.0
    nav = 1.0 + cum
    daily_pct = (nav / nav.shift(1).fillna(1.0) - 1.0) * 100.0
    part_cum_pct, part_daily_pct = {}, {}
    if is_mix:
        prev_nav = nav.shift(1).fillna(1.0)
        for X, c_x in part_cum.items():
            part_cum_pct[X] = c_x * 100.0
            # 일간 기여 = 전략 누적 증가분 ÷ 전일 포트폴리오 가치 → 세 전략 합이 일간 합계와 정확히 일치
            part_daily_pct[X] = (c_x - c_x.shift(1).fillna(0.0)) / prev_nav * 100.0

    last_cum = float(cum_pct.iloc[-1])
    last_daily = float(daily_pct.iloc[-1])
    worst_cum = float(cum_pct.min())
    cards = [
        ("월초 대비 누적 (이번 달 복리)", last_cum, "전월 말 종가 대비"),
        (f"최근일 ({cum_pct.index[-1].strftime('%m/%d')}) 일간 수익률", last_daily, "전일 대비"),
        ("이번 달 최저 누적", worst_cum, "월중 가장 낮았던 누적"),
    ]
    hl_cards(cards)
    if is_mix:
        st.caption(
            f"월초 대비 누적 {last_cum:+.2f}% = "
            f"A {part_cum_pct['A'].iloc[-1]:+.2f}%p + B {part_cum_pct['B'].iloc[-1]:+.2f}%p + C {part_cum_pct['C'].iloc[-1]:+.2f}%p  ·  "
            f"최근일 {last_daily:+.2f}% = "
            f"A {part_daily_pct['A'].iloc[-1]:+.2f}%p + B {part_daily_pct['B'].iloc[-1]:+.2f}%p + C {part_daily_pct['C'].iloc[-1]:+.2f}%p"
        )


    df_days = pd.DataFrame({
        "날짜": cum_pct.index,
        "일간 수익률 (%)": daily_pct.values,
        "월초 대비 누적 (%)": cum_pct.values,
    })
    try:
        base = alt.Chart(df_days).encode(x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%m/%d")))
        if is_mix:
            df_long = pd.concat([
                pd.DataFrame({"날짜": cum_pct.index, "전략": f"전략 {X}", "일간 기여 (%p)": part_daily_pct[X].values})
                for X in ("A", "B", "C")
            ])
            bars = alt.Chart(df_long).mark_bar(opacity=0.6).encode(
                x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%m/%d")),
                y=alt.Y("sum(일간 기여 (%p)):Q", title="수익률 (%)"),
                color=alt.Color("전략:N", scale=alt.Scale(domain=["전략 A", "전략 B", "전략 C"], range=["#3b82f6", "#f59e0b", "#10b981"]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=[alt.Tooltip("날짜:T", format="%Y-%m-%d"), "전략:N", alt.Tooltip("일간 기여 (%p):Q", format=".2f")],
            )
        else:
            bars = base.mark_bar(opacity=0.45).encode(
                y=alt.Y("일간 수익률 (%):Q", title="수익률 (%)"),
                color=alt.condition("datum['일간 수익률 (%)'] >= 0", alt.value("#16a34a"), alt.value("#dc2626")),
                tooltip=[alt.Tooltip("날짜:T", format="%Y-%m-%d"), alt.Tooltip("일간 수익률 (%):Q", format=".2f")],
            )
        line = base.mark_line(point=True, color="#1e293b").encode(
            y="월초 대비 누적 (%):Q",
            tooltip=[alt.Tooltip("날짜:T", format="%Y-%m-%d"), alt.Tooltip("월초 대비 누적 (%):Q", format=".2f")],
        )
        zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(color="#94a3b8").encode(y="y:Q")
        layers = bars + line + zero
        st.altair_chart(layers.properties(height=260), use_container_width=True)
        if is_mix:
            st.caption("막대 = 일간 수익률의 전략별 기여(A·B·C 누적 막대, 합계 = 일간 합계), 선 = 월초 대비 누적 합계")
        else:
            st.caption("막대 = 일간 수익률, 선 = 월초 대비 누적 수익률")
    except Exception:
        st.line_chart(df_days.set_index("날짜")["월초 대비 누적 (%)"])

    if is_mix:
        # 괄호 안 = 전략 A·B·C의 기여도(%p). 세 값을 더하면 합계와 정확히 같음
        def _fmt_combo(total, a, b, c):
            total, a, b, c = [0.0 if abs(v) < 0.005 else v for v in (total, a, b, c)]  # "-0.00" 방지
            s_ = f"{a:.2f}"
            for v in (b, c):
                s_ += f"+{v:.2f}" if v >= 0 else f"{v:.2f}"
            return f"{total:.2f} ({s_})"

        df_days_view = pd.DataFrame({
            "날짜": cum_pct.index,
            "일간 수익률 (%) (A+B+C)": [
                _fmt_combo(daily_pct.iloc[i], part_daily_pct["A"].iloc[i], part_daily_pct["B"].iloc[i], part_daily_pct["C"].iloc[i])
                for i in range(len(cum_pct))
            ],
            "월초 대비 누적 (%) (A+B+C)": [
                _fmt_combo(cum_pct.iloc[i], part_cum_pct["A"].iloc[i], part_cum_pct["B"].iloc[i], part_cum_pct["C"].iloc[i])
                for i in range(len(cum_pct))
            ],
        }).sort_values("날짜", ascending=False)
    else:
        df_days_view = df_days.sort_values("날짜", ascending=False).copy()
    df_days_view["날짜"] = df_days_view["날짜"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        df_days_view.round(2), use_container_width=True, hide_index=True,
        height=(len(df_days_view) + 1) * 35 + 3,
    )
    if is_mix:
        st.caption(
            "※ 괄호 안은 전략 A·B·C가 혼합 포트폴리오 수익률에 기여한 값(%p)이며, 세 값을 더하면 앞의 합계와 같습니다"
            "(표시값은 소수 둘째 자리 반올림이라 0.01 차이가 날 수 있음). "
            "각 전략의 단독 수익률은 전략 A·B·C 탭에서 확인할 수 있습니다."
        )

    st.markdown("**종목별 월초 대비 수익률과 기여도**")
    df_contrib = pd.DataFrame(contrib_rows).sort_values("포트폴리오 기여 (%p)")
    st.dataframe(df_contrib, use_container_width=True, hide_index=True,
                 height=(len(df_contrib) + 1) * 35 + 3)
    if is_mix:
        st.caption("※ 일별 종가 기준입니다. 장중에는 최근일 값이 실시간 가격으로 계속 바뀌며, 규칙상 판정은 종가로 합니다. 월중 리밸런싱이 없는 매수 후 보유 가정이며, 슬리피지·거래비용·세금은 반영되지 않았습니다.")
    else:
        st.caption("※ 일별 종가 기준입니다. 장중에는 최근일 값이 실시간 가격으로 계속 바뀝니다. 월중 리밸런싱이 없는 매수 후 보유 가정이며, 슬리피지·거래비용·세금은 반영되지 않았습니다.")

    with st.expander("🔍 데이터 확인 — 계산에 쓴 종목별 일별 종가 (원본)", expanded=False):
        _show = raw_px[[t for t in risky if t in raw_px.columns]]
        _show = _show[_show.index >= base_px.index[-1]]
        if view_end is not None:
            _show = _show[_show.index <= view_end]
        _show = _show.sort_index(ascending=False).round(2)
        _show.index = [d.strftime("%Y-%m-%d") + (" (기준일)" if d == base_px.index[-1] else "") for d in _show.index]
        st.dataframe(_show.astype(object).where(_show.notna(), "없음"), use_container_width=True,
                     height=(len(_show) + 1) * 35 + 3)
        st.caption(f"출처: {src_note}. '없음'은 야후가 그날 값을 주지 않은 것으로, 계산에서는 직전 종가로 채웁니다. "
                   "숫자가 이상해 보이면 야후 파이낸스 사이트의 Historical Data와 비교해 보세요.")


import html as _html

# 티커 -> (짧은 한글명, 간략 설명). 표에서 티커 옆에 한글명을 보여주고, 마우스를 올리면 설명이 나옵니다.
TICKER_INFO = {
    "TIP": ("물가연동채", "iShares TIPS Bond · 원금이 물가상승률에 연동되는 미국 물가연동국채(TIPS)"),
    "SPY": ("S&P500", "SPDR S&P 500 · 미국 대형주 500개 지수 추종"),
    "QQQ": ("나스닥100", "Invesco QQQ · 나스닥 상위 100개 비금융 대형주(기술주 중심) 추종"),
    "QQQM": ("나스닥100", "Invesco NASDAQ 100 · QQQ와 같은 지수를 추종하며 보수가 더 낮은 ETF"),
    "FEZ": ("유로존50", "SPDR EURO STOXX 50 · 유로존 대형주 50개 추종"),
    "GLD": ("금", "SPDR Gold Shares · 금 현물 가격 추종"),
    "IBB": ("바이오", "iShares Biotechnology · 미국 바이오테크 기업 지수 추종"),
    "SMH": ("반도체", "VanEck Semiconductor · 미국 반도체 대형주 추종"),
    "EEM": ("신흥국", "iShares MSCI Emerging Markets · 신흥국 주식 시장 추종"),
    "XLK": ("기술주", "Technology Select Sector SPDR · S&P500 내 정보기술 섹터"),
    "LIT": ("리튬·배터리", "Global X Lithium & Battery Tech · 리튬 채굴·2차전지 관련 기업"),
    "XLE": ("에너지", "Energy Select Sector SPDR · S&P500 내 에너지 섹터(석유·가스)"),
    "UBT": ("장기국채 2배", "ProShares Ultra 20+ Year Treasury · 미국 20년 이상 장기국채 일간 2배 레버리지"),
    "XLV": ("헬스케어", "Health Care Select Sector SPDR · S&P500 내 헬스케어 섹터"),
    "QTUM": ("양자컴퓨팅", "Defiance Quantum ETF · 양자컴퓨팅·머신러닝 관련 기업"),
    "BIL": ("초단기국채", "SPDR 1-3 Month T-Bill · 만기 1~3개월 미국 단기국채, 현금에 가까운 자산"),
    "IEF": ("중기국채", "iShares 7-10 Year Treasury · 만기 7~10년 미국 중기국채"),
    "AGG": ("종합채권", "iShares Core US Aggregate Bond · 미국 국채·회사채·MBS 등 종합 채권"),
    "HYG": ("하이일드채", "iShares iBoxx High Yield Corporate Bond · 신용등급이 낮은 고수익 회사채"),
    "TBF": ("장기국채 인버스", "ProShares Short 20+ Year Treasury · 20년 이상 장기국채와 반대로 움직이는 -1배 인버스. 금리 상승 시 이익"),
    "TYD": ("중기국채 3배", "Direxion 7-10 Year Treasury Bull 3X · 만기 7~10년 미국 국채 일간 3배 레버리지"),
    "UPRO": ("S&P500 3배", "ProShares UltraPro S&P500 · S&P500 일간 3배 레버리지"),
    "VNQ": ("미국 리츠", "Vanguard Real Estate · 미국 상장 부동산투자회사(리츠)"),
    "DOG": ("다우 인버스", "ProShares Short Dow30 · 다우존스30 지수와 반대로 움직이는 -1배 인버스"),
    "RWM": ("러셀2000 인버스", "ProShares Short Russell2000 · 미국 소형주(러셀2000)와 반대로 움직이는 -1배 인버스"),
    "FDN": ("인터넷", "First Trust Dow Jones Internet · 미국 인터넷 기업"),
    "IGV": ("소프트웨어", "iShares Expanded Tech-Software · 미국 소프트웨어 기업"),
    "XLU": ("유틸리티", "Utilities Select Sector SPDR · S&P500 내 전력·가스 등 유틸리티 섹터"),
    "PDBC": ("원자재", "Invesco Optimum Yield Diversified Commodity · 에너지·금속·농산물 등 다변화 원자재 선물"),
    "OILK": ("원유", "ProShares K-1 Free Crude Oil Strategy · 원유 선물 추종(K-1 세무서류 없음)"),
    "SHY": ("단기국채", "iShares 1-3 Year Treasury · 만기 1~3년 미국 단기국채"),
    "TLT": ("장기국채", "iShares 20+ Year Treasury · 만기 20년 이상 미국 장기국채"),
    "SCHD": ("배당성장", "Schwab US Dividend Equity · 배당 지속성이 높은 미국 배당성장주"),
    "JEPI": ("커버드콜", "JPMorgan Equity Premium Income · S&P500 주식 + 옵션 매도로 월 배당을 높인 ETF"),
    "TQQQ": ("나스닥100 3배", "ProShares UltraPro QQQ · 나스닥100 일간 3배 레버리지"),
    "SOXL": ("반도체 3배", "Direxion Semiconductor Bull 3X · 반도체 지수 일간 3배 레버리지"),
    "DIA": ("다우30", "SPDR Dow Jones Industrial Average · 다우존스 산업평균 30개 종목 추종"),
    "IWM": ("러셀2000", "iShares Russell 2000 · 미국 소형주 2000개 추종"),
    "XLF": ("금융", "Financial Select Sector SPDR · S&P500 내 금융 섹터"),
}


# S&P500 대형주 중 나스닥100에 없는 종목의 한글명·설명 (TICKER_INFO에 없는 것만 채움)
SP500_KR_INFO = {
    "BRK-B": ("버크셔 해서웨이", "Berkshire Hathaway · 워런 버핏의 복합 지주사(보험·철도·에너지·투자)"),
    "LLY": ("일라이 릴리", "Eli Lilly · 비만·당뇨 치료제(마운자로·젭바운드) 중심 제약사"),
    "JPM": ("JP모건", "JPMorgan Chase · 미국 최대 은행(상업·투자은행)"),
    "V": ("비자", "Visa · 세계 최대 카드 결제 네트워크"),
    "MA": ("마스터카드", "Mastercard · 글로벌 카드 결제 네트워크"),
    "XOM": ("엑슨모빌", "Exxon Mobil · 미국 최대 종합 석유회사"),
    "CVX": ("셰브론", "Chevron · 종합 석유·가스 회사"),
    "COP": ("코노코필립스", "ConocoPhillips · 석유·가스 탐사·생산"),
    "UNH": ("유나이티드헬스", "UnitedHealth · 미국 최대 건강보험·헬스케어 서비스"),
    "ORCL": ("오라클", "Oracle · 데이터베이스·클라우드 인프라 소프트웨어"),
    "HD": ("홈디포", "Home Depot · 주택 개량·건자재 소매 1위"),
    "LOW": ("로우스", "Lowe's · 주택 개량·건자재 소매"),
    "PG": ("P&G", "Procter & Gamble · 생활용품(세제·면도기·기저귀)"),
    "JNJ": ("존슨앤드존슨", "Johnson & Johnson · 제약·의료기기"),
    "BAC": ("뱅크오브아메리카", "Bank of America · 미국 2위 은행"),
    "WFC": ("웰스파고", "Wells Fargo · 미국 대형 상업은행"),
    "C": ("씨티그룹", "Citigroup · 글로벌 은행"),
    "GS": ("골드만삭스", "Goldman Sachs · 투자은행·자산운용"),
    "MS": ("모건스탠리", "Morgan Stanley · 투자은행·자산관리"),
    "SCHW": ("찰스 슈왑", "Charles Schwab · 온라인 증권·자산관리"),
    "BLK": ("블랙록", "BlackRock · 세계 최대 자산운용사(iShares ETF)"),
    "BX": ("블랙스톤", "Blackstone · 사모펀드·부동산 대체투자 운용"),
    "KKR": ("KKR", "KKR · 사모펀드·대체투자 운용"),
    "AXP": ("아메리칸 익스프레스", "American Express · 카드 발급·결제"),
    "COF": ("캐피털원", "Capital One · 카드·소비자금융 은행"),
    "SPGI": ("S&P 글로벌", "S&P Global · 신용평가·지수(S&P500)·금융정보"),
    "MCO": ("무디스", "Moody's · 신용평가·금융정보"),
    "ICE": ("ICE", "Intercontinental Exchange · 뉴욕증권거래소 운영사"),
    "CME": ("CME그룹", "CME Group · 세계 최대 선물거래소"),
    "PGR": ("프로그레시브", "Progressive · 자동차 손해보험"),
    "CB": ("처브", "Chubb · 글로벌 손해보험"),
    "MMC": ("마시 맥레넌", "Marsh McLennan · 보험중개·컨설팅"),
    "ABBV": ("애브비", "AbbVie · 면역질환(휴미라·스카이리치) 제약사"),
    "MRK": ("머크", "Merck · 항암제(키트루다) 중심 제약사"),
    "PFE": ("화이자", "Pfizer · 대형 제약사"),
    "ABT": ("애보트", "Abbott · 의료기기·진단·영양식"),
    "TMO": ("써모피셔", "Thermo Fisher · 생명과학 연구장비·서비스"),
    "DHR": ("다나허", "Danaher · 생명과학·진단 장비"),
    "BSX": ("보스턴 사이언티픽", "Boston Scientific · 심혈관 의료기기"),
    "SYK": ("스트라이커", "Stryker · 정형외과·수술 의료기기"),
    "ELV": ("엘레반스", "Elevance Health · 건강보험"),
    "CI": ("시그나", "Cigna · 건강보험·약제 관리"),
    "CVS": ("CVS헬스", "CVS Health · 약국·건강보험(애트나)"),
    "HCA": ("HCA헬스케어", "HCA Healthcare · 미국 최대 병원 운영사"),
    "MCK": ("맥케슨", "McKesson · 의약품 유통"),
    "KO": ("코카콜라", "Coca-Cola · 음료"),
    "PM": ("필립모리스", "Philip Morris · 담배·전자담배(아이코스)"),
    "MO": ("알트리아", "Altria · 미국 담배(말보로)"),
    "WMT": ("월마트", "Walmart · 세계 최대 소매 유통"),
    "TGT": ("타깃", "Target · 종합 할인점"),
    "TJX": ("TJX", "TJX · 할인 의류·잡화(TJ맥스)"),
    "NKE": ("나이키", "Nike · 스포츠 의류·신발"),
    "MCD": ("맥도날드", "McDonald's · 패스트푸드"),
    "CMG": ("치폴레", "Chipotle · 멕시칸 패스트캐주얼"),
    "DIS": ("디즈니", "Walt Disney · 미디어·테마파크·스트리밍"),
    "T": ("AT&T", "AT&T · 통신(무선·유선)"),
    "VZ": ("버라이즌", "Verizon · 미국 최대 무선통신"),
    "IBM": ("IBM", "IBM · 하이브리드 클라우드·AI·컨설팅"),
    "CRM": ("세일즈포스", "Salesforce · 고객관리(CRM) 클라우드 소프트웨어"),
    "NOW": ("서비스나우", "ServiceNow · 기업 업무 자동화 클라우드"),
    "ACN": ("액센츄어", "Accenture · IT 컨설팅·아웃소싱"),
    "ANET": ("아리스타", "Arista Networks · 데이터센터 네트워크 스위치"),
    "DELL": ("델", "Dell Technologies · PC·서버·스토리지"),
    "HPE": ("HPE", "Hewlett Packard Enterprise · 서버·네트워크"),
    "SMCI": ("슈퍼마이크로", "Super Micro Computer · AI 서버"),
    "APH": ("암페놀", "Amphenol · 커넥터·센서 부품"),
    "UBER": ("우버", "Uber · 차량 호출·음식 배달 플랫폼"),
    "GE": ("GE에어로스페이스", "GE Aerospace · 항공기 엔진"),
    "GEV": ("GE버노바", "GE Vernova · 발전 설비·전력망 장비"),
    "RTX": ("RTX", "RTX · 항공 엔진(프랫앤휘트니)·미사일 방산"),
    "BA": ("보잉", "Boeing · 민항기·방산"),
    "LMT": ("록히드마틴", "Lockheed Martin · 방산(F-35 전투기)"),
    "NOC": ("노스롭그루먼", "Northrop Grumman · 방산·우주"),
    "GD": ("제너럴다이내믹스", "General Dynamics · 방산·비즈니스 제트기"),
    "CAT": ("캐터필러", "Caterpillar · 건설·광산 장비"),
    "DE": ("디어", "Deere · 농기계(존디어)"),
    "ETN": ("이튼", "Eaton · 전력 관리 장비"),
    "VRT": ("버티브", "Vertiv · 데이터센터 전력·냉각 장비"),
    "UNP": ("유니언퍼시픽", "Union Pacific · 미국 철도 화물"),
    "UPS": ("UPS", "UPS · 택배·물류"),
    "FDX": ("페덱스", "FedEx · 특송·물류"),
    "WM": ("웨이스트매니지먼트", "Waste Management · 폐기물 처리"),
    "NEE": ("넥스트에라", "NextEra Energy · 전력·신재생 발전"),
    "SO": ("서던컴퍼니", "Southern Company · 전력 유틸리티"),
    "DUK": ("듀크에너지", "Duke Energy · 전력 유틸리티"),
    "PLD": ("프롤로지스", "Prologis · 물류창고 리츠"),
    "AMT": ("아메리칸타워", "American Tower · 통신탑 리츠"),
    "EQIX": ("에퀴닉스", "Equinix · 데이터센터 리츠"),
    "SHW": ("셔윈윌리엄스", "Sherwin-Williams · 페인트"),
    "FCX": ("프리포트맥모란", "Freeport-McMoRan · 구리·금 광산"),
    "NEM": ("뉴몬트", "Newmont · 세계 최대 금광 회사"),
    "MPC": ("마라톤페트롤리엄", "Marathon Petroleum · 정유"),
    "PSX": ("필립스66", "Phillips 66 · 정유·화학"),
    "SLB": ("슐럼버거", "SLB · 유전 서비스"),
    "F": ("포드", "Ford · 자동차"),
    "GM": ("GM", "General Motors · 자동차"),
    "RCL": ("로열캐리비안", "Royal Caribbean · 크루즈"),
    "HLT": ("힐튼", "Hilton · 호텔"),
}
# 한글 설명이 없는 종목은 위키피디아 S&P500 표의 영문 회사명·업종으로 대신 표시 (S&P500 불러올 때 채워짐)
TICKER_EXTRA_NAMES = {}


def tab_toggle(label, key, open_default=False):
    """켜기/끄기 단추. ..."""
    return st.radio(label, ["접기", "펼치기"], index=1 if open_default else 0, horizontal=True, key=key) == "펼치기"

def cap_on_setting():
    """'비중 상한' 설정값 (라디오 '켜기'면 True). 여러 곳에서 같은 값을 읽음."""
    return st.session_state.get("apply_cap_mix_r", "끄기") == "켜기"


def ticker_cell_html(t, show_name=True):
    """티커 + (한글명) + 마우스 오버/터치 설명(data-tip)."""
    info = TICKER_INFO.get(str(t))
    if not info and str(t) in TICKER_EXTRA_NAMES:
        _en, _sec = TICKER_EXTRA_NAMES[str(t)]
        tip = _html.escape(f"{t} · {_en}\n{_sec}", quote=True).replace("\n", "&#10;")
        name = f'<span class="tk-name">({_html.escape(_en)})</span>' if show_name else ""
        return f'<span class="tk gl" data-tip="{tip}">{_html.escape(str(t))}</span>{name}'
    if not info:
        return _html.escape(str(t))
    short, desc = info
    tip = _html.escape(f"{t} · {short}\n{desc}", quote=True).replace("\n", "&#10;")
    name = f'<span class="tk-name">({_html.escape(short)})</span>' if show_name else ""
    return f'<span class="tk gl" data-tip="{tip}">{_html.escape(str(t))}</span>{name}'


# ===================== 용어 설명 (마우스 오버 / 폰 터치) =====================
import re as _re
from streamlit.delta_generator import DeltaGenerator as _DG

GL_TICKERS_IN_TEXT = True  # 본문 속 티커에도 설명을 붙이려면 True, 끄려면 False

_GL_DEFS = [
    (("^TNX", "TNX"), "미국 10년물 국채 금리. 주식 가치평가와 기업 차입금리의 기준이 되는 무위험 수익률 지표"),
    (("^TYX", "TYX"), "미국 30년물 국채 금리. 초장기 인플레이션·경제성장 기대를 반영하는 장기금리 지표"),
    (("USDKRW=X",), "달러/원 환율. 해외 ETF 환전 매수와 환노출 성과에 직접 영향"),
    (("DX-Y.NYB",), "달러 인덱스. 유로·엔·파운드 등 주요 6개 통화 대비 달러의 상대 가치"),
    (("CL=F",), "WTI 원유 선물 가격. 국제 유가와 생산자 물가 압력을 나타냄"),
    (("^VIX", "VIX"), "변동성 지수(공포 지수). S&P500 옵션 가격으로 산출한 시장의 기대 변동성"),
    (("SPY 배당수익률", "배당수익률"), "S&P500의 주가 대비 배당금 비율. 전략 C에서 과열·저평가를 판단하는 카나리아 지표(1.33% 기준선)"),
    (("카나리아 신호", "카나리아"), "탄광의 카나리아처럼 하락 위험을 미리 알려주는 선행 경고 지표 (TIP 이동평균·모멘텀, S&P500 배당수익률)"),
    (("모멘텀 스코어",), "과거 1·3·6·12개월 수익률로 계산한 추세 강도. 최근 기간에 가중치를 주기도 함"),
    (("NAV",), "순자산가치. 시작 시점을 100으로 두고 누적 복리 수익을 반영한 자산 곡선 값"),
    (("CAGR",), "연평균 복리 수익률. 전체 기간 성과를 매년 일정 비율로 복리 성장한 것으로 환산한 값"),
    (("MDD",), "최대 낙폭. 직전 고점 대비 가장 크게 떨어진 하락률 = 감내해야 할 최대 손실 위험"),
    (("샤프 지수",), "변동성(위험) 한 단위당 얻은 초과수익. 높을수록 위험 대비 효율이 좋음"),
    (("소티노 지수",), "손실이 난 '하방 변동성'만 위험으로 보고 계산한 위험조정 수익 지표"),
    (("UPI 지수",), "Ulcer Performance Index. 낙폭의 깊이와 지속기간을 반영한 위험 대비 수익률"),
    (("연간 턴오버", "턴오버"), "1년 동안 포트폴리오 자산이 교체된 비중의 합(회전율). 높을수록 거래비용·슬리피지 증가"),
    (("비중 상한",), "여러 전략이 같은 자산을 고를 때 한 자산에 쏠리지 않게 정한 한도(예: 35%). 초과분은 현금 전환"),
    (("월중 하드스탑", "하드스탑"), "월말 리밸런싱을 기다리지 않고, 월중 누적 손실이 기준(예: -10%)에 닿으면 즉시 전량 현금화하는 규칙"),
    (("연 변동성",), "수익률의 표준편차를 연 단위로 환산한 값. 클수록 등락이 심함"),
    (("표준편차",), "수익률이 평균에서 흩어진 정도. 클수록 변동이 큼"),
    (("YTD",), "Year-To-Date. 올해 1월 1일부터 현재까지의 누적 수익률"),
    (("슬리피지",), "주문 예상가와 실제 체결가의 차이로 생기는 숨은 거래비용"),
    (("대공황",), "1929년 미국 증시 폭락으로 시작된 세계적 경제 불황. S&P500이 1929~1932년 약 80%대 하락"),
    (("블랙먼데이",), "1987년 10월 19일 미국 증시가 하루에 약 20% 폭락한 사건. 프로그램 매매와 공포 매도가 겹침"),
    (("닷컴버블",), "1990년대 후반 인터넷 기업 주가 거품이 2000년 3월부터 꺼진 폭락. 나스닥이 2002년까지 약 78% 하락"),
    (("글로벌 금융위기", "금융위기"), "2007~2009년 미국 서브프라임 모기지 부실에서 시작된 세계 금융 위기. S&P500이 약 57% 하락"),
    (("긴축 발작",), "2022년 연준의 급격한 금리 인상으로 주식·채권이 동반 하락한 시기"),
    (("전고점 회복",), "하락 뒤 주가가 직전 최고점을 다시 넘는 데 걸린 시간. 길수록 '물린 기간'이 깁니다"),
]
GLOSSARY = {}
for _keys, _d in _GL_DEFS:
    for _k in _keys:
        GLOSSARY[_k] = _d
if GL_TICKERS_IN_TEXT:
    for _t, (_s, _d) in TICKER_INFO.items():
        GLOSSARY.setdefault(_t, f"{_t} ({_s}) — {_d}".replace("|", "/"))
_GL_RE = _re.compile(
    r"(?<![A-Za-z0-9_^])(?:" + "|".join(_re.escape(k) for k in sorted(GLOSSARY, key=len, reverse=True)) + r")(?![A-Za-z0-9_])"
)
_GL_SPLIT = _re.compile(r"(</?[A-Za-z][^>]*>|`[^`]*`|\$\$.+?\$\$|\$[^$\n]+\$)", _re.S)
_GL_MATH = _re.compile(r"^(\$\$.+\$\$|\$[^$\n]+\$)$", _re.S)  # 수식($...$) 안에는 설명 태그를 넣지 않음 (수식이 깨짐)


def glossify(text):
    """글 속 용어를 <span class="gl" data-tip=...>로 감쌉니다 (태그·코드·스타일 블록 안은 건드리지 않음)."""
    if "<style" in text or "```" in text:
        return text
    out, skip = [], False
    for part in _GL_SPLIT.split(text):
        if _GL_MATH.match(part):
            out.append(part)
        elif part.startswith("<") or part.startswith("`"):
            if _re.search(r'class="[^"]*\bgl\b', part):
                skip = True
            elif part == "</span>" and skip:
                skip = False
            out.append(part)
        elif skip:
            out.append(part)
        else:
            out.append(_GL_RE.sub(
                lambda m: f'<span class="gl" data-tip="{_html.escape(GLOSSARY[m.group(0)], quote=True)}">{m.group(0)}</span>', part))
    return "".join(out)


def _gl_patch(owner, name, handler):
    cur = getattr(owner, name)
    orig = getattr(cur, "_gl_orig", cur)  # 재실행해도 겹겹이 감싸지지 않도록 원본 기준으로 교체

    def f(*args, **k):
        i = 1 if args and isinstance(args[0], _DG) else 0
        return handler(orig, args, k, i)
    f._gl_orig = orig
    setattr(owner, name, f)


def _h_text(orig, args, k, i):
    if len(args) > i and isinstance(args[i], str):
        new = glossify(args[i])
        if new != args[i]:
            args = args[:i] + (new,) + args[i + 1:]
            k["unsafe_allow_html"] = True
    return orig(*args, **k)


def _h_metric(orig, args, k, i):
    """st.metric 라벨에 용어가 있으면 ⓘ 도움말 아이콘(터치 가능)을 자동으로 붙입니다."""
    if "help" not in k and i < len(args) <= i + 4 and isinstance(args[i], str):
        seen = []
        for m in _GL_RE.finditer(args[i]):
            if m.group(0) not in seen:
                seen.append(m.group(0))
        if seen:
            k["help"] = "\n\n".join(f"**{x}** — {GLOSSARY[x]}" for x in seen)
    return orig(*args, **k)


for _o in (st, _DG):
    for _n, _h in (("markdown", _h_text), ("caption", _h_text), ("metric", _h_metric)):
        _gl_patch(_o, _n, _h)

st.markdown("<style>.gl{border-bottom:1px dotted #64748b;cursor:help;-webkit-tap-highlight-color:transparent}</style>",
            unsafe_allow_html=True)


# ===================== 핵심 수치 강조 (비중 칩 · 일별/월별 복리 수익 카드) =====================
st.markdown("""<style>
.hl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:0.3rem 0 0.7rem}
.hl-card{border-radius:12px;padding:9px 12px;border:1px solid #bfdbfe;background:#f5f9ff;color:#2563eb}
.hl-card.pos{border-color:#a7f3d0;background:#f3fcf8;color:#059669}
.hl-card.neg{border-color:#fecaca;background:#fff6f6;color:#dc2626}
.hl-card .hl-l{font-size:0.78rem;font-weight:700;color:#334155;word-break:keep-all}
.hl-card .hl-v{font-size:1.4rem;font-weight:700;line-height:1.25}
.hl-card .hl-s{font-size:0.72rem;color:#64748b;word-break:keep-all}
.al-wrap{display:flex;flex-wrap:wrap;gap:8px;margin:0.3rem 0 0.6rem}
.al-chip{flex:1 1 140px;border-radius:12px;padding:10px 12px;background:#fff;border:1px solid #e2e8f0;border-left:5px solid #3b82f6;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.al-chip .al-t{font-size:1.05rem;font-weight:700;color:#0f172a}
.al-chip .al-n{font-size:0.78rem;color:#64748b;margin-left:4px}
.al-chip .al-w{font-size:1.45rem;font-weight:700;line-height:1.2;color:#0f172a}
</style>""", unsafe_allow_html=True)


def hl_cards(items):
    """items: [(라벨, 숫자 또는 문자열, 부가설명, 'auto'|'pos'|'neg'|'neutral'), ...] -> 큼직한 강조 카드."""
    html = ""
    for label, val, sub, *rest in items:
        tone = rest[0] if rest else "auto"
        if isinstance(val, (int, float, np.floating)):
            if tone == "auto":
                tone = "pos" if val > 0 else ("neg" if val < 0 else "neutral")
            val = f"{val:.2f}%" if label.startswith("연환산") else f"{val:+.2f}%"
        cls = {"pos": " pos", "neg": " neg"}.get(tone, "")
        html += (f'<div class="hl-card{cls}"><div class="hl-l">{_html.escape(label)}</div>'
                 f'<div class="hl-v">{_html.escape(str(val))}</div><div class="hl-s">{_html.escape(sub)}</div></div>')
    st.markdown(f'<div class="hl-grid">{html}</div>', unsafe_allow_html=True)


def monthly_compound_cards(bt):
    """월별 수익률 위에 이번 달 / 올해(YTD) / 최근 12개월 복리 수익을 크게 표시."""
    try:
        r = bt["monthly_return"].astype(float).values / 100.0
        d = pd.to_datetime(bt["date"])
        last = d.iloc[-1]
        ytd = (np.prod(1 + r[(d.dt.year == last.year).values]) - 1) * 100
        items = [(f"이번 달 ({last.strftime('%Y-%m')})", r[-1] * 100, "월 수익률"),
                 ("올해 복리 수익 (YTD)", ytd, "월 수익률을 연초부터 복리로 누적")]
        if len(r) >= 12:
            items.append(("최근 12개월 복리", (np.prod(1 + r[-12:]) - 1) * 100, "최근 1년 복리 누적"))
        hl_cards(items)
    except Exception:
        pass


def render_alloc_chips(df, ticker_col="자산군 (Ticker)", weight_col="배분 비중 (%)",
                       colors=("#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316")):
    """포트폴리오 자산군과 비중을 도넛 색과 같은 색의 큰 칩으로 강조."""
    chips = ""
    for i, (_, r) in enumerate(df.iterrows()):
        try:
            w = f"{float(r[weight_col]):,.2f}%"
        except Exception:
            w = str(r[weight_col])
        chips += (f'<div class="al-chip" style="border-left-color:{colors[i % len(colors)]}">'
                  f'<div><span class="al-t">{ticker_cell_html(r[ticker_col], show_name=False)}</span></div>'
                  f'<div class="al-w">{_html.escape(w)}</div></div>')
    st.markdown(f'<div class="al-wrap">{chips}</div>', unsafe_allow_html=True)


# ===================== 장기 낙폭 (SPY·QQQ 등) 헬퍼 =====================
LONG_EVENTS = [
    ("대공황", "1929 대공황", "1929-09-01", "1932-12-31"),
    ("오일쇼크", "1973-74 오일쇼크 약세장", "1973-01-01", "1974-12-31"),
    ("블랙먼데이", "1987 블랙먼데이", "1987-08-01", "1987-12-31"),
    ("LTCM", "1998 LTCM·러시아 위기", "1998-07-01", "1998-10-31"),
    ("닷컴", "2000 닷컴버블 붕괴", "2000-03-01", "2002-12-31"),
    ("금융위기", "2007-09 글로벌 금융위기", "2007-10-01", "2009-04-30"),
    ("유럽위기", "2011 美 신용등급 강등·유럽 재정위기", "2011-04-01", "2011-10-31"),
    ("중국쇼크", "2015-16 중국 쇼크·유가 급락", "2015-05-01", "2016-02-29"),
    ("2018 Q4", "2018 4분기 긴축·무역분쟁", "2018-09-01", "2018-12-31"),
    ("코로나", "2020 코로나 팬데믹", "2020-02-01", "2020-04-30"),
    ("러우전쟁", "2022 러시아-우크라이나 전쟁", "2022-02-01", "2022-03-31"),
    ("2022 긴축", "2022 긴축 발작 (금리 인상기)", "2022-01-01", "2022-12-31"),
    ("엔캐리", "2024 엔캐리 청산·AI 주가 조정", "2024-07-01", "2024-08-31"),
    ("관세쇼크", "2025 美 관세 쇼크", "2025-02-01", "2025-05-31"),
    ("이란전쟁", "2026 미국-이란 전쟁·유가 급등", "2026-01-01", "2026-05-31"),
]


# 포트폴리오 드로우다운 Top 10 표의 '주요 이슈' 열: 구간(시작~종료월)과 기간이 겹치는 이슈를 보여줍니다.
# 장기 낙폭 탭의 LONG_EVENTS + 아래 보조 이슈(해당 표에만 사용). 겹치는 이슈가 없으면 '-'.
TOP10_EXTRA_ISSUES = [
    ("2018 변동성 쇼크", "2018 2월 변동성 쇼크·무역분쟁", "2018-02-01", "2018-04-30"),
    ("2019 무역전쟁", "2019 5월 미중 무역전쟁 격화", "2019-05-01", "2019-06-30"),
    ("2020 기술주 조정", "2020 9월 기술주 조정", "2020-09-01", "2020-10-31"),
    ("오미크론·테이퍼링", "2021 11월 오미크론·연준 긴축 전환", "2021-11-01", "2021-12-31"),
    ("금리 재상승·중동 긴장", "2024 4월 금리 재상승·중동 긴장", "2024-04-01", "2024-04-30"),
]


def issues_for_period(start, end):
    """start/end: 'YYYY/MM' 문자열 또는 Timestamp. 구간 안(시작월 1일~종료월 말일)에 걸치는 이슈 이름을 ' · '로 연결."""
    def _ts(x):
        return pd.Timestamp(str(x).replace("/", "-") + "-01") if isinstance(x, str) else pd.Timestamp(x)
    s0 = _ts(start).to_period("M").start_time
    e1 = _ts(end).to_period("M").end_time
    names = []
    for short, _full, a, b in list(LONG_EVENTS) + TOP10_EXTRA_ISSUES:
        if pd.Timestamp(a) <= e1 and pd.Timestamp(b) >= s0 and short not in names:
            names.append(short)
    return " · ".join(names) if names else "-"



@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_long_history(symbols, start):
    """일별 종가(배당·분할 반영) 장기 시계열. symbols는 tuple. {심볼: Series}"""
    out = {}
    for sym in symbols:
        try:
            df = yf.download(sym, start=start, interval="1d", progress=False, auto_adjust=True)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        close = close[close > 0].astype(float)
        if len(close) > 50:
            out[sym] = close
    return out


def _fmt_dur(days):
    if days is None:
        return "-"
    if days >= 365:
        return f"{days / 365.25:.1f}년"
    if days >= 45:
        return f"{days / 30.44:.0f}개월"
    return f"{int(days)}일"


def dd_episodes(px, min_depth=-2.0):
    """고점 → 저점 → (전고점 회복) 낙폭 구간 목록.
    가장 깊은 낙폭을 찾은 뒤, 그 '앞 구간'·'저점~회복 사이 구간'·'회복 이후 구간'을 다시 따로 탐색합니다.
    그래서 전고점을 오래 못 넘은 기간 안에 있던 별도 폭락(예: 닷컴 회복 구간 중 금융위기)도 독립 구간으로 잡힙니다."""
    vals, idx = px.values, px.index
    n = len(vals)
    out, stack = [], [(0, n)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 3:
            continue
        seg = vals[lo:hi]
        dd = seg / np.maximum.accumulate(seg) - 1
        k = int(np.argmin(dd))
        if dd[k] * 100 > min_depth:
            continue
        t = lo + k
        pk = lo + int(np.argmax(seg[:k + 1]))
        hit = np.nonzero(vals[t + 1:] >= vals[pk])[0]
        r = (t + 1 + int(hit[0])) if len(hit) else None
        out.append({"peak": idx[pk], "trough": idx[t], "recovery": (idx[r] if r is not None else None),
                    "depth": float(dd[k] * 100)})
        stack.append((lo, pk + 1))                           # 고점 이전 구간
        stack.append((t, (r + 1) if r is not None else n))   # 저점 ~ 회복 사이 구간
        if r is not None and r < hi - 1:
            stack.append((r, hi))                            # 회복 이후 구간
    return out


def event_stats(px, start, end):
    """이슈 기간 안에서의 고점→저점 낙폭, 전고점 회복, 저점 후 1년 수익률. 데이터가 없으면 None."""
    s0, e0 = pd.Timestamp(start), pd.Timestamp(end)
    w = px[(px.index >= s0) & (px.index <= e0)]
    if len(w) < 5 or (w.index[0] - s0).days > 45:
        return None
    dd = w / w.cummax() - 1
    t = dd.idxmin()
    depth = float(dd.min() * 100)
    if depth > -3:
        return None
    p = w.loc[:t].idxmax()
    after = px.loc[t:]
    rec = after[after >= px.loc[p]]
    j = px.index.get_loc(t)
    rebound = float((px.iloc[j + 252] / px.iloc[j] - 1) * 100) if j + 252 < len(px) else None
    return {"peak": p, "trough": t, "depth": depth,
            "recovery": (rec.index[0] if len(rec) else None), "rebound": rebound}


NDX_INFO = {
    "ADBE": ("어도비", "Adobe · 포토샵·PDF 등 크리에이티브·문서 소프트웨어"),
    "AMD": ("AMD", "Advanced Micro Devices · CPU·GPU·AI 가속기 반도체"),
    "ABNB": ("에어비앤비", "Airbnb · 숙박 공유 플랫폼"),
    "ALNY": ("알닐람", "Alnylam Pharmaceuticals · RNA 간섭(RNAi) 치료제 바이오텍"),
    "GOOGL": ("알파벳A", "Alphabet Class A · 구글·유튜브·클라우드 모회사(의결권 주식)"),
    "GOOG": ("알파벳C", "Alphabet Class C · 같은 회사의 무의결권 주식"),
    "AMZN": ("아마존", "Amazon · 전자상거래와 AWS 클라우드"),
    "AEP": ("아메리칸일렉트릭", "American Electric Power · 미국 전력 유틸리티"),
    "AMGN": ("암젠", "Amgen · 바이오 제약"),
    "ADI": ("아날로그디바이시스", "Analog Devices · 아날로그·혼합신호 반도체"),
    "AAPL": ("애플", "Apple · 아이폰·맥·서비스"),
    "AMAT": ("어플라이드머티리얼즈", "Applied Materials · 반도체 제조 장비"),
    "APP": ("앱러빈", "AppLovin · 모바일 광고·앱 수익화 소프트웨어"),
    "ARM": ("암홀딩스", "Arm Holdings · CPU 설계 기술(IP) 라이선스"),
    "ASML": ("ASML", "ASML Holding · 극자외선(EUV) 노광장비 (네덜란드)"),
    "ALAB": ("아스테라랩스", "Astera Labs · AI 서버용 연결(커넥티비티) 반도체"),
    "ADSK": ("오토데스크", "Autodesk · 설계·건축용 소프트웨어(AutoCAD)"),
    "ADP": ("ADP", "Automatic Data Processing · 급여·인사 관리 서비스"),
    "AXON": ("액손", "Axon Enterprise · 테이저·바디캠 등 공공안전 기술"),
    "BKR": ("베이커휴즈", "Baker Hughes · 에너지 장비·서비스"),
    "BKNG": ("부킹홀딩스", "Booking Holdings · 온라인 여행 예약(Booking.com)"),
    "AVGO": ("브로드컴", "Broadcom · 네트워크·AI 반도체와 인프라 소프트웨어"),
    "CDNS": ("케이던스", "Cadence Design Systems · 반도체 설계 자동화(EDA) 소프트웨어"),
    "CTAS": ("신타스", "Cintas · 유니폼·시설 관리 서비스"),
    "CSCO": ("시스코", "Cisco · 네트워크 장비·보안"),
    "CCEP": ("코카콜라유로퍼시픽", "Coca-Cola Europacific Partners · 유럽·호주 코카콜라 병입·판매"),
    "CMCSA": ("컴캐스트", "Comcast · 케이블·방송·NBC유니버설"),
    "CEG": ("컨스텔레이션에너지", "Constellation Energy · 원자력 중심 발전"),
    "CPRT": ("코파트", "Copart · 온라인 중고차·사고차 경매"),
    "CRWV": ("코어위브", "CoreWeave · AI 전용 GPU 클라우드"),
    "COST": ("코스트코", "Costco · 회원제 창고형 할인점"),
    "CRWD": ("크라우드스트라이크", "CrowdStrike · 클라우드 사이버보안"),
    "CSX": ("CSX", "CSX Corporation · 미국 동부 철도 운송"),
    "DDOG": ("데이터독", "Datadog · 클라우드 모니터링 소프트웨어"),
    "DXCM": ("덱스콤", "DexCom · 연속혈당측정기"),
    "FANG": ("다이아몬드백", "Diamondback Energy · 셰일 원유·가스 생산"),
    "DASH": ("도어대시", "DoorDash · 음식 배달 플랫폼"),
    "EXC": ("엑셀론", "Exelon · 미국 전력 유틸리티"),
    "FAST": ("패스널", "Fastenal · 산업용 체결 부품·공구 유통"),
    "FER": ("페로비알", "Ferrovial · 고속도로·공항 등 인프라 운영"),
    "FTNT": ("포티넷", "Fortinet · 네트워크 보안 장비"),
    "GEHC": ("GE헬스케어", "GE HealthCare · 의료영상·진단 장비"),
    "GILD": ("길리어드", "Gilead Sciences · 항바이러스 등 바이오 제약"),
    "HONA": ("허니웰항공우주", "Honeywell Aerospace · 허니웰에서 분리된 항공우주 사업"),
    "HON": ("허니웰", "Honeywell · 산업 자동화·빌딩 기술"),
    "IDXX": ("아이덱스", "Idexx Laboratories · 동물 진단 장비"),
    "INTC": ("인텔", "Intel · CPU와 파운드리(위탁생산)"),
    "INTU": ("인튜이트", "Intuit · 터보택스·퀵북스 소프트웨어"),
    "ISRG": ("인튜이티브서지컬", "Intuitive Surgical · 다빈치 수술 로봇"),
    "KDP": ("큐리그닥터페퍼", "Keurig Dr Pepper · 음료와 커피 머신"),
    "KLAC": ("KLA", "KLA Corporation · 반도체 검사·계측 장비"),
    "KHC": ("크래프트하인즈", "Kraft Heinz · 가공식품"),
    "LRCX": ("램리서치", "Lam Research · 반도체 식각·증착 장비"),
    "LIN": ("린데", "Linde · 산업용 가스"),
    "LITE": ("루멘텀", "Lumentum · 광통신·레이저 부품"),
    "MAR": ("메리어트", "Marriott International · 호텔 체인"),
    "MRVL": ("마벨", "Marvell Technology · 데이터센터·네트워크 반도체"),
    "MELI": ("메르카도리브레", "Mercado Libre · 중남미 전자상거래·핀테크"),
    "META": ("메타", "Meta Platforms · 페이스북·인스타그램"),
    "MCHP": ("마이크로칩", "Microchip Technology · 마이크로컨트롤러 반도체"),
    "MU": ("마이크론", "Micron Technology · 메모리 반도체(D램·낸드)"),
    "MSFT": ("마이크로소프트", "Microsoft · 윈도우·오피스·애저 클라우드"),
    "MSTR": ("스트래티지", "MicroStrategy · 비트코인을 대량 보유한 소프트웨어 기업"),
    "MDLZ": ("몬덜리즈", "Mondelez International · 오레오 등 과자·스낵"),
    "MPWR": ("모놀리식파워", "Monolithic Power Systems · 전력관리 반도체"),
    "MNST": ("몬스터베버리지", "Monster Beverage · 에너지 음료"),
    "NBIS": ("네비우스", "Nebius Group · AI 클라우드 인프라 (네덜란드)"),
    "NFLX": ("넷플릭스", "Netflix · 동영상 스트리밍"),
    "NVDA": ("엔비디아", "Nvidia · AI·그래픽 GPU"),
    "NXPI": ("NXP", "NXP Semiconductors · 차량용 반도체 (네덜란드)"),
    "ORLY": ("오라일리", "O'Reilly Automotive · 자동차 부품 소매"),
    "ODFL": ("올드도미니언", "Old Dominion Freight Line · 화물 운송"),
    "PCAR": ("팩카", "Paccar · 트럭 제조(켄워스·피터빌트)"),
    "PLTR": ("팔란티어", "Palantir Technologies · 데이터 분석·AI 플랫폼"),
    "PANW": ("팔로알토", "Palo Alto Networks · 사이버보안 플랫폼"),
    "PAYX": ("페이첵스", "Paychex · 중소기업 급여·인사 서비스"),
    "PYPL": ("페이팔", "PayPal · 온라인 결제"),
    "PDD": ("PDD", "PDD Holdings · 테무·핀둬둬 운영 (중국 전자상거래)"),
    "PEP": ("펩시코", "PepsiCo · 음료와 스낵"),
    "QCOM": ("퀄컴", "Qualcomm · 모바일 칩과 통신 특허"),
    "REGN": ("리제네론", "Regeneron Pharmaceuticals · 바이오 제약"),
    "RKLB": ("로켓랩", "Rocket Lab · 소형 로켓 발사·우주 부품"),
    "ROP": ("로퍼", "Roper Technologies · 산업·소프트웨어 지주회사"),
    "ROST": ("로스스토어", "Ross Stores · 할인 의류 소매"),
    "SNDK": ("샌디스크", "Sandisk · 낸드 플래시·SSD"),
    "STX": ("시게이트", "Seagate Technology · 하드디스크 드라이브"),
    "SHOP": ("쇼피파이", "Shopify · 온라인 쇼핑몰 구축 플랫폼"),
    "SPCX": ("스페이스X", "SpaceX · 로켓 발사와 스타링크 위성 인터넷"),
    "SBUX": ("스타벅스", "Starbucks · 커피 체인"),
    "SNPS": ("시높시스", "Synopsys · 반도체 설계 자동화(EDA) 소프트웨어"),
    "TMUS": ("티모바일", "T-Mobile US · 미국 이동통신"),
    "TTWO": ("테이크투", "Take-Two Interactive · GTA 등 게임 퍼블리셔"),
    "TER": ("테라다인", "Teradyne · 반도체 테스트 장비·로봇"),
    "TSLA": ("테슬라", "Tesla · 전기차·에너지 저장장치"),
    "TXN": ("텍사스인스트루먼트", "Texas Instruments · 아날로그 반도체"),
    "TRI": ("톰슨로이터", "Thomson Reuters · 뉴스·법률 정보 서비스"),
    "VRTX": ("버텍스", "Vertex Pharmaceuticals · 낭포성 섬유증 등 바이오 제약"),
    "WMT": ("월마트", "Walmart · 대형 할인점"),
    "WBD": ("워너브라더스", "Warner Bros. Discovery · 미디어·HBO 스트리밍"),
    "WDC": ("웨스턴디지털", "Western Digital · 하드디스크 드라이브"),
    "WDAY": ("워크데이", "Workday · 인사·재무 클라우드 소프트웨어"),
    "XEL": ("엑셀에너지", "Xcel Energy · 미국 중서부 전력 유틸리티"),
}
for _k, _v in NDX_INFO.items():
    TICKER_INFO.setdefault(_k, _v)  # 용어 사전(GLOSSARY) 생성 이후에 추가하므로 본문 자동 밑줄에는 영향 없음
NDX_FALLBACK = list(NDX_INFO)  # 위키피디아 자동 갱신 실패 시 쓰는 내장 구성 종목 목록


# ============================================================
# 섹터·테마 현황 (ETF 랭킹 탭의 두 번째 보기) — 레버리지·인버스 제외
# ============================================================
SECTOR_GROUPS = {
    "기준 지수": ["SPY", "QQQ", "RSP", "IWM"],
    "11개 섹터": ["XLK", "XLC", "XLY", "XLP", "XLV", "XLF", "XLI", "XLE", "XLB", "XLU", "XLRE"],
    "세부 테마": ["SMH", "IGV", "CIBR", "FDN", "QTUM", "ITA", "URA", "XBI", "IBB", "KRE", "ITB", "LIT", "COPX", "GDX"],
    "국가·지역": ["FEZ", "EWJ", "INDA", "EWT", "EWY", "MCHI", "EEM"],
    "원자재": ["GLD", "SLV", "PDBC", "OILK"],
}
SECTOR_INFO = {
    "RSP": ("S&P500 동일가중", "Invesco S&P 500 Equal Weight · S&P500 500개 종목을 같은 비중으로 담아 시장 전체의 체력을 보여줌"),
    "XLC": ("커뮤니케이션", "Communication Services Select Sector SPDR · 통신·미디어·인터넷 플랫폼 섹터"),
    "XLY": ("경기소비재", "Consumer Discretionary Select Sector SPDR · 자동차·유통·여가 등 경기에 민감한 소비재 섹터"),
    "XLP": ("필수소비재", "Consumer Staples Select Sector SPDR · 식품·생활용품 등 경기 방어적 소비재 섹터"),
    "XLI": ("산업재", "Industrial Select Sector SPDR · 항공·기계·운송·건설 등 산업재 섹터"),
    "XLB": ("소재", "Materials Select Sector SPDR · 화학·금속·건설자재 등 소재 섹터"),
    "XLRE": ("부동산", "Real Estate Select Sector SPDR · S&P500 내 부동산(리츠) 섹터"),
    "CIBR": ("사이버보안", "First Trust NASDAQ Cybersecurity · 사이버보안 기업"),
    "ITA": ("방산·항공우주", "iShares U.S. Aerospace & Defense · 미국 방산·항공우주 기업"),
    "URA": ("우라늄·원전", "Global X Uranium · 우라늄 채굴·원자력 관련 기업"),
    "XBI": ("바이오(동일가중)", "SPDR S&P Biotech · 바이오테크 동일가중, 중소형 바이오 비중이 큼"),
    "KRE": ("지역은행", "SPDR S&P Regional Banking · 미국 지역은행"),
    "ITB": ("주택건설", "iShares U.S. Home Construction · 주택건설·건자재 기업"),
    "COPX": ("구리 광산", "Global X Copper Miners · 구리 채굴 기업 (전력망·AI 인프라 수요와 연관)"),
    "GDX": ("금 광산", "VanEck Gold Miners · 금 채굴 기업"),
    "EWJ": ("일본", "iShares MSCI Japan · 일본 대형·중형주"),
    "INDA": ("인도", "iShares MSCI India · 인도 대형·중형주"),
    "EWT": ("대만", "iShares MSCI Taiwan · 대만 대형·중형주 (TSMC 비중 큼)"),
    "EWY": ("한국", "iShares MSCI South Korea · 한국 대형·중형주"),
    "MCHI": ("중국", "iShares MSCI China · 중국 대형·중형주"),
    "SLV": ("은", "iShares Silver Trust · 은 현물 가격 추종"),
}
for _k, _v in SECTOR_INFO.items():
    TICKER_INFO.setdefault(_k, _v)  # 용어 사전 생성 이후 추가 → 본문 자동 밑줄에는 영향 없음
for _k, _v in SP500_KR_INFO.items():
    TICKER_INFO.setdefault(_k, _v)  # S&P500 종목도 용어 사전 생성 이후 추가 → 'C'·'T'·'V' 같은 한 글자 티커가 본문(예: 전략 C)에 밑줄로 붙지 않음


@st.cache_data(ttl=3600, show_spinner=False)
def get_sector_flow_data(tickers):
    """섹터·테마 ETF 일봉으로 수익률·상대강도·200일선·거래대금 변화를 계산."""
    tickers = list(tickers)
    start = (datetime.datetime.now() - datetime.timedelta(days=420)).strftime("%Y-%m-%d")
    try:
        df = yf.download(tickers, start=start, interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    close, vol = df["Close"], df["Volume"]
    if isinstance(close, pd.Series):
        close, vol = close.to_frame(tickers[0]), vol.to_frame(tickers[0])

    def _ret(s, n):
        return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100 if len(s) > n and s.iloc[-1 - n] > 0 else np.nan

    spy = close["SPY"].dropna() if "SPY" in close.columns else pd.Series(dtype=float)
    spy3 = _ret(spy, 63) if len(spy) else np.nan
    rows = []
    for t in tickers:
        if t not in close.columns:
            continue
        c = close[t].dropna()
        v = vol[t].reindex(c.index).fillna(0)
        if len(c) < 130:
            continue
        r1w, r1, r3, r6, r12 = _ret(c, 5), _ret(c, 21), _ret(c, 63), _ret(c, 126), _ret(c, 252)
        parts = [x for x in (r1, r3, r6, r12) if pd.notna(x)]
        dv = c * v
        dv20, dv120 = dv.iloc[-20:].mean(), dv.iloc[-120:].mean()
        ma200 = c.iloc[-200:].mean() if len(c) >= 200 else np.nan
        rows.append({
            "Ticker": t,
            "1W": r1w, "1M": r1, "3M": r3, "6M": r6, "12M": r12,
            "score": float(np.mean(parts)) if parts else np.nan,
            "rs3": r3 - spy3 if pd.notna(r3) and pd.notna(spy3) else np.nan,
            "above200": ("위 ▲" if c.iloc[-1] > ma200 else "아래 ▼") if pd.notna(ma200) else "-",
            "flow": dv20 / dv120 if dv120 > 0 else np.nan,
            "asof": c.index[-1].strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def render_sector_flow():
    """🧭 섹터·테마 현황: 11개 섹터·세부 테마·국가·원자재의 상대강도와 자금 유입 신호."""
    st.markdown(
        "레버리지·인버스를 뺀 **섹터·테마·국가·원자재 ETF**로, 지금 어디가 주도하고 어디로 돈이 몰리는지 봅니다. "
        "전략 매매 신호가 아니라 시장을 읽기 위한 참고 화면입니다."
    )
    all_t = list(dict.fromkeys(t for g in SECTOR_GROUPS.values() for t in g))
    _ph = st.empty()
    with _ph.container():
        with st.status(f"📥 섹터·테마 ETF {len(all_t)}개의 1년치 시세를 불러오는 중입니다… (처음엔 10~30초, 이후 1시간은 바로 표시)",
                       expanded=True) as _stt:
            st.write("⏳ 야후 파이낸스에서 일봉 데이터를 내려받고 수익률·200일선·거래대금을 계산하고 있어요. 화면이 잠시 흐려져도 정상입니다.")
            st.caption("1분 넘게 이 상태면 인터넷 연결이나 야후 서버 문제일 수 있으니 새로고침(F5)해 주세요.")
            sf = get_sector_flow_data(tuple(all_t))
            _stt.update(label="✅ 섹터·테마 데이터 불러오기 완료", state="complete", expanded=False)
    _ph.empty()
    if sf is None or sf.empty:
        st.warning("섹터·테마 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        return
    sf = sf.set_index("Ticker")

    # ── 시장 체력: 대형주 쏠림 vs 고른 상승 ──
    def _g(t, k):
        return sf.at[t, k] if t in sf.index else np.nan

    gap_rsp = _g("RSP", "3M") - _g("SPY", "3M")
    gap_iwm = _g("IWM", "3M") - _g("SPY", "3M")
    if pd.notna(gap_rsp):
        if gap_rsp <= -3:
            breadth = f"⚠️ **대형주 쏠림** — 최근 3개월 동일가중(RSP)이 S&P500(SPY)보다 {abs(gap_rsp):.1f}%p 뒤처짐. 소수 대형주가 지수를 끌고 가는 장입니다."
        elif gap_rsp >= 1:
            breadth = f"✅ **고른 상승** — 최근 3개월 동일가중(RSP)이 S&P500(SPY)보다 {gap_rsp:.1f}%p 앞섬. 시장 전체로 돈이 퍼지고 있습니다."
        else:
            breadth = f"➖ **중립** — 최근 3개월 RSP와 SPY 차이 {gap_rsp:+.1f}%p."
        if pd.notna(gap_iwm):
            breadth += f" 소형주(IWM)는 SPY 대비 {gap_iwm:+.1f}%p."
        st.info(breadth)

    # ── 보기 선택 ──
    c1, c2 = st.columns([1, 1.6])
    with c1:
        grp = st.radio("📂 분류", ["11개 섹터", "세부 테마", "국가·지역", "원자재", "기준 지수", "전체"],
                       horizontal=True, key="sector_grp_radio", index=1)
    with c2:
        sort_lbl = st.radio("🏆 정렬 기준",
                            ["종합 스코어", "1주", "1개월", "3개월", "6개월", "12개월", "SPY 대비 3개월", "거래대금 증가"],
                            horizontal=True, key="sector_sort_radio")
    tick = all_t if grp == "전체" else SECTOR_GROUPS[grp]
    grp_of = {t: g for g, ts in SECTOR_GROUPS.items() for t in ts}
    sort_map = {"종합 스코어": "종합 스코어", "1주": "1주 (%)", "1개월": "1개월 (%)", "3개월": "3개월 (%)",
                "6개월": "6개월 (%)", "12개월": "12개월 (%)", "SPY 대비 3개월": "SPY 대비 3M (%p)",
                "거래대금 증가": "거래대금 배수"}

    rows = []
    for t in tick:
        if t not in sf.index:
            continue
        r = sf.loc[t]
        rows.append({
            "티커 (Ticker)": t,
            "분류": grp_of.get(t, ""),
            "종합 스코어": r["score"],
            "1주 (%)": r["1W"], "1개월 (%)": r["1M"], "3개월 (%)": r["3M"],
            "6개월 (%)": r["6M"], "12개월 (%)": r["12M"],
            "SPY 대비 3M (%p)": r["rs3"],
            "200일선": r["above200"],
            "거래대금 배수": r["flow"],
        })
    if not rows:
        st.warning("표시할 ETF가 없습니다.")
        return
    dfv = pd.DataFrame(rows)
    scol = sort_map[sort_lbl]
    dfv = dfv.sort_values(scol, ascending=False, na_position="last").reset_index(drop=True)
    dfv.index += 1

    # ── 요약: 주도 Top3 + 자금 유입 신호 ──
    top3 = [f"{t}({TICKER_INFO.get(t, (t,))[0]})" for t in
            dfv.sort_values("종합 스코어", ascending=False)["티커 (Ticker)"].head(3)]
    inflow = dfv[(dfv["거래대금 배수"] >= 1.3) & (dfv["1개월 (%)"] > 0) & (dfv["200일선"] == "위 ▲")]
    inflow_txt = ", ".join(f"{t}({TICKER_INFO.get(t, (t,))[0]})" for t in inflow["티커 (Ticker)"]) or "없음"
    st.markdown(
        f"**🥇 {grp} 주도 Top 3 (종합 스코어)**: {' · '.join(top3)}  \n"
        f"**💰 자금 유입 신호** (거래대금 1.3배↑ · 1개월 상승 · 200일선 위): {inflow_txt}"
    )

    # ── 차트 ──
    try:
        _ch = dfv.head(15).copy()
        _ch["이름"] = [f"{t} {TICKER_INFO.get(t, ('',))[0]}" for t in _ch["티커 (Ticker)"]]
        chart = alt.Chart(_ch).mark_bar(cornerRadiusEnd=6).encode(
            x=alt.X(f"{scol}:Q", title=sort_lbl),
            y=alt.Y("이름:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelLimit=200, labelFontSize=12)),
            color=alt.condition(alt.datum[scol] >= 0, alt.value("#10b981"), alt.value("#ef4444")),
            tooltip=["이름", alt.Tooltip(f"{scol}:Q", format=".2f")],
        ).properties(height=max(240, 30 * len(_ch)))
        st.altair_chart(chart, use_container_width=True)
    except Exception:
        st.bar_chart(dfv.set_index("티커 (Ticker)")[scol])

    _t = dfv.copy()
    _t.insert(0, "순위", _t.index)
    _t = _t.astype(object).where(_t.notna(), "-")
    render_html_table(_t, ticker_cols=("티커 (Ticker)",), text_cols=("분류", "200일선"))
    st.caption(
        f"기준일 {sf['asof'].max()} · 수익률은 거래일 기준(1주=5일, 1개월=21일, 3개월=63일, 6개월=126일, 12개월=252일). "
        "종합 스코어 = 1·3·6·12개월 수익률 평균. 'SPY 대비 3M'은 3개월 수익률에서 SPY 3개월 수익률을 뺀 값(상대강도). "
        "'거래대금 배수' = 최근 20일 평균 거래대금 ÷ 최근 120일 평균 거래대금으로, 1.3배 이상이면 평소보다 돈이 많이 오가는 중입니다. "
        "실제 ETF 자금 유출입(설정·환매) 데이터가 아니라 거래대금으로 추정한 값이며, 하락하면서 거래대금이 늘 때도 있으니 수익률과 함께 보세요."
    )


# ============================================================
# 인사이트 추가 (2026-10-05): ① 카나리아 경계 거리 ② 포트폴리오 성격 진단 ③ 시장 위험 신호판
# ============================================================
def _bdays_to_month_end():
    today = pd.Timestamp(datetime.datetime.now().date())
    return len(pd.bdate_range(today, today + pd.offsets.MonthEnd(0)))


def _mode_pill(attack):
    """공격/방어 라벨 (st.metric의 화살표 대신 색 라벨로 표시)."""
    if attack:
        return ("<span style='display:inline-block;padding:3px 12px;border-radius:999px;background:#dcfce7;"
                "color:#15803d;font-weight:700;font-size:0.95rem'>🟢 공격</span>")
    return ("<span style='display:inline-block;padding:3px 12px;border-radius:999px;background:#fee2e2;"
            "color:#b91c1c;font-weight:700;font-size:0.95rem'>🔴 방어</span>")


def render_canary_guide(tip_ratio, tip_score_b, realtime_dy, is_attack_a, is_attack_b, is_attack_c):
    """카나리아 신호 요약 아래 '📖 읽는 법' (지금 값으로 해석 문장 포함)."""
    n_def = [is_attack_a, is_attack_b, is_attack_c].count(False)
    if n_def == 0:
        combo = "**3개 모두 공격** — 금리 환경도 우호적이고 주식도 비싸지 않은 상태입니다. 혼합 포트폴리오가 위험자산 중심입니다."
    elif n_def == 3:
        combo = ("**3개 모두 방어** — 금리 흐름도 불리하고 주식도 비싼 상태입니다. 포트폴리오 대부분이 채권·금·원자재·현금·인버스라, "
                 "시장이 계속 오르면 QQQ보다 뒤처지고 떨어지면 덜 잃는 구성입니다.")
    else:
        combo = f"**{3 - n_def}개 공격 · {n_def}개 방어** — 일부 전략만 공격 중이라 주식과 방어 자산이 섞여 있습니다."
    a_gap = (tip_ratio - 1) * 100
    a_txt = (f"TIP이 11개월 평균보다 **{abs(a_gap):.1f}% {'위' if a_gap > 0 else '아래'}** → "
             + ("실질금리가 내려가는(돈이 풀리는) 흐름이라 공격입니다." if is_attack_a else "실질금리가 오르는(돈이 귀해지는) 흐름이라 방어입니다."))
    b_txt = (f"TIP의 1·3·6·9·12개월 수익률 평균이 **{tip_score_b:+.2f}%** → "
             + ("여러 기간에 걸쳐 TIP이 오르고 있어 공격입니다." if is_attack_b else "여러 기간에 걸쳐 TIP이 내리고 있어 방어입니다."))
    c_txt = (f"S&P500 배당수익률 **{realtime_dy:.2f}%** (기준 1.33%) → "
             + ("주가가 배당에 비해 비싸지 않은 구간이라 공격입니다." if is_attack_c
                else "주가가 배당에 비해 비싼 구간이라 방어입니다. 참고로 2000년 닷컴버블 고점이 약 0.99%였습니다."))
    with st.expander("📖 카나리아 신호 읽는 법 — 무엇이고, 왜 이것이고, 숫자는 어떻게 보나", expanded=False):
        st.markdown(f"""
**지금 화면 해석**

- **A**: {a_txt}
- **B**: {b_txt}
- **C**: {c_txt}
- **종합**: {combo}

---

**카나리아 자산이란?**

옛날 광부들은 탄광에 카나리아를 데리고 들어갔습니다. 유독가스에 사람보다 먼저 반응해서, 카나리아가 이상하면 바로 탈출했습니다. 투자에서도 **위험을 먼저 알려주는 지표**를 정해 두고 그 신호로 공격(주식 등 위험자산)과 방어(채권·금·현금)를 바꿉니다. 카나리아는 **사는 자산이 아니라 판단에 쓰는 신호**입니다.

**왜 이 두 가지인가?**

| 카나리아 | 무엇을 보나 | 쓰는 전략 |
|---|---|---|
| **TIP (미국 물가연동국채)** | **돈의 흐름(금리·유동성)**. TIP 가격은 실질금리와 반대로 움직입니다. TIP이 내린다 = 실질금리가 오른다 = 돈이 귀해지고 긴축이 심해진다는 신호이고, 주식(특히 성장주)에 불리합니다. | A, B |
| **S&P500 배당수익률** | **주식 가격 수준(밸류에이션)**. 배당 ÷ 주가라서 주가가 비쌀수록 낮아집니다. 낮으면 고평가, 높으면 저평가입니다. | C |

하나는 채권시장(금리), 하나는 주식시장(가격 수준)에서 나오는 **서로 다른 종류의 신호**라, 하나가 틀려도 다른 쪽이 받쳐 줍니다. 채권시장은 주식시장보다 경기 변화를 먼저 반영하는 경우가 많아 카나리아로 쓰기 좋습니다.

**숫자 읽는 법**

| 전략 | 계산 | 기준 | 감 잡기 |
|---|---|---|---|
| A · TIP 비율 | 지금 TIP 가격 ÷ 최근 11개월 평균 | 1 초과 공격 / 1 이하 방어 | 1.00 근처는 전환 경계, 0.98 이하는 뚜렷한 하락 추세. TIP은 한 달에 보통 1\\~2% 움직입니다 |
| B · TIP 모멘텀 | TIP의 1·3·6·9·12개월 수익률 평균 | 0 초과 공격 / 0 이하 방어 | A는 '평균선보다 위인가', B는 '여러 기간 동안 올랐나'. **A·B가 둘 다 방어면** 금리 흐름이 확실히 불리 |
| C · 배당수익률 | 최근 12개월 SPY 배당 ÷ 현재 SPY 가격 | 1.33% 초과 공격 / 이하 방어 | 1.0% 안팎은 2000년 닷컴버블 고점 수준의 고평가 |

**C를 볼 때 주의할 점**

- **고평가 ≠ 곧 하락.** 비싼 시장은 몇 년씩 이어질 수 있습니다. 실제로 C는 2024년 4월부터 방어였지만 그 사이 금이 크게 올라 수익을 냈습니다.
- **폭락 경보가 아닙니다.** 주가가 떨어지면 배당수익률은 오히려 올라가서, 2008년 금융위기 때도 이 신호는 공격이었습니다. "비싸다"를 알려 주는 신호이고, 폭락은 A·B와 다른 전략들이 받쳐 줍니다.
- 기업들이 배당 대신 자사주 매입을 늘려 배당수익률이 예전보다 구조적으로 낮아진 면도 있습니다.

**세 신호를 함께 보면**

| 상황 | 뜻 |
|---|---|
| 3개 모두 공격 | 위험자산 중심. 상승장 수익을 최대한 따라감 |
| 섞여 있음 | 주식과 방어 자산이 섞인 중간 상태 |
| 3개 모두 방어 | 대부분 방어 자산. 상승장에선 QQQ보다 뒤처지고, 하락장에선 덜 잃음 |

**다음에 볼 것**: 바로 아래 '🧭 카나리아 경계 거리'에서 각 신호가 바뀌려면 얼마나 움직여야 하는지 확인하세요. 공격/방어 전환은 **월말 종가 기준**으로만 하고, 중간에 미리 매매하지 않습니다.
""")


def render_canary_distance(tip_closes, tip_current, realtime_dy, is_attack_a, is_attack_b, is_attack_c, only=None):
    """① 각 카나리아가 공격/방어를 바꾸려면 기준 가격이 몇 % 움직여야 하는지."""
    closes = [float(x) for x in (tip_closes or []) if x == x]
    p = float(tip_current or 0)

    def _status(gap, near, warn):
        a = abs(gap)
        return "⚠️ 전환 임박" if a < near else ("🟡 주의" if a < warn else "🟢 여유")

    rows = []
    if p > 0 and len(closes) >= 11:
        flip = float(np.mean(closes[-11:-1]))  # TIP > 직전 10개월 평균이면 11개월 평균 위
        gap = (p / flip - 1) * 100
        what = f"TIP이 {abs(gap):.2f}% 넘게 {'내리면 방어' if is_attack_a else '오르면 공격'}로 전환"
        rows.append({"전략": "A · TIP 11개월 평균", "현재 모드": "공격" if is_attack_a else "방어",
                     "전환 기준": f"TIP ${flip:.2f}", "현재 값": f"TIP ${p:.2f}",
                     "전환까지": f"{gap:+.2f}%", "상태": _status(gap, 0.5, 1.5), "해석": what})
    if p > 0 and len(closes) >= 13:
        past = [closes[-2], closes[-4], closes[-7], closes[-10], closes[-13]]
        flip = 1.0 / float(np.mean([1.0 / x for x in past]))  # 1·3·6·9·12개월 평균 수익률이 0이 되는 가격
        gap = (p / flip - 1) * 100
        what = f"TIP이 {abs(gap):.2f}% 넘게 {'내리면 방어' if is_attack_b else '오르면 공격'}로 전환"
        rows.append({"전략": "B · TIP 모멘텀 점수", "현재 모드": "공격" if is_attack_b else "방어",
                     "전환 기준": f"TIP ${flip:.2f}", "현재 값": f"TIP ${p:.2f}",
                     "전환까지": f"{gap:+.2f}%", "상태": _status(gap, 0.5, 1.5), "해석": what})
    if realtime_dy and realtime_dy > 0:
        gap = (realtime_dy / 1.33 - 1) * 100  # SPY 가격이 이만큼 변하면 배당수익률이 1.33%가 됨
        what = (f"SPY가 약 {abs(gap):.1f}% 오르면 방어로 전환" if is_attack_c
                else f"SPY가 약 {abs(gap):.1f}% 내려야 공격으로 전환 (배당이 그대로일 때)")
        rows.append({"전략": "C · SPY 배당수익률", "현재 모드": "공격" if is_attack_c else "방어",
                     "전환 기준": "1.33%", "현재 값": f"{realtime_dy:.2f}%",
                     "전환까지": f"SPY {gap:+.1f}%", "상태": _status(gap, 3, 8), "해석": what})
    if only:
        rows = [r for r in rows if r["전략"].startswith(only)]
    if not rows:
        return
    if only:
        st.markdown("#### 🧭 전환까지 거리 — 다음 월말에 모드가 바뀔까?")
        st.caption(f"오늘부터 월말까지 약 {_bdays_to_month_end()}거래일(오늘 포함). 실제 공격/방어 판단은 월말 종가로 합니다.")
        render_html_table(pd.DataFrame(rows), text_cols=("전략", "현재 모드", "전환 기준", "현재 값", "상태", "해석"))
        return
    st.markdown("#### 🧭 카나리아 경계 거리 — 다음 월말에 모드가 바뀔까?")
    st.caption(f"오늘부터 월말까지 약 {_bdays_to_month_end()}거래일(오늘 포함). 실제 공격/방어 판단은 월말 종가로 합니다.")
    render_html_table(pd.DataFrame(rows), text_cols=("전략", "현재 모드", "전환 기준", "현재 값", "상태", "해석"))
    with st.expander("📖 읽는 법", expanded=False):
        st.markdown("""
- **전환까지**: 지금 값에서 기준 가격(또는 비율)까지 몇 % 남았는지입니다. **+**면 기준보다 위(공격 쪽), **−**면 아래(방어 쪽)입니다.
- **A**: TIP(물가연동채)이 직전 10개월 평균보다 높으면 공격입니다(= 11개월 평균 위). 전환 기준은 그 평균 가격입니다.
- **B**: TIP의 1·3·6·9·12개월 수익률 평균이 0보다 크면 공격입니다. 전환 기준은 그 평균이 정확히 0이 되는 TIP 가격입니다.
- **C**: SPY 배당수익률이 1.33%보다 높으면 공격입니다. 배당이 그대로일 때 SPY가 몇 % 움직여야 1.33%가 되는지로 표시합니다.
- **상태**: A·B는 TIP의 한 달 움직임이 보통 1\\~2%라 **0.5% 이내 ⚠️ 전환 임박 · 1.5% 이내 🟡 주의**, C는 SPY 기준이라 **3% 이내 ⚠️ · 8% 이내 🟡**로 봅니다.
- **활용**: ⚠️가 뜬 전략은 이번 월말 리밸런싱 때 공격/방어가 바뀔 수 있으니, 바뀔 경우의 종목을 미리 확인해 두세요. 판단은 월말 종가 하나로만 하며, 중간에 미리 매매하지 않습니다.
""")


_CANARY_INTRO = (
    "**카나리아란?** 옛날 광부들은 유독가스에 먼저 반응하는 카나리아를 탄광에 데리고 들어갔습니다. "
    "투자에서도 **위험을 먼저 알려주는 지표**를 정해 두고 그 신호로 공격(위험자산)과 방어(채권·금·현금 등)를 바꿉니다. "
    "카나리아는 **사는 자산이 아니라 판단에 쓰는 신호**입니다."
)


# ── 반대 모드로 바뀐다면 (2026-10-23): 전략 A·B·C 탭에서 지금과 반대 모드의 자산 순위와 예상 포트폴리오 (기본 접기) ──
_OTHER_MODE_SPEC = {   # 전략: (공격 자산, 방어 자산, 공격 정렬열, 공격 표 열, 공격 고르기 수, 방어 정렬열, 방어 표 열, 방어 진입 점수열, 열 이름 바꾸기)
    "A": (OFFENSIVE_A, DEFENSIVE_A, "A_공격스코어", ["Ticker", "현재가", "1M", "3M", "6M", "12M", "A_공격스코어"], 4,
          "A_방어스코어", ["Ticker", "현재가", "1M", "3M", "6M", "9M", "12M", "A_방어스코어"], "A_방어스코어",
          {"A_공격스코어": "모멘텀 스코어", "A_방어스코어": "모멘텀 스코어"}),
    "B": (OFFENSIVE_B, DEFENSIVE_B, "B_공격스코어", ["Ticker", "현재가", "1M", "3M", "6M", "12M", "B_공격스코어"], 1,
          "5M", ["Ticker", "현재가", "5M", "B_단순모멘텀"], "B_단순모멘텀",
          {"B_공격스코어": "가중 모멘텀 스코어", "5M": "5개월 수익률", "B_단순모멘텀": "자체 단순모멘텀"}),
    "C": (OFFENSIVE_C, DEFENSIVE_C, "A_공격스코어", ["Ticker", "현재가", "1M", "3M", "6M", "12M", "A_공격스코어"], 1,
          "A_방어스코어", ["Ticker", "현재가", "1M", "3M", "6M", "9M", "12M", "A_방어스코어"], "A_방어스코어",
          {"A_공격스코어": "모멘텀 스코어", "A_방어스코어": "모멘텀 스코어"}),
}


def render_other_mode(strat, is_attack, df_all, data_dict, capital=10_000_000):
    """지금 모드의 반대 모드로 바뀐다면: 그 모드 자산 순위표 + 같은 규칙으로 고른 예상 포트폴리오(금액 포함). 기본 접기."""
    off, dfn, o_sort, o_cols, o_n, d_sort, d_cols, d_gate, ren = _OTHER_MODE_SPEC[strat]
    other = "방어" if is_attack else "공격"
    if not tab_toggle(f"🔄 {other} 모드로 바뀐다면 — {other} 자산 순위와 예상 포트폴리오", key=f"other_mode_{strat}_r"):
        return
    if other == "공격":
        d = df_all[df_all["Ticker"].isin(off)].sort_values(by=o_sort, ascending=False)
        cols = [c for c in o_cols if c in d.columns]
        picks = [(t, 100.0 / o_n) for t in d.head(o_n)["Ticker"]] or [("CASH (현금)", 100.0)]
        rule = (f"공격 자산 중 점수 상위 {o_n}종목에 {100 / o_n:.0f}%씩" if o_n > 1 else "공격 자산 중 점수 1위에 100%")
    else:
        d = df_all[df_all["Ticker"].isin(dfn)].sort_values(by=d_sort, ascending=False)
        cols = [c for c in d_cols if c in d.columns]
        if d.empty:
            picks = [("CASH (현금)", 100.0)]
        else:
            top = d.iloc[0]
            picks = [(top["Ticker"], 100.0)] if float(top.get(d_gate, 0) or 0) > 0 else [("CASH (현금)", 100.0)]
        rule = ("방어 자산 중 5개월 수익률 1위를 고르고, 그 자산의 자체 모멘텀이 0보다 크면 100%, 아니면 현금" if strat == "B"
                else "방어 자산 중 점수 1위에 100%, 1위 점수가 0 이하면 현금")
    with st.container(border=True):
        st.markdown(f"**{other} 모드 자산 순위** (지금 가격 기준) · 규칙: {rule}")
        render_html_table(d[cols].rename(columns=ren), ticker_cols=("Ticker",))
        _rows = []
        for t, w in picks:
            px_ = data_dict.get(t, {}).get("현재가", None) if t != "CASH (현금)" else None
            amt = capital * w / 100
            _rows.append(f"<b>{_html.escape(t)}</b> {w:.0f}% · {amt / 1e4:,.0f}만원"
                         + (f" · 현재가 &#36;{px_:,.2f} → 약 {int(amt / 1350 / px_):,}주" if px_ else ""))
        st.markdown("<div style='border:2px solid #f59e0b;background:#fff7ed;border-radius:10px;padding:10px 14px;margin:8px 0;line-height:1.8'>"
                    f"<b style='color:#9a3412'>🎯 지금 {other} 모드로 바뀐다면 (전략 몫 1,000만원 기준)</b><br>" + "<br>".join(_rows) + "</div>",
                    unsafe_allow_html=True)
        st.caption("참고용 미리보기입니다. 실제 모드 전환과 종목 선택은 월말 종가로 정해지므로, 그때까지 순위가 바뀔 수 있습니다. "
                   "수량은 환율 1,350원 가정의 대략값이고, 2026 혼합전략에서는 이 비중의 1/3이 적용됩니다. "
                   "모드가 바뀌려면 얼마나 움직여야 하는지는 위 '🧭 전환까지 거리'에서 볼 수 있습니다.")


def render_canary_guide_single(strat, tip_ratio, tip_score_b, realtime_dy, attack, tip_closes, tip_current):
    """전략 A·B·C 탭용: 그 전략의 카나리아만 골라 경계 거리 + 읽는 법을 보여 줌."""
    with st.container(border=True):
        st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
        render_canary_distance(tip_closes, tip_current, realtime_dy, attack, attack, attack, only=strat)
    mode = "공격" if attack else "방어"
    if strat == "A":
        gap = (tip_ratio - 1) * 100
        now = (f"TIP이 11개월 평균보다 **{abs(gap):.1f}% {'위' if gap > 0 else '아래'}**(비율 {tip_ratio:.3f}) → "
               + ("실질금리가 내려가는(돈이 풀리는) 흐름이라 **공격**입니다. 공격 자산 12개 중 모멘텀 상위 4개를 25%씩 담습니다."
                  if attack else "실질금리가 오르는(돈이 귀해지는) 흐름이라 **방어**입니다. 채권·현금성 자산 중 모멘텀 1위를 담고, 모두 마이너스면 현금으로 둡니다."))
        body = f"""
**지금 화면 해석**: {now}

{_CANARY_INTRO}

**왜 TIP(미국 물가연동국채)인가?** TIP은 **돈의 흐름(실질금리·유동성)** 을 보여 줍니다. TIP 가격은 실질금리와 반대로 움직여서, TIP이 내린다 = 실질금리가 오른다 = 돈이 귀해지고 긴축이 심해진다는 뜻이고, 주식(특히 성장주)에 불리합니다. 채권시장은 주식시장보다 경기 변화를 먼저 반영하는 경우가 많아 카나리아로 쓰기 좋습니다.

| 항목 | 내용 |
|---|---|
| 계산 | 신호 비율 = 지금 TIP 가격 ÷ 최근 11개월(당월 포함) 평균 |
| 기준 | **1 초과 공격 / 1 이하 방어** |
| 감 잡기 | 1.00 근처는 전환 경계, 0.98 이하는 뚜렷한 하락 추세. TIP은 한 달에 보통 1\\~2% 움직이니, 비율이 1에서 2% 이상 떨어져 있으면 바뀌는 데 보통 몇 달이 걸립니다 |
| 성격 | 평균선 위·아래를 보는 **추세 필터**라 천천히, 덜 흔들리며 바뀝니다 |

- 같은 TIP을 전략 B는 '여러 기간 수익률'로 봅니다. **A·B가 둘 다 방어면** 금리 흐름이 확실히 불리하다는 뜻입니다.
- 위 '전환까지' 표는 이번 월말에 모드가 바뀌려면 TIP이 몇 % 움직여야 하는지입니다. 판단은 **월말 종가 기준**으로만 하고, 중간에 미리 매매하지 않습니다.
"""
    elif strat == "B":
        now = (f"TIP의 1·3·6·9·12개월 수익률 평균이 **{tip_score_b:+.2f}%** → "
               + ("여러 기간에 걸쳐 TIP이 오르고 있어 **공격**입니다. 레버리지 자산(TYD·UPRO·VNQ) 중 가중 모멘텀 1위에 100% 투자합니다."
                  if attack else "여러 기간에 걸쳐 TIP이 내리고 있어 **방어**입니다. 인버스 자산(DOG·RWM·TBF) 중 5개월 수익률 1위를 담고, 모두 마이너스면 현금으로 둡니다."))
        body = f"""
**지금 화면 해석**: {now}

{_CANARY_INTRO}

**왜 TIP(미국 물가연동국채)인가?** TIP 가격은 실질금리와 반대로 움직입니다. TIP이 오르면 돈이 풀리는(유동성 우호) 환경, 내리면 돈이 귀해지는(긴축) 환경입니다. 전략 B는 **3배 레버리지에 100% 집중**하는 공격형이라, 이 신호 하나가 '레버리지로 올라탈지 / 인버스로 방어할지'를 가릅니다. 그래서 방향이 확실할 때만 공격하도록 여러 기간을 평균 냅니다.

| 항목 | 내용 |
|---|---|
| 계산 | TIP의 1·3·6·9·12개월 수익률 평균 |
| 기준 | **0 초과 공격 / 0 이하 방어** |
| 감 잡기 | 0에 가까울수록 전환 경계. ±1% 이내면 다음 달 바뀔 수 있고, -2% 이하면 뚜렷한 하락 흐름 |
| 성격 | 짧은 기간(1개월)부터 긴 기간(12개월)까지 함께 봐서, 전략 A의 평균선 비교보다 **최근 움직임에 조금 더 민감**합니다 |

- 같은 TIP을 전략 A는 '11개월 평균선 대비 위치'로 봅니다. **A·B가 둘 다 방어면** 금리 흐름이 확실히 불리하다는 뜻입니다.
- 위 '전환까지' 표는 점수가 0이 되는 TIP 가격까지 몇 % 남았는지입니다. 판단은 **월말 종가 기준**으로만 합니다.
"""
    else:
        gap = (realtime_dy / 1.33 - 1) * 100 if realtime_dy else float("nan")
        now = (f"S&P500 배당수익률 **{realtime_dy:.2f}%**(기준 1.33%) → "
               + ("주가가 배당에 비해 비싸지 않은 구간이라 **공격**입니다. 주도 섹터 후보 7개 중 모멘텀 1위에 100% 투자합니다."
                  if attack else f"주가가 배당에 비해 비싼 구간이라 **방어**입니다. 금·원자재·채권 중 모멘텀 1위를 담고, 모두 마이너스면 현금으로 둡니다. "
                  f"배당이 그대로라면 SPY가 약 {abs(gap):.0f}% 내려야 공격으로 바뀝니다."))
        body = f"""
**지금 화면 해석**: {now}

{_CANARY_INTRO}

**왜 S&P500 배당수익률인가?** 배당수익률 = 최근 12개월 배당 ÷ 주가라서, 같은 배당이면 **주가가 비쌀수록 낮아집니다**. 즉 **주식 가격 수준(밸류에이션)** 을 보는 신호입니다. 전략 A·B가 채권시장(금리)을 보는 것과 달리, 전략 C는 주식시장 자체가 비싼지 싼지를 봅니다. 서로 다른 종류의 신호라 혼합전략에서 서로를 보완합니다.

| 항목 | 내용 |
|---|---|
| 계산 | 최근 12개월 SPY 배당 합계 ÷ SPY 실제 종가(배당 미조정) |
| 기준 | **1.33% 초과 공격(상대적으로 쌈) / 이하 방어(비쌈)** |
| 감 잡기 | 1.0% 안팎은 2000년 닷컴버블 고점(약 0.99%) 수준의 고평가. 1.2\\~1.6% 어디에 기준을 두어도 백테스트 성과가 비슷해, 1.33%는 무리하게 맞춘 값이 아닙니다 |

**주의할 점**

- **고평가 ≠ 곧 하락.** 비싼 시장은 몇 년씩 이어질 수 있습니다. C는 2024년 4월부터 방어였지만 그 사이 금이 크게 올라 수익을 냈습니다.
- **폭락 경보가 아닙니다.** 주가가 떨어지면 배당수익률은 오히려 올라가서, 2008년 금융위기 때도 이 신호는 공격이었습니다. 폭락 방어는 전략 A·B와 혼합 구성이 맡습니다.
- 기업들이 배당 대신 자사주 매입을 늘려 배당수익률이 예전보다 구조적으로 낮아진 면도 있습니다.
- 판단은 **월말 종가 기준**으로만 하고, 중간에 미리 매매하지 않습니다.
"""
    with st.expander(f"📖 전략 {strat} 카나리아 신호 읽는 법 — 지금 {mode}인 이유와 숫자 보는 법", expanded=False):
        st.markdown(body)


_PC_TECH = {"QQQ", "QQQM", "SMH", "XLK", "QTUM", "IGV", "FDN", "SOXL", "TQQQ"}
_PC_EQ = {"FEZ", "EEM", "IBB", "XLV", "XLE", "XLU", "LIT", "VNQ", "SPY", "DIA", "IWM", "XLF", "SCHD", "JEPI"}
_PC_LEV_EQ = {"UPRO": 3.0}
_PC_BOND = {"BIL", "IEF", "AGG", "HYG", "SHY", "TLT", "TIP"}
_PC_LEV_BOND = {"TYD": 3.0, "UBT": 2.0}
_PC_INV = {"DOG": "eq", "RWM": "eq", "TBF": "bond"}
_PC_COMM = {"GLD", "PDBC", "OILK"}


def render_portfolio_character(combined_alloc, hist_prices):
    """② 지금 혼합 포트폴리오가 어떤 자산에 얼마나 실려 있고, QQQ와 얼마나 같이 움직이는지."""
    w = {t: float(v) for t, v in combined_alloc.items() if v > 0.01}
    if not w:
        return
    groups = {"기술주": [], "기타 주식": [], "레버리지 주식": [], "채권": [], "레버리지 채권": [],
              "인버스": [], "금·원자재": [], "현금": [], "기타": []}
    for t, v in w.items():
        g = ("현금" if t == "CASH (현금)" else "기술주" if t in _PC_TECH else "기타 주식" if t in _PC_EQ
             else "레버리지 주식" if t in _PC_LEV_EQ else "채권" if t in _PC_BOND
             else "레버리지 채권" if t in _PC_LEV_BOND else "인버스" if t in _PC_INV
             else "금·원자재" if t in _PC_COMM else "기타")
        groups[g].append((t, v))
    tech = sum(v for _, v in groups["기술주"])
    eq_eff = (tech + sum(v for _, v in groups["기타 주식"])
              + sum(v * _PC_LEV_EQ[t] for t, v in groups["레버리지 주식"])
              - sum(v for t, v in groups["인버스"] if _PC_INV[t] == "eq"))
    bond_eff = (sum(v for _, v in groups["채권"]) + sum(v * _PC_LEV_BOND[t] for t, v in groups["레버리지 채권"])
                - sum(v for t, v in groups["인버스"] if _PC_INV[t] == "bond"))

    # 최근 3개월(63거래일) 동안 지금 비중을 들고 있었다면의 일간 수익률
    beta = corr = vol_p = vol_q = np.nan
    try:
        rets = {}
        for t in list(w) + ["QQQ"]:
            if t != "CASH (현금)" and t in hist_prices:
                rets[t] = pd.Series(hist_prices[t]).pct_change()
        rdf = pd.DataFrame(rets).dropna(how="all").iloc[-63:]
        if "QQQ" in rdf.columns and len(rdf) >= 40:
            port = sum(rdf[t].fillna(0) * (v / 100.0) for t, v in w.items() if t in rdf.columns)
            q = rdf["QQQ"].fillna(0)
            vol_p, vol_q = port.std() * np.sqrt(252) * 100, q.std() * np.sqrt(252) * 100
            beta = port.cov(q) / q.var() if q.var() > 0 else np.nan
            corr = port.corr(q)
    except Exception:
        pass

    st.markdown("#### 🧭 포트폴리오 성격 진단 — 지금 무엇에 실려 있나?")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("기술주 비중", f"{tech:.1f}%")
    m2.metric("실질 주식 노출", f"{eq_eff:.0f}%", help="레버리지는 배수만큼, 인버스는 마이너스로 계산한 주식 노출")
    m3.metric("QQQ 대비 베타", "-" if beta != beta else f"{beta:.2f}", help="QQQ가 1% 움직일 때 포트폴리오가 평균 몇 % 움직이는지 (최근 3개월)")
    m4.metric("변동성 (포트/QQQ)", "-" if vol_p != vol_p else f"{vol_p:.0f}% / {vol_q:.0f}%")

    msgs = []
    if tech >= 40:
        msgs.append(f"⚠️ **기술주 쏠림** — 포트폴리오의 {tech:.0f}%가 기술주입니다. 기술주가 급락하면 함께 크게 흔들립니다.")
    elif tech >= 25:
        msgs.append(f"🟡 **기술주 비중 높음** — {tech:.0f}%. 주도 섹터에 올라탄 상태지만 쏠림은 지켜보세요.")
    else:
        msgs.append(f"🟢 **기술주 분산** — 기술주 {tech:.0f}%로 한쪽에 몰려 있지 않습니다.")
    if corr == corr:
        if corr >= 0.8 and beta >= 0.8:
            msgs.append(f"⚠️ **사실상 QQQ와 비슷하게 움직이는 상태** — 상관 {corr:.2f}, 베타 {beta:.2f}. 지금은 하락장 방어보다 상승 추종 쪽에 가깝습니다.")
        elif corr < 0.5:
            msgs.append(f"🟢 **QQQ와 다르게 움직이는 상태** — 상관 {corr:.2f}. 채권·금·현금 등으로 분산되어 QQQ 급락 영향이 작습니다.")
        else:
            msgs.append(f"🟡 **QQQ를 부분적으로 따라가는 상태** — 상관 {corr:.2f}, 베타 {beta:.2f}.")
    if eq_eff > 100:
        msgs.append(f"🟡 **레버리지로 실질 주식 노출 {eq_eff:.0f}%** — 원금보다 큰 주식 위험을 지고 있습니다.")
    st.markdown("  \n".join(msgs))

    rows = []
    for g, items in groups.items():
        if items:
            rows.append({"자산군": g, "비중 (%)": round(sum(v for _, v in items), 2),
                         "종목": ", ".join(f"{t} {v:.1f}%" for t, v in sorted(items, key=lambda x: -x[1]))})
    render_html_table(pd.DataFrame(rows), text_cols=("자산군", "종목"))
    with st.expander("📖 읽는 법", expanded=False):
        st.markdown("""
- **기술주 비중**: QQQ·QQQM·SMH·XLK·QTUM·IGV·FDN의 합. **25% 이상 🟡, 40% 이상 ⚠️**. 여러 전략이 동시에 기술주를 고르면 쏠림이 커집니다.
- **실질 주식 노출**: UPRO(3배)는 비중×3, DOG·RWM(인버스)은 마이너스로 계산합니다. 100%를 넘으면 원금보다 큰 주식 위험입니다.
- **QQQ 대비 베타**: 지금 비중을 최근 3개월 들고 있었다고 가정했을 때, QQQ가 1% 움직이면 포트폴리오가 평균 몇 % 움직였는지. **1에 가까우면 QQQ와 비슷한 위험**, 0.5 이하면 방어적입니다.
- **상관계수**: QQQ와 같은 방향으로 움직인 정도(−1\\~1). **0.8 이상**이면 사실상 QQQ와 같이 움직이고, **0.5 미만**이면 분산 효과가 큽니다.
- **변동성**: 같은 기간 일간 등락을 연환산한 크기입니다. 포트폴리오가 QQQ보다 낮으면 덜 흔들리는 상태입니다.
- **활용**: 이 전략의 목표는 "상승장에서는 QQQ에 버금가는 수익, 위기에는 QQQ보다 얕은 낙폭"입니다. ⚠️가 여러 개면 지금은 상승 추종 쪽에 기운 상태라는 뜻이니, 비중 상한(설정 패널)을 켤지 판단하는 참고로 쓰세요. 판단 기준은 월말 리밸런싱 규칙 그대로입니다.
""")


# ===================== 🧮 시장 밸류에이션 계기판 (켄 피셔 『불변의 차트 90』 지표 응용, 2026-10-13) =====================
@st.cache_data(ttl=12 * 3600, show_spinner=False)
def get_fred_series(series_id):
    """미국 연준 공개 데이터(FRED)를 API 키 없이 CSV로 받음. 실패하면 빈 Series."""
    try:
        import requests
        from io import StringIO
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                         headers={"User-Agent": "Mozilla/5.0 (asset-allocation-dashboard)"}, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        s.index = pd.to_datetime(df.iloc[:, 0])
        s = s.dropna()
        if s.empty:
            raise ValueError("empty")
        return s
    except Exception as e:
        raise RuntimeError(f"FRED {series_id} 실패: {e}")   # 실패는 캐시하지 않음(다음 접속 때 다시 시도)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_etf_pe(ticker):
    """ETF의 후행 PER(야후 파이낸스 종목 정보). 없으면 NaN."""
    try:
        info = yf.Ticker(ticker).info or {}
        v = info.get("trailingPE")
    except Exception as e:
        raise RuntimeError(f"{ticker} PER 실패: {e}")
    if not v:
        raise RuntimeError(f"{ticker} PER 없음")       # 실패는 캐시하지 않음
    return float(v)


VALUATION_SNAPSHOT = "valuation_snapshot.json"


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def _valuation_load():
    """밸류에이션 계기판 데이터 (Cloud에서 막히면 PC 저장값으로 대체) — 밸류에이션·시장위험진단 공용."""
    pe_spy, pe_qqq = _try(get_etf_pe, "SPY"), _try(get_etf_pe, "QQQ")
    baa = _try(get_fred_series, "DBAA")          # 무디스 Baa 회사채 금리(일별)
    unrate = _try(get_fred_series, "UNRATE")     # 실업률(월별)
    # Cloud 서버에서는 야후 종목정보·FRED 접속이 막히는 경우가 있어, PC에서 받은 값(valuation_snapshot.json)으로 대체
    import json
    snap, used_snap = {}, []
    try:
        with open(VALUATION_SNAPSHOT, encoding="utf-8") as _f:
            snap = json.load(_f)
    except Exception:
        snap = {}
    if pe_spy is None and snap.get("pe_spy"):
        pe_spy = snap["pe_spy"]; used_snap.append("S&P500 PER")
    if pe_qqq is None and snap.get("pe_qqq"):
        pe_qqq = snap["pe_qqq"]; used_snap.append("나스닥100 PER")
    if baa is None and snap.get("baa"):
        baa = pd.Series(snap["baa"]["v"], index=pd.to_datetime(snap["baa"]["d"])); used_snap.append("회사채 금리")
    if unrate is None and snap.get("unrate"):
        unrate = pd.Series(snap["unrate"]["v"], index=pd.to_datetime(snap["unrate"]["d"])); used_snap.append("실업률")
    if not used_snap and all(x is not None for x in (pe_spy, pe_qqq, baa, unrate)):
        try:   # 모두 실시간으로 받았으면 저장값 갱신 (PC에서 저장 → 대시보드_업로드.bat으로 Cloud에 전달)
            with open(VALUATION_SNAPSHOT, "w", encoding="utf-8") as _f:
                json.dump({"saved": datetime.datetime.now().strftime("%Y-%m-%d"), "pe_spy": pe_spy, "pe_qqq": pe_qqq,
                           "baa": {"d": [d.strftime("%Y-%m-%d") for d in baa.index[-30:]], "v": [float(x) for x in baa.iloc[-30:]]},
                           "unrate": {"d": [d.strftime("%Y-%m-%d") for d in unrate.index[-24:]], "v": [float(x) for x in unrate.iloc[-24:]]}},
                          _f, ensure_ascii=False)
        except Exception:
            pass
    pe_spy = np.nan if pe_spy is None else pe_spy
    pe_qqq = np.nan if pe_qqq is None else pe_qqq
    baa = pd.Series(dtype=float) if baa is None else baa
    unrate = pd.Series(dtype=float) if unrate is None else unrate
    risk = get_risk_signal_data()           # ^TNX 포함
    divs = get_spy_dividend_history()
    nominal = get_spy_nominal_close()
    return dict(pe_spy=pe_spy, pe_qqq=pe_qqq, baa=baa, unrate=unrate, risk=risk, divs=divs, nominal=nominal, used_snap=used_snap, snap=snap)


def _valuation_cards(v):
    """밸류에이션 카드 목록 [(제목, 값, 상태, 설명)]."""
    pe_spy, pe_qqq, baa, unrate = v["pe_spy"], v["pe_qqq"], v["baa"], v["unrate"]
    risk, divs, nominal = v["risk"], v["divs"], v["nominal"]
    cards = []
    # ① 이익수익률 − 회사채 금리
    if pd.notna(pe_spy) and len(baa):
        ey = 100 / pe_spy
        b = float(baa.iloc[-1])
        gap = ey - b
        if gap >= 1:
            stt, txt = "🟢", f"주식이 회사채보다 {gap:.1f}%p 더 법니다. 주식이 상대적으로 싼 구간입니다."
        elif gap >= -1:
            stt, txt = "🟡", f"주식과 회사채의 수익률이 비슷합니다({gap:+.1f}%p). 주식이 특별히 싸지 않습니다."
        else:
            stt, txt = "🔴", f"회사채가 주식보다 {-gap:.1f}%p 더 줍니다. 주식이 채권 대비 비싼 구간입니다(2000년 닷컴버블 때도 이랬습니다)."
        cards.append(("① S&P500 이익수익률 − 회사채 금리", f"{gap:+.1f}%p",
                      stt, txt + f" (S&P500 PER {pe_spy:.1f}배 → 이익수익률 {ey:.1f}%, Baa 회사채 {b:.2f}%)"))
    # ② S&P500 배당수익률의 과거 위치
    try:
        if len(divs) and len(nominal):
            px_m = nominal.resample("ME").last().dropna()
            dy = []
            for d_, p_ in px_m.items():
                s_ = divs[(divs.index > d_ - pd.Timedelta(days=365)) & (divs.index <= d_)].sum()
                if s_ > 0 and p_ > 0:
                    dy.append((d_, s_ / p_ * 100))
            dy = pd.Series(dict(dy)).sort_index()
            if len(dy) > 24:
                cur = float(dy.iloc[-1])
                pct = float((dy < cur).mean() * 100)          # 배당수익률이 높을수록 쌈
                if pct >= 60:
                    stt = "🟢"
                elif pct >= 25:
                    stt = "🟡"
                else:
                    stt = "🔴"
                cards.append(("② S&P500 배당수익률의 과거 위치", f"{cur:.2f}%", stt,
                              f"{dy.index[0]:%Y}년 이후 {len(dy)}개월 중 하위 {pct:.0f}% 위치(낮을수록 비쌈). 주가÷배당 = {100 / cur:.0f}배. "
                              f"전략 C 기준선 1.33%보다 {'높아 공격' if cur > 1.33 else '낮아 방어'} 신호입니다. 이 기간 최저 {dy.min():.2f}%({dy.idxmin():%Y-%m}), 최고 {dy.max():.2f}%({dy.idxmax():%Y-%m})."))
    except Exception:
        pass
    # ③ 10년물 금리 급등
    if risk is not None and not risk.empty and "^TNX" in risk.columns:
        t = risk["^TNX"].dropna()
        if len(t) > 64:
            ch = float(t.iloc[-1] - t.iloc[-64])
            if ch >= 0.75:
                stt, txt = "⚠️", f"3개월 만에 {ch:+.2f}%p 급등. 켄 피셔가 경고한 '채권 금리가 갑자기 튀어 오르는' 상태로, 주식 하락 압력이 커집니다(2022년이 대표적)."
            elif ch >= 0.4:
                stt, txt = "🟡", f"3개월 {ch:+.2f}%p 상승. 금리가 빠르게 오르는 중이라 주의가 필요합니다."
            else:
                stt, txt = "🟢", f"3개월 {ch:+.2f}%p. 금리 급등 신호는 없습니다."
            cards.append(("③ 미국 10년물 금리 3개월 변화", f"{t.iloc[-1]:.2f}% ({ch:+.2f}%p)", stt, txt))
    # ④ 성장주 프리미엄
    if pd.notna(pe_spy) and pd.notna(pe_qqq):
        r = pe_qqq / pe_spy
        if r <= 1.25:
            stt, txt = "🟢", f"나스닥100이 S&P500보다 {(r - 1) * 100:.0f}%만 비쌉니다. 피셔 기준으로 성장주를 상대적으로 싸게 살 수 있는 구간입니다."
        elif r <= 1.6:
            stt, txt = "🟡", f"성장주 프리미엄 {(r - 1) * 100:.0f}%. 성장 기대만큼의 보통 수준입니다."
        else:
            stt, txt = "🔴", f"성장주 프리미엄 {(r - 1) * 100:.0f}%. 성장 기대가 가격에 많이 반영돼 있습니다."
        cards.append(("④ 성장주 프리미엄 (나스닥100 PER ÷ S&P500 PER)", f"{r:.2f}배", stt,
                      txt + f" (나스닥100 PER {pe_qqq:.1f}배, S&P500 PER {pe_spy:.1f}배)"))
    # ⑤ 실업률 (삼의 법칙)
    if len(unrate) > 15:
        m3 = unrate.rolling(3).mean()
        sahm = float(m3.iloc[-1] - m3.iloc[-13:-1].min())
        if sahm >= 0.5:
            stt, txt = "⚠️", (f"실업률 급등 신호(+{sahm:.2f}%p). 경기침체가 시작됐을 가능성이 큽니다. 다만 피셔는 이렇게 공포가 커질 때가 "
                              "오히려 주가 바닥에 가까운 경우가 많다고 봅니다. 추세 규칙으로 바닥 확인 후 대응하세요.")
        elif sahm >= 0.3:
            stt, txt = "🟡", f"실업률이 오르기 시작(+{sahm:.2f}%p). 경기 둔화를 지켜볼 구간입니다."
        else:
            stt, txt = "🟢", f"실업률 안정(+{sahm:.2f}%p). 고용 악화 신호는 없습니다."
        cards.append(("⑤ 실업률 변화 (삼의 법칙)", f"{unrate.iloc[-1]:.1f}% ({unrate.index[-1]:%Y-%m})", stt, txt))

    return cards


def render_valuation_board():
    """켄 피셔식 '지금 시장이 싼가 비싼가' 계기판 (타이밍 신호가 아니라 배경 판단용)."""
    st.markdown("켄 피셔가 『불변의 차트 90』에서 강조한 대로, 주가를 맞히려 하기보다 **지금 시장이 싼지 비싼지**를 여러 지표로 확인하는 화면입니다. "
                "매매 신호가 아니라 '지금 얼마나 조심해야 하나'를 보는 배경 정보이고, 실제 매매는 200일선 같은 추세 규칙으로 합니다.")
    _ph = st.empty()
    with _ph.container():
        with st.status("📥 PER·회사채 금리·배당·실업률 데이터를 불러오는 중입니다… (처음엔 5\\~20초, 이후 몇 시간은 바로 표시)",
                       expanded=True) as _stt:
            _v = _valuation_load()
            _stt.update(label="✅ 밸류에이션 데이터 불러오기 완료", state="complete", expanded=False)
    _ph.empty()

    pe_spy, pe_qqq, baa, unrate = _v["pe_spy"], _v["pe_qqq"], _v["baa"], _v["unrate"]
    used_snap, snap = _v["used_snap"], _v["snap"]
    cards = _valuation_cards(_v)
    if not cards:
        st.warning("밸류에이션 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        return
    if used_snap:
        st.info(f"ℹ️ 서버에서 실시간으로 받지 못한 {', '.join(used_snap)}은(는) PC에서 저장한 값({snap.get('saved', '날짜 모름')} 기준)을 썼습니다.")
    _missing = [n for n, ok in (("① 이익수익률−회사채", pd.notna(pe_spy) and len(baa)), ("④ 성장주 프리미엄", pd.notna(pe_spy) and pd.notna(pe_qqq)),
                                ("⑤ 실업률", len(unrate) > 15)) if not ok]
    if _missing:
        st.caption(f"⚠️ 데이터를 받지 못해 빠진 지표: {', '.join(_missing)} — 잠시 후 새로고침하거나, PC에서 대시보드를 한 번 연 뒤 대시보드_업로드.bat으로 올리면 저장값으로 표시됩니다.")
    nr = sum(1 for x in cards if x[2] in ("🔴", "⚠️"))
    ny = sum(1 for x in cards if x[2] == "🟡")
    if nr >= 3:
        st.error(f"🔴 **종합: 비싸고 긴장된 시장** — 비쌈·경고 {nr}개 · 보통 {ny}개. 새로 크게 사기보다 추세 규칙(손절선)을 엄격히 지킬 때입니다.")
    elif nr >= 1:
        st.warning(f"🟡 **종합: 일부 고평가·주의** — 비쌈·경고 {nr}개 · 보통 {ny}개. 몇 년 단위 기대수익은 평소보다 낮게 잡는 편이 안전합니다.")
    else:
        st.success(f"🟢 **종합: 부담 적음** — 비쌈·경고 {nr}개 · 보통 {ny}개. 밸류에이션 부담이 크지 않은 구간입니다.")
    # 두 장씩 한 줄로 그림 → 휴대폰에서 세로로 쌓여도 ①②③… 번호 순서가 유지됨
    for i, (title, val, stt, txt) in enumerate(cards):
        if i % 2 == 0:
            cols = st.columns(2)
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{stt} {title}**")
                st.markdown(f"<div style='font-size:1.5rem;font-weight:700'>{val}</div>", unsafe_allow_html=True)
                st.caption(txt)
    st.caption("출처: 야후 파이낸스(SPY·QQQ 후행 PER, ^TNX, SPY 배당·실제 종가) · 미국 연준 FRED(DBAA 무디스 Baa 회사채 금리, UNRATE 실업률). "
               "PER은 야후가 제공하는 ETF 후행 PER이라 다른 출처와 조금 다를 수 있습니다.")
    with st.expander("📖 읽는 법 · 켄 피셔의 한계 지적", expanded=False):
        st.markdown("""
| 지표 | 계산 | 🟢 / 🟡 / 🔴(⚠️) 기준 | 왜 보나 |
|---|---|---|---|
| ① 이익수익률 − 회사채 금리 | (1 ÷ S&P500 PER) − 무디스 Baa 회사채 금리 | +1%p 이상 / ±1%p / −1%p 미만 | 주식을 통째로 샀을 때 버는 비율을 안전한 회사채 이자와 비교. 금리 수준이 달라도 공정하게 비교됩니다 |
| ② 배당수익률의 과거 위치 | 최근 12개월 SPY 배당 ÷ 실제 종가, 1999년 이후 분포에서 위치 | 상위 40% / 중간 / 하위 25% | 배당수익률이 낮을수록 주가가 비쌈. 자사주 매입이 늘어 옛 기준(주가÷배당 22.7배)은 쓸 수 없어 **최근 25년 안에서의 상대 위치**로 봅니다 |
| ③ 10년물 금리 3개월 변화 | 지금 금리 − 63거래일 전 금리 | +0.4%p 미만 / +0.4\\~0.75%p / +0.75%p 이상 | 채권 금리가 갑자기 튀어 오르면 주식 할인율이 올라 주가에 부담. 2022년 하락장이 대표 사례 |
| ④ 성장주 프리미엄 | 나스닥100 PER ÷ S&P500 PER | 1.25배 이하 / 1.25\\~1.6배 / 1.6배 초과 | 성장주는 원래 더 비싼 게 정상이지만, 프리미엄이 25% 안쪽으로 좁혀지면 성장주를 싸게 살 기회(피셔의 1962·1976년 사례) |
| ⑤ 실업률 (삼의 법칙) | 최근 3개월 평균 실업률 − 직전 12개월 중 최저 3개월 평균 | +0.3%p 미만 / +0.3\\~0.5%p / +0.5%p 이상 | +0.5%p를 넘으면 경기침체가 시작된 경우가 많았습니다. 단, 주가는 경기보다 먼저 움직여 이때 이미 바닥 근처인 경우도 많습니다 |

**어떻게 쓰나**
- 이 계기판은 **'언제 사고팔지'가 아니라 '얼마나 조심해야 하나'**를 알려 줍니다. 🔴가 많아도 비싼 시장은 몇 년씩 더 오를 수 있고, 🟢가 많아도 더 빠질 수 있습니다.
- 실제 매매는 지금처럼 **추세 규칙(200일선 −3% 매도·+5% 재매수, 2026 혼합전략 월말 리밸런싱)**으로 하고, 이 화면은 기대수익을 얼마로 잡을지, 신규 자금을 한 번에 넣을지 나눠 넣을지 정할 때 참고합니다.

**켄 피셔의 한계 지적**: 이 지표들은 1987년 책 『불변의 차트 90』(원제 The Wall Street Waltz)의 관점입니다. 피셔 본인은 이후 『3개의 질문으로 주식시장을 이겨라』에서 "PER이 높다고 주가가 떨어지는 것은 아니다"라고 데이터로 반박했습니다. 밸류에이션은 몇 년에 걸친 기대수익을 가늠하는 데는 쓸모 있지만 타이밍 도구로는 약하다는 것이 그의 후기 입장입니다.
""")


RISK_TICKERS = ["^TNX", "^IRX", "^VIX", "^VIX3M", "HYG", "IEF", "DX-Y.NYB"]


@st.cache_data(ttl=3600, show_spinner=False)
def get_risk_signal_data():
    try:
        df = yf.download(RISK_TICKERS, period="2y", interval="1d", progress=False, auto_adjust=True)
        c = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
        c.index = pd.to_datetime(c.index).tz_localize(None) if getattr(c.index, "tz", None) else pd.to_datetime(c.index)
        return c.ffill()
    except Exception:
        return pd.DataFrame()


def _risk_cards(c):
    """위험 신호판 카드 목록 [(제목, 값, 상태, 설명)] — 신호판·시장위험진단 공용."""
    def _s(t):
        return c[t].dropna() if t in c.columns else pd.Series(dtype=float)

    cards = []
    # 1) 장단기 금리차 (10년 - 3개월)
    tnx, irx = _s("^TNX"), _s("^IRX")
    if len(tnx) and len(irx):
        sp = (tnx - irx).dropna()
        v, mn = sp.iloc[-1], sp.iloc[-252:].min()
        if v < 0:
            stt, txt = "⚠️", f"역전 상태({v:+.2f}%p). 단기 금리가 장기보다 높아 경기침체 경고로 봅니다. 역전이 풀리는 시점에 침체가 시작된 경우가 많았습니다."
        elif mn < 0:
            stt, txt = "⚠️", f"최근 1년 안에 역전(최저 {mn:+.2f}%p)됐다가 풀린 직후입니다. 과거 2001·2008·2020년 침체는 이 시기에 시작됐습니다."
        elif v < 0.5:
            stt, txt = "🟡", f"평탄({v:+.2f}%p). 정상이지만 여유가 크지 않습니다."
        else:
            stt, txt = "🟢", f"정상({v:+.2f}%p). 장기 금리가 단기보다 충분히 높아 경기 우려가 크지 않은 모양입니다."
        cards.append(("장단기 금리차 (10년 − 3개월)", f"{v:+.2f}%p", stt, txt))
    # 2) VIX 기간구조
    vix, vix3 = _s("^VIX"), _s("^VIX3M")
    if len(vix) and len(vix3):
        r = (vix / vix3).dropna().iloc[-1]
        lv = vix.iloc[-1]
        lvl = "매우 높음" if lv >= 30 else ("높음" if lv >= 20 else "평온")
        if r >= 1:
            stt, txt = "⚠️", f"단기 공포가 중기보다 큰 상태(비율 {r:.2f}). 급락장에서 나타납니다. VIX {lv:.1f}({lvl})."
        elif r >= 0.9:
            stt, txt = "🟡", f"긴장(비율 {r:.2f}). 단기 불안이 커지는 중입니다. VIX {lv:.1f}({lvl})."
        else:
            stt, txt = "🟢", f"안정(비율 {r:.2f}). 평소처럼 먼 미래 불확실성이 더 큰 정상 구조입니다. VIX {lv:.1f}({lvl})."
        cards.append(("VIX 기간구조 (VIX ÷ 3개월 VIX)", f"{r:.2f}", stt, txt))
    # 3) 신용 위험 (HYG ÷ IEF)
    hyg, ief = _s("HYG"), _s("IEF")
    if len(hyg) and len(ief):
        cr = (hyg / ief).dropna()
        ma50, ma200 = cr.iloc[-50:].mean(), cr.iloc[-200:].mean()
        ch3 = (cr.iloc[-1] / cr.iloc[-64] - 1) * 100 if len(cr) > 64 else np.nan
        if cr.iloc[-1] < ma200 and ch3 == ch3 and ch3 < 0:
            stt, txt = "⚠️", f"하이일드채가 국채보다 약해지는 중(3개월 {ch3:+.1f}%, 200일선 아래). 기업 신용 불안이 커지고 있습니다."
        elif cr.iloc[-1] < ma50:
            stt, txt = "🟡", f"단기적으로 약해짐(50일선 아래, 3개월 {ch3:+.1f}%). 아직 추세 전환은 아닙니다."
        else:
            stt, txt = "🟢", f"안정(3개월 {ch3:+.1f}%). 투자자들이 위험한 회사채도 잘 사고 있습니다."
        cards.append(("신용 위험 (하이일드 ÷ 국채)", f"{ch3:+.1f}% (3개월)", stt, txt))
    # 4) 달러 강도
    dxy = _s("DX-Y.NYB")
    if len(dxy) > 200:
        ma200 = dxy.iloc[-200:].mean()
        ch3 = (dxy.iloc[-1] / dxy.iloc[-64] - 1) * 100
        if ch3 > 5:
            stt, txt = "⚠️", f"급격한 강세(3개월 {ch3:+.1f}%). 신흥국·원자재·위험자산에 부담이 되는 경우가 많습니다."
        elif dxy.iloc[-1] > ma200:
            stt, txt = "🟡", f"강세(200일선 위, 3개월 {ch3:+.1f}%). 위험자산에 약한 부담입니다."
        else:
            stt, txt = "🟢", f"약세·안정(200일선 아래, 3개월 {ch3:+.1f}%). 위험자산에 우호적인 편입니다."
        cards.append(("달러 강도 (달러지수)", f"{dxy.iloc[-1]:.1f}", stt, txt))

    return cards


DIAG_MATRIX = {   # (위험 신호판 0평온/1긴장/2위험, 밸류 0부담적음/1일부고평가/2비싸고긴장) → (제목, 할 일)
    (0, 0): ("가장 편안한 구간", "신규 자금 평소대로 · 기대수익 평소 가정"),
    (0, 1): ("흔한 구간 (상승장 중반)", "신규 자금 평소대로 · 장기 기대수익은 한 단계 보수적으로"),
    (0, 2): ("비싸지만 아직 평온", "목돈은 2&#126;3회 분할 · 위성 자산 확대 보류"),
    (1, 0): ("싼데 흔들림", "조정이 기회가 되기 쉬운 곳 · 신규 자금은 분할로 꾸준히"),
    (1, 1): ("주의 구간", "켜진 지표 주 1회 추적 · 목돈 분할 · 위성 자산 매도 기준 점검"),
    (1, 2): ("경계 구간", "신규 목돈 보류·분할 · 위성 자산 규칙 엄수"),
    (2, 0): ("급락 진행 중, 가격은 싸짐", "규칙대로 방어 · 공포 매도 금지 · 바닥 확인은 추세 규칙에 맡김"),
    (2, 1): ("위기 진행 가능성", "혼합전략 방어 전환 여부 확인 · 위성 자산 신규 매수 중단"),
    (2, 2): ("가장 위험한 조합 (2000·2007년형)", "규칙 엄수 · 레버리지 금지 · 신규 자금은 현금 대기 후 규칙 재진입에 맞춤"),
}
DIAG_BG = {(0, 0): "#e8f5ec", (0, 1): "#f3f8ee", (1, 0): "#f3f8ee", (0, 2): "#fdf5e6", (1, 1): "#fdf5e6", (2, 0): "#fdf5e6",
           (1, 2): "#fdecea", (2, 1): "#fdecea", (2, 2): "#f9d9d5"}


def render_risk_diagnosis():
    """🩺 시장위험진단: 위험 신호판(긴장) × 밸류에이션(가격 부담)을 한 화면에서 겹쳐 읽기."""
    st.markdown("위험 신호판(지금 시장의 **긴장**)과 시장 밸류에이션(지금 시장의 **가격 부담**)을 한 화면에서 겹쳐 봅니다. "
                "둘 다 매매 신호가 아니라 **규칙 밖의 결정**(신규 자금 투입 방식, 기대수익 가정, 위성 자산 비중)을 정할 때 참고하는 배경 정보입니다.")
    # ── 1) 두 화면 비교표 ──
    _th = "background:#0f2747;color:#fff;font-weight:700;padding:9px 12px;text-align:left;"
    _td = "padding:9px 12px;border-bottom:1px solid #e3e6eb;vertical-align:top;"
    _rows = [
        ("묻는 질문", "지금 시장이 얼마나 <b>긴장</b>했나?", "지금 시장이 <b>싼가 비싼가</b>?"),
        ("시간 단위", "몇 주 &#126; 몇 달 (빠르게 바뀜)", "몇 년 (천천히 바뀜)"),
        ("지표 수", "4개: 장단기 금리차, VIX 기간구조, 신용 위험, 달러 강도",
         "5개: 이익수익률−회사채, 배당수익률 위치, 10년물 급등, 성장주 프리미엄, 실업률(삼의 법칙)"),
        ("판정 색", "<span style='color:#1f8a4c;font-weight:800'>🟢 정상</span> · <span style='color:#c98500;font-weight:800'>🟡 주의</span> · "
                   "<span style='color:#d1453b;font-weight:800'>⚠️ 경고</span>",
         "<span style='color:#1f8a4c;font-weight:800'>🟢 쌈·안정</span> · <span style='color:#c98500;font-weight:800'>🟡 보통</span> · "
         "<span style='color:#d1453b;font-weight:800'>🔴 비쌈 / ⚠️ 경고</span>"),
        ("종합", "평온 / 긴장 / 위험", "부담 적음 / 일부 고평가·주의 / 비싸고 긴장된 시장"),
        ("쓰임", "\"왜 지금 방어로 갔나 / 갈 수 있나\"를 이해, 신규 자금 투입 속도", "몇 년 기대수익을 얼마로 잡을지, 계획의 보수성"),
        ("출처", "^TNX, ^IRX, ^VIX, ^VIX3M, HYG, IEF, DX-Y.NYB", "SPY·QQQ 후행 PER, FRED DBAA·UNRATE, ^TNX, SPY 배당·실제 종가"),
    ]
    _h = ["<div style='overflow-x:auto;border:1px solid #e3e6eb;border-radius:10px;margin:6px 0 10px'>",
          "<table style='border-collapse:collapse;width:100%;min-width:560px;font-size:0.93rem'>",
          f"<tr><th style='{_th}width:16%'>구분</th><th style='{_th}width:42%'>⚠️ 시장 위험 신호판</th><th style='{_th}'>🧮 시장 밸류에이션</th></tr>"]
    for k, (a_, b_, c_) in enumerate(_rows):
        _bg = "background:#fafbfc;" if k % 2 else ""
        _h.append(f"<tr><td style='{_td}{_bg}font-weight:700'>{a_}</td><td style='{_td}{_bg}'>{b_}</td><td style='{_td}{_bg}'>{c_}</td></tr>")
    _h.append("</table></div>")
    st.markdown("".join(_h), unsafe_allow_html=True)
    st.markdown("<div style='background:#f4f6f9;border-left:4px solid #0f2747;border-radius:4px;padding:10px 14px;margin:4px 0 14px;font-size:0.92rem'>"
                "<b>비유로 보면</b> — 위험 신호판은 <b>날씨 예보</b>(지금 비바람이 오는가), 밸류에이션은 <b>지형</b>(지금 서 있는 곳이 얼마나 높은가)입니다. "
                "높은 곳에서 폭풍을 만나면 가장 위험하고, 낮은 곳에서 맑은 날이면 가장 편안합니다. 하지만 높은 곳에서도 맑은 날은 몇 년씩 이어질 수 있습니다.</div>",
                unsafe_allow_html=True)

    # ── 2) 지금 판정 ──
    _ph = st.empty()
    with _ph.container():
        with st.status("📥 위험 신호·밸류에이션 데이터를 불러오는 중입니다… (처음엔 10\\~20초, 이후 1시간은 바로 표시)", expanded=True) as _stt:
            c = get_risk_signal_data()
            _v = _valuation_load()
            _stt.update(label="✅ 진단 데이터 불러오기 완료", state="complete", expanded=False)
    _ph.empty()
    rc = _risk_cards(c) if (c is not None and not c.empty) else []
    vc = _valuation_cards(_v)
    if not rc and not vc:
        st.warning("진단 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        return
    nw = sum(1 for x in rc if x[2] == "⚠️"); nc = sum(1 for x in rc if x[2] == "🟡")
    r_i = 2 if nw >= 2 else (1 if (nw == 1 or nc >= 2) else 0)
    nr = sum(1 for x in vc if x[2] in ("🔴", "⚠️")); ny = sum(1 for x in vc if x[2] == "🟡")
    v_i = 2 if nr >= 3 else (1 if nr >= 1 else 0)
    r_lab = ["평온", "긴장", "위험"][r_i]; v_lab = ["부담 적음", "일부 고평가·주의", "비싸고 긴장된 시장"][v_i]
    _col = ["#1f8a4c", "#c98500", "#d1453b"]

    def _lst(cards, bad):
        on = [f"{x[2]} {x[0]} <b>{x[1]}</b>" for x in cards if x[2] in bad]
        return "<br>".join(on) if on else "켜진 지표 없음"

    st.markdown("#### 🩺 지금 진단")
    c1, c2 = st.columns(2)
    for col, ttl, lab, idx, cnt, body in (
            (c1, "⚠️ 시장 위험 신호판", r_lab, r_i, f"경고 {nw} · 주의 {nc} (지표 {len(rc)}개)", _lst(rc, ("⚠️", "🟡"))),
            (c2, "🧮 시장 밸류에이션", v_lab, v_i, f"비쌈·경고 {nr} · 보통 {ny} (지표 {len(vc)}개)", _lst(vc, ("🔴", "⚠️", "🟡")))):
        with col:
            st.markdown(
                f"<div style='border:2px solid {_col[idx]};border-radius:12px;padding:12px 14px;margin-bottom:8px;background:#fff'>"
                f"<div style='font-weight:800;color:#0f2747'>{ttl}</div>"
                f"<div style='font-size:1.6rem;font-weight:900;color:{_col[idx]};margin:2px 0'>{lab}</div>"
                f"<div style='font-size:0.85rem;color:#475569;margin-bottom:6px'>{cnt}</div>"
                f"<div style='font-size:0.86rem;color:#1e293b;line-height:1.6'>{body}</div></div>", unsafe_allow_html=True)
    if _v.get("used_snap"):
        st.caption(f"ℹ️ 서버에서 받지 못한 {', '.join(_v['used_snap'])}은(는) PC 저장값({_v['snap'].get('saved', '날짜 모름')} 기준)을 썼습니다.")

    # ── 3) 3 × 3 판단표 (지금 칸 강조) ──
    st.markdown("#### 🧭 두 화면을 겹쳐 읽기 — 3 × 3 판단표")
    _hd = "background:#eef2f7;font-weight:800;color:#0f2747;padding:8px;text-align:center;border:1px solid #fff;"
    _m = ["<div style='overflow-x:auto;margin:4px 0 8px'><table style='border-collapse:separate;border-spacing:4px;width:100%;min-width:600px;font-size:0.86rem'>",
          f"<tr><th style='{_hd}'></th>" + "".join(f"<th style='{_hd}'>🧮 {x}</th>" for x in ["부담 적음", "일부 고평가·주의", "비싸고 긴장된 시장"]) + "</tr>"]
    for ri, rl in enumerate(["평온", "긴장", "위험"]):
        _m.append(f"<tr><td style='{_hd}'>⚠️ {rl}</td>")
        for vi in range(3):
            t1, t2 = DIAG_MATRIX[(ri, vi)]
            on = (ri, vi) == (r_i, v_i)
            _st = (f"background:{DIAG_BG[(ri, vi)]};padding:8px 10px;text-align:center;vertical-align:middle;border-radius:8px;line-height:1.5;"
                   + ("border:3px solid #c2410c;box-shadow:0 0 0 2px #fed7aa;" if on else "border:1px solid #e3e6eb;opacity:0.85;"))
            _tag = ("<div><span style='background:#c2410c;color:#fff;border-radius:6px;padding:1px 8px;font-size:0.78rem;font-weight:800'>지금</span></div>"
                    if on else "")
            _m.append(f"<td style='{_st}'>{_tag}<b>{t1}</b><br><span style='color:#475569'>{t2}</span></td>")
        _m.append("</tr>")
    _m.append("</table></div>")
    st.markdown("".join(_m), unsafe_allow_html=True)
    t1, t2 = DIAG_MATRIX[(r_i, v_i)]
    st.markdown(
        f"<div style='border:3px solid #0f2747;border-radius:12px;padding:12px 16px;background:#fff;margin:6px 0 10px'>"
        f"<div style='font-weight:800;color:#0f2747;font-size:1.02rem'>📍 지금 칸: 신호판 '{r_lab}' × 밸류 '{v_lab}' → {t1}</div>"
        f"<div style='font-size:0.95rem;margin-top:6px'><b>규칙 밖 결정</b>: {t2}</div>"
        f"<div style='font-size:0.9rem;color:#dc2626;font-weight:700;margin-top:6px'>2026 혼합전략(월말 리밸런싱·전략 A·B·C 공격/방어)과 개별 종목·ETF의 200일선 보유 기준은 "
        f"어느 칸이든 <b>그대로</b> 따릅니다.</div></div>", unsafe_allow_html=True)
    st.caption("각 지표의 값과 해석은 위 '보기 선택'의 ⚠️ 시장 위험 신호판 · 🧮 시장 밸류에이션에서 자세히 볼 수 있습니다. "
               "판정 기준은 백테스트로 검증하지 않은 참고값이며, 비싸고 긴장된 시장이 몇 년씩 더 오른 적도 있습니다. "
               "자세한 해설: 보고서 '대시보드로 보는 위험진단법'(2026-10-15).")


def render_risk_board():
    """③ 시장 위험 신호판: 장단기 금리차·VIX 기간구조·신용·달러."""
    st.markdown("가격만 보여 주는 매크로 시황판과 달리, **과거 위기 전에 먼저 움직였던 지표**를 해석과 함께 보여 줍니다. "
                "매매 신호가 아니라 '지금 시장이 얼마나 긴장했나'를 보는 참고 화면입니다.")
    _ph = st.empty()
    with _ph.container():
        with st.status("📥 금리·VIX·채권·달러 데이터를 불러오는 중입니다… (처음엔 5\\~15초, 이후 1시간은 바로 표시)", expanded=True) as _stt:
            st.caption("1분 넘게 이 상태면 인터넷 연결이나 야후 서버 문제일 수 있으니 새로고침(F5)해 주세요.")
            c = get_risk_signal_data()
            _stt.update(label="✅ 위험 신호 데이터 불러오기 완료", state="complete", expanded=False)
    _ph.empty()
    if c is None or c.empty:
        st.warning("위험 신호 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        return

    cards = _risk_cards(c)
    if not cards:
        st.warning("표시할 지표가 없습니다.")
        return
    nw = sum(1 for x in cards if x[2] == "⚠️")
    nc = sum(1 for x in cards if x[2] == "🟡")
    if nw >= 2:
        st.error(f"🔴 **종합: 위험** — 경고 {nw}개 · 주의 {nc}개. 여러 지표가 동시에 긴장 신호를 보내고 있습니다.")
    elif nw == 1 or nc >= 2:
        st.warning(f"🟡 **종합: 긴장** — 경고 {nw}개 · 주의 {nc}개. 일부 지표가 불안 신호를 보내고 있습니다.")
    else:
        st.success(f"🟢 **종합: 평온** — 경고 {nw}개 · 주의 {nc}개. 시장 전반에 큰 긴장 신호는 없습니다.")
    # 두 장씩 한 줄로 그림 → 휴대폰에서 세로로 쌓여도 ①②③… 번호 순서가 유지됨
    for i, (title, val, stt, txt) in enumerate(cards):
        if i % 2 == 0:
            cols = st.columns(2)
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{stt} {title}**")
                st.markdown(f"<div style='font-size:1.5rem;font-weight:700'>{val}</div>", unsafe_allow_html=True)
                st.caption(txt)
    st.caption(f"기준일 {c.index[-1].strftime('%Y-%m-%d')} · 출처: 야후 파이낸스 (^TNX, ^IRX, ^VIX, ^VIX3M, HYG, IEF, DX-Y.NYB)")
    with st.expander("📖 읽는 법", expanded=False):
        st.markdown("""
| 지표 | 계산 | 🟢 / 🟡 / ⚠️ 기준 | 왜 보나 |
|---|---|---|---|
| 장단기 금리차 | 미국 10년물 금리 − 3개월물 금리 | 0.5%p 이상 / 0\\~0.5%p / 마이너스(역전) 또는 최근 1년 내 역전 후 해소 | 역전은 대표적인 경기침체 선행 신호. 실제 침체는 역전이 **풀린 뒤** 시작된 경우가 많았습니다 |
| VIX 기간구조 | VIX ÷ 3개월 VIX | 0.9 미만 / 0.9\\~1 / 1 이상 | 평소엔 먼 미래 불안이 더 커서 1보다 작습니다. 1을 넘으면 '지금 당장'이 무서운 급락장입니다 |
| 신용 위험 | 하이일드 회사채(HYG) ÷ 중기국채(IEF) | 50일선 위 / 50일선 아래 / 200일선 아래 + 3개월 하락 | 위기 전에는 위험한 회사채부터 팔립니다. 주식보다 먼저 움직이는 경우가 많습니다 |
| 달러 강도 | 달러지수 | 200일선 아래 / 200일선 위 / 3개월 +5% 이상 급등 | 달러가 급하게 오르면 세계 자금이 위험자산에서 빠지는 경우가 많습니다 |

- **종합**: 경고 2개 이상이면 🔴 위험, 경고 1개 또는 주의 2개 이상이면 🟡 긴장, 그 밖에는 🟢 평온입니다.
- **활용**: 이 신호로 매매하지 않습니다. 2026 혼합전략은 카나리아(TIP·배당수익률)로 공격/방어를 정하고, 이 화면은 "왜 지금 방어로 갔는지 / 앞으로 갈 수 있는지"를 이해하는 배경 정보입니다.
- **한계**: 금리차 역전은 침체를 맞힌 적이 많지만 시점은 6개월\\~2년으로 들쭉날쭉했고, 틀린 적도 있습니다. 한 지표보다 여러 지표가 동시에 켜질 때를 더 의미 있게 보세요.
""")


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_ndx_tickers():
    """나스닥100 구성 종목: 위키피디아 표에서 자동 갱신하고, 실패하면 내장 목록을 사용합니다."""
    try:
        import requests
        from io import StringIO
        r = requests.get("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
                         headers={"User-Agent": "Mozilla/5.0 (asset-allocation-dashboard)"}, timeout=10)
        r.raise_for_status()
        for t in pd.read_html(StringIO(r.text)):
            if "Ticker" in [str(c) for c in t.columns]:
                tick = [str(x).strip().replace(".", "-") for x in t["Ticker"].dropna().tolist()]
                tick = [x for x in tick if x and x.replace("-", "").isalnum()]
                if 90 <= len(tick) <= 110:
                    return list(dict.fromkeys(tick)), "auto"
    except Exception:
        pass
    return list(NDX_FALLBACK), "fallback"


GICS_SECTOR_KR = {
    "Information Technology": "정보기술", "Communication Services": "커뮤니케이션",
    "Consumer Discretionary": "경기소비재", "Consumer Staples": "필수소비재", "Health Care": "헬스케어",
    "Financials": "금융", "Industrials": "산업재", "Energy": "에너지", "Materials": "소재",
    "Utilities": "유틸리티", "Real Estate": "부동산",
}
ICB_KR = {
    # ICB Industry
    "Technology": "기술", "Telecommunications": "통신", "Basic Materials": "소재",
    # ICB Subsector (위키피디아 나스닥100 표 기준)
    "Software": "소프트웨어", "Computer Software": "소프트웨어", "Diversified Commercial Services": "상업 서비스",
    "Catalog/Specialty Distribution": "온라인·전문 유통", "Electric Utilities": "전력", "Computer Hardware": "컴퓨터 하드웨어",
    "Industrial Machinery": "산업기계", "Ordnance & Accessories": "방산 장비", "Oil Equipment & Services": "석유 장비·서비스",
    "Transportation Services": "운송 서비스", "Garments & Clothing": "의류", "Computer Communications Equipment": "네트워크 장비",
    "Cable & Other Pay Television Services": "케이블·유료방송", "Retail": "유통", "Computer Services": "IT 서비스",
    "Department/Specialty Retail Stores": "백화점·전문점", "Railroads": "철도", "Medical/Dental Instruments": "의료기기",
    "Oil & Gas Production": "석유·가스 생산", "Power Generation": "발전", "Construction & Materials": "건설·자재",
    "Military, Government, Technical": "정부·기술 서비스", "Computer Peripheral Equipment": "컴퓨터 주변기기",
    "Medical Electronics": "의료 전자기기", "Aerospace": "항공우주", "Diversified Industrials": "복합 산업재",
    "Industrial Specialties": "산업 특수재", "Electronic Components": "전자부품", "Packaged Foods": "가공식품",
    "Major Chemicals": "화학", "Communication Equipment": "통신장비", "Hotels/Resorts": "호텔·리조트",
    "Consumer Electronics": "가전·전자기기", "Specialty Retailers": "전문 유통", "Trucking": "트럭 운송",
    "Motor Vehicles": "자동차", "Automobiles & Parts": "자동차·부품", "EDP Services": "데이터 처리 서비스",
    "Clothing/Shoe/Accessory Stores": "의류·신발 매장", "Telecommunications Services": "통신 서비스",
    "Restaurants": "외식", "Miscellaneous Amusement & Recreation Services": "레저·오락", "Entertainment": "엔터테인먼트",
    "Conventional Electricity": "전력", "Semiconductors": "반도체", "Biotechnology": "바이오", "Soft Drinks": "음료",
    "Pharmaceuticals": "제약", "Internet": "인터넷", "Medical Equipment": "의료기기",
}

GICS_SUB_KR = {
    "Semiconductors": "반도체", "Semiconductor Materials & Equipment": "반도체 장비",
    "Application Software": "응용 소프트웨어", "Systems Software": "시스템 소프트웨어",
    "Interactive Media & Services": "인터넷 플랫폼", "Broadline Retail": "온라인·종합 유통",
    "Technology Hardware, Storage & Peripherals": "하드웨어·저장장치", "Communications Equipment": "통신장비",
    "Electronic Components": "전자부품", "Electronic Equipment & Instruments": "전자장비",
    "IT Consulting & Other Services": "IT 서비스", "Internet Services & Infrastructure": "인터넷 인프라",
    "Biotechnology": "바이오", "Pharmaceuticals": "제약", "Health Care Equipment": "의료기기",
    "Health Care Supplies": "의료소모품", "Life Sciences Tools & Services": "생명과학 도구",
    "Health Care Distributors": "의약품 유통", "Managed Health Care": "건강보험",
    "Movies & Entertainment": "영화·엔터테인먼트", "Cable & Satellite": "케이블·위성",
    "Integrated Telecommunication Services": "통신 서비스", "Wireless Telecommunication Services": "무선통신",
    "Interactive Home Entertainment": "게임", "Publishing": "출판", "Advertising": "광고",
    "Automobile Manufacturers": "자동차", "Hotels, Resorts & Cruise Lines": "호텔·크루즈",
    "Restaurants": "외식", "Apparel, Accessories & Luxury Goods": "의류·명품",
    "Other Specialty Retail": "전문 유통", "Home Improvement Retail": "주택용품 유통",
    "Consumer Staples Merchandise Retail": "할인점", "Soft Drinks & Non-alcoholic Beverages": "음료",
    "Packaged Foods & Meats": "가공식품", "Food Retail": "식품 유통", "Food Distributors": "식품 유통",
    "Distillers & Vintners": "주류", "Agricultural & Farm Machinery": "농기계",
    "Electric Utilities": "전력", "Multi-Utilities": "종합 유틸리티",
    "Rail Transportation": "철도", "Air Freight & Logistics": "항공화물·물류",
    "Trading Companies & Distributors": "산업재 유통", "Industrial Machinery & Supplies & Components": "산업기계",
    "Construction Machinery & Heavy Transportation Equipment": "건설기계", "Aerospace & Defense": "항공우주·방산",
    "Research & Consulting Services": "리서치·컨설팅", "Human Resource & Employment Services": "인사·고용 서비스",
    "Diversified Support Services": "지원 서비스", "Environmental & Facilities Services": "환경·시설 서비스",
    "Data Processing & Outsourced Services": "데이터 처리", "Financial Exchanges & Data": "거래소·금융정보",
    "Transaction & Payment Processing Services": "결제 서비스", "Specialty Chemicals": "특수화학",
    "Industrial Gases": "산업용 가스", "Oil & Gas Exploration & Production": "석유·가스 개발",
    "Oil & Gas Equipment & Services": "석유 장비", "Real Estate Services": "부동산 서비스",
    "Specialized REITs": "특수 리츠", "Electrical Components & Equipment": "전기장비",
    "Heavy Electrical Equipment": "중전기", "Diversified Banks": "은행", "Consumer Finance": "소비자금융",
    "Asset Management & Custody Banks": "자산운용", "Investment Banking & Brokerage": "증권",
    "Leisure Facilities": "레저시설", "Homebuilding": "주택건설", "Casinos & Gaming": "카지노",
}


GICS_SUB_KR.update({
    "Multi-Sector Holdings": "복합 지주사", "Integrated Oil & Gas": "종합 석유", "Oil & Gas Refining & Marketing": "정유",
    "Oil & Gas Storage & Transportation": "석유·가스 운송", "Coal & Consumable Fuels": "석탄·연료",
    "Property & Casualty Insurance": "손해보험", "Life & Health Insurance": "생명보험", "Multi-line Insurance": "종합보험",
    "Insurance Brokers": "보험중개", "Reinsurance": "재보험", "Regional Banks": "지역은행",
    "Diversified Financial Services": "종합 금융", "Specialized Finance": "특수 금융", "Mortgage REITs": "모기지 리츠",
    "Personal Care Products": "개인용품", "Household Products": "생활용품", "Tobacco": "담배", "Brewers": "맥주",
    "Agricultural Products & Services": "농산물", "Drug Retail": "약국", "Apparel Retail": "의류 소매", "Footwear": "신발",
    "Automotive Retail": "자동차부품 소매", "Computer & Electronics Retail": "전자제품 소매", "Automotive Parts & Equipment": "자동차부품",
    "Health Care Services": "헬스케어 서비스", "Health Care Facilities": "병원", "Health Care Technology": "헬스케어 IT",
    "Industrial Conglomerates": "복합기업", "Building Products": "건축자재", "Construction & Engineering": "건설·엔지니어링",
    "Passenger Airlines": "항공사", "Cargo Ground Transportation": "화물 운송", "Marine Transportation": "해운",
    "Copper": "구리", "Gold": "금광", "Steel": "철강", "Aluminum": "알루미늄", "Diversified Metals & Mining": "광업",
    "Fertilizers & Agricultural Chemicals": "비료", "Commodity Chemicals": "범용 화학", "Diversified Chemicals": "종합 화학",
    "Construction Materials": "건축 소재", "Paper & Plastic Packaging Products & Materials": "포장재",
    "Metal, Glass & Plastic Containers": "용기", "Retail REITs": "리테일 리츠", "Industrial REITs": "물류 리츠",
    "Multi-Family Residential REITs": "임대주택 리츠", "Single-Family Residential REITs": "단독주택 리츠",
    "Health Care REITs": "헬스케어 리츠", "Office REITs": "오피스 리츠", "Self-Storage REITs": "창고 리츠",
    "Telecom Tower REITs": "통신탑 리츠", "Data Center REITs": "데이터센터 리츠", "Hotel & Resort REITs": "호텔 리츠",
    "Timber REITs": "산림 리츠", "Other Specialized REITs": "기타 리츠", "Gas Utilities": "가스", "Water Utilities": "수도",
    "Independent Power Producers & Energy Traders": "발전사", "Renewable Electricity": "신재생 발전",
    "Electronic Manufacturing Services": "전자 위탁생산", "Technology Distributors": "IT 유통", "Leisure Products": "레저용품",
    "Housewares & Specialties": "생활 잡화", "Home Furnishings": "가구", "Consumer Electronics": "가전",
    "Distributors": "유통", "Broadcasting": "방송", "Education Services": "교육", "Specialized Consumer Services": "생활 서비스",
    "Security & Alarm Services": "보안", "Office Services & Supplies": "사무용품", "Airport Services": "공항",
    "Diversified Capital Markets": "종합 자본시장", "Health Care Equipment & Supplies": "의료기기",
})


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_ndx_sectors():
    """나스닥100 구성 종목의 GICS 업종·세부업종(위키피디아). 실패하면 빈 dict."""
    try:
        import requests
        from io import StringIO
        r = requests.get("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
                         headers={"User-Agent": "Mozilla/5.0 (asset-allocation-dashboard)"}, timeout=10)
        r.raise_for_status()
        for t in pd.read_html(StringIO(r.text)):
            cols = [str(c) for c in t.columns]
            low = [c.lower() for c in cols]
            if "Ticker" not in cols:
                continue
            sub_i = next((i for i, c in enumerate(low) if "sub" in c), None)
            ind_i = next((i for i, c in enumerate(low) if ("industry" in c or "sector" in c) and "sub" not in c), None)
            if sub_i is None and ind_i is None:
                continue
            sc = t.columns[ind_i] if ind_i is not None else None
            sub = t.columns[sub_i] if sub_i is not None else None
            out = {}
            for _, row in t.iterrows():
                tk = str(row["Ticker"]).strip().replace(".", "-")
                sec = str(row[sc]).strip() if sc is not None else ""
                sb = str(row[sub]).strip() if sub is not None else ""
                sec = "" if sec == "nan" else sec
                sb = "" if sb == "nan" else sb
                sec_kr = GICS_SECTOR_KR.get(sec) or ICB_KR.get(sec) or sec
                sb_kr = GICS_SUB_KR.get(sb) or ICB_KR.get(sb) or sb
                out[tk] = (sec_kr, sb_kr)
            if len(out) >= 90:
                return out
    except Exception:
        pass
    return {}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_sp500_universe():
    """S&P500 구성 종목과 GICS 업종·세부업종(위키피디아). 실패하면 ([], {})."""
    try:
        import requests
        from io import StringIO
        r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                         headers={"User-Agent": "Mozilla/5.0 (asset-allocation-dashboard)"}, timeout=15)
        r.raise_for_status()
        for t in pd.read_html(StringIO(r.text)):
            cols = [str(c) for c in t.columns]
            if "Symbol" not in cols:
                continue
            sec_c = next((c for c in t.columns if "sector" in str(c).lower()), None)
            sub_c = next((c for c in t.columns if "sub" in str(c).lower()), None)
            nm_c = next((c for c in t.columns if str(c).lower() in ("security", "company", "name")), None)
            tick, out, names = [], {}, {}
            for _, row in t.iterrows():
                tk = str(row["Symbol"]).strip().replace(".", "-")
                if not tk or not tk.replace("-", "").isalnum():
                    continue
                tick.append(tk)
                sec = str(row[sec_c]).strip() if sec_c is not None else ""
                sb = str(row[sub_c]).strip() if sub_c is not None else ""
                sec = "" if sec == "nan" else sec
                sb = "" if sb == "nan" else sb
                out[tk] = (GICS_SECTOR_KR.get(sec, sec), GICS_SUB_KR.get(sb, sb))
                nm = str(row[nm_c]).strip() if nm_c is not None else ""
                if nm and nm != "nan":
                    names[tk] = (nm, f"{out[tk][0]} / {out[tk][1]}")
            if 450 <= len(tick) <= 520:
                return list(dict.fromkeys(tick)), out, names
    except Exception:
        pass
    return [], {}, {}


KOSPI200_CSV = "kospi200.csv"


@st.cache_data(ttl=3600, show_spinner=False)
def get_kospi200_universe(mtime=0):
    """PC에서 make_kospi200_list.py로 만든 kospi200.csv를 읽음 (한국거래소 데이터는 Cloud에서 막히는 경우가 많아 파일 방식).
    반환: (야후 티커 목록 [코드.KS], 업종 {티커:(업종, 세부업종)}, 이름 {티커:(종목명, 업종)}, 시가총액 {티커: 원}, 기준일)"""
    try:
        df = pd.read_csv(KOSPI200_CSV, dtype={"code": str}, encoding="utf-8-sig")
    except Exception:
        return [], {}, {}, {}, ""
    df["code"] = df["code"].str.zfill(6)
    tk = [c + ".KS" for c in df["code"]]
    sec = {t: (str(a) if a == a else "", str(b) if b == b else "") for t, a, b in zip(tk, df.get("sector", ""), df.get("industry", ""))}
    names = {t: (n, sec[t][1] or sec[t][0]) for t, n in zip(tk, df["name"])}
    mcap = {t: float(v) for t, v in zip(tk, df.get("marcap", np.nan)) if v == v}
    asof = str(df["asof"].iloc[0]) if "asof" in df.columns else ""
    return tk, sec, names, mcap, asof


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_ndx_market_caps(tickers):
    """나스닥100 종목 시가총액(달러). 야후 fast_info → 실패 시 info. 6시간 저장."""
    from concurrent.futures import ThreadPoolExecutor

    def _one(t):
        try:
            tk = yf.Ticker(t)
            mc = None
            try:
                fi = tk.fast_info
                mc = fi.get("marketCap") if hasattr(fi, "get") else None
                if not mc:
                    mc = getattr(fi, "market_cap", None)
            except Exception:
                mc = None
            if not mc:
                mc = (tk.info or {}).get("marketCap")
            return t, float(mc) if mc else np.nan
        except Exception:
            return t, np.nan
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(ex.map(_one, list(tickers)))


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_ndx_sectors_yahoo(tickers):
    """위키피디아 업종표를 못 읽었을 때 야후 종목 정보(sector·industry)로 대체."""
    from concurrent.futures import ThreadPoolExecutor

    def _one(t):
        try:
            inf = yf.Ticker(t).info or {}
            return t, (inf.get("sector") or "", inf.get("industry") or "")
        except Exception:
            return t, ("", "")
    out = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for t, (sec, ind) in ex.map(_one, list(tickers)):
            if sec or ind:
                out[t] = (GICS_SECTOR_KR.get(sec, sec), ind)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def get_ndx_daily_metrics(tickers, bench="QQQ"):
    """나스닥100 종목 일봉으로 수익률·52주 고점 대비·200일선·QQQ 대비·변동성·거래대금 변화·상태를 계산."""
    tickers = list(tickers)
    dl = list(dict.fromkeys(tickers + [bench]))
    start = (datetime.datetime.now() - datetime.timedelta(days=420)).strftime("%Y-%m-%d")
    try:
        df = yf.download(dl, start=start, interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    close, vol = df["Close"], df["Volume"]

    def _ret(s, n):
        return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100 if len(s) > n and s.iloc[-1 - n] > 0 else np.nan

    q = close[bench].dropna() if bench in close.columns else pd.Series(dtype=float)
    q3 = _ret(q, 63) if len(q) else np.nan
    rows = []
    for t in tickers:
        if t not in close.columns:
            continue
        c = close[t].dropna()
        if len(c) < 253:  # 12개월 수익률이 없는 신규 상장 종목 제외 (기존 랭킹과 동일)
            continue
        v = vol[t].reindex(c.index).fillna(0)
        r1, r3, r6, r12 = _ret(c, 21), _ret(c, 63), _ret(c, 126), _ret(c, 252)
        score = np.nanmean([r1, r3, r6, r12])
        hi = c.iloc[-252:].max()
        ma200 = c.iloc[-200:].mean()
        ma50 = c.iloc[-50:].mean()
        dr = c.pct_change().iloc[-63:]
        vol_a = dr.std() * np.sqrt(252) * 100
        dv = c * v
        dv120 = dv.iloc[-120:].mean()
        above = c.iloc[-1] > ma200
        hi_gap = (c.iloc[-1] / hi - 1) * 100
        if above and hi_gap >= -10 and r1 >= 0:
            tag = "🟢 주도"
        elif above:
            tag = "🟡 추세 둔화"
        elif r1 > 0:
            tag = "🔵 200일선 아래 반등"
        else:
            tag = "🔴 200일선 아래 하락"
        rows.append({
            "Ticker": t, "price": c.iloc[-1], "1M": r1, "3M": r3, "6M": r6, "12M": r12, "score": score,
            "hi_gap": hi_gap, "above200": bool(above), "above50": bool(c.iloc[-1] > ma50),
            "rs3": r3 - q3 if pd.notna(q3) else np.nan, "vol": vol_a,
            "stable": score / vol_a if vol_a and vol_a > 0 else np.nan,
            "flow": dv.iloc[-20:].mean() / dv120 if dv120 > 0 else np.nan,
            "tag": tag, "asof": c.index[-1].strftime("%Y-%m-%d"),
            # 보유 기준 (백테스트 검증: 200일선 −3% 아래 매도, 200일선 +5% 위로 올라오면 재매수·신규 매수)
            "ma200_gap": (c.iloc[-1] / ma200 - 1) * 100,
            "hold": ("🟢 보유·매수 가능" if c.iloc[-1] > ma200 * 1.05 else
                     "🟢 보유 (재매수 대기)" if c.iloc[-1] > ma200 else
                     "🟡 경계" if c.iloc[-1] >= ma200 * 0.97 else "🔴 매도 기준"),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out.attrs["qqq3"] = q3
    return out


# ===================== 종목 차트·보유 점검 (미국 주식 랭킹 → 종목 검색) =====================
@st.cache_data(ttl=3600, show_spinner=False, max_entries=60)
def get_stock_chart_data(ticker, bench):
    """검색한 종목 하나만 3년치 일봉(고가·저가·종가·거래량)과 비교 기준(QQQ/SPY) 종가를 받음. 실패하면 None."""
    start = (datetime.datetime.now() - datetime.timedelta(days=3 * 365 + 30)).strftime("%Y-%m-%d")
    try:
        df = yf.download([ticker, bench], start=start, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        out = pd.DataFrame({
            "Close": df["Close"][ticker], "High": df["High"][ticker], "Low": df["Low"][ticker],
            "Volume": df["Volume"][ticker], "Bench": df["Close"][bench],
        }).dropna(subset=["Close"])
        out.index = pd.to_datetime(out.index).tz_localize(None)
        return out if len(out) >= 60 else None
    except Exception:
        return None


def _stock_tech(d):
    """보조지표·추세선·목표가·손절가·보유 점검을 계산 (마지막 거래일 기준)."""
    d = d.copy()
    c, h, l = d["Close"], d["High"], d["Low"]
    d["MA50"] = c.rolling(50).mean()
    d["MA200"] = c.rolling(200).mean()
    d["H52"] = c.rolling(252, min_periods=60).max()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["RSI"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["Signal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["Chand"] = h.rolling(22).max() - 3 * d["ATR"]       # 샹들리에 스탑 (중기 손절)

    last = d.iloc[-1]
    px, atr = float(last["Close"]), float(last["ATR"])
    # 6개월 추세선 (로그 가격 회귀) — 보유 점검용, 화면 기간과 무관하게 고정
    w = c.tail(126)
    x = np.arange(len(w))
    b, a = np.polyfit(x, np.log(w.values), 1)
    trend6 = float(np.exp(a + b * x[-1]))
    slope6 = float(np.exp(b * 252) - 1) * 100

    lo20 = float(l.tail(20).min())
    hi60 = float(h.tail(60).max())
    h52 = float(last["H52"])
    stop_s = max(px - 2 * atr, lo20)            # 단기 손절: 현재가-2×ATR과 20일 최저가 중 가까운 쪽
    stop_m = float(last["Chand"])               # 중기 손절: 22일 최고가 - 3×ATR
    # 단기 목표: 60일 고점(이미 고점이면 +2×ATR), 단 1~4주에 닿기 먼 거리면 +3×ATR로 제한
    tgt_s = min(hi60 if hi60 > px * 1.01 else px + 2 * atr, px + 3 * atr)
    # 중기 목표: 52주 고점(근처면 +4×ATR), 단 1~3개월에 닿기 먼 거리면 +6×ATR로 제한
    tgt_m = min(h52 if h52 > px * 1.05 else px + 4 * atr, px + 6 * atr)
    rr = (tgt_m - px) / (px - stop_m) if px > stop_m else np.nan
    # 장기(6~12개월) 목표: 1년 추세선을 6개월 앞으로 연장한 값과 52주 고점 중 높은 값, 단 현재가 + 12×ATR로 제한
    w1 = c.tail(252)
    x1 = np.arange(len(w1))
    b1, a1 = np.polyfit(x1, np.log(w1.values), 1)
    proj = float(np.exp(a1 + b1 * (x1[-1] + 126)))
    slope1 = float(np.exp(b1 * 252) - 1) * 100   # 1년 추세 기울기 (연율 %)
    # 52주 고점이 현재가 바로 위(5% 이내)면 저항이 아니므로 현재가 + 8×ATR을 대신 씀 (중기의 +4×ATR보다 멀게)
    near_high = h52 <= px * 1.05
    res_l = px + 8 * atr if near_high else h52
    tgt_l = min(max(proj, res_l), px + 12 * atr)
    if tgt_l == px + 12 * atr:
        tgt_l_src = "현재가 + 12×ATR (추세 연장·52주 고점은 6~12개월에 닿기 먼 거리)"
    elif proj >= res_l:
        tgt_l_src = "1년 추세선을 6개월 앞으로 연장한 값"
    else:
        tgt_l_src = "52주 고점 근처 → 현재가 + 8×ATR" if near_high else "52주 고점 (회복 목표)"
    if tgt_l < tgt_m:   # 장기 목표가 중기 목표보다 낮을 수 없음
        tgt_l, tgt_l_src = tgt_m, "중기 목표와 같음 (장기 근거가 중기보다 낮게 나와 중기 값을 하한으로 사용)"
    # 장기 손절: 200일선 아래 3% (200일선 이탈 = 장기 추세 종료)
    ma200_v = float(d["MA200"].iloc[-1]) if pd.notna(d["MA200"].iloc[-1]) else np.nan
    stop_l = ma200_v * 0.97 if pd.notna(ma200_v) else np.nan
    _chand_src = "샹들리에 스탑: 최근 22일 최고가 − 3×ATR"
    _ma_src = "200일선 × 0.97 (200일선 3% 아래로 마감하면 장기 추세 종료)"
    stop_m_src, stop_l_src = _chand_src, _ma_src
    # (2026-10-12 백테스트: 200일선 -3% 매도·200일선 회복 재매수가 가장 효율적 → 장기 손절은 항상 200일선 기준으로 고정)
    rr = (tgt_m - px) / (px - stop_m) if px > stop_m else np.nan
    rr_l = (tgt_l - px) / (px - stop_l) if pd.notna(stop_l) and px > stop_l else np.nan

    bench_rs = (c.iloc[-1] / c.iloc[-64] - d["Bench"].iloc[-1] / d["Bench"].iloc[-64]) * 100 if len(d) > 64 else np.nan
    ma50, ma200 = last["MA50"], last["MA200"]
    ma200_up = (d["MA200"].iloc[-1] > d["MA200"].iloc[-21]) if pd.notna(d["MA200"].iloc[-21]) else None
    checks = [
        ("정배열 (주가 > 50일선 > 200일선)", bool(pd.notna(ma200) and px > ma50 > ma200)),
        ("200일선 상승 중 (20일 전보다 높음)", bool(ma200_up)),
        ("6개월 추세선 위 (추세 기울기 연 %+.0f%%)" % slope6, px > trend6),
        ("MACD > 시그널 (단기 모멘텀 상승)", bool(last["MACD"] > last["Signal"])),
        ("비교지수보다 강함 (3개월 상대성과 %+.1f%%p)" % bench_rs if pd.notna(bench_rs) else "비교지수보다 강함", bool(pd.notna(bench_rs) and bench_rs > 0)),
    ]
    score = sum(ok for _, ok in checks)
    if pd.notna(ma200) and px < ma200 * 0.97:
        verdict = ("🔴", "약세", "200일선보다 3% 넘게 아래라 장기 추세가 꺾인 상태입니다.")
    elif score >= 4:
        verdict = ("🟢", "보유 유지", "추세·모멘텀·상대강도가 대체로 양호합니다.")
    elif score >= 3:
        verdict = ("🟡", "주의 보유", "일부 지표가 약해졌습니다. 신규 매수는 서두르지 않는 구간입니다.")
    else:
        verdict = ("🔴", "약세", "대부분의 추세 지표가 약합니다. 신규 매수는 피하는 구간입니다.")
    rsi = float(last["RSI"])
    rsi_note = ("RSI %.0f — 과열(75 이상). 추세가 좋아도 조정 가능성이 큽니다. 새로 사기보다 기다리는 구간입니다." % rsi if rsi >= 75 else
                "RSI %.0f — 과열권 진입(70 이상). 강한 추세에서는 흔하지만 추가 매수는 서두르지 않는 편이 낫습니다." % rsi if rsi >= 70 else
                "RSI %.0f — 과매도(30 이하). 하락이 과했지만 추세 전환 신호는 아닙니다." % rsi if rsi <= 30 else
                "RSI %.0f — 보통 범위(30\\~70)." % rsi)
    levels = dict(px=px, atr=atr, stop_s=stop_s, stop_m=stop_m, tgt_s=tgt_s, tgt_m=tgt_m, rr=rr,
                  tgt_l=tgt_l, tgt_l_src=tgt_l_src, stop_l=stop_l, rr_l=rr_l,
                  trend6=trend6, slope1=slope1, stop_m_src=stop_m_src, stop_l_src=stop_l_src,
                  lo20=lo20, hi60=hi60, h52=h52, ma50=ma50, ma200=ma200, slope6=slope6)
    return d, levels, checks, score, verdict, rsi_note


ETF_RULE_NOTES = {
    "index": ("지수·섹터·국가·배당형 ETF", 0.0, "rule",
              "ETF 49개 백테스트(1998&#126;): 이 종류는 −3% 매도·200일선 회복 재매수가 +5% 재매수보다 나았고, 최대 낙폭이 평균 20%p 이상 줄었습니다(수익은 연 1&#126;2%p 덜 받는 보험)"),
    "theme": ("테마·원자재 ETF", 0.05, "rule",
              "ETF 49개 백테스트: 개별 종목만큼 출렁이는 종류라 +5% 재매수가 휩소를 줄여 더 나았습니다(테마 10개 중 7개)"),
    "bond": ("채권 ETF", 0.0, "ref",
             "ETF 49개 백테스트: 채권은 낙폭 개선이 작고 샤프가 오히려 낮아져 규칙 효과가 약합니다. 참고로만 보세요"),
    "gold": ("금 ETF", 0.0, "ref",
             "ETF 49개 백테스트: 금(GLD)은 그냥 보유가 규칙보다 나았습니다(샤프 0.64 vs 0.53&#126;0.57). 참고로만 보세요"),
    "lev": ("레버리지·인버스 ETF", 0.0, "none",
            "ETF 백테스트: 200일선 규칙을 써도 최대 낙폭이 −70&#126;−90%였고 수익만 연 10%p 넘게 줄었습니다. 장기 보유용이 아니라 보유 기준을 적용하지 않습니다"),
    "unknown": ("종류 미확인 ETF", 0.0, "ref",
                "종류를 알 수 없어 지수형 규칙(−3% 매도·200일선 회복 재매수)을 참고로 보여 줍니다"),
}
_ETF_KIND = {}
for _t in ["SPY", "QQQ", "QQQM", "DIA", "IWM", "RSP", "VOO", "IVV", "SPLG", "VTI", "VT", "VEA", "EFA", "IEFA", "VWO", "IEMG",
           "VUG", "VTV", "SCHG", "MGK", "IJH", "MDY", "SCHB", "VNQ", "SCHD", "JEPI", "JEPQ", "VIG", "VYM", "DGRO", "DVY", "COWZ",
           "SPMO", "MTUM", "QUAL", "USMV"] + SECTOR_GROUPS["기준 지수"] + SECTOR_GROUPS["11개 섹터"] + SECTOR_GROUPS["국가·지역"]:
    _ETF_KIND[_t] = "index"
for _t in SECTOR_GROUPS["세부 테마"] + ["SOXX", "ARKK", "IBIT", "FBTC", "BITO", "SLV", "PDBC", "OILK", "DBC", "USO", "UNG", "COPX", "URA"]:
    _ETF_KIND[_t] = "theme"
for _t in ["BIL", "SHY", "IEF", "TLT", "AGG", "BND", "LQD", "HYG", "JNK", "TIP", "SGOV", "SHV", "GOVT", "VGLT", "EDV", "MUB", "EMB"]:
    _ETF_KIND[_t] = "bond"
for _t in ["GLD", "IAU", "GLDM", "SGOL"]:
    _ETF_KIND[_t] = "gold"
for _t in ["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXL", "SPXU", "SDS", "SSO", "QLD", "TECL", "FNGU", "LABU", "TNA", "TZA",
           "UVXY", "SVXY", "TMF", "TMV", "UBT", "TYD", "TBF", "DOG", "RWM", "SH", "PSQ", "NUGT", "DUST", "BITX", "MSTU", "CONL"]:
    _ETF_KIND[_t] = "lev"


@st.cache_data(ttl=86400, show_spinner=False)
def _etf_long_name(t):
    """목록에 없는 ETF의 이름(야후). 실패하면 빈 문자열."""
    try:
        _i = yf.Ticker(t).info or {}
        return str(_i.get("longName") or _i.get("shortName") or "")
    except Exception:
        return ""


def etf_rule_for(t):
    """ETF 종류에 맞는 보유 기준 (2026-10-15 ETF 49개 백테스트 근거)."""
    k = _ETF_KIND.get(t)
    if k is None:
        _n = _etf_long_name(t).upper()
        if any(w in _n for w in ("2X", "3X", "-1X", "-2X", "-3X", "ULTRA", "BULL ", "BEAR ", "INVERSE", "LEVERAGED", "DAILY ")):
            k = "lev"
        elif "MINER" in _n:
            k = "theme"
        elif "GOLD" in _n:
            k = "gold"
        elif any(w in _n for w in ("TREASURY", "BOND", "T-BILL", "AGGREGATE", "MUNICIPAL", "CORPORATE")):
            k = "bond"
        else:
            k = "unknown"
    lab, rb, mode, note = ETF_RULE_NOTES[k]
    return {"rebuy": rb, "mode": mode, "label": lab, "note": note}


# ===================== ⭐ 내 관심 종목 (비밀번호 · 나만 보기, 2026-10-15) =====================
# 저장: GitHub 저장소의 별도 브랜치(watchlist-data)의 watchlist.json — 앱이 배포된 main 브랜치가 아니라서 저장해도 Cloud 앱이 재시작되지 않음
# Secrets: GITHUB_TOKEN · GITHUB_REPO(자료실과 같은 값) + WATCHLIST_PASSWORD(없으면 UPLOAD_PASSWORD 사용)
# PC(Secrets 없음): 비밀번호 없이 폴더의 watchlist_local.json에 저장
WL_BRANCH, WL_PATH, WL_LOCAL = "watchlist-data", "watchlist.json", "watchlist_local.json"


def _wl_secret(k):
    try:
        return st.secrets.get(k)
    except Exception:
        return None


def _wl_gh():
    tok, repo = _wl_secret("GITHUB_TOKEN"), _wl_secret("GITHUB_REPO")
    if not (tok and repo):
        return None
    return tok, repo


def _wl_api(method, url, tok, **kw):
    import requests
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    return requests.request(method, url, headers=h, timeout=30, **kw)


def _wl_load():
    """관심 종목 목록 [{"t": 티커, "d": 추가일}]."""
    gh = _wl_gh()
    try:
        if gh:
            tok, repo = gh
            r = _wl_api("GET", f"https://api.github.com/repos/{repo}/contents/{WL_PATH}?ref={WL_BRANCH}", tok)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            import base64
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8")).get("items", [])
        if os.path.exists(WL_LOCAL):
            with open(WL_LOCAL, encoding="utf-8") as f:
                return json.load(f).get("items", [])
    except Exception as e:
        st.warning(f"관심 종목 목록을 불러오지 못했습니다: {e}")
    return []


def _wl_save(items):
    data = json.dumps({"items": items, "saved": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1)
    gh = _wl_gh()
    if not gh:
        with open(WL_LOCAL, "w", encoding="utf-8") as f:
            f.write(data)
        return True
    tok, repo = gh
    import base64
    api = f"https://api.github.com/repos/{repo}"
    try:
        # 저장용 브랜치가 없으면 기본 브랜치에서 만듦
        if _wl_api("GET", f"{api}/git/ref/heads/{WL_BRANCH}", tok).status_code == 404:
            base = _wl_api("GET", api, tok).json().get("default_branch", "main")
            sha = _wl_api("GET", f"{api}/git/ref/heads/{base}", tok).json()["object"]["sha"]
            _wl_api("POST", f"{api}/git/refs", tok, json={"ref": f"refs/heads/{WL_BRANCH}", "sha": sha}).raise_for_status()
        cur = _wl_api("GET", f"{api}/contents/{WL_PATH}?ref={WL_BRANCH}", tok)
        body = {"message": "관심 종목 저장", "branch": WL_BRANCH,
                "content": base64.b64encode(data.encode("utf-8")).decode("ascii")}
        if cur.status_code == 200:
            body["sha"] = cur.json()["sha"]
        _wl_api("PUT", f"{api}/contents/{WL_PATH}", tok, json=body).raise_for_status()
        return True
    except Exception as e:
        st.error(f"저장하지 못했습니다: {e}")
        return False


@st.cache_data(ttl=86400, show_spinner=False)
def _wl_quote_type(t):
    try:
        return str((yf.Ticker(t).info or {}).get("quoteType") or "")
    except Exception:
        return ""


def _wl_rule(t):
    """ETF면 ETF 종류별 기준, 아니면 개별 종목 기준(None)."""
    if t in _ETF_KIND or _wl_quote_type(t).upper() == "ETF":
        return etf_rule_for(t)
    return None


def _wl_status(close, rule):
    ma = close.rolling(200).mean().iloc[-1]
    px = close.iloc[-1]
    if pd.isna(ma):
        return "-", np.nan, "200일선 계산 전 (상장 1년 미만)"
    gap = (px / ma - 1) * 100
    if rule is not None and rule.get("mode") == "none":
        return "⛔ 미적용", gap, rule["label"]
    rb = 0.05 if rule is None else rule.get("rebuy", 0.05)
    if px > ma * (1 + rb):
        lab = "🟢 보유·매수 가능"
    elif px > ma:
        lab = "🟢 보유 (재매수 대기)"
    elif px >= ma * 0.97:
        lab = "🟡 경계"
    else:
        lab = "🔴 매도 기준"
    if rule is not None and rule.get("mode") == "ref":
        lab += " (참고용)"
    kind = "개별 종목 (−3% 매도 · +5% 재매수)" if rule is None else rule["label"]
    return lab, gap, kind


def render_stock_finder():
    """🔎 실시간 미국 주식 종목 찾기: 랭킹을 불러오지 않고 아무 미국 주식·ETF의 차트와 보유·매도 기준을 봄.
    랭킹을 이미 불러왔다면 그 지수 안의 순위 줄도 함께 표시."""
    with st.container(border=True):
        st.markdown("### 🔎 실시간 미국 주식 종목 찾기")
        with st.form(key="stkfind_form", clear_on_submit=False, border=False):
            _q = st.text_input("티커나 회사 이름을 입력하고 Enter (여러 개는 쉼표로 · 나스닥100·S&P500·그 밖의 미국 주식·ETF 모두)",
                               key="stkfind_text", placeholder="예: TSLA, 애플, 엔비디아, Costco, PLTR, VOO")
            _c1, _c2 = st.columns([1, 1])
            _go = _c1.form_submit_button("🔍 검색", use_container_width=True)
            _clr = _c2.form_submit_button("지우기", use_container_width=True)
        if _clr:
            st.session_state["stkfind_list"], st.session_state["stkfind_miss"] = [], []
        elif _go:
            _found, _miss = [], []
            _names = None
            for _term in [x.strip() for x in _q.replace("，", ",").split(",") if x.strip()]:
                _tu = _term.upper().replace(".", "-")
                _looks_tk = _tu.isascii() and _tu.replace("-", "").isalnum() and len(_tu) <= 6
                if _looks_tk and (_term.isupper() or _tu in TICKER_INFO):
                    _found.append(_tu)                     # 티커로 바로 조회
                    continue
                if _names is None:                         # 이름 검색: 한글명(대형주·ETF) + S&P500 영문 회사명·업종
                    _sp = get_sp500_universe()
                    _names = {t: " ".join([t, *v]) for t, v in TICKER_INFO.items()}
                    for t, v in (_sp[2] or {}).items():
                        _names[t] = (_names.get(t, t) + " " + " ".join(v)).strip()
                    for t, v in TICKER_EXTRA_NAMES.items():
                        _names[t] = (_names.get(t, t) + " " + " ".join(v)).strip()
                _tl = _term.lower()
                _hits = [t for t, h in _names.items() if _tl in h.lower()][:5]
                if _hits:
                    _found.extend(_hits)
                elif _looks_tk:
                    _found.append(_tu)                     # 소문자로 친 티커 (목록에 없으면 그대로 조회)
                else:
                    _miss.append(_term)
            st.session_state["stkfind_list"] = list(dict.fromkeys(_found))
            st.session_state["stkfind_miss"] = _miss
        if st.session_state.get("stkfind_miss"):
            st.warning(f"찾지 못한 검색어: {', '.join(st.session_state['stkfind_miss'])} — 영문 티커로 입력해 주세요(예: PLTR).")
        _pick = st.session_state.get("stkfind_list", [])
        if not _pick:
            st.caption("랭킹을 불러오지 않아도 바로 검색됩니다(종목당 1\\~2초, 이후 1시간은 누구나 바로 표시). "
                       "결과는 종목 차트 · 보유 기준(개별 종목 −3% 매도 · +5% 재매수, ETF는 종류별 기준) · 매도 기준까지 거리입니다. "
                       "아래에서 랭킹을 불러온 상태라면 그 지수 안의 순위도 함께 보여 줍니다.")
            return
        # 랭킹을 불러온 경우: 순위 줄
        for _un, (_dfa, _sb) in st.session_state.get("stk_rank_store", {}).items():
            _sr = _dfa[_dfa["티커 (Ticker)"].isin(_pick)]
            if _sr.empty:
                continue
            _sr = _sr.drop(columns=[c for c in ["_업종"] if c in _sr.columns]).copy()
            _rk = f"{_un} 순위 (/{len(_dfa)})"
            _sr.insert(0, _rk, [f"{i}위" for i in _sr.index])
            _sr = _sr.astype(object).where(_sr.notna(), "-")
            st.markdown(f"**{_un} 랭킹 안의 위치** ('{_sb}' 기준)")
            render_html_table(_sr, ticker_cols=("티커 (Ticker)",), text_cols=(_rk, "상태", "보유 기준", "세부업종", "시총 순위"), scroll_x=True)
        try:
            _ndx = set(get_ndx_tickers())
        except Exception:
            _ndx = set()
        st.caption("고른 종목만 서버에서 3년치 시세를 받아 계산합니다. 3\\~5개 이내를 권합니다. 실제 매매 판단은 월말 종가입니다.")
        for _j, _tk in enumerate(_pick):
            _rule = _wl_rule(_tk)
            _bench, _bl = ("QQQ", "QQQ") if (_rule is None and _tk in _ndx) else ("SPY", "SPY")
            _nm = TICKER_INFO.get(_tk, ("",))[0] or TICKER_EXTRA_NAMES.get(_tk, ("",))[0]
            with st.expander(f"📈 {_tk}" + (f" · {_nm}" if _nm else ""), expanded=(_j == 0)):
                if _rule is None:
                    render_stock_chart(_tk, _bench, "stkfind", show_rules=True, bench_label=_bl)
                else:
                    render_stock_chart(_tk, "SPY", "stkfind", show_rules=True, bench_label="SPY", etf_rule=_rule)


# ── 관리자 모드 공용 저장소: GitHub 별도 브랜치(watchlist-data) · PC에서는 admin_local 폴더 ──
ADMIN_LOCAL = "admin_local"


def _br_get(path):
    """브랜치의 파일 내용(bytes). 없으면 None."""
    gh = _wl_gh()
    if not gh:
        fp = os.path.join(ADMIN_LOCAL, path)
        return open(fp, "rb").read() if os.path.exists(fp) else None
    tok, repo = gh
    import base64
    r = _wl_api("GET", f"https://api.github.com/repos/{repo}/contents/{path}?ref={WL_BRANCH}", tok)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    j = r.json()
    if j.get("content"):
        return base64.b64decode(j["content"])
    if j.get("download_url"):          # 1MB 넘는 파일
        return _wl_api("GET", j["download_url"], tok).content
    return b""


def _br_put(path, data, msg):
    gh = _wl_gh()
    if not gh:
        fp = os.path.join(ADMIN_LOCAL, path)
        os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
        open(fp, "wb").write(data)
        return True
    tok, repo = gh
    import base64
    api = f"https://api.github.com/repos/{repo}"
    try:
        if _wl_api("GET", f"{api}/git/ref/heads/{WL_BRANCH}", tok).status_code == 404:
            base = _wl_api("GET", api, tok).json().get("default_branch", "main")
            sha = _wl_api("GET", f"{api}/git/ref/heads/{base}", tok).json()["object"]["sha"]
            _wl_api("POST", f"{api}/git/refs", tok, json={"ref": f"refs/heads/{WL_BRANCH}", "sha": sha}).raise_for_status()
        cur = _wl_api("GET", f"{api}/contents/{path}?ref={WL_BRANCH}", tok)
        body = {"message": msg, "branch": WL_BRANCH, "content": base64.b64encode(data).decode("ascii")}
        if cur.status_code == 200:
            body["sha"] = cur.json()["sha"]
        _wl_api("PUT", f"{api}/contents/{path}", tok, json=body).raise_for_status()
        return True
    except Exception as e:
        st.error(f"저장하지 못했습니다: {e}")
        return False


def _br_list(folder):
    """폴더 안 파일 이름 목록."""
    gh = _wl_gh()
    if not gh:
        fp = os.path.join(ADMIN_LOCAL, folder)
        return sorted(os.listdir(fp)) if os.path.isdir(fp) else []
    tok, repo = gh
    r = _wl_api("GET", f"https://api.github.com/repos/{repo}/contents/{folder}?ref={WL_BRANCH}", tok)
    if r.status_code != 200:
        return []
    return sorted(x["name"] for x in r.json() if x.get("type") == "file")


def _br_del(path):
    gh = _wl_gh()
    if not gh:
        fp = os.path.join(ADMIN_LOCAL, path)
        if os.path.exists(fp):
            os.remove(fp)
        return True
    tok, repo = gh
    api = f"https://api.github.com/repos/{repo}"
    try:
        cur = _wl_api("GET", f"{api}/contents/{path}?ref={WL_BRANCH}", tok)
        if cur.status_code != 200:
            return True
        _wl_api("DELETE", f"{api}/contents/{path}", tok,
                json={"message": f"삭제 {path}", "branch": WL_BRANCH, "sha": cur.json()["sha"]}).raise_for_status()
        return True
    except Exception as e:
        st.error(f"지우지 못했습니다: {e}")
        return False


def _admin_holdings():
    """💼 내 보유 현황: 종목·수량·평균단가를 저장해 두고 평가액·손익·비중·보유 기준을 봄 (달러 기준)."""
    st.markdown("#### 💼 내 보유 현황")
    if "hold_items" not in st.session_state:
        try:
            raw = _br_get("holdings.json")
            st.session_state["hold_items"] = json.loads(raw.decode("utf-8")).get("items", []) if raw else []
        except Exception as e:
            st.warning(f"보유 현황을 불러오지 못했습니다: {e}")
            st.session_state["hold_items"] = []
    items = st.session_state["hold_items"]

    def _save():
        data = json.dumps({"items": items, "saved": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
                          ensure_ascii=False, indent=1).encode("utf-8")
        return _br_put("holdings.json", data, "보유 현황 저장")

    with st.form("hold_edit", border=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        _t = c1.text_input("티커", placeholder="예: QQQ")
        _qn = c2.number_input("수량", min_value=0.0, step=1.0, format="%.4g")
        _pr = c3.number_input("평균 단가 ($)", min_value=0.0, step=0.01, format="%.2f")
        _memo = st.text_input("메모 (선택)", placeholder="예: 연금계좌, 혼합전략 A")
        b1, b2 = st.columns([1, 1])
        _go = b1.form_submit_button("➕ 추가·수정 저장", use_container_width=True)
        _del = b2.multiselect("지울 종목", [x["t"] for x in items], placeholder="지울 종목 고르기", label_visibility="collapsed")
        _rm = st.form_submit_button("🗑️ 고른 종목 지우기·저장", use_container_width=True)
    if _go and _t.strip():
        t = _t.strip().upper().replace(".", "-")
        items[:] = [x for x in items if x["t"] != t] + [{"t": t, "q": float(_qn), "p": float(_pr), "m": _memo.strip()}]
        if _save():
            st.success(f"{t} 저장했습니다. 같은 티커를 다시 넣으면 수량·단가가 바뀝니다.")
    if _rm and _del:
        items[:] = [x for x in items if x["t"] not in _del]
        if _save():
            st.success("지웠습니다.")
    if not items:
        st.info("보유 종목을 티커·수량·평균 단가로 넣고 '추가·수정 저장'을 누르세요.")
        return

    rows, tot_v, tot_c = [], 0.0, 0.0
    for x in items:
        raw = get_stock_chart_data(x["t"], "SPY")
        px_ = float(raw["Close"].dropna().iloc[-1]) if (raw is not None and "Close" in raw) else np.nan
        lab = "-"
        if raw is not None and "Close" in raw:
            lab = _wl_status(raw["Close"].dropna(), _wl_rule(x["t"]))[0]
        v, c = x["q"] * px_, x["q"] * x["p"]
        if pd.notna(v):
            tot_v += v
        tot_c += c
        rows.append({"티커": x["t"], "수량": x["q"], "평균 단가": x["p"], "현재가": px_, "평가액 ($)": v,
                     "손익 ($)": v - c, "수익률 %": (px_ / x["p"] - 1) * 100 if x["p"] else np.nan,
                     "보유 기준": lab, "메모": x.get("m", "")})
    df = pd.DataFrame(rows)
    df.insert(5, "비중 %", df["평가액 ($)"] / tot_v * 100 if tot_v else np.nan)
    df = df.sort_values("평가액 ($)", ascending=False)
    k1, k2, k3 = st.columns(3)
    k1.metric("평가액 합계", f"${tot_v:,.0f}")
    k2.metric("손익", f"${tot_v - tot_c:,.0f}", f"{(tot_v / tot_c - 1) * 100:+.1f}%" if tot_c else None)
    k3.metric("종목 수", f"{len(items)}")
    st.dataframe(df.style.format({"수량": "{:,.4g}", "평균 단가": "{:,.2f}", "현재가": "{:,.2f}", "평가액 ($)": "{:,.0f}",
                                  "비중 %": "{:.1f}", "손익 ($)": "{:+,.0f}", "수익률 %": "{:+.1f}"}, na_rep="-"),
                 use_container_width=True, hide_index=True)
    st.caption("현재가는 최근 종가(야후, 1시간 저장)입니다. 보유 기준은 개별 종목 −3% 매도·+5% 재매수, ETF는 종류별 기준이며 "
               "실제 판단은 월말 종가입니다. 계좌번호·로그인 정보는 넣지 마세요.")


# 📊 내 백테스트 결과 — 정리해 둔 결과(펼치기). 새 결과를 정리하면 이 목록 맨 앞에 (제목, 본문) 추가
ADMIN_NOTES = [
    ("✅ 검증 끝 — 익절 4방식 · 주간 매매 · 30종목 하이브리드 · QQQ 비교 (2026-10-23 PC 실행)", """
**다시 하지 않아도 되는 백테스트 정리.** 결론: **재돌파 전략은 월간 매매 · 익절 없음 그대로**, 30종목 하이브리드 전략은 폐기.

#### 1. 익절 방식 × 매매 주기 — `backtest/sp500_band_exit_backtest.py`

공통: 재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순 · 매도 200일선 −3% · 슬리피지 0.2% · 세금 미반영 · 판단일 종가 체결.

| 주기 · 익절 없음 | 2006\\~ CAGR · MDD | 2015\\~ CAGR · MDD | 연 매매 |
|---|---|---|---|
| **월간** | **13.3% · −26.7%** | **12.1% · −18.6%** | 23\\~28회 |
| 주간 | 9.0% · −25.5% | 10.0% · −22.8% | 34\\~38회 |

- **주간 매매는 탈락.** CAGR이 2\\~4%p 낮고 MDD도 줄지 않음. −3% 선 근처에서 팔고 사기(휩소)가 늘어서이며, 익절 10가지 모두 월간이 나았습니다.

월간 기준, 익절 없음 대비 변화 (MDD는 +가 개선):

| 익절 방식 | 2006\\~ CAGR / MDD | 2015\\~ CAGR / MDD | 판정 |
|---|---|---|---|
| ① 절반 익절 (200일선 +25·30·35·40%에서 절반 매도) | −0.8\\~−1.5 / +4.7 | −1.2\\~0 / −0.1\\~−3.0 | ✗ 두 기간 결과가 반대 |
| ② 트레일링 (고점 −15·20·25%) | −20%만 +0.4 / +5.5 | −0.4 / 0 | ✗ 한 숫자에서만 좋음 (−15% 나쁨, −25% 거의 발동 안 함) |
| ③ 수익 +25·30·35% 닿은 뒤 50일선 아래 매도 | −1.1\\~−1.7 / **+7.5\\~8.3** | −0.5\\~+0.2 / **+1.0\\~1.3** | △ 유일하게 일관된 MDD 개선 |

- ③의 대가: 매매 연 23 → 35\\~40회, 평균 보유 263 → 165\\~185일(양도세가 앞당겨짐, 표에는 미반영), 강세장 손해(2024년 기준 +31.1% vs ③ +9\\~13%). MDD 개선은 대부분 2007\\~09년 금융위기 구간.
- **결정: 익절 없음 유지.** 10% 위성 칸이라 MDD −27% → −19%도 전체 계좌로는 1%p 미만이고, 혼합전략의 하드스탑·비중 상한을 뺀 판단과도 같습니다.
  꼭 넣는다면 **③ +35% (월간)**: 2015\\~ 12.1% · −17.4% · 샤프 0.97.
- 기준 줄(13.3% · −26.7%)이 sp500_band_backtest.py(14.0% · −22.1%)와 조금 다른 것은 비중 배분 등 세부 처리 차이 — 방식 간 우열에는 영향 없음.

#### 2. QQQ 장기보유와 비교 (2015\\~, 세전)

| | CAGR | MDD | 샤프 |
|---|---|---|---|
| QQQ 장기보유 | **약 19%** | −35% | 약 0.9 |
| 재돌파 · 월간 · 익절 없음 | 12.1% | −18.6% | 0.90 |
| 재돌파 · 월간 · ③ +35% | 12.1% | **−17.4%** | **0.97** |
| SPY 장기보유 | 13.6% | −33.7% | 0.82 |
| (참고) 2026 혼합전략 | 세후 24\\~31% | −15% | 1.6 |

- 읽는 법: CAGR은 연 7%p 낮고(10년 1,000만원 → QQQ 약 5,700만원 vs 약 3,100만원), MDD는 절반, **샤프는 비슷** → 효율이 더 좋은 게 아니라 '덜 벌고 덜 잃는' 전략.
  **QQQ 50% + 현금 50%**와 비슷한 성격이며, 생존편향까지 감안하면 실제는 더 낮습니다.
- 긴 하락장(2008년형) 방어는 확실하지만, 그건 **QQQ + 200일선 규칙**으로 더 단순하게 얻을 수 있습니다.

**정리**

| 목적 | 더 나은 선택 |
|---|---|
| 장기 수익 | QQQ 장기보유 |
| 낙폭 방어 | QQQ + 200일선 규칙, 또는 2026 혼합전략 |
| 위험 대비 효율 | 2026 혼합전략 (샤프 1.6) |

재돌파 전략이 이 셋 중 어느 것보다 나은 영역은 찾기 어렵습니다. 의미를 찾는다면, 기술주 중심인 혼합전략·QQQ와 다른 종목군(S&P500 전반)을 담는 **분산 효과** 정도입니다.
이마저도 **10% 위성 칸 안에서는 효과가 작습니다.**

#### 3. 30종목 하이브리드 전략 (외부 app.py — 시총 상위 30 · 5슬롯 · 3일 안착 · −8% 트레일링 · SPY 120일선) — 폐기

- 명세서 성과 15.5% · −18.8% · 샤프 1.09는 **믿기 어려움**:
  ① 지금(2026년) 시총 상위 30종목(NVDA·AVGO·LLY·TSLA·META 등)을 2015년부터 쓴 **사후 선택 편향**
  ② `run_backtest` 인자가 모두 `_`로 시작해 캐시 키에서 빠짐 → **사이드바 값을 바꿔도 결과가 안 바뀌는 버그**
  ③ 실시간 추천 탭이 진입 조건을 확인하지 않음(사실상 모멘텀 상위 5개) ④ 비용 0 · 신호 당일 종가 체결
- 사실상 위 재돌파 전략의 변형이고, 재돌파 전략(S&P500 전체 12.3%)보다 높은 3%p는 대부분 종목 선택 편향에서 온 것으로 판단.
- MSTR 반반 규칙(78.7% · −48.3% · 샤프 1.37)보다 수익·샤프 모두 낮음. 종목당 20% 집중이라 투자 선언문 '개별투자 10% 이내'와도 맞지 않음.

#### 다시 해 볼 가치가 있는 것 (아직 안 함)

- 스크립트에 **QQQ 보유 · QQQ 200일선 규칙**을 같은 기간·비용으로 넣어 실측 비교 (위 QQQ 값은 이전 hold_rule_backtest 값)
- `--lag 1`(다음 날 종가 체결)로 같은 표 재확인

<small>생존편향(현재 S&P500 종목)·세금 미반영 · 결과 파일: backtest/band_exit_results.csv · band_exit_yearly.csv(2006\\~ 연도별)</small>
"""),
    ("📖 읽는 법 — 'SPY↓ 신규매수 중단'(시장 필터)이란?", """
**SPY↓ 신규매수 중단**은 SPY가 200일선 아래로 내려가면(↓) 새로 사지 않는 시장 필터입니다. 
개별 종목을 고르기 전에 **시장 전체가 상승 추세인지**를 먼저 확인하는 장치입니다.

#### 어떻게 작동하나 (매달 월말 종가로 판단)

| 월말 SPY 상태 | 새로 사기 (빈자리 채우기) | 이미 가진 종목 |
|---|---|---|
| SPY가 200일선 **위** | ✅ 평소대로 후보 종목으로 채움 | 각자 200일선 −3% 규칙대로 |
| SPY가 200일선 **아래** | ⛔ **사지 않음** · 빈자리는 현금으로 둠 | 그대로 둠 · 다만 −3% 아래로 가면 평소처럼 팜 |

SPY가 다시 200일선 위로 올라온 월말부터 빈자리를 다시 채웁니다.

#### '전부 현금'과의 차이

| | 신규매수 중단 | 전부 현금 |
|---|---|---|
| SPY가 200일선 아래면 | **새로 안 사기만** 함 | 가진 종목도 **모두 팖** |
| 버티는 종목 | 시장이 약해도 혼자 강한 종목은 계속 보유 | 없음 |
| 백테스트 결과 | 두 기간 모두 MDD −20% 안팎으로 안정 | 2015년 이후 V자 반등을 놓쳐 크게 손해 |

#### 왜 필요했나

필터가 없으면 2008년 같은 하락장에서 이런 일이 반복됐습니다.

1. 가진 종목이 −3% 규칙으로 팔린다.
2. 하락장 중간에 잠깐 반등한 다른 종목이 +5\\~10% 구간에 들어온다.
3. 빈자리를 그 종목으로 채운다 → 다시 떨어져 팔린다.

하락장 내내 계속 사서 계속 잃는 구조였고, 신규매수 중단은 이 **'하락장에서 다시 사기'**만 막아 줍니다.

#### 효과 (재돌파 · 15종목 · +5%근접순 기준)

| 시작 | 필터 없음 | SPY↓ 신규매수 중단 |
|---|---|---|
| 2006\\~ | 13.9% · MDD −48.7% | 14.0% · MDD **−22.1%** |
| 2015\\~ | 14.1% · MDD −34.9% | 12.3% · MDD **−19.5%** |

낙폭은 절반 가까이 줄고, 수익은 비슷하거나 조금 줄었습니다.

#### 같은 생각의 다른 규칙

MSTR 반반 규칙의 **BTC 120일선**, 혼합전략의 **카나리아(TIP · SPY 배당수익률)**도 같은 계열입니다. 
'내가 산 것'만 보지 않고 **그것을 움직이는 더 큰 흐름**을 함께 보는 두 겹 확인입니다. 
다만 MSTR은 비트코인에 강하게 묶여 있어 큰 흐름 신호로 **직접 줄이고**, 개별 종목은 시장과 느슨하게 연결돼 있어 **'문지기'(신규 매수만 막기)**로만 쓰는 쪽이 나았습니다.

#### 확인하는 법

월말마다 SPY가 200일선 위인지 봅니다 — 미국 주식 탭 맨 위 '🔎 종목 찾기'에 SPY를 넣으면 200일선 대비 거리가 바로 나옵니다. 
(2026-10-15 종가 기준 SPY는 200일선보다 +7.0% 위 → 매수 허용)
"""),
    ("📌 TIP 카나리아 필터 · 종목 범위 비교 (2026-10-16 PC 실행)", """
**1. TIP 카나리아 필터 (전략 A·B 카나리아를 '신규매수 중단' 신호로 사용)**

| 시작 | 재돌파 · 15종목 · +5%근접순 | CAGR | MDD | 샤프 |
|---|---|---|---|---|
| 2006\\~ | SPY↓ 신규매수 중단 | 14.0% | **−22.1%** | **0.96** |
| 2006\\~ | TIP-A↓ 신규매수 중단 | 14.5% | −37.2% | 0.89 |
| 2006\\~ | TIP-B↓ 신규매수 중단 | **15.3%** | −36.1% | 0.94 |
| 2015\\~ | SPY↓ 신규매수 중단 | 12.3% | **−19.5%** | **0.91** |
| 2015\\~ | TIP-A↓ 신규매수 중단 | 11.3% | −37.4% | 0.76 |
| 2015\\~ | TIP-B↓ 신규매수 중단 | 12.3% | −36.2% | 0.82 |

- TIP 필터는 **수익은 비슷하거나 조금 높지만 낙폭 방어는 SPY 필터보다 약했습니다**(MDD −35\\~−38% vs −20\\~−22%). 
  TIP은 금리·물가 신호라 2008년처럼 주식이 먼저 무너지는 하락에는 늦게 반응했습니다.
- 대신 2015년 이후 V자 반등장에서는 SPY 필터처럼 팔고 놓치는 일이 적어, **모멘텀순과 조합**하면 수익이 좋았습니다
  (재돌파 · TIP-A↓ · 10종목 · 모멘텀순: 2006\\~ 15.5% · −43.1%, 2015\\~ 17.2% · −34.8%).
- 정리: **SPY 필터 = 낙폭 방어형, TIP 필터 = 수익과 방어의 중간형.** SPY 필터는 +5%근접순, TIP 필터는 모멘텀순과 잘 맞았습니다.

**2. 종목 범위 비교 (재돌파 조건 없이, 6가지 조합 평균)**

| 시작 · 필터 | S&P500 전체 | 거래대금 상위 200 | 거래대금 상위 100 |
|---|---|---|---|
| 2006\\~ · 필터 없음 | **15.8% · −49.8% · 0.82** | 10.6% · −46.9% · 0.64 | 9.6% · −40.0% · 0.60 |
| 2006\\~ · SPY↓ 신규매수 중단 | **12.8% · −33.5% · 0.81** | 10.6% · −27.5% · 0.73 | 9.3% · −31.2% · 0.67 |
| 2015\\~ · 필터 없음 | **18.3% · −38.4% · 0.92** | 12.4% · −36.0% · 0.71 | 12.0% · −31.9% · 0.71 |
| 2015\\~ · SPY↓ 신규매수 중단 | **14.0% · −33.1% · 0.86** | 11.1% · −26.9% · 0.73 | 9.8% · −31.1% · 0.68 |

- 대형주로 좁히면 **더 안정적이지 않았습니다.** 낙폭은 조금 줄기도 했지만 수익과 샤프가 크게 떨어졌습니다. 
  범위가 좁으면 +5\\~10% 구간에 드는 후보가 적어 빈자리(현금)가 늘고, 좋은 종목을 고를 폭도 줄기 때문입니다.
- 나스닥100은 위키피디아에서 구성 종목을 받지 못해 이번에는 빠졌습니다.
- 정리: **S&P500 전체를 그대로 쓰는 것이 낫습니다.**

**결론** — 추천 조합은 그대로 **재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순**(두 기간 모두 MDD −20% 안팎). 
수익을 조금 더 원하고 낙폭 −35\\~−40%를 감수할 수 있으면 대안으로 **재돌파 · TIP-A↓ 신규매수 중단 · 10종목 · 모멘텀순**. 
어느 쪽이든 투자 선언문의 **개별투자 10% 이내**에서.

<small>생존편향·세금 미반영 · 원본: sp500_band_summary.md · band_universe_summary.md</small>
"""),
    ("📌 재돌파 조건 추가 — 200일선 아래로 내려갔다가 다시 +5\\~10% (2026-10-16)", """
**바뀐 매수 조건**: 최근 6개월(126거래일) 안에 종가가 200일선 아래였던 적이 있고, 지금 200일선 +5\\~10%인 종목만 삽니다. 
(이전 백테스트는 계속 위에 있다가 내려와 구간에 들어온 종목도 샀음.) 매도는 같음(200일선 −3%), 월말 판단 · 슬리피지 0.2% · 세금 미반영.

#### 조합 평균 (6가지 조합 평균, CAGR · MDD · 샤프)

| 시작 | 필터 | 조건 없음 | 재돌파 |
|---|---|---|---|
| 2006\\~ | 필터 없음 | 15.8% · −49.8% · 0.82 | 14.0% · −50.4% · 0.77 |
| 2006\\~ | SPY↓ 신규매수 중단 | 12.8% · −33.5% · 0.81 | 12.5% · **−25.0%** · **0.85** |
| 2015\\~ | 필터 없음 | **18.3%** · −38.4% · **0.92** | 15.6% · −35.7% · 0.84 |
| 2015\\~ | SPY↓ 신규매수 중단 | 14.0% · −33.2% · 0.86 | 11.0% · **−24.2%** · 0.78 |

재돌파 조건은 수익을 조금 줄이는 대신, **시장 필터와 함께 쓰면 낙폭을 평균 8\\~9%p 더 줄였습니다.** 
모멘텀순과는 잘 안 맞았고(재돌파+필터+모멘텀순 2015\\~ 9\\~11%), **+5%근접순**과 잘 맞았습니다.

#### 가장 균형 잡힌 조합 — 재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순

| 시작 | CAGR | MDD | 샤프 | 승률 |
|---|---|---|---|---|
| 2006\\~ | **14.0%** | −22.2% | **0.96** | 54% |
| 2015\\~ | 12.3% | **−19.5%** | 0.91 | 46% |
| (이전 최선) 조건 없음 · 같은 설정 | 12.0% / 12.3% | −21.0% / −20.6% | 0.86 / 0.92 | |
| SPY 보유 | 11.1% / 13.7% | −55.2% / −33.7% | 0.65 / 0.82 | |

두 기간 모두 MDD −20% 안팎으로 SPY의 절반 이하이고, 2006년부터는 수익·샤프도 이전 최선보다 나아졌습니다. 
'🎯 지금 선정 종목'은 이 조합 기준으로 바꿨습니다.

<small>생존편향·세금 미반영 · TIP 카나리아 필터와 종목 범위 비교는 PC에서 추가 실행 예정</small>
"""),
    ("📌 S&P500 200일선 +5\\~10% 종목 포트폴리오 · 시장 필터 비교 (2026-10-16)", """
**규칙**: 종가가 200일선보다 **+5\\~10%** 위인 S&P500 종목을 10·15·20개까지 담고, **200일선 −3%** 아래로 내려가면 매도. 빈자리는 다음 판단일에 채움. 
월말 판단 · 슬리피지 0.2% · 세금 미반영. 후보가 많을 때 고르는 순서: 6개월 수익률 높은 순(모멘텀순) / +5%에 가까운 순(+5%근접순).
**시장 필터**: 월말에 SPY가 200일선 아래면 ① 필터 없음 ② 신규 매수 중단 ③ 전부 현금.

**1차 결과에서 알게 된 것** (2006\\~, 필터 없음): 월말 판단이 주말보다 모든 조합에서 나았고, 모멘텀순이 +5%근접순보다 수익이 높았습니다. 
승률은 약 40%, 거래당 중앙값 −3\\~−5%, 상위 10% 거래가 +70\\~+100% — 몇 번의 큰 추세가 수익을 만드는 추세추종형입니다.

#### 2006년부터 (금융위기 포함) — 필터가 낙폭을 크게 줄임

| 규칙 | CAGR | MDD | 샤프 |
|---|---|---|---|
| 필터 없음 · 10종목 · 모멘텀순 | **19.4%** | −55.6% | 0.85 |
| SPY↓ 신규매수 중단 · 15종목 · +5%근접순 | 12.0% | **−21.0%** | 0.86 |
| SPY↓ 신규매수 중단 · 20종목 · +5%근접순 | 12.5% | −22.3% | 0.88 |
| SPY↓ 전부 현금 · 20종목 · +5%근접순 | 11.5% | −28.6% | **0.90** |
| SPY 보유 | 11.1% | −55.2% | 0.65 |

필터 없이는 하락장 중간 반등에 다른 종목을 계속 다시 사서 2008년에 −25\\~−45%를 잃었습니다. 필터를 넣으면 MDD가 절반 이하로 줄지만 수익도 19% → 11\\~12%로 줄었습니다.

#### 2015년부터 (금융위기 제외) — 필터가 오히려 손해

| 규칙 | CAGR | MDD | 샤프 |
|---|---|---|---|
| 필터 없음 · 10종목 · 모멘텀순 | **22.9%** | −42.3% | 0.97 |
| 필터 없음 · 10종목 · +5%근접순 | 17.8% | −36.9% | **1.01** |
| SPY↓ 신규매수 중단 · 15종목 · +5%근접순 | 12.3% | **−20.6%** | 0.92 |
| SPY↓ 전부 현금 · 15종목 · +5%근접순 | 9.6% | −29.5% | 0.77 |
| SPY 보유 | 13.7% | −33.7% | 0.82 |

2015년 이후 하락장(2018년 말·2020년·2022년)은 모두 빠르게 회복한 V자형이라, 필터가 팔고 나면 반등을 놓쳤습니다(2019년 SPY +31%, 2023년 SPY +26% 때 필터 버전은 −11\\~+11%).

#### 두 기간 모두 일관된 조합

**SPY↓ 신규매수 중단 · 15종목 · +5%근접순** — 2006\\~ 12.0% · −21.0%, 2015\\~ 12.3% · −20.6%. 수익은 SPY와 비슷하고 낙폭은 SPY의 절반 수준.

#### 정리

- 시장 필터는 QQQ 200일선 규칙과 같은 성격: **긴 하락장(2008년형)에는 보험, V자 반등장에서는 보험료**를 냅니다.
- 수익 우선 → 필터 없음 · 10종목 · 모멘텀순 (낙폭 −40\\~−55% 감수). 안정 우선 → 신규매수 중단 · 15종목 · +5%근접순.
- 종목 목록이 '지금' S&P500이라 **생존편향**으로 실제보다 좋게 나왔고, 세금도 빠져 있습니다. 어느 쪽도 2026 혼합전략(세후 연 24% 안팎, MDD −15%)보다 낫지 않아, 쓴다면 작은 비중의 위성 전략입니다.

<small>스크립트: sp500_band_backtest.py · 상세 표·그래프: 아래 파일 목록의 sp500_band_summary.md · sp500_band_chart.png</small>
"""),
]


# 🎯 선정 종목 스냅샷 (sp500_band_backtest 규칙, 2026-10-15 종가 · 후보 74개 · SPY 200일선 대비 +7.0%)
#   (티커, 200일선 대비 %, 6개월 수익률 %, 종가) — 매수 조건: 최근 6개월 안에 200일선 아래였다가 다시 +5~10%(재돌파)
BAND_PICKS_DATE = "2026-10-15"
BAND_PICKS = {
    "추천 — 재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순 (두 기간 모두 안정)": [
        ("UHS", 5.1, 5.1, 187.36),
        ("JPM", 5.1, 9.3, 335.53),
        ("OMC", 5.1, 4.6, 80.72),
        ("WTW", 5.1, 5.6, 310.36),
        ("ROP", 5.2, 6.2, 382.45),
        ("CME", 5.2, -1.3, 289.46),
        ("INCY", 5.4, 18.8, 113.27),
        ("MSI", 5.5, 3.3, 456.39),
        ("CF", 5.5, -3.1, 119.77),
        ("HCA", 5.6, -2.6, 468.50),
        ("CVS", 5.9, 22.4, 92.58),
        ("KVUE", 6.1, 10.7, 18.67),
        ("QCOM", 6.1, 33.9, 178.40),
        ("MNST", 6.3, 20.3, 45.34),
        ("ECL", 6.4, 8.6, 290.81),
    ],
    "참고 — 재돌파 · 필터 없음 · 10종목 · 모멘텀순": [
        ("URI", 9.5, 35.2, 1047.58),
        ("QCOM", 6.1, 33.9, 178.40),
        ("DLTR", 6.4, 24.5, 124.41),
        ("SMCI", 8.1, 23.6, 35.09),
        ("PAYX", 8.6, 23.1, 110.78),
        ("CVS", 5.9, 22.4, 92.58),
        ("MNST", 6.3, 20.3, 45.34),
        ("PRU", 9.0, 19.6, 116.35),
        ("INCY", 5.4, 18.8, 113.27),
        ("VRTX", 7.0, 16.8, 508.75),
    ],
}
BAND_PICKS_NOTE = ("2026-10-15 종가 기준, 200일선 아래로 내려갔다가 다시 올라와(최근 6개월 내 200일선 아래였던 적 있음) 200일선 +5\\~10%인 S&P500 종목은 57개(조건 없이는 74개)였고 SPY는 200일선보다 7.0% 위라 "
                   "시장 필터(신규매수 중단)도 매수 허용 상태였습니다.")


def _render_band_picks():
    with st.expander(f"🎯 지금 선정 종목 — 200일선 +5\\~10% 전략 ({BAND_PICKS_DATE} 종가 기준)", expanded=False):
        st.caption(BAND_PICKS_NOTE + " 백테스트 규칙으로 '오늘 새로 시작한다면' 담을 종목입니다. 실제로는 보유 중인 종목이 −3% 규칙으로 팔릴 때만 "
                   "빈자리를 채우므로, 매달 월말 종가로 다시 확인해야 합니다.")
        for ttl, rows in BAND_PICKS.items():
            st.markdown(f"**{ttl}**")
            _df = pd.DataFrame([{"티커": t, "이름": TICKER_INFO.get(t, ("",))[0] or TICKER_EXTRA_NAMES.get(t, ("",))[0],
                                  "200일선 대비 %": a, "6개월 수익률 %": b, "종가 ($)": c} for t, a, b, c in rows])
            st.dataframe(_df.style.format({"200일선 대비 %": "{:+.1f}", "6개월 수익률 %": "{:+.1f}", "종가 ($)": "{:,.2f}"}),
                         use_container_width=True, hide_index=True)
        st.caption("종목별 차트와 매도 기준(200일선 −3%)은 미국 주식 탭 맨 위 '🔎 실시간 미국 주식 종목 찾기'에 티커를 넣어 확인하세요. "
                   "생존편향·세금 미반영 백테스트에 근거한 참고 목록이며 매수 권유가 아닙니다.")


def _admin_results():
    """📊 내 백테스트 결과: PC 스크립트로 만든 결과 파일(csv·png·jpg·md·txt)을 올려 두고 보는 곳 — 서버는 계산하지 않음."""
    st.markdown("#### 📊 내 백테스트 결과")
    _render_band_picks()
    for _ttl, _body in ADMIN_NOTES:          # 정리해 둔 결과 (펼치기)
        with st.expander(_ttl, expanded=False):
            st.markdown(_body, unsafe_allow_html=True)
    st.markdown("**📁 올린 결과 파일**")
    st.caption("무거운 백테스트는 PC에서 돌리고, 결과 파일만 여기 올려 두면 휴대폰·태블릿에서도 볼 수 있습니다. 서버는 계산하지 않아 앱이 느려지지 않습니다.")
    with st.form("res_up", border=False, clear_on_submit=True):
        # 파일 종류를 막지 않음: 안드로이드·태블릿 파일 선택 창이 csv를 회색(선택 불가)으로 보여 주는 문제 → 올린 뒤 확장자로 확인
        ups = st.file_uploader("결과 파일 올리기 (csv · png · jpg · md · txt)", accept_multiple_files=True)
        if st.form_submit_button("⬆️ 올리기", use_container_width=True) and ups:
            ok = 0
            for u in ups:
                if u.name.rsplit(".", 1)[-1].lower() not in ("csv", "png", "jpg", "jpeg", "md", "txt"):
                    st.warning(f"{u.name}: csv · png · jpg · md · txt 파일만 올릴 수 있습니다.")
                    continue
                name = _re.sub(r"[^\w가-힣.\-]+", "_", u.name)
                if _br_put(f"results/{name}", u.getvalue(), f"결과 올리기 {name}"):
                    ok += 1
            st.session_state.pop("res_files", None)
            st.success(f"{ok}개 올렸습니다.")
    if "res_files" not in st.session_state:
        st.session_state["res_files"] = _br_list("results")
    files = st.session_state["res_files"]
    if not files:
        st.info("아직 올린 결과가 없습니다.")
        return
    c1, c2 = st.columns([3, 1])
    pick = c1.selectbox("볼 파일", files[::-1], key="res_pick")
    if c2.button("🔄 목록 새로고침", use_container_width=True):
        st.session_state["res_files"] = _br_list("results")
        st.rerun()
    try:
        data = _br_get(f"results/{pick}")
    except Exception as e:
        st.warning(f"파일을 불러오지 못했습니다: {e}")
        return
    if data is None:
        st.warning("파일이 없습니다. 목록을 새로고침해 주세요.")
        return
    ext = pick.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        import io
        try:
            _df = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
        except Exception:
            _df = pd.read_csv(io.BytesIO(data), encoding="cp949")
        st.dataframe(_df, use_container_width=True, hide_index=True)
    elif ext in ("png", "jpg", "jpeg"):
        st.image(data, use_container_width=True)
    elif ext == "md":
        st.markdown(data.decode("utf-8", errors="ignore"))
    else:
        st.code(data.decode("utf-8", errors="ignore"))
    with st.expander("🗑️ 이 파일 지우기"):
        if st.button(f"'{pick}' 지우기", key="res_del"):
            if _br_del(f"results/{pick}"):
                st.session_state["res_files"] = [f for f in files if f != pick]
                st.rerun()


def _admin_manifesto():
    """📜 나의 투자 원칙 선언문 (관리자 모드 첫 화면)."""
    _sec = ("border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin:10px 0;background:#fff;")
    _q = "color:#475569;font-style:italic;margin:2px 0 8px;"
    st.markdown(f"""
<div style="border:3px solid #0f2747;border-radius:14px;padding:18px 20px;background:#f8fafc;line-height:1.75;font-size:0.98rem;">
<div style="font-size:1.35rem;font-weight:900;color:#0f2747;margin-bottom:8px;">📜 나의 투자 원칙 선언문</div>
<div style="margin-bottom:6px;">나는 감정적 혼란과 불확실한 시장의 소음 속에서 나의 자산을 지키고,<br>
궁극적인 목표인 <b>'자유'</b>를 달성하기 위해<br>
다음과 같은 원칙을 선언하며 이를 반드시 준수할 것을 맹세한다.</div>

<div style="{_sec}">
<div style="font-weight:800;color:#0f2747;font-size:1.08rem;">제1원칙: 생존 (Survival)</div>
<div style="{_q}">"부는 쌓는 것보다 지키는 것이 더 어렵다."</div>
나는 단기 고수익의 유혹보다 장기적인 생존을 최우선 가치로 삼는다.<br>
시장에서 퇴출당하지 않는 것이 가장 위대한 수익률임을 항상 기억한다.
</div>

<div style="{_sec}">
<div style="font-weight:800;color:#0f2747;font-size:1.08rem;">제2원칙: 리스크 관리 (Risk Management)</div>
<div style="{_q}">"미래는 예측할 수 없으며, 알 수 없는 리스크는 항상 존재한다."</div>
나는 이 불확실성에 대비하기 위해, 내가 정한 <b>'동적 자산배분'</b>의 규칙을 기계적으로 따른다.<br>
공포나 탐욕이 아닌, 나의 원칙에 기반하여 행동한다.<br>
<b>개별투자는 운용자금의 10% 이내에서만 투자한다.</b><br>
나의 예측이 틀려도 무너지지 않을 '안전 완충 지대'를 항상 확보한다. (MDD)
</div>

<div style="{_sec}">
<div style="font-weight:800;color:#0f2747;font-size:1.08rem;">제3원칙: 목표와 충분함 (The Goal &amp; Sufficiency)</div>
<div style="{_q}">"나의 최종 목표는 돈 그 자체가 아니라 <b>'자유'</b>다."</div>
나의 '골대'는 명확하다. <b>[50억원]</b>은 나의 노후, 나의 자녀, 그리고 내가 돈 걱정 없이 하고 싶은 일을 하며 살기 위한 '충분함'의 기준이다.<br>
나는 이 목표를 향해 꾸준히 나아가되, 목표에 도달했을 때는 탐욕을 멈추고 진정한 부(富)인 <b>'자유'</b>를 누릴 것을 선언한다.
</div>
</div>
""", unsafe_allow_html=True)


# ===================== 📈 MSTR 매매 (관리자 모드 · 규칙대로 매매한 장부) =====================
MSTR_PAPER_START = pd.Timestamp("2026-10-20")     # 시작일 (사이클 현금 구간이 끝나는 날)
MSTR_PAPER_CAPITAL = 20_000_000                   # MSTR에 배정한 몫 (원)
MSTR_PAPER_FEE = 0.002                            # 매매마다 편도 0.2% (백테스트와 같음)
MSTR_PAPER_BAND = 0.10                            # 금요일 변동성 조정은 목표와 차이가 10%p 이상일 때만


@st.cache_data(ttl=3600)
def get_usdkrw_daily():
    """원/달러 환율 일별 종가 (야후 KRW=X)."""
    try:
        df = yf.download("KRW=X", period="2y", interval="1d", auto_adjust=True, progress=False)
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        c.index = pd.to_datetime(c.index).tz_localize(None)
        return c if len(c) > 20 else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_long_close(ticker, years=6):
    """장부용 긴 일봉 종가 (샘플 B처럼 몇 년 전부터 시작해도 120·200일선이 계산되도록)."""
    try:
        df = yf.download(ticker, period=f"{years}y", interval="1d", auto_adjust=True, progress=False)
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        c.index = pd.to_datetime(c.index).tz_localize(None)
        if ticker == "BTC-USD":                    # 진행 중인 오늘 봉 제외
            _t = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
            if len(c) and c.index[-1] >= _t:
                c = c.iloc[:-1]
        return c if len(c) > 250 else None
    except Exception:
        return None


MSTR_TAX_RATE = 0.22          # 해외주식 양도소득세 22% (지방세 포함) — 2026-10-23: MSTR 장부·백테스트에 기본 반영
MSTR_TAX_DEDUCT = 0           # 연 기본공제: 0원 (공제 250만원은 2026 혼합전략이 이미 쓴다고 보고 MSTR 몫은 없음 → 가장 보수적)


def mstr_paper_ledger(m, b, fx, start=None, vol_target=0.8, capital=None, deposits=None, tax_rate=None):
    """MSTR 반반 규칙을 start부터 capital로 따랐다면의 일자별 장부 (미국 종가 체결, 원화 환산).
    비용: 매매마다 편도 0.2%(슬리피지·수수료). 세금(2026-10-23): 한 해 실현손익(이익·손실 합산)에 22%, 공제 없음,
    이듬해 5월 말 납부 — 낼 세금만큼 현금을 남겨 두고 비중을 정하며, 현금이 모자라면 그날 주식을 팔아 냄.
    '총평가'는 오늘 전량 매도하고 세금까지 낸다면 손에 남는 돈(세후 청산 기준), '총평가(세전)'은 현금 + 보유금액."""
    capital = MSTR_PAPER_CAPITAL if capital is None else capital
    rate = MSTR_TAX_RATE if tax_rate is None else tax_rate
    ded = MSTR_TAX_DEDUCT
    bma = b.rolling(120).mean()
    bs = (b > bma).astype(float).where(bma.notna())
    bs.index = bs.index + pd.Timedelta(days=1)            # 미국 종가 판단에는 전날 BTC 일봉 종가 사용 (미래 정보 방지)
    bsig = bs.reindex(m.index, method="ffill")
    mma = m.rolling(200).mean()
    msig = (m > mma).astype(float).where(mma.notna()).shift(1)   # MSTR 신호는 종가가 나와야 확정 → 다음 거래일 종가에 매매
    vol = m.pct_change().rolling(20).std() * np.sqrt(252)
    volf = (vol_target / vol).clip(upper=1.0)
    wk = pd.Series(m.index, index=m.index)
    week_end = set(pd.DatetimeIndex(wk.groupby(m.index.to_period("W-FRI")).max().values))
    fxs = fx.reindex(m.index, method="ffill").bfill() if fx is not None else pd.Series(1350.0, index=m.index)
    days = m.index[m.index >= (start if start is not None else MSTR_PAPER_START)]
    cash, sh, basis, cum = float(capital), 0.0, 0.0, 0.0
    prev, vf, rows = None, None, []
    # 추가 입금: 입금일(또는 그 뒤 첫 미국 거래일) 종가에 현금으로 들어와 목표 비중으로 맞춤
    _deps = sorted([(pd.Timestamp(x["d"]), float(x["a"])) for x in (deposits or []) if float(x.get("a", 0)) > 0], key=lambda t: t[0])
    _di, contributed, prev_total, twr, bh_units = 0, float(capital), None, 1.0, None
    # 세금 상태
    yr_real = {}                  # 해마다 실현손익 (이익 − 손실)
    unpaid = {}                   # 해가 끝나 확정됐지만 아직 안 낸 세금 {연도: 금액}
    tax_paid_cum, cur_year = 0.0, None

    def _sell(q, px):
        nonlocal sh, basis, cash, cum
        proceeds = q * px * (1 - MSTR_PAPER_FEE)
        cost = basis * (q / sh) if sh > 0 else 0.0
        pnl_ = proceeds - cost
        cum += pnl_
        basis -= cost; sh -= q; cash += proceeds
        if sh < 1e-9:
            sh, basis = 0.0, 0.0
        return pnl_

    for k, d in enumerate(days):
        px_usd = float(m[d]); fxv = float(fxs[d]); px = px_usd * fxv
        # 해가 바뀌면 지난해 세금 확정
        if cur_year is None:
            cur_year = d.year
        while d.year > cur_year:
            unpaid[cur_year] = max(0.0, yr_real.get(cur_year, 0.0) - ded) * rate
            cur_year += 1
        dep = 0.0
        while _di < len(_deps) and _deps[_di][0] <= d:
            dep += _deps[_di][1]; _di += 1
        cash += dep; contributed += dep
        # 세금 납부: 이듬해 5월 마지막 평일(휴장이면 그다음 거래일)
        tax_pay, forced = 0.0, False
        for y in sorted(list(unpaid)):
            if d >= pd.offsets.BMonthEnd().rollforward(pd.Timestamp(y + 1, 5, 1)):   # 5월 마지막 평일
                tax_pay += unpaid.pop(y)
        if tax_pay > 0:
            if cash < tax_pay and sh > 0:          # 현금이 모자라면 모자란 만큼 주식을 팔아 냄
                need = (tax_pay - cash) / (px * (1 - MSTR_PAPER_FEE))
                p_ = _sell(min(need, sh), px)
                yr_real[d.year] = yr_real.get(d.year, 0.0) + p_
                forced = True
            cash -= tax_pay; tax_paid_cum += tax_pay
        b_on, m_on = bsig.get(d) == 1, msig.get(d) == 1
        parts = 0.5 * b_on + 0.5 * m_on
        cap = _btc_cycle_state(d)[2] / 100
        if vf is None or d in week_end:
            vf = float(volf.get(d)) if pd.notna(volf.get(d)) else 1.0
        target = parts * cap * vf
        est_cur = max(0.0, yr_real.get(d.year, 0.0) - ded) * rate      # 올해 지금까지 실현이익에 대한 예상 세금
        reserve = sum(unpaid.values()) + est_cur                        # 낼 세금만큼 현금으로 남겨 둠
        value = cash + sh * px - reserve
        cur_w = sh * px / value if value > 0 else 0.0
        reason = ""
        if k == 0:
            reason = "시작"
        elif dep > 0:
            reason = "추가 입금"
        elif prev is not None and parts != prev[0]:
            reason = "신호 변경"
        elif prev is not None and cap != prev[1]:
            reason = "사이클 변경"
        elif d in week_end and abs(target - cur_w) >= MSTR_PAPER_BAND:
            reason = "금요일 비중"
        buy = sell = pnl = 0.0
        if reason:
            diff = target * value - sh * px
            if diff > 1:
                buy = min(diff, max(0.0, cash - reserve))
                q = buy * (1 - MSTR_PAPER_FEE) / px
                sh += q; basis += buy; cash -= buy
            elif diff < -1 and sh > 0:
                q = min(-diff / px, sh)
                sell = q * px
                pnl = _sell(q, px)
                yr_real[d.year] = yr_real.get(d.year, 0.0) + pnl
        hold = sh * px
        pre_total = cash + hold
        # 세후 청산 기준: 오늘 전량 매도(수수료 포함) 후 올해 세금 + 아직 안 낸 지난해 세금까지 낸다면
        liq_gain = hold * (1 - MSTR_PAPER_FEE) - basis
        tax_liq = max(0.0, yr_real.get(d.year, 0.0) + liq_gain - ded) * rate
        total = cash + hold * (1 - MSTR_PAPER_FEE) - sum(unpaid.values()) - tax_liq
        if prev_total is None:
            prev_total = float(capital)
        twr *= (total - dep) / prev_total if prev_total > 0 else 1.0       # 입금을 뺀 순수 투자 성과 (세후)
        prev_total = total
        if bh_units is None:
            bh_units = capital / px
        bh_units += dep / px
        bh_val = bh_units * px * (1 - MSTR_PAPER_FEE)
        bh_after = bh_val - max(0.0, bh_val - contributed - ded) * rate     # 그냥 보유도 오늘 판다면(세후 청산)
        post_w = hold / pre_total if pre_total else 0.0
        if reason:
            if buy:
                why = f"{reason} · 증가" if reason != "시작" else "시작 · 매수"
            elif sell:
                why = f"{reason} · 축소"
            else:
                why = "시작 · 현금 대기" if reason == "시작" else f"{reason} (매매 없음)"
            if tax_pay > 0:
                why += " · 양도세 납부"
        elif tax_pay > 0:
            why = "양도세 납부" + (" · 주식 일부 매도" if forced else " (현금)")
        else:
            why = "-"
        rows.append({"날짜": d.strftime("%Y-%m-%d"), "BTC 120일선": "위" if b_on else "아래", "MSTR 200일선": "위" if m_on else "아래",
                     "사이클 상한 %": cap * 100, "변동성 비중 %": vf * 100, "목표 비중 %": target * 100,
                     "매매 전 비중 %": cur_w * 100, "매매 후 비중 %": post_w * 100, "비중 증감 %p": (post_w - cur_w) * 100,
                     "실제 비중 %": post_w * 100,
                     "매매 사유": why,
                     "매수금액": buy, "매도금액": sell, "보유 주식수": sh, "MSTR 종가 $": px_usd, "환율": fxv,
                     "보유금액": hold, "현금": cash, "매도 손익": pnl if sell else np.nan, "누적 실현손익": cum,
                     "올해 실현손익": yr_real.get(d.year, 0.0), "세금 납부": tax_pay, "낸 세금 합계": tax_paid_cum,
                     "미납 세금": sum(unpaid.values()) + max(0.0, yr_real.get(d.year, 0.0) - ded) * rate,
                     "평가손익": hold - basis, "총평가(세전)": pre_total, "총평가": total, "입금": dep, "누적 투입금": contributed,
                     "손익 금액": total - contributed, "누적 수익률 %": (twr - 1) * 100, "MSTR 그냥 보유": bh_after})
        prev = (parts, cap)
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def mstr_tax_backtest(vol_target=0.8):
    """2020-08-11부터 권장 규칙을 앱에서 다시 계산: 세전 vs 세후(22%, 공제 없음) + MSTR 그냥 보유 (원화 기준)."""
    m, b, fx = get_long_close("MSTR", 8), get_long_close("BTC-USD", 8), get_long_close("KRW=X", 8)
    if m is None or b is None:
        return None
    st0 = pd.Timestamp("2020-08-11")
    out, yearly = [], {}

    def _stats(nav, dates):
        nav = pd.Series(np.asarray(nav, dtype=float), index=pd.to_datetime(dates))
        yrs = (nav.index[-1] - nav.index[0]).days / 365.25
        cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan
        mdd = (nav / nav.cummax() - 1).min()
        r = nav.pct_change().dropna()
        shp = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
        ye = nav.groupby(nav.index.year).last()
        yr_ret = (ye / ye.shift(1).fillna(nav.iloc[0]) - 1) * 100
        return cagr * 100, mdd * 100, shp, nav.iloc[-1] / nav.iloc[0], yr_ret

    for lab, rate in (("세전", 0.0), ("세후", MSTR_TAX_RATE)):
        df = mstr_paper_ledger(m, b, fx, st0, vol_target, 10_000_000, None, tax_rate=rate)
        if df.empty:
            return None
        c, md, sp, mult, yr = _stats(1 + df["누적 수익률 %"] / 100, df["날짜"])
        out.append((f"권장 규칙 (반반 · 변동성 {vol_target * 100:.0f}%) · {lab}", c, md, sp, mult * 10_000_000, df["낸 세금 합계"].iloc[-1]))
        yearly[f"권장 규칙 · {lab}"] = yr
        _bh_pre = (df["MSTR 종가 $"] * df["환율"]) / (df["MSTR 종가 $"].iloc[0] * df["환율"].iloc[0]) * 10_000_000
        bh = df["MSTR 그냥 보유"] if rate > 0 else _bh_pre
        c, md, sp, mult, yr = _stats(bh, df["날짜"])
        _bh_tax = float(_bh_pre.iloc[-1] * (1 - MSTR_PAPER_FEE) - bh.iloc[-1]) if rate > 0 else 0.0
        out.append((f"MSTR 그냥 보유 · {lab}" + (" (오늘 판다면)" if rate > 0 else ""), c, md, sp, mult * 10_000_000, max(0.0, _bh_tax)))
        yearly[f"MSTR 그냥 보유 · {lab}"] = yr
    tbl = pd.DataFrame(out, columns=["규칙", "CAGR %", "MDD %", "샤프", "최종 금액 (1,000만원 시작)", "낸 세금"])
    return tbl, pd.DataFrame(yearly).T, str(m.index[-1].date())


def _load_mstr_deps():
    """관리자 모드 추가 입금 기록 (화면 위쪽 신호판에서도 쓰도록 미리 읽음)."""
    if "mstr_deps" not in st.session_state:
        try:
            raw = _br_get("mstr_deposits.json")
            st.session_state["mstr_deps"] = json.loads(raw.decode("utf-8")).get("items", []) if raw else []
        except Exception:
            st.session_state["mstr_deps"] = []
    return st.session_state["mstr_deps"]


def _friday_check_html(m, vol, vol_target, parts, cap, capital, px_usd, fx, use_deposits=False):
    """📌 금요일 변동성 점검: 장부 기준 지금 비중 → 새 목표(오늘 변동성으로 계산) → 차이 → 매매 금액·LOC 지정가·수량 (2026-10-23)."""
    head = "오늘 밤은 <b>금요일 장 → 변동성 비중 점검</b>"
    try:
        _yrs = max(2, int((pd.Timestamp.today() - MSTR_PAPER_START).days / 365.25) + 2)
        lm, lb, lfx = get_long_close("MSTR", _yrs), get_long_close("BTC-USD", _yrs), get_long_close("KRW=X", _yrs)
        led = mstr_paper_ledger(lm, lb, lfx, MSTR_PAPER_START, vol_target, capital, _load_mstr_deps() if use_deposits else None)
        last = led.iloc[-1]
        sh, cash, owed = float(last["보유 주식수"]), float(last["현금"]), float(last["미납 세금"])
        hold = sh * px_usd * fx                                       # 지금 가격으로 다시 평가
        value = cash + hold - owed                                    # 낼 세금은 빼고 굴리는 돈
        cur_w = hold / value if value > 0 else 0.0
    except Exception:
        return head + " — 장부를 불러오지 못해 숫자를 계산하지 못했습니다. ④ 변동성 비중 칸의 '오늘 값'과 지금 비중을 비교해 10%p 이상 차이 나면 조정하세요."
    v_now = float(vol.iloc[-1])                                       # 연환산 %, 금요일 종가 전이라 가장 최근 종가 기준 값으로 추정
    vf = min(1.0, vol_target * 100 / v_now) if v_now > 0 else 1.0
    tgt = (parts / 100) * (cap / 100) * vf
    diff = (tgt - cur_w) * 100
    amt = abs(tgt * value - hold)
    lines = [f"{head}",
             f"<span style='margin-left:14px;font-size:0.88rem'>① 지금 비중 <b>{cur_w * 100:.0f}%</b> "
             f"(MSTR {hold / 1e4:,.0f}만원 / 굴리는 돈 {value / 1e4:,.0f}만원 · 장부 기준, 지금 가격)</span>",
             f"<span style='margin-left:14px;font-size:0.88rem'>② 새 목표 <b>{tgt * 100:.0f}%</b> = 신호 {parts}% × 상한 {cap}% × 변동성 비중 {vf * 100:.0f}% "
             f"(20일 변동성 {v_now:.0f}% → {vol_target * 100:.0f} ÷ {v_now:.0f})</span>",
             f"<span style='margin-left:14px;font-size:0.88rem'>③ 차이 <b>{diff:+.0f}%p</b> → "
             + (f"<b style='color:#9a3412'>10%p 이상이라 조정</b></span>" if abs(diff) >= MSTR_PAPER_BAND * 100
                else "10%p 미만이라 <b>매매 없음</b> (그대로 보유)</span>")]
    if abs(diff) >= MSTR_PAPER_BAND * 100 and cap > 0:
        if diff > 0:
            lim = px_usd * 1.08; q = int(amt / fx / lim)
            lines.append(f"<span style='display:inline-block;margin:2px 0 0 14px;padding:2px 8px;border-radius:6px;background:#fff;border:1px solid #fdba74;"
                         f"font-size:0.88rem;color:#9a3412'>🧾 LOC <b>매수</b> 약 <b>{amt / 1e4:,.0f}만원</b> · 지정가 <b>&#36;{lim:,.2f}</b> (현재가 +8%) · "
                         f"수량 <b>{q:,}주</b> (지정가 기준 — 증거금 거부 방지)</span>")
        else:
            q = int(amt / fx / px_usd)
            lines.append(f"<span style='display:inline-block;margin:2px 0 0 14px;padding:2px 8px;border-radius:6px;background:#fff;border:1px solid #fdba74;"
                         f"font-size:0.88rem;color:#9a3412'>🧾 LOC <b>매도</b> 약 <b>{amt / 1e4:,.0f}만원</b> · 지정가 <b>&#36;{px_usd * 0.92:,.2f}</b> (현재가 −8%) · "
                         f"수량 약 <b>{q:,}주</b></span>")
    lines.append("<span style='margin-left:14px;font-size:0.8rem;color:#64748b'>금요일 종가가 나오기 전이라 가장 최근 종가로 계산한 추정치입니다. "
                 "실제 계좌 보유가 장부와 다르면 ①의 지금 비중을 실제 보유로 바꿔 생각하세요. 환율 "
                 f"{fx:,.0f}원 기준.</span>")
    return "<br>".join(lines)


def _mstr_signal_panel(vol_target=0.8, key="mstr_sig", capital=None, show_timing=True, use_deposits=False):
    """📡 오늘의 MSTR 신호판: ① BTC 120일선 ② MSTR 200일선 ③ 사이클 상한 ④ 변동성 비중 — 차트를 따로 안 봐도 되게."""
    capital = MSTR_PAPER_CAPITAL if capital is None else capital
    b, m = get_btc_daily_close(), get_mstr_daily_close()
    if b is None or m is None or len(m) < 210:
        st.warning("BTC 또는 MSTR 시세를 불러오지 못해 신호판을 표시할 수 없습니다.")
        return
    bma = b.rolling(120).mean(); mma = m.rolling(200).mean()
    bsig = (b > bma).where(bma.notna()); msig = (m > mma).where(mma.notna())

    def _last_change(sig):
        s_ = sig.dropna().astype(int)
        ch = s_.ne(s_.shift())
        ch.iloc[0] = False
        return s_.index[ch][-1] if ch.any() else None

    def _near(gap):
        return " · <span style='color:#c2410c;font-weight:700'>⚠️ 선 근처(±3% 이내) — 휩소 주의</span>" if abs(gap) < 3 else ""

    b_on, m_on = bool(bsig.iloc[-1]), bool(msig.iloc[-1])
    b_gap = (b.iloc[-1] / bma.iloc[-1] - 1) * 100; m_gap = (m.iloc[-1] / mma.iloc[-1] - 1) * 100
    vol = m.pct_change().rolling(20).std() * np.sqrt(252) * 100
    vf_now = min(100.0, vol_target * 100 / vol.iloc[-1] * 100) if vol.iloc[-1] > 0 else 100.0
    _fri = m[m.index.weekday == 4]
    _fd = _fri.index[-1] if len(_fri) else m.index[-1]
    vf_fri = min(100.0, vol_target * 100 / vol.loc[_fd] * 100) if vol.loc[_fd] > 0 else 100.0
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    _h, _mo, cap, (_nd, _nl) = _btc_cycle_state(today)
    parts = 50 * b_on + 50 * m_on
    target = (parts / 100) * (cap / 100) * (vf_fri / 100)          # 0~1 (예: 0.85 = 85%)

    def _box(title, on, big, lines):
        col = "#16a34a" if on else "#dc2626"
        return (f"<div style='border:2px solid {col};border-radius:12px;padding:10px 14px;background:#fff;height:100%'>"
                f"<div style='font-weight:800;color:#0f2747'>{title}</div>"
                f"<div style='font-size:1.5rem;font-weight:900;color:{col};margin:2px 0'>{big}</div>"
                f"<div style='font-size:0.85rem;color:#334155;line-height:1.6'>{lines}</div></div>")
    _lb = _last_change(bsig); _lm = _last_change(msig)
    # 소제목 모양이지만 위 여백은 아래 여백과 같게 (전역 h5 여백 1.8rem을 받지 않도록 제목 태그 대신 div)
    st.markdown("<div style='font-size:1.125rem;font-weight:700;color:rgb(49,51,63);line-height:1.4;margin:0'>"
                "📡 오늘의 신호 (차트를 따로 안 봐도 되게)</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(_box("① BTC 120일선 (50% 몫)", b_on, "🟢 켜짐 (위)" if b_on else "🔴 꺼짐 (아래)",
                     f"BTC 종가 &#36;{b.iloc[-1]:,.0f} · 120일선 &#36;{bma.iloc[-1]:,.0f}<br>"
                     f"거리 <b>{b_gap:+.1f}%</b>{_near(b_gap)}<br>"
                     f"기준: {b.index[-1]:%Y-%m-%d} 마감 일봉 · 마지막 변경 {(_lb.strftime('%Y-%m-%d') if _lb is not None else '-')}"),
                unsafe_allow_html=True)
    c2.markdown(_box("② MSTR 200일선 (50% 몫)", m_on, "🟢 켜짐 (위)" if m_on else "🔴 꺼짐 (아래)",
                     f"MSTR 종가 &#36;{m.iloc[-1]:,.2f} · 200일선 &#36;{mma.iloc[-1]:,.2f}<br>"
                     f"거리 <b>{m_gap:+.1f}%</b>{_near(m_gap)}<br>"
                     f"기준: {m.index[-1]:%Y-%m-%d} 미국 종가 · 마지막 변경 {(_lm.strftime('%Y-%m-%d') if _lm is not None else '-')}<br>"
                     f"<span style='color:#64748b'>종가가 나와야 확정 → 바뀌면 다음 미국 장 종가에 매매</span>"),
                unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    c3.markdown(_box("③ 반감기 사이클 상한", cap > 0, f"{cap}%",
                     f"{_h:%Y-%m-%d} 반감기 후 {_mo:.1f}개월<br>다음 변경 {_nd:%Y-%m-%d} ({_nl})"), unsafe_allow_html=True)
    c4.markdown(_box(f"④ 변동성 비중 (목표 {vol_target * 100:.0f}%)", True, f"{vf_fri:.0f}%",
                     f"이번 주 적용값: {_fd:%m-%d}(금) 20일 변동성 {vol.loc[_fd]:.0f}% → {vol_target * 100:.0f} ÷ {vol.loc[_fd]:.0f}<br>"
                     f"오늘 값(참고): 변동성 {vol.iloc[-1]:.0f}% → {vf_now:.0f}% · 다음 금요일에 반영"), unsafe_allow_html=True)
    # ── 📌 오늘 할 일 ──
    def _kd(d, year=False):                  # 날짜를 '10월 20일'처럼 (숫자 날짜 10-20은 날짜로 안 읽힘)
        d = pd.Timestamp(d)
        return (f"{d.year}년 " if year else "") + f"{d.month}월 {d.day}일"
    _px_usd = float(m.iloc[-1])
    try:
        _fxs = get_usdkrw_daily()
        _fx = float(_fxs.iloc[-1]) if _fxs is not None else 1350.0
    except Exception:
        _fx = 1350.0

    def _loc(side, amt=None):
        """LOC 주문 참고 줄: 매수는 현재가 +8%, 매도는 −8% 지정가 (종가로 체결되므로 실제로 비싸게 사거나 싸게 팔지 않음)."""
        lim = _px_usd * (1.08 if side == "매수" else 0.92)
        txt = (f"<br><span style='display:inline-block;margin:2px 0 0 14px;padding:2px 8px;border-radius:6px;background:#fff;border:1px solid #fdba74;"
               f"font-size:0.86rem;color:#9a3412'>🧾 LOC <b>{side}</b> 지정가 <b>&#36;{lim:,.2f}</b> (현재가 &#36;{_px_usd:,.2f} {'+8%' if side == '매수' else '−8%'})")
        if amt is not None and amt > 0:
            if side == "매수":           # 증권사가 '지정가 × 수량'만큼 달러를 묶으므로 지정가로 나눠야 주문이 거부되지 않음
                q = int(amt / _fx / lim)
                txt += (f" · 수량 <b>{q:,}주</b> ({amt / 1e4:,.0f}만원 ÷ 환율 {_fx:,.0f}원 ÷ 지정가 &#36;{lim:,.2f} — "
                        f"묶이는 금액 약 {q * lim * _fx / 1e4:,.0f}만원, 실제 체결은 종가라 조금 남음)")
            else:
                q = int(amt / _fx / _px_usd)
                txt += f" · 수량 약 <b>{q:,}주</b> ({amt / 1e4:,.0f}만원 ÷ 환율 {_fx:,.0f}원 ÷ 현재가 &#36;{_px_usd:,.2f})"
        return txt + "</span>"

    _todo = []
    _bch = len(bsig.dropna()) > 1 and bool(bsig.dropna().iloc[-1]) != bool(bsig.dropna().iloc[-2])
    _mch = len(msig.dropna()) > 1 and bool(msig.dropna().iloc[-1]) != bool(msig.dropna().iloc[-2])
    if _bch:
        _todo.append(f"BTC 신호가 {_kd(b.index[-1] + pd.Timedelta(days=1))} 오전 9시에 <b>'{'위' if b_on else '아래'}'</b>로 바뀜 → "
                     f"그날 밤 미국 장 종가(LOC)로 BTC 몫 50% <b>{'매수' if b_on else '매도'}</b>"
                     + (_loc("매수" if b_on else "매도", capital * 0.5 * cap / 100 * vf_fri / 100) if cap > 0 else ""))
    if _mch:
        _todo.append(f"MSTR 신호가 {_kd(m.index[-1])} 미국 종가로 <b>'{'위' if m_on else '아래'}'</b>로 바뀜 → "
                     f"다음 미국 장 종가(LOC)로 MSTR 몫 50% <b>{'매수' if m_on else '매도'}</b>"
                     + (_loc("매수" if m_on else "매도", capital * 0.5 * cap / 100 * vf_fri / 100) if cap > 0 else ""))
    if 0 <= (_nd - today).days <= 3:
        _todo.append(f"사이클 상한이 <b>{_kd(_nd)}</b>부터 바뀜({_nl}) → 그날 밤 미국 장 종가에 목표 비중으로 조정")
    try:                                                         # 사이클 구간이 막 바뀐 날(시작 후 3일 이내)
        _rows_c, _cur_c, _ = _btc_phase_rows(today)
        _ps = _rows_c[_cur_c][5]
        if 0 <= (today - _ps).days <= 3:
            _todo.append(f"사이클 상한이 <b>{_kd(_ps)}</b>부터 <b>{cap}%</b>로 바뀜 → 아직 조정 전이면 미국 장 종가(LOC)로 "
                         f"<b>목표 비중 {(parts / 100) * (cap / 100) * (vf_fri / 100) * 100:.0f}%</b>에 맞춰 매매"
                         + (" (첫 매수)" if cap > 0 and parts > 0 else "")
                         + (_loc("매수", capital * (parts / 100) * (cap / 100) * (vf_fri / 100)) if cap > 0 and parts > 0
                            else (_loc("매도") if cap < 100 else "")))
    except Exception:
        pass
    _now_kst = pd.Timestamp.now(tz="Asia/Seoul")
    if today.weekday() == 4 or (today.weekday() == 5 and _now_kst.hour < 7):     # 금요일 미국 장(한국 금요일 밤 ~ 토요일 새벽)
        _todo.append(_friday_check_html(m, vol, vol_target, parts, cap, capital, _px_usd, _fx, use_deposits))
    if cap == 0 and _todo:
        _todo.append(f"<span style='color:#dc2626'>지금은 사이클 현금 구간이라 신호가 바뀌어도 실제 매매는 없음 ({_kd(_nd, True)}부터 반영)</span>")
    if not _todo:
        _todo.append("신호 변화 없음 → <b>그대로 보유</b> (매매 없음)")
    st.markdown("<div style='border:2px solid #f59e0b;background:#fff7ed;border-radius:12px;padding:10px 16px;margin:10px 0'>"
                "<div style='font-weight:800;color:#9a3412;margin-bottom:4px'>📌 오늘 할 일</div>"
                + "".join(f"<div style='font-size:0.92rem;line-height:1.7'>• {t}</div>" for t in _todo) + "</div>",
                unsafe_allow_html=True)
    _amt = capital * target
    st.markdown(
        f"<div style='border:3px solid #0f2747;border-radius:12px;padding:10px 16px;margin:10px 0;background:#f8fafc'>"
        f"<b>목표 비중 = ({'50' if b_on else '0'} + {'50' if m_on else '0'}) × {cap}% × {vf_fri:.0f}% = "
        f"<span style='font-size:1.25rem;color:#0f2747'>{target * 100:.0f}%</span></b>"
        f" &nbsp;→&nbsp; {capital / 1e4:,.0f}만원 기준 MSTR <b>{_amt:,.0f}원</b> · 현금 {capital - _amt:,.0f}원"
        + ("" if cap > 0 else f"<br><span style='color:#dc2626'>사이클 현금 구간이라 신호와 관계없이 0% — {_nd:%Y-%m-%d}부터 위 신호대로</span>")
        + "</div>", unsafe_allow_html=True)
    with st.expander("📖 읽는 법 — 선 근처에서 샀는데 다음 날 다시 팔게 되면? (휩소 대응 · LOC 증거금)", expanded=False):
        st.markdown("""
**휩소**는 가격이 기준선(BTC 120일선 · MSTR 200일선) 바로 위아래를 오가면서 신호가 하루 이틀 만에 켜졌다 꺼지는 것입니다. 
신호판 칸에 **'⚠️ 선 근처(±3% 이내)'**가 뜨면 이런 일이 생길 수 있다는 뜻입니다.

**1. 오늘 밤 주문은 '어제 종가' 신호로 정해집니다**

| 어제 종가 기준 MSTR 신호 | 오늘 밤 할 일 | 오늘 밤 종가가 200일선 아래로 끝나면 |
|---|---|---|
| 위 | 목표 비중 전체(두 신호 × 상한 × 변동성) 매수 | 내일 밤 **MSTR 몫 50%만** 매도 (BTC 몫은 유지) |
| 아래 | BTC 몫 **50%만** 매수 | 그대로 (MSTR 몫은 이미 0) |

예: 2026-10-20 — 어제 종가 &#36;136.02가 200일선 &#36;135.53보다 0.4% 위 → 오늘 밤 100% 매수. 
그런데 프리마켓이 &#36;134로 이미 선 아래 → 오늘 밤 종가도 아래면 내일 아침 ② 칸이 '아래'로 바뀌고 내일 밤 절반 매도.

**2. 다음 날 절반을 다시 팔면 손해가 크지 않나?**
- 손해는 **MSTR 몫 50%에 대한 하루치 가격 변동 + 사고파는 비용(약 0.2% × 2)** 정도입니다.
- 이런 휩소는 백테스트에 이미 다 들어 있습니다(2024년 여름 한 달 반 사이 7번 매매). 그 비용을 내고 대신 큰 하락(-83%)을 피하는 구조입니다.

**3. "내일 팔 수도 있으니 오늘은 사지 말자"는 안 됩니다**
- 감으로 끼어드는 순간 규칙의 근거가 사라집니다 — 선언문 제2원칙(공포나 탐욕이 아닌 원칙에 기반하여).
- 그렇게 기다리다 크게 오르는 날을 놓치는 경우도 백테스트에 똑같이 많습니다.

**4. 선 근처일 때 순서**
1. ⋮ → Clear cache → 새로고침으로 최신 신호 확인
2. 📌 오늘 할 일의 수량·지정가대로 LOC 주문
3. 다음 날 아침 다시 확인 → ② 칸이 바뀌었으면 그날 밤 해당 몫 50%를 LOC로 매매

**5. LOC 매수 증거금**
증권사는 LOC 매수 때 **지정가 × 수량**만큼 달러를 미리 묶어 둡니다. 그래서 📌 오늘 할 일의 매수 수량은 **지정가 기준**(금액 ÷ 환율 ÷ 지정가)으로 계산해, 계좌에 있는 금액으로 바로 주문이 들어가게 했습니다. 
실제 체결은 종가라 금액이 조금 남고, 남은 현금은 금요일 비중 점검 때 맞추면 됩니다.
""", unsafe_allow_html=True)
    if tab_toggle("📈 최근 6개월 차트 (BTC · MSTR와 기준선)", key=f"{key}_chart_r", open_default=True):
        cc1, cc2 = st.columns(2)
        for col, ser, ma, nm, ln in ((cc1, b, bma, "BTC", "120일선"), (cc2, m, mma, "MSTR", "200일선")):
            _d = pd.DataFrame({"날짜": ser.index, nm: ser.values, ln: ma.values}).tail(130).melt("날짜", [nm, ln], "구분", "가격")
            col.altair_chart(alt.Chart(_d).mark_line().encode(
                x=alt.X("날짜:T", title=None), y=alt.Y("가격:Q", title="$", scale=alt.Scale(zero=False)),
                color=alt.Color("구분:N", scale=alt.Scale(domain=[nm, ln], range=["#0f2747", "#f7931a"]), legend=alt.Legend(orient="top", title=None)),
                tooltip=["구분", alt.Tooltip("날짜:T"), alt.Tooltip("가격:Q", format=",.2f")]).properties(height=220),
                use_container_width=True)
    if show_timing:
        st.markdown("""
**매매 시점 정리** (BTC는 한국 시간 오전 9시 마감 일봉, MSTR은 미국 장 종가 기준 · 시세는 최대 1시간 전 값이라, 오전 9시 직후나 미국 장 마감 직후에 바로 보려면 오른쪽 위 ⋮ → Clear cache 후 새로고침)
- **BTC 신호가 바뀌면 → 그날 밤 미국 장 종가에 매매합니다.** 오전 9시에 이미 확정되니 낮에 LOC 주문을 걸어 두면 됩니다.
- **MSTR 신호가 바뀌면 → 다음 미국 장 종가에 매매합니다.** 종가가 나와야 신호가 확정되므로 하루 늦을 수밖에 없습니다.
- 변동성 비중은 금요일 값으로 한 주 동안 씁니다. 사이클 상한은 정해진 날짜 밤 미국 장 종가에 맞춥니다.
""")
    st.markdown("---")


def _admin_mstr_trading():
    """📈 MSTR 매매: 2026-10-20부터 2,000만원으로 MSTR 반반 규칙을 따랐다면의 일자별 장부."""
    st.markdown("#### 📈 MSTR 매매")
    _mstr_signal_panel(0.8, use_deposits=True)
    st.markdown("##### 📒 장부")
    _mode = st.radio("장부", [f"실제 장부 ({MSTR_PAPER_START:%Y-%m-%d} 시작)", "샘플 A (2022-11-11 시작 · 변동성 목표 80%)",
                             "샘플 B (2022-11-11 시작 · 이전 규칙 변동성 60%)"], horizontal=True, key="mstr_paper_mode")
    _vt = 0.8                                   # 2026-10-16 결정: 변동성 목표 80%
    if _mode.startswith("샘플 A"):
        _start, _vt = pd.Timestamp("2022-11-11"), 0.8
        st.info("📎 샘플 A (지금 규칙): 지난 사이클 '④ 다음 사이클 준비' 시작일(2022-11-11)부터 2,000만원으로, 변동성 목표 80%로 했다면의 장부입니다. "
                "④ 100% → 2024-04 반감기 후 ① 100% → ② 50%(2025-04-21) → ③ 0%(2025-07-21, 전량 매도) → 오늘까지 한 사이클 전체가 들어 있습니다.")
    elif _mode.startswith("샘플 B"):
        _start, _vt = pd.Timestamp("2022-11-11"), 0.6
        st.info("📎 샘플 B (이전 규칙 · 비교용): 샘플 A와 같은 날·같은 금액이지만 변동성 목표가 60%였던 이전 규칙의 장부입니다. "
                "급등 구간에서 비중을 더 많이 줄였던 차이를 비교해 볼 수 있습니다. "
                "④ 100% → 2024-04 반감기 후 ① 100% → ② 50%(2025-04-21) → ③ 0%(2025-07-21, 전량 매도) → 오늘까지 한 사이클 전체가 들어 있습니다.")
    else:
        _start = MSTR_PAPER_START
    _deps = None
    if _mode.startswith("실제"):
        _deps = _mstr_deposits_ui()
    _render_mstr_ledger(_start, _vt, key="mstr_paper", deposits=_deps, compare_prev=_mode.startswith("실제"))


def _mstr_deposits_ui():
    """➕ MSTR 추가 입금 기록 (관리자 모드 · 실제 장부): 날짜·금액을 저장해 두면 장부가 그날 종가에 목표 비중으로 맞춤."""
    if "mstr_deps" not in st.session_state:
        try:
            raw = _br_get("mstr_deposits.json")
            st.session_state["mstr_deps"] = json.loads(raw.decode("utf-8")).get("items", []) if raw else []
        except Exception:
            st.session_state["mstr_deps"] = []
    deps = st.session_state["mstr_deps"]
    _tot = sum(float(x["a"]) for x in deps)
    with st.expander(f"➕ 추가 입금 기록 ({len(deps)}건 · {_tot / 1e4:,.0f}만원)" if deps else "➕ 추가 입금 기록", expanded=False):
        st.caption("MSTR 몫에 돈을 더 넣었을 때 적어 두면, 그날(주말·휴일이면 다음 미국 거래일) 종가에 현금으로 들어가 목표 비중대로 맞춰집니다. "
                   "넣기 전에 개별투자 합계가 운용자금의 10% 이내인지 확인하세요.")
        with st.form("mstr_dep_form", border=False):
            c1, c2, c3 = st.columns([1, 1, 1.4])
            _d = c1.date_input("입금 날짜", value=pd.Timestamp.now(tz="Asia/Seoul").date())
            _a = c2.number_input("금액 (만원)", min_value=0, step=100, value=0)
            _mm = c3.text_input("메모 (선택)", placeholder="예: 10월 추가분")
            b1, b2 = st.columns([1, 1])
            _add = b1.form_submit_button("➕ 입금 저장", use_container_width=True)
            _del = b2.multiselect("지울 기록", [f"{x['d']} · {float(x['a']) / 1e4:,.0f}만원" for x in deps],
                                  placeholder="지울 기록 고르기", label_visibility="collapsed")
            _rm = st.form_submit_button("🗑️ 고른 기록 지우기", use_container_width=True)

        def _save():
            return _br_put("mstr_deposits.json", json.dumps({"items": deps}, ensure_ascii=False, indent=1).encode("utf-8"), "MSTR 추가 입금 기록")
        if _add and _a > 0:
            deps.append({"d": str(_d), "a": float(_a) * 10_000, "m": _mm.strip()})
            deps.sort(key=lambda x: x["d"])
            if _save():
                st.success(f"{_d} · {_a:,.0f}만원 저장했습니다.")
        if _rm and _del:
            keep = [x for x in deps if f"{x['d']} · {float(x['a']) / 1e4:,.0f}만원" not in _del]
            deps[:] = keep
            if _save():
                st.success("지웠습니다.")
        if deps:
            st.dataframe(pd.DataFrame([{"날짜": x["d"], "금액 (원)": f"{float(x['a']):,.0f}", "메모": x.get("m", "")} for x in deps]),
                         use_container_width=True, hide_index=True)
    return deps


# ── 이번 사이클 vs 지난 사이클 (2026-10-22) ──
MSTR_PREV_CYCLE_START = pd.Timestamp("2022-11-11")      # 지난 사이클 '④ 다음 사이클 준비' 시작일 (2020-05-11 반감기 + 30개월)
MSTR_PREV_CYCLE_MARKS = [(pd.Timestamp("2024-04-20"), "반감기 · ① 100%"), (pd.Timestamp("2025-04-21"), "② 50%"),
                         (pd.Timestamp("2025-07-21"), "③ 0% 전량 매도")]


def _render_cycle_compare(df_now, vt, capital, key):
    """실시간·실제 장부 아래: 이번 사이클과 지난 사이클을 같은 출발점(④ 시작일)·같은 금액에서 겹쳐 봄. x축 = 시작 후 거래일."""
    _yrs = max(2, int((pd.Timestamp.today() - MSTR_PREV_CYCLE_START).days / 365.25) + 2)   # 지난 사이클 장부와 같은 시세(캐시 공유)
    m, b, fx = get_long_close("MSTR", _yrs), get_long_close("BTC-USD", _yrs), get_long_close("KRW=X", _yrs)
    if m is None or b is None:
        st.caption("지난 사이클 시세를 불러오지 못해 비교 그래프를 표시할 수 없습니다.")
        return
    prev = mstr_paper_ledger(m, b, fx, MSTR_PREV_CYCLE_START, vt, capital)
    cur_v = capital * (1 + df_now["누적 수익률 %"].values / 100)       # 추가 입금은 빼고 순수 투자 성과로
    prev_v = capital * (1 + prev["누적 수익률 %"].values / 100)
    n_now = len(cur_v)
    _cur_lab = f"이번 사이클 ({df_now['날짜'].iloc[0]}\u007e)"
    _prev_lab = f"지난 사이클 ({MSTR_PREV_CYCLE_START:%Y-%m-%d}\u007e)"
    st.markdown(f"**이번 사이클 vs 지난 사이클** — 같은 출발점('④ 다음 사이클 준비' 시작일)에서 같은 금액 {capital / 1e4:,.0f}만원으로 규칙대로 매매했을 때")
    _rng = st.radio("보기 범위", ["지난 사이클 전체 (앞으로의 참고)", "같은 기간만"], horizontal=True, key=f"{key}_cmp_rng")
    _np = len(prev_v) if _rng.startswith("지난") else min(n_now, len(prev_v))
    d = pd.concat([
        pd.DataFrame({"경과 거래일": np.arange(_np), "평가액": prev_v[:_np], "구분": _prev_lab, "날짜": prev["날짜"].values[:_np]}),
        pd.DataFrame({"경과 거래일": np.arange(n_now), "평가액": cur_v, "구분": _cur_lab, "날짜": df_now["날짜"].values}),
    ], ignore_index=True)
    _col = alt.Color("구분:N", scale=alt.Scale(domain=[_cur_lab, _prev_lab], range=["#f7931a", "#2563eb"]),
                     legend=alt.Legend(orient="bottom", title=None, labelLimit=220))
    _line = alt.Chart(d).mark_line(strokeWidth=2).encode(
        x=alt.X("경과 거래일:Q", title="시작 후 거래일 (약 250일 = 1년)"),
        y=alt.Y("평가액:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(labelExpr="datum.value >= 1e8 ? format(datum.value / 1e8, ',.1f') + '억' : format(datum.value / 1e4, ',.0f') + '만'")),
        color=_col, tooltip=["구분", "날짜", "경과 거래일", alt.Tooltip("평가액:Q", format=",.0f")])
    _now_pt = alt.Chart(d[d["구분"] == _cur_lab].tail(1)).mark_point(size=90, filled=True, color="#f7931a").encode(
        x="경과 거래일:Q", y="평가액:Q", tooltip=["구분", "날짜", alt.Tooltip("평가액:Q", format=",.0f")])
    _layers = [_line, _now_pt]
    # 지난 사이클의 구간 변경 시점 (세로 점선)
    _pd = pd.to_datetime(prev["날짜"])
    _mk = pd.DataFrame([{"경과 거래일": int((_pd < dt).sum()), "표시": lab} for dt, lab in MSTR_PREV_CYCLE_MARKS if int((_pd < dt).sum()) < _np])
    if not _mk.empty:
        _layers.append(alt.Chart(_mk).mark_rule(strokeDash=[4, 3], color="#94a3b8").encode(x="경과 거래일:Q", tooltip=["표시"]))
        _layers.append(alt.Chart(_mk).mark_text(align="left", dx=4, dy=-6, fontSize=11, color="#475569").encode(
            x="경과 거래일:Q", y=alt.value(12), text="표시"))
    st.altair_chart(alt.layer(*_layers).properties(height=260), use_container_width=True)
    _k = min(n_now, len(prev_v)) - 1
    _cur_r = (cur_v[-1] / capital - 1) * 100
    _prev_r = (prev_v[_k] / capital - 1) * 100
    _prev_end = (prev_v[-1] / capital - 1) * 100
    _pk = prev_v / np.maximum.accumulate(prev_v) - 1
    st.caption(f"같은 경과일({_k + 1}거래일째): 이번 사이클 {_cur_r:+.1f}% · 지난 사이클 {_prev_r:+.1f}% · "
               f"지난 사이클은 이후 오늘까지 {_prev_end:+.1f}%(최고 {(prev_v.max() / capital - 1) * 100:+.0f}%, 최대 낙폭 {_pk.min() * 100:.0f}%)")
    with st.expander("📖 사이클 비교 그래프 읽는 법", expanded=False):
        st.markdown("""
- 두 사이클을 **날짜가 아니라 '시작 후 몇 거래일째인지'**로 맞춰 겹쳤습니다. 둘 다 반감기 후 30개월, 사이클 현금 구간이 끝나 다시 사기 시작한 날이 출발점입니다.
- **주황 = 이번 사이클**(굵은 점이 오늘), **파랑 = 지난 사이클**. 지난 사이클의 세로 점선은 반감기(① 100%) · ② 50% 축소 · ③ 0% 전량 매도 시점입니다.
- 이번 사이클도 비슷한 흐름이면 약 1년 반 뒤 다음 반감기(2028년 4월 추정), 그 1년 뒤 ② 50% 축소가 옵니다.
- **지난 사이클은 참고선일 뿐 예측이 아닙니다.** 표본이 한 번뿐이고, 비트코인 사이클은 회를 거듭할수록 약해지고 있습니다. 같은 경과일에 이번 선이 아래에 있어도 규칙은 그대로 따릅니다.
- 추가 입금이 있으면 입금을 뺀 투자 성과로 계산해 두 사이클을 같은 금액으로 비교합니다.
""")


def _render_mstr_ledger(_start, _vt=0.8, key="mstr_paper", capital=None, deposits=None, compare_prev=False):
    """MSTR 장부 화면 (요약 숫자 · 오늘의 목표 비중 · 표 · 그래프 · 낙폭). 관리자 모드와 MSTR 탭이 함께 씀."""
    capital = MSTR_PAPER_CAPITAL if capital is None else capital
    st.caption(f"변동성 목표 {_vt * 100:.0f}% · 시작 {_start:%Y-%m-%d} · 배정 금액 {capital:,.0f}원 · 미국 장 종가 체결 · 그날 원/달러 환율로 원화 환산 · "
               f"수수료·슬리피지 편도 {MSTR_PAPER_FEE * 100:.1f}% · 양도세 {MSTR_TAX_RATE * 100:.0f}%(공제 없음, 한 해 이익·손실 합산, 이듬해 5월 말 납부) · "
               "총평가 = 오늘 전량 매도하고 세금까지 냈을 때 남는 돈(세후 청산 기준) · 금요일 비중 조정은 차이 {MSTR_PAPER_BAND * 100:.0f}%p 이상일 때만 · "
               "BTC 신호는 그날 밤, MSTR 신호는 다음 미국 장 종가에 반영(표의 'MSTR 200일선'은 그날 매매에 쓴 전 거래일 신호)")
    # 시작일보다 최소 1년 앞선 시세가 있어야 200일선·120일선이 맞게 계산됨 → 긴 시세 사용
    _yrs = max(2, int((pd.Timestamp.today() - _start).days / 365.25) + 2)
    m, b, fx = get_long_close("MSTR", _yrs), get_long_close("BTC-USD", _yrs), get_long_close("KRW=X", _yrs)
    if m is None or b is None:
        st.warning("MSTR 또는 BTC 시세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return
    if fx is None:
        st.caption("⚠️ 환율을 불러오지 못해 1,350원/$로 계산했습니다.")
    df = mstr_paper_ledger(m, b, fx, _start, _vt, capital, deposits)
    if df.empty:
        st.info(f"{MSTR_PAPER_START:%Y-%m-%d}(미국 장)부터 장부가 시작됩니다. 그날 BTC 120일선·MSTR 200일선 신호, 사이클 상한(그날부터 100%), "
                "변동성 비중으로 첫 매수 금액이 정해지고, 이후 매일 자동으로 한 줄씩 쌓입니다. 화면 구성은 위에서 '샘플'을 골라 미리 볼 수 있습니다.")
        return
    last = df.iloc[-1]
    k1, k2, k3, k4 = st.columns(4)
    _has_dep = df["입금"].sum() > 0
    # 큰 숫자가 칸에 다 안 들어가 '10,163,1…'로 잘리던 문제 → 만원·억원 단위로 짧게 표시, 원 단위 전체 값은 ⓘ(도움말)에 (2026-10-23)
    def _sg(x):
        return ("+" if x > 0 else "") + fmt_krw(x)
    k1.metric("총평가", fmt_krw(last['총평가']), f"투자 성과 {last['누적 수익률 %']:+.2f}%", help=f"{last['총평가']:,.0f}원")
    k2.metric("손익 금액", _sg(last['손익 금액']), f"투입 {last['누적 투입금'] / 1e4:,.0f}만원" + (" (추가 입금 포함)" if _has_dep else ""),
              help=f"{last['손익 금액']:+,.0f}원")
    k3.metric("보유금액", fmt_krw(last['보유금액']), f"비중 {last['실제 비중 %']:.0f}%", help=f"{last['보유금액']:,.0f}원")
    k4.metric("세금 (낸 것 + 낼 것)", fmt_krw(last['낸 세금 합계'] + last['미납 세금']),
              f"올해 실현손익 {_sg(last['올해 실현손익'])}", delta_color="off",
              help=f"낸 세금 {last['낸 세금 합계']:,.0f}원 · 아직 안 낸 세금(올해 실현이익 기준 예상 포함) {last['미납 세금']:,.0f}원 · "
                   f"누적 실현손익 {last['누적 실현손익']:+,.0f}원")
    if _has_dep:
        st.caption("투자 성과 %는 추가 입금을 뺀 순수 운용 성과(시간가중 수익률)입니다. 손익 금액 = 총평가 − 누적 투입금.")
    _tv = df["총평가"]
    _ntr = int(((df["매수금액"] > 0) | (df["매도금액"] > 0)).sum())
    st.caption(f"매매 {_ntr}회 · 최대 낙폭(총평가) {(_tv / _tv.cummax() - 1).min() * 100:.1f}% · "
               f"수수료·슬리피지 합계 약 {(df['매수금액'].sum() + df['매도금액'].sum()) * MSTR_PAPER_FEE:,.0f}원 · "
               f"총평가(세전 · 현금+보유) {last['총평가(세전)']:,.0f}원 · 최고 총평가 {_tv.max():,.0f}원 ({df.loc[_tv.idxmax(), '날짜']})")
    st.markdown(f"**오늘의 목표 비중 {last['목표 비중 %']:.0f}%** = (BTC 120일선 {last['BTC 120일선']} · MSTR 200일선 {last['MSTR 200일선']}) "
                f"× 사이클 상한 {last['사이클 상한 %']:.0f}% × 변동성 비중 {last['변동성 비중 %']:.0f}% · 기준일 {last['날짜']}")
    _only = st.radio("보기", ["매매한 날만", "모든 날"], horizontal=True, key=f"{key}_view")
    view = df[(df["매수금액"] > 0) | (df["매도금액"] > 0) | (df["입금"] > 0) | (df["세금 납부"] > 0) | (df.index == 0)] if _only == "매매한 날만" else df
    _dep_cols = ["입금", "누적 투입금"] if _has_dep else []
    show = view[["날짜", "BTC 120일선", "MSTR 200일선", "사이클 상한 %", "변동성 비중 %", "목표 비중 %",
                 "매매 전 비중 %", "비중 증감 %p", "매매 후 비중 %", "매매 사유"] + _dep_cols +
                ["매수금액", "매도금액", "보유금액", "현금", "매도 손익", "누적 실현손익", "세금 납부", "미납 세금",
                 "총평가(세전)", "총평가", "누적 수익률 %", "MSTR 종가 $", "환율"]].iloc[::-1]
    def _pp(v):
        return "-" if abs(v) < 0.5 else f"{v:+.0f}"
    st.dataframe(show.style.format({"사이클 상한 %": "{:.0f}", "변동성 비중 %": "{:.0f}", "목표 비중 %": "{:.0f}",
                                    "매매 전 비중 %": "{:.0f}", "매매 후 비중 %": "{:.0f}", "비중 증감 %p": _pp,
                                    "매수금액": "{:,.0f}", "매도금액": "{:,.0f}", "보유금액": "{:,.0f}", "현금": "{:,.0f}",
                                    "매도 손익": "{:+,.0f}", "누적 실현손익": "{:+,.0f}", "총평가": "{:,.0f}", "총평가(세전)": "{:,.0f}",
                                    "세금 납부": lambda v: "-" if not v else f"{v:,.0f}", "미납 세금": lambda v: "-" if not v else f"{v:,.0f}",
                                    "누적 수익률 %": "{:+.2f}", "MSTR 종가 $": "{:,.2f}", "환율": "{:,.1f}",
                                    "입금": lambda v: "-" if not v else f"+{v:,.0f}", "누적 투입금": "{:,.0f}"}, na_rep="-"),
                 use_container_width=True, hide_index=True, height=min(420, 38 + 35 * len(show)))
    _few = len(df) < 40                     # 시작한 지 얼마 안 된 장부: 선이 짧아 점을 함께 찍음
    if len(df) >= 1:                        # 2026-10-22: 시작 첫날(1줄)에도 그래프가 보이게 (전에는 2줄 이상일 때만)
        _c = df[["날짜", "총평가", "MSTR 종가 $", "환율"]].copy()
        _c["MSTR 그냥 보유"] = df["MSTR 그냥 보유"].values      # 같은 날 같은 금액(추가 입금 포함)을 MSTR에 그냥 넣었다면
        _c = _c.rename(columns={"총평가": "규칙대로 매매"})
        _c["날짜"] = pd.to_datetime(_c["날짜"])
        _l = _c.melt("날짜", ["규칙대로 매매", "MSTR 그냥 보유"], "구분", "평가액")
        st.markdown("**총평가 추이** (세후 청산 기준) — 같은 금액으로 MSTR을 그냥 들고 있었을 때(역시 오늘 판다면 세후)와 비교 · 초록 선 = 비트코인 가격(오른쪽 축, $)")
        _base = alt.Chart(_l).mark_line(point=_few).encode(
            x=alt.X("날짜:T", title=None),
            y=alt.Y("평가액:Q", title=None, scale=alt.Scale(zero=False),
                    axis=alt.Axis(labelExpr="datum.value >= 1e8 ? format(datum.value / 1e8, ',.1f') + '억' : format(datum.value / 1e4, ',.0f') + '만'")),
            color=alt.Color("구분:N", scale=alt.Scale(domain=["규칙대로 매매", "MSTR 그냥 보유", "비트코인 가격"],
                                                     range=["#f7931a", "#94a3b8", "#16a34a"]),
                            legend=alt.Legend(orient="bottom", title=None, columns=3, labelLimit=140)),
            strokeDash=alt.condition("datum['구분'] == 'MSTR 그냥 보유'", alt.value([4, 3]), alt.value([1, 0])),
            tooltip=["구분", alt.Tooltip("날짜:T"), alt.Tooltip("평가액:Q", format=",.0f")])
        _chart = _base
        try:
            if b is not None:
                _bt = b.reindex(_c["날짜"], method="ffill")
                _bdf = pd.DataFrame({"날짜": _c["날짜"].values, "BTC $": _bt.values, "구분": "비트코인 가격"}).dropna()
                _btc_line = alt.Chart(_bdf).mark_line(strokeWidth=1.3, opacity=0.85, point=_few).encode(
                    x="날짜:T",
                    y=alt.Y("BTC $:Q", title=None, scale=alt.Scale(zero=False),
                            axis=alt.Axis(orient="right", titleColor="#16a34a", labelColor="#16a34a",
                                          labelExpr="'$' + format(datum.value / 1000, ',.0f') + 'k'")),
                    color=alt.Color("구분:N", scale=alt.Scale(domain=["규칙대로 매매", "MSTR 그냥 보유", "비트코인 가격"],
                                                             range=["#f7931a", "#94a3b8", "#16a34a"])),
                    tooltip=[alt.Tooltip("날짜:T"), alt.Tooltip("BTC $:Q", format=",.0f", title="비트코인 $")])
                _chart = alt.layer(_base, _btc_line).resolve_scale(y="independent")
        except Exception:
            _chart = _base
        st.altair_chart(_chart.properties(height=260), use_container_width=True)
        # ── 낙폭(MDD) 그래프: 각 날짜가 그때까지의 최고점보다 몇 % 아래인지 (2026-10-22) ──
        #    추가 입금이 낙폭을 가리지 않도록 규칙은 입금을 뺀 투자 성과, 그냥 보유는 투입금 1원당 세후 평가액으로 계산
        _dd = pd.DataFrame({"날짜": _c["날짜"]})
        _perf = 1 + df["누적 수익률 %"].values / 100
        _bh = (df["MSTR 그냥 보유"] / df["누적 투입금"]).values           # 그냥 보유도 세후 청산 기준(투입금 1원당)
        _dd["규칙대로 매매"] = (_perf / np.maximum.accumulate(_perf) - 1) * 100
        _dd["MSTR 그냥 보유"] = (_bh / np.maximum.accumulate(_bh) - 1) * 100
        _ddl = _dd.melt("날짜", ["규칙대로 매매", "MSTR 그냥 보유"], "구분", "낙폭")
        _mdd_r, _mdd_b = float(_dd["규칙대로 매매"].min()), float(_dd["MSTR 그냥 보유"].min())
        st.markdown(f"**낙폭 (MDD)** — 그때까지의 최고점보다 몇 % 아래인지 · 최대 낙폭: 규칙대로 매매 **{_mdd_r:.1f}%** · "
                    f"MSTR 그냥 보유 **{_mdd_b:.1f}%**")
        st.altair_chart(alt.Chart(_ddl).mark_area(opacity=0.35, line=True, point=_few).encode(
            x=alt.X("날짜:T", title=None),
            y=alt.Y("낙폭:Q", title=None, stack=None, scale=alt.Scale(domain=[min(-5.0, float(_ddl["낙폭"].min()) * 1.05), 0]),
                    axis=alt.Axis(labelExpr="format(datum.value, '.0f') + '%'")),
            color=alt.Color("구분:N", scale=alt.Scale(domain=["규칙대로 매매", "MSTR 그냥 보유"], range=["#f7931a", "#94a3b8"]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["구분", alt.Tooltip("날짜:T"), alt.Tooltip("낙폭:Q", format=".1f", title="낙폭 %")]).properties(height=200),
            use_container_width=True)
        with st.expander("📖 낙폭 그래프 읽는 법", expanded=False):
            st.markdown(f"""
- **0%** = 그날이 지금까지의 최고점(신고점)입니다. 아래로 내려갈수록 최고점에서 많이 빠진 상태입니다.
- 가장 깊은 곳이 **최대 낙폭(MDD)** — 이 장부에서는 규칙 {_mdd_r:.1f}%, 그냥 보유 {_mdd_b:.1f}%.
  예를 들어 -40%는 1,000만원이 최고 1,500만원까지 올랐다가 900만원으로 줄어든 것과 같습니다.
- 규칙(주황)은 신호가 꺼지거나 사이클 현금 구간이면 현금으로 물러나 바닥이 얕고, 그냥 보유(회색)는 하락장을 그대로 맞습니다.
- 낙폭이 얕아야 규칙을 끝까지 지킬 수 있습니다 — 선언문 제1원칙(생존). 추가 입금이 있으면 입금을 뺀 투자 성과로 계산합니다.
""")
        if compare_prev:
            try:
                _render_cycle_compare(df, _vt, capital, key)
            except Exception as _e_cmp:
                st.caption(f"지난 사이클 비교 그래프를 그리지 못했습니다: {_e_cmp}")
    st.caption("최신 날짜가 맨 위입니다. 규칙대로 미국 장 종가에 매매했다고 보고 계산한 것이라 실제 체결가·환율·세금과 조금 다를 수 있으며, 실제 매매 기록은 '💼 내 보유 현황'에 따로 남기세요. "
               "MSTR을 포함한 개별투자는 운용자금의 10% 이내 (투자 원칙 선언문).")


def render_watchlist():
    """⭐ 내 관심 종목: 비밀번호로 잠근 나만의 목록. 랭킹을 불러오지 않고 종목 차트·보유 기준만 봄."""
    with st.expander("🔧 관리자 모드", expanded=bool(st.session_state.get("wl_open"))):
        pw_need = _wl_secret("WATCHLIST_PASSWORD") or _wl_secret("UPLOAD_PASSWORD")
        if st.session_state.get("_is_owner"):          # 접속 화면에서 내 비밀번호(OWNER_PASSWORD)로 들어왔으면 바로 열림
            st.session_state["wl_ok"] = True
        if pw_need and not st.session_state.get("wl_ok"):
            with st.form("wl_login", border=False):
                _p = st.text_input("확인", type="password", key="wl_pw", label_visibility="collapsed", placeholder="••••")
                if st.form_submit_button("열기", use_container_width=True):
                    if _p == pw_need:
                        st.session_state["wl_ok"] = True
                        st.session_state["wl_open"] = True
                        st.rerun()
                    else:
                        st.error("맞지 않습니다.")
            return
        st.session_state["wl_open"] = True
        _menu = st.radio("관리자 메뉴", ["📜 투자 선언문", "⭐ 관심 종목", "💼 내 보유 현황", "📈 MSTR 매매", "📊 내 백테스트 결과"],
                         horizontal=True, key="admin_menu", label_visibility="collapsed")
        if not pw_need:
            st.caption("PC(로컬) 실행 중: 저장 내용은 이 PC 폴더(watchlist_local.json · admin_local)에 따로 보관됩니다.")
        if _menu.startswith("📜"):
            _admin_manifesto()
        elif _menu.startswith("⭐"):
            _admin_watchlist()
        elif _menu.startswith("💼"):
            _admin_holdings()
        elif _menu.startswith("📈"):
            _admin_mstr_trading()
        else:
            _admin_results()


def _admin_watchlist():
    """⭐ 관심 종목 (관리자 모드 메뉴)."""
    if "wl_items" not in st.session_state:
        st.session_state["wl_items"] = _wl_load()
    items = st.session_state["wl_items"]

    # ── 추가 · 지우기 ──
    with st.form("wl_add", border=False):
        _q = st.text_input("추가할 티커 (여러 개는 쉼표로 · 미국 주식·ETF 모두 가능)", placeholder="예: TSLA, PLTR, VOO")
        _c1, _c2 = st.columns([1, 1])
        _add = _c1.form_submit_button("➕ 추가·저장", use_container_width=True)
        _del = _c2.multiselect("지울 종목", [x["t"] for x in items], placeholder="눌러서 고르기", label_visibility="collapsed")
        _rm = st.form_submit_button("🗑️ 고른 종목 지우기·저장", use_container_width=True)
    if _add and _q.strip():
        _have = {x["t"] for x in items}
        _today = datetime.date.today().isoformat()
        for t in [x.strip().upper().replace(".", "-") for x in _q.replace("，", ",").split(",") if x.strip()]:
            if t not in _have and t.replace("-", "").isalnum() and len(t) <= 6:
                items.append({"t": t, "d": _today}); _have.add(t)
        if _wl_save(items):
            st.success("저장했습니다.")
    if _rm and _del:
        items = [x for x in items if x["t"] not in _del]
        st.session_state["wl_items"] = items
        if _wl_save(items):
            st.success("지웠습니다.")
    if not items:
        st.info("아직 관심 종목이 없습니다. 위에 티커를 넣고 '추가·저장'을 누르세요.")
        return

    # ── 한눈에 보기 ──
    rows = []
    for x in items:
        raw = get_stock_chart_data(x["t"], "SPY")
        if raw is None or "Close" not in raw:
            rows.append({"티커": x["t"], "보유 기준": "시세 없음", "현재가": "-", "200일선 대비": "-", "기준": "-", "추가일": x.get("d", "")})
            continue
        cl = raw["Close"].dropna()
        lab, gap, kind = _wl_status(cl, _wl_rule(x["t"]))
        rows.append({"티커": x["t"], "보유 기준": lab, "현재가": f"{cl.iloc[-1]:,.2f}",
                     "200일선 대비": "-" if pd.isna(gap) else f"{gap:+.1f}%", "기준": kind, "추가일": x.get("d", "")})
    st.markdown("**한눈에 보기** (최근 종가 기준 · 실제 매매 판단은 월말 종가)")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("🔴 매도 기준 = 200일선 −3% 아래(월말 종가도 아래면 매도) · 🟡 경계 = 200일선 아래 3% 이내 · "
               "🟢 = 보유. 재매수 기준은 개별 종목 +5%, ETF는 종류별(지수형은 200일선 회복).")

    # ── 종목 차트 ──
    if tab_toggle("📈 종목 차트 보기 (종목당 1\\~2초)", key="wl_charts_r"):
        for j, x in enumerate(items):
            with st.expander(f"📈 {x['t']}", expanded=(j == 0)):
                render_stock_chart(x["t"], "SPY", "wl", show_rules=True, bench_label="SPY", etf_rule=_wl_rule(x["t"]))


def render_etf_search():
    """🔎 ETF 검색: 랭킹에 없는 ETF도 티커로 바로 차트·보유 기준 확인 (미국 주식 랭킹의 종목 검색과 같은 화면)."""
    _known = sorted(set([t for t in ALL_TICKERS if t != "TIP"] + [t for g in SECTOR_GROUPS.values() for t in g]))

    def _nm(t):
        return TICKER_INFO.get(t, ("", ""))[0]

    with st.container(border=True):
        st.markdown("#### 🔎 ETF 검색")
        with st.form(key="etf_search_form", clear_on_submit=False, border=False):
            _q = st.text_input("ETF 티커나 이름을 입력하고 Enter (여러 개는 쉼표로 구분 · 랭킹에 없는 미국 ETF도 티커로 검색 가능)",
                               key="etf_search_text", placeholder="예: VOO, SOXX, IBIT, 반도체, 금, 배당")
            _c1, _c2 = st.columns([1, 1])
            _go = _c1.form_submit_button("🔍 검색", use_container_width=True)
            _clr = _c2.form_submit_button("지우기", use_container_width=True)
        if _clr:
            st.session_state["etf_search_list"] = []
        elif _go:
            _found, _miss = [], []
            for _term in [x.strip() for x in _q.replace("，", ",").split(",") if x.strip()]:
                _tu = _term.upper().replace(".", "-")
                _looks_tk = _tu.isascii() and _tu.replace("-", "").isalnum() and len(_tu) <= 6
                if _tu in _known:                          # 랭킹에 있는 티커
                    _found.append(_tu)
                    continue
                _tl = _term.lower()                        # 한글·영문 이름 일부 → 랭킹에 있는 ETF 중 최대 5개
                _hits = [t for t in _known if _tl in " ".join([t, *TICKER_INFO.get(t, ("", ""))]).lower()][:5]
                if _hits and not (_looks_tk and _term.isupper()):   # 대문자로 친 짧은 글자는 티커로 우선
                    _found.extend(_hits)
                elif _looks_tk:                            # 랭킹에 없는 ETF → 티커로 그대로 조회
                    _found.append(_tu)
                else:
                    _miss.append(_term)
            st.session_state["etf_search_list"] = list(dict.fromkeys(_found))
            st.session_state["etf_search_miss"] = _miss
        if _clr:
            st.session_state["etf_search_miss"] = []
        if st.session_state.get("etf_search_miss"):
            st.warning(f"찾지 못한 검색어: {', '.join(st.session_state['etf_search_miss'])} — 랭킹에 없는 ETF는 티커(예: VOO)로 입력해 주세요.")
        _pick = st.session_state.get("etf_search_list", [])
        if _pick:
            st.caption("고른 ETF만 서버에서 3년치 시세를 따로 받아 계산합니다(1개당 1\\~2초, 이후 1시간은 바로 표시). "
                       "보유 기준은 ETF 종류별로 다릅니다(ETF 49개 백테스트 근거): 지수·섹터·국가·배당 = −3% 매도·200일선 회복 재매수, "
                       "테마·원자재 = −3% 매도·+5% 재매수, 채권·금 = 참고용, 레버리지·인버스 = 미적용. 판단은 월말 종가 1회.")
            for _j, _tk in enumerate(_pick):
                _label = f"📈 {_tk} · {_nm(_tk)}" if _nm(_tk) else f"📈 {_tk}"
                with st.expander(_label, expanded=(_j == 0)):
                    _desc = TICKER_INFO.get(_tk, ("", ""))[1]
                    if _desc:
                        st.caption(_desc)
                    render_stock_chart(_tk, "SPY", "etfsrch", show_rules=True, bench_label="SPY", etf_rule=etf_rule_for(_tk))
        else:
            st.caption("랭킹 표에 있는 ETF는 이름 일부(예: 반도체·금·배당)로, 없는 ETF는 티커(예: VOO·IBIT·JEPQ)로 찾을 수 있습니다. "
                       "결과는 미국 주식 랭킹의 종목 차트와 같은 화면(보유 기준·200일선·추세 배지·RSI·SPY 대비 성과)으로 나옵니다.")


def render_stock_chart(ticker, bench, uk, show_rules=True, bench_label=None, etf_rule=None):
    """종목 하나의 차트(주가·이동평균·추세선·목표/손절선, 거래량, RSI, 상대성과)와 보유 점검표.
    etf_rule: ETF 검색용 종류별 보유 기준 {"rebuy": 0.0|0.05, "mode": "rule"|"ref"|"none", "label": 종류, "note": 근거}
              (없으면 개별 종목 기준: −3% 매도 · +5% 재매수)"""
    raw = get_stock_chart_data(ticker, bench)
    if raw is None:
        st.warning(f"{ticker} 시세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return
    _rb = 0.05 if etf_rule is None else etf_rule.get("rebuy", 0.05)          # 재매수 기준 (200일선 대비)
    _rb_txt = "200일선 +5% 위" if _rb > 0 else "200일선 위(회복)"
    _rule_basis = ("나스닥100·S&P500 백테스트로 정한 규칙, 읽는 법 참고" if etf_rule is None
                   else f"{etf_rule.get('label', 'ETF')} · {etf_rule.get('note', '')}")
    if etf_rule is not None and etf_rule.get("mode") == "none":
        st.markdown(
            "<div style='background:#fee2e2;border:2px solid #b91c1c;border-radius:10px;padding:10px 14px;margin:2px 0 6px'>"
            f"<div style='color:#b91c1c;font-weight:800;font-size:1.1rem'>⛔ 보유 기준 미적용 — {etf_rule.get('label', '레버리지·인버스')}</div>"
            f"<div style='font-size:0.86rem;color:#334155;margin-top:4px'>{etf_rule.get('note', '')}</div></div>",
            unsafe_allow_html=True)
        show_rules = False
    d, lv, checks, score, verdict, rsi_note = _stock_tech(raw)
    px = lv["px"]
    cur = "₩" if str(ticker).endswith((".KS", ".KQ")) else "$"
    bench_label = bench_label or bench
    _dp = 0 if cur == "₩" else 2   # 원화는 소수점 없이

    if show_rules:
        # ── 보유 기준 (백테스트 검증: 월말 종가가 200일선 3% 아래면 매도, 200일선 위로 회복하면 재매수) ──
        _ma200 = lv["ma200"]
        if pd.isna(_ma200):
            st.markdown("##### ⚪ 보유 기준: 판단 불가")
            st.caption("상장 200거래일 미만이라 200일선이 없습니다.")
        else:
            def _state(p_, m_):
                if p_ > m_ * (1 + _rb):
                    return "🟢", "보유·매수 가능", "#15803d", "#dcfce7"
                if p_ > m_:
                    return "🟢", "보유 (재매수 대기)", "#15803d", "#ecfdf5"
                if p_ >= m_ * 0.97:
                    return "🟡", "경계", "#b45309", "#fef3c7"
                return "🔴", "매도 기준 도달", "#b91c1c", "#fee2e2"
            _gap = (px / _ma200 - 1) * 100
            _ic, _nm, _fc, _bg = _state(px, _ma200)
            # 지난 월말 판정 (실제 매매 판단은 월말 종가로)
            _dt = d.index.to_series()
            _me = _dt[_dt.dt.month != _dt.shift(-1).dt.month].iloc[:-1]
            _me_txt = ""
            if len(_me):
                _md = _me.index[-1]
                _mp, _mm = float(d.loc[_md, "Close"]), d.loc[_md, "MA200"]
                if pd.notna(_mm):
                    _mi, _mn, *_ = _state(_mp, _mm)
                    _me_txt = f"지난 월말({_md:%Y-%m-%d}) 종가 판정: {_mi} {_mn} · "
            _desc = {"보유·매수 가능": ("주가가 200일선보다 5% 넘게 위입니다. 계속 보유하고, 새로 사거나 다시 사도 되는 구간입니다." if _rb > 0
                                       else "주가가 200일선 위입니다. 계속 보유하고, 새로 사거나 다시 사도 되는 구간입니다."),
                     "보유 (재매수 대기)": "200일선 위지만 5% 이내입니다. 가진 종목은 계속 보유하고, 팔았던 종목이나 새 종목은 200일선 +5% 위로 올라올 때까지 기다립니다.",
                     "경계": "200일선 아래로 내려왔지만 3% 이내입니다. 아직 매도 기준은 아니며, 월말 종가를 확인합니다.",
                     "매도 기준 도달": f"200일선보다 3% 넘게 아래입니다. 월말 종가도 이 아래면 매도, 이후 월말 종가가 {_rb_txt}로 올라오면 재매수하는 것이 검증된 기준입니다."}[_nm]
            if etf_rule is not None and etf_rule.get("mode") == "ref":
                _nm_show = f"{_nm} (참고용)"
            else:
                _nm_show = _nm
            st.markdown(
                f"<div style='background:{_bg};border-radius:10px;padding:10px 14px;margin:2px 0 6px'>"
                f"<div style='color:{_fc};font-weight:800;font-size:1.15rem'>{_ic} 보유 기준: {_nm_show} "
                f"<span style='font-weight:600;font-size:0.9rem'>(200일선 대비 {_gap:+.1f}%)</span></div>"
                f"<div style='font-size:0.86rem;color:#334155;margin-top:4px'>{_desc}</div>"
                f"<div style='font-size:0.78rem;color:#64748b;margin-top:4px'>{_me_txt}판단은 월말 종가 1회 · "
                f"매도: 200일선 −3% 아래 · 재매수·신규 매수: {_rb_txt} ({_rule_basis})</div></div>",
                unsafe_allow_html=True)
    else:
        _g = (px / lv["ma200"] - 1) * 100 if pd.notna(lv["ma200"]) else np.nan
        st.markdown(f"##### 📈 추세 확인 — 200일선 대비 {_g:+.1f}%" if _g == _g else "##### 📈 추세 확인")
        st.caption(("이 ETF는 " if etf_rule is not None else "이 지수는 ") +
                   "매매 기준(보유 기준·매도 기준) 없이 추세만 보여 줍니다. 아래 차트 오른쪽 위의 🟢/🟡/🔴 추세 배지와 "
                   "6개월·1년 추세 조합으로 추세가 살아 있는지 확인하세요.")
    st.caption(f"추세 건강도(참고, 매도 신호 아님): {verdict[0]} {verdict[1]} · 점검 {score}/{len(checks)} — {verdict[2]} {rsi_note}")

    if show_rules:
        def _pct(v):
            return f"{(v / px - 1) * 100:+.1f}%"
        # 목표가는 표시하지 않음: 검증된 200일선 규칙은 '추세가 꺾일 때까지 보유'라 목표가 매도는 큰 승자를 일찍 자름
        _has200 = pd.notna(lv["ma200"])
        lv_tbl = pd.DataFrame([
            ["현재가", f"{cur}{px:,.{_dp}f}", "", f"ATR(14) {cur}{lv['atr']:,.{_dp}f} = 하루 평균 움직임 {lv['atr'] / px * 100:.1f}%"],
            ["재매수 기준", f"{cur}{lv['ma200'] * (1 + _rb):,.{_dp}f}" if _has200 else "-", _pct(lv["ma200"] * (1 + _rb)) if _has200 else "",
             ("200일선 × 1.05" if _rb > 0 else "200일선과 같음") + " · 팔았던 종목·새 종목은 월말 종가가 이 위일 때 매수"],
            ["200일선", f"{cur}{lv['ma200']:,.{_dp}f}" if _has200 else "-", _pct(lv["ma200"]) if _has200 else "", "장기 추세선"],
            ["매도 기준", f"{cur}{lv['stop_l']:,.{_dp}f}" if _has200 else "-", _pct(lv["stop_l"]) if _has200 else "",
             ("200일선 × 0.97 · 월말 종가가 이 아래면 매도" + (" · ⚠️ 이미 아래" if px <= lv["stop_l"] else ""))
             if _has200 else "상장 200거래일 미만이라 계산 불가"],
        ], columns=["구분", "가격", "현재가 대비", "의미"])
        st.dataframe(lv_tbl, use_container_width=True, hide_index=True)
        # 매도 기준까지 거리 = 지금 사면 규칙대로 해도 감수해야 하는 최대 하락폭(대략)
        if _has200 and px > lv["stop_l"]:
            _risk = (1 - lv["stop_l"] / px) * 100
            if _risk > 25:
                st.warning(f"⚠️ **매도 기준까지 −{_risk:.0f}%** — 지금 새로 사면 규칙상 이만큼 떨어져야 팝니다. "
                           "주가가 200일선보다 많이 올라 있어 감수할 하락폭이 큽니다. 이미 가진 물량은 그대로 보유하되, "
                           "새로 사거나 늘리는 것은 50일선·200일선 쪽으로 눌릴 때를 기다리는 편이 위험 대비 유리합니다.")
            elif _risk > 10:
                st.info(f"💡 **매도 기준까지 −{_risk:.0f}%** — 새로 사도 감수할 하락폭이 보통 수준입니다.")
            else:
                st.info(f"💡 **매도 기준까지 −{_risk:.0f}%** — 하락폭 부담은 작지만, 200일선 근처라 기준 이탈·재매수가 반복될 수 있는 구간입니다.")
        elif _has200:
            st.error(f"🔴 이미 매도 기준 아래입니다. 규칙상 새로 사지 않고, 월말 종가가 {_rb_txt}로 올라올 때 재매수를 검토합니다.")
    # 결과 아이콘을 항목 이름 앞에 붙여 한 칸으로 (빈 아이콘 칸이 넓게 잡히지 않도록)
    st.dataframe(pd.DataFrame({f"추세 건강도 점검 ({score}/{len(checks)}) — 참고용": [("✅ " if ok else "❌ ") + name for name, ok in checks]}),
                 use_container_width=True, hide_index=True)

    # ── 차트 ──
    per = st.radio("차트 기간 (판정은 기간과 관계없이 6개월 기준)", ["3개월", "6개월", "1년", "2년"], index=1,
                   horizontal=True, key=f"{uk}_chart_per_{ticker}")
    n = {"3개월": 63, "6개월": 126, "1년": 252, "2년": 504}[per]
    v = d.tail(n).copy()
    xx = np.arange(len(v))
    b, a = np.polyfit(xx, np.log(v["Close"].values), 1)
    fit = a + b * xx
    sd = float(np.std(np.log(v["Close"].values) - fit))
    v["추세선"] = np.exp(fit)
    v["채널 상단"] = np.exp(fit + 2 * sd)
    v["채널 하단"] = np.exp(fit - 2 * sd)
    v = v.reset_index().rename(columns={v.index.name or "index": "날짜"})
    if "날짜" not in v.columns:
        v = v.rename(columns={v.columns[0]: "날짜"})

    long = v.melt(id_vars=["날짜"], value_vars=["Close", "MA50", "MA200", "추세선"], var_name="선", value_name="가격").dropna()
    long["선"] = long["선"].replace({"Close": "주가", "MA50": "50일선", "MA200": "200일선"})
    color = alt.Scale(domain=["주가", "50일선", "200일선", "추세선"], range=["#0f172a", "#2563eb", "#dc2626", "#7c3aed"])
    dash = alt.Scale(domain=["주가", "50일선", "200일선", "추세선"], range=[[1, 0], [1, 0], [1, 0], [6, 4]])
    _xfmt = "%m/%d" if n <= 126 else "%y.%m"   # 3·6개월: 10/12, 1·2년: 25.11
    base_x = alt.X("날짜:T", title=None, axis=alt.Axis(format=_xfmt, labelAngle=0))
    band = alt.Chart(v).mark_area(opacity=0.08, color="#7c3aed").encode(x=base_x, y="채널 하단:Q", y2="채널 상단:Q")
    lines = alt.Chart(long).mark_line(strokeWidth=1.6).encode(
        x=base_x, y=alt.Y("가격:Q", scale=alt.Scale(zero=False), title=f"가격 ({cur})"),
        color=alt.Color("선:N", scale=color, legend=None),   # 범례는 위 HTML 줄에서 추세 상태와 함께 표시
        strokeDash=alt.StrokeDash("선:N", scale=dash, legend=None),
        tooltip=[alt.Tooltip("날짜:T"), "선:N", alt.Tooltip("가격:Q", format=",.2f")])
    lvl = pd.DataFrame([
        ["재매수 기준", lv["ma200"] * (1 + _rb) if (pd.notna(lv["ma200"]) and _rb > 0) else np.nan, "#15803d"],
        ["매도 기준", lv["stop_l"], "#b91c1c"],
    ] if show_rules else [], columns=["구분", "가격", "색"]).dropna()
    rules = alt.Chart(lvl).mark_rule(strokeDash=[3, 3], strokeWidth=1.2).encode(
        y="가격:Q", color=alt.Color("색:N", scale=None), tooltip=["구분:N", alt.Tooltip("가격:Q", format=",.2f")])
    labels = alt.Chart(lvl).mark_text(align="left", dx=4, dy=-6, fontSize=11).encode(
        x=alt.value(4), y="가격:Q", text="구분:N", color=alt.Color("색:N", scale=None))
    # ── 추세 생존 표시 (읽는 법의 판단 순서 ①~④를 화면 기간 기준으로 그대로 적용) ──
    _ma50, _ma200 = lv["ma50"], lv["ma200"]
    _conds = [
        ("200일선 위", bool(pd.notna(_ma200) and px > _ma200)),
        ("정배열", bool(pd.notna(_ma200) and pd.notna(_ma50) and _ma50 > _ma200)),
        ("6개월 추세선 위", bool(px > lv["trend6"])),
        ("200일선 상승 중", bool(pd.notna(_ma200) and d["MA200"].iloc[-1] > d["MA200"].iloc[-21])),
    ]
    _ok = sum(o for _, o in _conds)
    if _ok == 4:
        _tt, _tc, _tb = "🟢 추세 살아 있음 (4/4)", "#15803d", "#dcfce7"
    elif _ok == 3:
        _tt, _tc, _tb = "🟡 추세 약화 주의 (3/4)", "#b45309", "#fef3c7"
    else:
        _tt, _tc, _tb = f"🔴 추세 깨짐 ({_ok}/4)", "#b91c1c", "#fee2e2"
    _sub = " · ".join(("✅" if o else "❌") + nm for nm, o in _conds)
    # 6개월·1년 추세 방향 조합 → 해석 (읽는 법의 표와 같은 기준)
    _u6, _u1 = lv["slope6"] > 0, lv["slope1"] > 0
    _combo = {(True, True): "6개월·1년 모두 상승 — 가장 견고한 추세",
              (True, False): "하락 후 반등·전환 초기 — 아직 확정 아님, 200일선이 위로 꺾이는지 확인",
              (False, True): "장기 상승 중 조정 — 장기 손절(200일선)을 지키면 보유 가능",
              (False, False): "6개월·1년 모두 하락 — 추세 약세, 보유 근거 약함"}[(_u6, _u1)]
    _sub += (f"<br>6개월 추세 {'상승' if _u6 else '하락'}(연 {lv['slope6']:+.0f}%) · "
             f"1년 추세 {'상승' if _u1 else '하락'}(연 {lv['slope1']:+.0f}%) → {_combo}")

    def _lg(name, col, dashed=False):
        _ln = (f"border-top:2px dashed {col};width:18px;height:0" if dashed
               else f"background:{col};width:18px;height:3px;border-radius:2px")
        return (f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:12px'>"
                f"<span style='display:inline-block;{_ln}'></span>{name}</span>")
    _legend = (_lg("주가", "#0f172a") + _lg("50일선", "#2563eb") + _lg("200일선", "#dc2626") +
               _lg("추세선", "#7c3aed", dashed=True))
    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;"
        "margin:6px 0 -4px;font-size:0.85rem;color:#334155'>"
        f"<div>{_legend}</div>"
        f"<div style='text-align:right'><span style='background:{_tb};color:{_tc};font-weight:800;"
        f"padding:4px 12px;border-radius:999px;font-size:0.95rem;white-space:nowrap'>{_tt}</span>"
        f"<div style='font-size:0.75rem;color:#475569;margin-top:3px'>{_sub}</div></div></div>",
        unsafe_allow_html=True)
    st.altair_chart(alt.layer(band, lines, rules, labels).properties(height=320), use_container_width=True)

    vol = alt.Chart(v).mark_bar(color="#94a3b8").encode(
        x=base_x, y=alt.Y("Volume:Q", title="거래량", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("날짜:T"), alt.Tooltip("Volume:Q", format=",")]).properties(height=80)
    st.altair_chart(vol, use_container_width=True)

    rsi_df = v[["날짜", "RSI"]].dropna()
    rsi_line = alt.Chart(rsi_df).mark_line(color="#0f766e").encode(
        x=base_x, y=alt.Y("RSI:Q", scale=alt.Scale(domain=[0, 100]), title="RSI(14)"),
        tooltip=[alt.Tooltip("날짜:T"), alt.Tooltip("RSI:Q", format=".0f")])
    rsi_rule = alt.Chart(pd.DataFrame({"y": [30, 70]})).mark_rule(strokeDash=[4, 4], color="#94a3b8").encode(y="y:Q")
    st.altair_chart(alt.layer(rsi_line, rsi_rule).properties(height=110), use_container_width=True)

    rel = v[["날짜", "Close", "Bench"]].dropna().copy()
    if len(rel) > 1:
        rel[ticker] = rel["Close"] / rel["Close"].iloc[0] * 100
        rel[bench] = rel["Bench"] / rel["Bench"].iloc[0] * 100
        rl = rel.melt(id_vars=["날짜"], value_vars=[ticker, bench], var_name="종목", value_name="지수화")
        st.altair_chart(alt.Chart(rl).mark_line().encode(
            x=base_x, y=alt.Y("지수화:Q", scale=alt.Scale(zero=False), title=f"시작=100 (vs {bench})"),
            color=alt.Color("종목:N", scale=alt.Scale(domain=[ticker, bench], range=["#0f172a", "#a3a3a3"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("날짜:T"), "종목:N", alt.Tooltip("지수화:Q", format=".1f")]).properties(height=140),
            use_container_width=True)

    # (바깥이 이미 접는 상자라 상자 안에 상자를 둘 수 없어 토글로 표시)
    if tab_toggle("📖 차트·점검표 읽는 법", key=f"{uk}_chart_guide_{ticker}_r"):
        st.markdown(f"""
- **보유 기준(맨 위 상자)은 백테스트로 고른 규칙입니다.** 나스닥100 98종목·2015\\~ 현재·매매당 비용 0.2%로 여러 매도 규칙을 비교했습니다(세금 미반영, 현재 종목만 써서 생존편향 있음).

| 규칙 | CAGR | MDD | 샤프 | 연 매매 |
|---|---|---|---|---|
| 매수 후 보유 | 27.4% | -30.5% | 1.2 | - |
| 추세 건강도 점수로 매매 (정리 검토 매도·보유 유지 재매수) | 9.7% | -11.3% | 1.1 | 2.3 |
| **200일선 −3% 매도 · 회복 시 재매수 (주 1회)** | **18.1%** | **-19.8%** | **1.3** | 1.1 |
| **200일선 월 1회 판단** | **18.1%** | **-19.7%** | **1.3** | 0.9 |
| 50/200일선 교차 | 18.2% | -27.5% | 1.2 | 0.6 |
| QQQ 보유 | 19.2% | -35.1% | 0.9 | - |

  점수형 규칙은 자주 뒤집히는 MACD·상대강도 때문에 너무 일찍 팔고 늦게 다시 사서 수익을 크게 잃었고, 200일선 하나만 본 규칙이 낙폭을 줄이면서 위험 대비 효율(샤프)도 가장 높았습니다. 그래서 **매도는 200일선 기준만** 쓰고, 아래 점검표·추세 배지는 추세가 얼마나 건강한지 보는 **참고용**으로 둡니다.
- **판단 순서**: ① 주가가 200일선(빨강) 위인가 → 장기 추세 ② 50일선(파랑)이 200일선 위인가 → 정배열 ③ 보라 점선 추세선 위인가 → 현재 추세 ④ 200일선이 오르고 있는가 → 장기 추세의 방향. 넷 다 '예'면 추세가 살아 있는 상태입니다. 차트 오른쪽 위에 이 네 가지 결과가 🟢 살아 있음(4/4) · 🟡 약화 주의(3/4) · 🔴 깨짐(2개 이하)으로 표시됩니다. ③은 차트 기간과 관계없이 **항상 6개월 추세선** 기준이라, 기간을 바꿔 봐도 판정은 그대로입니다.
- **추세선·채널(보라)**: 화면 기간의 로그 가격 회귀선과 ±2 표준편차 범위입니다. 채널 상단 근처는 과열, 하단 근처는 눌림 구간으로 봅니다. 기본 화면인 6개월에서는 이 점선이 판정(③)에 쓰는 선과 같고, 다른 기간을 고르면 점선은 그 기간의 흐름을 보여 줄 뿐 판정은 바뀌지 않습니다.
- **어느 기간으로 볼까**: 보유 기간에 맞는 기간으로 판단하고 한 단계 긴 기간으로 확인합니다. 중·장기 보유라면 **6개월 = 기본 판단용**(1~3개월 흐름과 시간 단위가 맞음), **1년 = 큰 흐름 확인용**(지금 오름세가 큰 상승의 일부인지, 하락 속 반등인지 구분), **3개월 = 참고만**(짧은 출렁임에 방향이 자주 바뀌어 단타식 판단으로 흐르기 쉬움), **2년 = 장기 보유 종목의 큰 그림**용입니다.
- **6개월과 1년이 다르게 나올 때** (배지 아래 줄에 자동 표시):

| 6개월 | 1년 | 의미 |
|---|---|---|
| 상승 | 상승 | 가장 견고한 추세. 보유 근거가 강함 |
| 상승 | 하락 | 하락 후 반등·전환 초기. 아직 확정 아님. 200일선이 위로 꺾이는지가 확인 포인트 |
| 하락 | 상승 | 장기 상승 중 조정. 장기 손절(200일선)을 지키면 보유 가능 |
| 하락 | 하락 | 추세 약세. 보유 근거가 약함 |

- **ATR**: 하루 평균 움직임 폭. 같은 '매도 기준까지 −15%'라도 하루에 1%씩 움직이는 종목과 4%씩 움직이는 종목은 위험의 체감이 다르니, 변동성 비교용으로 참고합니다.
- **매도 기준(장기 손절)**: 200일선 3% 아래. 월말 종가가 이 아래면 매도합니다. **재매수 기준**: 200일선 5% 위. 팔았던 종목이나 새 종목은 월말 종가가 이 위일 때 삽니다.
  S&P500 2006\\~ 백테스트(돌파 매수 6,852건)에서 +0%에 다시 사면 3개월 안에 다시 손절되는 비율이 30%, +5%는 19%, +10%는 12%였습니다. 기준을 높일수록 실패는 줄지만 한 번 실패할 때 손실이 커지고(평균 −12% → −16% → −19%) 전체 수익은 거의 같아서, 실패율과 손실 크기의 균형점인 +5%를 씁니다. 샹들리에 스탑 같은 중기 손절선은 백테스트에서 단독 매도 기준으로 효과가 없어 표시하지 않습니다.
- **매도 기준까지 거리**: 지금 사면 규칙대로 해도 이만큼은 떨어져야 팔게 된다는 뜻입니다(대략적인 최대 손실). 25%를 넘으면 새로 사기엔 위험이 큰 편, 10% 이하면 부담은 작지만 200일선 근처라 사고팔기가 반복될 수 있습니다. **목표가는 표시하지 않습니다.** 검증된 200일선 규칙은 추세가 꺾일 때까지 들고 가서 크게 오르는 종목의 수익을 지키는 방식이라, 목표가에서 파는 것은 오히려 성과를 낮출 수 있기 때문입니다.
- **RSI**: 70 이상은 단기 과열, 30 이하는 과매도. 강한 추세에서는 70 이상이 오래 유지되기도 해서 단독 매도 신호로는 쓰지 않습니다.
- **상대성과 그래프**: 검은 선이 회색({bench}) 위에서 벌어지면 시장보다 강한 종목입니다.
- **한계**: 가격·거래량만 쓰는 기술적 규칙이라 실적·뉴스·밸류에이션은 반영하지 않습니다. 갭 하락 시에는 손절가보다 낮게 체결될 수 있습니다. 투자 권유가 아니라 보유 여부를 스스로 점검하기 위한 참고치입니다.
""")


# ===================== QQQ 장기 보유 가이드 (백테스트 정리, 2026-10-13) =====================
# 출처: qqq_mdd_backtest.py(세전) · qqq_mdd_tax_backtest.py(세후, 초기 1억원) 실행 결과. 화면 표·그래프·MD 파일이 모두 이 데이터를 씀
QQQ_RULES = ["QQQ 보유", "200일선 (매일)", "200일선 (주 1회)", "200일선 -3% (월 1회)", "200일선 -3% → 국채",
             "10개월선 (월 1회)", "50/200 교차", "듀얼 모멘텀", "200일선 아래면 50%만", "변동성 목표 20%"]
# 세전: (CAGR, MDD, 샤프, 연 매매)
QQQ_PRETAX = {
    "2000~": [(8.9, -83.0, 0.5, 0.0), (7.3, -57.8, 0.5, 7.0), (9.3, -46.9, 0.6, 3.1), (11.6, -36.5, 0.7, 1.1), (12.6, -36.5, 0.7, 1.1),
              (9.5, -41.5, 0.6, 1.9), (11.5, -36.5, 0.7, 1.2), (9.3, -42.9, 0.6, 1.1), (9.9, -64.9, 0.6, 1.7), (11.6, -51.3, 0.7, 6.3)],
    "2010~": [(19.2, -35.1, 1.0, 0.0), (12.5, -25.4, 0.8, 6.0), (13.3, -27.4, 0.9, 2.6), (14.6, -28.6, 0.8, 1.1), (13.7, -28.6, 0.8, 1.1),
              (13.4, -28.6, 0.8, 1.8), (15.1, -28.6, 0.9, 1.1), (16.3, -29.2, 0.9, 0.6), (16.8, -28.6, 0.9, 1.4), (18.1, -26.6, 1.0, 5.4)],
    "2015~": [(19.2, -35.1, 0.9, 0.0), (14.1, -24.1, 0.9, 4.9), (15.9, -25.2, 1.0, 1.9), (15.7, -28.6, 0.9, 1.0), (14.4, -28.6, 0.8, 1.0),
              (14.7, -28.6, 0.9, 1.5), (15.9, -28.6, 0.9, 1.0), (15.2, -29.2, 0.8, 0.9), (17.5, -28.6, 0.9, 1.4), (17.5, -26.6, 1.0, 6.3)],
}
# 세후(초기 1억원, 마지막 날 전량 매도 기준): (세후 CAGR, 세후 MDD, 최종 세후 자산 억원, 낸 세금 억원, 1천만원 CAGR, 5억원 CAGR)
QQQ_TAX_RULES = ["QQQ 보유", "200일선 (주 1회)", "200일선 -3% (월 1회)", "200일선 -3% → 국채",
                 "10개월선 (월 1회)", "50/200 교차", "200일선 아래면 50%만", "변동성 목표 20%"]
QQQ_AFTERTAX = {
    "2000~": [(7.8, -83.0, 7.5, 1.8, 7.8, 7.8), (6.3, -47.2, 5.2, 1.3, 7.1, 6.2), (9.3, -36.5, 10.8, 2.7, 9.8, 9.2), (10.0, -36.5, 12.8, 3.5, 10.6, 9.9),
              (7.4, -42.0, 6.7, 1.7, 8.1, 7.2), (9.3, -36.5, 10.8, 2.7, 9.9, 9.2), (8.6, -57.9, 9.1, 2.2, 9.2, 8.5), (9.2, -54.2, 10.6, 2.6, 10.0, 9.1)],
    "2010~": [(17.4, -35.1, 14.6, 3.8, 17.4, 17.4), (9.5, -32.7, 4.6, 1.0, 10.3, 9.4), (11.4, -32.7, 6.1, 1.4, 12.1, 11.4), (10.5, -32.1, 5.3, 1.3, 11.1, 10.4),
              (10.3, -34.1, 5.2, 1.2, 11.1, 10.2), (12.3, -28.6, 7.0, 1.6, 13.0, 12.2), (14.1, -28.6, 9.1, 2.1, 14.8, 14.0), (15.0, -27.6, 10.3, 2.4, 15.8, 14.8)],
    "2015~": [(17.0, -35.1, 6.4, 1.5, 17.1, 17.0), (11.7, -31.5, 3.7, 0.8, 12.5, 11.6), (12.5, -28.6, 4.0, 0.8, 13.3, 12.4), (11.0, -29.9, 3.4, 0.7, 11.9, 10.9),
              (11.1, -28.6, 3.4, 0.7, 11.9, 11.0), (13.0, -28.6, 4.2, 0.8, 13.9, 12.8), (14.6, -28.6, 5.0, 1.0, 15.4, 14.5), (14.4, -27.5, 4.9, 1.0, 15.6, 14.3)],
}
QQQ_CRISES = ["닷컴 붕괴 2000-02", "금융위기 2007-09", "코로나 2020", "긴축 2022"]
QQQ_CRISIS = [(-83.0, -53.4, -28.6, -34.8), (-52.0, -23.7, -22.4, -19.1), (-41.1, -16.7, -25.2, -12.6), (-36.5, -25.9, -28.6, -18.0),
              (-36.5, -28.1, -28.6, -27.8), (-41.5, -25.9, -28.6, -15.1), (-36.5, -22.6, -28.6, -18.0), (-42.9, -28.1, -28.6, -28.9),
              (-64.9, -40.2, -28.6, -22.1), (-51.3, -39.8, -23.7, -26.1)]
QQQ_RULE_DESC = {
    "QQQ 보유": "사서 계속 들고 감 (기준선)",
    "200일선 (매일)": "매일 종가가 200일선 아래면 현금, 위면 QQQ",
    "200일선 (주 1회)": "금요일 종가로 같은 판단",
    "200일선 -3% (월 1회)": "월말 종가가 200일선 3% 아래면 매도, 200일선 위로 회복하면 재매수",
    "200일선 -3% → 국채": "위와 같고, 대피처가 현금 대신 중기 국채(IEF)",
    "10개월선 (월 1회)": "월말 종가가 10개월 평균 아래면 현금 (파버 규칙)",
    "50/200 교차": "50일선이 200일선 아래로 내려가면 매도, 다시 위로 가면 재매수",
    "듀얼 모멘텀": "12개월 수익이 현금 금리보다 낮으면 국채로",
    "200일선 아래면 50%만": "월말에 200일선 아래면 절반만 보유",
    "변동성 목표 20%": "최근 20일 변동성이 20%를 넘는 만큼 비중을 줄임 (월 1회, 최대 100%)",
}

QQQ_GUIDE_INTRO = """
**한눈에 보는 결론**

1. **몇 년씩 이어지는 하락장에서는 규칙이 계좌를 지킵니다.** 2000년부터 보면 200일선 규칙은 세후로도 QQQ보다 수익이 높고(7.8% → 9.3~10.0%) 최대 낙폭은 -83%에서 -36%로 절반 이하입니다.
2. **길게 오르는 시장에서는 보험료가 큽니다.** 2010년 이후에는 모든 규칙이 QQQ 보유보다 낮고, 세금까지 넣으면 격차가 더 벌어집니다(17.4% vs 11.4%, 1억 → 14.6억 vs 6.1억). 규칙형은 1년에 한 번꼴로 팔면서 양도세를 내기 때문입니다.
3. **급락은 못 피합니다.** 코로나(한 달 -29%)는 월 1회 규칙도 QQQ와 똑같이 맞았습니다. 추세 규칙은 '몇 달에 걸친 하락장' 대비용입니다.
4. **일반 계좌라면 '덜 파는' 방식이, 매매 시 세금이 없는 계좌라면 200일선 −3% (월 1회)가** 현실적인 선택입니다.
"""

QQQ_GUIDE_COND = """
**테스트 조건**: QQQ 일봉(배당 포함), 2000-01 ~ 2026-10. 신호 다음 거래일 체결, 매매당 비용 0.2%. 현금 대피 시 3개월 미국채 금리 이자(세후는 15.4% 과세),
국채 대피는 IEF(2002년 이전은 뱅가드 중기국채 펀드로 대체). 세후는 양도세 22%(연 실현차익 − 공제 250만원, 이듬해 5월 납부)를 계좌에서 빼고,
마지막 날 전량 매도해 남은 차익의 세금까지 낸다고 본 '청산 기준'입니다. 환율은 고정, QQQ 배당 원천징수는 생략했습니다.
"""

QQQ_GUIDE_ACTION = """
**실제로 쓴다면**

| 상황 | 권하는 방식 | 이유 |
|---|---|---|
| 일반 계좌, 세금 부담을 줄이고 싶다 | QQQ 그냥 보유, 또는 **200일선 아래면 50%만** · **변동성 목표** | 전부 팔지 않아 실현 차익이 작음. 2010~ 세후 14~15%로 QQQ(17.4%)에 가장 가까우면서 낙폭은 -28% |
| 2000년형 장기 하락장이 가장 두렵다 | **200일선 −3% (월 1회)** | 세후로도 2000~ 9.3%, 낙폭 -36.5%. 1년에 한 번 정도 매매 |
| 매매 시 세금이 없는 계좌(연금저축·IRP 등) | **200일선 −3% (월 1회)** | 세금 약점이 사라져 세전 결과에 가까워짐 (계좌 한도·상품 제약은 증권사 확인) |
| 둘 다 잡고 싶다 | 일반 계좌는 QQQ 보유 + 연금 계좌는 200일선 규칙 | 세금 부담과 큰 하락 방어를 나눠서 담당 |

판단은 월말 리밸런싱 날 한 번만 하면 됩니다. 개별 종목의 보유 기준(200일선 −3% 매도, 200일선 회복 재매수)과 같은 규칙입니다.

**한계**: 과거 한 지수(QQQ)의 결과라 미래 성과를 보장하지 않습니다. 세금 계산은 단순화한 모델이고 세법은 바뀔 수 있으니, 실제 적용 전에는 세무 전문가나 증권사에 확인하세요.
참고로 2026 혼합전략(세후 CAGR 30.7%, MDD -15.1%)은 이 규칙들보다 수익·낙폭 모두 낫습니다. QQQ 규칙은 '더 단순한 대안'이나 '핵심 보유분 관리용'으로 보시면 됩니다.
"""


QQQ_MAIN_RULE = "200일선 -3% (월 1회)"


def _qqq_disp(nm):
    """표에 쓰는 규칙 이름: 기본 규칙에는 '(권장)' 표시 → 주황 배경 강조."""
    return f"{nm} · 권장" if nm == QQQ_MAIN_RULE else nm


QQQ_ACTION_CARDS = [
    ("일반 계좌 · 세금 부담을 줄이고 싶다", "QQQ 그냥 보유 · 200일선 아래면 50%만 · 변동성 목표",
     "전부 팔지 않아 실현 차익이 작음. 2010&#126; 세후 14&#126;15%로 QQQ(17.4%)에 가장 가까우면서 낙폭은 -28%"),
    ("2000년형 장기 하락장이 가장 두렵다", "200일선 −3% (월 1회)",
     "세후로도 2000&#126; 9.3%, 낙폭 -36.5%. 1년에 한 번 정도 매매"),
    ("매매 시 세금이 없는 계좌 (연금저축·IRP 등)", "200일선 −3% (월 1회)",
     "세금 약점이 사라져 세전 결과에 가까워짐 (계좌 한도·상품 제약은 증권사 확인)"),
    ("둘 다 잡고 싶다", "일반 계좌 QQQ 보유 + 연금 계좌 200일선 규칙",
     "세금 부담과 큰 하락 방어를 나눠서 담당"),
]

QQQ_GUIDE_ACTION_NOTE = """
판단은 월말 리밸런싱 날 한 번만 하면 됩니다. 개별 종목의 보유 기준(200일선 −3% 매도)과 같은 계열의 규칙입니다.

**한계**: 과거 한 지수(QQQ)의 결과라 미래 성과를 보장하지 않습니다. 세금 계산은 단순화한 모델이고 세법은 바뀔 수 있으니, 실제 적용 전에는 세무 전문가나 증권사에 확인하세요.
참고로 2026 혼합전략(세후 CAGR 30.7%, MDD -15.1%)은 이 규칙들보다 수익·낙폭 모두 낫습니다. QQQ 규칙은 '더 단순한 대안'이나 '핵심 보유분 관리용'으로 보시면 됩니다.
"""


def qqq_guide_markdown():
    """화면과 같은 내용을 MD 파일로."""
    out = ["# QQQ를 장기 보유하려면 — 큰 낙폭 줄이기 규칙 백테스트 정리", "",
           "*동적 자산배분 대시보드 · 2026-10-13 정리*", "", QQQ_GUIDE_INTRO.strip(), "", QQQ_GUIDE_COND.strip(), "",
           "## 비교한 규칙", "", "| 규칙 | 내용 |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in QQQ_RULE_DESC.items()]
    for per in ("2000~", "2010~", "2015~"):
        out += ["", f"## 세후 결과 ({per}, 초기 1억원, 청산 기준)", "",
                "| 규칙 | 세전 CAGR | 세후 CAGR | 세후 MDD | 최종 세후 자산 | 낸 세금 | 세후 CAGR(1천만원) | 세후 CAGR(5억원) |",
                "|---|---|---|---|---|---|---|---|"]
        pre = dict(zip(QQQ_RULES, QQQ_PRETAX[per]))
        for nm, v in zip(QQQ_TAX_RULES, QQQ_AFTERTAX[per]):
            out.append(f"| {nm} | {pre[nm][0]:.1f}% | **{v[0]:.1f}%** | {v[1]:.1f}% | {v[2]:.1f}억 | {v[3]:.1f}억 | {v[4]:.1f}% | {v[5]:.1f}% |")
    for per in ("2000~", "2010~", "2015~"):
        out += ["", f"## 세전 결과 ({per})", "", "| 규칙 | CAGR | MDD | 샤프 | 연 매매 |", "|---|---|---|---|---|"]
        out += [f"| {nm} | {v[0]:.1f}% | {v[1]:.1f}% | {v[2]:.1f} | {v[3]:.1f} |" for nm, v in zip(QQQ_RULES, QQQ_PRETAX[per])]
    out += ["", "## 위기 구간별 최대 낙폭 (세전)", "", "| 규칙 | " + " | ".join(QQQ_CRISES) + " |", "|---|" + "---|" * len(QQQ_CRISES)]
    out += [f"| {nm} | " + " | ".join(f"{x:.1f}%" for x in v) + " |" for nm, v in zip(QQQ_RULES, QQQ_CRISIS)]
    out += ["", QQQ_GUIDE_ACTION.strip(), ""]
    return "\n".join(out)


def render_qqq_longhold_guide():
    st.header("📘 QQQ를 장기 보유하려면~")
    st.caption("QQQ를 오래 들고 가면서 큰 낙폭(MDD)만 줄이는 규칙 10가지를 2000년부터 백테스트하고, 양도세까지 넣어 비교한 정리입니다.")
    if not tab_toggle("내용 펼치기 (표·그래프)", key="qqq_guide_open_r"):
        return

    st.markdown(QQQ_GUIDE_INTRO)

    # ── 지금 QQQ 상태: 기본 규칙(200일선 −3%, 월 1회)의 지금 비중 + 대안 두 가지 ──
    try:
        _q = get_stock_chart_data("QQQ", "SPY")
        if _q is not None and len(_q) > 200:
            _c = _q["Close"]
            _ma_s = _c.rolling(200).mean()
            _px, _ma = float(_c.iloc[-1]), float(_ma_s.iloc[-1])
            _gap = (_px / _ma - 1) * 100
            _vol = float(_c.pct_change().tail(20).std() * np.sqrt(252) * 100)     # 최근 20거래일 연율 변동성
            _w_vol = min(100.0, 20.0 / _vol * 100) if _vol > 0 else 100.0
            # 월말마다 규칙을 따라왔다고 보고 지금 상태 계산 (매도 후엔 200일선 위로 회복해야 재매수)
            _me = _c.groupby(_c.index.to_period("M")).tail(1)
            _state, _last_chg = 1, None
            for _d, _v in _me.items():
                _mv = _ma_s.get(_d)
                if _mv is None or pd.isna(_mv) or _d == _c.index[-1]:
                    continue
                if _state == 1 and _v < _mv * 0.97:
                    _state, _last_chg = 0, _d
                elif _state == 0 and _v > _mv:
                    _state, _last_chg = 1, _d
            _w_main = _state * 100
            if _state == 1 and _gap >= 0:
                _act, _zone = "200일선 위 → <b>QQQ 보유</b>. 월말에 다시 확인합니다.", 0
            elif _state == 1 and _gap >= -3:
                _act, _zone = "200일선 아래 3% 이내 → <b>아직 보유</b>(경계). 월말 종가가 −3%보다 아래면 매도합니다.", 1
            elif _state == 1:
                _act, _zone = "200일선 −3% 아래 → <b>이번 월말 종가도 이 아래면 매도</b>합니다.", 2
            elif _gap > 0:
                _act, _zone = "매도 후 현금 상태지만 지금 200일선 위 → <b>월말 종가가 200일선 위면 재매수</b>합니다.", 0
            else:
                _act, _zone = "매도 후 <b>현금</b> 상태 → 월말 종가가 200일선 위로 올라오면 재매수합니다.", (1 if _gap >= -3 else 2)
            _btc_card(f"지금 QQQ에 기본 규칙(200일선 −3%, 월 1회)을 적용하면 · 기준 {_q.index[-1]:%Y-%m-%d} 종가 (실제 판단은 월말 종가)",
                      f"QQQ {_w_main}%", f"현금 {100 - _w_main}% · {_act}",
                      f"① 200일선 대비 {_gap:+.1f}% — 종가 &#36;{_px:,.2f} · 200일선 &#36;{_ma:,.2f}"
                      + (f" · 마지막 상태 변경 {_last_chg:%Y-%m}" if _last_chg is not None else "") + "<br>"
                      f"<span style='color:#64748b'>일반 계좌 대안 — 200일선 아래면 50%만: {'100' if _px > _ma else '50'}% · "
                      f"변동성 목표 20%: {_w_vol:.0f}% (최근 20일 변동성 {_vol:.1f}%)</span>")
            st.caption("참고 정보이며 매매 지시가 아닙니다. 어떤 규칙이 맞는지는 아래 '실제로 쓴다면'의 계좌별 안내를 보세요.")
            _render_cards([
                ("① 200일선 위", "200일선 대비 0% 이상", "<b>보유 100%</b> · 계속 보유. 매도했던 상태라면 월말 종가가 이 구간이면 재매수"),
                ("② 경계", "200일선 아래 0&#126;−3%", "<b>보유 100% (경계)</b> · 아직 팔지 않음. 매도 후 현금이라면 그대로 현금 유지"),
                ("③ 매도 기준", "200일선 −3% 아래", "<b>보유 0%</b> · 월말 종가가 이 구간이면 전량 매도 → 200일선 위로 회복할 때까지 현금"),
            ], _zone)
            with st.expander("📖 변동성 목표 20%는 어떻게 읽나요? (쉬운 설명)", expanded=False):
                st.markdown("""
**비유: 비 오는 날 속도 줄이기.** 맑은 날은 시속 100km, 비가 오면 80km, 폭우면 50km로 줄이듯이,
시장이 얼마나 출렁이는지(도로 상태)에 맞춰 QQQ를 들고 있는 양(속도)을 조절하는 규칙입니다.

**1단계 — 변동성이란?** QQQ가 하루에 얼마나 크게 오르내리는지입니다. 하루 ±1% 정도로 잔잔하면 1년 기준 약 16%,
하루 ±2.5%씩 출렁이면 약 40%가 됩니다. 앱은 최근 한 달(20거래일)의 움직임으로 계산합니다.

**2단계 — 기준은 20%.** 20% 이하면 100% 보유, 넘으면 '20 ÷ 지금 변동성'만큼만 보유합니다.

| 지금 변동성 | 계산 | QQQ 비중 | 1억원이라면 |
|---|---|---|---|
| 16% (잔잔) | 20 ÷ 16 → 100% 넘음 | 100% | QQQ 1억 |
| 25% (조금 거침) | 20 ÷ 25 | 80% | QQQ 8천만 + 현금 2천만 |
| 40% (폭풍) | 20 ÷ 40 | 50% | QQQ 5천만 + 현금 5천만 |

**3단계 — 왜 효과가 있나?** 큰 하락장은 대부분 시장이 거칠게 출렁이면서 옵니다. 그래서 변동성 숫자가 먼저 커지고 규칙이 알아서 비중을 줄이며,
시장이 다시 잔잔해지면 자동으로 100%로 돌아옵니다.

**실제로 할 일:** 월말에 위 표의 '변동성 목표 20%' 지금 비중을 보고 그 비율에 맞춰 QQQ와 현금(또는 단기 국채 ETF)을 조정합니다.

**주의:** 백테스트에서 매매가 연 6번 정도로 가장 잦았고, 2000년 닷컴 붕괴처럼 천천히 오래 빠지는 하락에는 방어력이 약했습니다(-54%).
'상승장 수익을 덜 포기하면서 거친 구간만 줄이는' 용도로 보세요.
""")
    except Exception:
        pass

    st.markdown(QQQ_GUIDE_COND)
    per = st.radio("기간", ["2000~", "2010~", "2015~"], index=1, horizontal=True, key="qqq_guide_per")

    # ── 그래프: 세후 CAGR / 세후 MDD ──
    pre = dict(zip(QQQ_RULES, QQQ_PRETAX[per]))
    g = pd.DataFrame([{"규칙": nm, "세전 CAGR": pre[nm][0], "세후 CAGR": v[0], "세후 MDD": v[1],
                       "기준": "QQQ 보유" if nm == "QQQ 보유" else ("권장" if nm == QQQ_MAIN_RULE else "규칙")}
                      for nm, v in zip(QQQ_TAX_RULES, QQQ_AFTERTAX[per])])
    order = QQQ_TAX_RULES
    col = alt.Color("기준:N", scale=alt.Scale(domain=["QQQ 보유", "규칙", "권장"], range=["#64748b", "#0f766e", "#f7931a"]), legend=None)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**세후 연수익률 (CAGR, {per})** — 길수록 좋음 · 회색 눈금 = 세전 · 주황 = 기본 규칙")
        _bar = alt.Chart(g).mark_bar().encode(
            y=alt.Y("규칙:N", sort=order, title=None), x=alt.X("세후 CAGR:Q", title="%"), color=col,
            tooltip=["규칙", alt.Tooltip("세후 CAGR:Q", format=".1f"), alt.Tooltip("세전 CAGR:Q", format=".1f")])
        _tick = alt.Chart(g).mark_tick(color="#94a3b8", thickness=3, size=18).encode(
            y=alt.Y("규칙:N", sort=order), x="세전 CAGR:Q")
        st.altair_chart((_bar + _tick).properties(height=330), use_container_width=True)
    with c2:
        st.markdown(f"**세후 최대 낙폭 (MDD, {per})** — 짧을수록 좋음")
        st.altair_chart(alt.Chart(g).mark_bar().encode(
            y=alt.Y("규칙:N", sort=order, title=None), x=alt.X("세후 MDD:Q", title="%"), color=col,
            tooltip=["규칙", alt.Tooltip("세후 MDD:Q", format=".1f")]).properties(height=330), use_container_width=True)

    # ── 표: 세후 상세 ──
    st.markdown(f"**백테스트 결과 ({per}, 세후 · 초기 1억원, 마지막 날 전량 매도 기준)**")
    st.dataframe(_hl_rows(pd.DataFrame([{
        "규칙": _qqq_disp(nm), "세전 CAGR %": pre[nm][0], "세후 CAGR %": v[0], "세후 MDD %": v[1], "최종 세후 자산(억)": v[2],
        "낸 세금(억)": v[3], "세후 CAGR %(1천만원)": v[4], "세후 CAGR %(5억원)": v[5], "연 매매": pre[nm][3]}
        for nm, v in zip(QQQ_TAX_RULES, QQQ_AFTERTAX[per])]),
        fmt={"세전 CAGR %": "{:.1f}", "세후 CAGR %": "{:.1f}", "세후 MDD %": "{:.1f}", "최종 세후 자산(억)": "{:.1f}", "낸 세금(억)": "{:.1f}",
             "세후 CAGR %(1천만원)": "{:.1f}", "세후 CAGR %(5억원)": "{:.1f}", "연 매매": "{:.1f}"}),
        use_container_width=True, hide_index=True)
    st.caption("주황 배경 = 기본 규칙(200일선 −3%, 월 1회). 일반 계좌라면 '200일선 아래면 50%만'·'변동성 목표 20%'도 대안입니다(아래 '실제로 쓴다면').")

    # ── 위기 구간 ──
    st.markdown("**위기 구간별 최대 낙폭 (세전 %)** — 어떤 규칙이 어떤 하락에 강한지")
    cr = pd.DataFrame(QQQ_CRISIS, columns=QQQ_CRISES)
    cr.insert(0, "규칙", QQQ_RULES)
    crl = cr.melt(id_vars=["규칙"], var_name="위기", value_name="낙폭")
    st.altair_chart(alt.Chart(crl).mark_rect().encode(
        x=alt.X("위기:N", sort=QQQ_CRISES, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("규칙:N", sort=QQQ_RULES, title=None),
        color=alt.Color("낙폭:Q", scale=alt.Scale(scheme="reds", reverse=True, domain=[-85, 0]), legend=None),
        tooltip=["규칙", "위기", alt.Tooltip("낙폭:Q", format=".1f")]).properties(height=330)
        + alt.Chart(crl).mark_text(fontSize=11).encode(
            x=alt.X("위기:N", sort=QQQ_CRISES), y=alt.Y("규칙:N", sort=QQQ_RULES),
            text=alt.Text("낙폭:Q", format=".1f"),
            color=alt.condition("datum['낙폭'] < -45", alt.value("white"), alt.value("#0f172a"))),
        use_container_width=True)
    st.caption("코로나처럼 한 달 만에 끝난 급락은 대부분의 규칙이 QQQ와 같이 맞았고, 닷컴·금융위기처럼 길게 이어진 하락에서 차이가 컸습니다.")

    with st.expander("비교한 규칙 10가지 설명 · 세전 결과 표", expanded=False):
        st.dataframe(_hl_rows(pd.DataFrame([{"규칙": _qqq_disp(k), "내용": v} for k, v in QQQ_RULE_DESC.items()])),
                     use_container_width=True, hide_index=True)
        st.dataframe(_hl_rows(pd.DataFrame([{"규칙": _qqq_disp(nm), "CAGR %": v[0], "MDD %": v[1], "샤프": v[2], "연 매매": v[3]}
                                            for nm, v in zip(QQQ_RULES, QQQ_PRETAX[per])]),
                              fmt={"CAGR %": "{:.1f}", "MDD %": "{:.1f}", "샤프": "{:.1f}", "연 매매": "{:.1f}"}),
                     use_container_width=True, hide_index=True)

    st.markdown("**실제로 쓴다면**")
    _render_cards([(t, sub, body) for t, sub, body in QQQ_ACTION_CARDS])
    st.markdown(QQQ_GUIDE_ACTION_NOTE)


# ===================== 📘 비트코인을 장기 보유하려면~ (2026-10-14 백테스트 정리) =====================
BTC_HALVINGS = [pd.Timestamp("2012-11-28"), pd.Timestamp("2016-07-09"), pd.Timestamp("2020-05-11"), pd.Timestamp("2024-04-20")]
BTC_NEXT_HALVING_EST = pd.Timestamp("2028-04-15")     # 블록 1,050,000 · 추정치 (2027년 말쯤 카운트다운 사이트로 확정)
BTC_RULES = ["BTC 보유", "120일선만", "120일선 + 12개월 전량", "120일선 + 분할 (권장)", "120일선 + 15개월 전량", "120일선 + 18개월 전량"]
# (CAGR, MDD, 샤프, 연 매수) · 매일 판단 · 슬리피지 0.2% · 세금 미반영 · 현금 0%
BTC_RESULTS = {
    "2015~": [(60.3, -83.4, 1.05, 0.0), (76.9, -60.7, 1.38, 4.4), (58.6, -33.0, 1.34, 2.6), (66.0, -33.0, 1.43, 2.7), (72.5, -35.5, 1.46, 2.7), (93.4, -35.5, 1.60, 3.2)],
    "2015~2018": [(85.0, -83.4, 1.19, 0.0), (103.8, -60.1, 1.47, 5.1), (53.8, -32.6, 1.24, 3.0), (69.5, -32.6, 1.42, 3.0), (83.5, -35.5, 1.47, 3.0), (145.7, -35.5, 1.83, 3.0)],
    "2019~2022": [(45.0, -76.6, 0.88, 0.0), (88.6, -33.0, 1.52, 2.3), (85.7, -33.0, 1.57, 1.5), (87.1, -33.0, 1.59, 1.8), (88.4, -33.0, 1.60, 1.8), (105.9, -33.0, 1.72, 1.8)],
    "2023~": [(53.3, -53.1, 1.15, 0.0), (42.8, -29.8, 1.16, 6.1), (38.8, -28.1, 1.16, 3.2), (43.1, -28.1, 1.25, 3.4), (47.3, -28.1, 1.31, 3.4), (41.1, -28.1, 1.16, 4.8)],
    "2020-08~": [(37.1, -76.6, 0.84, 0.0), (56.7, -32.6, 1.29, 4.4), (52.5, -28.1, 1.34, 2.1), (56.2, -28.1, 1.40, 2.4), (59.7, -28.1, 1.45, 2.4), (64.7, -28.1, 1.45, 3.2)],
}
BTC_CYCLES = ["2016~2020 사이클", "2020~2024 사이클", "2024~ 사이클 (진행 중)"]
# 반감기 → 다음 반감기: (수익률 %, MDD %)
BTC_CYCLE_RES = [[(1221, -83), (656, -77), (28, -53)], [(1865, -61), (1586, -33), (31, -30)], [(497, -33), (1485, -25), (18, -26)],
                 [(778, -33), (1533, -25), (33, -26)], [(1102, -36), (1581, -25), (48, -26)], [(3720, -36), (2296, -27), (25, -26)]]
BTC_RULE_DESC = {
    "BTC 보유": "사서 계속 들고 감 (기준선)",
    "120일선만": "매일 종가가 120일선 위면 BTC 100%, 아래면 현금",
    "120일선 + 12개월 전량": "120일선 규칙 + 반감기 후 12~30개월은 현금",
    "120일선 + 분할 (권장)": "120일선 규칙 + 반감기 후 12~15개월은 최대 50%, 15~30개월은 현금",
    "120일선 + 15개월 전량": "120일선 규칙 + 반감기 후 15~30개월은 현금",
    "120일선 + 18개월 전량": "120일선 규칙 + 반감기 후 18~30개월은 현금 (과거 고점에 맞춘 사후 최적값 · 참고용)",
}

BTC_GUIDE_INTRO = """
**한눈에 보는 결론**

1. **1순위 기준 — 120일선 + 반감기 사이클 분할 정리.** 매일 종가가 120일선 위면 보유하되, 반감기 후 12개월에 절반, 15개월에 전부 정리하고 30개월 이후 다시 120일선 규칙으로 돌아갑니다. 2015\\~ 백테스트에서 CAGR 66.0%, 최대 낙폭 -33.0%로, 그냥 보유(60.3%, -83.4%)보다 수익은 비슷하고 낙폭은 절반 이하였습니다.
2. **120일선만으로는 '포물선 고점 직후의 첫 급락'을 못 피합니다.** 2017-12 고점(\\$19,497) 뒤 첫 매도 신호는 2018-01-30(\\$10,106)에 나와 이미 -48%였고, 휩소까지 겹쳐 -60.7%까지 빠졌습니다. 사이클 정리가 이 약점을 메웁니다.
3. **2순위 기준 — 매달 돈을 넣는다면 '적립식 + 1순위 규칙'.** 매월 같은 날 같은 금액을 넣고, 그 돈을 BTC로 살지 현금으로 둘지는 1순위 규칙(종가가 120일선 위면 보유·아래면 현금, 반감기 후 12\\~15개월은 최대 50%, 15\\~30개월은 현금, 30개월 이후 120일선 규칙으로 복귀)이 정합니다. 2015년부터 월 적립 시 순수 적립식은 평가액이 -83%까지 빠졌지만, 120일선 적립식은 -59%, 사이클 분할까지 더하면 -33%였습니다.
4. **MSTR은 120일선만으로는 비트코인을 대신할 수 없습니다.** 120일선을 어떻게 적용해도 최대 낙폭이 -79\\~-89%였습니다. 코인 계좌 없이 MSTR을 쓰려면 위쪽 '🪙 MSTR' 탭의 규칙(반반 신호 + 사이클 + 비중 조절 · 변동성 목표 80%, 낙폭 -48%)을 따르세요.
5. **사이클 근거는 과거 3번뿐입니다.** 과거 고점이 반감기 17\\~18개월 후에 몰려 있었지만 표본이 작아, 고점보다 늦게 파는 위험을 줄이려고 12·15개월 분할을 기준으로 삼았습니다.
"""

BTC_GUIDE_COND = """
**테스트 조건**: BTC-USD 일봉(야후, 주말 포함), 2015-01 \\~ 2026-10-14. 매일 마감된 일봉 종가로 판단해 그 종가에 체결, 다음 날부터 수익 반영.
매매할 때마다 슬리피지 0.2%(편도), 현금 수익 0%, **세금 미반영**. 120일선은 최근 120개 일봉(약 4개월) 단순평균입니다.
반감기는 2016-07-09, 2020-05-11, 2024-04-20을 쓰고 '반감기 후 개월'은 30.44일 = 1개월로 셉니다. 모두 PC 스크립트(`btc_mstr_ma120_backtest.py`, `btc_ma_sensitivity.py`, `btc_cycle_split_backtest.py`, `btc_dca_backtest.py`) 결과입니다.
"""

BTC_GUIDE_ACTION = """
실제 보유 비중 = 120일선 신호(100% 또는 0%) × 사이클 상한입니다. 확인은 매일 한국 시간 오전 9시 이후(일봉 마감), 막 마감된 종가 하나만 봅니다. 차트는 한 곳으로 고정하세요(원화 거래소는 해외 가격과 차이가 있어 선 위치가 조금 다릅니다).

| 반감기 | 12개월 (50%) | 15개월 (0%) | 30개월 (복귀) |
|---|---|---|---|
| 2024-04-20 | 2025-04-20 | 2025-07-20 | 2026-10-20 |
| 2028년 4월 (추정) | 2029년 4월 | 2029년 7월 | 2030년 10월 |

**2순위: 매달 적립한다면 — 적립식 + 위 규칙**

1. 매월 같은 날 같은 금액을 거래소 원화 잔고에 넣습니다.
2. 보유 상태(120일선 위, 사이클 상한 100%)면 적립금도 바로 BTC를 삽니다. 상한 50% 구간이면 적립금의 절반만 삽니다.
3. 현금 상태면 적립금도 현금으로 쌓아 두었다가, 다음 매수 신호 때 쌓인 현금 전액으로 삽니다.
4. 사이클 규칙 없이 120일선만 쓰는 적립식(B)은 수익이 더 크지만 평가액 낙폭도 -59%까지 각오해야 합니다.

**주의와 한계**

- **세금 미반영**: 연 2\\~4회 사고팔기 때문에 국내 가상자산 과세가 시행되면 수익이 줄어듭니다. 시행 시점과 공제 조건은 따로 확인하세요.
- **휩소**: 120일선 근처에서는 몇 주 사이에 여러 번 사고팔 수 있습니다(2024년 여름 한 달 반 동안 7번). 판 가격보다 비싸도 규칙대로 다시 사야 규칙이 유지됩니다.
- **사이클은 약해지는 중**: 사이클 낙폭이 -83% → -77% → -53%로 줄고 있고, 현물 ETF 같은 기관 자금이 커졌습니다. 사이클이 흐려지면 상승기 일부를 놓치는 비용만 생깁니다.
- **비중**: 사이클 분할을 써도 기대 낙폭은 -33\\~-60% 범위입니다. 2026 혼합전략과 따로, 전체 자산의 일부로만 운용하는 것을 전제로 합니다. 과거 성과가 미래 수익을 보장하지 않습니다.
"""


@st.cache_data(ttl=3600)
def get_btc_daily_close():
    """BTC-USD 일봉 종가 (마감된 일봉만, UTC 기준 오늘 진행 중인 봉은 제외)."""
    try:
        df = yf.download("BTC-USD", period="2y", interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        c.index = pd.to_datetime(c.index).tz_localize(None)
        _today_utc = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        if len(c) and c.index[-1] >= _today_utc:
            c = c.iloc[:-1]
        return c if len(c) > 130 else None
    except Exception:
        return None


def _btc_cycle_state(day):
    """day 기준 직전 반감기, 경과 개월, 사이클 상한, 다음 경계일."""
    hs = [h for h in BTC_HALVINGS + [BTC_NEXT_HALVING_EST] if h <= day]
    h = hs[-1]
    b12, b15, b30 = h + pd.DateOffset(months=12), h + pd.DateOffset(months=15), h + pd.DateOffset(months=30)
    months = (day - h).days / 30.44
    if day < b12:
        cap, nxt = 100, (b12, "50%로 축소")
    elif day < b15:
        cap, nxt = 50, (b15, "0%로 전량 정리")
    elif day < b30:
        cap, nxt = 0, (b30, "100% 복귀 · 120일선 규칙")
    else:
        nh = BTC_NEXT_HALVING_EST if h < BTC_NEXT_HALVING_EST else h + pd.DateOffset(years=4)
        cap, nxt = 100, (nh + pd.DateOffset(months=12), "다음 반감기 후 12개월 · 50%로 축소 (반감기 날짜 추정)")
    return h, months, cap, nxt


_HL_STYLE = "background-color:#ffedd5;color:#7c2d12;font-weight:700;"


def _hl_rows(df, key_col="규칙", fmt=None):
    """지금 적용하는 규칙('(권장)'이 붙은 행)을 주황 배경으로 강조."""
    sty = df.style.apply(lambda r: [_HL_STYLE if "권장" in str(r[key_col]) else "" for _ in r], axis=1)
    return sty.format(fmt) if fmt else sty


def _btc_card(head, weight, weight_sub, body):
    """비트코인 섹션의 핵심 상자: 굵은 테두리 + '지금 보유 비중' 큰 숫자."""
    st.markdown(f"""
<div style="border:3px solid #0f2747;border-radius:14px;background:#ffffff;padding:14px 18px;margin:8px 0 8px 0;">
  <div style="font-size:0.98rem;font-weight:800;color:#0f2747;margin-bottom:10px;">{head}</div>
  <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;background:#f1f5f9;border-radius:10px;padding:12px 16px;">
    <div style="min-width:150px;">
      <div style="font-size:0.85rem;font-weight:700;color:#475569;">지금 보유 비중</div>
      <div style="font-size:2.5rem;font-weight:900;color:#0f2747;line-height:1.15;">{weight}</div>
    </div>
    <div style="flex:1;min-width:220px;font-size:1rem;color:#1e293b;line-height:1.6;">{weight_sub}</div>
  </div>
  <div style="margin-top:10px;font-size:0.9rem;color:#334155;line-height:1.75;">{body}</div>
</div>""", unsafe_allow_html=True)


def render_btc_longhold_guide():
    st.header("📘 비트코인을 장기 보유하려면~")
    st.caption("비트코인을 오래 들고 가면서 큰 낙폭(MDD)을 줄이는 규칙을 2015년부터 백테스트한 정리입니다. "
               "1순위는 '120일선 + 반감기 사이클 분할 정리', 2순위는 매달 적립할 때의 '적립식 + 1순위 규칙'(매월 같은 금액을 넣고, 종가가 120일선 위면 보유·아래면 현금, 반감기 후 12\\~15개월은 최대 50%, 15\\~30개월은 현금, 30개월 이후 120일선 규칙으로 복귀)입니다. 주황 배경 = 지금 적용하는 규칙.")
    if not tab_toggle("내용 펼치기 (표·그래프)", key="btc_guide_open_r"):
        return
    _btc_section_coin()


def render_mstr_tab():
    """🪙 MSTR 탭 (2026-10-22, 미국 주식 랭킹의 '📘 코인 계좌 없이 MSTR로 대신하려면~' 섹션을 탭으로 승격).
    순서: 한눈에 → 📡 오늘(신호판 + 실시간 장부 1,000만원) → 📋 규칙 → 사이클 카드 → 📊 근거 → 📒 지난 사이클 장부.
    이 탭은 눌렀을 때만 그려지므로(st.tabs on_change="rerun" + tab_mstr.open) 오늘의 신호·실시간 장부는 항상 펼쳐 둠."""
    st.header("🪙 MSTR — 코인 계좌 없이 비트코인 흐름에 투자")
    st.caption("코인 계좌 없이 증권 계좌로 비트코인 흐름에 투자하는 방법입니다. MSTR(스트래티지)을 BTC 120일선·MSTR 200일선 반반 신호, "
               "반감기 사이클 상한, 변동성 목표 80%로 매매하는 규칙과 백테스트, 오늘의 신호, 실시간·지난 사이클 1,000만원 장부를 정리했습니다. "
               "MSTR을 포함한 개별투자는 운용자금의 10% 이내(투자 원칙 선언문).")
    _PUB = 10_000_000                       # 이 탭은 1,000만원 기준 (관리자 모드는 2,000만원 + 추가 입금)

    def _today_block():
        _mstr_signal_panel(0.8, key="mstrtab_sig", capital=_PUB, show_timing=False)
        st.markdown("#### 📒 실시간 장부 (1,000만원)")
        st.info(f"사이클 현금 구간이 끝난 {MSTR_PAPER_START.month}월 {MSTR_PAPER_START.day}일(2026년)부터 1,000만원으로, 지금 규칙(반반 신호 · 사이클 · 변동성 목표 80%)대로 "
                "매매하는 장부입니다. 매일 미국 장 종가로 한 줄씩 자동으로 쌓이며, 추가 입금은 넣지 않습니다.")
        _render_mstr_ledger(MSTR_PAPER_START, 0.8, key="mstrtab_live", capital=_PUB, compare_prev=True)

    render_mstr_alternative(None, after_card=_today_block)
    st.markdown("#### 📒 지난 사이클 장부 (1,000만원)")
    st.info("지난 사이클 '④ 다음 사이클 준비' 시작일(2020-05-11 반감기 + 30개월 = 2022-11-11)부터 1,000만원으로, 지금 규칙(반반 신호 · 사이클 · 변동성 목표 80%)대로 "
            "매매했다면의 장부입니다. ④ 100% → 2024-04 반감기 후 ① 100% → ② 50%(2025-04-21) → ③ 0%(2025-07-21, 전량 매도) → 오늘까지 한 사이클 전체가 들어 있습니다.")
    if tab_toggle("📒 지난 사이클 장부 보기 (표·그래프·낙폭)", key="mstr_tab_past_r"):
        _render_mstr_ledger(pd.Timestamp("2022-11-11"), 0.8, key="btcguide_ledger", capital=_PUB)
    with st.expander("📖 읽는 법 — 사이클이 끝나면 두 선이 비슷해지는데, 그럼 규칙은 왜 필요한가", expanded=False):
        st.markdown("""
이 샘플만 보면 **사이클이 끝난 지금 두 선이 거의 같은 곳**(규칙 약 7,785만원, 그냥 보유 약 8,687만원)에 와 있습니다. 
다만 그건 **시작일이 운 좋게 바닥 근처였기 때문**이고, 두 방식의 진짜 차이는 도착점이 아니라 **가는 길**에 있습니다.

**1. 같은 도착점, 전혀 다른 길**

| | 규칙대로 매매 | MSTR 그냥 보유 |
|---|---|---|
| 최고 평가액 | 약 1억원 안팎 | **약 2억 7천만원** |
| 최고점 → 지금 | 크게 줄지 않음 (현금으로 지킴) | **2억 7천만 → 8천7백만원 (-83%)** |
| 최대 낙폭 | -41% | -83% |

그냥 보유로 지금의 8천7백만원에 도착하려면, **2억 7천만원이 5천만원대로 줄어드는 1년 반을 아무것도 하지 않고 버텨야** 했습니다. 실제로는 그 과정에서 팔고 나오는 사람이 대부분입니다.

**2. 시작일이 달랐다면** (같은 규칙 · 1,000만원 · 오늘까지)

| 시작일 | 규칙대로 매매 | MSTR 그냥 보유 |
|---|---|---|
| 2022-11-11 (바닥 근처 · 이 샘플) | 7,785만원 · MDD -41% | 8,687만원 · MDD -83% |
| 2023-06-01 (상승 초입) | **7,006만원** · -41% | 5,074만원 · -83% |
| 2021-02-09 (지난 고점) | **5,323만원** · -44% | **1,196만원** · -89% |
| 2024-03-28 (급등 후) | **1,628만원** · -41% | 893만원 · -83% |
| 2024-11-20 (이번 고점) | **758만원** · -40% | **321만원** · -83% |

**바닥에서 시작한 경우에만 그냥 보유가 비슷하거나 조금 앞섰고**, 나머지 시작일에서는 모두 규칙이 크게 앞섰습니다. 
고점 근처에서 시작하면 그냥 보유는 원금의 3분의 1 이하로 줄었는데, 규칙은 낙폭을 -40% 안팎으로 묶었습니다.

<div style="color:#dc2626;font-weight:700;line-height:1.75;margin-top:6px;">
정리<br>
• 규칙의 가치는 '더 많이 버는 것'보다 <u>언제 시작하든 비슷한 결과로, -40% 안쪽에서 버틸 수 있게 해 주는 것</u>입니다. 우리는 지금이 바닥인지 고점인지 미리 알 수 없습니다.<br>
• 선언문 제1원칙(생존)과 제2원칙(예측이 틀려도 무너지지 않을 완충 지대)이 바로 이 차이입니다.
</div>

<small>이 읽는 법의 금액은 환율 1,350원 고정·<b>세금 반영 전</b>(2026-10-20 계산) 값이라, 위 장부(실제 환율·양도세 22% 반영)보다 큽니다. 규칙과 그냥 보유의 차이를 보는 용도로만 보세요.</small>
""", unsafe_allow_html=True)


def _btc_now_state():
    """BTC 120일선 상태 (MSTR 섹션이 비트코인 섹션을 펼치지 않아도 쓸 수 있게 따로 계산)."""
    try:
        _c = get_btc_daily_close()
        if _c is None:
            return None
        _ma = float(_c.rolling(120).mean().iloc[-1]); _px = float(_c.iloc[-1])
        return {"above": _px > _ma, "gap": (_px / _ma - 1) * 100, "day": _c.index[-1]}
    except Exception:
        return None


def _btc_section_coin():
    """🪙 비트코인으로 매매 (코인 계좌로 직접): 1순위 120일선 + 반감기 사이클 분할 정리, 2순위 적립식."""

    st.markdown(BTC_GUIDE_INTRO)

    # ── 지금 BTC 상태: 1순위 규칙의 현재 값 ──
    _btc_now = None
    try:
        _c = get_btc_daily_close()
        if _c is not None:
            _px, _ma = float(_c.iloc[-1]), float(_c.rolling(120).mean().iloc[-1])
            _gap = (_px / _ma - 1) * 100
            _btc_now = {"above": _px > _ma, "gap": _gap, "day": _c.index[-1]}
            _day = _c.index[-1]
            _h, _mo, _cap, (_nd, _nl) = _btc_cycle_state(_day)
            _sig = 100 if _px > _ma else 0
            _w = _sig * _cap // 100
            if _w == 100:
                _act = "120일선 위 · 사이클 상한 100% → <b>BTC 보유</b> (적립금도 매수)."
            elif _w == 50:
                _act = "120일선 위 · 사이클 상한 50% → <b>절반만 보유</b>, 나머지는 현금."
            elif _sig and _cap == 0:
                _act = (f"120일선은 위지만 반감기 후 현금 구간이라 <b>사지 않습니다</b>. "
                        f"<b>{_nd:%Y-%m-%d}</b>부터 그날 종가가 120일선 위면 매수합니다.")
            else:
                _act = "120일선 아래라 <b>현금</b>으로 둡니다. 종가가 120일선 위로 올라오면 매수합니다."
            _btc_card(f"지금 비트코인에 1순위 규칙을 적용하면 · 기준 {_day:%Y-%m-%d} 마감 일봉 (한국 시간 오전 9시 마감)",
                      f"BTC {_w}%", f"현금 {100 - _w}% · {_act}",
                      f"① 120일선 신호: 선 {'위' if _sig else '아래'} ({_gap:+.1f}%) — 종가 &#36;{_px:,.0f} · 120일선 &#36;{_ma:,.0f}<br>"
                      f"② 반감기 사이클 상한: {_cap}% — {_h:%Y-%m-%d} 반감기 후 {_mo:.1f}개월 · 다음 변경 {_nd:%Y-%m-%d} ({_nl})<br>"
                      f"<span style='color:#64748b'>보유 비중 = ① 신호(위 100% · 아래 0%) × ② 상한</span>")
            st.caption("참고 정보이며 매매 지시가 아닙니다. 야후 BTC-USD 기준이라 원화 거래소 가격과 조금 다를 수 있습니다.")
    except Exception:
        pass

    st.markdown(BTC_GUIDE_COND)
    per = st.radio("기간", list(BTC_RESULTS.keys()), index=0, horizontal=True, key="btc_guide_per")

    # ── 그래프: CAGR / MDD ──
    g = pd.DataFrame([{"규칙": nm, "CAGR": v[0], "MDD": v[1], "샤프": v[2],
                       "기준": "BTC 보유" if nm == "BTC 보유" else ("권장" if "권장" in nm else "규칙")}
                      for nm, v in zip(BTC_RULES, BTC_RESULTS[per])])
    col = alt.Color("기준:N", scale=alt.Scale(domain=["BTC 보유", "규칙", "권장"], range=["#64748b", "#0f766e", "#f7931a"]), legend=None)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**연수익률 (CAGR, {per})** — 길수록 좋음 · 주황 = 1순위 규칙")
        st.altair_chart(alt.Chart(g).mark_bar().encode(
            y=alt.Y("규칙:N", sort=BTC_RULES, title=None), x=alt.X("CAGR:Q", title="%"), color=col,
            tooltip=["규칙", alt.Tooltip("CAGR:Q", format=".1f"), alt.Tooltip("샤프:Q", format=".2f")]).properties(height=300),
            use_container_width=True)
    with c2:
        st.markdown(f"**최대 낙폭 (MDD, {per})** — 짧을수록 좋음")
        st.altair_chart(alt.Chart(g).mark_bar().encode(
            y=alt.Y("규칙:N", sort=BTC_RULES, title=None), x=alt.X("MDD:Q", title="%"), color=col,
            tooltip=["규칙", alt.Tooltip("MDD:Q", format=".1f")]).properties(height=300), use_container_width=True)

    st.markdown(f"**백테스트 결과 ({per}, 세금 미반영)**")
    _bd = pd.DataFrame([{"규칙": nm, "CAGR %": v[0], "MDD %": v[1], "샤프": v[2],
                         "연 매수": v[3], "내용": BTC_RULE_DESC[nm]} for nm, v in zip(BTC_RULES, BTC_RESULTS[per])])
    st.dataframe(_hl_rows(_bd, fmt={"CAGR %": "{:.1f}", "MDD %": "{:.1f}", "샤프": "{:.2f}", "연 매수": "{:.1f}"}),
                 use_container_width=True, hide_index=True)
    st.caption("'18개월 전량'이 가장 좋아 보이는 건 과거 3번의 고점(반감기 후 17.3·18.0·17.6개월)에 맞춘 결과입니다. "
               "현금 전환이 고점보다 3개월만 늦어도(21개월) 2015\\~ 최대 낙폭이 -54\\~-59%로 돌아가, 앞당겨진 12·15개월 분할을 1순위로 삼았습니다.")

    # ── 사이클별 히트맵 ──
    st.markdown("**사이클별 최대 낙폭 (%)** — 반감기에서 다음 반감기까지, 칸에 마우스를 올리면 그 사이클 수익률")
    cy = pd.DataFrame([{"규칙": nm, "사이클": cn, "낙폭": r[1], "수익률": r[0]}
                       for nm, rows in zip(BTC_RULES, BTC_CYCLE_RES) for cn, r in zip(BTC_CYCLES, rows)])
    st.altair_chart(alt.Chart(cy).mark_rect().encode(
        x=alt.X("사이클:N", sort=BTC_CYCLES, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("규칙:N", sort=BTC_RULES, title=None),
        color=alt.Color("낙폭:Q", scale=alt.Scale(scheme="reds", reverse=True, domain=[-85, 0]), legend=None),
        tooltip=["규칙", "사이클", alt.Tooltip("낙폭:Q", format=".0f"), alt.Tooltip("수익률:Q", format=",.0f", title="사이클 수익률 %")]).properties(height=300)
        + alt.Chart(cy).mark_text(fontSize=11).encode(
            x=alt.X("사이클:N", sort=BTC_CYCLES), y=alt.Y("규칙:N", sort=BTC_RULES),
            text=alt.Text("낙폭:Q", format=".0f"),
            color=alt.condition("datum['낙폭'] < -45", alt.value("white"), alt.value("#0f172a"))),
        use_container_width=True)
    st.caption("분할 정리의 비용은 2016\\~2020 사이클에 몰려 있습니다: 2017년 7월 절반, 10월 전량 정리로 마지막 폭등(\\$5,000 → \\$19,500)을 대부분 놓쳤지만, 이후 -83% 하락은 피했습니다(사이클 수익 778% vs 120일선만 1,865%).")

    # ── 2순위: 적립식 ──
    st.markdown("**2순위 근거 — 매월 같은 금액 적립 시 (월초 적립, \\~2026-10-14)** · 주황 열(C) = 지금 적용하는 2순위 규칙: "
                "매월 적립 + 1순위 규칙(120일선 + 반감기 사이클 분할)")
    _dca = pd.DataFrame([
        ["2015-01", "60.5% · 47.9배 · -83.0%", "79.6% · 147.0배 · -59.4%", "67.0% · 70.7배 · -32.6%"],
        ["2017-12 (고점)", "35.3% · 5.1배 · -74.8%", "54.5% · 12.2배 · -42.5%", "55.5% · 12.7배 · -27.6%"],
        ["2021-11 (고점)", "27.1% · 1.9배 · -49.2%", "30.2% · 2.1배 · -22.8%", "31.6% · 2.1배 · -21.6%"],
        ["2024-04 (반감기)", "4.4% · 1.1배 · -40.2%", "10.9% · 1.1배 · -15.3%", "9.4% · 1.1배 · -15.3%"],
    ], columns=["적립 시작", "A 순수 적립식", "B 적립식 + 120일선", "C 적립식 + 120일선 + 분할 (2순위 권장)"])
    st.dataframe(_dca.style.apply(lambda c: [_HL_STYLE] * len(c), subset=["C 적립식 + 120일선 + 분할 (2순위 권장)"]),
                 use_container_width=True, hide_index=True)
    st.caption("각 칸 = 연 수익률(IRR) · 투입금 대비 배수 · 평가액 최대 하락. 적립식은 시작 시점 걱정을 덜어 주지만(2017년 고점에 시작해도 5.1배), "
               "몇 년 지나면 쌓인 금액에 비해 적립금이 작아져 하락장에서는 보유와 똑같이 빠집니다. 규칙 계좌에 적립하면 낙폭이 절반 이하로 줄었습니다.")

    with st.expander("추가 근거 · 이평선 길이 민감도 · 판단 주기 · MSTR · 과거 사이클", expanded=False):
        st.markdown("**이평선 길이 민감도** (2015\\~, 매일 판단, 사이클 규칙 없음) — 120은 좋은 쪽 끝이지만, 50\\~250일 모두 보유보다 샤프가 높음")
        _ml = [50, 60, 80, 100, 120, 150, 180, 200, 250]
        st.dataframe(pd.DataFrame([
            ["CAGR %"] + [69.9, 65.2, 59.1, 60.5, 76.9, 74.7, 62.2, 59.0, 60.1],
            ["MDD %"] + [-59.6, -62.0, -56.4, -62.1, -60.7, -61.7, -64.1, -70.4, -66.4],
            ["샤프"] + [1.35, 1.29, 1.19, 1.20, 1.38, 1.35, 1.20, 1.15, 1.14],
        ], columns=["이평선 (보유 60.3% · -83.4% · 1.05)"] + [f"{m}일" for m in _ml]), use_container_width=True, hide_index=True)
        st.markdown("""
**판단 주기** (2020-08\\~, 120일선 0%/0%): 매일 56.7% · -32.6% / 매주 34.7% · -50.8% / 매월 33.6% · -58.8%. 비트코인은 급락이 빨라 **매일 판단**이 필요합니다. 주식에서 쓰는 −3%/+5% 여유폭은 비트코인에서는 일관되게 낫지 않았습니다.

**MSTR로 대신하면?** (2020-08-11 \\~, MSTR이 비트코인을 사기 시작한 날부터)

| 방식 | CAGR | MDD | 샤프 |
|---|---|---|---|
| BTC 보유 | 37.0% | -76.6% | 0.84 |
| BTC · BTC 120일선 매일 | **56.7%** | **-32.6%** | **1.29** |
| MSTR 보유 | 50.2% | -89.3% | 0.90 |
| MSTR · MSTR 120일선 매일 | 44.7% | -83.6% | 0.87 |
| MSTR · BTC 120일선 매일 | 47.8% | -81.0% | 0.91 |

MSTR은 12가지 변형 모두 낙폭 -79\\~-89%였습니다. 급등 후 급락이 120일선보다 빠르고, 2025년처럼 BTC가 -6%일 때 MSTR이 -48%가 되는 '프리미엄 축소'는 BTC 신호로 잡히지 않습니다.

**과거 사이클** (반감기 → 고점 → 바닥)

| 반감기 | 고점 (반감기 후) | 바닥 (반감기 후) | 낙폭 |
|---|---|---|---|
| 2016-07-09 | 2017-12-16 \\$19,497 (17.3개월) | 2018-12 (29.2개월) | -83.4% |
| 2020-05-11 | 2021-11-08 \\$67,566 (18.0개월) | 2022-11 (30.4개월) | -76.6% |
| 2024-04-20 | 2025-10-06 \\$124,752 (17.6개월) | 2026-06 \\$58,558 (26.3개월, 지금까지 최저) | -53.1% |

**현금 전환 시점 민감도** (120일선 + n개월부터 30개월까지 현금, 2015\\~): 12개월 CAGR 59% · MDD -33% / 15개월 72% · -36% / 18개월 93% · -36% / **21개월 81% · -54%**. 고점을 지나서 팔면 방어 효과가 사라집니다.
""")

    render_btc_phase_now(_btc_now)
    st.markdown(BTC_GUIDE_ACTION)


BTC_PHASES = [  # (이름, 시작 개월, 끝 개월, 보유 상한, 할 일)
    ("① 상승기", 0, 12, 100, "120일선 규칙 그대로: 종가가 선 위면 보유(적립금도 매수), 아래면 전량 매도"),
    ("② 고점 경계", 12, 15, 50, "보유분의 절반 매도. 적립금은 절반만 매수. 120일선 아래로 가면 나머지도 매도"),
    ("③ 하락·바닥", 15, 30, 0, "전량 매도 후 현금 유지. 120일선 위여도 사지 않고 적립금도 현금으로 쌓음"),
    ("④ 다음 사이클 준비", 30, None, 100, "120일선 규칙으로 복귀: 종가가 선 위면 쌓인 현금 전액으로 매수"),
]


def _btc_phase_rows(today):
    """오늘이 속한 반감기 사이클의 ①~④ 구간 (이름, 시작·끝 개월, 상한, 할 일, 시작일, 끝일)과 지금 구간 번호."""
    h, _mo, _cap, _nx = _btc_cycle_state(today)
    nh = BTC_NEXT_HALVING_EST if h < BTC_NEXT_HALVING_EST else h + pd.DateOffset(years=4)
    rows, cur = [], 0
    for i, (nm, a, b, cp, todo) in enumerate(BTC_PHASES):
        s_ = h + pd.DateOffset(months=a)
        e_ = (h + pd.DateOffset(months=b)) if b is not None else nh
        if s_ <= today < e_:
            cur = i
        rows.append((nm, a, b, cp, todo, s_, e_))
    return rows, cur, nh


def _render_cards(items, cur=None):
    """카드 목록: items = [(제목, 왼쪽 작은 설명 html, 오른쪽 본문 html)]. cur 번째는 주황 테두리·배경 + '지금' 배지."""
    _cards = []
    for i, (title, sub, body) in enumerate(items):
        _on = (cur is not None and i == cur)
        _box = ("border:2px solid #f59e0b;background:#ffedd5;" if _on else "border:1px solid #e2e8f0;background:#ffffff;")
        _tag = ("<span style='background:#c2410c;color:#fff;border-radius:6px;padding:1px 8px;font-size:0.8rem;margin-left:6px;'>지금</span>"
                if _on else "")
        _cards.append(
            f"<div style='{_box}border-radius:10px;padding:10px 14px;margin:6px 0;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;'>"
            f"<div style='min-width:210px;flex:0 0 auto;'><b style='color:#0f2747;font-size:1rem;'>{title}</b>{_tag}"
            f"<div style='font-size:0.85rem;color:#475569;line-height:1.5;'>{sub}</div></div>"
            f"<div style='flex:1;min-width:200px;font-size:0.92rem;color:#1e293b;line-height:1.55;'>{body}</div></div>")
    st.markdown("<div style='margin:4px 0 6px 0;'>" + "".join(_cards) + "</div>", unsafe_allow_html=True)


def _render_phase_cards(rows, cur, todos=None):
    """반감기 구간 카드. todos로 할 일 문구를 바꿀 수 있음(MSTR용)."""
    items = []
    for i, (nm_, a_, b_, cp_, todo_, s2, e2) in enumerate(rows):
        if todos:
            todo_ = todos[i]
        rng = f"반감기 후 {a_}&#126;{b_}개월" if b_ is not None else f"반감기 후 {a_}개월&#126;다음 반감기"
        items.append((nm_, f"{s2:%Y-%m-%d} &#126; {e2 - pd.Timedelta(days=1):%Y-%m-%d}<br>{rng}", f"<b>보유 상한 {cp_}%</b> · {todo_}"))
    _render_cards(items, cur)


def render_btc_phase_now(btc_now=None):
    """'실제로 쓴다면': 오늘이 사이클의 어느 구간인지와 할 일을 날짜로 보여 줌."""
    st.markdown("**실제로 쓴다면 — 1순위: 120일선 + 반감기 사이클 분할 정리**")
    st.caption("반감기 = 비트코인 채굴 보상이 절반으로 줄어드는 날로, 약 4년마다 옵니다(최근 2024-04-20, 다음은 2028년 4월쯤 예상). "
               "과거 세 번 모두 반감기 후 17\\~18개월에 가격 고점이 왔고, 이후 약 1년간 큰 하락이 이어졌습니다. 그래서 반감기 날짜를 기준으로 구간을 나눕니다.")
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    h, mo, cap, (nd, nl) = _btc_cycle_state(today)
    rows, cur, nh = _btc_phase_rows(today)
    nm, a, b, cp, todo, s_, e_ = rows[cur]

    # ── 지금 위치 안내 상자 ──
    if btc_now is not None:
        _sig_txt = (f"지금 BTC는 120일선 **위**({btc_now['gap']:+.1f}%)" if btc_now["above"]
                    else f"지금 BTC는 120일선 **아래**({btc_now['gap']:+.1f}%)")
    else:
        _sig_txt = "120일선 값은 위 '지금 비트코인에 1순위 규칙을 적용하면' 표를 확인하세요"
    if cp == 0:
        _now_do = "BTC를 사지 않고 현금으로 둡니다. 매달 적립금도 현금으로 쌓아 둡니다."
    elif cp == 50:
        _now_do = "보유 비중을 최대 50%로 둡니다. 120일선 아래면 0%입니다."
    else:
        _now_do = ("120일선 위면 BTC 보유, 아래면 현금입니다. " +
                   ("지금은 선 위라 **보유(매수)** 구간입니다." if btc_now and btc_now["above"] else
                    ("지금은 선 아래라 **현금** 구간입니다." if btc_now else "")))
    _left = (nd - today).days
    _next_msg = f"**다음 변경: {nd:%Y-%m-%d} ({_left}일 뒤) — {nl}**"
    if cp == 0 and btc_now is not None:
        _next_msg += (" · 그날 종가가 120일선 위면 쌓인 현금으로 매수, 아래면 선 위로 올라올 때까지 현금 유지"
                      + (" (지금 기준이면 매수)" if btc_now["above"] else " (지금 기준이면 현금 유지)"))
    _md2html = lambda t: _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    if btc_now is not None:
        _wt = cp if btc_now["above"] else 0
        _wlabel = f"BTC {_wt}%"
    else:
        _wlabel = f"최대 {cp}%"
    _btc_card(f"📍 지금({today:%Y-%m-%d})은 {nm} 구간 — {h:%Y-%m-%d} 반감기 후 {mo:.1f}개월 "
              f"({s_:%Y-%m-%d} &#126; {e_ - pd.Timedelta(days=1):%Y-%m-%d})",
              _wlabel, "<b>할 일</b>: " + _md2html(_now_do),
              _md2html(_sig_txt) + ".<br>" + _md2html(_next_msg))

    # ── 구간 타임라인 ──
    try:
        tl = pd.DataFrame([{"구간": r[0], "시작": r[5], "끝": r[6], "상한": f"{r[3]}%",
                            "라벨": f"{r[0]} · {r[3]}%", "기간": f"{r[5]:%Y-%m-%d} ~ {r[6]:%Y-%m-%d}"} for r in rows])
        _col = alt.Color("상한:N", scale=alt.Scale(domain=["100%", "50%", "0%"], range=["#16a34a", "#f59e0b", "#94a3b8"]), legend=None)
        bars = alt.Chart(tl).mark_bar(height=34, cornerRadius=3).encode(
            x=alt.X("시작:T", title=None, axis=alt.Axis(format="%Y-%m", labelAngle=0)), x2="끝:T",
            y=alt.value(30), color=_col, tooltip=["구간", "기간", alt.Tooltip("상한:N", title="보유 상한")])
        txt = alt.Chart(tl).transform_calculate(mid="(toDate(datum['시작']).getTime() + toDate(datum['끝']).getTime()) / 2").mark_text(
            fontSize=11, fontWeight="bold", color="#0f172a").encode(x="mid:T", y=alt.value(30), text="라벨:N")
        tdf = pd.DataFrame([{"d": today, "t": "▼ 오늘"}])
        rule = alt.Chart(tdf).mark_rule(color="#dc2626", strokeWidth=2.5).encode(x="d:T")
        rtx = alt.Chart(tdf).mark_text(color="#dc2626", fontWeight="bold", dy=-4, fontSize=12).encode(x="d:T", y=alt.value(4), text="t:N")
        st.altair_chart((bars + txt + rule + rtx).properties(height=80), use_container_width=True)
    except Exception:
        pass

    # ── 구간표 (지금 구간 표시): 휴대폰에서도 읽히게 카드 형태 ──
    _render_phase_cards(rows, cur)
    if nh == BTC_NEXT_HALVING_EST and today < nh:
        st.caption(f"④ 구간 끝(다음 반감기 {nh:%Y-%m})은 추정치입니다. 반감기는 블록 1,050,000에서 일어나며, 2027년 말쯤 블록 카운트다운 사이트에서 날짜를 확인해 "
                   "코드의 BTC_NEXT_HALVING_EST 값을 고치면 이후 날짜가 모두 맞춰집니다.")


MSTR_RULES_TBL = [  # (규칙, CAGR, MDD, 샤프, 평균 비중, 연 매매)
    ("MSTR 보유", 50.2, -89.3, 0.90, 100, 0.0),
    ("BTC 120일선 신호만", 47.8, -81.0, 0.91, 57, 4.0),
    ("BTC 120일선 + 사이클 분할 (비트코인 1순위 규칙 그대로)", 70.1, -64.9, 1.15, 41, 2.4),
    ("위 규칙 × 비중 50% 고정", 36.8, -37.1, 1.15, 21, 2.4),
    ("BTC 120일선 + 사이클 × 변동성 목표 60%", 59.0, -40.7, 1.31, 30, 11.7),
    ("MSTR 200일선 + 사이클 × 변동성 60%", 72.1, -37.9, 1.40, 38, 13.0),
    ("반반 신호 + 사이클 × 변동성 60%", 66.4, -36.7, 1.40, 34, 14.7),
    ("반반 신호 + 사이클 × 변동성 80% (권장)", 78.7, -48.3, 1.37, 40, 24.3),
    ("+ MSTR/BTC 비율 120일선 필터", 30.4, -71.3, 0.75, 29, 6.5),
    ("[참고] 비트코인 1순위 규칙 (코인)", 56.2, -28.1, 1.40, 42, 2.4),
    ("[참고] QQQ 보유", 18.5, -35.1, 0.87, 100, 0.0),
]


@st.cache_data(ttl=3600)
def get_mstr_daily_close():
    try:
        df = yf.download("MSTR", period="2y", interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        c.index = pd.to_datetime(c.index).tz_localize(None)
        return c if len(c) > 210 else None
    except Exception:
        return None


def render_mstr_alternative(btc_now=None, after_card=None):
    """📘 코인 계좌 없이 MSTR로 대신하려면~ 본문 (2026-10-20 정리: 한눈에 → 오늘 → 규칙 → 근거, 같은 내용은 한 번씩)."""
    # ── ① 한눈에 (테두리 상자로 강조) ──
    st.markdown("""
<div style="border:3px solid #f7931a;border-radius:14px;background:#fffaf3;padding:14px 18px;margin:6px 0 10px;line-height:1.75;font-size:0.98rem;color:#1e293b;">
<div style="font-weight:900;color:#9a3412;font-size:1.05rem;margin-bottom:4px;">한눈에</div>
MSTR(스트래티지)은 비트코인을 대량 보유한 미국 상장사라 <b>증권 계좌로 살 수 있는 비트코인 대용품</b>입니다.
다만 비트코인보다 1.5&#126;2배 크게 출렁이고 회사 고유의 급락(프리미엄 축소)이 있어 <b>120일선 신호만으로는 낙폭이 -81%</b>였습니다.
그래서 언제 쉬는지(반감기 사이클)와 얼마나 담는지(변동성 비중)를 함께 정합니다.
<div style="background:#ffffff;border:1px solid #fdba74;border-radius:10px;padding:10px 14px;margin-top:10px;">
<b style="color:#0f2747;">목표 비중 = (BTC 120일선 위 50% + MSTR 200일선 위 50%) × 사이클 상한 × 변동성 비중</b><br>
<span style="color:#475569;font-size:0.9rem;">MSTR을 포함한 개별투자 전체는 <b>운용자금의 10% 이내</b> (투자 원칙 선언문) · 아래 금액은 MSTR 몫 1,000만원 기준</span>
</div>
</div>
""", unsafe_allow_html=True)

    # ── ② 오늘 ──
    st.markdown("#### ⭐ <span style='border-bottom:3px solid #f7931a;padding-bottom:3px'>오늘, 이것만 보면 됩니다</span>",
                unsafe_allow_html=True)
    if after_card is not None:
        after_card()

    # ── ③ 규칙 ──
    st.markdown("#### 📋 규칙")
    st.markdown("""
| 보는 것 | 기준 | 언제 보나 |
|---|---|---|
| ① BTC 120일선 (50% 몫) | BTC 일봉 종가가 120일선 위 → 켜짐 | **매일** (한국 시간 오전 9시 일봉 마감 후) |
| ② MSTR 200일선 (50% 몫) | MSTR 종가가 200일선 위 → 켜짐 | **매일** (미국 장 마감 후) |
| ③ 반감기 사이클 상한 | 아래 구간 카드의 날짜대로 100% · 50% · 0% | 구간이 바뀌는 날 |
| ④ 변동성 비중 | **80%** ÷ MSTR 최근 20일 변동성 (최대 100%) — 변동성 160%면 50%, 100%면 80%, 80% 이하면 100% | **매주 금요일** |

| 상황 | 할 일 |
|---|---|
| ①·② 둘 다 켜짐 | 목표 = 100% × 상한 × 변동성 비중 |
| 하나만 켜짐 | 목표 = 50% × 상한 × 변동성 비중 |
| 둘 다 꺼짐 | **전량 매도**, 현금 |
| 꺼졌던 신호가 다시 켜짐 | 그 신호 몫(50%)만큼 다시 매수 |
| 금요일 변동성 점검 | 목표 비중에 맞춰 수량 조정 (차이가 10%p 이상일 때만) |
| 사이클 상한이 바뀌는 날 | 상한에 맞춰 줄이거나 늘림 |

**매매 시점 정리**
- **BTC 신호가 바뀌면 → 그날 밤 미국 장 종가에 매매합니다.** 오전 9시에 이미 확정되니 낮에 LOC 주문을 걸어 두면 됩니다.
- **MSTR 신호가 바뀌면 → 다음 미국 장 종가에 매매합니다.** 종가가 나와야 신호가 확정되므로 하루 늦을 수밖에 없습니다.
- 변동성 비중은 금요일 값으로 한 주 동안 씁니다. 신호·변동성은 위 '📡 오늘'에 매일 계산돼 있고, 직접 보려면 트레이딩뷰 MSTR 일봉에 Historical Volatility(길이 20)를 추가하면 됩니다.
""")
    st.markdown("**사이클 구간별 할 일** (비트코인과 같은 반감기 구간 · 지금 구간 강조)")
    try:
        _today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
        _rows, _cur, _ = _btc_phase_rows(_today)
        _render_phase_cards(_rows, _cur, todos=[
            "반반 신호 × 변동성 비중만큼 보유: 두 신호 모두 선 위면 100% × 변동성 비중, 하나만 위면 50% ×, 둘 다 아래면 0%",
            "위 비중의 절반까지만 보유. 보유분의 절반 매도, 신호가 꺼지면 나머지도 매도",
            "MSTR 전량 매도 후 현금 유지. 신호가 선 위여도 사지 않음",
            "반반 신호 × 변동성 비중으로 복귀: 선 위인 신호만큼 쌓인 현금으로 매수",
        ])
    except Exception:
        pass

    # ── ④ 근거 ──
    st.markdown("#### 📊 근거 — 백테스트")
    st.markdown("**백테스트 결과 — PC 계산 · 세금 미반영** (2020-08-11 \\~ 2026-10-14 · MSTR이 비트코인을 사기 시작한 날부터 · 슬리피지 0.2%)")
    _keep = ["MSTR 보유", "BTC 120일선 신호만", "반반 신호 + 사이클 × 변동성 60%", "반반 신호 + 사이클 × 변동성 80% (권장)",
             "[참고] 비트코인 1순위 규칙 (코인)", "[참고] QQQ 보유"]
    _t = pd.DataFrame([r for r in MSTR_RULES_TBL if r[0] in _keep], columns=["규칙", "CAGR %", "MDD %", "샤프", "평균 비중 %", "연 매매"])
    st.dataframe(_hl_rows(_t, fmt={"CAGR %": "{:.1f}", "MDD %": "{:.1f}", "샤프": "{:.2f}", "평균 비중 %": "{:.0f}", "연 매매": "{:.1f}"}),
                 use_container_width=True, hide_index=True)
    st.markdown("""
| 연도별 수익 (%) | 2020 (8월\\~) | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| MSTR 보유 | +214 | +40 | **-74** | +346 | +359 | **-48** | 0 |
| **권장 규칙 (반반 · 변동성 80%)** | +180 | +53 | 0 (현금) | +131 | **+241** | +7 | 0 (현금) |

주황 배경 = 지금 적용하는 규칙. 상승기(2023\\~2024)에는 비중을 줄인 만큼 덜 벌지만, 2022·2025년의 큰 하락을 거의 피했습니다.
""")
    # ── 세후 결과 (2026-10-23): 수익은 보수적으로 — 앱에서 장부 엔진으로 다시 계산 ──
    st.markdown("**세후 결과 — 앱에서 다시 계산 (보수적 기준)** · 양도세 22%(공제 없음, 한 해 이익·손실 합산, 이듬해 5월 말 납부) · "
                "슬리피지 편도 0.2% · 원화 기준(그날 환율) · 1,000만원 시작")
    try:
        with st.spinner("2020-08부터 세전·세후 장부를 계산하는 중… (처음엔 몇 초, 이후 1시간은 바로 표시)"):
            _tx = mstr_tax_backtest(0.8)
    except Exception as _e_tx:
        _tx = None
        st.caption(f"세후 결과를 계산하지 못했습니다: {_e_tx}")
    if _tx is not None:
        _tt, _ty, _tend = _tx
        _tt = _tt.copy()
        _tt["규칙"] = _tt["규칙"].str.replace("권장 규칙 (반반 · 변동성 80%) · 세후", "권장 규칙 (반반 · 변동성 80%) · 세후 (권장)", regex=False)
        st.dataframe(_hl_rows(_tt, fmt={"CAGR %": "{:.1f}", "MDD %": "{:.1f}", "샤프": "{:.2f}",
                                        "최종 금액 (1,000만원 시작)": lambda v: fmt_krw(v), "낸 세금": lambda v: "-" if not v else fmt_krw(v)}),
                     use_container_width=True, hide_index=True)
        _ty = _ty.copy()
        _ty.columns = [f"{c} (8월~)" if c == 2020 else (f"{c} (~{_tend[5:7]}월)" if str(c) == _tend[:4] else str(c)) for c in _ty.columns]
        st.markdown("**연도별 수익 (%) — 세전 vs 세후**")
        st.dataframe(_ty.style.format("{:+.0f}", na_rep="-"), use_container_width=True)
        try:
            _pre = float(_tt.loc[_tt["규칙"].str.contains("권장") & _tt["규칙"].str.contains("세전"), "CAGR %"].iloc[0])
            _aft = float(_tt.loc[_tt["규칙"].str.contains("권장") & _tt["규칙"].str.contains("세후"), "CAGR %"].iloc[0])
            _gap = f"세금으로 연 수익률이 약 {_pre - _aft:.0f}%p 낮아집니다. "
        except Exception:
            _gap = ""
        with st.expander("📖 세후 결과 읽는 법", expanded=False):
            st.markdown(f"""
- **계산 방식**: 위 장부와 같은 엔진으로 2020-08-11부터 {_tend}까지 다시 계산했습니다. 팔아서 생긴 이익은 한 해 동안 손실과 합산하고, 남은 이익의 22%를 이듬해 5월 말에 냅니다. 낼 세금만큼은 현금으로 남겨 두고 비중을 정하며, 현금이 모자라면 주식을 팔아서 냅니다.
- **공제 없음**: 해외주식 공제 250만원은 사람당 1번뿐이라 2026 혼합전략이 이미 쓴다고 보고, MSTR 몫은 0원으로 잡았습니다(가장 보수적).
- **세후 = 오늘 판다면**: 마지막 날 가진 주식을 모두 팔고 그 세금까지 낸 금액입니다. 그냥 보유도 같은 기준이라, 중간에 팔지 않아 세금이 미뤄지는 효과(그냥 보유가 유리한 점)가 끝에 한 번에 반영됩니다.
- {_gap}규칙은 1년에 15\\~25번 사고팔아 이익이 생길 때마다 세금을 내므로, 세금이 쌓이지 않는 그냥 보유보다 세금 영향이 큽니다.
- **원화 기준**이라 환율 변동이 수익에 들어가고, PC 계산(달러 · 세전)과 숫자가 조금 다릅니다. 환전 비용은 빠져 있습니다.
- 앞으로의 계획에는 **세후 숫자**를 기준으로 삼으세요. 과거 성과가 미래 수익을 보장하지 않습니다.
""")
    with st.expander("📖 읽는 법 — 왜 반반 신호인가 · 왜 변동성 80%인가 · 효과 없던 규칙 · 한계", expanded=False):
        st.markdown("""
#### 1. 왜 'MSTR 200일선' 단독이 아니라 '반반 신호'인가
숫자는 MSTR 200일선 단독이 조금 좋았지만, **그 우위가 한 해(2024년)와 한 숫자(200일)에 기대고 있어서** 믿기 어려웠습니다. (사이클 × 변동성 60% 기준 비교)

| 신호 | CAGR · MDD · 샤프 | 2021 | 2024 | 2025 |
|---|---|---|---|---|
| BTC 120일선만 | 59.0% · -40.7% · 1.31 | +31% | +129% | -12% |
| MSTR 200일선만 | 72.1% · -37.9% · 1.40 | +51% | **+257%** | -8% |
| **반반** | 66.4% · **-36.7%** · 1.40 | +41% | +190% | -9% |
| 둘 다 위일 때만 | 52.4% · -42.6% · 1.22 | | | |
| 하나라도 위면 | 79.5% · -37.9% · 1.47 | | | |

- **우위가 2024년 한 해에서 나옴**: 그해 여름 BTC가 120일선 근처에서 휩소로 빠져나온 사이, MSTR은 200일선 위에 머물러 연말 급등을 탔습니다.
- **이평선 길이에 민감**: MSTR 단독은 150일선이면 샤프 1.12 · MDD -53%로 크게 나빠졌고, 반반은 180·200·250일에서 1.35\\~1.40으로 안정적이었습니다(150일 1.24).
- **두 신호가 다른 위험을 잡음**: BTC 120일선은 비트코인 시장 전체, MSTR 200일선은 2025년처럼 BTC -6%인데 MSTR -48%였던 **프리미엄 축소**. 한쪽이 틀려도 절반만 영향을 받습니다.
- '하나라도 위면'은 숫자가 가장 좋았지만 조합을 고르다 나온 최고값이라 **사후 맞춤 위험**이 커 택하지 않았습니다.

#### 2. 왜 변동성 목표 80%인가 (2026-10-16 결정)

| 목표 | CAGR | MDD | 샤프 |
|---|---|---|---|
| 40% | 46.4% | -27.9% | 1.39 |
| 60% | 66.4% | -36.7% | 1.40 |
| **80% (권장)** | **76.2%** | **-46.1%** | **1.35** |
| 100% | 82.4% | -52.7% | 1.32 |

- 60%는 2024년 11월 같은 급등 구간에서 금요일마다 비중을 줄여 상승을 절반만 받았습니다. 2022-11부터 같은 금액 장부로 비교하면 80%가 약 1.45배 많았고 MDD는 -38% → -41%로 비슷했습니다.
- MSTR은 개별투자 10% 칸 안의 위성이라, 80%의 최악 낙폭(-48%)도 전체 계좌로는 약 -4.8%입니다.
- (이 표는 MSTR 신호를 같은 날 종가에 매매한 계산 · 실제로 가능한 '다음 날 종가'로 하면 80%는 78.7% · -48.3% · 샤프 1.37로 거의 같음)

#### 3. 효과가 없던 규칙
- **오를 때는 줄이지 않기**(20일선 위면 금요일 축소 생략): 수익은 늘었지만 MDD -53% · 샤프 1.33으로 80%보다 비효율적
- **MSTR/BTC 가격 비율 필터**(프리미엄이 커지는지): 수익 30%대로 줄고 낙폭은 오히려 커짐
- **사이클 없이 변동성 비중만**: 낙폭 -63% · **변동성 비중 없이 신호 × 사이클만**: 79.3% · -61.9%

#### 4. 한계
- 표본은 약 6년(사이클 1.5번)뿐입니다. 2021년 2월처럼 신호가 반응하기 전에 빠지는 MSTR 고유의 급락은 다시 올 수 있습니다.
- 미국 주식이라 양도세 22%(연 250만원 공제) 대상이고, 금요일 비중 조정까지 연 15\\~25회 매매가 생깁니다.
- 국내 증권사의 미국 비트코인 현물 ETF 매매는 2024년부터 막혀 있고, 국내 현물 ETF 도입 법 개정안은 2026-09 기준 국회 심사 중입니다. 국내 현물 ETF가 상장되면 비트코인 1순위 규칙을 그 ETF에 쓰는 편이 MSTR보다 낫습니다(같은 규칙 MDD -28%).
- PC 스크립트: `mstr_rules_backtest.py`. 과거 성과가 미래 수익을 보장하지 않습니다.
""")


NDX_GUIDE_MD = """
**이 화면은 이렇게 보세요 (3단계)**

1. **시장 폭**으로 장의 성격을 봅니다 — 넓게 오르는 장인지, 소수 종목만 끌고 가는 장인지.
2. **상위 20 업종 분포**로 지금 돈이 몰린 업종을 봅니다 — 한 업종이 6개 이상이면 그 업종이 시장을 이끄는 중입니다. 같은 흐름을 '미국 ETF 탭 → 🧭 섹터·테마 현황'에서 ETF로 확인하세요.
3. 종목별 **상태 태그**로 주도가 이어지는지(🟢), 식어가는지(🟡)를 봅니다.

| 항목 | 뜻 | 읽는 법 |
|---|---|---|
| 시가총액 · 시총 순위 · 시총 비중 | 주가 × 발행주식 수(달러, $B = 10억 달러). 비중은 나스닥100 전체 시총 합에서 차지하는 몫 | 정렬을 '시가총액'으로 바꾸면 지수를 실제로 움직이는 대형주 순서가 보입니다. 큰 종목이 🟡 추세 둔화로 바뀌면 지수 전체에 부담이 됩니다. 실제 지수 비중은 상한 조정이 있어 이 값과 조금 다릅니다 |
| 종합 모멘텀 스코어 | 1·3·6·12개월 수익률의 평균 | 높을수록 지난 1년간 꾸준히 강했던 종목. 이미 많이 오른 종목일수록 높게 나옵니다 |
| 52주 고점 대비 | 현재가가 최근 1년 최고가에서 몇 % 아래인지 | **0 \\~ -10%**: 신고가 근처, 주도권 유지 · **-10 \\~ -25%**: 조정 중 · **-25% 이하**: 소외·약세 |
| QQQ 대비 3M | 3개월 수익률 − QQQ 3개월 수익률 (%p) | **+**면 지수보다 강함, **+10%p 이상**이면 뚜렷한 주도, **−**면 지수보다 약함 |
| 200일선 / 시장 폭 | 주가가 200일 평균 위인지, 나스닥100 중 200일선 위 종목 비율 | 200일선 위 = 장기 상승 추세. 시장 폭 **70% 이상**: 고른 강세 · **40\\~70%**: 보통 · **40% 미만**: 소수 종목 장세(지수가 올라도 체력 약함) |
| 변동성 | 최근 3개월 일간 등락의 연환산 크기 | **30% 이하**: 비교적 안정 · **30\\~50%**: 보통 · **50% 이상**: 급등락이 큰 종목 |
| 안정 모멘텀 | 종합 스코어 ÷ 변동성 | 흔들림 대비 얼마나 올랐는지. **1 이상**이면 출렁임보다 상승이 큼. 같은 스코어면 안정 모멘텀이 높은 쪽이 더 꾸준히 오른 것 |
| 거래대금 배수 | 최근 20일 평균 거래대금 ÷ 최근 120일 평균 | **1.3배 이상**: 평소보다 돈이 많이 오감(관심 집중) · **0.8배 이하**: 관심 감소. 하락하면서 늘면 매도세일 수 있으니 수익률과 함께 보세요 |

**상태 태그**

| 태그 | 조건 | 뜻 |
|---|---|---|
| 🟢 주도 | 200일선 위 · 52주 고점 -10% 이내 · 1개월 상승 | 상승 추세가 살아 있고 지금도 강한 종목 |
| 🟡 추세 둔화 | 200일선 위지만 고점에서 10% 넘게 빠졌거나 1개월 하락 | 장기 추세는 남아 있으나 힘이 빠지는 중 |
| 🔵 200일선 아래 반등 | 200일선 아래 · 1개월 상승 | 하락 추세 속 반등. 추세 전환인지는 아직 모름 |
| 🔴 200일선 아래 하락 | 200일선 아래 · 1개월 하락 | 하락 추세가 이어지는 중 |

**보유 기준 (매매 판단용, 백테스트 검증)**

| 표시 | 조건 | 뜻 |
|---|---|---|
| 🟢 보유·매수 가능 | 200일선 +5% 위 | 계속 보유. 새로 사거나 다시 사도 되는 구간 |
| 🟢 보유 (재매수 대기) | 200일선 위, +5% 이내 | 가진 종목은 계속 보유. 팔았던 종목·새 종목은 +5% 위로 올라올 때까지 기다림 |
| 🟡 경계 | 200일선 아래 3% 이내 | 아직 매도 아님. 월말 종가 확인 |
| 🔴 매도 기준 | 200일선보다 3% 넘게 아래 | 월말 종가도 이 아래면 매도. 다시 사는 건 월말 종가가 200일선 +5% 위로 올라온 뒤 |

재매수를 +5%로 잡은 이유: S&P500 2006\\~ 백테스트에서 200일선을 막 넘었을 때(+0%) 사면 3개월 안에 다시 손절되는 비율이 30%였지만, +5%에서는 19%로 줄고 거래당 중앙 수익이 플러스로 돌아섰습니다.

상태 태그는 시장·업종 흐름을 읽는 참고용이고, 실제로 들고 갈지 팔지는 **보유 기준**으로 판단합니다. 예를 들어 🔵 200일선 아래 반등은 최근 한 달은 올랐어도 보유 기준으로는 🟡 경계나 🔴 매도 기준입니다. 이 규칙은 나스닥100 2015\\~ 백테스트에서 매수 후 보유보다 수익은 낮지만(18% vs 27%) 낙폭을 크게 줄이고(-20% vs -31%) 위험 대비 효율(샤프)이 가장 높았던 기준입니다.

⚠️ **매수 신호가 아닙니다.** 시장과 업종 흐름을 읽기 위한 참고 화면입니다. '신고가 근처 + 거래대금 증가' 종목을 사는 개별주 전략(EMB)은 2015\\~2026 백테스트에서 CAGR 2\\~4%로 QQQ(19%)에 크게 못 미쳐 폐기했습니다. 실제 투자 판단은 2026 혼합전략의 규칙을 따르세요.
"""


# ===================== 🏠 홈 카드 (2026-10-22) — 탭 위: 오늘 볼 것 3장 + 메뉴 안내 =====================
# 마음에 안 들면 SHOW_HOME = False 로 바꾸면 예전 화면(탭만)으로 돌아감
SHOW_HOME = True

HOME_MENU = [  # (그룹, 색, [(탭 이름, 한 줄 설명)])
    ("🏆 전략 운용", "#1e3a8a", [
        ("🏆 2026 혼합전략", "전략 A·B·C를 1/3씩 합친 메인 전략 · 이번 달 비중 · 목표 수량 계산기 · 백테스트"),
        ("🛡️ 전략 A · ⚡ B · 🔄 C", "세 전략 각각의 카나리아 신호 · 공격/방어 · 백테스트"),
        ("🪙 MSTR", "코인 계좌 없이 비트코인 흐름에 투자 · 오늘의 신호 · 실시간 장부(개별투자 10% 칸)"),
    ]),
    ("🌍 시장 보기", "#0f766e", [
        ("미국 ETF", "전략 자산 랭킹 · 섹터·테마 · 🩺 시장위험진단 · 위험 신호판 · 밸류에이션"),
        ("🏢 미국 주식", "🔎 종목 찾기 · 나스닥100·S&P500 랭킹 · 보유 기준 · QQQ·비트코인 장기 보유 가이드"),
        ("📉 MDD", "SPY·QQQ 30년 장기 낙폭 — 큰 하락이 얼마나 깊고 길었나 (경각심용)"),
    ]),
    ("🧮 계산 · 📚 자료", "#7c3aed", [
        ("🧮 계산기", "전략별 실측 수익률로 미래 자산 계산"),
        ("📚 자료실", "투자 공부 슬라이드 · 맨 아래 🔧 관리자 모드(나만)"),
    ]),
]


def _home_next_rebalance(today):
    """다음 월말 리밸런싱일(그달 마지막 평일)과 남은 거래일 수 (미국 휴일은 따지지 않은 대략값)."""
    me = (today + pd.offsets.BMonthEnd(0)).normalize()
    left = len(pd.bdate_range(today, me)) - 1
    return me, left


def render_home(combined_alloc, is_attack_a, is_attack_b, is_attack_c, capital=10_000_000):
    """🏠 홈: ① 2026 혼합전략 오늘 신호 ② 다음 월말 리밸런싱 ③ MSTR 사이클 + 🧭 메뉴 안내(접기/펼치기).
    시세를 새로 받지 않음 — 이미 계산한 값과 날짜만 씀."""
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    _kd = lambda d: f"{d.month}월 {d.day}일"
    _wd = "월화수목금토일"
    _sig = lambda on: ("<b style='color:#15803d'>🟢 공격</b>" if on else "<b style='color:#dc2626'>🔴 방어</b>")

    # ① 혼합전략: 오늘 신호로 다시 계산한 비중 상위 3개 (원화는 1,000만원 기준)
    _top = sorted([(t, w) for t, w in combined_alloc.items() if w > 0.01], key=lambda x: -x[1])[:3]
    _rows = "".join(
        f"<div style='display:flex;justify-content:space-between;gap:8px'><span>{_html.escape(t)}"
        f"<span style='color:#64748b;font-size:0.8rem'> {_html.escape(TICKER_INFO.get(t, ('',))[0])}</span></span>"
        f"<span><b>{w:.1f}%</b> <span style='color:#64748b'>· {capital * w / 100 / 1e4:,.0f}만원</span></span></div>" for t, w in _top)
    c1 = (f"<div style='font-size:0.86rem;margin-bottom:6px'>A {_sig(is_attack_a)} · B {_sig(is_attack_b)} · C {_sig(is_attack_c)}</div>"
          f"<div style='font-size:0.86rem;line-height:1.7'>{_rows}</div>"
          "<div style='font-size:0.76rem;color:#64748b;margin-top:6px'>오늘 신호로 다시 계산한 비중(1,000만원 기준) · 월말 전까지는 지난 월말 포트폴리오를 그대로 들고 감</div>")

    # ② 다음 월말 리밸런싱
    me, left = _home_next_rebalance(today)
    if left <= 0:
        _big, _sub = "오늘", "미국 장 마감 무렵 혼합전략 리밸런싱 · 2026 혼합전략 탭의 목표 수량 계산기로 수량 확인"
    else:
        _big = f"{left}거래일 남음"
        _sub = (f"{_kd(me)}({_wd[me.weekday()]}) 미국 장 종가 기준 · 그날 목표 수량 계산기로 전체 리밸런싱"
                + (" · 이번 주 안에 목돈이 생기면 월말에 함께 넣기" if left <= 5 else ""))
    c2 = (f"<div style='font-size:1.45rem;font-weight:900;color:#0f2747;margin:2px 0'>{_big}</div>"
          f"<div style='font-size:0.86rem;color:#334155;line-height:1.6'>{_sub}</div>"
          "<div style='font-size:0.76rem;color:#64748b;margin-top:6px'>미국 휴일은 따지지 않은 대략값</div>")

    # ③ MSTR: 사이클 상한 (시세 없이 날짜로만) + 금요일 알림
    try:
        _rows_c, _cur_c, _ = _btc_phase_rows(today)
        _ph = _rows_c[_cur_c]
        _h, _mo, _cap, (_nd, _nl) = _btc_cycle_state(today)
        c3 = (f"<div style='font-size:1.45rem;font-weight:900;color:#0f2747;margin:2px 0'>상한 {_cap}%</div>"
              f"<div style='font-size:0.86rem;color:#334155;line-height:1.6'>{_ph[0]} 구간<br>다음 변경 {_nd.year}년 {_nd.month}월경 — {_nl.split(' (')[0]}"
              + ("<br><b style='color:#9a3412'>오늘 밤 금요일 장 → 변동성 비중 점검(차이 10%p 이상이면 조정)</b>" if today.weekday() == 4 else "")
              + "</div><div style='font-size:0.76rem;color:#64748b;margin-top:6px'>오늘 신호·할 일·LOC 지정가는 🪙 MSTR 탭 → 📡 오늘의 신호</div>")
    except Exception:
        c3 = "<div style='font-size:0.86rem;color:#64748b'>사이클 정보를 계산하지 못했습니다. 🪙 MSTR 탭에서 확인하세요.</div>"

    def _card(title, body, col):
        return (f"<div style='flex:1 1 230px;min-width:230px;background:#fff;border:1px solid #e2e8f0;border-top:4px solid {col};"
                f"border-radius:12px;padding:12px 14px'><div style='font-weight:800;color:#0f2747;font-size:0.95rem;margin-bottom:4px'>{title}</div>{body}</div>")
    st.markdown(
        "<div class='print-hide' style='margin:4px 0 6px'>"
        f"<div style='font-size:0.82rem;color:#64748b;margin-bottom:6px'>🏠 오늘 볼 것 · {today.year}년 {_kd(today)}({_wd[today.weekday()]})</div>"
        "<div style='display:flex;flex-wrap:wrap;gap:10px'>"
        + _card("🏆 2026 혼합전략 · 오늘 신호", c1, "#1e3a8a")
        + _card("🗓️ 다음 월말 리밸런싱", c2, "#0f766e")
        + _card("🪙 MSTR · 반감기 사이클", c3, "#f7931a")
        + "</div></div>", unsafe_allow_html=True)

    # 🧭 메뉴 안내 (기본 접기) — 제목은 소제목(####) 모양, 위아래 여백은 탭 제목(st.header) 위 여백과 같게
    st.markdown("<div class='print-hide' style='padding-top:2.2rem;font-size:1.25rem;font-weight:700;color:rgb(49,51,63);line-height:1.4'>"
                "🧭 메뉴 안내 — 어느 탭에서 무엇을 보나</div>", unsafe_allow_html=True)
    _menu_open = st.radio("메뉴 안내", ["접기", "펼치기"], index=0, horizontal=True, key="home_menu_r",
                          label_visibility="collapsed") == "펼치기"
    if _menu_open:
        _g = []
        for grp, col, items in HOME_MENU:
            _it = "".join(f"<div style='padding:6px 0;border-top:1px solid #f1f5f9'><div style='font-weight:700;color:#0f172a;font-size:0.9rem'>{_html.escape(n)}</div>"
                          f"<div style='font-size:0.8rem;color:#475569;line-height:1.5'>{_html.escape(d)}</div></div>" for n, d in items)
            _g.append(f"<div style='flex:1 1 230px;min-width:230px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:10px 14px'>"
                      f"<div style='font-weight:800;color:{col};font-size:0.95rem;margin-bottom:4px'>{grp}</div>{_it}</div>")
        st.markdown("<div class='print-hide' style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:6px'>" + "".join(_g) + "</div>",
                    unsafe_allow_html=True)
        st.caption("탭은 바로 아래 줄에 있습니다. 왼쪽 파란 묶음(STRATEGY)은 매매 규칙, 오른쪽 초록 묶음(INSIGHTS)은 시장을 읽는 참고 화면입니다.")
    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)    # 탭 줄과의 간격 (위 칸 사이 기본 간격 1rem × 2와 합쳐 MSTR 제목 위 여백과 비슷하게)


def render_gl_table(df):
    """지표 표: 첫 열(지표명)의 용어에 설명을 붙인 HTML 표 (스크롤 없이 전체 표시)."""
    head = "".join(f"<th>{_html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, row in df.iterrows():
        cells = ""
        for j, c in enumerate(df.columns):
            sv = str(row[c])
            if j == 0:
                cells += f'<td class="l">{glossify(_html.escape(sv))}</td>'
            else:
                neg = sv.startswith("-") and len(sv) > 1 and sv[1].isdigit()
                cells += f'<td class="{"neg" if neg else ""}">{_html.escape(sv)}</td>'
        body += f"<tr>{cells}</tr>"
    st.markdown(f'{_TBL_CSS}<table class="dtbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)


_TBL_CSS = (
    "<style>"
    ".dtbl{width:100%;border-collapse:collapse;font-size:0.85rem;margin:0.3rem 0 0.6rem}"
    ".dtbl th{background:#e2e8f0;color:#334155;padding:7px 5px;text-align:center;border:1px solid #cbd5e1;word-break:keep-all}"
    ".dtbl td{padding:6px 5px;text-align:right;border:1px solid #e2e8f0;white-space:nowrap}"
    ".dtbl td.l{text-align:left}"
    ".dtbl td.t{text-align:left;white-space:normal;word-break:keep-all;overflow-wrap:anywhere}"
    ".dtbl tr:nth-child(even) td{background:#f8fafc}"
    ".dtbl td.neg{color:#dc2626}"
    ".dtbl .tk{border-bottom:1px dotted #64748b;cursor:help;font-weight:600}"
    ".dtbl .tk-name{color:#64748b;font-size:0.82em;margin-left:2px;white-space:normal;word-break:keep-all}"
    "@media (max-width:640px){.dtbl{font-size:0.62rem}.dtbl th,.dtbl td{padding:4px 2px}}"
    "</style>"
)


def render_html_table(df, ticker_cols=(), text_cols=(), scroll_x=False):
    """DataFrame을 스크롤 없이 전체가 보이는 HTML 표로 표시. 티커 열은 한글명+마우스 오버 설명을 붙입니다."""
    head = "".join(f"<th>{_html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, row in df.iterrows():
        cells = ""
        for c in df.columns:
            v = row[c]
            if c in ticker_cols:
                cells += f'<td class="l">{ticker_cell_html(v)}</td>'
            elif c in text_cols:
                cells += f'<td class="t">{_html.escape(str(v))}</td>'
            elif isinstance(v, float):
                d = 2 if any(k in str(c) for k in ("스코어", "모멘텀", "현재가", "비중", "배수")) else 1
                cells += f'<td class="{"neg" if v < 0 else ""}">{v:,.{d}f}</td>'
            else:
                sv = str(v)
                neg = sv.startswith("-") and len(sv) > 1 and sv[1].isdigit()
                cells += f'<td class="{"neg" if neg else ""}">{_html.escape(sv)}</td>'
        body += f"<tr>{cells}</tr>"
    _tbl = f'<table class="dtbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    if scroll_x:  # 좁은 상자 안에서 표가 테두리를 넘지 않도록 가로 스크롤
        _tbl = f'<div style="overflow-x:auto;max-width:100%">{_tbl}</div>'
    st.markdown(f'{_TBL_CSS}{_tbl}', unsafe_allow_html=True)


def apply_weight_cap(alloc, cap):
    """단일 티커(현금 제외) 비중이 cap(%)을 넘으면 cap으로 줄이고 초과분을 현금으로 돌립니다.
    반환: (상한 적용 후 비중 dict, {티커: (원래 비중, 상한 후 비중)}, 현금으로 이동한 합계 %p)"""
    capped, hit, excess = {}, {}, 0.0
    for t, w in alloc.items():
        if t != "CASH (현금)" and w > cap:
            capped[t] = cap
            hit[t] = (w, cap)
            excess += w - cap
        else:
            capped[t] = w
    if excess > 0:
        capped["CASH (현금)"] = capped.get("CASH (현금)", 0.0) + excess
    return capped, hit, excess


def render_alloc_table(df):
    """비중 분배 현황: 자산마다 2줄(수치 줄 + 참여 전략·선택 기준 줄)로 폰에서도 한눈에 보이는 표."""
    num_cols = ["자산군", "현재가 ($)", "배분 비중 (%)", "1M", "3M", "6M", "12M"]
    head = "".join(f"<th>{_html.escape(c)}</th>" for c in num_cols)
    body = ""
    for _, r in df.iterrows():
        cells = f'<td class="l">{ticker_cell_html(r["자산군"])}</td>'
        cells += f'<td>{_html.escape(str(r["현재가 ($)"]))}</td>'
        cells += f'<td class="wt">{float(r["배분 비중 (%)"]):,.2f}%</td>'
        for c in ("1M", "3M", "6M", "12M"):
            sv = str(r[c])
            neg = sv.startswith("-") and len(sv) > 1 and sv[1].isdigit()
            cells += f'<td class="{"neg" if neg else ""}">{_html.escape(sv)}</td>'
        detail = (
            f'<b>참여 전략</b> {_html.escape(str(r["참여 전략 (신호)"]))}<br>'
            f'<b>선택 기준·값</b> {_html.escape(str(r["선택 기준 · 값"]))}'
        )
        body += f'<tr class="main">{cells}</tr><tr class="detail"><td colspan="{len(num_cols)}" class="t">{detail}</td></tr>'
    st.markdown(
        _TBL_CSS
        + "<style>.dtbl td.wt{background:#fefce8 !important;font-size:1.08em;font-weight:700;color:#0f172a}"
        + ".dtbl td.l .tk{font-size:1.08em;color:#0f172a}.dtbl td.l .tk-name{display:block;margin-left:0}"
        + ".dtbl tr.detail td{background:#f1f5f9;color:#334155;font-size:0.92em;line-height:1.45}"
        + ".dtbl tr.main td{border-bottom:none}.dtbl tr.detail td{border-top:none}</style>"
        + f'<table class="dtbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>',
        unsafe_allow_html=True,
    )


def render_monthly_return_table(heat_df, year_order, month_order, key):
    """월별 수익률을 휴대폰에서 크게 볼 수 있는 HTML 표로 (그래프와 같은 색, 좌우로 밀어 보기)."""
    if not tab_toggle("📱 크게 보기 (표)", key=f"mret_tbl_{key}_r"):
        return
    def _bg(v):
        if pd.isna(v):
            return "#ffffff"
        cuts = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        cols = ["#cf6265", "#e67f82", "#ecaaab", "#f6d4d5", "#fafbff", "#d7e4da", "#accab2", "#82ae8b", "#599265"]
        i = sum(1 for c in cuts if v >= c)
        return cols[i]
    piv = heat_df.pivot_table(index="year_label", columns="month_label", values="monthly_return", aggfunc="first")
    piv = piv.reindex(index=[y for y in year_order if y in piv.index], columns=[m for m in month_order if m in piv.columns])
    th = "padding:6px 8px;background:#0f2747;color:#fff;font-weight:700;position:sticky;top:0;"
    h = ["<div style='overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid #e2e8f0;border-radius:10px;'>",
         "<table style='border-collapse:collapse;font-size:15px;font-variant-numeric:tabular-nums;min-width:640px;width:100%;'>",
         f"<tr><th style='{th}left:0;z-index:2;'>연도</th>" + "".join(f"<th style='{th}'>{m}</th>" for m in piv.columns) + "</tr>"]
    for y, row in piv.iterrows():
        _bold = "font-weight:800;" if y == "평균" else ""
        h.append(f"<tr><td style='padding:6px 8px;background:#f1f5f9;font-weight:700;position:sticky;left:0;{_bold}'>{y}</td>"
                 + "".join(f"<td style='padding:6px 6px;text-align:right;background:{_bg(v)};color:#1e293b;font-weight:700;"
                           f"border:1px solid #fff;{_bold}'>{'' if pd.isna(v) else f'{v:+.1f}'}</td>" for v in row.values)
                 + "</tr>")
    h.append("</table></div>")
    st.markdown("".join(h), unsafe_allow_html=True)
    st.caption("표는 좌우로 밀어 볼 수 있습니다. 색 기준은 위 그래프와 같습니다.")


def render_drawdown_with_benchmark(chart_df, strategy_name):
    """낙폭 히스토리: 전략(진한 빨강) 위에 벤치마크 QQQ(연한 회색)를 겹쳐 표시."""
    import altair as alt
    dd_df = pd.DataFrame({
        "date_str": chart_df["date_str"].values,
        strategy_name: chart_df["drawdown"].values,
    })
    if "qqq_nav" in chart_df.columns:
        q_nav = pd.Series(chart_df["qqq_nav"].values, dtype=float)
        dd_df["QQQ"] = ((q_nav / q_nav.cummax() - 1.0) * 100.0).values
    # 표시 구간 선택 (슬라이더로 원하는 기간만 확대해서 보기)
    _all_dates = dd_df["date_str"].tolist()
    if len(_all_dates) > 2:
        _lo, _hi = st.select_slider(
            "🔍 표시 구간 (양쪽 손잡이를 움직이면 해당 기간만 확대됩니다)",
            options=_all_dates, value=(_all_dates[0], _all_dates[-1]),
            key=f"dd_zoom_{strategy_name}_{_all_dates[0]}_{_all_dates[-1]}_{len(_all_dates)}",  # 기간(시작일·안전장치 등)이 바뀌면 새 슬라이더로 초기화
        )
        _i0, _i1 = _all_dates.index(_lo), _all_dates.index(_hi)
        dd_df = dd_df.iloc[_i0:_i1 + 1].reset_index(drop=True)
    long_df = dd_df.melt(id_vars="date_str", var_name="series", value_name="drawdown")
    long_df["drawdown"] = long_df["drawdown"].round(2)

    domain = [strategy_name, "QQQ"]
    color_scale = alt.Scale(domain=domain, range=["#dc2626", "#9ca3af"])
    x_enc = alt.X("date_str:N", sort=None, title="년-월", axis=alt.Axis(labelOverlap=True))
    # 세로축 눈금을 5%p 간격(0, -5, -10, -15 ...)으로 촘촘하게 표시
    _dd_min = float(long_df["drawdown"].min()) if len(long_df) else 0.0
    _dd_lo = int(np.floor(_dd_min / 5.0) * 5)
    _dd_ticks = list(range(0, _dd_lo - 1, -5)) if _dd_lo < 0 else [0, -5]

    # 주요 이슈(장기 낙폭 탭과 같은 목록)의 저점 시기를 SPY 기준으로 찾아 표시 구간 안의 것만 사용
    ev_marks = []
    _vis = dd_df["date_str"].tolist()
    try:
        _hist = get_long_history(("SPY", "QQQ"), "1996-01-01")  # 장기 낙폭 탭과 같은 캐시를 재사용
        if "SPY" in _hist:
            for _short, _full, _a, _b in LONG_EVENTS:
                _es = event_stats(_hist["SPY"], _a, _b)
                if _es:
                    _m = f"{_es['trough']:%Y-%m}"
                    if _m in _vis:
                        ev_marks.append({"date_str": _m, "label": _short})
    except Exception:
        ev_marks = []
    _lo_dom = float(min(_dd_lo, -5))
    _hi_dom = max(8.0, abs(_lo_dom) * 0.3) if ev_marks else 0.0  # 0% 위쪽 흰 띠: 이슈 이름 자리
    _yscale = alt.Scale(domain=[_lo_dom, _hi_dom], nice=False)
    y_enc = alt.Y("drawdown:Q", title="MDD (%)", scale=_yscale, axis=alt.Axis(values=_dd_ticks))
    tip = [alt.Tooltip("date_str:N", title="년-월"), alt.Tooltip("series:N", title="구분"),
           alt.Tooltip("drawdown:Q", title="낙폭 (%)", format=".2f")]
    color_enc = alt.Color("series:N", scale=color_scale, sort=domain,
                          legend=alt.Legend(orient="top", title=None))

    # 뒤: QQQ 연한 회색 / 앞: 전략 진한 빨강 (면 + 테두리선)
    qqq_layer = alt.Chart(long_df[long_df["series"] == "QQQ"]).mark_area(
        opacity=0.35, line={"color": "#9ca3af", "strokeWidth": 1}
    ).encode(x=x_enc, y=y_enc, color=color_enc, tooltip=tip)
    strat_layer = alt.Chart(long_df[long_df["series"] == strategy_name]).mark_area(
        opacity=0.6, line={"color": "#991b1b", "strokeWidth": 1.5}
    ).encode(x=x_enc, y=y_enc, color=color_enc, tooltip=tip)

    layers = [qqq_layer, strat_layer]
    if ev_marks:
        ev_df = pd.DataFrame(ev_marks)
        _rows_y = [_hi_dom * 0.85, _hi_dom * 0.55, _hi_dom * 0.25]  # 이웃한 이슈가 겹치지 않게 3단 배치
        _pos = {m: i for i, m in enumerate(_vis)}
        ev_df["ypos"] = [_rows_y[k % 3] for k in range(len(ev_df))]
        ev_df["y0"] = _lo_dom
        ev_df["right"] = [_pos[m] >= 0.88 * len(_vis) for m in ev_df["date_str"]]  # 오른쪽 끝은 글자를 왼쪽으로
        layers.append(alt.Chart(ev_df).mark_rule(color="#94a3b8", strokeDash=[3, 3]).encode(
            x=alt.X("date_str:N", sort=None), y=alt.Y("y0:Q", scale=_yscale, title=None), y2="ypos:Q"))
        for _right in (False, True):
            _sub = ev_df[ev_df["right"] == _right]
            if len(_sub):
                layers.append(alt.Chart(_sub).mark_text(
                    align="right" if _right else "left", dx=-4 if _right else 4, baseline="middle",
                    fontSize=11, fontWeight="bold", color="#1e293b").encode(
                    x=alt.X("date_str:N", sort=None), y=alt.Y("ypos:Q", scale=_yscale, title=None), text="label:N"))
    st.altair_chart(alt.layer(*layers).properties(height=350), use_container_width=True)

    if "QQQ" in dd_df.columns:
        st.caption(
            f"빨강 = {strategy_name} (선택 구간 MDD {dd_df[strategy_name].min():.2f}%), "
            f"연회색 = 벤치마크 QQQ (선택 구간 MDD {dd_df['QQQ'].min():.2f}%)"
            + (" · 위쪽 이름과 점선 = 주요 이슈의 저점 시기(SPY 기준)" if ev_marks else "")
        )


def render_strategy_report():
    """혼합전략 탭 최하단: 종합평가서 + 개선 작업 보고서 (문제 -> 개선안 -> 백테스트 -> 판정 -> 최종 결과 -> 지적 대응)."""
    st.markdown("## 📑 전략 종합평가 및 개선 작업 보고서")
    st.caption("2026-10-22 갱신 · ⓪은 최신 설정·결과(2026-10-11 값), ⓪-1·⓪-2는 2026-10-05 추가 검증, ⓪-3은 2026-10-09\\~11 자료실, ⓪-4는 2026-10-12\\~14 미국 주식 랭킹·보유 기준·밸류에이션·자료실 올리기, ⓪-5는 2026-10-14\\~20 시장위험진단·관리자 모드·위성 전략(MSTR·S&P500 재돌파), ①\\~⑥은 2026-10-01 시점 검증 기록(야후 원본 데이터 2014-01 \\~ 2026-09, 비용·세금 미반영, 시작일 2015/2018/2020 교차 확인, 표는 2018\\~ 기준)")
    st.info(
        "**한 줄 결론** — 종합평가서가 지적한 개선안(전략 C Z-Score, 전략 B 평활화·변동성 타깃팅, VIX 레버리지 축소 등)을 "
        "모두 실제 데이터로 백테스트해 봤고, **기존 전략보다 성과를 개선한 항목은 없었습니다.** "
        "그래서 전략 로직은 기존 그대로 유지하고, 큰 폭락 대비용 안전장치는 비중 상한만 선택형으로 남겼습니다. (월중 하드스탑은 이후 효과가 뚜렷하지 않아 2026-10-04에 제거했습니다. 아래 하드스탑 관련 수치는 당시 검증 기록입니다.)"
    )

    with st.expander("⓪ 최신 갱신 (2026-10-11) — 현재 설정과 최신 백테스트 결과", expanded=True):
        st.markdown("""
**현재 앱 기본 설정**: 시작일 2015-01-01 · 슬리피지 0.2%/회 · 양도세 22%(12월 말 확정, 이듬해 6월 말 납부, 연 공제 250만원) · 초기 투자금 1,000만원 · 비중 상한 꺼짐(선택) · 월중 하드스탑 없음 · 데이터는 백필 파일(2000년\\~)에 최신 구간을 야후에서 이어붙임

**최신 백테스트** (2026-10-11 앱 화면 값 · 시뮬레이션 2016-02 \\~ 2026-10, 위 설정 기준, 배당수익률 정정 반영. QQQ도 같은 비용·세금 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)의 세후 값)

| 지표 | 2026 혼합전략 | QQQ (세후) |
|---|---|---|
| 기간 수익률 | 1,640.9% | 533.4% |
| 연환산 수익률 (CAGR) | 30.7% | 18.9% |
| 최대 낙폭 (MDD) | -15.1% (2019-05) | -29.9% (2022-12) |
| 월 최고 / 최저 | 24.0% / -15.1% | 14.8% / -12.4% |
| 수익 월 비중 | 93 / 129 | 85 / 129 |
| 연 변동성 | 17.4% | 16.7% |
| 샤프 / 소티노 / UPI | 1.63 / 2.47 / 7.61 | 1.12 / 1.80 / 2.28 |
| 1년 / 3년 / 5년 수익률 | 20.3% / 131.2% / 240.1% | 19.0% / 107.2% / 92.1% |
| 연간 턴오버 | 338.8% | 0.0% |

세후 최종 자산은 약 1.74억원입니다(초기 1,000만원). QQQ의 MDD가 세전(-32.6%)보다 작은 것은 보유 중 낙폭만큼 내야 할 세금도 함께 줄어들기 때문입니다.

**폭락 구간 성과** (2026-10-04 값, 같은 설정)

| 구간 | 혼합전략 | QQQ |
|---|---|---|
| 코로나 팬데믹 (2020-01 \\~ 03) | -1.0% | -10.3% |
| 2022 긴축 발작 (2022-01 \\~ 10) | +29.7% | -29.8% |
| 2018년 4분기 조정 (2018-10 \\~ 12) | -0.8% | -16.7% |

**2008 금융위기 확인** (시작일 2004-01-01 → 2005-02 \\~ 2026-10, 안전장치 없음, 당시 화면 값으로 비용·세금 미반영, 상장 전 구간은 백필·합성 데이터): 혼합전략 MDD -15.3%·2008년 연간 -6.0%, QQQ MDD -49.7%·2008년 연간 -41%.

**샤프가 내려간 이유** (2015\\~ 기준 2.03 → 1.63): 세금이 수익에 비례해 나가면 샤프는 거의 변하지 않지만, 이 앱은 전년도 세금을 6월 말에 한꺼번에 차감해 6월 수익률이 낮아지고 월 변동성이 커집니다(월별 수익률 표의 6월 평균 약 -1.6%, 나머지 달 약 +2.8%). 슬리피지 영향은 작습니다. 정확한 분해는 아래 '💸 비용·세금 전/후 비교' 표에서 확인합니다.

**2026-10-05 배당수익률 정정 반영**: 전략 C 배당수익률을 SPY 실제 종가로 계산하도록 고친 뒤, 비용·세금 미반영 2016\\~ 혼합 CAGR이 37.6%→36.9%로 소폭 낮아졌고 MDD(-14.9%)는 같습니다. 세후로는 2026-10-04의 31.2%에서 위 표의 30.7%가 되었습니다(정정과 최근 데이터 갱신이 함께 반영된 값).

**이전 검증값(2026-10-01)과 달라진 점**: ③·⑤의 혼합전략 수치(2015\\~ CAGR 37.7% / MDD -13.0% 등)는 비용·세금을 반영하지 않은 야후 원본 데이터 기준이라, 위 최신값(CAGR 30.7% / MDD -15.1%)보다 수익률이 높고 낙폭이 작습니다. 비용·세금 반영과 데이터 변경(백필 파일, 최신 데이터)이 함께 작용한 것으로 보이며, 각각의 영향은 따로 분해해 보지 않았습니다. 수치는 시작일·비용 설정·데이터 갱신에 따라 계속 달라질 수 있고, 과거 성과가 미래 수익을 보장하지 않습니다.
""")

    with st.expander("⓪-1 추가 검증 (2026-10-05) — 배당수익률 정정·자산 목록·전략 C 방어 보완", expanded=False):
        st.markdown("""
모두 비용·세금 미반영, 월말 기준입니다. 검증용 스크립트(etf_check.py, list_check.py, c_defense_check.py, c_nominal_check.py)는 앱 폴더에 있습니다.

**1. 전략 C 배당수익률 편향 정정 (✅ 적용)**

배당수익률을 수정주가(배당 재투자 반영)로 나누면 과거로 갈수록 값이 부풀려집니다. 2000-03 기준 수정주가로는 1.59%(공격)였지만 실제 주가로는 0.99%(방어)입니다. 그래서 정정 전 백테스트에서는 C의 방어 모드가 2021년 이전에 한 번도 나오지 않았습니다.

| 구분 | 2001\\~ 혼합 CAGR | 2016\\~ 혼합 CAGR | 닷컴 구간 C | 2021년 C | 2022년 C |
|---|---|---|---|---|---|
| 정정 전 (수정주가) | 23.6% | 37.3% | -25.8% | +62.5% | +57.5% |
| **정정 후 (실제 주가)** | **23.5%** | **36.6%** | **-18.1%** | +27.5% | **+68.9%** |

정정 후 닷컴 구간(2000\\~2002)에 방어 신호가 정상적으로 나오며, 전체 성과는 거의 같습니다. 실시간 신호는 원래부터 현재가로 계산해 영향이 없습니다.

**2. 기준선 1.33% 민감도 (실제 배당률 기준)**

| 기준선 | 1.20% | 1.30% | 1.33% | 1.40% | 1.50% | 1.60% |
|---|---|---|---|---|---|---|
| 2001\\~ 혼합 CAGR | 22.7% | 23.7% | 23.5% | 22.8% | 23.6% | 23.1% |
| 2001\\~ 혼합 MDD | -18.8% | -18.8% | -18.8% | -18.8% | -18.8% | -18.8% |

1.2\\~1.6% 전체가 고르게 안정적이라, 1.33%는 뾰족한 최적값이 아닙니다.

**3. 전략 C 방어 모드 보완안 (❌ 미적용)**

배당수익률이 낮아 C가 2024-04부터 방어 모드인 상태에서, 반도체 같은 주식 상승을 놓치지 않도록 세 가지를 검증했습니다(실제 배당률 기준).

| 안 | 2001\\~ 혼합 CAGR | 2016\\~ 혼합 CAGR | 판정 |
|---|---|---|---|
| **V0 현재 (방어 자산 1위)** | **23.5%** | **36.6%** | ✅ 유지 |
| V1 방어 후보에 공격 1위 추가 | 23.1% | 35.5% | ❌ |
| V2 SPY 10개월선 위면 공격 | 22.7% | 34.7% | ❌ (2022 긴축장에서 크게 뒤짐) |
| V3 방어 시 50%는 공격 1위 | 23.2% | 35.9% | ❌ |

2026년만 보면 V1이 앞서지만(C +69% vs +32%), 2024\\~2025년 금·원유 상승분을 놓쳐 전체로는 열위입니다.

**4. 자산 목록 사후 선택 점검 (✅ 문제 없음)**

전략 A 목록은 변경 전 10개(FEZ·GLD·IBB·LIT·QQQ·SMH·UBT·XLE·XLK·XLV)에서 EEM·QTUM을 추가했습니다.

| 경우 (2016\\~ 혼합) | CAGR | MDD |
|---|---|---|
| 현재 목록 | 37.3% | -14.9% |
| A 변경 전 10개 | 37.7% | -13.0% |
| A 공격 자산 하나씩 제외 (12가지) | 36.7\\~37.8% | |
| C에서 SMH / LIT 제외 | 34.7% / 34.8% | |
| A·C 모두 SMH+LIT+QTUM 제외 | 30.0% | -11.3% |

목록 변경으로 성과가 부풀려진 효과는 없고, 특정 자산 하나에 기대지 않습니다. C가 후보 구성에 가장 민감합니다(1종목 100% 집중). 대세 섹터를 모두 빼도 CAGR 30%이므로, 비용·세금과 강세장 효과를 감안해 장기 계획용 기대수익은 20%대 초중반으로 봅니다.

**5. 반도체·모멘텀 ETF와 비교 (2016-02\\~)**

| | CAGR | MDD | 샤프 |
|---|---|---|---|
| **2026 혼합전략** | **37.3%** | **-14.9% (월말)** | **1.99** |
| SMH (반도체) | 36.3% | -45.3% (일별) | 1.25 |
| QQQ | 21.0% | -35.1% (일별) | 1.12 |
| SPMO / MTUM (모멘텀) | 19.8% / 16.5% | -30.9% / -34.1% (일별) | 1.13 / 0.96 |

혼합전략은 반도체 ETF와 비슷한 수익을 1/3 수준의 낙폭으로 냈고, 모멘텀 ETF는 QQQ보다도 낮았습니다. 개별주 돌파 전략(EMB)은 같은 기간 CAGR 2.5\\~3.9%로 폐기했습니다.
""")

    with st.expander("⓪-2 추가 검증 (2026-10-05) — 인출 계획·다른 전략(CDS·매크로 레짐)", expanded=False):
        st.markdown("""
조건: 백필 데이터(2000\\~2026-09)와 앱 엔진 그대로, 슬리피지 0.2%·양도세 22%(공제 250만원)·**초기 투자금 5억원** 반영. QQQ는 비용·세금 없는 단순 보유입니다.

**1. 초기 5억원 기준 세후 성과 — 계획 수익률의 현실 점검**

| 시작 | 세후 CAGR | MDD | 세전 CAGR | QQQ |
|---|---|---|---|---|
| 2001\\~ | 17.4% | -22.0% | 23.5% | 10.7% |
| 2005\\~ | 19.3% | -22.0% | 25.8% | 15.2% |
| 2010\\~ | 22.0% | -17.9% | 29.5% | 19.1% |
| 2015\\~ | 24.6% | -15.1% | 32.2% | 19.1% |

⓪의 30.7%(초기 1,000만원)보다 낮은 이유는 양도세 공제 250만원이 고정 금액이라 투자금이 클수록 세금 비중이 커지기 때문입니다. 자산 계산기의 25%는 최근 10년 세후 실측치에 가깝지만 2001년 이후 장기로는 17\\~19%입니다.

**2. 인출 계획 백테스트 (초기 5억원, 1년차부터 월 생활비·물가 3% 인상, 20년)**

- 월 800만원: 2001\\~2015년 시작은 모두 6\\~11년차에 고갈. 2016\\~2020년 시작은 현재까지 유지(6\\~10년치만 확인 가능)
- 하락 시 생활비 25% 절감(계좌 고점 대비 -10% 이하일 때): 고갈이 2\\~4년 늦춰지고 2009·2013·2015년 시작은 생존
- 현금 버퍼 2년치: 개선 효과 없음 (현금의 수익 손실이 더 큼)
- 2001\\~2007년 시작 기준으로 20년을 버티는 최대 생활비(첫해): 기본 **월 350\\~450만원**, 하락 시 절감 규칙을 쓰면 **월 450\\~600만원**

**3. 다른 전략 검증 (❌ 둘 다 폐기)**

| 전략 | 2015\\~ 세후 CAGR / MDD / 샤프 | 판정 근거 |
|---|---|---|
| **2026 혼합전략 (현행)** | **24.8% / -15.1% / 1.36** | 기준 (1번 표의 24.6%와는 별도 실행이라 소폭 차이) |
| 코어 디펜더(CDS) | 10.7% / -14.0% / 0.82 | 전략 A와 공격 자산이 같고 상관 0.75 → A의 열위 버전. A 대신 넣거나 4분할로 추가해도 개선 없음 |
| 매크로 레짐 (분기+VIX25) | 5.0% / -11.3% / 0.60 | 혼합과 상관 0.29로 분산 효과는 있으나 25% 섞으면 CAGR -4\\~5%p에 MDD 개선은 2\\~4%p. 단독 성과가 60/40보다 낮음 |

검증 자료: `인출계획_백테스트_20261005.md`, `다른전략_검증_CDS_매크로_20261005.md`
""")

    with st.expander("⓪-3 앱 기능 추가 (2026-10-09 \\~ 10-11) — 자료실", expanded=False):
        st.markdown("""
전략 로직·백테스트 엔진은 바뀌지 않았고, 화면과 운영 방식만 추가·정리했습니다.

| 항목 | 내용 |
|---|---|
| 자료실 페이지 | 별도 페이지 `pages/9_library.py`. 처음엔 한글 파일 이름(`9_자료실.py`)이었으나 Cloud에서 한글 인코딩 차이로 페이지를 찾지 못해 영문 이름으로 확정 |
| 슬라이드 뷰어 | Streamlit 기본 확대 화면에서는 넘길 수 없어 전용 뷰어로 교체: 좌우 밀기, ‹ › 단추, ⛶ 전체화면(안드로이드 가로 회전, 전체화면 안에서도 넘김), 키보드 ← →, 문서별 보던 장 기억 |
| 이동 방식 | 사이드바 페이지 메뉴는 `.streamlit/config.toml`로 숨김. INSIGHTS 그룹에 '📚 자료실' 탭(장기 낙폭과 자산 계산기 사이)을 두고 '자료실 열기' 단추·문서 이름 클릭으로 이동, 자료실에서는 '🏠 전략 대시보드로 돌아가기' 버튼(위·아래)으로 복귀 |
| 탭 구조 | 탭 9개로 확장(칸 수·INSIGHTS 머리띠 폭 조정). '미국 ETF 랭킹' 탭의 국기 이모지는 윈도우에서 "us" 글자로 보여 제거 |
| 문서 순서 | '인포그래픽'은 항상 맨 위 → 휴대폰으로 올린 문서(최근 것부터) → `docs/_pinned.txt`에 적은 고정 문서 → 나머지 가나다순 (탭 목록과 자료실 화면 같음) |
| 자료 변환·업로드 | `자료실_업데이트.bat` → `update_library.py`: `pdf_src`의 PDF(100dpi·JPG 품질 80)와 이미지 폴더(가로 1600px)를 `docs`로 변환, 이미 변환된 것은 건너뜀, 원본이 지워진 문서는 확인 후 삭제, git push로 업로드. 약 40개 문서·114MB |
| 코드 업로드 | 로컬 폴더를 git으로 저장소와 연결(`.gitignore`로 필요한 파일만 허용). `대시보드_업로드.bat`이 `2026app-a.py`·`pages`·`requirements.txt`만 올림 |
| 안정성 | 링크·목록 오류가 나도 대시보드 전체가 멈추지 않도록 예외 처리, 한글 문서 이름 비교는 PC/Cloud 인코딩 차이를 무시(NFC 정규화) |
""")

    with st.expander("⓪-4 앱 기능 추가 (2026-10-12 \\~ 10-14) — 미국 주식 랭킹·보유 기준·시장 밸류에이션·자료실 올리기", expanded=False):
        st.markdown("""
전략 A·B·C와 혼합전략의 로직·백테스트 엔진은 바뀌지 않았습니다(⓪의 수치는 2026-10-11 값 그대로). 아래는 INSIGHTS 화면과 운영 방식에 추가된 내용과, 그 근거로 쓴 PC 백테스트입니다.

**1. 화면 정리**

| 항목 | 내용 |
|---|---|
| 탭 이름 | '나스닥100 랭킹' → '🏢 미국 주식 랭킹' (지수 3개 선택) |
| 혼합전략 탭 | '월말 기준 리밸런싱 포트폴리오 역사 (최근 1년)'를 화면에서 제거 — '월별 세부 리밸런싱 기록'과 내용이 겹침(함수는 남겨 둠) |
| 목표 수량 계산기 | 투자금을 만원 단위로 입력(기본 1,000만원, ±100만원) |

**2. 미국 주식 랭킹 탭**

| | 나스닥100 | S&P500 | KOSPI200 (테스트) |
|---|---|---|---|
| 구성 종목 | 위키피디아 (실패 시 내장 목록) | 위키피디아 | PC에서 만든 `kospi200.csv` |
| 비교 기준 | QQQ | SPY | KODEX200 |
| 첫 로딩 | 약 10초 | 약 1분 | 약 30초 |
| 보유 기준(매매) | ✅ | ✅ | ❌ 랭킹·상태·추세만 |

- 순위표 상위 50(1\\~20 바로, 21\\~50 접기), 기본 정렬 시가총액, 상태 필터·보유 기준 필터, 종목 검색(쉼표로 여러 개, 티커·한글명·영문명·업종 일부)
- 종목 차트: 보유 기준 상자, 가격 표(현재가·재매수 기준·200일선·매도 기준), 매도 기준까지 거리, 추세 건강도(참고용 5항목), 차트 오른쪽 위 추세 배지(🟢 4/4 · 🟡 3/4 · 🔴 2 이하)
- 목표가·중기 손절은 제거 — 200일선 규칙과 맞지 않고 백테스트상 효과가 없었음
- 맨 아래 '📘 QQQ를 장기 보유하려면\\~'(토글): 낙폭 줄이기 규칙 백테스트 정리

**3. 보유 기준 (미국 종목, 월말 종가 판단)**

| 표시 | 조건 |
|---|---|
| 🟢 보유·매수 가능 | 200일선 +5% 위 |
| 🟢 보유 (재매수 대기) | 200일선 위 \\~ +5% |
| 🟡 경계 | 200일선 아래 3% 이내 |
| 🔴 매도 기준 | 200일선 −3% 아래 |

**4. 근거 백테스트** (모두 PC 스크립트, 현재 지수 구성 종목만 써서 생존편향 있음)

| 검증 | 결과 | 반영 |
|---|---|---|
| ① 매도 기준 (`hold_rule_backtest.py`, 나스닥100 98종목, 2015\\~) | 매수 후 보유 27.4% / -30.5% / 샤프 1.2 · 점수형 판정 9.7% / -11.3% / 1.1 · **200일선 −3% 매도 18.1% / -19.8% / 1.3** · QQQ 19.2% / -35.1% / 0.9 | 200일선 규칙 채택, 점수형은 참고용 |
| ② QQQ 낙폭 대응 (세전·세후) | 2000\\~ 세후 QQQ 7.8% / -83% vs 200일선 월 1회 9.3% / -36.5%. 2010\\~ 세후는 QQQ 17.4%가 규칙(11.4%)보다 높음 | 장기 하락장 방어는 탁월, 상승장 보험료 큼. 일반 계좌는 덜 파는 방식, 매매 비과세 계좌는 200일선 규칙 |
| ③ 재매수 기준 (S&P500, 2006\\~, 6,852건) | 3개월 내 재손절: +0% 30% · **+5% 19%** · +10% 12%. 거래당 중앙값 +5%에서 플러스 전환 | 재매수 +5% 채택 |
| ④ 코스피200 (2006\\~) | 매수 후 보유 16.4% / -43.7% vs 규칙 9\\~11% / -22\\~28%, 샤프 0.8로 같음 | KOSPI200은 매매 기준 없이 표시 |

**5. 미국 ETF 랭킹 — 🧮 시장 밸류에이션 (4번째 보기)**

켄 피셔 『불변의 차트 90』 지표를 응용한 배경 판단용 계기판입니다. 기준값은 검증하지 않았고 매매 신호가 아닙니다.

| 지표 | 🟢 / 🟡 / 🔴 기준 |
|---|---|
| ① S&P500 이익수익률 − Baa 회사채 금리 | +1%p 이상 / ±1%p / −1%p 미만 |
| ② S&P500 배당수익률의 1999\\~ 위치 | 상위 40% / 중간 / 하위 25% |
| ③ 10년물 3개월 변화 | +0.4%p 미만 / \\~0.75%p / 그 이상 |
| ④ 나스닥100 PER ÷ S&P500 PER | 1.25배 이하 / \\~1.6배 / 초과 |
| ⑤ 실업률 삼의 법칙 | +0.3%p 미만 / \\~0.5%p / 그 이상 |

Cloud에서 야후 PER·FRED가 막히면 PC에서 이 화면을 열 때 저장되는 `valuation_snapshot.json` 값을 씁니다.

**6. 자료실 추가 기능**

| 항목 | 내용 |
|---|---|
| ⛶ 전체화면 확대 | 두 손가락 확대(최대 6배), 두 번 탭 2.5배, 확대 중 끌어서 이동, − 1:1 + 단추, PC 휠 확대 |
| 📤 문서 올리기 (휴대폰) | 새 문서: PDF 1개(최대 80장·25MB) 또는 이미지 여러 장 → 서버가 jpg로 변환 → GitHub API로 한 번에 커밋. 기존 문서 맨 앞에 이미지 추가(같은 그림은 자동 건너뜀) |
| 이미지·문서 지우기 | 미리보기 3장씩 + 체크 + 비밀번호. PC 변환 이미지를 지우면 `pdf_src` 원본도 지우라고 경고 |
| PC와의 구분 | 휴대폰 이미지는 `m…` 이름, 휴대폰 문서는 `_phone_upload.txt` 표시 → PC 스크립트가 지우지 않음 |
| 운영 | PC는 `pdf_src` + `자료실_업데이트.bat`, 휴대폰은 📤. 올리기는 Cloud에서만 동작(Secrets 필요) |
""")

    with st.expander("⓪-5 앱 기능 추가 (2026-10-14 \\~ 10-20) — 시장위험진단·관리자 모드·위성 전략(MSTR·S&P500 재돌파)", expanded=False):
        st.markdown("""
전략 A·B·C와 혼합전략의 로직·백테스트 엔진은 이번에도 바뀌지 않았습니다(⓪의 수치는 2026-10-11 값 그대로). 아래는 화면·운영 변경과, 투자 원칙 선언문의 **개별투자 10% 칸**에서 쓸 위성 전략 검증입니다.

**1. 화면 정리**

| 항목 | 내용 |
|---|---|
| 💸 수수료·세금 빠른 전환 | 혼합전략·전략 A\\~C 탭 연도별 수익률 바로 위 [반영 / 미반영] — 맨 위 ② 슬리피지·③ 양도세를 함께 켜고 끔. 반영 중이면 '비용·세금 반영 중 · 초기 투자금' 줄을 초록 상자로 강조 |
| 이번 달 일별 수익률 | -10% 참고 기준선 삭제 (2026-10-17) |
| 목표 수량 계산기 | 1,000 이상 입력하면 지워지던 문제 수정(숫자 칸에 콤마 넣던 스크립트 제외) · '📖 목돈·신규 투자금이 생겼을 때' 읽는 법 |
| 태블릿 터치 | `st.toggle`·`st.checkbox`가 일부 태블릿에서 반응하지 않아 접기/펼치기 라디오(`tab_toggle()`)로 교체. 비중 상한·자료실 페이지도 라디오 |
| 미국 ETF 랭킹 | 보기 2줄 배치 [전략 자산 랭킹 · 섹터·테마] / [🩺 시장위험진단 · 위험 신호판 · 밸류에이션], 🔎 ETF 검색은 윗줄 보기에서만 |
| 미국 주식 랭킹 | 맨 위 🔎 실시간 미국 주식 종목 찾기(랭킹 없이 아무 미국 주식·ETF) · KOSPI200 숨김 · 맨 아래 📘 QQQ · 📘 비트코인 · 📘 MSTR 세 섹션 |
| 날짜 표기 | 문장 속 날짜는 '10월 20일' 형식 (10-20은 날짜로 읽히지 않음) |

**2. 🩺 시장위험진단** — 위험 신호판(긴장, 몇 주\\~몇 달) × 밸류에이션(가격 부담, 몇 년)을 겹쳐 읽는 화면. 비교표 → 지금 진단(종합 판정과 켜진 지표) → 3 × 3 판단표(지금 칸 강조) → 규칙 밖 결정(신규 자금 투입 방식·기대수익 가정·위성 자산 비중). 혼합전략과 200일선 보유 기준은 어느 칸이든 그대로 따름. 해설: 보고서 '대시보드로 보는 위험진단법'(2026-10-15)

**3. ETF 종류별 보유 기준** (ETF 49개 백테스트, 1998\\~)

| 종류 | 재매수 | 적용 | 근거 |
|---|---|---|---|
| 지수·섹터·국가·배당형 | 200일선 회복 | 규칙 | +5% 재매수보다 나았고 MDD 평균 20%p 이상 감소 |
| 테마·원자재 | +5% | 규칙 | 출렁임이 커 +5%가 휩소를 줄임(10개 중 7개) |
| 채권 · 금 | 200일선 회복 | 참고용 | 규칙 효과가 약하거나(채권) 그냥 보유가 나음(금) |
| 레버리지·인버스 | — | ⛔ 미적용 | 규칙을 써도 MDD −70\\~−90% |

**4. 🔧 관리자 모드** (자료실 탭 맨 아래, 나만 보기)

| 메뉴 | 내용 |
|---|---|
| 📜 투자 선언문 | 생존 · 동적 자산배분 규칙 준수 · 개별투자 운용자금의 10% 이내 · 충분함 50억원 |
| ⭐ 관심 종목 · 💼 내 보유 현황 | 티커 목록·보유 수량·평균 단가 → 보유 기준·평가액·손익 |
| 📈 MSTR 매매 | 오늘의 신호판 · 장부(실제 2026-10-20 시작 2,000만원 · 샘플 A 80% · 샘플 B 60%) · 추가 입금 기록 |
| 📊 내 백테스트 결과 | S&P500 재돌파 선정 종목 · 정리 상자 4개 · PC 결과 파일 올려 보기 |

- 데이터는 GitHub 별도 브랜치 `watchlist-data`에 저장(main이 아니라 앱 재시작 없음), PC는 `watchlist_local.json`·`admin_local/`
- Secrets `OWNER_PASSWORD`(내 비밀번호)로 접속하면 관리자 모드가 자동으로 열리고 방문자 수에서 빠짐. 방문자 수는 `visits.json`에 누적(자산 계산기 탭 맨 아래 표시)
- `requirements.txt`는 `streamlit==1.65.0` 고정(Cloud 버전)

**5. 위성 전략 검증** (PC 스크립트, 세금 미반영)

| 검증 | 결과 | 반영 |
|---|---|---|
| ① 비트코인 장기 보유 (`btc_*`, 2015\\~) | 그냥 보유 60.3% / -83.4% · 120일선만 76.9% / -60.7% · **120일선 + 반감기 사이클 분할 66.0% / -33.0%** · 적립식 + 같은 규칙은 평가액 최대 하락 -33% (순수 적립식 -83%) | '📘 비트코인을 장기 보유하려면\\~' 1순위·2순위 |
| ② MSTR 대체 (`mstr_rules_backtest.py`, 2020-08\\~) | MSTR 보유 50.2% / -89.3% · BTC 120일선만 47.8% / -81.0% · 반반 + 사이클 × 변동성 60% 66.4% / -36.7% · **× 80% 78.7% / -48.3% / 샤프 1.37** (MSTR 신호 다음 날 매매) | 목표 = (BTC 120일선 50% + MSTR 200일선 50%) × 사이클 상한 × 80%÷20일 변동성. 금요일 값으로 한 주, 차이 10%p 이상만 조정, LOC ±8% 지정가, 매수 수량은 지정가 기준 |
| ③ S&P500 200일선 +5\\~10% (`sp500_band_backtest.py`) | 첫 비교: 필터 없음은 2008년 -25\\~-45%, SPY↓ 신규매수 중단은 MDD -21% 안팎 | 시장 필터 채택('전부 현금'은 V자 반등을 놓쳐 제외) |
| ④ 재돌파 조건 (최근 6개월 내 200일선 아래였던 종목만) | **재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순: 2006\\~ 14.0% / -22.1% · 2015\\~ 12.3% / -19.5%** (SPY 11.1% / -55.2% · 13.7% / -33.7%) | 추천 조합 |
| ⑤ TIP 카나리아 필터 · 종목 범위 (`band_universe_backtest.py`) | TIP 필터는 MDD -35\\~-38%로 방어가 약함(대안: TIP-A↓ · 10종목 · 모멘텀순). 거래대금 상위 100·200으로 좁히면 수익·샤프 하락 | 추천 유지, S&P500 전체 사용 |

- 사이클 상한: 반감기 후 0\\~12개월 100% · 12\\~15개월 50% · 15\\~30개월 0% · 30개월\\~ 100%. 2026-10-20부터 100%(④), 다음 변경 2029년 4월 추정(다음 반감기 2028-04 추정)
- 2026-10-20 MSTR 실제 첫 매수: 목표 100%, 전일 종가 \\$136.02 vs 200일선 \\$135.53(+0.4%, 휩소 주의)
- 반반을 택한 이유(MSTR 200일선 단독의 우위가 2024년 한 해·200일이라는 한 숫자에 기댐), 80%를 택한 이유(60%는 급등 구간 상승을 절반만 받음, 10% 칸 안이라 -48%도 전체 계좌로는 약 -4.8%), 휩소 대응은 MSTR 섹션 '읽는 법'에 정리
- 어느 위성 전략도 2026 혼합전략보다 낫지 않아, 모두 개별투자 10% 칸 안에서만 씀
""")

    with st.expander("① 종합평가서 요약 — 강점과 지적된 한계", expanded=False):
        st.markdown("""
**강점**

- 물가연동국채(TIP)로 실질금리 변화를 추적하고, 시장 배당수익률 밸류에이션 필터와 결합해 거시 국면 전환을 선제 감지
- 하락장에서는 모멘텀 제로 플로어(Zero-Floor) 규칙으로 최대 100% 현금 대피 가능

**지적된 구조적 한계**

- 명목 비중은 33.33%씩이지만 3배 레버리지에 단일 집중하는 전략 B가 전체 위험의 65\\~75% 이상을 지배
- 하위 전략 간 유니버스 중복으로 특정 ETF에 쏠림 발생 (예: 2019년 5월 SMH 41.66%)
- S&P 500 배당수익률이 구조적으로 낮아져(1% 내외) 전략 C의 고정 기준선(1.33%)이 강세장에서도 방어 신호만 내는 '신호 동결' 우려
""")

    with st.expander("② 분석 결과 — 확인된 문제와 개선 방향", expanded=False):
        st.markdown("""
| 항목 | 코드·데이터로 확인한 내용 | 제안된 개선 |
|---|---|---|
| 전략 C 신호 | 기준선 1.33%가 4곳에 하드코딩. 현재 배당수익률 0.99% | 36개월 롤링 Z-Score |
| 전략 B 집중 | 점수 공식에서 최근 1개월이 63.16% | 가중 완화 + 변동성 타깃팅 |
| 종목 쏠림 | 혼합 합산 시 한 종목에 비중 집중 가능 | 단일자산 상한 35% |
| 공포 구간 | 3배 ETF 변동성 잠식 우려 | VIX 28 초과 시 레버리지 절반 |
| **추가 발견** | 배당 조정가를 써서 과거 배당수익률이 과대 계산됨 | ✅ 2026-10-05 실제 종가로 정정 적용 (⓪-1 참고) |
""")
        st.caption("진행 방식: 모든 개선을 적용/미적용 토글과 전·후 비교표로 구현해 실제 데이터로 검증한 뒤, 효과 없는 항목은 제거했습니다.")

    with st.expander("③ 개선안 적용 백테스트 결과 (2018\\~ · 2026-10-01 검증, 비용·세금 미반영)", expanded=False):
        st.markdown("""
**전략 C — 배당수익률 신호**

| 방식 | CAGR | MDD | 샤프 | 공격 비율 |
|---|---|---|---|---|
| **① 기존 (고정 1.33%)** | **52.6%** | **-17.2%** | **1.68** | 65% |
| ② 고정 + 비조정가 | 49.3% | -17.2% | 1.61 | 56% |
| ③ Z-Score 36개월 | 42.8% | -23.4% | 1.54 | 34% |

2015\\~ 구간도 동일(CAGR 44.7% → 33.6%, MDD -17.2% → -31.0%). 2020\\~에서만 Z가 소폭 우세(51.1% vs 50.1%).

**전략 B — 모멘텀 가중·변동성 타깃팅**

| 방식 | CAGR | MDD | 샤프 |
|---|---|---|---|
| **① 기존 12-4-2-1** | **42.4%** | **-22.7%** | **1.34** |
| ② 완화 4-3-2-1 | 33.2% | -37.7% | 1.06 |
| ③ 변동성 타깃 35% | 30.6% | -15.8% | 1.29 |
| ④ 둘 다 | 24.3% | -31.7% | 0.98 |

**혼합전략 — MDD 안전장치**

| 방식 | CAGR | MDD | 샤프 | 발동 |
|---|---|---|---|---|
| ① 없음 | 43.9% | -13.0% | 2.10 | - |
| ② 상한 35% | 39.6% | -12.0% | 2.06 | 66개월 |
| ③ VIX 28 | 41.7% | -13.0% | 2.10 | 7개월 |
| ④ 상한 25% | 30.1% | -8.9% | 2.07 | 92개월 |
| ⑤ 하드스탑 -7% | 40.1% | -9.6% | 1.87 | 6개월 |
| ⑥ 상한 25% + 하드스탑 | 25.3% | -9.8% | 1.59 | 6개월 |
""")

    with st.expander("④ 판정 — 의미 없었던 것과 적용한 것", expanded=False):
        st.markdown("""
| 항목 | 판정 | 근거 |
|---|---|---|
| 전략 C Z-Score | ❌ 제거 | CAGR·MDD 모두 열위 |
| 전략 B 가중 완화 | ❌ 제거 | 수익·MDD 모두 악화 |
| 전략 B 변동성 타깃팅 | ❌ 제거 | MDD만 감소, CAGR 12%p 하락, 샤프 개선 없음 |
| VIX 28 레버리지 축소 | ❌ 제거 | 7개월만 발동, MDD 변화 없음 |
| 상관관계 필터 | ❌ 미구현 | 필요 없다고 판단 |
| 월중 하드스탑 (-7%) | ❌ 제거 (2026-10-04) | 당시 2018\\~ MDD -13.0% → -9.6%였으나 구간·임계치에 따라 효과가 일관되지 않아 제거 |
| 비중 상한 (입력칸) | ✅ 유지 | MDD를 줄이는 선택 장치 (CAGR도 함께 감소) |
| 전략 C 기준선 1.33% | ✅ 기존 유지 | 1.2\\~1.6% 모두 비슷한 안정 구간, 바꿔서 확실히 나아지는 값이 없음 |
| 전략 C 배당수익률 실제 종가 정정 | ✅ 적용 (2026-10-05) | 편향 제거, 닷컴 구간 방어 신호 정상화, 전체 성과는 거의 동일 |
| 전략 C 방어 보완 (탈출구·추세 보조·절반 탈출) | ❌ 미적용 (2026-10-05) | 세 안 모두 2001\\~·2016\\~ 성과 열위 |
| 전략 A 자산 목록 (EEM·QTUM 추가) | ✅ 유지 | 목록 변경 전후 차이 0.4%p로 우연 수준, 미래 대비 후보 |
""")

    with st.expander("⑤ 최종 결과 — 전략 로직 검증 (2026-10-01 검증값, 비용·세금 미반영)", expanded=False):
        st.markdown("""
전략 A·B·C의 로직은 **원본 그대로**이며, 제거 후 엔진의 NAV가 원본과 정확히 일치함을 3개 구간 × 4개 엔진 모두 확인했습니다.

| 전략 | 2015\\~ CAGR / MDD | 2018\\~ CAGR / MDD | 2020\\~ CAGR / MDD |
|---|---|---|---|
| A | 25.1% / -15.7% | 29.8% / -15.7% | 24.2% / -15.7% |
| B | 37.8% / -22.7% | 42.4% / -22.7% | 37.1% / -18.8% |
| C | 44.7% / -17.2% | 52.6% / -17.2% | 50.1% / -17.1% |
| **혼합** | **37.7% / -13.0%** | **43.9% / -13.0%** | **39.4% / -9.6%** |

혼합전략 샤프 지수는 2.03 / 2.10 / 2.21로, 개별 전략(1.3\\~1.7)보다 높습니다. 비중 상한은 체크박스로 켜고 끄며, 기본값은 꺼짐입니다. 최신 수치는 ⓪을 보세요.
""")

    with st.expander("⑥ 이런 지적을 받는다면 — 이미 검증했습니다", expanded=False):
        st.markdown("""
| 지적 | 검증 결과 |
|---|---|
| "배당수익률이 낮아져 전략 C 기준선 1.33%는 상시 방어 아닌가?" | 36개월 Z-Score로 바꿔 검증 → CAGR 52.6%→42.8%, MDD -17.2%→-23.4%로 오히려 악화. 실제 배당률 기준으로 기준선 1.2\\~1.6%를 비교해도 2001\\~ 혼합 CAGR 22.7\\~23.7%, MDD 모두 -18.8%로 안정 구간 확인 |
| "방어 모드에서 반도체 상승을 놓치지 않나?" | 방어 시 공격 자산 허용 3가지 안을 2001\\~로 검증 → 모두 현재 방식보다 열위(⓪-1). 반도체 상승은 전략 A(공격 4종목 중 SMH)가 주로 담당 |
| "자산 목록을 결과를 보고 고른 것 아닌가?" | 하나씩 빼기·변경 전 목록 비교 → 목록 변경 효과 없음, 대세 섹터를 모두 빼도 2016\\~ CAGR 30.0%·MDD -11.3% |
| "3배 레버리지 전략 B가 위험을 지배한다" | 변동성 타깃팅 검증 → MDD -22.7%→-15.8%로 줄지만 CAGR 42.4%→30.6%, 샤프 1.34→1.29. 위험만 줄이는 수단이라 제거. 혼합 시 MDD는 -13.0%로 분산 효과 확인 |
| "최근 1개월 비중 63%는 휩소가 많다" | 4-3-2-1 완화 검증 → CAGR 33.2%, MDD -37.7%로 악화 |
| "특정 ETF 쏠림이 위험하다" | 비중 상한 35%/25% 검증 → MDD -12.0%/-8.9%로 감소하나 CAGR 39.6%/30.1%로 하락, 샤프는 약 2.1로 동일. 선택 장치로 제공 |
| "공포 구간에 3배 ETF 비중을 줄여야 한다 (VIX 28)" | 검증 → 7개월만 발동하고 MDD 변화 없음 |
| "닷컴·금융위기급 폭락에 대비가 없다" | 백필 데이터(2000년\\~)로 직접 확인: 2004 시작(2005-02\\~) 기준 2008년 MDD -15.3%·연 -6.0% (QQQ -49.7%·-41%). 닷컴버블(2000\\~02)은 시작일 2000으로 볼 수 있으나 합성·대체 데이터 비중이 커서 참고용. 월중 하드스탑(-7%)은 한때 보유했으나 구간·임계치에 따라 효과가 일관되지 않아 2026-10-04 제거 |
| "백테스트가 과최적화 아닌가?" | 인정: 전 구간 표본 내 성과. 여러 시작일(2000·2004·2015·2018·2020)로 교차 확인할 수 있고, 한 점이 아닌 안정 구간을 기준으로 판단 |
| "비용과 세금을 빼면 수익이 크게 줄지 않나?" | 슬리피지 0.2%/회와 양도세 22%(이듬해 6월 말 납부)를 기본 반영했고 ⓪의 최신 수치가 그 결과(2016\\~ CAGR 30.7%, 세후). 연간 턴오버 약 339%로 비용 영향이 큰 구조이며 환전 비용·수수료는 빠져 있음 |
| "실제 운용 금액이 크면 세후 수익률이 다르지 않나?" | 맞음. 초기 5억원이면 2015\\~ 세후 CAGR 24.6%, 2001\\~ 17.4% (⓪-2). 공제 250만원이 고정 금액이라 투자금이 클수록 세금 비중이 커짐. 장기 계획은 20%대 초중반, 보수적으로 20% 기준 |
| "이 수익률이면 월 800만원 인출이 되나?" | 초기 5억원 기준 2001\\~2015년 시작은 모두 6\\~11년차 고갈. 장기 데이터 기준 안전선은 월 350\\~450만원, 하락 시 25% 절감 규칙을 쓰면 450\\~600만원 (⓪-2) |
| "다른 전략(CDS·매크로 레짐)을 섞으면 더 안정적이지 않나?" | 둘 다 검증 후 폐기. CDS는 전략 A의 열위 버전(상관 0.75), 매크로 레짐은 25% 섞으면 CAGR -4\\~5%p에 MDD 개선 2\\~4%p뿐 (⓪-2) |
""")

    with st.expander("⑦ 개선 작업 진행 내용", expanded=False):
        st.markdown("""
| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 전략 C 배당수익률 Z-Score 구현 → 실데이터 검증 → 효과 없어 제거 | ✅ 완료 |
| 2 | 전략 B 가중 완화·변동성 타깃팅 구현 → 검증 → 제거 | ✅ 완료 |
| 3 | 혼합 안전장치 검증 → VIX 제거, 비중 상한·하드스탑 유지 (하드스탑은 2026-10-04 제거) | ✅ 완료 |
| 4 | 정리 후 4개 엔진이 원본과 일치하는지 최종 검증 | ✅ 완료 |
| 5 | 화면 개선: 시작일 2015 기본, 탭 상단 고정, 월별 비중 33.3% 표기, 합계(A+B+C) 열, 비중 분배 표, 낙폭 확대 슬라이더, 일별 수익률 실시간 모니터 | ✅ 완료 |
| 6 | 자산 계산기: 전략별 실측 CAGR 퀵 프리셋 연동, 초기값 설정 | ✅ 완료 |
| 7 | 이 보고서를 혼합전략 최하단에 배치 | ✅ 완료 |
| 8 | 상장 전 구간 백필 데이터 구축(2000\\~): 뮤추얼펀드·지수 프록시, 레버리지·인버스 합성(차입비용 반영), 시작일 2004·2000 옵션 | ✅ 완료 |
| 9 | 슬리피지 0.2%·양도세 22%(이듬해 6월 말 납부) 기본 반영 + 설정 패널, 양도세 이중공제 오류 수정 | ✅ 완료 |
| 10 | 월중 하드스탑 제거 (여러 구간·임계치에서 효과 불일치), 비중 상한만 선택형으로 유지. 일별 수익률 모니터는 유지 | ✅ 완료 |
| 11 | 화면·기능 개선: 비용 설정·매크로 시황판을 탭 아래로, 비중 분배·목표 수량 계산기 테두리 상자, 월별 수익률 1\\~12월 표기, 드로우다운 Top 10 주요 이슈, 인쇄/PDF 저장, 접속 비밀번호(선택), 나스닥100 지연 로딩 | ✅ 완료 |
| 12 | 낙폭 히스토리 슬라이더가 백테스트 기간 변경을 반영하지 않던 문제 수정 | ✅ 완료 |
| 13 | 벤치마크 QQQ에도 같은 비용·세금 반영(처음 매수 슬리피지, 매도 시 1회 양도세 평가) → 전략과 같은 조건으로 비교 | ✅ 완료 |
| 14 | 비용·세금 전/후 비교 표 추가: 샤프 하락 원인(6월 일시 납부 세금이 변동성을 키움)을 단계별로 분해 | ✅ 완료 |
| 15 | 전략 C 배당수익률을 SPY 실제 종가(배당 미조정) 기준으로 정정, 기준선 민감도 확인 | ✅ 완료 (2026-10-05) |
| 16 | 추가 검증: 전략 C 방어 보완 3안(미적용), 자산 목록 사후 선택 점검, 반도체·모멘텀 ETF 비교 | ✅ 완료 (2026-10-05) |
| 17 | 인출 계획 백테스트(초기 5억원·월 생활비·물가 3%), 초기 투자금별 세후 CAGR 확인 | ✅ 완료 (2026-10-05) |
| 18 | 다른 전략 검증: 코어 디펜더(CDS)·매크로 레짐 → 둘 다 폐기 | ✅ 완료 (2026-10-05) |
| 19 | 미국 ETF 랭킹 3가지 보기(전략 자산 랭킹·섹터·테마 현황·시장 위험 신호판) | ✅ 완료 (2026-10-05) |
| 20 | 자료실: 별도 페이지·슬라이드 뷰어·INSIGHTS 탭·문서 고정 순서, PDF 변환·삭제·업로드 자동화(git) | ✅ 완료 (2026-10-11) |
| 21 | 미국 주식 랭킹: 나스닥100·S&P500·KOSPI200(테스트) 선택, 종목 검색, 상위 50 순위표 | ✅ 완료 (2026-10-13) |
| 22 | 개별 종목 보유 기준 백테스트 → 200일선 −3% 매도·+5% 재매수 채택, 목표가·중기 손절 제거, 종목 차트·추세 배지 | ✅ 완료 (2026-10-13) |
| 23 | QQQ 낙폭 대응 규칙 백테스트(세전·세후) → 'QQQ를 장기 보유하려면\\~' 섹션 | ✅ 완료 (2026-10-13) |
| 24 | 코스피200 규칙 백테스트 → 매매 기준 없이 랭킹·추세만 표시 | ✅ 완료 (2026-10-13) |
| 25 | 미국 ETF 랭킹 🧮 시장 밸류에이션(5개 지표, 참고용) | ✅ 완료 (2026-10-13) |
| 26 | 자료실 전체화면 확대, 휴대폰 📤 올리기·추가·지우기(GitHub API) | ✅ 완료 (2026-10-14) |
| 27 | 혼합전략 탭 '월말 리밸런싱 역사' 제거, 목표 수량 계산기 만원 단위 | ✅ 완료 (2026-10-12) |
| 28 | 비트코인 장기 보유 규칙 백테스트(120일선 + 반감기 사이클 분할, 적립식) → '📘 비트코인을 장기 보유하려면\\~' | ✅ 완료 (2026-10-14) |
| 29 | ETF 49개 보유 기준 백테스트 → ETF 종류별 기준, 🔎 ETF 검색 · 🔎 미국 주식 종목 찾기, KOSPI200 숨김 | ✅ 완료 (2026-10-15) |
| 30 | 미국 ETF 랭킹 🩺 시장위험진단(비교표·지금 진단·3 × 3 판단표·규칙 밖 결정) | ✅ 완료 (2026-10-15) |
| 31 | 🔧 관리자 모드(선언문·관심 종목·보유 현황·MSTR 매매·내 백테스트 결과), `watchlist-data` 브랜치 저장, `OWNER_PASSWORD`·방문자 수 개편 | ✅ 완료 (2026-10-15\\~16) |
| 32 | S&P500 200일선 +5\\~10% 전략: 시장 필터·재돌파·TIP 카나리아·종목 범위 → 추천 '재돌파 · SPY↓ 신규매수 중단 · 15종목 · +5%근접순' | ✅ 완료 (2026-10-16) |
| 33 | MSTR 규칙 확정(반반 신호 · 사이클 · 변동성 80%), 신호판·LOC 지정가·수량, 장부(실제·샘플 A·B, 추가 입금), '📘 MSTR로 대신하려면\\~' 섹션 정리 | ✅ 완료 (2026-10-20) |
| 34 | 💸 수수료·세금 빠른 전환, 일별 수익률 -10% 기준선 삭제, 목표 수량 계산기 입력 오류 수정·목돈 읽는 법, 태블릿용 라디오 교체 | ✅ 완료 (2026-10-14\\~20) |
| 35 | S&P500 재돌파 선정 종목 월말 갱신 · `use_container_width`·`components.html` 교체 · 관리자 모드 별도 페이지(선택) | ⏳ 남음 |
""")

    with st.expander("⑧ 한계와 유의사항", expanded=False):
        st.markdown("""
- 모든 결과는 표본 내(in-sample) 성과이며 CAGR이 매우 높아 과최적화·생존편향 가능성이 있습니다.
- 현금 수익률 0%, 월간 데이터 기준입니다. 슬리피지(0.2%/회)와 양도세(22%)는 기본 반영되며 '2026 혼합전략' 탭 상단의 '⚙️ 백테스트 비용·세금 반영 설정'에서 끄거나 바꿀 수 있습니다. 환전 비용·수수료는 반영하지 않았고, 양도세는 계좌 NAV 기준 단순 계산입니다(손실 이월공제 없음).
- 상장이 늦은 자산(UPRO·TYD 등 레버리지, QTUM·QQQM·OILK·PDBC 등)의 상장 전 구간은 대체·합성 데이터입니다. OILK→XLE(주식), PDBC→GLD처럼 성격이 다른 대용품이 있어 2015년 이전과 일부 초기 구간 결과는 참고용입니다.
- 전략 C 배당수익률은 2026-10-05부터 SPY 실제 종가(배당 미조정)로 나눠 계산합니다. 이전에는 수정주가로 나눠 과거 값이 부풀려졌습니다(2000-03 수정주가 1.59% vs 실제 0.99%). 정정 후 2016\\~ 혼합 CAGR은 37.6%→36.9%로 소폭 낮아졌고 MDD는 같으며, 닷컴 구간(2000\\~2002)에 방어 신호가 정상적으로 나옵니다.
- (제거 전 검증) 하드스탑은 최근 6\\~7회만 발동한 표본이라 2000·2008년급 붕괴에서의 효과는 검증되지 않았습니다.
- 세후 수익률은 초기 투자금에 따라 달라집니다. ⓪은 초기 1,000만원 기준이며, 5억원이면 같은 구간에서 약 6%p 낮습니다(⓪-2).
- ①\\~⑥의 수치는 2026-10-01 시점의 검증값이고, 최신 수치는 ⓪입니다. 새 데이터가 쌓이면 달라질 수 있습니다.
- ⓪-4의 개별 종목 규칙 백테스트는 현재 지수 구성 종목만 써서 생존편향이 있고, 나스닥100·S&P500 결과는 세금을 반영하지 않았습니다. 시장 밸류에이션의 판정 기준값은 검증하지 않은 참고값입니다.
- ⓪-5의 위성 전략(비트코인·MSTR·S&P500 재돌파)은 모두 세금 미반영입니다. MSTR은 표본이 약 6년(사이클 1.5번)뿐이고, 반감기 사이클 근거는 과거 3번뿐이며, S&P500 재돌파는 현재 구성 종목만 써서 생존편향이 있습니다. 🩺 시장위험진단의 판정 기준도 검증하지 않은 참고값입니다.
""")
        _dy_now = globals().get("realtime_dy")
        if isinstance(_dy_now, (int, float)):
            st.markdown(f"- 현재 SPY 배당수익률은 {_dy_now:.2f}%로, 전략 C는 고정 기준선(1.33%) 방식에서 {'공격' if _dy_now > 1.33 else '방어'} 신호입니다.")


with st.spinner("야후 파이낸스 실시간 데이터를 통합 집계 중..."):
    try:
        df_all = get_all_financial_data_v2(ALL_TICKERS)
    except Exception:
        df_all = pd.DataFrame(columns=["Ticker"])

if df_all.empty or "TIP" not in df_all["Ticker"].values:
    st.error("핵심 데이터 로딩에 실패했습니다. 야후 파이낸스가 일시적으로 요청을 제한했을 수 있습니다. "
             "1\\~2분 뒤 새로고침해 주세요. 계속 실패하면 명령창에서 `pip install -U yfinance` 로 업데이트해 주세요.")
    if st.button("🔄 다시 불러오기"):
        st.rerun()
else:
    data_dict = df_all.set_index("Ticker").to_dict(orient="index")
    
    with st.spinner("지난 12개월(최근 1년) 월말 포트폴리오 데이터를 로딩 및 역동 연산 중..."):
        hist_prices, spy_divs_hist = get_historical_simulation_data(ALL_TICKERS)
    
    # TIP 데이터 추출
    tip_data = data_dict.get("TIP", {})
    tip_closes = tip_data.get("raw_closes", [])
    tip_current = tip_data.get("현재가", 0.0)
    
    # 최근 11개 월간 종가 평균 계산
    tip_last11 = tip_closes[-11:] if len(tip_closes) >= 11 else tip_closes
    tip_ma11 = sum(tip_last11) / len(tip_last11) if tip_last11 else 1.0
    tip_ratio = tip_current / tip_ma11 if tip_ma11 > 0 else 1.0
    is_attack_a = tip_ratio > 1.0

    # 전략 B 카나리아 신호 계산
    tip_score_b = (tip_data.get("1M", 0.0) + tip_data.get("3M", 0.0) + tip_data.get("6M", 0.0) + tip_data.get("9M", 0.0) + tip_data.get("12M", 0.0)) / 5
    is_attack_b = tip_score_b > 0

    # S&P 500 실시간 배당수익률 산출 및 시그널 매핑
    realtime_dy = get_sp500_dividend_yield()
    is_attack_c = realtime_dy > 1.33
    
    c_home = st.container()      # 🏠 홈 카드 (탭 위) — 내용은 아래에서 비중 계산이 끝난 뒤 채움
    tab_2026, tab_a, tab_b, tab_c, tab_mstr, tab_rank, tab_ndx, tab_mdd, tab_lib, tab_calc = st.tabs([
        "🏆 2026 혼합전략", 
        "🛡️ 전략 A", 
        "⚡ 전략 B", 
        "🔄 전략 C",
        "🪙 MSTR",
        "미국 ETF",  # 국기 이모지는 윈도우에서 "us" 글자로 보여 제거
        "🏢 미국 주식",
        "📉 MDD",
        "📚 자료실",
        "🧮 계산기"
    ], key="main_tabs", on_change="rerun")   # 탭 상태 추적: MSTR 탭은 열렸을 때만 시세를 받음 (tab_mstr.open)


    # 용어 설명 팝업: 마우스는 올리면, 폰은 탭하면 표시 (다른 곳을 탭하면 닫힘)
    components.html("""
<script>
(function () {
  var win = window.parent, doc = win.document;
  try { if (win.__glOff) { win.__glOff(); } } catch (e) {}
  var pop = doc.getElementById('gl-pop');
  if (!pop) {
    pop = doc.createElement('div'); pop.id = 'gl-pop';
    pop.style.cssText = 'position:fixed;z-index:100000;display:none;background:#1e293b;color:#f8fafc;padding:8px 10px;border-radius:8px;font-size:13px;line-height:1.5;font-weight:400;white-space:pre-line;word-break:keep-all;box-shadow:0 6px 18px rgba(15,23,42,.35);pointer-events:none;';
    doc.body.appendChild(pop);
  }
  var cur = null, ptype = 'mouse';
  function tgt(e) { return e.target && e.target.closest ? e.target.closest('.gl') : null; }
  function show(el) {
    var t = el.getAttribute('data-tip'); if (!t) { return; }
    pop.textContent = t; pop.style.display = 'block';
    pop.style.maxWidth = Math.min(280, win.innerWidth - 16) + 'px';
    var r = el.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    var x = Math.max(8, Math.min(r.left, win.innerWidth - w - 8));
    var y = r.bottom + 6; if (y + h > win.innerHeight - 8) { y = Math.max(8, r.top - h - 6); }
    pop.style.left = x + 'px'; pop.style.top = y + 'px'; cur = el;
  }
  function hide() { pop.style.display = 'none'; cur = null; }
  // 차트(Altair/Vega) 말풍선: 폰에서 터치하면 생긴 뒤 저절로 안 사라져 화면을 따라다니는 문제 → 스크롤·다른 곳 터치 시 숨김
  function hideVg() {
    doc.querySelectorAll('#vg-tooltip-element, .vg-tooltip').forEach(function (v) { v.classList.remove('visible'); });
  }
  function onDown(e) {
    ptype = e.pointerType || 'mouse'; if (!tgt(e)) { hide(); }
    if (ptype !== 'mouse' && !(e.target && e.target.closest && e.target.closest('.vega-embed'))) { hideVg(); }
  }
  function onScrollAll() { hide(); if (ptype !== 'mouse') { hideVg(); } }
  function onOver(e) { if (ptype !== 'mouse') { return; } var el = tgt(e); if (el) { show(el); } }
  function onOut(e) { if (ptype !== 'mouse') { return; } if (tgt(e)) { hide(); } }
  function onClick(e) { if (ptype === 'mouse') { return; } var el = tgt(e); if (!el) { return; } if (cur === el) { hide(); } else { show(el); } }
  doc.addEventListener('pointerdown', onDown, true);
  doc.addEventListener('mouseover', onOver, true);
  doc.addEventListener('mouseout', onOut, true);
  doc.addEventListener('click', onClick, true);
  win.addEventListener('scroll', onScrollAll, true);
  doc.addEventListener('touchmove', hideVg, { capture: true, passive: true });
  // '(만원' 이 들어간 금액 입력칸: 입력하는 즉시 천단위 콤마 삽입 (예: 50000 → 50,000)
  var nativeSet = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
  function onMoneyInput(e) {
    var el = e.target;
    // 숫자 전용 칸(type=number, 예: 목표 수량 계산기)은 콤마를 넣으면 값이 지워지므로 건드리지 않음
    if (!el || el.tagName !== 'INPUT' || el.type === 'number' || (el.getAttribute('aria-label') || '').indexOf('(만원') < 0) { return; }
    var raw = el.value, pos = el.selectionStart || 0;
    var before = raw.slice(0, pos).replace(/[^0-9]/g, '').length;
    var digits = raw.replace(/[^0-9]/g, '').slice(0, 9);
    var f = digits ? Number(digits).toLocaleString('en-US') : '';
    if (f !== raw) {
      nativeSet.call(el, f);
      el.dispatchEvent(new win.Event('input', { bubbles: true }));
      var cnt = 0, np = 0;
      while (np < f.length && cnt < before) { if (/[0-9]/.test(f.charAt(np))) { cnt++; } np++; }
      try { el.setSelectionRange(np, np); } catch (err) {}
    }
  }
  doc.addEventListener('input', onMoneyInput, true);
  var mt = null;
  function markCost() {
    doc.querySelectorAll('[data-testid="stExpander"]').forEach(function (e) {
      var sm = e.querySelector('summary');
      if (sm && sm.textContent.indexOf('백테스트 비용·세금') >= 0) { e.classList.add('cost-exp'); }
    });
    doc.querySelectorAll('input[aria-label*="(만원"]').forEach(function (i) {
      if (i.getAttribute('inputmode') !== 'numeric') { i.setAttribute('inputmode', 'numeric'); }  // 폰에서 숫자 키패드
    });
  }
  markCost();
  var mo = new win.MutationObserver(function () { if (mt) { win.clearTimeout(mt); } mt = win.setTimeout(markCost, 200); });
  mo.observe(doc.body, { childList: true, subtree: true });
  win.__glOff = function () {
    doc.removeEventListener('pointerdown', onDown, true); doc.removeEventListener('mouseover', onOver, true);
    doc.removeEventListener('mouseout', onOut, true); doc.removeEventListener('click', onClick, true);
    win.removeEventListener('scroll', onScrollAll, true);
    doc.removeEventListener('touchmove', hideVg, { capture: true });
    mo.disconnect();
    doc.removeEventListener('input', onMoneyInput, true);
  };
})();
</script>
""", height=0)

    # 스크롤해도 전략 탭 메뉴(혼합전략/A/B/C/ETF 랭킹/자산 계산기)가 화면 상단에 고정되도록 함
    components.html("""
<script>
(function () {
  var win = window.parent, doc = win.document;
  if (win.__tabStickyTimer) { win.clearInterval(win.__tabStickyTimer); }
  var PROPS = ['position', 'top', 'left', 'width', 'z-index', 'box-shadow', 'box-sizing', 'background-color', 'padding-top', 'padding-bottom'];
  function headerH() {
    var h = doc.querySelector('[data-testid="stHeader"]');
    return h ? h.getBoundingClientRect().height : 0;
  }
  function update() {
    var tl = doc.querySelector('.stTabs [role="tablist"]') || doc.querySelector('[role="tablist"]') || doc.querySelector('[data-baseweb="tab-list"]');
    if (!tl || !tl.parentNode) { return; }
    var ph = doc.getElementById('tab-sticky-ph');
    if (!ph || !ph.isConnected || ph.nextSibling !== tl) {
      if (ph) { ph.remove(); }
      ph = doc.createElement('div');
      ph.id = 'tab-sticky-ph';
      tl.parentNode.insertBefore(ph, tl);
    }
    var N_STRAT = 5;  // 앞 5개 탭(혼합전략·A·B·C·MSTR)이 '전략' 그룹, 나머지는 '정보' 그룹
    var tabs = tl.querySelectorAll('[role="tab"]');
    for (var i = 0; i < tabs.length; i++) {
      var g = i < N_STRAT ? 's' : 'i';
      var f = (i === 0 || i === N_STRAT) ? '1' : '0';
      if (tabs[i].getAttribute('data-grp') !== g) { tabs[i].setAttribute('data-grp', g); }
      if (tabs[i].getAttribute('data-first') !== f) { tabs[i].setAttribute('data-first', f); }
    }
    if (tabs.length > N_STRAT) {
      var ge = tabs[0].parentElement;  // 모든 탭을 직접 담고 있는 가장 가까운 공통 부모
      while (ge && !ge.contains(tabs[tabs.length - 1])) { ge = ge.parentElement; }
      if (ge) {
        if (!ge.classList.contains('tab-grid')) { ge.classList.add('tab-grid'); }
        doc.querySelectorAll('.tab-grp-label').forEach(function (e) { if (e.parentElement !== ge) { e.remove(); } });  // 이전 버전이 남긴 라벨 정리
        if (ge.querySelectorAll(':scope > .tab-grp-label').length !== 2) {
          ge.querySelectorAll(':scope > .tab-grp-label').forEach(function (e) { e.remove(); });
          var lbI = doc.createElement('div'); lbI.className = 'tab-grp-label i'; lbI.textContent = 'INSIGHTS';
          var lbS = doc.createElement('div'); lbS.className = 'tab-grp-label s'; lbS.textContent = 'STRATEGY';
          ge.insertBefore(lbI, ge.firstChild);
          ge.insertBefore(lbS, ge.firstChild);
        }
      }
    }
    var top = headerH();
    var r = ph.getBoundingClientRect();
    if (r.top <= top) {
      ph.style.height = (tl.offsetHeight + 20) + 'px';
      tl.style.setProperty('position', 'fixed', 'important');
      tl.style.setProperty('top', top + 'px', 'important');
      tl.style.setProperty('left', r.left + 'px', 'important');
      tl.style.setProperty('width', r.width + 'px', 'important');
      tl.style.setProperty('box-sizing', 'border-box', 'important');
      tl.style.setProperty('background-color', '#f8fafc', 'important');
      tl.style.setProperty('z-index', '999', 'important');
      tl.style.setProperty('box-shadow', '0 6px 14px -4px rgba(15,23,42,0.35)', 'important');
    } else {
      ph.style.height = '0px';
      PROPS.forEach(function (p) { tl.style.removeProperty(p); });
    }
  }
  win.__tabStickyTimer = win.setInterval(update, 100);
  update();
})();
</script>
""", height=0)

    # 인쇄/PDF 저장 직전: 화면에 고정된 요소(모든 쪽에 반복 인쇄되는 아이콘 등)를 잠시 숨김
    components.html("""
<script>
(function () {
  var win = window.parent, doc = win.document;
  if (win.__prtBefore) { win.removeEventListener('beforeprint', win.__prtBefore); }
  if (win.__prtAfter) { win.removeEventListener('afterprint', win.__prtAfter); }
  var hidden = [];
  function hideEl(el) {
    hidden.push([el, el.style.getPropertyValue('display'), el.style.getPropertyPriority('display')]);
    el.style.setProperty('display', 'none', 'important');
  }
  function hideBetween(name) {
    var s = doc.querySelector('.print-skip-' + name + '-start');
    var e = doc.querySelector('.print-skip-' + name + '-end');
    if (!s || !e) { return; }
    var sel = '[data-testid="stElementContainer"], .element-container';
    var c1 = s.closest(sel), c2 = e.closest(sel);
    if (!c1 || !c2) { return; }
    var el = c1.nextElementSibling, guard = 0;
    while (el && el !== c2 && guard < 500) { hideEl(el); el = el.nextElementSibling; guard++; }
  }
  function before() {
    hidden = [];
    try { hideBetween('a'); hideBetween('b'); hideBetween('c'); } catch (e) {}
    try {
      doc.querySelectorAll('body *').forEach(function (el) {
        var cs = win.getComputedStyle(el);
        if (cs.position === 'fixed' && cs.display !== 'none') {
          hidden.push([el, el.style.getPropertyValue('display'), el.style.getPropertyPriority('display')]);
          el.style.setProperty('display', 'none', 'important');
        }
      });
    } catch (e) {}
  }
  function after() {
    hidden.forEach(function (h) {
      h[0].style.removeProperty('display');
      if (h[1]) { h[0].style.setProperty('display', h[1], h[2]); }
    });
    hidden = [];
  }
  win.__prtBefore = before; win.__prtAfter = after;
  win.addEventListener('beforeprint', before);
  win.addEventListener('afterprint', after);
})();
</script>
""", height=0)

    with tab_2026:
        c_2026 = st.container()
    with tab_a:
        c_a = st.container()
    with tab_b:
        c_b = st.container()
    with tab_c:
        c_c = st.container()
    with tab_mstr:
        c_mstr = st.container()
    with tab_rank:
        c_rank = st.container()
    with tab_ndx:
        c_ndx = st.container()
    with tab_mdd:
        c_mdd = st.container()
    with tab_lib:
        # 슬라이드 뷰어는 무거워서 탭이 아닌 별도 페이지(pages/9_library.py)에 둠 → 여기선 안내와 이동 단추만
        st.markdown("#### 📚 자료실")
        st.markdown("투자 공부용 PDF·인포그래픽 슬라이드 모음입니다. "
                    "좌우로 밀거나 ‹ › 단추로 넘기고, 휴대폰에서는 ⛶ 단추로 가로 전체화면으로 볼 수 있습니다.")
        # 자료실 열기 단추: 빨간 기본색 대신 INSIGHTS 그룹과 같은 청록색
        st.markdown("""<style>
.st-key-open_library button { background-color:#0f766e !important; border-color:#0f766e !important; color:#ffffff !important; font-weight:700 !important; }
.st-key-open_library button:hover { background-color:#115e59 !important; border-color:#115e59 !important; }
.st-key-open_library button p { color:#ffffff !important; }
</style>""", unsafe_allow_html=True)
        if st.button("📚 자료실 열기", use_container_width=True, key="open_library"):
            st.switch_page("pages/9_library.py")
        # 문서 목록: 한 줄에 하나씩, 칸 안에서 스크롤. 이름을 누르면 그 문서가 선택된 채로 자료실이 열림
        try:
            import unicodedata as _ud
            _docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
            _doc_names = [_ud.normalize("NFC", d) for d in os.listdir(_docs_dir)
                          if os.path.isdir(os.path.join(_docs_dir, d))]
            # 고정 순서: docs/_pinned.txt (자료실 페이지와 같은 파일 사용)
            try:
                with open(os.path.join(_docs_dir, "_pinned.txt"), encoding="utf-8-sig") as _f:
                    _pin = [_ud.normalize("NFC", l.strip()) for l in _f
                            if l.strip() and not l.strip().startswith("#")]
            except Exception:
                _pin = []
            # 순서: ① 휴대폰으로 올린 문서(최근 것부터) ② _pinned.txt 고정 문서 ③ 나머지 가나다순 (자료실 페이지와 같음)
            import re as _re2
            def _ph_time(n):
                _f = os.path.join(_docs_dir, n, "_phone_upload.txt")
                if not os.path.exists(_f):
                    # 폴더 이름이 NFD로 저장된 경우 대비
                    _f = os.path.join(_docs_dir, _ud.normalize("NFD", n), "_phone_upload.txt")
                    if not os.path.exists(_f):
                        return None
                try:
                    with open(_f, encoding="utf-8", errors="ignore") as _fh:
                        _m = _re2.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", _fh.read())
                    return _m.group(1) if _m else "0000"
                except Exception:
                    return "0000"
            _pt = {n: _ph_time(n) for n in _doc_names}
            _ph = sorted([n for n in _doc_names if _pt[n]], key=lambda n: _pt[n], reverse=True)
            _rs = sorted([n for n in _doc_names if not _pt[n]], key=lambda n: (_pin.index(n) if n in _pin else len(_pin), n))
            _doc_names = _ph + _rs
            # '인포그래픽'은 항상 맨 위 (휴대폰으로 올린 최신 문서보다도 위)
            _always_top = [n for n in ("인포그래픽",) if n in _doc_names]
            _doc_names = _always_top + [n for n in _doc_names if n not in _always_top]
        except Exception:
            _doc_names = []
        if _doc_names:
            st.markdown(
                f"<div style='font-size:0.88rem;color:#475569;margin:10px 0 4px'>문서 {len(_doc_names)}개 "
                f"<span style='color:#0f766e'>· 이름을 누르면 그 문서가 바로 열립니다</span></div>",
                unsafe_allow_html=True)
            st.markdown("""<style>
[class*="st-key-libdoc_"] button { width:100% !important; background:#ffffff !important; border:none !important;
  border-bottom:1px solid #e2e8f0 !important; border-radius:0 !important; padding:6px 10px !important;
  min-height:0 !important; justify-content:flex-start !important; color:#334155 !important; }
[class*="st-key-libdoc_"] button:hover { background:#f0fdfa !important; color:#0f766e !important; }
[class*="st-key-libdoc_"] button > div { width:100% !important; justify-content:flex-start !important; }
[class*="st-key-libdoc_"] button p { text-align:left !important; font-size:0.88rem !important; white-space:nowrap !important;
  overflow:hidden !important; text-overflow:ellipsis !important; }
.st-key-libdoc_list, .st-key-libdoc_list [data-testid="stVerticalBlock"] { gap:0 !important; }
</style>""", unsafe_allow_html=True)
            try:
                _box = st.container(height=280, border=True, key="libdoc_list")
            except TypeError:  # 예전 Streamlit은 container에 key가 없음
                _box = st.container(height=280, border=True)
            with _box:
                for _i, _n in enumerate(_doc_names, 1):
                    if st.button(f"{_i}.  {_n}", key=f"libdoc_{_i}", use_container_width=True):
                        st.session_state["library_open_doc"] = _n   # 자료실 페이지가 이 문서를 먼저 선택
                        st.switch_page("pages/9_library.py")
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        render_watchlist()      # 🔧 관리자 모드 (관심 종목) — 자료실 탭 맨 아래
    with tab_calc:
        c_calc = st.container()

    # [전략 A 할당 산출]
    alloc_a = {}
    if is_attack_a:
        df_off_a = df_all[df_all["Ticker"].isin(OFFENSIVE_A)].copy()
        if not df_off_a.empty:
            df_off_a = df_off_a.sort_values(by="A_공격스코어", ascending=False)
            top_4_a = df_off_a.head(4)
            for _, r in top_4_a.iterrows():
                alloc_a[r["Ticker"]] = 25.0
        else:
            alloc_a["CASH (현금)"] = 100.0
    else:
        df_def_a = df_all[df_all["Ticker"].isin(DEFENSIVE_A)].copy()
        if not df_def_a.empty:
            df_def_a = df_def_a.sort_values(by="A_방어스코어", ascending=False)
            top_1_a = df_def_a.iloc[0]
            if top_1_a["A_방어스코어"] > 0:
                alloc_a[top_1_a["Ticker"]] = 100.0
            else:
                alloc_a["CASH (현금)"] = 100.0
        else:
            alloc_a["CASH (현금)"] = 100.0

    # [전략 B 할당 산출]
    alloc_b = {}
    if is_attack_b:
        df_off_b = df_all[df_all["Ticker"].isin(OFFENSIVE_B)].copy()
        if not df_off_b.empty:
            df_off_b = df_off_b.sort_values(by="B_공격스코어", ascending=False)
            top_1_b = df_off_b.iloc[0]
            alloc_b[top_1_b["Ticker"]] = 100.0
        else:
            alloc_b["CASH (현금)"] = 100.0
    else:
        df_def_b = df_all[df_all["Ticker"].isin(DEFENSIVE_B)].copy()
        if not df_def_b.empty:
            df_def_b = df_def_b.sort_values(by="5M", ascending=False)
            top_1_b_def = df_def_b.iloc[0]
            if top_1_b_def["B_단순모멘텀"] > 0:
                alloc_b[top_1_b_def["Ticker"]] = 100.0
            else:
                alloc_b["CASH (현금)"] = 100.0
        else:
            alloc_b["CASH (현금)"] = 100.0

    # [전략 C 할당 산출]
    alloc_c = {}
    if is_attack_c:
        df_off_c = df_all[df_all["Ticker"].isin(OFFENSIVE_C)].copy()
        if not df_off_c.empty:
            df_off_c = df_off_c.sort_values(by="A_공격스코어", ascending=False)
            top_1_c = df_off_c.iloc[0]
            alloc_c[top_1_c["Ticker"]] = 100.0
        else:
            alloc_c["CASH (현금)"] = 100.0
    else:
        df_def_c = df_all[df_all["Ticker"].isin(DEFENSIVE_C)].copy()
        if not df_def_c.empty:
            df_def_c = df_def_c.sort_values(by="A_방어스코어", ascending=False)
            top_1_c_def = df_def_c.iloc[0]
            if top_1_c_def["A_방어스코어"] > 0:
                alloc_c[top_1_c_def["Ticker"]] = 100.0
            else:
                alloc_c["CASH (현금)"] = 100.0
        else:
            alloc_c["CASH (현금)"] = 100.0

    combined_alloc = {}
    contributions = {}

    def add_to_combined(alloc_dict, strategy_weight, strategy_name, mode_status):
        for ticker, asset_weight in alloc_dict.items():
            effective_weight = (asset_weight / 100.0) * strategy_weight
            combined_alloc[ticker] = combined_alloc.get(ticker, 0.0) + effective_weight
            
            if ticker not in contributions:
                contributions[ticker] = []
            contributions[ticker].append(f"{strategy_name} ({mode_status})")

    sig_a = "공격" if is_attack_a else "방어"
    sig_b = "공격" if is_attack_b else "방어"
    sig_c = "공격" if is_attack_c else "방어"

    add_to_combined(alloc_a, 33.333, "전략 A", sig_a)
    add_to_combined(alloc_b, 33.333, "전략 B", sig_b)
    add_to_combined(alloc_c, 33.333, "전략 C", sig_c)

    # 백테스트 설정의 '비중 상한' 체크박스가 켜져 있으면 실시간 비중에도 동일하게 적용 (초과분은 현금)
    live_cap_on = cap_on_setting()
    live_cap_pct = float(st.session_state.get("mix_cap_pct", 35.0))
    live_cap_hit, live_cap_excess = {}, 0.0
    if live_cap_on:
        combined_alloc, live_cap_hit, live_cap_excess = apply_weight_cap(combined_alloc, live_cap_pct)
        for _t, (_w0, _w1) in live_cap_hit.items():
            contributions[_t] = contributions.get(_t, []) + [f"📐 상한 {live_cap_pct:.0f}% 적용"]
        if live_cap_excess > 0:
            contributions["CASH (현금)"] = contributions.get("CASH (현금)", []) + ["📐 비중 상한 초과분"]

    # 🏠 홈 카드 (탭 위) — 실시간 비중 계산이 끝난 뒤 채움. SHOW_HOME = False 면 표시하지 않음
    if SHOW_HOME:
        with c_home:
            try:
                render_home(combined_alloc, is_attack_a, is_attack_b, is_attack_c)
            except Exception as _e_home:
                st.caption(f"홈 카드를 표시하지 못했습니다: {_e_home}")

    mix_data = []
    for ticker, weight in combined_alloc.items():
        if weight > 0.01:
            price = data_dict.get(ticker, {}).get("현재가", 1.0) if ticker != "CASH (현금)" else 1.0
            mix_data.append({
                "자산군 (Ticker)": ticker,
                "현재가 ($)": f"${price:.2f}" if ticker != "CASH (현금)" else "-",
                "배분 비중 (%)": round(weight, 2),
                "선택 근거 (참여 전략)": " + ".join(contributions[ticker])
            })
    df_mix = pd.DataFrame(mix_data).sort_values(by="배분 비중 (%)", ascending=False)

    # [선택 근거 상세] 각 전략이 어떤 기준·값으로 자산을 골랐는지 정리 (표시 전용, 배분 계산에는 영향 없음)
    basis_notes = {}

    def _note(ticker, text):
        basis_notes.setdefault(ticker, []).append(text)

    def _top_rows(tickers, col, n=1):
        return df_all[df_all["Ticker"].isin(tickers)].sort_values(by=col, ascending=False).head(n)

    # 전략 A
    if is_attack_a:
        for _rank, (_, _r) in enumerate(_top_rows(OFFENSIVE_A, "A_공격스코어", 4).iterrows(), start=1):
            _note(_r["Ticker"], f"A·공격: 공격스코어 {_rank}위 ({_r['A_공격스코어']:+.2f}%)")
    else:
        _d = _top_rows(DEFENSIVE_A, "A_방어스코어", 1)
        if not _d.empty:
            _r = _d.iloc[0]
            if _r["A_방어스코어"] > 0:
                _note(_r["Ticker"], f"A·방어: 방어스코어 1위 ({_r['A_방어스코어']:+.2f}%)")
            else:
                _note("CASH (현금)", f"A·방어: 1위 {_r['Ticker']} 방어스코어 {_r['A_방어스코어']:+.2f}% ≤ 0 → 현금")
    # 전략 B
    if is_attack_b:
        _d = _top_rows(OFFENSIVE_B, "B_공격스코어", 1)
        if not _d.empty:
            _r = _d.iloc[0]
            _note(_r["Ticker"], f"B·공격: 가중모멘텀 1위 ({_r['B_공격스코어']:+.2f}%)")
    else:
        _d = _top_rows(DEFENSIVE_B, "5M", 1)
        if not _d.empty:
            _r = _d.iloc[0]
            if _r["B_단순모멘텀"] > 0:
                _note(_r["Ticker"], f"B·방어: 5개월 수익률 1위 ({_r['5M']:+.1f}%, 단순모멘텀 {_r['B_단순모멘텀']:+.2f}%)")
            else:
                _note("CASH (현금)", f"B·방어: 5개월 1위 {_r['Ticker']} 단순모멘텀 {_r['B_단순모멘텀']:+.2f}% ≤ 0 → 현금")
    # 전략 C
    if is_attack_c:
        _d = _top_rows(OFFENSIVE_C, "A_공격스코어", 1)
        if not _d.empty:
            _r = _d.iloc[0]
            _note(_r["Ticker"], f"C·공격: 공격스코어 1위 ({_r['A_공격스코어']:+.2f}%)")
    else:
        _d = _top_rows(DEFENSIVE_C, "A_방어스코어", 1)
        if not _d.empty:
            _r = _d.iloc[0]
            if _r["A_방어스코어"] > 0:
                _note(_r["Ticker"], f"C·방어: 방어스코어 1위 ({_r['A_방어스코어']:+.2f}%)")
            else:
                _note("CASH (현금)", f"C·방어: 1위 {_r['Ticker']} 방어스코어 {_r['A_방어스코어']:+.2f}% ≤ 0 → 현금")

    for _t, (_w0, _w1) in live_cap_hit.items():
        _note(_t, f"비중 상한: 합산 {_w0:.2f}% → {_w1:.2f}%")
    if live_cap_excess > 0:
        _note("CASH (현금)", f"비중 상한 초과분 +{live_cap_excess:.2f}%p")

    def _ret_txt(ticker, col):
        v = data_dict.get(ticker, {}).get(col)
        return f"{v:+.1f}%" if v is not None and ticker != "CASH (현금)" else "-"

    df_mix_view = pd.DataFrame({
        "자산군": df_mix["자산군 (Ticker)"].values,
        "현재가 ($)": df_mix["현재가 ($)"].values,
        "배분 비중 (%)": df_mix["배분 비중 (%)"].values,
        "참여 전략 (신호)": df_mix["선택 근거 (참여 전략)"].values,
        "선택 기준 · 값": [" | ".join(basis_notes.get(t, ["-"])) for t in df_mix["자산군 (Ticker)"]],
        "1M": [_ret_txt(t, "1M") for t in df_mix["자산군 (Ticker)"]],
        "3M": [_ret_txt(t, "3M") for t in df_mix["자산군 (Ticker)"]],
        "6M": [_ret_txt(t, "6M") for t in df_mix["자산군 (Ticker)"]],
        "12M": [_ret_txt(t, "12M") for t in df_mix["자산군 (Ticker)"]],
    })

    def print_mark(name):
        """인쇄할 때만 영향을 주는 보이지 않는 표식. skip-a/b 시작~끝 사이와 print-end 이후는 인쇄에서 제외."""
        st.markdown(f'<div class="print-hide {name}"></div>', unsafe_allow_html=True)

    def render_print_section(scope, label="🖨️ 이 화면 인쇄 / PDF 저장", with_marker=True):
        """이 지점부터 아래 내용만 인쇄/PDF 저장하는 버튼. (위쪽 내용은 인쇄하는 동안만 숨김)
        - 인쇄 창에서 '대상'을 'PDF로 저장'으로 고르면 파일로 저장됩니다.
        - 버튼이 안 눌리는 브라우저에서는 Ctrl+P(맥: ⌘+P)로도 같은 화면을 인쇄할 수 있습니다."""
        if with_marker:
            st.markdown(f'<div class="print-marker" data-print-scope="{scope}"></div>', unsafe_allow_html=True)
        components.html("""
<style>
  body{margin:0;font-family:sans-serif;}
  button{background:#1e3a8a;color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:14px;font-weight:700;cursor:pointer;}
  button:hover{background:#1d4ed8;}
  span{color:#64748b;font-size:12px;margin-left:10px;}
  @media print{ body{display:none !important;} }
</style>
<button id="pbtn">__LABEL__</button><span>인쇄 창에서 대상을 'PDF로 저장'으로 선택하세요 (안 되면 Ctrl+P)</span>
<script>
document.getElementById('pbtn').addEventListener('click', function () {
  var win = window.parent, doc = win.document, hidden = [];
  try {
    var m = doc.querySelector('.print-marker[data-print-scope="__SCOPE__"]');
    if (m) {
      var c = m.closest('[data-testid="stElementContainer"], .element-container');
      var el = c ? c.previousElementSibling : null;
      while (el) { hidden.push([el, el.style.display]); el.style.setProperty('display', 'none', 'important'); el = el.previousElementSibling; }
    }
  } catch (e) {}
  var done = false;
  function restore() {
    if (done) { return; }
    done = true;
    hidden.forEach(function (h) { h[0].style.removeProperty('display'); if (h[1]) { h[0].style.display = h[1]; } });
    win.removeEventListener('afterprint', restore);
  }
  win.addEventListener('afterprint', restore);
  setTimeout(function () { win.print(); }, 200);
  setTimeout(restore, 180000);
});
</script>
""".replace("__SCOPE__", scope).replace("__LABEL__", label), height=46)

    def render_month_end_history(hist_prices, spy_divs_hist, live_cap_on, live_cap_pct):
        """월말 기준 리밸런싱 포트폴리오 역사 (최근 1년) — 월별 세부 리밸런싱 기록 아래에 표시."""
        if hist_prices and "SPY" in hist_prices:
            st.markdown("---")
            st.markdown("### 📅 월말 기준 리밸런싱 포트폴리오 역사 (최근 1년)")
            st.caption("매월 최종 영업일 마감 데이터를 기준으로 실시간 모멘텀과 시그널을 연산하여, 익월 1일 아침 리밸런싱 시 적용되는 혼합 포트폴리오 구성 비중입니다.")
            
            spy_series = hist_prices["SPY"]
            df_spy_dates = spy_series.to_frame()
            df_spy_dates['year'] = df_spy_dates.index.year
            df_spy_dates['month'] = df_spy_dates.index.month
            
            month_ends = df_spy_dates.groupby(['year', 'month']).apply(lambda x: x.index[-1]).tolist()
            
            now = now_us_eastern()  # 미국 동부 시간 기준 (한국 새벽에 미국 장중인 월말을 '완료'로 잘못 판정하지 않도록)
            completed_month_ends = [d for d in month_ends if not (d.year == now.year and d.month == now.month)]
            completed_12_months = completed_month_ends[-12:]
            completed_12_months.reverse()
            
            col_h1, col_h2 = st.columns(2)
            for idx, date in enumerate(completed_12_months):
                target_col = col_h1 if idx < 6 else col_h2  # 모바일에서 세로로 쌓여도 최신순 유지
                
                # 변수명 재사용 이슈 방지를 위한 hist_sig_a, hist_sig_b, hist_sig_c 구분 수정
                hist_portfolio, hist_sig_a, hist_sig_b, hist_sig_c, dy_c = compute_historical_portfolio_at_month_end(
                    hist_prices, spy_divs_hist, date,
                    OFFENSIVE_A, DEFENSIVE_A, OFFENSIVE_B, DEFENSIVE_B, OFFENSIVE_C, DEFENSIVE_C
                )
                
                date_str = date.strftime("%Y년 %m월 %d일")
                sig_text_a = "🟢 공격" if hist_sig_a else "🛡️ 방어"
                sig_text_b = "🟢 공격" if hist_sig_b else "🛡️ 방어"
                sig_text_c = "🟢 공격" if hist_sig_c else "🛡️ 방어"
                
                with target_col:
                    with st.expander(f"📅 {date_str} 마감 기준 포트폴리오"):
                        sm1, sm2, sm3 = st.columns(3)
                        with sm1:
                            st.caption("전략A 신호")
                            st.markdown(f"**{sig_text_a}**")
                        with sm2:
                            st.caption("전략B 신호")
                            st.markdown(f"**{sig_text_b}**")
                        with sm3:
                            st.caption("전략C 신호")
                            st.markdown(f"**{sig_text_c}**<br/><small>({dy_c:.2f}%)</small>", unsafe_allow_html=True)
                        
                        st.markdown("**포트폴리오 비중:**")
                        _hist_view = apply_weight_cap(hist_portfolio, live_cap_pct)[0] if live_cap_on else hist_portfolio
                        if live_cap_on:
                            st.caption(f"📐 비중 상한 {live_cap_pct:.0f}% 적용")
                        hist_rows = [{"자산명(Ticker)": k, "배분비중 (%)": f"{v:.2f}%"} for k, v in _hist_view.items() if v > 0.005]
                        if hist_rows:
                            st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
                        else:
                            st.write("⚠️ 해당 기간 데이터 부족")

    with c_2026:
        render_cost_settings_panel()
        render_macro_board()
        st.header("🏆 2026년 혼합 전략")
        st.markdown(
            "**🎯 목표: QQQ(나스닥100) 수준의 장기 수익을 추구하면서, 위기 때는 QQQ의 큰 변동성과 최대 낙폭(MDD)을 방어합니다.**\n\n"
            "안정 지향의 **전략 A**, 고수익 레버리지의 **전략 B**, 시황 로테이션인 **전략 C**를 "
            "각각 **33.33%씩 동일 비중**으로 혼합합니다. "
            "상승장에서는 세 전략이 그때의 주도 자산(나스닥·반도체·레버리지 등)에 올라타 QQQ에 버금가는 수익을 노리고, "
            "하락 신호가 오면 각 전략이 채권·금·원자재·현금으로 대피해 QQQ보다 훨씬 얕은 낙폭으로 버팁니다. "
            "세 전략은 서로 다른 신호(A: TIP 실질금리 추세, B: TIP 모멘텀, C: S&P500 배당수익률)로 움직여, "
            "한 전략이 틀려도 나머지가 받쳐 주도록 설계했습니다."
        )
        st.caption("예: 2022년 긴축 발작(2022-01 \\~ 10) 때 QQQ -29.8%, 2026 혼합전략 +29.7% (2026-10-04 검증, 비용·세금 반영). "
                   "과거 성과가 미래 수익을 보장하지 않습니다.")

        with st.expander("📖 2026 혼합전략 명세서", expanded=False):
            st.markdown(r"""
*최종 갱신 2026-10-14*

## 개요

2026 혼합전략은 성격이 다른 3개 동적 자산배분 전략(A 안정형, B 레버리지 공격형, C 섹터로테이션)을 각 33.33% 동일 비중으로 합친 월간 리밸런싱 전략입니다. 벤치마크는 QQQ입니다.

**목표**: QQQ의 장기 성장 수익을 추구하되, 하락장에서의 손실(MDD)을 방어하는 것입니다. 카나리아 신호가 약해지면 공격 자산을 팔고 채권·원자재·인버스 같은 방어 자산이나 현금으로 옮겨, 큰 폭락 때 낙폭을 QQQ보다 작게 만드는 구조입니다.

**백테스트 결과** (2026-10-11 앱 화면 값 · 시작일 2015-01-01 선택 → 2016-02 ~ 2026-10 · 슬리피지 0.2%/회·양도세 22% 반영 · 비중 상한 꺼짐 · 초기 투자금 1,000만원. QQQ도 같은 비용·세금 조건의 세후 값)

| 지표 | 2026 혼합전략 | QQQ (세후) |
| --- | --- | --- |
| 기간 수익률 | 1,640.9% | 533.4% |
| 연환산 수익률 (CAGR) | 30.7% | 18.9% |
| 최대 낙폭 (MDD) | -15.1% (2019-05) | -29.9% (2022-12) |
| 최악의 달 | -15.1% | -12.4% |
| 연 변동성 | 17.4% | 16.7% |
| 샤프 지수 | 1.63 | 1.12 |
| 소티노 지수 | 2.47 | 1.80 |
| 5년 수익률 | 240.1% | 92.1% |
| 연간 턴오버 | 338.8% | 0.0% |

같은 세후 조건에서 혼합전략의 MDD(-15.1%)는 QQQ(-29.9%)의 절반 수준이었고, CAGR은 QQQ보다 약 12%p 높았습니다. 세후 최종 자산은 약 1.74억원(초기 1,000만원)입니다. QQQ에는 처음 매수 시 슬리피지 0.2%, 매도 시 1회 양도세 22%(공제 250만원)를 넣었고, 세전 값은 CAGR 21.2%·MDD -32.6%입니다. 보유 중 낙폭은 매도 시 내야 할 세금도 함께 줄어들어 세전보다 약간 작게 나옵니다. 위 값은 2026-10-05 배당수익률 정정(실제 종가 기준)이 반영된 수치로, 정정 전 2026-10-04 값(CAGR 31.2%)보다 소폭 낮습니다. 위 수치는 시작일·비용 설정·데이터 갱신에 따라 달라지며, 과거 성과가 미래 수익을 보장하지 않습니다.

**초기 투자금과 시작 시점에 따라 세후 수익률이 크게 달라집니다** (2026-10-05 인출계획 검증, 슬리피지 0.2%·양도세 22%·공제 250만원). 양도세 연 공제 250만원은 금액이 고정이라, 투자금이 클수록 세금 비중이 커집니다.

| 시작 (초기 5억원) | 세후 CAGR | MDD | 세전 CAGR | QQQ |
| --- | --- | --- | --- | --- |
| 2001~ | 17.4% | -22.0% | 23.5% | 10.7% |
| 2005~ | 19.3% | -22.0% | 25.8% | 15.2% |
| 2010~ | 22.0% | -17.9% | 29.5% | 19.1% |
| 2015~ | 24.6% | -15.1% | 32.2% | 19.1% |

같은 2015~ 구간이라도 초기 1,000만원이면 세후 30.7%, 5억원이면 24.6%입니다. 2008년 이전은 일부 ETF가 백필 대체 데이터입니다. 장기 계획에는 20%대 초중반을, 보수적으로는 20%를 기준으로 봅니다.

| 구성 요소 | 카나리아(국면 판단) | 공격 시 | 방어 시 |
| --- | --- | --- | --- |
| 전략 A (안정형) | TIP 현재가 vs 11개월 이동평균 | 모멘텀 상위 4종목 × 25% | 모멘텀 1위 100% 또는 현금 |
| 전략 B (공격형) | TIP 1·3·6·9·12개월 평균 모멘텀 부호 | 가중 모멘텀 1위 100% | 5개월 수익률 1위 100% 또는 현금 |
| 전략 C (섹터로테이션) | SPY 12개월 배당수익률 > 1.33% | 모멘텀 1위 섹터 100% | 모멘텀 1위 100% 또는 현금 |

선택 적용 리스크 장치로 단일 자산 비중 상한(기본 35%)이 있습니다. 백테스트 설정 패널의 체크박스로 켜고 끄며, 기본 상태는 꺼짐입니다. 월중 하드스탑은 여러 구간·임계치로 백테스트했지만 뚜렷한 효과가 없어 2026-10-04에 제거했습니다.

## 투자 유니버스와 데이터

| 전략 | 공격 자산군 | 방어 자산군 |
| --- | --- | --- |
| A | QQQ, FEZ, GLD, IBB, SMH, EEM, XLK, LIT, XLE, UBT, XLV, QTUM (12개) | BIL, IEF, AGG, HYG, TBF (5개) |
| B | TYD, UPRO, VNQ (3개) | DOG, RWM, TBF (3개) |
| C | FDN, LIT, SMH, XLE, IGV, QQQM, XLU (7개) | GLD, PDBC, OILK, SHY, TLT (5개) |

전략 간 겹치는 티커가 있습니다. SMH·LIT·XLE는 A공격과 C공격, GLD는 A공격과 C방어, TBF는 A방어와 B방어에 함께 들어 있습니다. 합산 비중이 한 종목에 쏠리는 원인이 바로 이 중복입니다.

- **출처**: 백필 데이터 파일(`historical_daily_prices_2000_2026.parquet`, 2000년~)을 기본으로 쓰고, 파일 이후의 최신 구간은 yfinance(야후 파이낸스)에서 자동으로 이어붙입니다. 파일에 없는 티커는 야후에서 직접 받습니다. 모두 `auto_adjust=True`(배당·분할 반영 수정주가)이며 캐시 유효시간은 1시간입니다.
- **백필(상장 전 구간 대체)**: 상장이 늦은 ETF와 2003년 이전 TIP은 뮤추얼펀드·기초지수 일별 수익률로 이어붙였고, 레버리지·인버스(UPRO·TYD·UBT·DOG·RWM·TBF)는 일별 복리와 차입비용을 반영해 합성했습니다. 2015년 이전에는 합성·대체 데이터 비중이 크고, 이후에도 QTUM·QQQM·OILK·PDBC 등 상장이 늦은 일부 자산은 상장 전 구간에 대체 데이터가 쓰입니다.
- **월간 변환**: 일별 종가를 월말 마지막 값으로 리샘플링합니다.
- **배당 데이터**: SPY 배당 이력을 전략 C 카나리아에 씁니다.
- **시작일**: 2015-01-01(기본), 2004-01-01, 2000-01-01, 2018-01-01, 2020-01-01 중 선택. 첫 12개월은 모멘텀 계산용 워밍업이라 성과 기록에서 빠집니다(예: 2015-01-01 선택 시 2016-02부터 기록).

## 전략 A: 대형 우량 자산 안정형

매월 말 TIP 종가가 최근 11개월(당월 포함) 종가 평균보다 높으면 공격, 같거나 낮으면 방어입니다.

**모멘텀 정의**: R_n = (당월 말 종가 ÷ n개월 전 월말 종가 − 1) × 100. 모든 전략이 이 정의를 씁니다.

1. **공격 스코어**: 공격 자산 12개에 4구간 평균을 적용합니다. R_1과 R_12가 모두 있어야 후보가 됩니다.
2. **공격 배분**: 점수 상위 4종목에 각 25%. 후보가 없으면 현금 100%.
3. **방어 스코어**: 방어 자산 5개에 9개월 구간을 더한 5구간 평균을 씁니다.
4. **방어 배분**: 점수 1위 자산에 100%. 단, 1위 점수가 0 이하면 현금 100%.
""")
            st.latex(r"Score_{A,\text{공격}} = \frac{R_1 + R_3 + R_6 + R_{12}}{4} \qquad Score_{A,\text{방어}} = \frac{R_1 + R_3 + R_6 + R_9 + R_{12}}{5}")
            st.markdown(r"""
## 전략 B: 레버리지 공격형

TIP의 5구간 평균 모멘텀이 0보다 크면 공격, 0 이하면 방어입니다. 어느 쪽이든 1종목에 100% 집중합니다. TIP 모멘텀 5개 중 하나라도 계산되지 않는 달은 기록에서 빠집니다.

1. **공격 스코어**: TYD·UPRO·VNQ에 최근 수익률 비중이 큰 가중 모멘텀을 적용합니다. R_12가 있어야 후보가 됩니다.
2. **공격 배분**: 점수 1위에 100%. 후보가 없으면 현금 100%.
3. **방어 선정**: DOG·RWM·TBF 중 최근 5개월 수익률(R_5)이 가장 높은 자산을 고릅니다.
4. **방어 필터**: 선정 자산의 5구간 평균 모멘텀이 0보다 크면 100% 투자, 아니면 현금 100%.

방어 시 순위(R_5)와 진입 필터(5구간 평균)가 서로 다른 지표라는 점이 A·C와 다릅니다.
""")
            st.latex(r"Canary_B = \frac{R_1 + R_3 + R_6 + R_9 + R_{12}}{5}\,(TIP) > 0 \qquad Score_{B,\text{공격}} = \frac{12R_1 + 4R_3 + 2R_6 + R_{12}}{19}")
            st.markdown(r"""
## 전략 C: 배당 기반 섹터 로테이션

SPY의 최근 365일 배당 합계를 월말 SPY 실제 종가(배당 미조정)로 나눈 배당수익률이 1.33%를 넘으면 공격, 이하면 방어입니다. 배당 합계가 0이거나 가격이 없는 달은 기록에서 빠집니다.

1. **공격 스코어**: 섹터 ETF 7개에 전략 A와 같은 4구간 평균을 적용합니다. R_12가 있어야 후보가 됩니다.
2. **공격 배분**: 점수 1위 섹터에 100%. 후보가 없으면 현금 100%.
3. **방어 스코어**: 원자재·채권 5개에 5구간 평균(R_1·R_3·R_6·R_9·R_12)을 적용합니다.
4. **방어 배분**: 점수 1위에 100%. 1위 점수가 0 이하면 현금 100%.

실시간 화면의 배당수익률은 `get_sp500_dividend_yield()`가 최근 배당 이력과 현재가로 따로 계산하며, 백테스트와 같은 1.33% 기준을 씁니다.
""")
            st.latex(r"DY = \frac{\sum Div_{SPY}(\text{최근 365일})}{P_{SPY}(\text{월말})} \times 100 > 1.33\%")
            st.markdown(r"""
## 혼합전략 결합과 월간 흐름

세 전략은 서로 독립적으로 신호를 내고, 혼합전략은 각 전략 비중에 1/3을 곱해 티커별로 더합니다. 예를 들어 A가 QQQ·SMH·XLK·GLD에 25%씩, B가 UPRO 100%, C가 SMH 100%면 합산은 SMH 41.67%, UPRO 33.33%, QQQ·XLK·GLD 각 8.33%입니다.
""")
            st.graphviz_chart("""
digraph G {
    rankdir=TB; nodesep=0.35; ranksep=0.45;
    node [shape=box, style="rounded", fontname="sans-serif", fontsize=11, color="#94a3b8"];
    edge [color="#94a3b8", arrowsize=0.7];
    A [label="전략 A · 안정형\\nTIP vs 11개월 평균\\n공격: 상위 4종목 × 25%\\n방어: 채권 1위 또는 현금"];
    B [label="전략 B · 레버리지\\nTIP 5구간 모멘텀 양수 여부\\n공격: 가중 모멘텀 1위 100%\\n방어: 인버스 1위 또는 현금"];
    C [label="전략 C · 섹터로테이션\\nSPY 배당수익률 1.33% 초과\\n공격: 모멘텀 1위 섹터 100%\\n방어: 원자재·채권 또는 현금"];
    M [label="동일 비중 합산\\n전략별 비중 × 1/3을 티커별로 더함"];
    CAP [label="비중 상한 (선택)\\n단일 티커 35% 초과분 → 현금", style="rounded,dashed"];
    R [label="다음 달 수익 확정\\n다음 월말 종가 기준 수익률\\nNAV·드로다운 기록 후 반복", style="rounded,filled", fillcolor="#dbeafe", color="#2563eb"];
    {rank=same; A; B; C;}
    {rank=same; CAP; R;}
    A -> M; B -> M; C -> M;
    M -> CAP; CAP -> R;
}
""")
            st.caption("점선 상자는 체크박스로 켜는 선택 장치(비중 상한)이며 기본값은 꺼짐입니다. 꺼져 있으면 그대로 통과하고, 합산 비중이 그대로 다음 달 수익률에 적용됩니다.")
            st.markdown(r"""
## 리스크 관리 장치

비중 상한은 `run_backtest_strategy_mix_improved_full()`에 구현되어 있고, 켜면 개선판 엔진으로 계산합니다. 도입 근거는 2019년 5월 무역전쟁 급락 때 SMH 41.66%, UPRO 33.33%로 비중이 겹치며 그 달 낙폭이 컸던 사례입니다.

| 항목 | 비중 상한 (Cap) |
| --- | --- |
| 기본값 | 35% |
| 입력 범위 | 10 – 50%, 1%p 단위 |
| 기본 적용 여부 | 꺼짐 (체크박스) |
| 판단 시점 | 월말 리밸런싱 시 |
| 발동 조건 | 합산 후 단일 티커 비중 > 상한 |
| 처리 | 초과분을 현금으로 전환 (재배분 없음) |
| 모드 표시 | 📐Cap적용 |

**비중 상한이 실제로 걸리는 경우**: 한 전략이 100%를 넣어도 합산 비중은 33.33%라 35% 상한에 걸리지 않습니다. 두 전략 이상이 같은 티커를 고를 때만 발동합니다. 예를 들어 A가 SMH 25%, C가 SMH 100%를 고르면 합산 41.67%이고, 초과분 6.67%p가 현금이 됩니다.

**월중 하드스탑을 제거한 이유**: 월초 대비 일정 낙폭에 닿으면 월말까지 현금으로 두는 규칙을 -7%·-10% 등으로 백테스트했지만, 일상적 변동에도 자주 발동해 반등을 놓치거나(휩소) MDD 개선이 일관되지 않았고 CAGR만 낮아져 2026-10-04에 설정과 비교 항목에서 뺐습니다. 이번 달 낙폭은 '이번 달 일별 수익률' 모니터에서 일별로 확인할 수 있습니다(자동 청산 없음).

## 백테스트 방법론과 성과 지표

월말 종가로 신호와 비중을 정하고, 같은 종가에 체결했다고 보고 다음 달 월간 수익률을 적용합니다. NAV는 100에서 시작하며, 수익은 실현되는 달(다음 월말)에 기록합니다.

- **현금 수익률**: 0%로 가정합니다.
- **거래비용·세금·슬리피지**: 기본으로 반영합니다. 혼합전략 탭 상단의 '⚙️ 백테스트 비용·세금 반영 설정'에서 슬리피지(기본 0.2%/회)와 양도세(22%, 연 1회: 12월 말 확정·이듬해 6월 말 납부, 연 기본공제 250만원)를 끄거나 값을 바꿀 수 있습니다.
- **벤치마크(QQQ)의 비용·세금**: 비용·세금을 반영하면 QQQ에도 같은 조건을 넣어 비교합니다. 처음 매수할 때 슬리피지를 1회 차감하고, 양도세는 '그 달에 팔았다면' 내야 할 세금(수익에서 연 공제 250만원을 뺀 금액의 22%)을 뺀 세후 평가액으로 월수익률을 계산합니다. 그래서 기간 끝의 값이 세후 최종 가치와 일치하고, 보유 중에는 내재 세금이 함께 줄어들어 낙폭이 세전보다 약간 작게 나옵니다. 전략은 매년 과세하는 것과 달리 QQQ는 매도 시 1회만 과세하는 방식(매수 후 보유 가정)입니다.
- **혼합 결합**: 세 전략이 모두 기록을 가진 날짜만 씁니다(교집합).
- **드로다운**: 월말 NAV의 직전 고점 대비 하락률입니다. 월중 낙폭은 잡히지 않습니다.
  - 계산: 드로다운 = 월말 NAV ÷ 직전 월말 NAV 최고점 − 1
  - 예시 1 (월말 기준): 월말 NAV가 100 → 120(새 고점) → 102로 움직였다면 마지막 달의 드로다운은 102 ÷ 120 − 1 = −15%입니다. 이 백테스트의 MDD(−15.1%)도 2019년 5월 한 달 수익률(−15.1%)에서 나왔습니다.
  - 예시 2 (월중 낙폭 미반영): 월초 NAV 120이 월중 한때 105(−12.5%)까지 빠졌다가 월말에 117로 회복하면, 월말 기준 드로다운은 117 ÷ 120 − 1 = −2.5%만 기록되고 월중의 −12.5%는 나타나지 않습니다. 실제 계좌에서는 표시된 MDD보다 더 큰 일시적 낙폭을 겪을 수 있다는 뜻입니다. '이번 달 일별 수익률' 모니터는 일별 가격으로 이번 달의 낙폭을 따로 보여줍니다.

| 지표 | 계산 방식 |
| --- | --- |
| 기간 수익률 | 최종 NAV ÷ 100 − 1 |
| 연환산 수익률 (CAGR) | (최종 NAV ÷ 100)^(1 ÷ 연수) − 1, 연수 = 일수 ÷ 365.25 |
| 이번 달 수익률 | 마지막 달 월간 수익률 |
| 올해 수익률 (YTD) | 마지막 기록 연도의 월간 수익률 복리 누적 |
| 월 최고 / 월 최저 수익률 | 월간 수익률의 최댓값 / 최솟값 |
| 수익 월 비중 | 수익률 > 0인 달 수 / 전체 달 수 |
| 연 변동성 | 월간 수익률 표준편차 × √12 |
| 최대 낙폭 (MDD) / MDD 시점 | 드로다운 최솟값과 그 달 |
| 1년·3년·5년 수익률 | 최근 12·36·60개월 복리 누적. 데이터가 모자라면 "데이터 부족" |
| 1년·3년·5년 표준편차 | 같은 구간 월간 표준편차 × √12 |
| 샤프 지수 | (월평균 수익률 × 12) ÷ 연 변동성. 무위험수익률 0 |
| 소티노 지수 | (월평균 수익률 × 12) ÷ (음수 월 수익률 표준편차 × √12) |
| UPI 지수 | CAGR ÷ 궤양지수, 궤양지수 = √(드로다운² 평균) |
| 연간 턴오버 | 월별 (Σ 비중 변화의 절댓값 ÷ 2)의 평균 × 12. QQQ는 0% |

## 앱 화면 구성과 파라미터

앱은 9개 탭(2026 혼합전략, 전략 A, 전략 B, 전략 C, 미국 ETF 랭킹, 미국 주식 랭킹, 장기 낙폭, 자료실, 자산 계산기)으로 되어 있고, 탭 메뉴는 스크롤해도 상단에 고정됩니다. 혼합전략 탭은 위에서 아래로 다음 순서입니다.

1. ⚙️ 백테스트 비용·세금 반영 설정, 🌍 실시간 글로벌 매크로 시황판 (둘 다 접힘이 기본. 매크로 시황판은 모든 탭 맨 위에 있고, 비용·세금 설정은 이 탭에서만 바꿉니다)
2. 목표 문구(QQQ 수준의 장기 수익 추구 + 위기 시 변동성·MDD 방어)와 전략 명세서 (접이식 설명)
3. 📈 이번 달 일별 수익률: 직전 월말 확정 포트폴리오의 일간·월초 대비 누적 수익률, 전략 A·B·C별 기여, 종목별 기여도. 야후 일별 데이터에 최신 종가가 늦게 들어오면 5일 일봉 → 실시간 시세 순으로 보완하고(미국 정규장 중에는 보완하지 않음) 화면에 표시합니다. '🔍 데이터 확인'에서 계산에 쓴 종목별 종가 원본을 볼 수 있습니다.
4. 🚦 실시간 카나리아 신호 요약: A(TIP 비율)·B(TIP 모멘텀)·C(배당수익률) 값과 🟢 공격 / 🔴 방어 라벨, '📖 카나리아 신호 읽는 법'(지금 숫자로 해석 문장을 자동 생성), '🧭 카나리아 경계 거리'(이번 월말에 모드가 바뀌려면 몇 % 움직여야 하는지와 월말까지 남은 거래일)
5. 📊 이번 달 포트폴리오 비중 분배 현황 (종목별 합산 비중과 참여 전략)
6. 🧭 포트폴리오 성격 진단: 기술주 비중, 실질 주식 노출(레버리지 배수·인버스 반영), QQQ 대비 베타·상관계수·변동성(지금 비중을 최근 3개월 들고 있었다고 가정), 자산군별 표와 읽는 법
7. 💰 실시간 리밸런싱 목표 수량 계산기와 실전 매매 방법 (투자금은 만원 단위 입력, 기본 1,000만원·±100만원)
8. 백테스트 성과 분석: 설정 패널, 비용·세금 요약, 자산 곡선(NAV), 연도별·월별 수익률, 낙폭 히스토리, 드로다운 Top 10(주요 이슈 포함), 폭락 시장 성과, 주요 지표 비교(vs QQQ), 월별 세부 리밸런싱 기록
9. MDD 안전장치 전/후 비교: 안전장치 없음 / 비중 상한만 2가지를 같은 기간에 비교
10. 비용·세금 전/후 비교: 세전 / 슬리피지만 / 양도세만 / 둘 다의 CAGR·MDD·샤프와 6월 월평균 (인쇄에서는 제외)
11. 전략 종합평가 및 개선 작업 보고서

'월말 기준 리밸런싱 포트폴리오 역사 (최근 1년)'는 '월별 세부 리밸런싱 기록'과 내용이 겹쳐 2026-10-12에 화면에서 뺐습니다(함수는 남겨 둠).

**전략 A·B·C 탭**에도 신호값 아래 🟢 공격 / 🔴 방어 라벨, 그 전략의 '🧭 전환까지 거리'와 '📖 카나리아 신호 읽는 법'이 있습니다.

**INSIGHTS 탭** (매매 신호가 아닌 시장을 읽는 참고 화면, 레버리지·인버스 제외 화면 포함)

| 탭 | 내용 |
| --- | --- |
| 미국 ETF 랭킹 | 보기 3가지: ① 📊 전략 자산 랭킹(전략 A·B·C 자산과 주요 지수·배당형·레버리지 ETF) ② 🧭 섹터·테마 현황(11개 섹터·세부 테마·국가·원자재 40개 ETF의 수익률, SPY 대비 3개월 상대강도, 200일선, 거래대금 배수, 시장 체력(RSP vs SPY), 주도 Top 3·자금 유입 신호) ③ ⚠️ 시장 위험 신호판(장단기 금리차, VIX 기간구조, 하이일드÷국채, 달러 강도와 종합 판정) ④ 🧮 시장 밸류에이션(켄 피셔 『불변의 차트 90』 응용 5개 지표: 이익수익률−Baa 회사채 금리, 배당수익률의 1999\~ 위치, 10년물 3개월 변화, 나스닥100÷S&P500 PER, 실업률 삼의 법칙. 기준값 미검증·참고용) |
| 미국 주식 랭킹 | 지수 선택: 나스닥100(약 10초) / S&P500(약 1분) / KOSPI200 (테스트, 약 30초, `kospi200.csv` 사용). 버튼을 눌렀을 때만 불러오고 서버에 1시간 저장. 시장 폭(200일선 위 비율)과 상태 분포, 업종 분포, 상태 태그(🟢 주도·🟡 추세 둔화·🔵 200일선 아래 반등·🔴 200일선 아래 하락), 순위표 상위 50(기본 정렬 시가총액), 상태·보유 기준 필터, 종목 검색(쉼표로 여러 개), 검색한 종목의 차트·보유 기준·매도 기준까지 거리·추세 건강도(참고용)·추세 배지, 📖 읽는 법. 맨 아래 '📘 QQQ를 장기 보유하려면\~'(토글) |
| 장기 낙폭 | SPY·QQQ 30년, S&P500·나스닥100 지수 초장기 낙폭 (경각심용) |
| 자료실 | 투자 공부용 PDF·인포그래픽 슬라이드 모음. 탭에는 안내·'📚 자료실 열기' 단추·문서 목록(이름을 누르면 그 문서가 바로 열림)만 두고, 슬라이드 뷰어는 별도 페이지(`pages/9_library.py`)에서 엽니다. 뷰어는 좌우 밀기·‹ › 단추·⛶ 전체화면(안드로이드 가로 회전)·키보드 ← →를 지원하고 문서별로 보던 장을 기억합니다. 전체화면에서는 두 손가락 확대(최대 6배)·두 번 탭 2.5배·끌어서 이동·− 1:1 + 단추·PC 휠 확대가 됩니다. '📤 문서 올리기'로 휴대폰에서 PDF(최대 80장·25MB)·이미지를 새 문서로 올리거나 기존 문서 맨 앞에 이미지를 추가하고(같은 그림은 건너뜀), 비밀번호로 이미지·문서를 지울 수 있습니다(Cloud에서만 동작) |
| 자산 계산기 | 전략별 실측 CAGR 프리셋으로 미래 자산 시뮬레이션 |

**미국 주식 랭킹의 보유 기준** (미국 종목만, 월말 종가로 판단, PC 백테스트로 고른 규칙)

| 표시 | 조건 |
| --- | --- |
| 🟢 보유·매수 가능 | 200일선 +5% 위 |
| 🟢 보유 (재매수 대기) | 200일선 위 \~ +5% |
| 🟡 경계 | 200일선 아래 3% 이내 |
| 🔴 매도 기준 | 200일선 −3% 아래 |

매도는 200일선 −3% 아래, 재매수·신규 매수는 200일선 +5% 위입니다. 나스닥100 98종목(2015\~) 비교에서 200일선 규칙이 매수 후 보유보다 수익은 낮았지만(18.1% vs 27.4%) 낙폭이 작고(-19.8% vs -30.5%) 샤프가 가장 높았고, S&P500(2006\~) 재매수 검증에서 +5%가 3개월 내 재손절 비율을 30%에서 19%로 줄였습니다. 목표가·중기 손절은 이 규칙과 맞지 않고 효과가 없어 표시하지 않습니다. KOSPI200은 한국 백테스트(2006\~)에서 위험만 줄고 효율(샤프) 개선이 없어 매매 기준 없이 랭킹·추세만 보여 줍니다. 모든 종목 백테스트는 현재 구성 종목만 써서 생존편향이 있습니다.

랭킹·현황 데이터는 불러오는 동안 진행 안내 상자가 표시되고, 앱 서버 메모리에 1시간(구성 종목·업종 목록은 24시간) 저장됩니다. 파일로는 저장하지 않습니다.

백테스트 성과 분석과 자산 계산기 등에는 '🖨️ 이 화면 인쇄 / PDF 저장' 버튼이 있습니다.

| 파라미터 | 기본값 | 선택 범위 | 위치 |
| --- | --- | --- | --- |
| 백테스트 시작일 | 2015-01-01 | 2004 / 2000 / 2015 / 2018 / 2020년 1월 1일 | 설정 패널 |
| 비중 상한 | 35% | 10 – 50% | 설정 패널 |
| 비중 상한 적용 | 꺼짐 | 체크박스 | 설정 패널 |

실시간 비중 분배 현황에는 '비중 상한'이 체크 시 함께 적용됩니다. 이번 달 낙폭은 '이번 달 일별 수익률'에서 일별로 확인합니다(자동 청산 없음).

## 파일 구성과 운영

| 파일·폴더 | 역할 |
| --- | --- |
| `2026app-a.py` | 메인 대시보드 (Streamlit Cloud 진입 파일) |
| `pages/9_library.py` | 자료실 페이지. 한글 파일 이름은 Cloud에서 인식되지 않아 영문 이름 사용 |
| `docs/<문서명>/p001.jpg …` | 자료실 슬라이드 이미지 (문서 하나당 폴더 하나). `p###.jpg`는 PC 변환, `m…_01.jpg`는 휴대폰 추가(최신 업로드가 맨 앞) |
| `docs/<문서명>/_phone_upload.txt` | 휴대폰으로 만든 문서 표시 — PC 스크립트가 삭제 후보에서 뺌 |
| `docs/<문서명>/_source.txt` | PC 이미지 폴더 변환 기록(이름·수정 시각) |
| `docs/_pinned.txt` | 자료실 목록 맨 위에 고정할 문서 이름 (한 줄에 하나, 탭 목록과 자료실 화면이 함께 사용) |
| `.streamlit/config.toml` | `showSidebarNavigation = false` — 사이드바 페이지 메뉴 숨김(화면 안 링크로만 이동) |
| `historical_daily_prices_2000_2026.parquet`, `spy_dividends_*`, `spy_nominal_close.csv` | 백필 가격·SPY 배당·SPY 실제 종가 |
| `valuation_snapshot.json` | 시장 밸류에이션 PC 저장값. Cloud에서 야후 PER·FRED가 막힐 때 대체값 (PC에서 그 화면을 열면 자동 저장) |
| `kospi200.csv` | 코스피200 구성 종목·업종·시가총액 (KOSPI200 랭킹용) |
| `requirements.txt` | Cloud 설치 목록 (자료실 PDF 변환용 `pymupdf` 포함) |
| `pdf_src/` (PC 전용, 업로드 안 함) | 자료실 원본. PDF는 그대로, 이미지는 하위 폴더째 넣음 |
| `update_library.py` + `자료실_업데이트.bat` (PC 전용) | 먼저 GitHub 최신본(휴대폰 변경분)을 받은 뒤 `pdf_src` → `docs` 변환(PDF 100dpi·JPG 품질 80, 이미지는 가로 1600px·숫자 순 정렬, 변경 없으면 건너뜀), 원본이 지워진 문서 삭제(확인 후, 휴대폰 문서 제외), git으로 업로드. PC가 만든 `p###.jpg`만 지우고 휴대폰 이미지 `m…`는 보존 |
| `대시보드_업로드.bat` (PC 전용) | 최신본 받기(pull) → `2026app-a.py`·`pages`·`requirements.txt`와 `valuation_snapshot.json`·`kospi200.csv` 추가 → 메모 입력 후 commit·push |
| `make_kospi200_list.py` + `코스피200_목록_만들기.bat` (PC 전용) | `kospi200.csv` 생성. 6월·12월 정기변경 뒤 실행하고 `대시보드_업로드.bat`으로 올림 |
| `.gitignore` | 위 업로드 대상만 허용하고 venv·보고서·`pdf_src` 등은 제외 |

로컬 폴더는 git으로 GitHub 저장소 `2026st`와 연결되어 있고, 올리면 Cloud에 1~2분 안에 반영됩니다. 새 페이지 파일을 추가했을 때만 Cloud에서 Reboot가 필요합니다. 자료실에서 휴대폰으로 올리거나 지우면 GitHub에 커밋되므로 Cloud 앱이 잠깐 재시작됩니다.

**Streamlit Cloud Secrets**: 접속 잠금은 `APP_PASSWORD`·`PASSWORD_ENABLED`, 자료실 올리기는 `GITHUB_TOKEN`(fine-grained, 저장소 `2026st` Contents 읽기/쓰기, **2027-10경 만료** → 새로 발급해 교체)·`GITHUB_REPO`·`UPLOAD_PASSWORD`. PC(localhost)에는 Secrets가 없어 올리기 칸은 안내만 보이며, PC는 `pdf_src` + bat 방식을 씁니다.

## 한계와 유의사항

백테스트 수치는 월말 종가에 바로 체결된다는 가정 위의 값입니다. 슬리피지·양도세는 기본 반영하지만 환전 비용·매매 수수료는 빠져 있어, 실제 운용 성과보다 높게 나올 수 있습니다.

- **비용 구조**: 전략 B·C는 매달 100% 교체될 수 있어 턴오버가 큽니다(연 약 340%). 슬리피지 0.2%/회와 양도세 22%는 기본 반영되며, 초기 투자금이 클수록 세후 수익률이 낮아집니다(위 '초기 투자금과 시작 시점' 표).
- **동일 종가 체결**: 신호를 계산한 종가에 체결한다고 봅니다. 실제로는 다음 날 시가 등에 체결되므로 차이가 생깁니다.
- **배당수익률 계산 (편향 수정 완료)**: 전략 C 배당수익률은 SPY 실제 종가(배당 미조정, `spy_nominal_close.csv` + 야후 최신분)로 나눠 계산합니다. 수정주가로 나눌 때 생기던 과거 배당수익률 과대 계산 문제를 고쳐, 실시간 신호와 백테스트가 같은 방식입니다.
- **현금 수익률 0%**: 현금 비중이 큰 방어 구간과 상한 초과분의 이자 수익이 빠져 있습니다.
- **실시간 비중과 백테스트**: '비중 상한' 체크박스를 켜면 실시간 비중 분배·목표 수량 계산기에도 같은 상한(초과분은 현금)이 적용됩니다. 월중 낙폭은 비중표에 반영되지 않고 '📈 이번 달 일별 수익률'에서 따로 확인합니다.
- **짧은 이력 자산**: QTUM, QQQM, OILK 등은 상장 기간이 짧습니다. 데이터가 없는 달에는 후보에서 빠지므로 초기 구간의 선택 폭이 좁습니다.
- **데이터 의존성**: yfinance 응답이 바뀌거나 비면 결과가 달라지거나 표시되지 않을 수 있습니다.

이 명세서는 코드 동작을 정리한 문서이며 투자 권유가 아닙니다.
""")

        render_intramonth_stop_monitor(hist_prices, spy_divs_hist)

        st.markdown("### 🚦 실시간 카나리아 신호 요약")
        c_sig1, c_sig2, c_sig3 = st.columns(3)
        c_sig1.metric("전략A (TIP 비율)", f"{tip_ratio:.3f}")
        c_sig1.markdown(_mode_pill(is_attack_a), unsafe_allow_html=True)
        c_sig2.metric("전략B (TIP 모멘텀)", f"{tip_score_b:.2f}%")
        c_sig2.markdown(_mode_pill(is_attack_b), unsafe_allow_html=True)
        c_sig3.metric("전략C (배당수익률)", f"{realtime_dy:.2f}%")
        c_sig3.markdown(_mode_pill(is_attack_c), unsafe_allow_html=True)
        render_canary_guide(tip_ratio, tip_score_b, realtime_dy, is_attack_a, is_attack_b, is_attack_c)
        with st.container(border=True):
            st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
            render_canary_distance(tip_closes, tip_current, realtime_dy, is_attack_a, is_attack_b, is_attack_c)

        st.markdown("### 📊 이번 달 포트폴리오 비중 분배 현황")
        with st.container(border=True):
            st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
            if live_cap_on:
                if live_cap_hit:
                    _cap_txt = ", ".join(f"{t} {a:.2f}% → {b:.2f}%" for t, (a, b) in live_cap_hit.items())
                    st.info(f"📐 비중 상한 {live_cap_pct:.0f}% 적용 중: {_cap_txt} · 초과분 {live_cap_excess:.2f}%p는 현금 (아래 설정 패널의 체크박스를 해제하면 원래 비중으로 돌아갑니다)")
                else:
                    st.caption(f"📐 비중 상한 {live_cap_pct:.0f}% 적용 중 · 현재 상한을 넘는 종목이 없어 비중은 그대로입니다.")
            render_alloc_chips(df_mix)
            chart_col = st.container()

            with chart_col:
                try:
                    import altair as alt
                    df_chart = df_mix.copy()
                    df_chart["배분 비중 (%)"] = pd.to_numeric(df_chart["배분 비중 (%)"])
                    df_chart["차트라벨"] = df_chart["자산군 (Ticker)"] + " (" + df_chart["배분 비중 (%)"].astype(str) + "%)"
                
                    premium_colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"]
                    color_scale = alt.Scale(domain=df_chart["차트라벨"].tolist(), range=premium_colors[:len(df_chart)])
                
                    donut_chart = alt.Chart(df_chart).mark_arc(innerRadius=62, outerRadius=95, stroke='#ffffff', strokeWidth=2.5).encode(
                        theta=alt.Theta(field="배분 비중 (%)", type="quantitative"),
                        color=alt.Color(
                            field="차트라벨", 
                            type="nominal", 
                            scale=color_scale,
                            legend=None
                        ),
                        tooltip=[
                            alt.Tooltip("자산군 (Ticker)", title="자산군"),
                            alt.Tooltip("배분 비중 (%)", title="비중 (%)", format=".1f"),
                            alt.Tooltip("현재가 ($)", title="현재가")
                        ]
                    ).properties(height=230).configure_view(strokeWidth=0)
                
                    st.altair_chart(donut_chart, use_container_width=True)
                except Exception:
                    st.info("시각화 뷰 로드 완료")
                    st.bar_chart(df_mix.set_index("자산군 (Ticker)")["배분 비중 (%)"])
        
            render_alloc_table(df_mix_view)
            st.caption("※ 자산군에 마우스를 올리거나(폰은 터치) ETF 설명이 표시됩니다. 선택 기준·값: 각 전략이 해당 자산을 고른 이유와 스코어입니다. 1M·3M·6M·12M은 해당 자산의 기간별 수익률입니다. 배분 비중은 전체 자산 대비 %입니다. 비중 상한 체크박스를 켜면 상한이 반영된 비중입니다(이번 달 낙폭은 아래 '이번 달 일별 수익률' 모니터에서 별도로 확인).")

        with st.container(border=True):
            st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
            render_portfolio_character(combined_alloc, hist_prices)

        st.markdown("### 💰 실시간 리밸런싱 목표 수량 계산기")
        with st.container(border=True):
            st.markdown('<span class="content-box-marker"></span>', unsafe_allow_html=True)
            st.markdown("현재 환율과 실시간 주가를 기반으로, 설정한 원화 예산에 필요한 **자산별 목표 환전 달러** 및 **실제 매수 주수**를 계산해 드립니다.")
        
            live_exchange_rate = get_usd_krw_rate()
            st.info(f"💵 **실시간 적용 환율**: 1달러 = **{live_exchange_rate:,.2f}원** (야후 파이낸스 USDKRW=X 기준)")
        
            _budget_man = st.number_input(
                "총 투자 금액 입력 (만원)",
                min_value=0,
                value=1000,
                step=100,
                format="%d",
                key="calc_budget_man",
            )
            total_krw_budget = int(_budget_man) * 10000
            st.caption(f"= ₩ {total_krw_budget:,.0f}  (± 단추는 100만원씩)")
        
            if total_krw_budget > 0:
                calc_data = []
                for _, row in df_mix.iterrows():
                    ticker = row["자산군 (Ticker)"]
                    weight = row["배분 비중 (%)"]
                
                    krw_allocation = total_krw_budget * (weight / 100.0)
                    usd_allocation = krw_allocation / live_exchange_rate
                
                    if ticker == "CASH (현금)":
                        target_shares = "-"
                        current_price_str = "-"
                    else:
                        price = data_dict.get(ticker, {}).get("현재가", 0.0)
                        current_price_str = f"${price:.2f}"
                        if price > 0:
                            target_shares = f"{usd_allocation / price:.1f} 주"
                        else:
                            target_shares = "계산 불가"
                
                    calc_data.append({
                        "자산군 (Ticker)": ticker,
                        "배분 비중": f"{weight:.2f}%",
                        "배정액 (원화)": f"₩ {krw_allocation:,.0f}",
                        "목표 투자액 (달러)": f"${usd_allocation:,.2f}",
                        "현재가": current_price_str,
                        "목표 매수량": target_shares
                    })
            
                st.dataframe(pd.DataFrame(calc_data), use_container_width=True, hide_index=True)

            st.markdown(
                """
<div style="border:2px solid #f2c94c;background:#fffdf4;border-radius:12px;padding:14px 18px;margin:12px 0 4px 0;">
<div style="font-size:1.05rem;font-weight:800;margin-bottom:6px;">📌 리밸런싱 실전 매매 방법 — 슬리피지 0.2% 이내로 묶는 법</div>
<div style="margin-bottom:8px;">백테스트에서 슬리피지를 <b>0.2%</b>로 가정했으므로, 실제 계좌에서도 아래 규칙을 지켜야 이 수치 안에서 체결됩니다.</div>
<ol style="margin:0 0 0 18px;padding:0;">
<li style="margin-bottom:8px;"><b>미국 정규장 개장 직후(첫 15~30분) 주문 피하기</b><br/>
장 시작 직후는 호가 변동성이 극심해 슬리피지가 커집니다. 한국 시간으로 개장(서머타임 22:30 · 겨울 23:30) 후 30분이 지난 <b>장중 안정기~새벽</b>에 체결하세요.</li>
<li><b>시장가(Market) 대신 지정가(Limit) 또는 LOC 주문 활용</b><br/>
종가 기준 리밸런싱이므로 <b>LOC(Limit On Close, 종가 지정가 주문)</b>를 쓰면 종가 부근에서 슬리피지를 최소화할 수 있습니다.</li>
</ol>
</div>
""",
                unsafe_allow_html=True,
            )

            with st.expander("📖 목돈·신규 투자금이 생겼을 때 (읽는 법)", expanded=False):
                st.markdown("""
**기본 원칙 — 지금 들고 있어야 할 포트폴리오에 바로 합류**

이 전략은 월말에 정한 포트폴리오를 한 달 동안 들고 가는 구조입니다. 새 돈이 들어오면 **지난 월말에 확정된 이번 달 포트폴리오 비중대로** 바로 사면 백테스트와 같은 상태가 되고, 다음 월말에 전체 계좌를 한꺼번에 리밸런싱합니다. 백테스트상 현금으로 기다리는 쪽이 낫다는 근거는 없고, 장기적으로는 일찍 들어가는 쪽이 평균적으로 유리했습니다.

**실전 순서**

1. **목표 금액 계산** — 위 계산기에 **기존 평가액 + 새 돈 = 총액**을 넣어 종목별 목표 수량을 구합니다.
2. **부족분만 매수** — 목표 수량에서 지금 보유 수량을 뺀 만큼만 삽니다. 새 돈으로 비중이 모자란 종목을 채우는 방식이라 기존 종목을 팔 필요가 없어 매매 비용·양도세가 생기지 않습니다.
3. **비중 확인** — 계산기는 '실시간 비중'(오늘 가격으로 다시 계산한 신호) 기준입니다. 지난 월말 포트폴리오와 종목이 같으면 그대로 쓰고, 다르면 지난 월말 구성('월별 세부 리밸런싱 기록' 맨 아래 행)에 맞춰 삽니다.
4. **월말** — 평소처럼 전체 리밸런싱합니다.

**상황별 예외**

| 상황 | 권장 |
|---|---|
| 월말까지 1주일 이내 | 월말 리밸런싱 때 함께 넣기 (며칠 뒤 또 바꾸면 매매가 두 번 생김) |
| 금액이 크고 시장위험진단이 '평온'·'부담 적음' 쪽 | 한 번에 넣기 |
| 금액이 크고 진단이 '긴장' 이상이거나 '비싸고 긴장된 시장' | 2\\~3회로 나눠 넣기 (예: 지금 절반, 다음 월말 리밸런싱 때 나머지) |
| 전략이 방어 모드 (BIL·IEF·금 등) | 그대로 방어 자산을 사면 됨. 공격 전환을 기다릴 필요 없음 |

나눠 넣기는 수익을 늘리는 방법이 아니라 "넣자마자 크게 빠지면 어쩌나" 하는 부담을 줄이는 방법입니다. 평균적으로는 한 번에 넣는 쪽이 조금 더 벌었기 때문에, 시장위험진단의 판단표에서도 '목돈 분할'은 긴장 구간 이상에서만 권합니다(미국 ETF 탭 → 🩺 시장위험진단).

**잊기 쉬운 것**

- **환전** — 원화를 달러로 바꿀 때 증권사 환율 우대를 확인하세요. 금액이 크면 슬리피지보다 환전 비용이 더 클 수 있습니다.
- **기록** — 넣은 날짜와 금액을 적어 두면 연말 양도세 계산과 수익률 확인이 쉬워집니다.

전략 구조와 백테스트 가정에 근거한 설명이며, 투자 결정은 본인 판단입니다.
""")

        st.markdown("---")
        render_print_section("mix")
        st.markdown("### 🛑 2026 혼합전략 백테스트 성과 분석")

        print_mark("print-skip-a-start")
        with st.container(border=True):
            st.markdown('<div class="control-header">⚙️ 데이터 범위 및 리스크 관리 설정</div>', unsafe_allow_html=True)
            bt_start_label_mix = st.selectbox(
    "분석 및 백테스트 시작일",
    [
     "2004-01-01 (금융위기 포함 · 닷컴버블 제외)",        
     "2000-01-01 (닷컴버블 및 금융위기 포함)",
        "2015-01-01 (장기 검증)",
        "2018-01-01 (코로나 및 금리인상기 포함)",
        "2020-01-01 (최근 트렌드)"
    ],
    index=2,
    key="bt_start_select_mix"
)
            bt_start_mix = bt_start_label_mix.split(" ")[0]
            st.markdown("**🛡️ MDD 개선 로직 (선택 적용)**")
            mix_cap = st.number_input("비중 상한 (%)", min_value=10.0, max_value=50.0, value=35.0, step=1.0, key="mix_cap_pct")
            apply_cap_mix = st.radio(
                f"비중 상한: 단일 자산군 비중 상한(Cap {mix_cap:.0f}%) 적용",
                ["끄기", "켜기"], index=0, horizontal=True,
                key="apply_cap_mix_r",
                help="2019년 5월 무역전쟁 급락 시 SMH(41.66%)·UPRO(33.33%) 등 특정 자산에 3개 전략 비중이 겹치며 MDD가 커졌던 문제를 보완합니다. "
                     "3개 전략을 합산했을 때 단일 티커 비중이 위에서 설정한 상한을 넘으면 초과분을 현금으로 자동 전환합니다."
            ) == "켜기"
            st.caption("선택한 시작일 기준으로 2026 혼합전략(전략A+B+C 33.33%씩) 백테스트 시뮬레이션이 즉시 재계산됩니다.")
        print_mark("print-skip-a-end")

        use_improved_mix = apply_cap_mix

        with st.spinner("2026 혼합전략 실시간 백테스트 엔진 구동 중... (전략 A+B+C 통합 연산)"):
            try:
                bt_tickers_mix = sorted(set(
                    OFFENSIVE_A + DEFENSIVE_A + OFFENSIVE_B + DEFENSIVE_B + OFFENSIVE_C + DEFENSIVE_C
                    + ["TIP", "SPY", "QQQ"]
                ))
                daily_px_mix = get_daily_price_history_a(bt_tickers_mix, start=bt_start_mix)
                monthly_px_mix = to_monthly_last_a(daily_px_mix)
                spy_divs_mix = get_spy_dividend_history()
                if use_improved_mix:
                    bt_results_mix = run_backtest_strategy_mix_improved_full(
                        monthly_px_mix, spy_divs_mix, daily_px=daily_px_mix,
                        apply_cap=apply_cap_mix, weight_cap=mix_cap,
                    )
                else:
                    bt_results_mix = run_backtest_strategy_mix_full(monthly_px_mix, spy_divs_mix)
                bt_raw_mix = bt_results_mix  # 비용·세금 적용 전 원본 (비용·세금 전/후 비교용)
                bt_results_mix = apply_trading_costs(bt_raw_mix)
                bt_ok_mix = len(bt_results_mix) > 0
            except Exception as e:
                st.error(f"2026 혼합전략 백테스트 데이터 로딩 중 오류가 발생했습니다: {e}")
                bt_ok_mix = False

        if not bt_ok_mix:
            st.warning("백테스트 데이터가 부족하거나 오류가 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.caption(f"시뮬레이션 기간: {bt_results_mix['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_mix['date'].iloc[-1].strftime('%Y-%m')}")
            cost_status_caption(bt_results_mix)
            if use_improved_mix:
                st.success("🛡️ [개선판] 비중상한 로직이 적용된 결과입니다. 체크박스를 해제하면 기존 로직과 바로 비교할 수 있습니다.")

            total_days_mix = (bt_results_mix["date"].iloc[-1] - bt_results_mix["date"].iloc[0]).days
            total_years_mix = total_days_mix / 365.25 if total_days_mix > 0 else 1.0
            final_nav_mix = bt_results_mix["nav"].iloc[-1]

            cagr_mix = ((final_nav_mix / 100.0) ** (1 / total_years_mix) - 1) * 100
            mdd_mix = bt_results_mix["drawdown"].min()

            hl_cards([
                ("연환산 복리 수익률 (CAGR)", cagr_mix, "연평균 복리 수익률"),
                ("최대 낙폭 (MDD)", f"{mdd_mix:.2f}%", "직전 고점 대비 최대 하락", "neg"),
                ("최종 자산 가치 (NAV)", f"{final_nav_mix:.1f}", "초기금 100 기준", "neutral"),
            ])

            st.markdown("##### 📈 자산 곡선 (NAV) 추이")
            chart_df_mix = bt_results_mix.copy()
            chart_df_mix["date_str"] = chart_df_mix["date"].dt.strftime("%Y-%m")

            qqq_ret_series_mix = benchmark_after_costs(monthly_px_mix["QQQ"].pct_change().reindex(bt_results_mix["date"]))
            chart_df_mix["qqq_nav"] = (100 * (1 + qqq_ret_series_mix.fillna(0)).cumprod()).values

            nav_color_scale_mix = alt.Scale(domain=["2026 혼합전략", "QQQ"], range=["#0ea5e9", "#808080"])
            nav_long_mix = chart_df_mix.melt(
                id_vars="date_str", value_vars=["nav", "qqq_nav"], var_name="series", value_name="value"
            )
            nav_long_mix["series"] = nav_long_mix["series"].map({"nav": "2026 혼합전략", "qqq_nav": "QQQ"})

            nav_chart_mix = alt.Chart(nav_long_mix).mark_line(size=2.5).encode(
                x=alt.X("date_str:N", sort=None, title="년-월"),
                y=alt.Y("value:Q", title="NAV (기준 100)"),
                color=alt.Color("series:N", scale=nav_color_scale_mix, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("date_str:N", title="년-월"),
                    alt.Tooltip("series:N", title="구분"),
                    alt.Tooltip("value:Q", title="NAV", format=".1f"),
                ],
            ).properties(height=350)
            st.altair_chart(nav_chart_mix, use_container_width=True)

            # ------------------------------------------------------------
            # 연도별 수익률 (Annual Returns) — 막대 차트
            # ------------------------------------------------------------
            render_cost_quick_switch("mix")
            st.markdown("##### 📊 연도별 수익률 (%)")
            yearly_df_mix = bt_results_mix.copy()
            yearly_df_mix["year"] = yearly_df_mix["date"].dt.year
            yearly_returns_mix = (
                yearly_df_mix.groupby("year")["monthly_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            yearly_returns_mix["year_str"] = yearly_returns_mix["year"].astype(str)
            yearly_returns_mix["series"] = "2026 혼합전략"
            year_sort_order_mix = yearly_returns_mix["year_str"].tolist()

            qqq_monthly_ret_mix = benchmark_after_costs(monthly_px_mix["QQQ"].pct_change().reindex(bt_results_mix["date"])) * 100
            qqq_ret_df_mix = pd.DataFrame({
                "date": bt_results_mix["date"].values,
                "qqq_return": qqq_monthly_ret_mix.values,
            })
            qqq_ret_df_mix["year"] = pd.to_datetime(qqq_ret_df_mix["date"]).dt.year
            qqq_yearly_mix = (
                qqq_ret_df_mix.groupby("year")["qqq_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            qqq_yearly_mix["year_str"] = qqq_yearly_mix["year"].astype(str)
            qqq_yearly_mix["series"] = "QQQ"

            color_scale_mix = alt.Scale(domain=["2026 혼합전략", "QQQ"], range=["#0ea5e9", "#808080"])

            annual_bar_mix = alt.Chart(yearly_returns_mix).mark_bar().encode(
                x=alt.X("year_str:N", title="연도", sort=year_sort_order_mix, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q", title="수익률 (%)"),
                color=alt.Color("series:N", scale=color_scale_mix, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="수익률", format="+.2f"),
                ],
            )
            annual_labels_mix = alt.Chart(yearly_returns_mix).mark_text(
                dy=alt.expr("datum.annual_return >= 0 ? -8 : 14"), fontWeight="bold", fontSize=10, color="#0f172a"
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_mix, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                text=alt.Text("annual_return:Q", format=".1f"),
            )
            qqq_points_mix = alt.Chart(qqq_yearly_mix).mark_point(
                filled=True, size=110, stroke="white", strokeWidth=1.2
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_mix, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                color=alt.Color("series:N", scale=color_scale_mix, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="QQQ 수익률", format="+.2f"),
                ],
            )
            st.altair_chart(
                (annual_bar_mix + annual_labels_mix + qqq_points_mix).properties(height=320),
                use_container_width=True,
            )

            # ------------------------------------------------------------
            # 월별 수익률 (Monthly Returns) — 히트맵 테이블
            # ------------------------------------------------------------
            monthly_compound_cards(bt_results_mix)
            st.markdown("##### 🗓️ 월별 수익률 (%)")
            monthly_df_mix = bt_results_mix.copy()
            monthly_df_mix["year"] = monthly_df_mix["date"].dt.year
            monthly_df_mix["month"] = monthly_df_mix["date"].dt.month

            month_labels_mix = {m: (f"{m}월*" if (m == 6 and COST_TAX_ON) else f"{m}월") for m in range(1, 13)}  # 양도세 반영 시 6월에 * 표시
            monthly_df_mix["month_label"] = monthly_df_mix["month"].map(month_labels_mix)
            monthly_df_mix["year_label"] = monthly_df_mix["year"].astype(str)

            avg_by_month_mix = monthly_df_mix.groupby(["month", "month_label"])["monthly_return"].mean().reset_index()
            avg_by_month_mix["year_label"] = "평균"

            heat_df_mix = pd.concat([
                monthly_df_mix[["year_label", "month", "month_label", "monthly_return"]],
                avg_by_month_mix[["year_label", "month", "month_label", "monthly_return"]],
            ], ignore_index=True)

            year_sort_order_full_mix = [str(y) for y in sorted(monthly_df_mix["year"].unique())] + ["평균"]
            month_sort_order_mix = [month_labels_mix[m] for m in range(1, 13)]

            heat_rect_mix = alt.Chart(heat_df_mix).mark_rect(stroke="white", strokeWidth=1.5).encode(
                x=alt.X("month_label:N", title=None, sort=month_sort_order_mix, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", title=None, sort=year_sort_order_full_mix),
                color=alt.Color(
                    "monthly_return:Q",
                    scale=alt.Scale(
                        type="threshold",
                        domain=[-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5],
                        range=["#cf6265", "#e67f82", "#ecaaab", "#f6d4d5", "#fafbff",
                               "#d7e4da", "#accab2", "#82ae8b", "#599265"],
                    ),
                    legend=alt.Legend(title="수익률 (%)", orient="bottom", gradientLength=220),
                ),
                tooltip=[
                    alt.Tooltip("year_label:N", title="연도"),
                    alt.Tooltip("month_label:N", title="월"),
                    alt.Tooltip("monthly_return:Q", title="수익률", format="+.2f"),
                ],
            )
            heat_text_mix = alt.Chart(heat_df_mix).mark_text(fontSize=10, fontWeight="bold").encode(
                x=alt.X("month_label:N", sort=month_sort_order_mix, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", sort=year_sort_order_full_mix),
                text=alt.Text("monthly_return:Q", format="+.1f"),
                color=alt.value("#334155"),
            )
            st.altair_chart(
                (heat_rect_mix + heat_text_mix).properties(height=32 * len(year_sort_order_full_mix) + 80),
                use_container_width=True,
            )
            render_monthly_return_table(heat_df_mix, year_sort_order_full_mix, month_sort_order_mix, "mix")
            if COST_TAX_ON:
                st.caption("* 6월 수익률에는 전년도 양도세 납부분이 포함되어 있습니다. (전년도 수익에 대한 세금을 6월 말에 한꺼번에 차감하므로 6월 수익률이 낮게 나옵니다)")

            st.markdown("##### 📉 낙폭 (Drawdown) 히스토리")
            render_drawdown_with_benchmark(chart_df_mix, "2026 혼합전략")

            _ser_a_mix = run_backtest_strategy_a_full(monthly_px_mix).set_index("date")["monthly_return"]
            _ser_b_mix = run_backtest_strategy_b_full(monthly_px_mix).set_index("date")["monthly_return"]
            _ser_c_mix = run_backtest_strategy_c_full(monthly_px_mix, spy_divs_mix).set_index("date")["monthly_return"]

            def _period_ret_mix(ser, a, b):
                sub = ser[(ser.index >= a) & (ser.index <= b)]
                return (np.prod(1 + sub.values / 100.0) - 1) * 100 if len(sub) else float("nan")

            st.markdown("##### 🚨 포트폴리오 드로우다운 Top 10")
            dd_vals_mix = bt_results_mix["drawdown"].values
            dd_dates_mix = bt_results_mix["date"].values
            n_mix = len(dd_vals_mix)
            episodes_mix = []
            i_ep = 0
            while i_ep < n_mix:
                if dd_vals_mix[i_ep] < -0.001:
                    start_i = i_ep
                    j_ep = i_ep
                    min_val = dd_vals_mix[i_ep]
                    min_idx = i_ep
                    while j_ep < n_mix and dd_vals_mix[j_ep] < -0.001:
                        if dd_vals_mix[j_ep] < min_val:
                            min_val = dd_vals_mix[j_ep]
                            min_idx = j_ep
                        j_ep += 1
                    episodes_mix.append({
                        "시작": pd.Timestamp(dd_dates_mix[start_i]).strftime("%Y/%m"),
                        "종료": pd.Timestamp(dd_dates_mix[min_idx]).strftime("%Y/%m"),
                        "드로우다운": min_val,
                        "_s": pd.Timestamp(dd_dates_mix[start_i]),
                        "_e": pd.Timestamp(dd_dates_mix[min_idx]),
                    })
                    i_ep = j_ep
                else:
                    i_ep += 1

            episodes_mix.sort(key=lambda x: x["드로우다운"])
            top10_mix = episodes_mix[:10]
            for idx, ep in enumerate(top10_mix):
                ep["순위"] = idx + 1
                ep["드로우다운"] = f"{ep['드로우다운']:.1f}%"
                ep["A 전략"] = f"{_period_ret_mix(_ser_a_mix, ep['_s'], ep['_e']):+.1f}%"
                ep["B 전략"] = f"{_period_ret_mix(_ser_b_mix, ep['_s'], ep['_e']):+.1f}%"
                ep["C 전략"] = f"{_period_ret_mix(_ser_c_mix, ep['_s'], ep['_e']):+.1f}%"
                ep["주요 이슈"] = issues_for_period(ep["_s"], ep["_e"])
            if top10_mix:
                df_dd_top10_mix = pd.DataFrame(top10_mix)[["순위", "시작", "종료", "드로우다운", "A 전략", "B 전략", "C 전략", "주요 이슈"]].rename(columns={"드로우다운": "합계(A+B+C) 드로우다운"})
                st.dataframe(df_dd_top10_mix, use_container_width=True, hide_index=True)
                st.caption("※ 합계(A+B+C)는 세 전략을 1/3씩 섞은 혼합 포트폴리오의 낙폭이고, A·B·C 열은 같은 기간(시작\\~종료월) 각 전략을 단독(100%)으로 운용했을 때의 수익률입니다. '주요 이슈'는 시작\\~종료월과 기간이 겹치는 대형 이슈이며, 겹치는 이슈가 없으면 '-'입니다.")
            else:
                st.info("드로우다운 구간이 발견되지 않았습니다.")

            st.markdown("##### 🔻 폭락 시장 포트폴리오 성과")
            STRESS_PERIODS_MIX = [
                ("코로나 팬데믹", "2020-01-01", "2020-03-31"),
                ("2022 긴축 발작 (금리인상기)", "2022-01-01", "2022-10-31"),
                ("2018년 4분기 조정", "2018-10-01", "2018-12-31"),
            ]
            stress_rows_mix = []
            for label, s, e in STRESS_PERIODS_MIX:
                s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
                mask_mix = (bt_results_mix["date"] >= s_ts) & (bt_results_mix["date"] <= e_ts)
                sub_mix = bt_results_mix[mask_mix]
                if len(sub_mix) == 0:
                    continue
                port_cum_mix = (np.prod(1 + sub_mix["monthly_return"].values / 100.0) - 1) * 100
                qqq_sub_ret_mix = qqq_ret_series_mix.reindex(sub_mix["date"]).fillna(0.0)
                qqq_cum_mix = (np.prod(1 + qqq_sub_ret_mix.values) - 1) * 100
                stress_rows_mix.append({
                    "스트레스 기간": label,
                    "시작": s_ts.strftime("%Y/%m"),
                    "종료": e_ts.strftime("%Y/%m"),
                    "합계(A+B+C) 수익률": f"{port_cum_mix:+.1f}%",
                    "A 전략": f"{_period_ret_mix(_ser_a_mix, s_ts, e_ts):+.1f}%",
                    "B 전략": f"{_period_ret_mix(_ser_b_mix, s_ts, e_ts):+.1f}%",
                    "C 전략": f"{_period_ret_mix(_ser_c_mix, s_ts, e_ts):+.1f}%",
                    "QQQ 수익률": f"{qqq_cum_mix:+.1f}%",
                })
            if stress_rows_mix:
                st.dataframe(pd.DataFrame(stress_rows_mix), use_container_width=True, hide_index=True)
            else:
                st.info("선택한 시작일 범위 내 해당하는 폭락장 스트레스 기간 데이터가 없습니다. 시작일을 앞당겨 보세요.")

            st.markdown("##### 📊 주요 지표 비교 (vs QQQ)")

            def _fmt_pct_mix(x):
                return f"{x:.1f}%" if x is not None and not (isinstance(x, float) and np.isnan(x)) else "데이터 부족"

            port_ret_arr_mix = bt_results_mix["monthly_return"].values
            qqq_ret_arr_mix = qqq_monthly_ret_mix.values
            dd_arr_mix = bt_results_mix["drawdown"].values
            qqq_nav_arr_mix = chart_df_mix["qqq_nav"].values
            qqq_running_max_mix = np.maximum.accumulate(qqq_nav_arr_mix)
            qqq_dd_arr_mix = (qqq_nav_arr_mix / qqq_running_max_mix - 1) * 100

            period_ret_mix = (final_nav_mix / 100.0 - 1) * 100
            qqq_final_nav_mix = qqq_nav_arr_mix[-1]
            qqq_period_ret_mix = (qqq_final_nav_mix / 100.0 - 1) * 100
            qqq_cagr_mix = ((qqq_final_nav_mix / 100.0) ** (1 / total_years_mix) - 1) * 100

            last_date_mix2 = bt_results_mix["date"].iloc[-1]
            current_year_mix2 = last_date_mix2.year
            ytd_mask_mix = bt_results_mix["date"].dt.year == current_year_mix2
            port_ytd_mix = (np.prod(1 + bt_results_mix.loc[ytd_mask_mix, "monthly_return"].values / 100.0) - 1) * 100
            qqq_ytd_mix = (np.prod(1 + (qqq_ret_arr_mix[ytd_mask_mix.values] / 100.0)) - 1) * 100

            win_months_mix = int((port_ret_arr_mix > 0).sum())
            qqq_win_months_mix = int((qqq_ret_arr_mix > 0).sum())
            total_months_mix = len(port_ret_arr_mix)

            mdd_idx_mix = int(np.argmin(dd_arr_mix))
            mdd_date_mix = bt_results_mix["date"].iloc[mdd_idx_mix].strftime("%Y-%m")
            qqq_mdd_idx_mix = int(np.argmin(qqq_dd_arr_mix))
            qqq_mdd_date_mix = bt_results_mix["date"].iloc[qqq_mdd_idx_mix].strftime("%Y-%m")

            def _trailing_mix(arr, months):
                if len(arr) < months:
                    return None, None
                window = arr[-months:]
                cum = (np.prod(1 + window / 100.0) - 1) * 100
                ann_std = np.std(window, ddof=1) * np.sqrt(12) if len(window) > 1 else None
                return cum, ann_std

            ret_1y_mix, std_1y_mix = _trailing_mix(port_ret_arr_mix, 12)
            ret_3y_mix, std_3y_mix = _trailing_mix(port_ret_arr_mix, 36)
            ret_5y_mix, std_5y_mix = _trailing_mix(port_ret_arr_mix, 60)
            qqq_ret_1y_mix, qqq_std_1y_mix = _trailing_mix(qqq_ret_arr_mix, 12)
            qqq_ret_3y_mix, qqq_std_3y_mix = _trailing_mix(qqq_ret_arr_mix, 36)
            qqq_ret_5y_mix, qqq_std_5y_mix = _trailing_mix(qqq_ret_arr_mix, 60)

            mean_m_mix = np.mean(port_ret_arr_mix) / 100.0
            std_m_mix = np.std(port_ret_arr_mix, ddof=1) / 100.0 if total_months_mix > 1 else np.nan
            annual_vol_mix = std_m_mix * np.sqrt(12) * 100 if not np.isnan(std_m_mix) else np.nan
            sharpe_mix = (mean_m_mix * 12) / (std_m_mix * np.sqrt(12)) if std_m_mix and std_m_mix > 0 else np.nan

            downside_mix = port_ret_arr_mix[port_ret_arr_mix < 0] / 100.0
            downside_std_mix = np.std(downside_mix, ddof=1) if len(downside_mix) > 1 else np.nan
            sortino_mix = (mean_m_mix * 12) / (downside_std_mix * np.sqrt(12)) if downside_std_mix and downside_std_mix > 0 else np.nan

            ulcer_mix = np.sqrt(np.mean(dd_arr_mix ** 2))
            upi_mix = cagr_mix / ulcer_mix if ulcer_mix > 0 else np.nan

            qqq_mean_m_mix = np.mean(qqq_ret_arr_mix) / 100.0
            qqq_std_m_mix = np.std(qqq_ret_arr_mix, ddof=1) / 100.0 if total_months_mix > 1 else np.nan
            qqq_annual_vol_mix = qqq_std_m_mix * np.sqrt(12) * 100 if not np.isnan(qqq_std_m_mix) else np.nan
            qqq_sharpe_mix = (qqq_mean_m_mix * 12) / (qqq_std_m_mix * np.sqrt(12)) if qqq_std_m_mix and qqq_std_m_mix > 0 else np.nan

            qqq_downside_mix = qqq_ret_arr_mix[qqq_ret_arr_mix < 0] / 100.0
            qqq_downside_std_mix = np.std(qqq_downside_mix, ddof=1) if len(qqq_downside_mix) > 1 else np.nan
            qqq_sortino_mix = (qqq_mean_m_mix * 12) / (qqq_downside_std_mix * np.sqrt(12)) if qqq_downside_std_mix and qqq_downside_std_mix > 0 else np.nan

            qqq_ulcer_mix = np.sqrt(np.mean(qqq_dd_arr_mix ** 2))
            qqq_upi_mix = qqq_cagr_mix / qqq_ulcer_mix if qqq_ulcer_mix > 0 else np.nan

            alloc_list_mix = bt_results_mix["alloc"].tolist()
            monthly_turnovers_mix = []
            prev_alloc_mix = {}
            for alloc_d in alloc_list_mix:
                all_tk_mix = set(prev_alloc_mix.keys()) | set(alloc_d.keys())
                diff_mix = sum(abs(alloc_d.get(t, 0.0) - prev_alloc_mix.get(t, 0.0)) for t in all_tk_mix)
                monthly_turnovers_mix.append(diff_mix / 2.0)
                prev_alloc_mix = alloc_d
            avg_turnover_mix = np.mean(monthly_turnovers_mix) if monthly_turnovers_mix else 0.0
            annual_turnover_mix = avg_turnover_mix * 12

            metrics_rows_mix = [
                ("기간 수익률", _fmt_pct_mix(period_ret_mix), _fmt_pct_mix(qqq_period_ret_mix)),
                ("연환산 수익률 (CAGR)", _fmt_pct_mix(cagr_mix), _fmt_pct_mix(qqq_cagr_mix)),
                ("이번 달 수익률", _fmt_pct_mix(port_ret_arr_mix[-1]), _fmt_pct_mix(qqq_ret_arr_mix[-1])),
                ("올해 수익률 (YTD)", _fmt_pct_mix(port_ytd_mix), _fmt_pct_mix(qqq_ytd_mix)),
                ("월 최고 수익률", _fmt_pct_mix(port_ret_arr_mix.max()), _fmt_pct_mix(qqq_ret_arr_mix.max())),
                ("월 최저 수익률", _fmt_pct_mix(port_ret_arr_mix.min()), _fmt_pct_mix(qqq_ret_arr_mix.min())),
                ("수익 월 비중", f"{win_months_mix} / {total_months_mix}", f"{qqq_win_months_mix} / {total_months_mix}"),
                ("연 변동성", _fmt_pct_mix(annual_vol_mix), _fmt_pct_mix(qqq_annual_vol_mix)),
                ("최대 낙폭 (MDD)", _fmt_pct_mix(mdd_mix), _fmt_pct_mix(qqq_dd_arr_mix.min())),
                ("MDD 시점", mdd_date_mix, qqq_mdd_date_mix),
                ("1년 수익률", _fmt_pct_mix(ret_1y_mix), _fmt_pct_mix(qqq_ret_1y_mix)),
                ("3년 수익률", _fmt_pct_mix(ret_3y_mix), _fmt_pct_mix(qqq_ret_3y_mix)),
                ("5년 수익률", _fmt_pct_mix(ret_5y_mix), _fmt_pct_mix(qqq_ret_5y_mix)),
                ("1년 표준편차", _fmt_pct_mix(std_1y_mix), _fmt_pct_mix(qqq_std_1y_mix)),
                ("3년 표준편차", _fmt_pct_mix(std_3y_mix), _fmt_pct_mix(qqq_std_3y_mix)),
                ("5년 표준편차", _fmt_pct_mix(std_5y_mix), _fmt_pct_mix(qqq_std_5y_mix)),
                ("샤프 지수", f"{sharpe_mix:.2f}" if not np.isnan(sharpe_mix) else "데이터 부족", f"{qqq_sharpe_mix:.2f}" if not np.isnan(qqq_sharpe_mix) else "데이터 부족"),
                ("소티노 지수", f"{sortino_mix:.2f}" if not np.isnan(sortino_mix) else "데이터 부족", f"{qqq_sortino_mix:.2f}" if not np.isnan(qqq_sortino_mix) else "데이터 부족"),
                ("UPI 지수", f"{upi_mix:.2f}" if not np.isnan(upi_mix) else "데이터 부족", f"{qqq_upi_mix:.2f}" if not np.isnan(qqq_upi_mix) else "데이터 부족"),
                ("연간 턴오버", f"{annual_turnover_mix:.1f}%", "0.0%"),
            ]
            df_metrics_mix = pd.DataFrame(metrics_rows_mix, columns=["지표", "2026 혼합전략", "QQQ"])
            render_gl_table(df_metrics_mix)
            st.caption(f"※ 기간: {bt_results_mix['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_mix['date'].iloc[-1].strftime('%Y-%m')} 야후 파이낸스 실시간 데이터 기준. 1/3/5년 지표는 해당 기간의 월 데이터가 충분할 때만 표시됩니다. 비용·세금 반영 중에는 QQQ도 같은 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)의 세후 값입니다.")



            st.markdown("##### 🗓️ 월별 세부 리밸런싱 기록")
            display_bt_mix = bt_results_mix.copy()
            display_bt_mix["연월"] = display_bt_mix["date"].dt.strftime("%Y-%m")
            display_bt_mix["월 수익률"] = display_bt_mix["monthly_return"].apply(lambda x: f"{x:+.2f}%")
            display_bt_mix["낙폭"] = display_bt_mix["drawdown"].apply(lambda x: f"{x:.2f}%")
            display_bt_mix["NAV"] = display_bt_mix["nav"].apply(lambda x: f"{x:.1f}")
            st.caption("※ 전략 A·B·C는 각각 전체 자산의 33.3%씩 배분되며, 괄호 안 비중은 전체 자산 대비 비중입니다. (예: A[TBF 33.3%] = 전략 A가 TBF에 100% 투자)")

            st.dataframe(
                display_bt_mix[["연월", "mode", "월 수익률", "weights_str", "NAV", "낙폭"]].iloc[::-1],
                use_container_width=True, hide_index=True
            )

            print_mark("print-skip-b-start")
            # (월말 기준 리밸런싱 포트폴리오 역사는 '월별 세부 리밸런싱 기록'과 중복되어 2026-10-12 화면에서 제거. 함수는 남겨 둠)
            print_mark("print-skip-b-end")

            st.markdown("---")
            st.markdown("### 🔬 MDD 안전장치 전/후 비교 (비중 상한)")
            st.caption(f"같은 기간·같은 전략에서 비중 상한만 바꿔 비교합니다. 상한 {mix_cap:.0f}%는 위 설정값입니다.")

            def _run_mix(cap=None):
                return run_backtest_strategy_mix_improved_full(
                    monthly_px_mix, spy_divs_mix, daily_px=None,
                    apply_cap=cap is not None, weight_cap=cap if cap is not None else 35.0,
                )

            _mix_cases = {
                "① 안전장치 없음": {},
                f"② 상한 {mix_cap:.0f}%만": {"cap": mix_cap},
            }
            _mix_res = {k: apply_trading_costs(_run_mix(**v)) for k, v in _mix_cases.items()}
            _mix_rows = []
            for _k, _bt in _mix_res.items():
                _sm = summarize_bt_mix(_bt)
                if _sm:
                    _mix_rows.append({"방식": _k, **_sm})
            if _mix_rows:
                st.dataframe(pd.DataFrame(_mix_rows).drop(columns=["손절 발동 (월)"], errors="ignore").round(2), use_container_width=True, hide_index=True)
                st.caption("비중 상한은 MDD·최악의 달을 줄이는 대신 평상시 CAGR·샤프를 깎습니다. '발동 (월)'은 실제로 개입한 횟수입니다.")
                _nav_mix = pd.concat({_k.split(" ")[0]: _bt.set_index("date")["nav"] for _k, _bt in _mix_res.items() if len(_bt) > 0}, axis=1)
                st.line_chart(_nav_mix)

            print_mark("print-skip-c-start")
            st.markdown("---")
            st.markdown("### 💸 비용·세금 전/후 비교")
            st.caption(
                f"같은 기간·같은 전략에서 슬리피지({COST_SLIP_PCT:g}%/회)와 양도세({COST_TAX_PCT:g}%)를 단계별로 넣어 비교합니다. "
                "위 '비용·세금 반영 설정'의 값을 쓰며, 설정을 꺼 두었어도 이 표는 값을 적용해 보여줍니다."
            )
            _cc_cases = {
                "① 세전 (비용·세금 없음)": (False, False),
                "② 슬리피지만": (True, False),
                "③ 양도세만": (False, True),
                "④ 둘 다 (현재 반영값)": (True, True),
            }
            _cc_rows, _cc_nav = [], {}
            for _nm, (_sl, _tx) in _cc_cases.items():
                _cfg = (_sl, float(COST_SLIP_PCT), _tx, float(COST_TAX_PCT), float(COST_CAPITAL), float(COST_DEDUCT))
                _b = apply_trading_costs(bt_raw_mix, _cfg)
                _sm = summarize_bt_mix(_b)
                if not _sm:
                    continue
                _mo = pd.to_datetime(_b["date"]).dt.month
                _jun = float(_b.loc[_mo == 6, "monthly_return"].mean()) if (_mo == 6).any() else np.nan
                _oth = float(_b.loc[_mo != 6, "monthly_return"].mean())
                _cc_rows.append({
                    "방식": _nm,
                    "CAGR (%)": _sm["CAGR (%)"], "MDD (%)": _sm["MDD (%)"], "연변동성 (%)": _sm["연변동성 (%)"],
                    "샤프": _sm["샤프"], "최악 월 (%)": _sm["최악 월 (%)"],
                    "6월 월평균 (%)": _jun, "6월 외 월평균 (%)": _oth,
                    "최종 자산": fmt_krw(float(_b["nav"].iloc[-1]) / 100.0 * COST_CAPITAL),
                })
                _cc_nav[_nm.split(" ")[0]] = _b.set_index("date")["nav"]
            if _cc_rows:
                _df_cc = pd.DataFrame(_cc_rows)
                st.dataframe(_df_cc.round(2), use_container_width=True, hide_index=True)
                if len(_cc_rows) == 4:
                    _s0 = _cc_rows[0]["샤프"]
                    st.info(
                        f"샤프 변화(세전 {_s0:.2f} 기준): 슬리피지만 {_cc_rows[1]['샤프'] - _s0:+.2f} · "
                        f"양도세만 {_cc_rows[2]['샤프'] - _s0:+.2f} · 둘 다 {_cc_rows[3]['샤프'] - _s0:+.2f}"
                    )
                st.caption(
                    "양도세가 수익에 비례해 조금씩 나가면 샤프는 거의 변하지 않습니다. 이 앱은 전년도 세금을 6월 말에 한꺼번에 차감하므로 "
                    "6월 수익률이 인위적으로 낮아지고(표의 '6월 월평균' 참고) 월 수익률 변동성이 커져 샤프와 MDD가 실제 시장 위험보다 나쁘게 보일 수 있습니다. "
                    "슬리피지는 회전율에 비례한 작은 비용입니다."
                )
                if _cc_nav:
                    st.line_chart(pd.concat(_cc_nav, axis=1))
            print_mark("print-skip-c-end")

        print_mark("print-end")
        st.markdown("---")
        render_strategy_report()

    with c_a:
        render_macro_board()
        st.header("🛡️ 전략 A (안정형)")

        with st.expander("📖 전략 A 명세서", expanded=False):
            st.markdown(r"""
## 개요

전략 A는 TIP(물가연동채)로 국면을 판단해, 공격 국면에는 모멘텀 상위 4종목에 25%씩 분산하고 방어 국면에는 채권 1종목 또는 현금으로 대피하는 월간 로테이션 전략입니다. 2026 혼합전략에서 33.33%를 맡는 안정형 축입니다.

| 항목 | 내용 |
| --- | --- |
| 카나리아 | TIP 월말 종가 vs 최근 11개월(당월 포함) 월말 종가 평균 |
| 공격 조건 | TIP 종가 > 11개월 평균 (신호 비율 > 1.0) |
| 공격 시 | 공격 자산 12개 중 모멘텀 상위 4종목 × 25% |
| 방어 시 | 방어 자산 5개 중 모멘텀 1위 100%, 1위 점수 ≤ 0이면 현금 100% |
| 리밸런싱 | 매월 말 종가 기준 전량 재배분, 월중 매매 없음 |

## 자산군

| 구분 | 티커 |
| --- | --- |
| 공격 (12개) | QQQ, FEZ, GLD, IBB, SMH, EEM, XLK, LIT, XLE, UBT, XLV, QTUM |
| 방어 (5개) | BIL, IEF, AGG, HYG, TBF |

## 운용 규칙

**모멘텀 정의**: R_n = (당월 말 종가 ÷ n개월 전 월말 종가 − 1) × 100.

1. **국면 판단**: 매월 말 TIP 종가를 최근 11개월 평균과 비교해 공격 또는 방어를 정합니다.
2. **공격 스코어**: 공격 자산 12개에 4구간 평균 모멘텀을 계산합니다. R_1과 R_12가 모두 있어야 후보가 됩니다.
3. **공격 배분**: 점수 상위 4종목에 각 25%. 절대 모멘텀 컷오프 없이 순위로만 고르며, 후보가 없으면 현금 100%.
4. **방어 스코어**: 방어 자산 5개에 9개월 구간을 더한 5구간 평균을 계산합니다.
5. **방어 배분**: 점수 1위 자산에 100%. 1위 점수가 0 이하면 현금 100%.
""")
            st.latex(r"Score_{\text{공격}} = \frac{R_1 + R_3 + R_6 + R_{12}}{4} \qquad Score_{\text{방어}} = \frac{R_1 + R_3 + R_6 + R_9 + R_{12}}{5}")
            st.markdown(r"""
## 혼합전략 안에서의 역할

전략 A 비중은 혼합 포트폴리오의 33.33%이므로, 공격 시 종목당 8.33%, 방어 시 1종목 33.33%가 됩니다. SMH·LIT·XLE는 전략 C 공격 자산과, GLD는 전략 C 방어 자산과, TBF는 전략 B 방어 자산과 겹칩니다. 같은 종목이 동시에 선택되면 혼합 포트폴리오에서 비중이 합쳐집니다.

## 화면 구성

1. 카나리아 신호: TIP 현재가, 11개월 평균, 신호 비율과 🟢 공격 / 🔴 방어 라벨, '🧭 전환까지 거리', '📖 카나리아 신호 읽는 법'(지금 숫자로 해석 자동 생성)
2. 자산 순위표와 최종 포트폴리오 가이드
3. 이번 달 일별 수익률: 직전 월말 확정 포트폴리오의 일간·월초 대비 누적 수익률과 종목별 기여도 (최신 종가가 늦으면 자동 보완, '🔍 데이터 확인'으로 원본 종가 확인)
4. 백테스트 성과 분석: 시작일 선택(2015-01-01 기본, 2004, 2000, 2018, 2020), 자산 곡선, 연도별·월별 수익률, 낙폭, 드로다운 Top 10, 폭락 시장 성과, 주요 지표 비교(vs QQQ), 월별 리밸런싱 기록

신호 화면은 실시간 현재가로 계산한 참고값입니다. 실제 매매 판단은 월말 종가로 합니다.

## 백테스트 가정과 한계

- 월말 종가로 신호를 계산하고 같은 종가에 체결했다고 봅니다. 현금 수익률은 0%입니다.
- 슬리피지·세금은 기본으로 반영되며(슬리피지 0.2%/회, 양도세 22%) 혼합전략 탭 상단 설정에서 끄거나 바꿀 수 있습니다. 환전 비용은 반영하지 않았습니다.
- 첫 12개월은 모멘텀 계산용 워밍업이라 성과 기록에서 빠집니다.
- QTUM처럼 상장 기간이 짧은 자산은 데이터가 없는 달에 후보에서 빠집니다.
- 공격 시 순위만으로 4종목을 고르므로, 공격 국면 중 하락장에서는 손실을 그대로 받습니다.
""")

        st.markdown(
            "**1단계: 카나리아 신호 판단** \n"
            "신호 비율($\\dfrac{\\text{TIP 현재가}}{\\text{TIP 11개월 이동평균}}$)이 $1.0$을 초과하면 공격 모드, 이하이면 방어 모드로 진입합니다."
        )
        col1, col2, col3 = st.columns(3)
        col1.metric("TIP 현재가", f"${tip_current:.2f}")
        col2.metric("TIP 11M 이평", f"${tip_ma11:.2f}")
        col3.metric("신호 비율 (현재/이평)", f"{tip_ratio:.3f}")
        col3.markdown(_mode_pill(is_attack_a), unsafe_allow_html=True)
        render_canary_guide_single("A", tip_ratio, tip_score_b, realtime_dy, is_attack_a, tip_closes, tip_current)
        
        if is_attack_a:
            st.success("🔥 **현재 모드: 공격 자산 모드** - 시장의 위험 신호가 낮습니다.")
            df_off_a = df_all[df_all["Ticker"].isin(OFFENSIVE_A)].copy()
            df_off_a = df_off_a.sort_values(by="A_공격스코어", ascending=False)
            
            st.write("**공격 자산 순위 (1-3-6-12M 단순 평균 모멘텀):**")
            render_html_table(
                df_off_a[["Ticker", "현재가", "1M", "3M", "6M", "12M", "A_공격스코어"]]
                .rename(columns={"A_공격스코어": "모멘텀 스코어"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드 (각 25% 균등 분배)")
            for t, _ in alloc_a.items():
                p = data_dict.get(t, {}).get("현재가", 0.0)
                s = data_dict.get(t, {}).get("A_공격스코어", 0.0)
                st.info(f"**{t}** (25% 배분) - 현재가: ${p:.2f} (모멘텀: {s:.2f}%)")
        else:
            st.warning("🛡️ **현재 모드: 방어 자산 모드** - 하락장을 방어하는 구간입니다.")
            df_def_a = df_all[df_all["Ticker"].isin(DEFENSIVE_A)].copy()
            df_def_a = df_def_a.sort_values(by="A_방어스코어", ascending=False)
            
            st.write("**방어 자산 순위 (1-3-6-9-12M 단순 평균 모멘텀):**")
            render_html_table(
                df_def_a[["Ticker", "현재가", "1M", "3M", "6M", "9M", "12M", "A_방어스코어"]]
                .rename(columns={"A_방어스코어": "모멘텀 스코어"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드")
            for t, _ in alloc_a.items():
                if t == "CASH (현금)":
                    st.error("🚨 **현금(CASH) 보유 : 비중 100%**")
                else:
                    p = data_dict.get(t, {}).get("현재가", 0.0)
                    s = data_dict.get(t, {}).get("A_방어스코어", 0.0)
                    st.info(f"**{t}** : 비중 **100%** (현재가: ${p:.2f}, 모멘텀: {s:.2f}%)")

        render_other_mode("A", is_attack_a, df_all, data_dict)   # 🔄 반대 모드로 바뀐다면 (기본 접기)
        st.markdown("---")
        render_intramonth_stop_monitor(hist_prices, spy_divs_hist, strategy="A")

        st.markdown("---")
        render_print_section("a")
        st.markdown("### 🛑 전략 A 백테스트 성과 분석")

        with st.container(border=True):
            st.markdown('<div class="control-header">⚙️ 데이터 범위 및 리스크 관리 설정</div>', unsafe_allow_html=True)
            bt_start_label_a = st.selectbox(
                "분석 및 백테스트 시작일",
                [
                    "2004-01-01 (금융위기 포함 · 닷컴버블 제외)",
                    "2000-01-01 (닷컴버블 및 금융위기 포함)",
                    "2015-01-01 (장기 검증)",
                    "2018-01-01 (코로나 및 금리인상기 포함)",
                    "2020-01-01 (최근 트렌드)"
                ],
                index=2,
                key="bt_start_select_a"
            )
            bt_start_a = bt_start_label_a.split(" ")[0]
            st.caption("선택한 시작일 기준으로 전략 A 백테스트 시뮬레이션(NAV, 연도별/월별 수익률, 낙폭, 리밸런싱 기록)이 즉시 재계산됩니다.")

        with st.spinner("전략 A 실시간 백테스트 엔진 구동 중..."):
            try:
                bt_tickers_a = sorted(set(OFFENSIVE_A + DEFENSIVE_A + ["TIP", "QQQ"]))
                daily_px_a = get_daily_price_history_a(bt_tickers_a, start=bt_start_a)
                monthly_px_a = to_monthly_last_a(daily_px_a)
                bt_results_a = run_backtest_strategy_a_full(monthly_px_a)
                bt_results_a = apply_trading_costs(bt_results_a)
                bt_ok_a = len(bt_results_a) > 0
            except Exception as e:
                st.error(f"전략 A 백테스트 데이터 로딩 중 오류가 발생했습니다: {e}")
                bt_ok_a = False

        if not bt_ok_a:
            st.warning("백테스트 데이터가 부족하거나 오류가 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.caption(f"시뮬레이션 기간: {bt_results_a['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_a['date'].iloc[-1].strftime('%Y-%m')}")
            cost_status_caption(bt_results_a)

            total_days_a = (bt_results_a["date"].iloc[-1] - bt_results_a["date"].iloc[0]).days
            total_years_a = total_days_a / 365.25 if total_days_a > 0 else 1.0
            final_nav_a = bt_results_a["nav"].iloc[-1]

            cagr_a = ((final_nav_a / 100.0) ** (1 / total_years_a) - 1) * 100
            mdd_a = bt_results_a["drawdown"].min()

            hl_cards([
                ("연환산 복리 수익률 (CAGR)", cagr_a, "연평균 복리 수익률"),
                ("최대 낙폭 (MDD)", f"{mdd_a:.2f}%", "직전 고점 대비 최대 하락", "neg"),
                ("최종 자산 가치 (NAV)", f"{final_nav_a:.1f}", "초기금 100 기준", "neutral"),
            ])

            st.markdown("##### 📈 자산 곡선 (NAV) 추이")
            chart_df_a = bt_results_a.copy()
            chart_df_a["date_str"] = chart_df_a["date"].dt.strftime("%Y-%m")

            qqq_ret_series_a = benchmark_after_costs(monthly_px_a["QQQ"].pct_change().reindex(bt_results_a["date"]))
            chart_df_a["qqq_nav"] = (100 * (1 + qqq_ret_series_a.fillna(0)).cumprod()).values

            nav_color_scale_a = alt.Scale(domain=["전략A", "QQQ"], range=["#50ad6a", "#808080"])
            nav_long_a = chart_df_a.melt(
                id_vars="date_str", value_vars=["nav", "qqq_nav"], var_name="series", value_name="value"
            )
            nav_long_a["series"] = nav_long_a["series"].map({"nav": "전략A", "qqq_nav": "QQQ"})

            nav_chart_a = alt.Chart(nav_long_a).mark_line(size=2.5).encode(
                x=alt.X("date_str:N", sort=None, title="년-월"),
                y=alt.Y("value:Q", title="NAV (기준 100)"),
                color=alt.Color("series:N", scale=nav_color_scale_a, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("date_str:N", title="년-월"),
                    alt.Tooltip("series:N", title="구분"),
                    alt.Tooltip("value:Q", title="NAV", format=".1f"),
                ],
            ).properties(height=350)
            st.altair_chart(nav_chart_a, use_container_width=True)

            # ------------------------------------------------------------
            # 연도별 수익률 (Annual Returns) — 막대 차트
            # ------------------------------------------------------------
            render_cost_quick_switch("a")
            st.markdown("##### 📊 연도별 수익률 (%)")
            yearly_df_a = bt_results_a.copy()
            yearly_df_a["year"] = yearly_df_a["date"].dt.year
            yearly_returns_a = (
                yearly_df_a.groupby("year")["monthly_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            yearly_returns_a["year_str"] = yearly_returns_a["year"].astype(str)
            yearly_returns_a["series"] = "전략A"
            year_sort_order_a = yearly_returns_a["year_str"].tolist()

            qqq_monthly_ret_a = benchmark_after_costs(monthly_px_a["QQQ"].pct_change().reindex(bt_results_a["date"])) * 100
            qqq_ret_df_a = pd.DataFrame({
                "date": bt_results_a["date"].values,
                "qqq_return": qqq_monthly_ret_a.values,
            })
            qqq_ret_df_a["year"] = pd.to_datetime(qqq_ret_df_a["date"]).dt.year
            qqq_yearly_a = (
                qqq_ret_df_a.groupby("year")["qqq_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            qqq_yearly_a["year_str"] = qqq_yearly_a["year"].astype(str)
            qqq_yearly_a["series"] = "QQQ"

            color_scale_a = alt.Scale(domain=["전략A", "QQQ"], range=["#50ad6a", "#808080"])

            annual_bar_a = alt.Chart(yearly_returns_a).mark_bar().encode(
                x=alt.X("year_str:N", title="연도", sort=year_sort_order_a, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q", title="수익률 (%)"),
                color=alt.Color("series:N", scale=color_scale_a, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="수익률", format="+.2f"),
                ],
            )
            annual_labels_a = alt.Chart(yearly_returns_a).mark_text(
                dy=alt.expr("datum.annual_return >= 0 ? -8 : 14"), fontWeight="bold", fontSize=10, color="#0f172a"
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_a, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                text=alt.Text("annual_return:Q", format=".1f"),
            )
            qqq_points_a = alt.Chart(qqq_yearly_a).mark_point(
                filled=True, size=110, stroke="white", strokeWidth=1.2
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_a, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                color=alt.Color("series:N", scale=color_scale_a, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="QQQ 수익률", format="+.2f"),
                ],
            )
            st.altair_chart(
                (annual_bar_a + annual_labels_a + qqq_points_a).properties(height=320),
                use_container_width=True,
            )

            # ------------------------------------------------------------
            # 월별 수익률 (Monthly Returns) — 히트맵 테이블
            # ------------------------------------------------------------
            monthly_compound_cards(bt_results_a)
            st.markdown("##### 🗓️ 월별 수익률 (%)")
            monthly_df_a = bt_results_a.copy()
            monthly_df_a["year"] = monthly_df_a["date"].dt.year
            monthly_df_a["month"] = monthly_df_a["date"].dt.month

            month_labels_a = {m: (f"{m}월*" if (m == 6 and COST_TAX_ON) else f"{m}월") for m in range(1, 13)}  # 양도세 반영 시 6월에 * 표시
            monthly_df_a["month_label"] = monthly_df_a["month"].map(month_labels_a)
            monthly_df_a["year_label"] = monthly_df_a["year"].astype(str)

            avg_by_month_a = monthly_df_a.groupby(["month", "month_label"])["monthly_return"].mean().reset_index()
            avg_by_month_a["year_label"] = "평균"

            heat_df_a = pd.concat([
                monthly_df_a[["year_label", "month", "month_label", "monthly_return"]],
                avg_by_month_a[["year_label", "month", "month_label", "monthly_return"]],
            ], ignore_index=True)

            year_sort_order_full_a = [str(y) for y in sorted(monthly_df_a["year"].unique())] + ["평균"]
            month_sort_order_a = [month_labels_a[m] for m in range(1, 13)]

            heat_rect_a = alt.Chart(heat_df_a).mark_rect(stroke="white", strokeWidth=1.5).encode(
                x=alt.X("month_label:N", title=None, sort=month_sort_order_a, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", title=None, sort=year_sort_order_full_a),
                color=alt.Color(
                    "monthly_return:Q",
                    scale=alt.Scale(
                        type="threshold",
                        domain=[-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5],
                        range=["#cf6265", "#e67f82", "#ecaaab", "#f6d4d5", "#fafbff",
                               "#d7e4da", "#accab2", "#82ae8b", "#599265"],
                    ),
                    legend=alt.Legend(title="수익률 (%)", orient="bottom", gradientLength=220),
                ),
                tooltip=[
                    alt.Tooltip("year_label:N", title="연도"),
                    alt.Tooltip("month_label:N", title="월"),
                    alt.Tooltip("monthly_return:Q", title="수익률", format="+.2f"),
                ],
            )
            heat_text_a = alt.Chart(heat_df_a).mark_text(fontSize=10, fontWeight="bold").encode(
                x=alt.X("month_label:N", sort=month_sort_order_a, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", sort=year_sort_order_full_a),
                text=alt.Text("monthly_return:Q", format="+.1f"),
                color=alt.value("#334155"),
            )
            st.altair_chart(
                (heat_rect_a + heat_text_a).properties(height=32 * len(year_sort_order_full_a) + 80),
                use_container_width=True,
            )
            render_monthly_return_table(heat_df_a, year_sort_order_full_a, month_sort_order_a, "a")
            if COST_TAX_ON:
                st.caption("* 6월 수익률에는 전년도 양도세 납부분이 포함되어 있습니다. (전년도 수익에 대한 세금을 6월 말에 한꺼번에 차감하므로 6월 수익률이 낮게 나옵니다)")

            st.markdown("##### 📉 낙폭 (Drawdown) 히스토리")
            render_drawdown_with_benchmark(chart_df_a, "전략A")

            st.markdown("##### 🚨 포트폴리오 드로우다운 Top 10")
            dd_vals_a = bt_results_a["drawdown"].values
            dd_dates_a = bt_results_a["date"].values
            n_a = len(dd_vals_a)
            episodes_a = []
            i_ep_a = 0
            while i_ep_a < n_a:
                if dd_vals_a[i_ep_a] < -0.001:
                    start_i_a = i_ep_a
                    j_ep_a = i_ep_a
                    min_val_a = dd_vals_a[i_ep_a]
                    min_idx_a = i_ep_a
                    while j_ep_a < n_a and dd_vals_a[j_ep_a] < -0.001:
                        if dd_vals_a[j_ep_a] < min_val_a:
                            min_val_a = dd_vals_a[j_ep_a]
                            min_idx_a = j_ep_a
                        j_ep_a += 1
                    episodes_a.append({
                        "시작": pd.Timestamp(dd_dates_a[start_i_a]).strftime("%Y/%m"),
                        "종료": pd.Timestamp(dd_dates_a[min_idx_a]).strftime("%Y/%m"),
                        "드로우다운": min_val_a,
                    })
                    i_ep_a = j_ep_a
                else:
                    i_ep_a += 1

            episodes_a.sort(key=lambda x: x["드로우다운"])
            top10_a = episodes_a[:10]
            for idx, ep in enumerate(top10_a):
                ep["순위"] = idx + 1
                ep["드로우다운"] = f"{ep['드로우다운']:.1f}%"
                ep["주요 이슈"] = issues_for_period(ep["시작"], ep["종료"])
            if top10_a:
                df_dd_top10_a = pd.DataFrame(top10_a)[["순위", "시작", "종료", "드로우다운", "주요 이슈"]]
                st.dataframe(df_dd_top10_a, use_container_width=True, hide_index=True)
                st.caption("※ 드로우다운은 시작월 직전 고점부터 종료월(최저점)까지의 하락률입니다. '주요 이슈'는 시작\\~종료월과 기간이 겹치는 대형 이슈이며, 겹치는 이슈가 없으면 '-'입니다.")
            else:
                st.info("드로우다운 구간이 발견되지 않았습니다.")

            st.markdown("##### 🔻 폭락 시장 포트폴리오 성과")
            STRESS_PERIODS_A = [
                ("코로나 팬데믹", "2020-01-01", "2020-03-31"),
                ("2022 긴축 발작 (금리인상기)", "2022-01-01", "2022-10-31"),
                ("2018년 4분기 조정", "2018-10-01", "2018-12-31"),
            ]
            stress_rows_a = []
            for label_a, s_str_a, e_str_a in STRESS_PERIODS_A:
                s_ts_a, e_ts_a = pd.Timestamp(s_str_a), pd.Timestamp(e_str_a)
                mask_a = (bt_results_a["date"] >= s_ts_a) & (bt_results_a["date"] <= e_ts_a)
                sub_a = bt_results_a[mask_a]
                if len(sub_a) == 0:
                    continue
                port_cum_a = (np.prod(1 + sub_a["monthly_return"].values / 100.0) - 1) * 100
                bench_sub_ret_a = qqq_ret_series_a.reindex(sub_a["date"]).fillna(0.0)
                bench_cum_a = (np.prod(1 + bench_sub_ret_a.values) - 1) * 100
                stress_rows_a.append({
                    "스트레스 기간": label_a,
                    "시작": s_ts_a.strftime("%Y/%m"),
                    "종료": e_ts_a.strftime("%Y/%m"),
                    "포트폴리오 수익률": f"{port_cum_a:+.1f}%",
                    "QQQ 수익률": f"{bench_cum_a:+.1f}%",
                })
            if stress_rows_a:
                st.dataframe(pd.DataFrame(stress_rows_a), use_container_width=True, hide_index=True)
            else:
                st.info("선택한 시작일 범위 내 해당하는 폭락장 스트레스 기간 데이터가 없습니다. 시작일을 앞당겨 보세요.")

            st.markdown("##### 📊 주요 지표 비교 (vs QQQ)")

            def _fmt_pct_a(x):
                return f"{x:.1f}%" if x is not None and not (isinstance(x, float) and np.isnan(x)) else "데이터 부족"

            port_ret_arr_a = bt_results_a["monthly_return"].values
            bench_ret_arr_a = qqq_monthly_ret_a.values
            dd_arr_a = bt_results_a["drawdown"].values
            bench_nav_arr_a = chart_df_a["qqq_nav"].values
            bench_running_max_a = np.maximum.accumulate(bench_nav_arr_a)
            bench_dd_arr_a = (bench_nav_arr_a / bench_running_max_a - 1) * 100

            period_ret_a = (final_nav_a / 100.0 - 1) * 100
            bench_final_nav_a = bench_nav_arr_a[-1]
            bench_period_ret_a = (bench_final_nav_a / 100.0 - 1) * 100
            bench_cagr_a = ((bench_final_nav_a / 100.0) ** (1 / total_years_a) - 1) * 100

            last_date2_a = bt_results_a["date"].iloc[-1]
            current_year2_a = last_date2_a.year
            ytd_mask_a = bt_results_a["date"].dt.year == current_year2_a
            port_ytd_a = (np.prod(1 + bt_results_a.loc[ytd_mask_a, "monthly_return"].values / 100.0) - 1) * 100
            bench_ytd_a = (np.prod(1 + (bench_ret_arr_a[ytd_mask_a.values] / 100.0)) - 1) * 100

            win_months_a = int((port_ret_arr_a > 0).sum())
            bench_win_months_a = int((bench_ret_arr_a > 0).sum())
            total_months_a = len(port_ret_arr_a)

            mdd_idx_a = int(np.argmin(dd_arr_a))
            mdd_date_a = bt_results_a["date"].iloc[mdd_idx_a].strftime("%Y-%m")
            bench_mdd_idx_a = int(np.argmin(bench_dd_arr_a))
            bench_mdd_date_a = bt_results_a["date"].iloc[bench_mdd_idx_a].strftime("%Y-%m")

            def _trailing_a(arr, months):
                if len(arr) < months:
                    return None, None
                window = arr[-months:]
                cum = (np.prod(1 + window / 100.0) - 1) * 100
                ann_std = np.std(window, ddof=1) * np.sqrt(12) if len(window) > 1 else None
                return cum, ann_std

            ret_1y_a, std_1y_a = _trailing_a(port_ret_arr_a, 12)
            ret_3y_a, std_3y_a = _trailing_a(port_ret_arr_a, 36)
            ret_5y_a, std_5y_a = _trailing_a(port_ret_arr_a, 60)
            bench_ret_1y_a, bench_std_1y_a = _trailing_a(bench_ret_arr_a, 12)
            bench_ret_3y_a, bench_std_3y_a = _trailing_a(bench_ret_arr_a, 36)
            bench_ret_5y_a, bench_std_5y_a = _trailing_a(bench_ret_arr_a, 60)

            mean_m_a = np.mean(port_ret_arr_a) / 100.0
            std_m_a = np.std(port_ret_arr_a, ddof=1) / 100.0 if total_months_a > 1 else np.nan
            annual_vol_a = std_m_a * np.sqrt(12) * 100 if not np.isnan(std_m_a) else np.nan
            sharpe_a = (mean_m_a * 12) / (std_m_a * np.sqrt(12)) if std_m_a and std_m_a > 0 else np.nan

            downside_a = port_ret_arr_a[port_ret_arr_a < 0] / 100.0
            downside_std_a = np.std(downside_a, ddof=1) if len(downside_a) > 1 else np.nan
            sortino_a = (mean_m_a * 12) / (downside_std_a * np.sqrt(12)) if downside_std_a and downside_std_a > 0 else np.nan

            ulcer_a = np.sqrt(np.mean(dd_arr_a ** 2))
            upi_a = cagr_a / ulcer_a if ulcer_a > 0 else np.nan

            bench_mean_m_a = np.mean(bench_ret_arr_a) / 100.0
            bench_std_m_a = np.std(bench_ret_arr_a, ddof=1) / 100.0 if total_months_a > 1 else np.nan
            bench_annual_vol_a = bench_std_m_a * np.sqrt(12) * 100 if not np.isnan(bench_std_m_a) else np.nan
            bench_sharpe_a = (bench_mean_m_a * 12) / (bench_std_m_a * np.sqrt(12)) if bench_std_m_a and bench_std_m_a > 0 else np.nan

            bench_downside_a = bench_ret_arr_a[bench_ret_arr_a < 0] / 100.0
            bench_downside_std_a = np.std(bench_downside_a, ddof=1) if len(bench_downside_a) > 1 else np.nan
            bench_sortino_a = (bench_mean_m_a * 12) / (bench_downside_std_a * np.sqrt(12)) if bench_downside_std_a and bench_downside_std_a > 0 else np.nan

            bench_ulcer_a = np.sqrt(np.mean(bench_dd_arr_a ** 2))
            bench_upi_a = bench_cagr_a / bench_ulcer_a if bench_ulcer_a > 0 else np.nan

            alloc_list_a = bt_results_a["alloc"].tolist()
            monthly_turnovers_a = []
            prev_alloc_a = {}
            for alloc_d in alloc_list_a:
                all_tk_a = set(prev_alloc_a.keys()) | set(alloc_d.keys())
                diff_a = sum(abs(alloc_d.get(t, 0.0) - prev_alloc_a.get(t, 0.0)) for t in all_tk_a)
                monthly_turnovers_a.append(diff_a / 2.0)
                prev_alloc_a = alloc_d
            avg_turnover_a = np.mean(monthly_turnovers_a) if monthly_turnovers_a else 0.0
            annual_turnover_a = avg_turnover_a * 12

            metrics_rows_a = [
                ("기간 수익률", _fmt_pct_a(period_ret_a), _fmt_pct_a(bench_period_ret_a)),
                ("연환산 수익률 (CAGR)", _fmt_pct_a(cagr_a), _fmt_pct_a(bench_cagr_a)),
                ("이번 달 수익률", _fmt_pct_a(port_ret_arr_a[-1]), _fmt_pct_a(bench_ret_arr_a[-1])),
                ("올해 수익률 (YTD)", _fmt_pct_a(port_ytd_a), _fmt_pct_a(bench_ytd_a)),
                ("월 최고 수익률", _fmt_pct_a(port_ret_arr_a.max()), _fmt_pct_a(bench_ret_arr_a.max())),
                ("월 최저 수익률", _fmt_pct_a(port_ret_arr_a.min()), _fmt_pct_a(bench_ret_arr_a.min())),
                ("수익 월 비중", f"{win_months_a} / {total_months_a}", f"{bench_win_months_a} / {total_months_a}"),
                ("연 변동성", _fmt_pct_a(annual_vol_a), _fmt_pct_a(bench_annual_vol_a)),
                ("최대 낙폭 (MDD)", _fmt_pct_a(mdd_a), _fmt_pct_a(bench_dd_arr_a.min())),
                ("MDD 시점", mdd_date_a, bench_mdd_date_a),
                ("1년 수익률", _fmt_pct_a(ret_1y_a), _fmt_pct_a(bench_ret_1y_a)),
                ("3년 수익률", _fmt_pct_a(ret_3y_a), _fmt_pct_a(bench_ret_3y_a)),
                ("5년 수익률", _fmt_pct_a(ret_5y_a), _fmt_pct_a(bench_ret_5y_a)),
                ("1년 표준편차", _fmt_pct_a(std_1y_a), _fmt_pct_a(bench_std_1y_a)),
                ("3년 표준편차", _fmt_pct_a(std_3y_a), _fmt_pct_a(bench_std_3y_a)),
                ("5년 표준편차", _fmt_pct_a(std_5y_a), _fmt_pct_a(bench_std_5y_a)),
                ("샤프 지수", f"{sharpe_a:.2f}" if not np.isnan(sharpe_a) else "데이터 부족", f"{bench_sharpe_a:.2f}" if not np.isnan(bench_sharpe_a) else "데이터 부족"),
                ("소티노 지수", f"{sortino_a:.2f}" if not np.isnan(sortino_a) else "데이터 부족", f"{bench_sortino_a:.2f}" if not np.isnan(bench_sortino_a) else "데이터 부족"),
                ("UPI 지수", f"{upi_a:.2f}" if not np.isnan(upi_a) else "데이터 부족", f"{bench_upi_a:.2f}" if not np.isnan(bench_upi_a) else "데이터 부족"),
                ("연간 턴오버", f"{annual_turnover_a:.1f}%", "0.0%"),
            ]
            df_metrics_a = pd.DataFrame(metrics_rows_a, columns=["지표", "전략A", "QQQ"])
            render_gl_table(df_metrics_a)
            st.caption(f"※ 기간: {bt_results_a['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_a['date'].iloc[-1].strftime('%Y-%m')} 야후 파이낸스 실시간 데이터 기준. 1/3/5년 지표는 해당 기간의 월 데이터가 충분할 때만 표시됩니다. 비용·세금 반영 중에는 QQQ도 같은 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)의 세후 값입니다.")




            st.markdown("##### 🗓️ 월별 세부 리밸런싱 기록")
            display_bt_a = bt_results_a.copy()
            display_bt_a["연월"] = display_bt_a["date"].dt.strftime("%Y-%m")
            display_bt_a["월 수익률"] = display_bt_a["monthly_return"].apply(lambda x: f"{x:+.2f}%")
            display_bt_a["낙폭"] = display_bt_a["drawdown"].apply(lambda x: f"{x:.2f}%")
            display_bt_a["NAV"] = display_bt_a["nav"].apply(lambda x: f"{x:.1f}")

            st.dataframe(
                display_bt_a[["연월", "mode", "월 수익률", "weights_str", "NAV", "낙폭"]].iloc[::-1],
                use_container_width=True, hide_index=True
            )

    with c_b:
        render_macro_board()
        st.header("⚡ 전략 B (공격형)")
        
        with st.expander("📖 전략 B 명세서", expanded=False):
            st.markdown(r"""
## 개요

전략 B는 TIP 모멘텀의 방향으로 국면을 판단해, 3배 레버리지·리츠 또는 인버스 자산 중 1종목에 100% 집중하는 월간 로테이션 전략입니다. 2026 혼합전략에서 33.33%를 맡는 고수익·고변동 축입니다.

| 항목 | 내용 |
| --- | --- |
| 카나리아 | TIP 5구간(1·3·6·9·12개월) 평균 모멘텀 |
| 공격 조건 | TIP 스코어 > 0 |
| 공격 시 | 공격 자산 3개 중 가중 모멘텀 1위 100% |
| 방어 시 | 방어 자산 3개 중 5개월 수익률 1위, 그 자산의 5구간 평균 ≤ 0이면 현금 100% |
| 리밸런싱 | 매월 말 종가 기준 전량 재배분, 월중 매매 없음 |

## 자산군

| 구분 | 티커 |
| --- | --- |
| 공격 (3개) | TYD(미국채 3X), UPRO(S&P500 3X), VNQ(리츠) |
| 방어 (3개) | DOG(다우 인버스), RWM(러셀2000 인버스), TBF(미국채 장기 인버스) |

## 운용 규칙

**모멘텀 정의**: R_n = (당월 말 종가 ÷ n개월 전 월말 종가 − 1) × 100.

1. **국면 판단**: 매월 말 TIP 5구간 평균 모멘텀이 0보다 크면 공격, 0 이하면 방어입니다. 5개 구간 중 하나라도 계산되지 않는 달은 건너뜁니다.
2. **공격 스코어**: 공격 자산 3개에 최근 수익률 비중이 큰 가중 모멘텀을 계산합니다. R_12가 있어야 후보가 됩니다.
3. **공격 배분**: 점수 1위에 100%. 컷오프 없음, 후보가 없으면 현금 100%.
4. **방어 선정**: 방어 자산 3개 중 최근 5개월 수익률(R_5)이 가장 높은 자산을 고릅니다.
5. **방어 필터**: 선정 자산의 5구간 평균 모멘텀이 0보다 크면 100% 투자, 아니면 현금 100%.

방어 시 순위(R_5)와 진입 필터(5구간 평균)가 서로 다른 지표라는 점이 전략 A·C와 다릅니다.
""")
            st.latex(r"Canary_B = \frac{R_1 + R_3 + R_6 + R_9 + R_{12}}{5}\,(TIP) \qquad Score_{\text{공격}} = \frac{12R_1 + 4R_3 + 2R_6 + R_{12}}{19}")
            st.markdown(r"""
## 혼합전략 안에서의 역할

전략 B 비중은 혼합 포트폴리오의 33.33%이므로, 선택된 1종목이 전체의 33.33%가 됩니다. TBF는 전략 A 방어 자산과 겹쳐, 두 전략이 함께 방어일 때 TBF 비중이 최대 66.67%까지 커질 수 있습니다. 혼합전략의 비중 상한(기본 35%)은 이런 중복을 제한하는 장치입니다.

## 화면 구성

1. 카나리아 신호: TIP 5구간 모멘텀과 🟢 공격 / 🔴 방어 라벨, '🧭 전환까지 거리', '📖 카나리아 신호 읽는 법'(지금 숫자로 해석 자동 생성)
2. 자산 순위표와 최종 포트폴리오 가이드
3. 이번 달 일별 수익률: 직전 월말 확정 포트폴리오의 일간·월초 대비 누적 수익률과 종목별 기여도 (최신 종가가 늦으면 자동 보완, '🔍 데이터 확인'으로 원본 종가 확인)
4. 백테스트 성과 분석: 시작일 선택(2015-01-01 기본, 2004, 2000, 2018, 2020), 자산 곡선, 연도별·월별 수익률, 낙폭, 드로다운 Top 10, 폭락 시장 성과, 주요 지표 비교(vs QQQ), 월별 리밸런싱 기록

신호 화면은 실시간 현재가로 계산한 참고값입니다. 실제 매매 판단은 월말 종가로 합니다.

## 백테스트 가정과 한계

- 월말 종가로 신호를 계산하고 같은 종가에 체결했다고 봅니다. 현금 수익률은 0%입니다.
- 슬리피지·세금은 기본으로 반영되며(슬리피지 0.2%/회, 양도세 22%) 혼합전략 탭 상단 설정에서 끄거나 바꿀 수 있습니다. 환전 비용은 반영하지 않았습니다. 1종목 전량 교체가 잦아 비용 영향이 큽니다.
- 3배 레버리지 ETF는 변동성 손실(음의 복리)이 있어, 횡보·급변 구간에서 기초지수 3배보다 성과가 나빠질 수 있습니다.
- 1종목 집중이라 월중 급락을 그대로 받습니다.
""")

        st.markdown(
            "**1단계: 카나리아 신호 판단** \n"
            "TIP의 단순 모멘텀 스코어가 양수($> 0$)이면 공격, 음수($\\le 0$)이면 방어 모드로 진입합니다."
        )
        col1_b, col2_b = st.columns(2)
        col1_b.metric("TIP 현재가", f"${tip_current:.2f}")
        col2_b.metric("TIP 단순 모멘텀", f"{tip_score_b:.2f}%")
        col2_b.markdown(_mode_pill(is_attack_b), unsafe_allow_html=True)
        render_canary_guide_single("B", tip_ratio, tip_score_b, realtime_dy, is_attack_b, tip_closes, tip_current)
        
        if is_attack_b:
            st.success("⚔️ **현재 모드: 공격 자산 모드** - 레버리지 투자를 적극 실행합니다.")
            df_off_b = df_all[df_all["Ticker"].isin(OFFENSIVE_B)].copy()
            df_off_b = df_off_b.sort_values(by="B_공격스코어", ascending=False)
            
            st.write("**공격 자산 순위 (1-3-6-12M 가중 평균 모멘텀):**")
            st.caption("가중치 공식: $\\frac{12 \\cdot R_1 + 4 \\cdot R_3 + 2 \\cdot R_6 + R_{12}}{19}$")
            render_html_table(
                df_off_b[["Ticker", "현재가", "1M", "3M", "6M", "12M", "B_공격스코어"]]
                .rename(columns={"B_공격스코어": "가중 모멘텀 스코어"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드 (100% 집중 투자)")
            for t, _ in alloc_b.items():
                p = data_dict.get(t, {}).get("현재가", 0.0)
                s = data_dict.get(t, {}).get("B_공격스코어", 0.0)
                st.info(f"🏆 **{t}** : 비중 **100%** (현재가: ${p:.2f}, 가중 모멘텀: {s:.2f}%)")
        else:
            st.warning("🛡️ **현재 모드: 방어 자산 모드** - 인버스 자산을 활용하여 하락장에 방어 베팅합니다.")
            df_def_b = df_all[df_all["Ticker"].isin(DEFENSIVE_B)].copy()
            df_def_b = df_def_b.sort_values(by="5M", ascending=False)
            
            st.write("**방어 자산 순위 (5개월 단순 수익률 기준):**")
            render_html_table(
                df_def_b[["Ticker", "현재가", "5M", "B_단순모멘텀"]]
                .rename(columns={"5M": "5개월 수익률", "B_단순모멘텀": "자체 단순모멘텀"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드")
            for t, _ in alloc_b.items():
                if t == "CASH (현금)":
                    st.error("🚨 **현금(CASH) 보유 : 비중 100%**")
                else:
                    p = data_dict.get(t, {}).get("현재가", 0.0)
                    s = data_dict.get(t, {}).get("B_단순모멘텀", 0.0)
                    st.info(f"🏆 **{t}** : 비중 **100%** (현재가: ${p:.2f}, 자체 모멘텀: {s:.2f}%)")

        render_other_mode("B", is_attack_b, df_all, data_dict)   # 🔄 반대 모드로 바뀐다면 (기본 접기)
        st.markdown("---")
        render_intramonth_stop_monitor(hist_prices, spy_divs_hist, strategy="B")

        st.markdown("---")
        render_print_section("b")
        st.markdown("### 🛑 전략 B 백테스트 성과 분석")

        with st.container(border=True):
            st.markdown('<div class="control-header">⚙️ 데이터 범위 및 리스크 관리 설정</div>', unsafe_allow_html=True)
            bt_start_label_b = st.selectbox(
                "분석 및 백테스트 시작일",
                [
                    "2004-01-01 (금융위기 포함 · 닷컴버블 제외)",
                    "2000-01-01 (닷컴버블 및 금융위기 포함)",
                    "2015-01-01 (장기 검증)",
                    "2018-01-01 (코로나 및 금리인상기 포함)",
                    "2020-01-01 (최근 트렌드)"
                ],
                index=2,
                key="bt_start_select_b"
            )
            bt_start_b = bt_start_label_b.split(" ")[0]
            st.caption("선택한 시작일 기준으로 전략 B 백테스트 시뮬레이션(NAV, 연도별/월별 수익률, 낙폭, 리밸런싱 기록)이 즉시 재계산됩니다.")

        with st.spinner("전략 B 실시간 백테스트 엔진 구동 중..."):
            try:
                bt_tickers_b = sorted(set(OFFENSIVE_B + DEFENSIVE_B + ["TIP", "QQQ"]))
                daily_px_b = get_daily_price_history_a(bt_tickers_b, start=bt_start_b)
                monthly_px_b = to_monthly_last_a(daily_px_b)
                bt_results_b = run_backtest_strategy_b_full(monthly_px_b)
                bt_results_b = apply_trading_costs(bt_results_b)
                bt_ok_b = len(bt_results_b) > 0
            except Exception as e:
                st.error(f"전략 B 백테스트 데이터 로딩 중 오류가 발생했습니다: {e}")
                bt_ok_b = False

        if not bt_ok_b:
            st.warning("백테스트 데이터가 부족하거나 오류가 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.caption(f"시뮬레이션 기간: {bt_results_b['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_b['date'].iloc[-1].strftime('%Y-%m')}")
            cost_status_caption(bt_results_b)

            total_days_b = (bt_results_b["date"].iloc[-1] - bt_results_b["date"].iloc[0]).days
            total_years_b = total_days_b / 365.25 if total_days_b > 0 else 1.0
            final_nav_b = bt_results_b["nav"].iloc[-1]

            cagr_b = ((final_nav_b / 100.0) ** (1 / total_years_b) - 1) * 100
            mdd_b = bt_results_b["drawdown"].min()

            hl_cards([
                ("연환산 복리 수익률 (CAGR)", cagr_b, "연평균 복리 수익률"),
                ("최대 낙폭 (MDD)", f"{mdd_b:.2f}%", "직전 고점 대비 최대 하락", "neg"),
                ("최종 자산 가치 (NAV)", f"{final_nav_b:.1f}", "초기금 100 기준", "neutral"),
            ])

            st.markdown("##### 📈 자산 곡선 (NAV) 추이")
            chart_df_b = bt_results_b.copy()
            chart_df_b["date_str"] = chart_df_b["date"].dt.strftime("%Y-%m")

            qqq_ret_series_b = benchmark_after_costs(monthly_px_b["QQQ"].pct_change().reindex(bt_results_b["date"]))
            chart_df_b["qqq_nav"] = (100 * (1 + qqq_ret_series_b.fillna(0)).cumprod()).values

            nav_color_scale_b = alt.Scale(domain=["전략B", "QQQ"], range=["#f97316", "#808080"])
            nav_long_b = chart_df_b.melt(
                id_vars="date_str", value_vars=["nav", "qqq_nav"], var_name="series", value_name="value"
            )
            nav_long_b["series"] = nav_long_b["series"].map({"nav": "전략B", "qqq_nav": "QQQ"})

            nav_chart_b = alt.Chart(nav_long_b).mark_line(size=2.5).encode(
                x=alt.X("date_str:N", sort=None, title="년-월"),
                y=alt.Y("value:Q", title="NAV (기준 100)"),
                color=alt.Color("series:N", scale=nav_color_scale_b, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("date_str:N", title="년-월"),
                    alt.Tooltip("series:N", title="구분"),
                    alt.Tooltip("value:Q", title="NAV", format=".1f"),
                ],
            ).properties(height=350)
            st.altair_chart(nav_chart_b, use_container_width=True)

            # ------------------------------------------------------------
            # 연도별 수익률 (Annual Returns) — 막대 차트
            # ------------------------------------------------------------
            render_cost_quick_switch("b")
            st.markdown("##### 📊 연도별 수익률 (%)")
            yearly_df_b = bt_results_b.copy()
            yearly_df_b["year"] = yearly_df_b["date"].dt.year
            yearly_returns_b = (
                yearly_df_b.groupby("year")["monthly_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            yearly_returns_b["year_str"] = yearly_returns_b["year"].astype(str)
            yearly_returns_b["series"] = "전략B"
            year_sort_order_b = yearly_returns_b["year_str"].tolist()

            qqq_monthly_ret_b = benchmark_after_costs(monthly_px_b["QQQ"].pct_change().reindex(bt_results_b["date"])) * 100
            qqq_ret_df_b = pd.DataFrame({
                "date": bt_results_b["date"].values,
                "qqq_return": qqq_monthly_ret_b.values,
            })
            qqq_ret_df_b["year"] = pd.to_datetime(qqq_ret_df_b["date"]).dt.year
            qqq_yearly_b = (
                qqq_ret_df_b.groupby("year")["qqq_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            qqq_yearly_b["year_str"] = qqq_yearly_b["year"].astype(str)
            qqq_yearly_b["series"] = "QQQ"

            color_scale_b = alt.Scale(domain=["전략B", "QQQ"], range=["#f97316", "#808080"])

            annual_bar_b = alt.Chart(yearly_returns_b).mark_bar().encode(
                x=alt.X("year_str:N", title="연도", sort=year_sort_order_b, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q", title="수익률 (%)"),
                color=alt.Color("series:N", scale=color_scale_b, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="수익률", format="+.2f"),
                ],
            )
            annual_labels_b = alt.Chart(yearly_returns_b).mark_text(
                dy=alt.expr("datum.annual_return >= 0 ? -8 : 14"), fontWeight="bold", fontSize=10, color="#0f172a"
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_b, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                text=alt.Text("annual_return:Q", format=".1f"),
            )
            qqq_points_b = alt.Chart(qqq_yearly_b).mark_point(
                filled=True, size=110, stroke="white", strokeWidth=1.2
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_b, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                color=alt.Color("series:N", scale=color_scale_b, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="QQQ 수익률", format="+.2f"),
                ],
            )
            st.altair_chart(
                (annual_bar_b + annual_labels_b + qqq_points_b).properties(height=320),
                use_container_width=True,
            )

            # ------------------------------------------------------------
            # 월별 수익률 (Monthly Returns) — 히트맵 테이블
            # ------------------------------------------------------------
            monthly_compound_cards(bt_results_b)
            st.markdown("##### 🗓️ 월별 수익률 (%)")
            monthly_df_b = bt_results_b.copy()
            monthly_df_b["year"] = monthly_df_b["date"].dt.year
            monthly_df_b["month"] = monthly_df_b["date"].dt.month

            month_labels_b = {m: (f"{m}월*" if (m == 6 and COST_TAX_ON) else f"{m}월") for m in range(1, 13)}  # 양도세 반영 시 6월에 * 표시
            monthly_df_b["month_label"] = monthly_df_b["month"].map(month_labels_b)
            monthly_df_b["year_label"] = monthly_df_b["year"].astype(str)

            avg_by_month_b = monthly_df_b.groupby(["month", "month_label"])["monthly_return"].mean().reset_index()
            avg_by_month_b["year_label"] = "평균"

            heat_df_b = pd.concat([
                monthly_df_b[["year_label", "month", "month_label", "monthly_return"]],
                avg_by_month_b[["year_label", "month", "month_label", "monthly_return"]],
            ], ignore_index=True)

            year_sort_order_full_b = [str(y) for y in sorted(monthly_df_b["year"].unique())] + ["평균"]
            month_sort_order_b = [month_labels_b[m] for m in range(1, 13)]

            heat_rect_b = alt.Chart(heat_df_b).mark_rect(stroke="white", strokeWidth=1.5).encode(
                x=alt.X("month_label:N", title=None, sort=month_sort_order_b, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", title=None, sort=year_sort_order_full_b),
                color=alt.Color(
                    "monthly_return:Q",
                    scale=alt.Scale(
                        type="threshold",
                        domain=[-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5],
                        range=["#cf6265", "#e67f82", "#ecaaab", "#f6d4d5", "#fafbff",
                               "#d7e4da", "#accab2", "#82ae8b", "#599265"],
                    ),
                    legend=alt.Legend(title="수익률 (%)", orient="bottom", gradientLength=220),
                ),
                tooltip=[
                    alt.Tooltip("year_label:N", title="연도"),
                    alt.Tooltip("month_label:N", title="월"),
                    alt.Tooltip("monthly_return:Q", title="수익률", format="+.2f"),
                ],
            )
            heat_text_b = alt.Chart(heat_df_b).mark_text(fontSize=10, fontWeight="bold").encode(
                x=alt.X("month_label:N", sort=month_sort_order_b, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", sort=year_sort_order_full_b),
                text=alt.Text("monthly_return:Q", format="+.1f"),
                color=alt.value("#334155"),
            )
            st.altair_chart(
                (heat_rect_b + heat_text_b).properties(height=32 * len(year_sort_order_full_b) + 80),
                use_container_width=True,
            )
            render_monthly_return_table(heat_df_b, year_sort_order_full_b, month_sort_order_b, "b")
            if COST_TAX_ON:
                st.caption("* 6월 수익률에는 전년도 양도세 납부분이 포함되어 있습니다. (전년도 수익에 대한 세금을 6월 말에 한꺼번에 차감하므로 6월 수익률이 낮게 나옵니다)")

            st.markdown("##### 📉 낙폭 (Drawdown) 히스토리")
            render_drawdown_with_benchmark(chart_df_b, "전략B")

            st.markdown("##### 🚨 포트폴리오 드로우다운 Top 10")
            dd_vals_b = bt_results_b["drawdown"].values
            dd_dates_b = bt_results_b["date"].values
            n_b = len(dd_vals_b)
            episodes_b = []
            i_ep_b = 0
            while i_ep_b < n_b:
                if dd_vals_b[i_ep_b] < -0.001:
                    start_i_b = i_ep_b
                    j_ep_b = i_ep_b
                    min_val_b = dd_vals_b[i_ep_b]
                    min_idx_b = i_ep_b
                    while j_ep_b < n_b and dd_vals_b[j_ep_b] < -0.001:
                        if dd_vals_b[j_ep_b] < min_val_b:
                            min_val_b = dd_vals_b[j_ep_b]
                            min_idx_b = j_ep_b
                        j_ep_b += 1
                    episodes_b.append({
                        "시작": pd.Timestamp(dd_dates_b[start_i_b]).strftime("%Y/%m"),
                        "종료": pd.Timestamp(dd_dates_b[min_idx_b]).strftime("%Y/%m"),
                        "드로우다운": min_val_b,
                    })
                    i_ep_b = j_ep_b
                else:
                    i_ep_b += 1

            episodes_b.sort(key=lambda x: x["드로우다운"])
            top10_b = episodes_b[:10]
            for idx, ep in enumerate(top10_b):
                ep["순위"] = idx + 1
                ep["드로우다운"] = f"{ep['드로우다운']:.1f}%"
                ep["주요 이슈"] = issues_for_period(ep["시작"], ep["종료"])
            if top10_b:
                df_dd_top10_b = pd.DataFrame(top10_b)[["순위", "시작", "종료", "드로우다운", "주요 이슈"]]
                st.dataframe(df_dd_top10_b, use_container_width=True, hide_index=True)
                st.caption("※ 드로우다운은 시작월 직전 고점부터 종료월(최저점)까지의 하락률입니다. '주요 이슈'는 시작\\~종료월과 기간이 겹치는 대형 이슈이며, 겹치는 이슈가 없으면 '-'입니다.")
            else:
                st.info("드로우다운 구간이 발견되지 않았습니다.")

            st.markdown("##### 🔻 폭락 시장 포트폴리오 성과")
            STRESS_PERIODS_B = [
                ("코로나 팬데믹", "2020-01-01", "2020-03-31"),
                ("2022 긴축 발작 (금리인상기)", "2022-01-01", "2022-10-31"),
                ("2018년 4분기 조정", "2018-10-01", "2018-12-31"),
            ]
            stress_rows_b = []
            for label_b, s_str_b, e_str_b in STRESS_PERIODS_B:
                s_ts_b, e_ts_b = pd.Timestamp(s_str_b), pd.Timestamp(e_str_b)
                mask_b = (bt_results_b["date"] >= s_ts_b) & (bt_results_b["date"] <= e_ts_b)
                sub_b = bt_results_b[mask_b]
                if len(sub_b) == 0:
                    continue
                port_cum_b = (np.prod(1 + sub_b["monthly_return"].values / 100.0) - 1) * 100
                bench_sub_ret_b = qqq_ret_series_b.reindex(sub_b["date"]).fillna(0.0)
                bench_cum_b = (np.prod(1 + bench_sub_ret_b.values) - 1) * 100
                stress_rows_b.append({
                    "스트레스 기간": label_b,
                    "시작": s_ts_b.strftime("%Y/%m"),
                    "종료": e_ts_b.strftime("%Y/%m"),
                    "포트폴리오 수익률": f"{port_cum_b:+.1f}%",
                    "QQQ 수익률": f"{bench_cum_b:+.1f}%",
                })
            if stress_rows_b:
                st.dataframe(pd.DataFrame(stress_rows_b), use_container_width=True, hide_index=True)
            else:
                st.info("선택한 시작일 범위 내 해당하는 폭락장 스트레스 기간 데이터가 없습니다. 시작일을 앞당겨 보세요.")

            st.markdown("##### 📊 주요 지표 비교 (vs QQQ)")

            def _fmt_pct_b(x):
                return f"{x:.1f}%" if x is not None and not (isinstance(x, float) and np.isnan(x)) else "데이터 부족"

            port_ret_arr_b = bt_results_b["monthly_return"].values
            bench_ret_arr_b = qqq_monthly_ret_b.values
            dd_arr_b = bt_results_b["drawdown"].values
            bench_nav_arr_b = chart_df_b["qqq_nav"].values
            bench_running_max_b = np.maximum.accumulate(bench_nav_arr_b)
            bench_dd_arr_b = (bench_nav_arr_b / bench_running_max_b - 1) * 100

            period_ret_b = (final_nav_b / 100.0 - 1) * 100
            bench_final_nav_b = bench_nav_arr_b[-1]
            bench_period_ret_b = (bench_final_nav_b / 100.0 - 1) * 100
            bench_cagr_b = ((bench_final_nav_b / 100.0) ** (1 / total_years_b) - 1) * 100

            last_date2_b = bt_results_b["date"].iloc[-1]
            current_year2_b = last_date2_b.year
            ytd_mask_b = bt_results_b["date"].dt.year == current_year2_b
            port_ytd_b = (np.prod(1 + bt_results_b.loc[ytd_mask_b, "monthly_return"].values / 100.0) - 1) * 100
            bench_ytd_b = (np.prod(1 + (bench_ret_arr_b[ytd_mask_b.values] / 100.0)) - 1) * 100

            win_months_b = int((port_ret_arr_b > 0).sum())
            bench_win_months_b = int((bench_ret_arr_b > 0).sum())
            total_months_b = len(port_ret_arr_b)

            mdd_idx_b = int(np.argmin(dd_arr_b))
            mdd_date_b = bt_results_b["date"].iloc[mdd_idx_b].strftime("%Y-%m")
            bench_mdd_idx_b = int(np.argmin(bench_dd_arr_b))
            bench_mdd_date_b = bt_results_b["date"].iloc[bench_mdd_idx_b].strftime("%Y-%m")

            def _trailing_b(arr, months):
                if len(arr) < months:
                    return None, None
                window = arr[-months:]
                cum = (np.prod(1 + window / 100.0) - 1) * 100
                ann_std = np.std(window, ddof=1) * np.sqrt(12) if len(window) > 1 else None
                return cum, ann_std

            ret_1y_b, std_1y_b = _trailing_b(port_ret_arr_b, 12)
            ret_3y_b, std_3y_b = _trailing_b(port_ret_arr_b, 36)
            ret_5y_b, std_5y_b = _trailing_b(port_ret_arr_b, 60)
            bench_ret_1y_b, bench_std_1y_b = _trailing_b(bench_ret_arr_b, 12)
            bench_ret_3y_b, bench_std_3y_b = _trailing_b(bench_ret_arr_b, 36)
            bench_ret_5y_b, bench_std_5y_b = _trailing_b(bench_ret_arr_b, 60)

            mean_m_b = np.mean(port_ret_arr_b) / 100.0
            std_m_b = np.std(port_ret_arr_b, ddof=1) / 100.0 if total_months_b > 1 else np.nan
            annual_vol_b = std_m_b * np.sqrt(12) * 100 if not np.isnan(std_m_b) else np.nan
            sharpe_b = (mean_m_b * 12) / (std_m_b * np.sqrt(12)) if std_m_b and std_m_b > 0 else np.nan

            downside_b = port_ret_arr_b[port_ret_arr_b < 0] / 100.0
            downside_std_b = np.std(downside_b, ddof=1) if len(downside_b) > 1 else np.nan
            sortino_b = (mean_m_b * 12) / (downside_std_b * np.sqrt(12)) if downside_std_b and downside_std_b > 0 else np.nan

            ulcer_b = np.sqrt(np.mean(dd_arr_b ** 2))
            upi_b = cagr_b / ulcer_b if ulcer_b > 0 else np.nan

            bench_mean_m_b = np.mean(bench_ret_arr_b) / 100.0
            bench_std_m_b = np.std(bench_ret_arr_b, ddof=1) / 100.0 if total_months_b > 1 else np.nan
            bench_annual_vol_b = bench_std_m_b * np.sqrt(12) * 100 if not np.isnan(bench_std_m_b) else np.nan
            bench_sharpe_b = (bench_mean_m_b * 12) / (bench_std_m_b * np.sqrt(12)) if bench_std_m_b and bench_std_m_b > 0 else np.nan

            bench_downside_b = bench_ret_arr_b[bench_ret_arr_b < 0] / 100.0
            bench_downside_std_b = np.std(bench_downside_b, ddof=1) if len(bench_downside_b) > 1 else np.nan
            bench_sortino_b = (bench_mean_m_b * 12) / (bench_downside_std_b * np.sqrt(12)) if bench_downside_std_b and bench_downside_std_b > 0 else np.nan

            bench_ulcer_b = np.sqrt(np.mean(bench_dd_arr_b ** 2))
            bench_upi_b = bench_cagr_b / bench_ulcer_b if bench_ulcer_b > 0 else np.nan

            alloc_list_b = bt_results_b["alloc"].tolist()
            monthly_turnovers_b = []
            prev_alloc_b = {}
            for alloc_d in alloc_list_b:
                all_tk_b = set(prev_alloc_b.keys()) | set(alloc_d.keys())
                diff_b = sum(abs(alloc_d.get(t, 0.0) - prev_alloc_b.get(t, 0.0)) for t in all_tk_b)
                monthly_turnovers_b.append(diff_b / 2.0)
                prev_alloc_b = alloc_d
            avg_turnover_b = np.mean(monthly_turnovers_b) if monthly_turnovers_b else 0.0
            annual_turnover_b = avg_turnover_b * 12

            metrics_rows_b = [
                ("기간 수익률", _fmt_pct_b(period_ret_b), _fmt_pct_b(bench_period_ret_b)),
                ("연환산 수익률 (CAGR)", _fmt_pct_b(cagr_b), _fmt_pct_b(bench_cagr_b)),
                ("이번 달 수익률", _fmt_pct_b(port_ret_arr_b[-1]), _fmt_pct_b(bench_ret_arr_b[-1])),
                ("올해 수익률 (YTD)", _fmt_pct_b(port_ytd_b), _fmt_pct_b(bench_ytd_b)),
                ("월 최고 수익률", _fmt_pct_b(port_ret_arr_b.max()), _fmt_pct_b(bench_ret_arr_b.max())),
                ("월 최저 수익률", _fmt_pct_b(port_ret_arr_b.min()), _fmt_pct_b(bench_ret_arr_b.min())),
                ("수익 월 비중", f"{win_months_b} / {total_months_b}", f"{bench_win_months_b} / {total_months_b}"),
                ("연 변동성", _fmt_pct_b(annual_vol_b), _fmt_pct_b(bench_annual_vol_b)),
                ("최대 낙폭 (MDD)", _fmt_pct_b(mdd_b), _fmt_pct_b(bench_dd_arr_b.min())),
                ("MDD 시점", mdd_date_b, bench_mdd_date_b),
                ("1년 수익률", _fmt_pct_b(ret_1y_b), _fmt_pct_b(bench_ret_1y_b)),
                ("3년 수익률", _fmt_pct_b(ret_3y_b), _fmt_pct_b(bench_ret_3y_b)),
                ("5년 수익률", _fmt_pct_b(ret_5y_b), _fmt_pct_b(bench_ret_5y_b)),
                ("1년 표준편차", _fmt_pct_b(std_1y_b), _fmt_pct_b(bench_std_1y_b)),
                ("3년 표준편차", _fmt_pct_b(std_3y_b), _fmt_pct_b(bench_std_3y_b)),
                ("5년 표준편차", _fmt_pct_b(std_5y_b), _fmt_pct_b(bench_std_5y_b)),
                ("샤프 지수", f"{sharpe_b:.2f}" if not np.isnan(sharpe_b) else "데이터 부족", f"{bench_sharpe_b:.2f}" if not np.isnan(bench_sharpe_b) else "데이터 부족"),
                ("소티노 지수", f"{sortino_b:.2f}" if not np.isnan(sortino_b) else "데이터 부족", f"{bench_sortino_b:.2f}" if not np.isnan(bench_sortino_b) else "데이터 부족"),
                ("UPI 지수", f"{upi_b:.2f}" if not np.isnan(upi_b) else "데이터 부족", f"{bench_upi_b:.2f}" if not np.isnan(bench_upi_b) else "데이터 부족"),
                ("연간 턴오버", f"{annual_turnover_b:.1f}%", "0.0%"),
            ]
            df_metrics_b = pd.DataFrame(metrics_rows_b, columns=["지표", "전략B", "QQQ"])
            render_gl_table(df_metrics_b)
            st.caption(f"※ 기간: {bt_results_b['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_b['date'].iloc[-1].strftime('%Y-%m')} 야후 파이낸스 실시간 데이터 기준. 1/3/5년 지표는 해당 기간의 월 데이터가 충분할 때만 표시됩니다. 비용·세금 반영 중에는 QQQ도 같은 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)의 세후 값입니다.")




            st.markdown("##### 🗓️ 월별 세부 리밸런싱 기록")
            display_bt_b = bt_results_b.copy()
            display_bt_b["연월"] = display_bt_b["date"].dt.strftime("%Y-%m")
            display_bt_b["월 수익률"] = display_bt_b["monthly_return"].apply(lambda x: f"{x:+.2f}%")
            display_bt_b["낙폭"] = display_bt_b["drawdown"].apply(lambda x: f"{x:.2f}%")
            display_bt_b["NAV"] = display_bt_b["nav"].apply(lambda x: f"{x:.1f}")

            st.dataframe(
                display_bt_b[["연월", "mode", "월 수익률", "weights_str", "NAV", "낙폭"]].iloc[::-1],
                use_container_width=True, hide_index=True
            )

    with c_c:
        render_macro_board()
        st.header("🔄 전략 C (섹터로테이션)")
        
        with st.expander("📖 전략 C 명세서", expanded=False):
            st.markdown(r"""
## 개요

전략 C는 S&P 500(SPY) 배당수익률로 주식시장의 저평가·과열을 판단해, 주도 섹터 1개 또는 원자재·채권 1개에 100% 투자하는 월간 섹터 로테이션 전략입니다. 2026 혼합전략에서 33.33%를 맡습니다.

| 항목 | 내용 |
| --- | --- |
| 카나리아 | SPY 최근 365일 배당 합계 ÷ 월말 SPY 실제 종가(배당 미조정) |
| 공격 조건 | 배당수익률 > 1.33% (저평가 국면) |
| 공격 시 | 섹터 ETF 7개 중 모멘텀 1위 100% |
| 방어 시 | 원자재·채권 5개 중 모멘텀 1위 100%, 1위 점수 ≤ 0이면 현금 100% |
| 리밸런싱 | 매월 말 종가 기준 전량 재배분, 월중 매매 없음 |

## 자산군

| 구분 | 티커 |
| --- | --- |
| 공격 (7개) | FDN, LIT, SMH, XLE, IGV, QQQM, XLU |
| 방어 (5개) | GLD, PDBC, OILK, SHY, TLT |

## 운용 규칙

**모멘텀 정의**: R_n = (당월 말 종가 ÷ n개월 전 월말 종가 − 1) × 100.

1. **국면 판단**: 매월 말 배당수익률이 1.33%를 넘으면 공격, 이하면 방어입니다. 배당 합계가 0이거나 가격이 없는 달은 건너뜁니다.
2. **공격 스코어**: 섹터 ETF 7개에 4구간 평균 모멘텀을 계산합니다. R_12가 있어야 후보가 됩니다.
3. **공격 배분**: 점수 1위 섹터에 100%. 컷오프 없음, 후보가 없으면 현금 100%.
4. **방어 스코어**: 원자재·채권 5개에 5구간 평균 모멘텀을 계산합니다.
5. **방어 배분**: 점수 1위에 100%. 1위 점수가 0 이하면 현금 100%.
""")
            st.latex(r"DY = \frac{\sum Div_{SPY}(\text{최근 365일})}{P_{SPY}(\text{월말})} \times 100 \qquad Score_{\text{공격}} = \frac{R_1 + R_3 + R_6 + R_{12}}{4} \qquad Score_{\text{방어}} = \frac{R_1 + R_3 + R_6 + R_9 + R_{12}}{5}")
            st.markdown(r"""
## 혼합전략 안에서의 역할

전략 C 비중은 혼합 포트폴리오의 33.33%이므로, 선택된 1종목이 전체의 33.33%가 됩니다. SMH·LIT·XLE는 전략 A 공격 자산과, GLD는 전략 A 공격 자산과 겹칩니다. 예를 들어 A가 SMH 25%, C가 SMH 100%를 고르면 혼합 비중은 41.67%가 되며, 혼합전략의 비중 상한(기본 35%)이 켜져 있으면 초과분이 현금이 됩니다.

## 화면 구성

1. 카나리아 신호: 실시간 배당수익률과 🟢 공격 / 🔴 방어 라벨, '🧭 전환까지 거리', '📖 카나리아 신호 읽는 법'(지금 숫자로 해석 자동 생성)
2. 자산 순위표와 최종 포트폴리오 가이드
3. 이번 달 일별 수익률: 직전 월말 확정 포트폴리오의 일간·월초 대비 누적 수익률과 종목별 기여도 (최신 종가가 늦으면 자동 보완, '🔍 데이터 확인'으로 원본 종가 확인)
4. 백테스트 성과 분석: 시작일 선택(2015-01-01 기본, 2004, 2000, 2018, 2020), 자산 곡선, 연도별·월별 수익률, 낙폭, 드로다운 Top 10, 폭락 시장 성과, 주요 지표 비교(vs QQQ), 월별 리밸런싱 기록

실시간 배당수익률은 최근 배당 이력과 현재가로 따로 계산한 참고값입니다. 실제 매매 판단은 월말 종가로 합니다.

## 백테스트 가정과 한계

- 월말 종가로 신호를 계산하고 같은 종가에 체결했다고 봅니다. 현금 수익률은 0%입니다.
- 슬리피지·세금은 기본으로 반영되며(슬리피지 0.2%/회, 양도세 22%) 혼합전략 탭 상단 설정에서 끄거나 바꿀 수 있습니다. 환전 비용은 반영하지 않았습니다.
- 배당수익률은 SPY 실제 종가(배당 미조정)로 나눠 계산합니다(2026-10-05 수정). 이전의 수정주가 방식은 과거 배당수익률을 부풀려 2000~2002 닷컴 구간에도 공격 신호를 냈지만, 지금은 그 구간에 방어 신호가 나옵니다. 투자 자산의 수익률은 그대로 수정주가(배당 포함 총수익) 기준입니다.
- 1.33% 기준은 고정값입니다. 금리·배당 성향이 바뀌면 기준의 의미도 달라질 수 있습니다.
- QQQM·OILK 등은 상장 기간이 짧아 초기 구간에는 후보에서 빠집니다.
""")

        st.markdown(
            "**1단계: 카나리아 신호 판단 (S&P 500 배당수익률)** \n"
            "배당수익률이 **1.33%** 초과 시 주식 저평가로 판단하여 공격 모드, 이하일 경우 시장 과열로 판단하여 방어 모드로 진입합니다."
        )
        
        st.markdown(f"""
        <div class="control-panel">
            <div class="control-header">📊 S&P 500 (SPY) 실시간 배당수익률 모니터링</div>
            <div class="control-subheader">
                야후 파이낸스(yfinance) API로부터 소수 및 백분율 단위를 실시간으로 정합 보정하여 산출한 데이터입니다.<br/>
                • <b>실시간 배당수익률: {realtime_dy:.2f}%</b><br/>
                • <b>모드 분류 기준선: 1.33%</b> (초과 시 공격 모드 / 이하 시 방어 모드)
            </div>
        </div>
        """, unsafe_allow_html=True)
        _c_m1, _c_m2 = st.columns(2)
        _c_m1.metric("SPY 배당수익률 (기준 1.33%)", f"{realtime_dy:.2f}%")
        _c_m1.markdown(_mode_pill(is_attack_c), unsafe_allow_html=True)
        render_canary_guide_single("C", tip_ratio, tip_score_b, realtime_dy, is_attack_c, tip_closes, tip_current)
        
        if is_attack_c:
            st.success(f"🔥 **현재 모드: 공격 자산 모드** (실시간 배당수익률 {realtime_dy:.2f}% > 1.33%) - 시장 저평가 국면으로 주식을 매수합니다.")
            df_off_c = df_all[df_all["Ticker"].isin(OFFENSIVE_C)].copy()
            df_off_c = df_off_c.sort_values(by="A_공격스코어", ascending=False)
            
            st.write("**주도 섹터 후보 순위 (1-3-6-12M 단순 평균 모멘텀):**")
            render_html_table(
                df_off_c[["Ticker", "현재가", "1M", "3M", "6M", "12M", "A_공격스코어"]]
                .rename(columns={"A_공격스코어": "모멘텀 스코어"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드 (100% 단일 섹터 투자)")
            for t, _ in alloc_c.items():
                p = data_dict.get(t, {}).get("현재가", 0.0)
                s = data_dict.get(t, {}).get("A_공격스코어", 0.0)
                st.info(f"🏆 **{t}** : 비중 **100%** (현재가: ${p:.2f}, 모멘텀: {s:.2f}%)")
        else:
            st.warning(f"🛡️ **현재 모드: 방어 자산 모드** (실시간 배당수익률 {realtime_dy:.2f}% <= 1.33%) - 시장 과열 국면으로 원자재 자산으로 대피합니다.")
            df_def_c = df_all[df_all["Ticker"].isin(DEFENSIVE_C)].copy()
            df_def_c = df_def_c.sort_values(by="A_방어스코어", ascending=False)
            
            st.write("**원자재 방어 자산 순위 (1-3-6-9-12M 단순 평균 모멘텀):**")
            render_html_table(
                df_def_c[["Ticker", "현재가", "1M", "3M", "6M", "9M", "12M", "A_방어스코어"]]
                .rename(columns={"A_방어스코어": "모멘텀 스코어"}),
                ticker_cols=("Ticker",)
            )
            
            st.subheader("🎯 최종 포트폴리오 가이드")
            for t, _ in alloc_c.items():
                if t == "CASH (현금)":
                    st.error("🚨 **현금(CASH) 보유 : 비중 100%**")
                else:
                    p = data_dict.get(t, {}).get("현재가", 0.0)
                    s = data_dict.get(t, {}).get("A_방어스코어", 0.0)
                    st.info(f"🏆 **{t}** : 비중 **100%** (현재가: ${p:.2f}, 모멘텀: {s:.2f}%)")

        render_other_mode("C", is_attack_c, df_all, data_dict)   # 🔄 반대 모드로 바뀐다면 (기본 접기)
        st.markdown("---")
        render_intramonth_stop_monitor(hist_prices, spy_divs_hist, strategy="C")

        st.markdown("---")
        render_print_section("c")
        st.markdown("### 🛑 전략 C 백테스트 성과 분석")

        with st.container(border=True):
            st.markdown('<div class="control-header">⚙️ 데이터 범위 및 리스크 관리 설정</div>', unsafe_allow_html=True)
            bt_start_label_c = st.selectbox(
                "분석 및 백테스트 시작일",
                [
                    "2004-01-01 (금융위기 포함 · 닷컴버블 제외)",
                    "2000-01-01 (닷컴버블 및 금융위기 포함)",
                    "2015-01-01 (장기 검증)",
                    "2018-01-01 (코로나 및 금리인상기 포함)",
                    "2020-01-01 (최근 트렌드)"
                ],
                index=2,
                key="bt_start_select_c"
            )
            bt_start_c = bt_start_label_c.split(" ")[0]
            st.caption("선택한 시작일 기준으로 전략 C 백테스트 시뮬레이션(NAV, 연도별/월별 수익률, 낙폭, 리밸런싱 기록)이 즉시 재계산됩니다.")

        with st.spinner("전략 C 실시간 백테스트 엔진 구동 중..."):
            try:
                bt_tickers_c = sorted(set(OFFENSIVE_C + DEFENSIVE_C + ["SPY", "QQQ"]))
                daily_px_c = get_daily_price_history_a(bt_tickers_c, start=bt_start_c)
                monthly_px_c = to_monthly_last_a(daily_px_c)
                spy_divs_c = get_spy_dividend_history()
                bt_results_c = run_backtest_strategy_c_full(monthly_px_c, spy_divs_c)
                bt_results_c = apply_trading_costs(bt_results_c)
                bt_ok_c = len(bt_results_c) > 0
            except Exception as e:
                st.error(f"전략 C 백테스트 데이터 로딩 중 오류가 발생했습니다: {e}")
                bt_ok_c = False

        if not bt_ok_c:
            st.warning("백테스트 데이터가 부족하거나 오류가 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.caption(f"시뮬레이션 기간: {bt_results_c['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_c['date'].iloc[-1].strftime('%Y-%m')}")
            cost_status_caption(bt_results_c)

            total_days_c = (bt_results_c["date"].iloc[-1] - bt_results_c["date"].iloc[0]).days
            total_years_c = total_days_c / 365.25 if total_days_c > 0 else 1.0
            final_nav_c = bt_results_c["nav"].iloc[-1]

            cagr_c = ((final_nav_c / 100.0) ** (1 / total_years_c) - 1) * 100
            mdd_c = bt_results_c["drawdown"].min()

            hl_cards([
                ("연환산 복리 수익률 (CAGR)", cagr_c, "연평균 복리 수익률"),
                ("최대 낙폭 (MDD)", f"{mdd_c:.2f}%", "직전 고점 대비 최대 하락", "neg"),
                ("최종 자산 가치 (NAV)", f"{final_nav_c:.1f}", "초기금 100 기준", "neutral"),
            ])

            st.markdown("##### 📈 자산 곡선 (NAV) 추이")
            chart_df_c = bt_results_c.copy()
            chart_df_c["date_str"] = chart_df_c["date"].dt.strftime("%Y-%m")

            qqq_ret_series_c = benchmark_after_costs(monthly_px_c["QQQ"].pct_change().reindex(bt_results_c["date"]))
            chart_df_c["qqq_nav"] = (100 * (1 + qqq_ret_series_c.fillna(0)).cumprod()).values

            nav_color_scale_c = alt.Scale(domain=["전략C", "QQQ"], range=["#8b5cf6", "#808080"])
            nav_long_c = chart_df_c.melt(
                id_vars="date_str", value_vars=["nav", "qqq_nav"], var_name="series", value_name="value"
            )
            nav_long_c["series"] = nav_long_c["series"].map({"nav": "전략C", "qqq_nav": "QQQ"})

            nav_chart_c = alt.Chart(nav_long_c).mark_line(size=2.5).encode(
                x=alt.X("date_str:N", sort=None, title="년-월"),
                y=alt.Y("value:Q", title="NAV (기준 100)"),
                color=alt.Color("series:N", scale=nav_color_scale_c, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("date_str:N", title="년-월"),
                    alt.Tooltip("series:N", title="구분"),
                    alt.Tooltip("value:Q", title="NAV", format=".1f"),
                ],
            ).properties(height=350)
            st.altair_chart(nav_chart_c, use_container_width=True)

            # ------------------------------------------------------------
            # 연도별 수익률 (Annual Returns) — 막대 차트
            # ------------------------------------------------------------
            render_cost_quick_switch("c")
            st.markdown("##### 📊 연도별 수익률 (%)")
            yearly_df_c = bt_results_c.copy()
            yearly_df_c["year"] = yearly_df_c["date"].dt.year
            yearly_returns_c = (
                yearly_df_c.groupby("year")["monthly_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            yearly_returns_c["year_str"] = yearly_returns_c["year"].astype(str)
            yearly_returns_c["series"] = "전략C"
            year_sort_order_c = yearly_returns_c["year_str"].tolist()

            qqq_monthly_ret_c = benchmark_after_costs(monthly_px_c["QQQ"].pct_change().reindex(bt_results_c["date"])) * 100
            qqq_ret_df_c = pd.DataFrame({
                "date": bt_results_c["date"].values,
                "qqq_return": qqq_monthly_ret_c.values,
            })
            qqq_ret_df_c["year"] = pd.to_datetime(qqq_ret_df_c["date"]).dt.year
            qqq_yearly_c = (
                qqq_ret_df_c.groupby("year")["qqq_return"]
                .apply(lambda x: (np.prod(1 + x / 100.0) - 1) * 100)
                .reset_index(name="annual_return")
            )
            qqq_yearly_c["year_str"] = qqq_yearly_c["year"].astype(str)
            qqq_yearly_c["series"] = "QQQ"

            color_scale_c = alt.Scale(domain=["전략C", "QQQ"], range=["#8b5cf6", "#808080"])

            annual_bar_c = alt.Chart(yearly_returns_c).mark_bar().encode(
                x=alt.X("year_str:N", title="연도", sort=year_sort_order_c, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q", title="수익률 (%)"),
                color=alt.Color("series:N", scale=color_scale_c, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="수익률", format="+.2f"),
                ],
            )
            annual_labels_c = alt.Chart(yearly_returns_c).mark_text(
                dy=alt.expr("datum.annual_return >= 0 ? -8 : 14"), fontWeight="bold", fontSize=10, color="#0f172a"
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_c, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                text=alt.Text("annual_return:Q", format=".1f"),
            )
            qqq_points_c = alt.Chart(qqq_yearly_c).mark_point(
                filled=True, size=110, stroke="white", strokeWidth=1.2
            ).encode(
                x=alt.X("year_str:N", sort=year_sort_order_c, scale=alt.Scale(paddingInner=0.5, paddingOuter=0.2)),
                y=alt.Y("annual_return:Q"),
                color=alt.Color("series:N", scale=color_scale_c, legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip("year_str:N", title="연도"),
                    alt.Tooltip("annual_return:Q", title="QQQ 수익률", format="+.2f"),
                ],
            )
            st.altair_chart(
                (annual_bar_c + annual_labels_c + qqq_points_c).properties(height=320),
                use_container_width=True,
            )

            # ------------------------------------------------------------
            # 월별 수익률 (Monthly Returns) — 히트맵 테이블
            # ------------------------------------------------------------
            monthly_compound_cards(bt_results_c)
            st.markdown("##### 🗓️ 월별 수익률 (%)")
            monthly_df_c = bt_results_c.copy()
            monthly_df_c["year"] = monthly_df_c["date"].dt.year
            monthly_df_c["month"] = monthly_df_c["date"].dt.month

            month_labels_c = {m: (f"{m}월*" if (m == 6 and COST_TAX_ON) else f"{m}월") for m in range(1, 13)}  # 양도세 반영 시 6월에 * 표시
            monthly_df_c["month_label"] = monthly_df_c["month"].map(month_labels_c)
            monthly_df_c["year_label"] = monthly_df_c["year"].astype(str)

            avg_by_month_c = monthly_df_c.groupby(["month", "month_label"])["monthly_return"].mean().reset_index()
            avg_by_month_c["year_label"] = "평균"

            heat_df_c = pd.concat([
                monthly_df_c[["year_label", "month", "month_label", "monthly_return"]],
                avg_by_month_c[["year_label", "month", "month_label", "monthly_return"]],
            ], ignore_index=True)

            year_sort_order_full_c = [str(y) for y in sorted(monthly_df_c["year"].unique())] + ["평균"]
            month_sort_order_c = [month_labels_c[m] for m in range(1, 13)]

            heat_rect_c = alt.Chart(heat_df_c).mark_rect(stroke="white", strokeWidth=1.5).encode(
                x=alt.X("month_label:N", title=None, sort=month_sort_order_c, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", title=None, sort=year_sort_order_full_c),
                color=alt.Color(
                    "monthly_return:Q",
                    scale=alt.Scale(
                        type="threshold",
                        domain=[-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5],
                        range=["#cf6265", "#e67f82", "#ecaaab", "#f6d4d5", "#fafbff",
                               "#d7e4da", "#accab2", "#82ae8b", "#599265"],
                    ),
                    legend=alt.Legend(title="수익률 (%)", orient="bottom", gradientLength=220),
                ),
                tooltip=[
                    alt.Tooltip("year_label:N", title="연도"),
                    alt.Tooltip("month_label:N", title="월"),
                    alt.Tooltip("monthly_return:Q", title="수익률", format="+.2f"),
                ],
            )
            heat_text_c = alt.Chart(heat_df_c).mark_text(fontSize=10, fontWeight="bold").encode(
                x=alt.X("month_label:N", sort=month_sort_order_c, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("year_label:N", sort=year_sort_order_full_c),
                text=alt.Text("monthly_return:Q", format="+.1f"),
                color=alt.value("#334155"),
            )
            st.altair_chart(
                (heat_rect_c + heat_text_c).properties(height=32 * len(year_sort_order_full_c) + 80),
                use_container_width=True,
            )
            render_monthly_return_table(heat_df_c, year_sort_order_full_c, month_sort_order_c, "c")
            if COST_TAX_ON:
                st.caption("* 6월 수익률에는 전년도 양도세 납부분이 포함되어 있습니다. (전년도 수익에 대한 세금을 6월 말에 한꺼번에 차감하므로 6월 수익률이 낮게 나옵니다)")

            st.markdown("##### 📉 낙폭 (Drawdown) 히스토리")
            render_drawdown_with_benchmark(chart_df_c, "전략C")

            st.markdown("##### 🚨 포트폴리오 드로우다운 Top 10")
            dd_vals_c = bt_results_c["drawdown"].values
            dd_dates_c = bt_results_c["date"].values
            n_c = len(dd_vals_c)
            episodes_c = []
            i_ep_c = 0
            while i_ep_c < n_c:
                if dd_vals_c[i_ep_c] < -0.001:
                    start_i_c = i_ep_c
                    j_ep_c = i_ep_c
                    min_val_c = dd_vals_c[i_ep_c]
                    min_idx_c = i_ep_c
                    while j_ep_c < n_c and dd_vals_c[j_ep_c] < -0.001:
                        if dd_vals_c[j_ep_c] < min_val_c:
                            min_val_c = dd_vals_c[j_ep_c]
                            min_idx_c = j_ep_c
                        j_ep_c += 1
                    episodes_c.append({
                        "시작": pd.Timestamp(dd_dates_c[start_i_c]).strftime("%Y/%m"),
                        "종료": pd.Timestamp(dd_dates_c[min_idx_c]).strftime("%Y/%m"),
                        "드로우다운": min_val_c,
                    })
                    i_ep_c = j_ep_c
                else:
                    i_ep_c += 1

            episodes_c.sort(key=lambda x: x["드로우다운"])
            top10_c = episodes_c[:10]
            for idx, ep in enumerate(top10_c):
                ep["순위"] = idx + 1
                ep["드로우다운"] = f"{ep['드로우다운']:.1f}%"
                ep["주요 이슈"] = issues_for_period(ep["시작"], ep["종료"])
            if top10_c:
                df_dd_top10_c = pd.DataFrame(top10_c)[["순위", "시작", "종료", "드로우다운", "주요 이슈"]]
                st.dataframe(df_dd_top10_c, use_container_width=True, hide_index=True)
                st.caption("※ 드로우다운은 시작월 직전 고점부터 종료월(최저점)까지의 하락률입니다. '주요 이슈'는 시작\\~종료월과 기간이 겹치는 대형 이슈이며, 겹치는 이슈가 없으면 '-'입니다.")
            else:
                st.info("드로우다운 구간이 발견되지 않았습니다.")

            st.markdown("##### 🔻 폭락 시장 포트폴리오 성과")
            STRESS_PERIODS_C = [
                ("코로나 팬데믹", "2020-01-01", "2020-03-31"),
                ("2022 긴축 발작 (금리인상기)", "2022-01-01", "2022-10-31"),
                ("2018년 4분기 조정", "2018-10-01", "2018-12-31"),
            ]
            stress_rows_c = []
            for label_c, s_str_c, e_str_c in STRESS_PERIODS_C:
                s_ts_c, e_ts_c = pd.Timestamp(s_str_c), pd.Timestamp(e_str_c)
                mask_c = (bt_results_c["date"] >= s_ts_c) & (bt_results_c["date"] <= e_ts_c)
                sub_c = bt_results_c[mask_c]
                if len(sub_c) == 0:
                    continue
                port_cum_c = (np.prod(1 + sub_c["monthly_return"].values / 100.0) - 1) * 100
                bench_sub_ret_c = qqq_ret_series_c.reindex(sub_c["date"]).fillna(0.0)
                bench_cum_c = (np.prod(1 + bench_sub_ret_c.values) - 1) * 100
                stress_rows_c.append({
                    "스트레스 기간": label_c,
                    "시작": s_ts_c.strftime("%Y/%m"),
                    "종료": e_ts_c.strftime("%Y/%m"),
                    "포트폴리오 수익률": f"{port_cum_c:+.1f}%",
                    "QQQ 수익률": f"{bench_cum_c:+.1f}%",
                })
            if stress_rows_c:
                st.dataframe(pd.DataFrame(stress_rows_c), use_container_width=True, hide_index=True)
            else:
                st.info("선택한 시작일 범위 내 해당하는 폭락장 스트레스 기간 데이터가 없습니다. 시작일을 앞당겨 보세요.")

            st.markdown("##### 📊 주요 지표 비교 (vs QQQ)")

            def _fmt_pct_c(x):
                return f"{x:.1f}%" if x is not None and not (isinstance(x, float) and np.isnan(x)) else "데이터 부족"

            port_ret_arr_c = bt_results_c["monthly_return"].values
            bench_ret_arr_c = qqq_monthly_ret_c.values
            dd_arr_c = bt_results_c["drawdown"].values
            bench_nav_arr_c = chart_df_c["qqq_nav"].values
            bench_running_max_c = np.maximum.accumulate(bench_nav_arr_c)
            bench_dd_arr_c = (bench_nav_arr_c / bench_running_max_c - 1) * 100

            period_ret_c = (final_nav_c / 100.0 - 1) * 100
            bench_final_nav_c = bench_nav_arr_c[-1]
            bench_period_ret_c = (bench_final_nav_c / 100.0 - 1) * 100
            bench_cagr_c = ((bench_final_nav_c / 100.0) ** (1 / total_years_c) - 1) * 100

            last_date2_c = bt_results_c["date"].iloc[-1]
            current_year2_c = last_date2_c.year
            ytd_mask_c = bt_results_c["date"].dt.year == current_year2_c
            port_ytd_c = (np.prod(1 + bt_results_c.loc[ytd_mask_c, "monthly_return"].values / 100.0) - 1) * 100
            bench_ytd_c = (np.prod(1 + (bench_ret_arr_c[ytd_mask_c.values] / 100.0)) - 1) * 100

            win_months_c = int((port_ret_arr_c > 0).sum())
            bench_win_months_c = int((bench_ret_arr_c > 0).sum())
            total_months_c = len(port_ret_arr_c)

            mdd_idx_c = int(np.argmin(dd_arr_c))
            mdd_date_c = bt_results_c["date"].iloc[mdd_idx_c].strftime("%Y-%m")
            bench_mdd_idx_c = int(np.argmin(bench_dd_arr_c))
            bench_mdd_date_c = bt_results_c["date"].iloc[bench_mdd_idx_c].strftime("%Y-%m")

            def _trailing_c(arr, months):
                if len(arr) < months:
                    return None, None
                window = arr[-months:]
                cum = (np.prod(1 + window / 100.0) - 1) * 100
                ann_std = np.std(window, ddof=1) * np.sqrt(12) if len(window) > 1 else None
                return cum, ann_std

            ret_1y_c, std_1y_c = _trailing_c(port_ret_arr_c, 12)
            ret_3y_c, std_3y_c = _trailing_c(port_ret_arr_c, 36)
            ret_5y_c, std_5y_c = _trailing_c(port_ret_arr_c, 60)
            bench_ret_1y_c, bench_std_1y_c = _trailing_c(bench_ret_arr_c, 12)
            bench_ret_3y_c, bench_std_3y_c = _trailing_c(bench_ret_arr_c, 36)
            bench_ret_5y_c, bench_std_5y_c = _trailing_c(bench_ret_arr_c, 60)

            mean_m_c = np.mean(port_ret_arr_c) / 100.0
            std_m_c = np.std(port_ret_arr_c, ddof=1) / 100.0 if total_months_c > 1 else np.nan
            annual_vol_c = std_m_c * np.sqrt(12) * 100 if not np.isnan(std_m_c) else np.nan
            sharpe_c = (mean_m_c * 12) / (std_m_c * np.sqrt(12)) if std_m_c and std_m_c > 0 else np.nan

            downside_c = port_ret_arr_c[port_ret_arr_c < 0] / 100.0
            downside_std_c = np.std(downside_c, ddof=1) if len(downside_c) > 1 else np.nan
            sortino_c = (mean_m_c * 12) / (downside_std_c * np.sqrt(12)) if downside_std_c and downside_std_c > 0 else np.nan

            ulcer_c = np.sqrt(np.mean(dd_arr_c ** 2))
            upi_c = cagr_c / ulcer_c if ulcer_c > 0 else np.nan

            bench_mean_m_c = np.mean(bench_ret_arr_c) / 100.0
            bench_std_m_c = np.std(bench_ret_arr_c, ddof=1) / 100.0 if total_months_c > 1 else np.nan
            bench_annual_vol_c = bench_std_m_c * np.sqrt(12) * 100 if not np.isnan(bench_std_m_c) else np.nan
            bench_sharpe_c = (bench_mean_m_c * 12) / (bench_std_m_c * np.sqrt(12)) if bench_std_m_c and bench_std_m_c > 0 else np.nan

            bench_downside_c = bench_ret_arr_c[bench_ret_arr_c < 0] / 100.0
            bench_downside_std_c = np.std(bench_downside_c, ddof=1) if len(bench_downside_c) > 1 else np.nan
            bench_sortino_c = (bench_mean_m_c * 12) / (bench_downside_std_c * np.sqrt(12)) if bench_downside_std_c and bench_downside_std_c > 0 else np.nan

            bench_ulcer_c = np.sqrt(np.mean(bench_dd_arr_c ** 2))
            bench_upi_c = bench_cagr_c / bench_ulcer_c if bench_ulcer_c > 0 else np.nan

            alloc_list_c = bt_results_c["alloc"].tolist()
            monthly_turnovers_c = []
            prev_alloc_c = {}
            for alloc_d in alloc_list_c:
                all_tk_c = set(prev_alloc_c.keys()) | set(alloc_d.keys())
                diff_c = sum(abs(alloc_d.get(t, 0.0) - prev_alloc_c.get(t, 0.0)) for t in all_tk_c)
                monthly_turnovers_c.append(diff_c / 2.0)
                prev_alloc_c = alloc_d
            avg_turnover_c = np.mean(monthly_turnovers_c) if monthly_turnovers_c else 0.0
            annual_turnover_c = avg_turnover_c * 12

            metrics_rows_c = [
                ("기간 수익률", _fmt_pct_c(period_ret_c), _fmt_pct_c(bench_period_ret_c)),
                ("연환산 수익률 (CAGR)", _fmt_pct_c(cagr_c), _fmt_pct_c(bench_cagr_c)),
                ("이번 달 수익률", _fmt_pct_c(port_ret_arr_c[-1]), _fmt_pct_c(bench_ret_arr_c[-1])),
                ("올해 수익률 (YTD)", _fmt_pct_c(port_ytd_c), _fmt_pct_c(bench_ytd_c)),
                ("월 최고 수익률", _fmt_pct_c(port_ret_arr_c.max()), _fmt_pct_c(bench_ret_arr_c.max())),
                ("월 최저 수익률", _fmt_pct_c(port_ret_arr_c.min()), _fmt_pct_c(bench_ret_arr_c.min())),
                ("수익 월 비중", f"{win_months_c} / {total_months_c}", f"{bench_win_months_c} / {total_months_c}"),
                ("연 변동성", _fmt_pct_c(annual_vol_c), _fmt_pct_c(bench_annual_vol_c)),
                ("최대 낙폭 (MDD)", _fmt_pct_c(mdd_c), _fmt_pct_c(bench_dd_arr_c.min())),
                ("MDD 시점", mdd_date_c, bench_mdd_date_c),
                ("1년 수익률", _fmt_pct_c(ret_1y_c), _fmt_pct_c(bench_ret_1y_c)),
                ("3년 수익률", _fmt_pct_c(ret_3y_c), _fmt_pct_c(bench_ret_3y_c)),
                ("5년 수익률", _fmt_pct_c(ret_5y_c), _fmt_pct_c(bench_ret_5y_c)),
                ("1년 표준편차", _fmt_pct_c(std_1y_c), _fmt_pct_c(bench_std_1y_c)),
                ("3년 표준편차", _fmt_pct_c(std_3y_c), _fmt_pct_c(bench_std_3y_c)),
                ("5년 표준편차", _fmt_pct_c(std_5y_c), _fmt_pct_c(bench_std_5y_c)),
                ("샤프 지수", f"{sharpe_c:.2f}" if not np.isnan(sharpe_c) else "데이터 부족", f"{bench_sharpe_c:.2f}" if not np.isnan(bench_sharpe_c) else "데이터 부족"),
                ("소티노 지수", f"{sortino_c:.2f}" if not np.isnan(sortino_c) else "데이터 부족", f"{bench_sortino_c:.2f}" if not np.isnan(bench_sortino_c) else "데이터 부족"),
                ("UPI 지수", f"{upi_c:.2f}" if not np.isnan(upi_c) else "데이터 부족", f"{bench_upi_c:.2f}" if not np.isnan(bench_upi_c) else "데이터 부족"),
                ("연간 턴오버", f"{annual_turnover_c:.1f}%", "0.0%"),
            ]
            df_metrics_c = pd.DataFrame(metrics_rows_c, columns=["지표", "전략C", "QQQ"])
            render_gl_table(df_metrics_c)
            st.caption(f"※ 기간: {bt_results_c['date'].iloc[0].strftime('%Y-%m')} ~ {bt_results_c['date'].iloc[-1].strftime('%Y-%m')} 야후 파이낸스 실시간 데이터 기준. 1/3/5년 지표는 해당 기간의 월 데이터가 충분할 때만 표시됩니다. 비용·세금 반영 중에는 QQQ도 같은 조건(처음 매수 시 슬리피지, 매도 시 1회 양도세 평가)의 세후 값입니다.")




            st.markdown("##### 🗓️ 월별 세부 리밸런싱 기록")
            display_bt_c = bt_results_c.copy()
            display_bt_c["연월"] = display_bt_c["date"].dt.strftime("%Y-%m")
            display_bt_c["월 수익률"] = display_bt_c["monthly_return"].apply(lambda x: f"{x:+.2f}%")
            display_bt_c["낙폭"] = display_bt_c["drawdown"].apply(lambda x: f"{x:.2f}%")
            display_bt_c["NAV"] = display_bt_c["nav"].apply(lambda x: f"{x:.1f}")

            st.dataframe(
                display_bt_c[["연월", "mode", "월 수익률", "weights_str", "NAV", "낙폭"]].iloc[::-1],
                use_container_width=True, hide_index=True
            )

    with c_mstr:
        render_macro_board()
        # 탭을 눌렀을 때만 그림 (.open: 열림 True / 닫힘 False / 상태 추적이 안 되는 예전 Streamlit은 None → 그냥 그림)
        if getattr(tab_mstr, "open", None) is not False:
            render_mstr_tab()

    with c_rank:
        render_macro_board()
        st.header("🇺🇸 실시간 미국 ETF 랭킹")
        _rank_view = st.radio(
            "보기 선택",
            ["📊 전략 자산 랭킹", "🧭 섹터·테마 현황 (레버리지·인버스 제외)", "🩺 시장위험진단", "⚠️ 시장 위험 신호판", "🧮 시장 밸류에이션"],
            horizontal=True, key="rank_view_radio", index=0
        )
        # 보기 단추 두 줄 배치: [전략 자산 랭킹 · 섹터·테마] / [시장위험진단 · 위험 신호판 · 밸류에이션]
        st.markdown("""<style>
.st-key-rank_view_radio div[role="radiogroup"]{flex-wrap:wrap;}
.st-key-rank_view_radio div[role="radiogroup"]::before{content:"";flex-basis:100%;height:0;order:2;}
.st-key-rank_view_radio div[role="radiogroup"] > *:nth-child(-n+2){order:1;}
.st-key-rank_view_radio div[role="radiogroup"] > *:nth-child(n+3){order:3;}
</style>""", unsafe_allow_html=True)
        if not _rank_view.startswith(("🩺", "⚠️", "🧮")):   # ETF 검색은 랭킹·섹터 보기에서만
            render_etf_search()
        if _rank_view.startswith("🩺"):
            render_risk_diagnosis()
        elif _rank_view.startswith("🧭"):
            render_sector_flow()
        elif _rank_view.startswith("⚠️"):
            render_risk_board()
        elif _rank_view.startswith("🧮"):
            render_valuation_board()
        else:
            st.markdown(
                "2026 전략(A·B·C)에 쓰이는 자산과 주요 지수·배당형·레버리지 ETF의 실시간 모멘텀과 "
                "수익률을 정렬한 랭킹입니다. 섹터 흐름은 위의 '🧭 섹터·테마 현황'에서 확인하세요."
            )

            sort_by = st.radio(
                "🏆 정렬 기준 선택",
                options=["종합 모멘텀 스코어", "1개월 수익률", "3개월 수익률", "6개월 수익률", "12개월 수익률"],
                horizontal=True,
                key="etf_sort_by_radio"
            )
        
            rank_data = []
            for ticker, metrics in data_dict.items():
                if ticker == "TIP":
                    continue
            
                rank_data.append({
                    "티커 (Ticker)": ticker,
                    "현재가 ($)": f"${metrics['현재가']:.2f}",
                    "종합 모멘텀 스코어": metrics["A_공격스코어"],
                    "1개월 수익률 (%)": metrics["1M"],
                    "3개월 수익률 (%)": metrics["3M"],
                    "6개월 수익률 (%)": metrics["6M"],
                    "12개월 수익률 (%)": metrics["12M"],
                })
        
            df_ranking = pd.DataFrame(rank_data)
        
            sort_column_map = {
                "종합 모멘텀 스코어": "종합 모멘텀 스코어",
                "1개월 수익률": "1개월 수익률 (%)",
                "3개월 수익률": "3개월 수익률 (%)",
                "6개월 수익률": "6개월 수익률 (%)",
                "12개월 수익률": "12개월 수익률 (%)"
            }
        
            selected_sort_col = sort_column_map[sort_by]
            df_ranking = df_ranking.sort_values(by=selected_sort_col, ascending=False).reset_index(drop=True)
            df_ranking.index += 1
        
            st.markdown(f"### 📊 Top 10 Performers ({sort_by} 기준)")
            df_top5 = df_ranking.head(10).copy()
        
            try:
                import altair as alt
                top_chart = alt.Chart(df_top5).mark_bar(cornerRadiusEnd=6).encode(
                    x=alt.X(f"{selected_sort_col}:Q", title=sort_by),
                    y=alt.Y("티커 (Ticker):N", sort='-x', title="ETF 티커"),
                    color=alt.Color("티커 (Ticker):N", scale=alt.Scale(scheme='tableau10'), legend=None),
                    tooltip=["티커 (Ticker)", "현재가 ($)", selected_sort_col]
                ).properties(height=340)
                st.altair_chart(top_chart, use_container_width=True)
            except Exception:
                st.bar_chart(df_top5.set_index("티커 (Ticker)")[selected_sort_col])
        
            st.markdown("### 🏆 실시간 모멘텀 순위표")
            _rk = df_ranking.copy()
            _rk.insert(0, "순위", _rk.index)
            render_html_table(_rk, ticker_cols=("티커 (Ticker)",))
            st.caption("※ 티커 옆 괄호는 ETF의 한글 명칭이며, 티커에 마우스를 올리면 간략 설명이 표시됩니다. 점수·수익률 단위는 %입니다.")

    with c_ndx:
        render_macro_board()
        render_stock_finder()
        st.header("🏢 실시간 미국 주식 랭킹")
        # KOSPI200은 당분간 숨김 (2026-10-15). 다시 보이게 하려면 SHOW_KOSPI200 = True — 코드·kospi200.csv는 그대로 둠
        SHOW_KOSPI200 = False
        _uni_opts = ["나스닥100", "S&P500"] + (["KOSPI200 (테스트)"] if SHOW_KOSPI200 else [])
        if st.session_state.get("stk_universe") not in _uni_opts:
            st.session_state.pop("stk_universe", None)      # 예전에 KOSPI200을 골라 둔 상태 정리
        _uni = st.radio("📌 지수 선택", _uni_opts, horizontal=True, key="stk_universe")
        _is_sp = _uni == "S&P500"
        _is_kr = _uni.startswith("KOSPI")
        if _is_kr:
            _uname, _bench, _uk, _blabel = "KOSPI200", "069500.KS", "kr", "KODEX200"
        elif _is_sp:
            _uname, _bench, _uk, _blabel = "S&P500", "SPY", "sp", "SPY"
        else:
            _uname, _bench, _uk, _blabel = "나스닥100", "QQQ", "ndx", "QQQ"
        _show_rules = not _is_kr        # 코스피200은 매매 기준(보유 기준) 없이 랭킹·상태·추세만 (한국 백테스트에서 효과 약함)
        _TOPN = 50 if _is_sp else (40 if _is_kr else 20)   # 업종 분포를 계산할 상위 종목 수
        _TABLE_N = 50                   # 순위표에 보여 줄 종목 수 (1~20위는 바로, 21위부터는 접어 둠)
        st.markdown(
            f"{_uname} 구성 종목의 모멘텀·추세·상대강도·변동성·거래대금을 함께 보여 줍니다. "
            f"시장 체력(시장 폭) → 주도 업종 → 종목 상태 순서로 읽으면 됩니다. 순위표는 상위 {_TABLE_N}개까지 표시하고, 나머지는 맨 위 '🔎 실시간 미국 주식 종목 찾기'로 볼 수 있습니다."
        )
        st.caption(
            "ℹ️ 데이터는 접속한 휴대폰·PC가 아니라 이 앱의 서버(Streamlit Cloud)에서 야후 파이낸스로부터 받아 계산합니다. "
            "그래서 접속 기기의 성능이나 데이터 요금과는 관계없고, 화면에는 계산 결과만 전송됩니다. "
            "한 번 불러오면 서버에 1시간 저장되어, 다른 기기나 다른 사람이 접속해 버튼을 눌러도 바로 표시됩니다."
        )

        _loaded_key = f"{_uk}_loaded"

        def _stk_set_loaded():
            st.session_state[_loaded_key] = True

        if not st.session_state.get(_loaded_key, False):
            if _is_sp:
                st.warning(
                    "**S&P500은 약 500종목이라 처음 불러올 때 1분 정도 걸립니다** (나스닥100은 약 10초). "
                    "서버가 500종목의 1년치 시세와 시가총액을 야후에서 받아 오는 시간입니다. 진행 상황이 단계별로 표시되니 화면을 닫지 말고 기다려 주세요. "
                    "야후가 요청이 많다고 잠시 막으면 일부 종목의 시가총액이 '-'로 나올 수 있습니다."
                )
            elif _is_kr:
                st.warning(
                    "**KOSPI200 (테스트)** — 약 200종목이라 처음 불러올 때 30초 안팎 걸립니다. 구성 종목·업종·시가총액은 PC에서 만든 "
                    "`kospi200.csv`를 쓰고, 시세는 야후 파이낸스에서 받습니다. **랭킹·상태·추세 확인용**이며, 미국 종목에 쓰는 매매 기준"
                    "(200일선 −3% 매도 · +5% 재매수)은 한국 백테스트에서 위험 대비 효율을 높이지 못해 표시하지 않습니다."
                )
            else:
                st.info(
                    "나스닥100은 종목이 약 100개라 불러오는 데 시간이 걸립니다. 앱 첫 로딩을 빠르게 하려고 "
                    "자동으로 불러오지 않으니, 필요할 때 아래 버튼을 눌러주세요. 처음 불러올 때는 10초 정도 걸리고 진행 상황이 표시됩니다."
                )
            # 랭킹 불러오기 단추: 기본 흰 단추는 눈에 덜 띄어 진한 회색으로 강조
            st.markdown("""<style>
[class*="_load_btn"] button { background-color:#6b7280 !important; border-color:#6b7280 !important; color:#ffffff !important;
  font-weight:700 !important; padding:0.5rem 1.2rem !important; }
[class*="_load_btn"] button:hover { background-color:#4b5563 !important; border-color:#4b5563 !important; }
[class*="_load_btn"] button p { color:#ffffff !important; font-weight:700 !important; }
</style>""", unsafe_allow_html=True)
            st.button(f"📥 {_uname} 랭킹 불러오기", key=f"{_uk}_load_btn", on_click=_stk_set_loaded)
        else:
            _ph_ndx = st.empty()
            _wait = "처음엔 약 1분" if _is_sp else ("처음엔 약 30초" if _is_kr else "처음엔 약 10초")
            with _ph_ndx.container():
                with st.status(f"📥 {_uname} 데이터를 불러오는 중입니다… ({_wait}, 이후 1시간은 바로 표시)",
                               expanded=True) as _stt:
                    st.caption("화면이 잠시 흐려져도 정상입니다. 계산은 서버에서 진행됩니다. 오래 멈춰 있으면 인터넷 연결이나 야후 서버 문제일 수 있으니 새로고침(F5)해 주세요.")
                    st.write("① 구성 종목 확인 중…")
                    _kr_mcap = None
                    if _is_kr:
                        _mt = os.path.getmtime(KOSPI200_CSV) if os.path.exists(KOSPI200_CSV) else 0
                        _ndx_list, _secmap, _kr_names, _kr_mcap, _kr_asof = get_kospi200_universe(mtime=_mt)
                        TICKER_EXTRA_NAMES.update(_kr_names)     # 종목명(한글)으로 표시
                        _ndx_src = f"kr:{_kr_asof}"
                    elif _is_sp:
                        _ndx_list, _secmap, _sp_names = get_sp500_universe()
                        TICKER_EXTRA_NAMES.update(_sp_names)   # 한글 설명이 없는 종목은 영문 회사명으로 표시
                        _ndx_src = "auto"
                    else:
                        _ndx_list, _ndx_src = get_ndx_tickers()
                        _secmap = None
                    if not _ndx_list:
                        _nd = pd.DataFrame()
                        _mcap = {}
                        _stt.update(label=f"⚠️ {_uname} 구성 종목 목록을 불러오지 못했습니다", state="error", expanded=False)
                    else:
                        st.write(f"② {len(_ndx_list)}종목의 1년치 일봉 시세 내려받는 중… (가장 오래 걸리는 단계)")
                        _nd = get_ndx_daily_metrics(tuple(_ndx_list), _bench)
                        if _secmap is None:
                            st.write("③ 업종 정보 확인 중…")
                            _secmap = get_ndx_sectors()
                            if not _secmap:
                                st.write("③-2 위키피디아 업종표를 못 읽어 야후 종목 정보로 업종을 확인 중…")
                                _secmap = get_ndx_sectors_yahoo(tuple(_ndx_list))
                        if _kr_mcap is not None:
                            _mcap = _kr_mcap
                        else:
                            st.write(f"④ 시가총액 확인 중… ({len(_ndx_list)}종목)")
                            _mcap = get_ndx_market_caps(tuple(_ndx_list))
                        _stt.update(label=f"✅ {_uname} 데이터 불러오기 완료", state="complete", expanded=False)
            _ph_ndx.empty()

            if _nd is None or _nd.empty:
                st.warning(f"{_uname} 종목 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요."
                           + (" KOSPI200은 PC에서 `코스피200_목록_만들기.bat`을 실행해 kospi200.csv를 만든 뒤 대시보드_업로드.bat으로 올려야 합니다." if _is_kr else ""))
            else:
                _nd = _nd.copy()
                _nd["업종"] = [_secmap.get(t, ("", ""))[0] or "-" for t in _nd["Ticker"]]
                _nd["세부업종"] = [(_secmap.get(t, ("", ""))[1] or _secmap.get(t, ("", ""))[0]) or "-" for t in _nd["Ticker"]]
                _n = len(_nd)
                _q3 = _nd.attrs.get("qqq3", np.nan)

                # ── 1) 시장 요약 + 자동 해석 ──
                _b200 = _nd["above200"].mean() * 100
                _b50 = _nd["above50"].mean() * 100
                if _b200 >= 70:
                    _bt = "**고른 강세** — 대부분 종목이 장기 상승 추세에 있습니다. 지수 상승의 체력이 튼튼한 상태입니다."
                elif _b200 >= 40:
                    _bt = "**보통** — 오르는 종목과 쉬는 종목이 섞여 있습니다. 업종별로 차별화되는 장입니다."
                else:
                    _bt = "**소수 종목 장세** — 200일선 위 종목이 절반에 못 미칩니다. 지수가 올라도 몇몇 대형주에 기댄 상승이라 체력이 약합니다."
                _tags = _nd["tag"].value_counts()
                _tag_txt = " · ".join(f"{k} {_tags.get(k, 0)}개" for k in ["🟢 주도", "🟡 추세 둔화", "🔵 200일선 아래 반등", "🔴 200일선 아래 하락"])
                st.markdown(f"### 🩺 {_uname} 시장 체력")
                st.info(
                    f"**시장 폭**: 200일선 위 **{_b200:.0f}%** (50일선 위 {_b50:.0f}%) → {_bt}  \n"
                    f"**상태 분포** ({_n}종목): {_tag_txt}  \n"
                    + ((f"**보유 기준 분포**: " + " · ".join(f"{k} {(_nd['hold'] == k).sum()}개" for k in ["🟢 보유·매수 가능", "🟢 보유 (재매수 대기)", "🟡 경계", "🔴 매도 기준"]) + "  \n") if _show_rules else "")
                    + (f"**{_blabel} 3개월 수익률**: {_q3:+.1f}% — 아래 '{_blabel} 대비 3M'은 이 값과 비교한 것입니다." if pd.notna(_q3) else "")
                )
                with st.expander("📖 읽는 법 — 각 숫자의 뜻과 해석 기준", expanded=False):
                    if _is_kr:
                        st.caption("KOSPI200에서는 아래 설명의 'QQQ'를 'KODEX200'으로, '나스닥100'을 'KOSPI200'으로, '상위 20'을 '상위 40'으로 바꿔 읽으면 됩니다. "
                                   "시가총액은 조원 단위입니다. **보유 기준(매매 기준)은 KOSPI200에서는 쓰지 않습니다** — 한국 백테스트(2006\\~)에서 "
                                   "200일선 규칙이 낙폭은 줄였지만 수익도 같은 비율로 줄여 위험 대비 효율(샤프 0.8)이 그대로였고, 지수(KODEX200) 단위로는 오히려 손해였습니다.")
                    if _is_sp:
                        st.caption("S&P500에서는 아래 설명의 'QQQ'를 'SPY'로, '나스닥100'을 'S&P500'으로, '상위 20'을 '상위 50'으로 바꿔 읽으면 됩니다. "
                                   "업종 쏠림 기준도 비율로 같아서 상위 50개 중 15개 이상이면 쏠림, 10개 이상이면 우세입니다.")
                    st.markdown(NDX_GUIDE_MD)

                # ── 2) 정렬·필터 ──
                _c1, _c2 = st.columns([1.7, 1])
                with _c1:
                    ndx_sort_by = st.radio(
                        "🏆 정렬 기준 선택",
                        options=["종합 모멘텀 스코어", "시가총액", "1개월 수익률", "3개월 수익률", "12개월 수익률", "52주 고점 대비",
                                 f"{_blabel} 대비 3개월", "안정 모멘텀", "거래대금 증가"],
                        index=1, horizontal=True, key=f"{_uk}_sort_by_radio"   # 기본: 시가총액
                    )
                with _c2:
                    ndx_tag_f = st.radio("🏷️ 상태 필터", ["전체", "🟢 주도", "🟡 추세 둔화", "🔵 200일선 아래 반등", "🔴 200일선 아래 하락"],
                                         horizontal=True, key=f"{_uk}_tag_radio")
                    ndx_hold_f = (st.radio("📌 보유 기준 필터", ["전체", "🟢 보유·매수 가능", "🟢 보유 (재매수 대기)", "🟡 경계", "🔴 매도 기준"],
                                           horizontal=True, key=f"{_uk}_hold_radio") if _show_rules else "전체")

                _mc = pd.Series([_mcap.get(t, np.nan) for t in _nd["Ticker"]], index=_nd.index)
                _mc_rank = _mc.rank(ascending=False, method="min")
                _mcol = "시가총액 (조원)" if _is_kr else "시가총액 ($B)"
                df_ndx = pd.DataFrame({
                    "티커 (Ticker)": _nd["Ticker"],
                    "상태": _nd["tag"],
                    "보유 기준": _nd["hold"],
                    "200일선 대비 (%)": _nd["ma200_gap"],
                    "세부업종": _nd["세부업종"],
                    "시총 순위": _mc_rank.map(lambda v: "-" if v != v else f"{int(v)}위"),
                    _mcol: _mc / (1e12 if _is_kr else 1e9),
                    "시총 비중 (%)": _mc / _mc.sum() * 100 if _mc.notna().any() else np.nan,
                    "종합 모멘텀 스코어": _nd["score"],
                    "1개월 (%)": _nd["1M"], "3개월 (%)": _nd["3M"], "12개월 (%)": _nd["12M"],
                    "52주 고점 대비 (%)": _nd["hi_gap"],
                    f"{_blabel} 대비 3M (%p)": _nd["rs3"],
                    "변동성 (%)": _nd["vol"],
                    "안정 모멘텀 (배수)": _nd["stable"],
                    "거래대금 배수": _nd["flow"],
                    "_업종": _nd["업종"],
                })
                if not _show_rules:
                    df_ndx = df_ndx.drop(columns=["보유 기준"])
                _df_ndx_all = df_ndx.copy()   # 종목 검색용 (상태 필터 적용 전 전체)
                if ndx_tag_f != "전체":
                    df_ndx = df_ndx[df_ndx["상태"] == ndx_tag_f]
                if ndx_hold_f != "전체":
                    df_ndx = df_ndx[df_ndx["보유 기준"] == ndx_hold_f]
                _ndx_sort_map = {
                    "종합 모멘텀 스코어": "종합 모멘텀 스코어", "시가총액": _mcol, "1개월 수익률": "1개월 (%)", "3개월 수익률": "3개월 (%)",
                    "12개월 수익률": "12개월 (%)", "52주 고점 대비": "52주 고점 대비 (%)",
                    f"{_blabel} 대비 3개월": f"{_blabel} 대비 3M (%p)", "안정 모멘텀": "안정 모멘텀 (배수)", "거래대금 증가": "거래대금 배수",
                }
                _ndx_col = _ndx_sort_map[ndx_sort_by]
                df_ndx = df_ndx.sort_values(by=_ndx_col, ascending=False, na_position="last").reset_index(drop=True)
                df_ndx.index += 1

                # ── 종목 검색: 상위 20 밖 종목도 같은 지표로 확인 (순위는 상태 필터와 무관한 전체 기준) ──
                _df_ndx_all = _df_ndx_all.sort_values(by=_ndx_col, ascending=False, na_position="last").reset_index(drop=True)
                _df_ndx_all.index += 1
                _all_tk = sorted(_df_ndx_all["티커 (Ticker)"].tolist())
                _sub_of = dict(zip(_df_ndx_all["티커 (Ticker)"], _df_ndx_all["세부업종"]))

                def _ndx_label(t):
                    _nm = TICKER_INFO.get(t, ("",))[0] or TICKER_EXTRA_NAMES.get(t, ("",))[0]
                    return f"{t} · {_nm}" if _nm else f"{t} · {_sub_of.get(t, '')}"

                # 맨 위 '🔎 실시간 미국 주식 종목 찾기'에서 순위 줄을 함께 보여 주도록 이번 랭킹 결과를 보관
                st.session_state.setdefault("stk_rank_store", {})[_uname] = (_df_ndx_all, ndx_sort_by)

                if df_ndx.empty:
                    st.warning("고른 필터(" + " · ".join(x for x in (ndx_tag_f, ndx_hold_f) if x != "전체") + ")에 해당하는 종목이 없습니다.")
                else:
                    _top20 = df_ndx.head(_TOPN)

                    # ── 3) 상위 20 업종 분포 + 해석 ──
                    st.markdown(f"### 🧩 상위 {_TOPN} 업종 분포 ({ndx_sort_by} 기준{''.join(' · ' + x for x in (ndx_tag_f, ndx_hold_f) if x != '전체')})")
                    _grp = (_top20.groupby("세부업종")
                            .agg(종목수=("티커 (Ticker)", "count"),
                                 평균_스코어=("종합 모멘텀 스코어", "mean"),
                                 종목=("티커 (Ticker)", lambda x: ", ".join(x)))
                            .sort_values(["종목수", "평균_스코어"], ascending=False).reset_index())
                    _lead = _grp.iloc[0]
                    if _lead["세부업종"] in ("-", ""):
                        st.info("업종 정보를 불러오지 못해 업종 분포를 판단할 수 없습니다. 잠시 뒤 새로고침해 주세요.")
                    elif _lead["종목수"] >= round(_TOPN * 0.3):   # 상위 N의 30% 이상이 한 업종이면 쏠림
                        st.success(f"**{_lead['세부업종']}** 쏠림 — 상위 {_TOPN}개 중 {_lead['종목수']}개가 이 업종입니다. 지금 시장을 이끄는 곳입니다.")
                    elif _lead["종목수"] >= round(_TOPN * 0.2):
                        st.info(f"**{_lead['세부업종']}** 우세 — 상위 {_TOPN}개 중 {_lead['종목수']}개. 뚜렷한 우세지만 다른 업종도 함께 강합니다.")
                    else:
                        st.info("특정 업종 쏠림 없음 — 여러 업종에 고르게 퍼져 있습니다.")
                    _grp = _grp.rename(columns={"평균_스코어": "평균 스코어", "종목수": "종목 수"})
                    render_html_table(_grp, text_cols=("세부업종", "종목"))

                    # ── 4) 차트 ──
                    st.markdown(f"### 📊 Top 10 ({ndx_sort_by} 기준)")
                    try:
                        import altair as alt
                        _ch = df_ndx.head(10).copy()
                        _ch["이름"] = [(TICKER_EXTRA_NAMES.get(t, (t,))[0] if _is_kr else f"{t} {TICKER_INFO.get(t, ('',))[0]}")
                                      for t in _ch["티커 (Ticker)"]]
                        ndx_chart = alt.Chart(_ch).mark_bar(cornerRadiusEnd=6).encode(
                            x=alt.X(f"{_ndx_col}:Q", title=ndx_sort_by),
                            y=alt.Y("이름:N", sort='-x', title=None,
                                    axis=alt.Axis(labelOverlap=False, labelLimit=200, labelFontSize=12)),
                            color=alt.condition(alt.datum[_ndx_col] >= 0, alt.value("#10b981"), alt.value("#ef4444")),
                            tooltip=["이름", "상태"] + (["보유 기준"] if _show_rules else []) + ["세부업종", alt.Tooltip(f"{_ndx_col}:Q", format=".2f")]
                        ).properties(height=330)
                        st.altair_chart(ndx_chart, use_container_width=True)
                    except Exception:
                        st.bar_chart(df_ndx.head(10).set_index("티커 (Ticker)")[_ndx_col])

                    # ── 5) 순위표 ──
                    st.markdown(f"### 🏆 실시간 순위표 (상위 {min(_TABLE_N, len(df_ndx))})")
                    _ndx_rk = df_ndx.head(_TABLE_N).drop(columns=["_업종"]).copy()
                    _ndx_rk.insert(0, "순위", _ndx_rk.index)
                    _ndx_rk = _ndx_rk.astype(object).where(_ndx_rk.notna(), "-")
                    _rk_kw = dict(ticker_cols=("티커 (Ticker)",), text_cols=("상태", "보유 기준", "세부업종", "시총 순위"))
                    if len(_ndx_rk) > 20:
                        # 상위 20개는 바로 보이고, 21위부터는 접어 둠 (휴대폰에서 표가 너무 길어지지 않게)
                        render_html_table(_ndx_rk.iloc[:20], **_rk_kw)
                        with st.expander(f"➕ 21\\~{len(_ndx_rk)}위 더 보기", expanded=False):
                            render_html_table(_ndx_rk.iloc[20:], **_rk_kw)
                    else:
                        render_html_table(_ndx_rk, **_rk_kw)
                    st.caption(
                        f"※ 기준일 {_nd['asof'].max()} · {_uname} 구성 종목 {len(_ndx_list)}개 중 데이터가 확보된 {_n}개를 비교합니다 "
                        "(상장 12개월 미만 제외). 수익률은 거래일 기준(1개월=21일, 3개월=63일, 12개월=252일)이라 월말 기준인 ETF 랭킹의 점수와 조금 다를 수 있습니다. "
                        "티커에 마우스를 올리면(폰은 터치) 회사 설명이 나옵니다. 각 숫자의 해석은 위 '📖 읽는 법'을 보세요."
                        + (" 구성 종목·업종은 하루 한 번 위키피디아 표에서 자동 갱신합니다." if _ndx_src == "auto" else
                           (f" 구성 종목·업종·시가총액은 PC에서 만든 kospi200.csv({_ndx_src[3:] or '기준일 모름'} 기준)를 씁니다. 6월·12월 정기변경 뒤 다시 만들어 올리세요." if str(_ndx_src).startswith("kr:")
                            else " 구성 종목은 내장 목록(2026-10 기준)을 사용 중입니다."))
                        + ("" if _secmap else " 업종 정보를 불러오지 못해 업종이 '-'로 표시됩니다.")
                    )

        # ── QQQ 장기 보유 가이드 (랭킹 불러오기와 상관없이 항상 표시) ──
        st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)   # 랭킹 불러오기 버튼과 간격
        st.markdown("---")
        render_qqq_longhold_guide()
        st.markdown("---")
        render_btc_longhold_guide()
        st.info("🪙 코인 계좌 없이 MSTR로 비트코인 흐름에 투자하는 규칙·오늘의 신호·장부는 위쪽 **🪙 MSTR** 탭으로 옮겼습니다.")

    with c_mdd:
        render_macro_board()
        import altair as alt
        render_print_section("mdd")
        st.header("📉 SPY·QQQ 장기 낙폭 (경각심용)")
        st.caption("내 전략은 2015년 이전 백테스트가 어려워, 닷컴버블·금융위기 같은 대형 폭락을 SPY·QQQ로 대신 확인하는 참고 화면입니다. 전략 성과와는 무관하며 일별 종가 기준입니다.")

        _LONG_MODES = {
            "ETF 30년 (배당 포함)": ("1996-01-01", [("SPY", "SPY"), ("QQQ", "QQQ")]),
            "지수 초장기 (대공황 포함 · 배당 제외)": ("1927-12-30", [("S&P500", "^GSPC"), ("나스닥100", "^NDX")]),
        }
        _mode_names = list(_LONG_MODES)
        long_mode = st.radio("데이터 범위", _mode_names, horizontal=True, key="long_mode")
        _mi = _mode_names.index(long_mode)
        _start, _series = _LONG_MODES[long_mode]
        with st.spinner("장기 가격 데이터를 불러오는 중..."):
            _hist = get_long_history(tuple(sym for _, sym in _series), _start)
        long_px = {n: _hist[sym] for n, sym in _series if sym in _hist}

        if not long_px:
            st.warning("장기 가격 데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        else:
            if _mi == 0:
                st.caption("SPY는 1993년, QQQ는 1999년 3월 상장이라 QQQ는 약 27년치입니다. 1929 대공황·1987 블랙먼데이는 ETF가 없어 '지수 초장기'에서 확인하세요.")
            else:
                st.caption("S&P500(1927~)·나스닥100(1985~) 지수의 가격 기준이라 배당이 빠져 ETF보다 낙폭이 조금 더 깊게 나옵니다. 대공황·1987년·오일쇼크를 볼 수 있습니다.")

            # ---- 요약 카드 ----
            _cards_mdd, _cards_cur = [], []
            for n, px in long_px.items():
                dd_s = px / px.cummax() - 1
                t = dd_s.idxmin()
                pk = px.loc[:t].idxmax()
                mdd = float(dd_s.min() * 100)
                _cards_mdd.append((f"{n} 최대 낙폭 (MDD)", f"{mdd:.2f}%",
                                   f"{pk:%Y-%m} → {t:%Y-%m} · 초기 투자금이면 약 {fmt_krw(COST_CAPITAL * abs(mdd) / 100)} 평가손실", "neg"))
                cur = float(dd_s.iloc[-1] * 100)
                _cards_cur.append((f"{n} 현재 낙폭", f"{cur:.2f}%",
                                   f"역대 고점 {px.idxmax():%Y-%m-%d} 대비", "neg" if cur <= -10 else "neutral"))
            hl_cards(_cards_mdd + _cards_cur)

            # ---- 낙폭 히스토리 ----
            st.markdown("##### 📉 낙폭 (Drawdown) 히스토리")
            frames = []
            for n, px in long_px.items():
                d = ((px / px.cummax() - 1) * 100).resample("W").min().dropna()
                frames.append(pd.DataFrame({"date": d.index, "series": n, "drawdown": d.values.round(2)}))
            long_df = pd.concat(frames, ignore_index=True)
            _y_all = list(range(int(long_df["date"].dt.year.min()), int(long_df["date"].dt.year.max()) + 1))
            if len(_y_all) > 2:
                _y0, _y1 = st.select_slider("🔍 표시 구간 (년)", options=_y_all, value=(_y_all[0], _y_all[-1]), key=f"long_zoom_{_mi}")
            else:
                _y0, _y1 = _y_all[0], _y_all[-1]
            view_df = long_df[(long_df["date"].dt.year >= _y0) & (long_df["date"].dt.year <= _y1)]

            _names = list(long_px)
            _palette = ["#2563eb", "#dc2626"][:len(_names)]
            x_enc = alt.X("date:T", title=None, axis=alt.Axis(format="%Y", labelOverlap=True))
            # 0% 위쪽에 흰 여백(라벨 띠)을 만들어 이슈 이름이 색 영역에 가리지 않게 함
            _ymin = float(view_df["drawdown"].min())
            _y_lo = float(np.floor(_ymin / 10.0) * 10 - 5)
            _y_hi = 34.0
            _yscale = alt.Scale(domain=[_y_lo, _y_hi], nice=False)
            _ticks = list(range(0, int(_y_lo) - 1, -20))  # 0, -20, -40 ... (양수 눈금은 표시하지 않음)
            y_enc = alt.Y("drawdown:Q", title="낙폭 (%)", stack=None, scale=_yscale, axis=alt.Axis(values=_ticks))  # 두 자산을 쌓지 않고 겹쳐서 표시
            color_enc = alt.Color("series:N", scale=alt.Scale(domain=_names, range=_palette), sort=_names,
                                  legend=alt.Legend(orient="top", title=None))
            tip = [alt.Tooltip("date:T", title="주", format="%Y-%m-%d"), alt.Tooltip("series:N", title="구분"),
                   alt.Tooltip("drawdown:Q", title="낙폭 (%)", format=".2f")]
            layers = [alt.Chart(view_df).mark_area(opacity=0.33, line={"strokeWidth": 1.2}).encode(x=x_enc, y=y_enc, color=color_enc, tooltip=tip)]

            ev_rows = []
            for short, full, a, b in LONG_EVENTS:
                for n, px in long_px.items():
                    es = event_stats(px, a, b)
                    if es:
                        ev_rows.append({"date": es["trough"], "label": short})
                        break
            ev_df = pd.DataFrame(ev_rows)
            if len(ev_df):
                ev_df = ev_df[(ev_df["date"].dt.year >= _y0) & (ev_df["date"].dt.year <= _y1)].reset_index(drop=True)
            if len(ev_df):
                _rows_y = [28.0, 20.0, 12.0]  # 이웃한 이슈가 겹치지 않게 3단으로 엇갈려 배치
                ev_df["ypos"] = [_rows_y[k % 3] for k in range(len(ev_df))]
                ev_df["y0"] = _y_lo
                _xmin, _xmax = view_df["date"].min(), view_df["date"].max()
                ev_df["right"] = ev_df["date"] >= (_xmax - (_xmax - _xmin) * 0.12)  # 오른쪽 끝 이슈는 글자를 왼쪽으로
                layers.append(alt.Chart(ev_df).mark_rule(color="#94a3b8", strokeDash=[3, 3]).encode(
                    x="date:T", y=alt.Y("y0:Q", scale=_yscale, title=None), y2="ypos:Q"))
                for _right in (False, True):
                    sub = ev_df[ev_df["right"] == _right]
                    if len(sub):
                        layers.append(alt.Chart(sub).mark_text(
                            align="right" if _right else "left", dx=-4 if _right else 4, baseline="middle",
                            fontSize=11, fontWeight="bold", color="#1e293b").encode(
                            x="date:T", y=alt.Y("ypos:Q", scale=_yscale, title=None), text="label:N"))
            st.altair_chart(alt.layer(*layers).properties(height=300), use_container_width=True)
            _rng_txt = " · ".join(f"{n} {view_df[view_df['series'] == n]['drawdown'].min():.1f}%" for n in _names if (view_df['series'] == n).any())
            st.caption(f"위쪽 흰 띠의 이름과 점선 = 주요 이슈의 저점 시기. 선택 구간 최대 낙폭: {_rng_txt} (주간 기준 표시, 계산은 일별 종가)")

            # ---- 드로우다운 Top 10 ----
            st.markdown("##### 🚨 포트폴리오 드로우다운 Top 10")
            _pick = st.radio("자산", _names, horizontal=True, key=f"long_top10_{_mi}") if len(_names) > 1 else _names[0]
            eps = sorted(dd_episodes(long_px[_pick]), key=lambda e: e["depth"])[:10]
            top_rows = []
            for i, e in enumerate(eps, 1):
                issue = next((short for short, full, a, b in LONG_EVENTS
                              if pd.Timestamp(a) <= e["trough"] <= pd.Timestamp(b)), "-")
                top_rows.append({
                    "순위": i, "고점일": f"{e['peak']:%Y-%m-%d}", "저점일": f"{e['trough']:%Y-%m-%d}",
                    "최대 낙폭": f"{e['depth']:.1f}%", "하락 기간": _fmt_dur((e["trough"] - e["peak"]).days),
                    "전고점 회복": (f"{_fmt_dur((e['recovery'] - e['trough']).days)} 후" if e["recovery"] is not None else "미회복"),
                    "주요 이슈": issue,
                })
            if top_rows:
                st.dataframe(pd.DataFrame(top_rows), use_container_width=True, hide_index=True)
                st.caption("※ 고점 → 저점 → 전고점 회복까지를 한 구간으로 봅니다. 전고점을 오래 못 넘은 기간 안의 별도 폭락(예: 닷컴 회복 중 금융위기)도 각각 독립 구간으로 집계합니다. '전고점 회복'은 저점에서 그 구간의 고점을 다시 넘기까지 걸린 시간입니다.")

            # ---- 폭락 시장 성과 ----
            st.markdown("##### 🔻 폭락 시장 성과 (대형 이슈별)")
            crash_rows = []
            for short, full, a, b in LONG_EVENTS:
                for n, px in long_px.items():
                    es = event_stats(px, a, b)
                    if not es:
                        continue
                    crash_rows.append({
                        "이슈": full, "자산": n, "고점일": f"{es['peak']:%Y-%m-%d}", "저점일": f"{es['trough']:%Y-%m-%d}",
                        "최대 낙폭": f"{es['depth']:.1f}%", "고점→저점": _fmt_dur((es["trough"] - es["peak"]).days),
                        "전고점 회복": (f"{_fmt_dur((es['recovery'] - es['trough']).days)} 후 ({es['recovery']:%Y-%m})"
                                      if es["recovery"] is not None else "미회복"),
                        "저점 후 1년": (f"{es['rebound']:+.0f}%" if es["rebound"] is not None else "-"),
                    })
            if crash_rows:
                st.dataframe(pd.DataFrame(crash_rows), use_container_width=True, hide_index=True)
                st.markdown(  # 인쇄 때는 이 각주를 빼서 마지막에 빈 쪽이 따로 생기지 않게 함 (화면에는 그대로 표시)
                    '<div class="print-hide" style="font-size:0.875rem;color:rgba(49,51,63,0.6);">'
                    "※ 낙폭은 각 이슈 기간 안의 고점→저점 기준이라, 전체 기간의 최대 낙폭(역대 고점 기준)과 다를 수 있습니다. 데이터가 없는 시기는 표시하지 않습니다.</div>",
                    unsafe_allow_html=True)
            else:
                st.info("표시할 폭락 구간 데이터가 없습니다.")

    with c_calc:
        render_macro_board()
        render_print_section("calc", with_marker=False)
        st.header("🧮 복리의 마법 & 미래 계산기")
        st.markdown(
            "자산배분 백테스트의 실제 연평균 수익률(CAGR)을 기반으로, 매월 적립식 저축 및 정기 생활비 지출이 유발하는 "
            "미래 자산의 실제 성장 경로를 정밀하게 예측합니다. **세율 적용**, **생활비 지출 설정**, 및 **물가상승률 할인**까지 연산하는 실전형 자산 시뮬레이터입니다."
        )

        _cost_on = bool(COST_SLIP_ON or COST_TAX_ON)
        _mix_opts = (
            cap_on_setting(), float(st.session_state.get("mix_cap_pct", 35.0)),
            False, -10.0,
        )
        _preset_cagr = get_preset_cagrs(PRESET_START, _cost_cfg() if _cost_on else None, _mix_opts)

        def _pv(k):
            v = _preset_cagr.get(k)
            return float(v) if v is not None else float(PRESET_FALLBACK_CAGR[k])

        if "cagr_input" not in st.session_state:
            st.session_state.cagr_input = 25.0  # 계산기 초기값 (퀵 프리셋 버튼으로 전략별 실측값 선택 가능)

        # 상단 설정이 바뀌면, 직전에 눌러 둔 프리셋 값(직접 고치지 않은 경우)을 새 값으로 갱신
        _sel = st.session_state.get("_preset_sel")
        if _sel and abs(st.session_state.cagr_input - st.session_state.get("_preset_val", -999.0)) < 0.005 \
                and abs(_pv(_sel) - st.session_state["_preset_val"]) >= 0.005:
            st.session_state.cagr_input = _pv(_sel)
            st.session_state["_preset_val"] = _pv(_sel)

        def _apply_preset(k):
            st.session_state.cagr_input = _pv(k)
            st.session_state["_preset_sel"] = k
            st.session_state["_preset_val"] = _pv(k)

        st.markdown("##### ⚡ 자산배분 전략 실측 CAGR 퀵 프리셋")
        col_pre1, col_pre2, col_pre3, col_pre4 = st.columns(4)
        col_pre1.button(f"🏆 2026 혼합 ({_pv('mix'):.2f}%)", key="preset_btn_mix", on_click=_apply_preset, args=("mix",))
        col_pre2.button(f"🛡️ 전략 A ({_pv('A'):.2f}%)", key="preset_btn_A", on_click=_apply_preset, args=("A",))
        col_pre3.button(f"⚡ 전략 B ({_pv('B'):.2f}%)", key="preset_btn_B", on_click=_apply_preset, args=("B",))
        col_pre4.button(f"🔄 전략 C ({_pv('C'):.2f}%)", key="preset_btn_C", on_click=_apply_preset, args=("C",))
        if all(_preset_cagr.get(k) is not None for k in ["mix", "A", "B", "C"]):
            _safe_bits = []
            if _mix_opts[0]:
                _safe_bits.append(f"혼합 비중상한 {_mix_opts[1]:g}%")
            _safe_txt = " · ".join(_safe_bits) if _safe_bits else "안전장치 미적용"
            st.caption(f"※ 각 전략 탭의 초기 설정(백테스트 시작일 {PRESET_START}, {_safe_txt}) 기준 실측 CAGR이며, 전략 탭의 '연환산 복리 수익률(CAGR)'과 같은 값입니다.")
            if _cost_on:
                _bits = []
                if COST_SLIP_ON:
                    _bits.append(f"슬리피지 {COST_SLIP_PCT:g}%/회")
                if COST_TAX_ON:
                    _bits.append(f"양도세 {COST_TAX_PCT:g}% (연 공제 {fmt_krw(COST_DEDUCT)})")
                st.caption(f"💸 '2026 혼합전략' 탭 상단 '백테스트 비용·세금 반영 설정'이 적용된 값입니다 · " + " · ".join(_bits) + f" · 초기 투자금 {fmt_krw(COST_CAPITAL)}")
        else:
            st.caption("※ 일부 전략의 실측 CAGR을 불러오지 못해 기존 참고값을 표시 중입니다. 잠시 후 새로고침해 주세요.")

        st.markdown("---")
        # 인쇄/PDF는 여기(입력칸)부터 시작: 위쪽 설명·프리셋 버튼은 제외
        st.markdown('<div class="print-marker" data-print-scope="calc"></div>', unsafe_allow_html=True)
        if _cost_on:
            _pbits = []
            if COST_SLIP_ON:
                _pbits.append(f"슬리피지 {COST_SLIP_PCT:g}%/회")
            if COST_TAX_ON:
                _pbits.append(f"양도세 {COST_TAX_PCT:g}% (연 공제 {fmt_krw(COST_DEDUCT)})")
            st.markdown(
                '<div class="print-only" style="font-size:0.85rem;color:#64748b;margin-bottom:6px;">💸 백테스트 비용·세금 반영 · '
                + " · ".join(_pbits) + f" · 초기 투자금 {fmt_krw(COST_CAPITAL)}</div>",
                unsafe_allow_html=True)
        if st.session_state.get("_calc_init_sync") != COST_CAPITAL:  # 상단 '초기 투자금'이 바뀌면 계산기에도 반영
            st.session_state["calc_init_input"] = f"{int(round(COST_CAPITAL / 10000)):,}"
            st.session_state["_calc_init_sync"] = COST_CAPITAL
        _TAX_DONE = "양도세 반영 완료 (0.0% · 프리셋 CAGR에 포함)"
        if st.session_state.get("_calc_tax_prev") != COST_TAX_ON:  # 양도세 반영을 켜면 이중 과세 방지로 세율 0% 선택
            st.session_state["calc_tax_sel"] = _TAX_DONE if COST_TAX_ON else "미국주식양도세 (22.0%)"
            st.session_state["_calc_tax_prev"] = COST_TAX_ON
        col_inp1, col_inp2 = st.columns(2)
        with col_inp1:
            calc_init = money_man_input("초기 투자금 (만원 ₩)", "calc_init_input", 1000,
                                        help="'2026 혼합전략' 탭 상단 '백테스트 비용·세금 반영 설정'의 초기 투자금과 연동됩니다. 여기서 직접 바꿀 수도 있습니다. 만원 단위로 입력합니다 (예: 5억원 = 50,000).")
            calc_monthly = money_man_input("매월 저축/적립금 (만원 ₩)", "calc_monthly_man", 0)
            calc_expense = money_man_input("매월 지출/생활비 (만원 ₩)", "calc_expense_man", 0, help="투자수익에서 정기 지출하는 생활비가 있다면 마이너스로 처리됩니다.")
            calc_years = st.slider("시뮬레이션 투자 기간 (년)", min_value=1, max_value=40, value=20)
        with col_inp2:
            calc_cagr = st.number_input("연 목표 수익률 CAGR (%)", min_value=0.0, max_value=100.0, key="cagr_input", step=0.1, format="%.2f")
            calc_inflation = st.number_input("연 예상 물가상승률 (%)", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
            calc_expense_start = st.number_input("지출 시작 시점 (년차)", min_value=1, max_value=max(1, calc_years), value=1, step=1, help="생활비 지출을 몇 년차부터 적용할지 연차를 지정합니다.")
            calc_tax_opt = st.selectbox("세율 설정", ["일반과세 (15.4%)", "미국주식양도세 (22.0%)", "비과세 계좌 (0.0% / ISA 및 연금저축)", "사용자 정의", _TAX_DONE], key="calc_tax_sel")
        
        if calc_tax_opt == "일반과세 (15.4%)":
            tax_rate = 15.4
        elif calc_tax_opt == "미국주식양도세 (22.0%)":
            tax_rate = 22.0
        elif calc_tax_opt in ("비과세 계좌 (0.0% / ISA 및 연금저축)", _TAX_DONE):
            tax_rate = 0.0
        else:
            tax_rate = st.number_input("세율 직접 입력 (%)", min_value=0.0, max_value=50.0, value=15.4, step=0.1)

        records = []
        curr_nominal = calc_init * 10000
        curr_contribution = calc_init * 10000
        monthly_contrib = calc_monthly * 10000
        base_expense = calc_expense * 10000
        r_monthly = (1 + calc_cagr / 100) ** (1/12) - 1 if calc_cagr > 0 else 0.0

        for y in range(1, calc_years + 1):
            current_year_monthly_expense = base_expense * ((1 + calc_inflation / 100) ** (y - 1)) if y >= calc_expense_start else 0.0
            
            for m in range(12):
                net_flow = monthly_contrib - current_year_monthly_expense
                curr_contribution += net_flow
                curr_nominal = (curr_nominal + net_flow) * (1 + r_monthly)
                
                if curr_nominal < 0:
                    curr_nominal = 0.0
            
            effective_contribution = max(0.0, curr_contribution)
            profit = curr_nominal - effective_contribution
            tax_due = profit * (tax_rate / 100) if profit > 0 else 0.0
            curr_after_tax = curr_nominal - tax_due
            
            real_value = curr_after_tax / ((1 + calc_inflation / 100) ** y)
            
            records.append({
                "년차": f"{y}년차",
                "누적 납입원금": round(curr_contribution),
                "세전 일반복리": round(curr_nominal),
                "세후 수령예정액": round(curr_after_tax),
                "세후 실질가치 (물가반영)": round(real_value)
            })

        df_calc = pd.DataFrame(records)

        def format_krw(val):
            sign = "-" if val < 0 else ""
            val = abs(val)
            if val == 0:
                return "0원"
            if val >= 100000000:
                eok = int(val // 100000000)
                man = int((val % 100000000) // 10000)
                if man > 0:
                    return f"{sign}{eok}억 {man:,}만원"
                return f"{sign}{eok}억원"
            else:
                man = int(val // 10000)
                return f"{sign}{man:,}만원"

        last_rec = records[-1]
        st.markdown("### 🏆 시뮬레이션 최종 기대 성과 요약")
        sum_col1, sum_col2, sum_col3 = st.columns(3)
        sum_col1.metric("총 순 원금(저축-지출)", format_krw(last_rec["누적 납입원금"]))
        sum_col2.metric("세후 최종 자산", format_krw(last_rec["세후 수령예정액"]))
        sum_col3.metric("실질구매력 가치", format_krw(last_rec["세후 실질가치 (물가반영)"]))

        st.markdown("### 📈 미래 자산 성장 시뮬레이션")
        df_melt = df_calc.melt(id_vars="년차", value_vars=["누적 납입원금", "세전 일반복리", "세후 수령예정액", "세후 실질가치 (물가반영)"], var_name="구분", value_name="자산액")
        
        try:
            import altair as alt
            line_chart = alt.Chart(df_melt).mark_line(point=True, size=2.5).encode(
                x=alt.X("년차:N", sort=None, title="년차"),
                y=alt.Y("자산액:Q", title="평가액 (₩)"),
                color=alt.Color("구분:N", scale=alt.Scale(range=["#94a3b8", "#ef4444", "#10b981", "#3b82f6"])),
                tooltip=[alt.Tooltip("년차"), alt.Tooltip("구분"), alt.Tooltip("자산액", format=",.0f")]
            ).properties(height=350)
            st.altair_chart(line_chart, use_container_width=True)
        except Exception:
            st.line_chart(df_calc.set_index("년차"))

        st.markdown('<div class="print-pagebreak"></div>', unsafe_allow_html=True)
        st.markdown("### 📊 연도별 세부 자산 성장 상세표")
        df_display = df_calc.copy()
        for col in ["누적 납입원금", "세전 일반복리", "세후 수령예정액", "세후 실질가치 (물가반영)"]:
            df_display[col] = df_display[col].apply(format_krw)
        
        _hdr = "".join(f"<th>{c}</th>" for c in df_display.columns)
        _body = ""
        _last = len(df_display) - 1
        for _ri, (_, _row) in enumerate(df_display.iterrows()):
            _cls = ' class="last"' if _ri == _last else ""
            _body += f"<tr{_cls}>" + "".join(f"<td>{v}</td>" for v in _row.values) + "</tr>"
        st.markdown(
            "<style>"
            ".growth-tbl{width:100%;border-collapse:collapse;font-size:0.9rem;margin-bottom:0.5rem}"
            ".growth-tbl th{background:#e2e8f0;color:#334155;padding:8px 6px;text-align:center;border:1px solid #cbd5e1;word-break:keep-all}"
            ".growth-tbl td{padding:7px 6px;text-align:right;border:1px solid #e2e8f0;white-space:nowrap}"
            ".growth-tbl td:first-child{text-align:center}"
            ".growth-tbl tr:nth-child(even) td{background:#f8fafc}"
            ".growth-tbl tr.last td{background:#e8f1fa;font-weight:700}"
            "@media (max-width:640px){.growth-tbl{font-size:0.62rem}.growth-tbl th{font-size:0.6rem}.growth-tbl th,.growth-tbl td{padding:5px 2px}}"
            "</style>"
            f'<table class="growth-tbl"><thead><tr>{_hdr}</tr></thead><tbody>{_body}</tbody></table>',
            unsafe_allow_html=True,
        )

        if _v_src != "off":
            st.markdown(
                '<div class="print-hide"><hr style="border:0;border-top:1px solid #e2e8f0;margin:1rem 0 .6rem 0;"/>'
                f'<div style="font-size:0.85rem;color:#64748b;">👥 오늘 {_v_today:,}명 · 누적 {_v_total:,}명 방문 (내 접속 제외)'
                + (" · 🔑 지금은 내 접속이라 세지 않음" if _v_src == "me" else "") + "</div></div>",
                unsafe_allow_html=True)
