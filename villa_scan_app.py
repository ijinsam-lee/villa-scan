"""
빌라 경매 시세조사 앱 (1단계)
- 동네 프로필: 법정동별로 실제 팔린 빌라의 가격·평수·연식·층 분포
- 비교사례: 반경 / 전용평수 / 연식 조건으로 유사 거래 찾기 + 지도
- 예상 매도가: 대표 평단가 × 전용평수, 이상치(업계약 의심) 경고, 간단 입찰가 역산

필요한 키 (.streamlit/secrets.toml 또는 사이드바 입력)
  DATA_GO_KR_KEY = "공공데이터포털 일반 인증키(Decoding)"
  KAKAO_REST_KEY = "카카오 디벨로퍼스 REST API 키"

공공데이터포털에서 '국토교통부_연립다세대 매매 실거래가 자료' 활용신청 필요
실행: pip install streamlit pandas requests  →  streamlit run villa_scan_app.py
"""

import json
import math
import os
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
import requests
import streamlit as st

PYEONG = 3.3058
RT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade2/getRTMSDataSvcRHTrade2"
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/address.json"
GEO_CACHE_FILE = "geocode_cache.json"
LIGHT_MAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

# 신규(영문 태그)·구버전(한글 태그) 응답을 모두 같은 컬럼으로 맞춤
TAG_MAP = {
    "umdNm": "dong", "법정동": "dong",
    "jibun": "jibun", "지번": "jibun",
    "mhouseNm": "name", "연립다세대": "name",
    "buildYear": "build_year", "건축년도": "build_year",
    "excluUseAr": "area_m2", "전용면적": "area_m2",
    "landAr": "land_m2", "대지권면적": "land_m2",
    "dealYear": "year", "년": "year",
    "dealMonth": "month", "월": "month",
    "dealDay": "day", "일": "day",
    "dealAmount": "price", "거래금액": "price",
    "floor": "floor", "층": "floor",
    "cdealType": "cancel", "해제여부": "cancel",
    "dealingGbn": "deal_type", "거래유형": "deal_type",
}


# ───────────────────────── 데이터 수집 ─────────────────────────

def parse_rt_xml(text: str) -> list[dict]:
    root = ET.fromstring(text)
    code = root.findtext(".//resultCode")
    if code not in (None, "00", "000"):
        raise RuntimeError(f"실거래 API 오류: {code} {root.findtext('.//resultMsg')}")
    rows = []
    for item in root.iter("item"):
        row = {}
        for child in item:
            key = TAG_MAP.get(child.tag.strip())
            if key:
                row[key] = (child.text or "").strip()
        rows.append(row)
    return rows


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_month(service_key: str, lawd_cd: str, ymd: str) -> list[dict]:
    rows, page = [], 1
    while True:
        r = requests.get(RT_URL, params={
            "serviceKey": service_key, "LAWD_CD": lawd_cd, "DEAL_YMD": ymd,
            "pageNo": page, "numOfRows": 1000,
        }, timeout=20)
        if r.status_code == 403:
            raise PermissionError("403")
        r.raise_for_status()
        chunk = parse_rt_xml(r.text)
        rows += chunk
        if len(chunk) < 1000:
            return rows
        page += 1


def recent_months(n: int) -> list[str]:
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def clean_trades(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ["cancel", "jibun", "name", "dong", "floor", "build_year"]:
        if c not in df:
            df[c] = ""
    df = df[df["cancel"].fillna("").str.strip() == ""].copy()  # 해제된 거래 제외
    df["price"] = pd.to_numeric(df["price"].str.replace(",", ""), errors="coerce")  # 만원
    for c in ["area_m2", "land_m2", "build_year", "floor", "year", "month", "day"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["price", "area_m2"])
    df["area_py"] = df["area_m2"] / PYEONG
    df["ppy"] = df["price"] / df["area_py"]                       # 평단가(만원)
    df["age"] = date.today().year - df["build_year"]
    df["deal_date"] = pd.to_datetime(
        dict(year=df["year"], month=df["month"], day=df["day"]), errors="coerce")
    df["jibun"] = df["jibun"].fillna("")
    return df.reset_index(drop=True)


# ───────────────────────── 지오코딩 ─────────────────────────

def load_geo_cache() -> dict:
    if os.path.exists(GEO_CACHE_FILE):
        with open(GEO_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_geo_cache(cache: dict):
    with open(GEO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def kakao_lookup(kakao_key: str, query: str, strict: bool = False):
    """주소 → [위도, 경도, 법정동코드10자리] 또는 None.
    strict=True면 카카오 쪽 오류 원인을 그대로 예외로 올림"""
    try:
        r = requests.get(KAKAO_URL, params={"query": query},
                         headers={"Authorization": f"KakaoAK {kakao_key.strip()}"}, timeout=10)
        body = r.json()
    except Exception as e:
        if strict:
            raise RuntimeError(f"카카오 API 연결 실패: {e}")
        return None
    if r.status_code != 200:
        if strict:
            raise RuntimeError(f"카카오 API 오류 {r.status_code}: {body.get('message', body)}")
        return None
    docs = body.get("documents", [])
    if not docs:
        return None
    d = docs[0]
    b_code = (d.get("address") or {}).get("b_code", "")
    return [float(d["y"]), float(d["x"]), b_code]


def geocode_many(kakao_key: str, queries: list[str]) -> dict:
    cache = load_geo_cache()
    todo = [q for q in set(queries) if q not in cache]
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for q, res in zip(todo, ex.map(lambda q: kakao_lookup(kakao_key, q), todo)):
                cache[q] = res
        save_geo_cache(cache)
    return cache


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ───────────────────────── 분석 ─────────────────────────

PRICE_BINS = [0, 5000, 10000, 15000, 20000, 30000, 1e9]
PRICE_LABELS = ["5천 미만", "5천~1억", "1억~1.5억", "1.5억~2억", "2억~3억", "3억 이상"]
AREA_BINS = [0, 10, 15, 20, 25, 1e9]
AREA_LABELS = ["10평 미만", "10~15평", "15~20평", "20~25평", "25평 이상"]
AGE_BINS = [-1, 5, 12, 20, 30, 1e9]
AGE_LABELS = ["5년 이하", "6~12년", "13~20년", "21~30년", "30년 초과"]
FLOOR_BINS = [-10, 0, 1, 2, 3, 4, 100]
FLOOR_LABELS = ["지하", "1층", "2층", "3층", "4층", "5층 이상"]


def profile(df: pd.DataFrame) -> dict[str, pd.Series]:
    def dist(col, bins, labels):
        return (pd.cut(df[col], bins=bins, labels=labels)
                  .value_counts().reindex(labels, fill_value=0))
    return {
        "매매금액": dist("price", PRICE_BINS, PRICE_LABELS),
        "전용평수": dist("area_py", AREA_BINS, AREA_LABELS),
        "건물 연식": dist("age", AGE_BINS, AGE_LABELS),
        "층": dist("floor", FLOOR_BINS, FLOOR_LABELS),
    }


def bin_of(value, bins, labels):
    if value is None or pd.isna(value):
        return None
    return pd.cut([value], bins=bins, labels=labels)[0]


def fit_score(dist: pd.Series, label) -> tuple[float, int]:
    """대상 구간의 거래 비중(%)과 순위(1=가장 많이 팔림)"""
    if label is None or dist.sum() == 0:
        return 0.0, 0
    share = dist[label] / dist.sum() * 100
    rank = int(dist.rank(ascending=False, method="min")[label])
    return share, rank


def price_estimate(comps: pd.DataFrame) -> dict:
    s = comps["ppy"].dropna()
    if len(s) == 0:
        return {}
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inliers = s[(s >= lo) & (s <= hi)]
    med = inliers.median()
    spread = s.max() / s.min() if s.min() > 0 else float("inf")
    return {
        "n": len(s), "n_out": len(s) - len(inliers),
        "median": med, "p25": inliers.quantile(0.25), "p75": inliers.quantile(0.75),
        "min": s.min(), "max": s.max(), "spread": spread,
        "lo": lo, "hi": hi,
    }


def won(manwon: float) -> str:
    if manwon is None or pd.isna(manwon):
        return "-"
    eok, man = divmod(int(round(manwon)), 10000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


# ───────────────────────── 화면 ─────────────────────────

def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:  # secrets.toml이 없을 때
        return ""


st.set_page_config(page_title="빌라 시세조사", page_icon="🏘️", layout="wide")
st.title("빌라 시세조사")
st.caption("이 동네에서 실제로 팔리는 빌라인지, 얼마에 팔 수 있는지 확인합니다.")

with st.sidebar:
    st.subheader("API 키")
    data_key = st.text_input("공공데이터포털 인증키", type="password",
                             value=secret("DATA_GO_KR_KEY"))
    kakao_key = st.text_input("카카오 REST API 키", type="password",
                              value=secret("KAKAO_REST_KEY"))

    st.subheader("경매 물건")
    addr = st.text_input("주소 (지번 주소 권장)", placeholder="경기도 부천시 오정구 고강동 123-4")
    c1, c2 = st.columns(2)
    area_m2 = c1.number_input("전용면적 ㎡", 10.0, 200.0, 42.0, 0.1)
    build_year = c2.number_input("건축년도", 1960, date.today().year, 1990)
    c3, c4 = st.columns(2)
    floor = c3.number_input("층", -2, 30, 2)
    min_bid = c4.number_input("최저가 (만원)", 0, 200000, 6664, 10)

    st.subheader("조회 조건")
    months = st.slider("기간 (개월)", 6, 24, 12)
    radius = st.select_slider("반경", [300, 500, 700, 1000], value=300, format_func=lambda v: f"{v}m")
    area_tol = st.slider("전용평수 허용 범위 (±평)", 1, 6, 3)
    age_tol = st.slider("연식 허용 범위 (±년)", 2, 15, 5)
    run = st.button("시세 조회", type="primary", use_container_width=True)

if run:
    missing = [n for n, v in [("공공데이터포털 인증키", data_key),
                              ("카카오 REST API 키", kakao_key),
                              ("물건 주소", addr.strip())] if not v]
    if missing:
        st.error(f"{', '.join(missing)}를 입력하세요. 주소 칸의 회색 글씨는 예시라 직접 입력해야 합니다.")
        st.stop()
    try:
        target = kakao_lookup(kakao_key, addr.strip(), strict=True)
    except RuntimeError as e:
        msg = str(e)
        if "OPEN_MAP_AND_LOCAL" in msg or "disabled" in msg:
            st.error("카카오 앱에서 '카카오맵' 사용 설정이 꺼져 있습니다. 카카오 디벨로퍼스 → 내 애플리케이션 → "
                     "제품 설정 → 카카오맵에서 사용 설정을 ON으로 바꾼 뒤 다시 시도하세요.")
        elif "401" in msg:
            st.error("카카오 키가 맞지 않습니다. JavaScript 키가 아니라 'REST API 키'를 넣었는지 확인하세요.")
        else:
            st.error(msg)
        st.stop()
    if not target or not target[2]:
        st.error(f"'{addr}' 주소를 찾지 못했습니다. 호수·건물명은 빼고 '시/도 시군구 동 번지'까지만 입력하세요.")
        st.stop()
    lat0, lon0, b_code = target
    lawd_cd = b_code[:5]

    with st.spinner(f"최근 {months}개월 실거래를 불러오는 중"):
        rows = []
        for ymd in recent_months(months):
            try:
                rows += fetch_month(data_key, lawd_cd, ymd)
            except PermissionError:
                st.error("공공데이터포털이 접근을 거부했습니다(403). 마이페이지 → 데이터활용 → 활용신청 현황에서 "
                         "'국토교통부_연립다세대 매매 실거래가 자료'가 승인 상태인지 확인하세요. "
                         "승인 직후라면 키가 반영되기까지 1~2시간 걸릴 수 있습니다.")
                st.stop()
            except Exception as e:
                st.warning(f"{ymd} 조회 실패: {str(e).split(' for url')[0]}")
        trades = clean_trades(rows)
    if trades.empty:
        st.error("이 지역의 빌라 실거래가 없습니다. 기간을 늘려 보세요.")
        st.stop()

    st.session_state.update(trades=trades, lat0=lat0, lon0=lon0, addr=addr,
                            sgg=" ".join(addr.split()[:-2]))

if "trades" not in st.session_state:
    st.info("왼쪽에 경매 물건 정보를 입력하고 시세 조회를 누르세요.")
    st.stop()

trades = st.session_state.trades
lat0, lon0 = st.session_state.lat0, st.session_state.lon0
area_py = area_m2 / PYEONG
age = date.today().year - build_year

dongs = sorted(trades["dong"].dropna().unique())
guess = next((d for d in dongs if d in st.session_state.addr), dongs[0])
dong = st.selectbox("동네", dongs, index=dongs.index(guess))
dong_df = trades[trades["dong"] == dong]
print_slot = st.container()
report = {"fit": [], "verdict": "", "comps": None, "est": None}

tab1, tab2, tab3 = st.tabs(["동네 프로필", "비교사례", "예상 매도가"])

# ── 동네 프로필
with tab1:
    st.write(f"**{dong}** 최근 {months}개월 빌라 매매 **{len(dong_df)}건**")
    prof = profile(dong_df)
    targets = {
        "매매금액": bin_of(min_bid, PRICE_BINS, PRICE_LABELS),
        "전용평수": bin_of(area_py, AREA_BINS, AREA_LABELS),
        "건물 연식": bin_of(age, AGE_BINS, AGE_LABELS),
        "층": bin_of(floor, FLOOR_BINS, FLOOR_LABELS),
    }
    cols = st.columns(4)
    hits = 0
    for col, (name, dist) in zip(cols, prof.items()):
        share, rank = fit_score(dist, targets[name])
        hits += rank in (1, 2)
        with col:
            st.markdown(f"**{name}**")
            st.bar_chart(dist, height=220)
            if targets[name] is not None:
                st.caption(f"이 물건: {targets[name]} · 거래 비중 {share:.0f}% · {rank}위")
                report["fit"].append((name, str(targets[name]), share, rank,
                                      str(dist.idxmax()) if dist.sum() else "-"))
    st.caption("매매금액은 최저가 기준 구간입니다.")
    verdict = {4: "네 항목 모두 이 동네에서 잘 팔리는 구간입니다.",
               3: "대부분 잘 팔리는 구간입니다. 벗어난 항목을 임장에서 확인하세요.",
               2: "절반만 맞습니다. 누구에게 팔지 다시 따져 보세요."}
    msg = verdict.get(hits, "이 동네 매수자들이 잘 사지 않는 유형입니다. 손품 단계에서 거르는 것을 권합니다.")
    (st.success if hits >= 3 else st.warning)(msg)
    report["verdict"] = msg
    report["n_dong"] = len(dong_df)

# ── 비교사례
with tab2:
    cand = trades[
        (trades["area_py"].between(area_py - area_tol, area_py + area_tol)) &
        (trades["age"].between(age - age_tol, age + age_tol)) &
        (trades["jibun"] != "")
    ].copy()
    sgg = st.session_state.sgg
    cand["q"] = sgg + " " + cand["dong"] + " " + cand["jibun"]
    with st.spinner(f"{cand['q'].nunique()}개 주소 위치 확인 중"):
        geo = geocode_many(kakao_key, cand["q"].tolist())
    cand["lat"] = cand["q"].map(lambda q: (geo.get(q) or [None])[0])
    cand["lon"] = cand["q"].map(lambda q: (geo.get(q) or [None, None])[1])
    cand = cand.dropna(subset=["lat", "lon"])
    cand["dist_m"] = [haversine_m(lat0, lon0, a, b) for a, b in zip(cand["lat"], cand["lon"])]
    comps = cand[cand["dist_m"] <= radius].sort_values("dist_m")
    st.session_state.comps = comps

    st.write(f"반경 {radius}m · 전용 {area_py:.1f}±{area_tol}평 · 연식 {age}±{age_tol}년 → **{len(comps)}건**")
    if comps.empty:
        st.warning("조건에 맞는 거래가 없습니다. 반경이나 허용 범위를 넓혀 보세요.")
    else:
        map_slot = st.container()

        comps = comps.reset_index(drop=True)
        show = comps.assign(
            거래일=comps["deal_date"].dt.strftime("%y.%m.%d"),
            거리=comps["dist_m"].round().astype(int).astype(str) + "m",
            전용평=comps["area_py"].round(1),
            금액=comps["price"].map(won),
            평단가=comps["ppy"].round().astype(int),
        )[["거래일", "name", "jibun", "거리", "전용평", "build_year", "floor", "금액", "평단가"]]
        report["comps"] = show
        st.caption("표에서 행을 선택하면 지도에 노란색으로 표시됩니다.")
        event = st.dataframe(
            show.rename(columns={"name": "건물명", "jibun": "지번", "build_year": "건축년도", "floor": "층"}),
            hide_index=True, use_container_width=True,
            on_select="rerun", selection_mode="single-row", key="comp_table")
        sel_rows = event.selection.rows if event else []
        sel_q = comps.loc[sel_rows[0], "q"] if sel_rows else None

        # 같은 지번의 여러 거래를 한 점으로 묶고, 마우스를 올리면 내역이 보이게 함
        def summarize(g):
            g = g.sort_values("deal_date", ascending=False)
            name, jibun = str(g["name"].iloc[0]), str(g["jibun"].iloc[0])
            title = name if jibun in name else f"{name} ({jibun})"
            lines = "\n".join(
                f"{d:%y.%m.%d} · {f:.0f}층 · {won(p)} (평당 {pp:,.0f}만)"
                for d, f, p, pp in zip(g["deal_date"], g["floor"], g["price"], g["ppy"]))
            return pd.Series({
                "lat": g["lat"].iloc[0], "lon": g["lon"].iloc[0],
                "label": f"{title} · {g['dist_m'].iloc[0]:.0f}m\n"
                         f"{g['build_year'].iloc[0]:.0f}년식 · 전용 {g['area_py'].iloc[0]:.1f}평\n"
                         f"{lines}",
                "n": len(g),
            })
        grouped = pd.DataFrame([summarize(g).rename(None) for _, g in comps.groupby("q")])
        grouped["q"] = [q for q, _ in comps.groupby("q")]
        grouped["color"] = [[250, 176, 5, 230] if q == sel_q else [28, 126, 214, 200] for q in grouped["q"]]
        grouped["radius"] = [float(18 if q == sel_q else 8 + 3 * min(n, 4))
                             for q, n in zip(grouped["q"], grouped["n"])]
        grouped["lat"] = grouped["lat"].astype(float)
        grouped["lon"] = grouped["lon"].astype(float)
        target_df = pd.DataFrame({"lat": [lat0], "lon": [lon0],
                                  "label": [f"경매 물건\n{st.session_state.addr}"]})

        import pydeck as pdk
        deck = pdk.Deck(
            layers=[
                pdk.Layer("ScatterplotLayer", grouped, get_position="[lon, lat]",
                          get_fill_color="color", get_radius="radius",
                          radius_min_pixels=5, radius_max_pixels=20, pickable=True),
                # 경매 물건은 속이 빈 빨간 원 → 같은 자리의 거래 점이 가려지지 않음
                pdk.Layer("ScatterplotLayer", target_df, get_position="[lon, lat]",
                          filled=False, stroked=True, get_line_color=[224, 49, 49],
                          line_width_min_pixels=4, get_radius=25,
                          radius_min_pixels=12, radius_max_pixels=26, pickable=True),
            ],
            initial_view_state=pdk.ViewState(
                latitude=lat0 if sel_q is None else grouped.loc[grouped["q"] == sel_q, "lat"].iloc[0],
                longitude=lon0 if sel_q is None else grouped.loc[grouped["q"] == sel_q, "lon"].iloc[0],
                zoom=16),
            tooltip={"text": "{label}"},
            map_style=LIGHT_MAP,  # 컴퓨터가 다크 모드여도 항상 밝은 지도
        )
        with map_slot:
            st.pydeck_chart(deck, use_container_width=True)
            st.caption("빨간 테두리가 경매 물건, 파란 점이 최근 거래입니다. 점에 마우스를 올리면 건물명과 거래 내역이 보이고, "
                       "점이 클수록 같은 건물에서 거래가 많았다는 뜻입니다.")

# ── 예상 매도가
with tab3:
    comps = st.session_state.get("comps", pd.DataFrame())
    est = price_estimate(comps) if not comps.empty else {}
    if not est:
        st.info("비교사례가 있어야 예상 매도가를 계산할 수 있습니다.")
    else:
        if est["spread"] >= 2.0 or est["n_out"] > 0:
            st.warning(
                f"평단가가 {won(est['min'])}~{won(est['max'])}으로 {est['spread']:.1f}배 차이 납니다. "
                f"이상치 {est['n_out']}건은 업계약(컨설팅 작업) 가능성이 있어 계산에서 뺐습니다.")
        ppy = st.number_input("적용 평단가 (만원)", value=int(round(est["median"])), step=10,
                              help="이상치를 뺀 중앙값이 기본값입니다. 현장 비교 후 조정하세요.")
        sell = ppy * area_py
        a, b, c = st.columns(3)
        a.metric("예상 매도가", won(sell))
        b.metric("평단가 범위 (중간 50%)", f"{est['p25']:,.0f}~{est['p75']:,.0f}만")
        c.metric("비교 거래", f"{est['n']}건")
        st.bar_chart(comps["ppy"].round(-1).value_counts().sort_index(), height=200)

        st.markdown("**입찰가 역산**")
        x1, x2, x3 = st.columns(3)
        repair = x1.number_input("수리비 (만원)", 0, 10000, 500, 50)
        extra = x2.number_input("부대비용 (취득세·명도·중개 등, 만원)", 0, 10000, 400, 50)
        profit = x3.number_input("희망 차익 (세전, 만원)", 0, 20000, 2500, 100)
        bid = sell - repair - extra - profit
        st.metric("최대 입찰가", won(bid), delta=f"최저가 대비 {won(bid - min_bid)}" if bid >= min_bid
                  else f"최저가보다 {won(min_bid - bid)} 낮음", delta_color="normal" if bid >= min_bid else "inverse")
        report["est"] = dict(est=est, ppy=ppy, sell=sell, repair=repair, extra=extra,
                             profit=profit, bid=bid)
        st.caption("희망 차익은 매도가 − 낙찰가 기준입니다. 강의 기준으로 세후 1천만 원은 차익 약 2,500만 원이 필요합니다.")


# ───────────────────────── 인쇄용 보고서 ─────────────────────────

def build_report_html() -> str:
    from html import escape as e
    today = date.today().strftime("%Y.%m.%d")
    parts = [f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>빌라 시세조사 - {e(st.session_state.addr)}</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; color: #222; font-size: 12px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }} h2 {{ font-size: 15px; margin: 18px 0 6px; border-bottom: 2px solid #333; padding-bottom: 3px; }}
  .muted {{ color: #666; }} .box {{ background: #f4f6f8; padding: 8px 10px; border-radius: 4px; margin: 6px 0; }}
  .warn {{ background: #fff4e5; }}
  table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #bbb; padding: 4px 6px; text-align: left; }}
  th {{ background: #eceff3; }} td.num {{ text-align: right; }} tr {{ page-break-inside: avoid; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .grid div {{ border: 1px solid #ccc; padding: 6px; border-radius: 4px; }} .grid b {{ display: block; font-size: 15px; }}
</style></head><body>
<h1>빌라 시세조사</h1>
<div class="muted">{today} 출력 · 최근 {months}개월 국토부 실거래가 기준</div>
<h2>물건 정보</h2>
<table><tr><th>주소</th><td colspan="3">{e(st.session_state.addr)}</td></tr>
<tr><th>전용면적</th><td>{area_m2:.2f}㎡ ({area_py:.1f}평)</td><th>건축년도</th><td>{build_year}년 ({age}년차)</td></tr>
<tr><th>층</th><td>{floor}층</td><th>최저가</th><td>{won(min_bid)}</td></tr></table>
<h2>동네 프로필 · {e(dong)} ({report.get('n_dong', 0)}건)</h2>
<table><tr><th>항목</th><th>이 물건 구간</th><th>거래 비중</th><th>순위</th><th>가장 많이 팔린 구간</th></tr>"""]
    for name, label, share, rank, top in report["fit"]:
        parts.append(f"<tr><td>{e(name)}</td><td>{e(label)}</td><td class='num'>{share:.0f}%</td>"
                     f"<td class='num'>{rank}위</td><td>{e(top)}</td></tr>")
    parts.append(f"</table><div class='box'>{e(report['verdict'])}</div>")

    r = report.get("est")
    if r:
        est = r["est"]
        parts.append(f"""<h2>예상 매도가 · 입찰가</h2>
<div class="grid"><div>예상 매도가<b>{won(r['sell'])}</b></div><div>적용 평단가<b>{r['ppy']:,.0f}만</b></div>
<div>평단가 범위(중간 50%)<b>{est['p25']:,.0f}~{est['p75']:,.0f}만</b></div><div>최대 입찰가<b>{won(r['bid'])}</b></div></div>
<div class="box">예상 매도가 {won(r['sell'])} − 수리비 {won(r['repair'])} − 부대비용 {won(r['extra'])} − 희망 차익 {won(r['profit'])}
= 최대 입찰가 {won(r['bid'])} (최저가 {won(min_bid)} 대비 {'+' if r['bid'] >= min_bid else '−'}{won(abs(r['bid'] - min_bid))})</div>""")
        if est["spread"] >= 2.0 or est["n_out"] > 0:
            parts.append(f"<div class='box warn'>평단가 편차 {est['spread']:.1f}배, 이상치 {est['n_out']}건 제외 "
                         f"(업계약 가능성 확인 필요)</div>")

    show = report.get("comps")
    if show is not None and len(show):
        parts.append(f"<h2>비교사례 {len(show)}건 · 반경 {radius}m · 전용 ±{area_tol}평 · 연식 ±{age_tol}년</h2><table><tr>")
        headers = ["거래일", "건물명", "지번", "거리", "전용평", "건축년도", "층", "금액", "평단가(만)"]
        parts.append("".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for row in show.itertuples(index=False):
            v = list(row)
            parts.append(
                f"<tr><td>{e(str(v[0]))}</td><td>{e(str(v[1]))}</td><td>{e(str(v[2]))}</td><td class='num'>{v[3]}</td>"
                f"<td class='num'>{v[4]:.1f}</td><td class='num'>{v[5]:.0f}</td><td class='num'>{v[6]:.0f}</td>"
                f"<td class='num'>{e(str(v[7]))}</td><td class='num'>{v[8]:,}</td></tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    return "".join(parts)


report_html = build_report_html()
with print_slot:
    p1, p2, _ = st.columns([1, 1, 3])
    with p1:
        import streamlit.components.v1 as components
        components.html(f"""
<button id="pbtn" style="width:100%;height:38px;border:1px solid #d0d4da;border-radius:8px;background:#fff;
  font-size:14px;cursor:pointer;font-family:sans-serif">🖨️ 인쇄</button>
<script>
const html = {json.dumps(report_html)};
document.getElementById('pbtn').onclick = () => {{
  const w = window.open('', '_blank');
  if (!w) {{ alert('팝업이 차단되었습니다. 브라우저 주소창 오른쪽에서 팝업을 허용하거나, 옆의 보고서 저장 버튼을 쓰세요.'); return; }}
  w.document.open(); w.document.write(html); w.document.close();
  let done = false;
  const go = () => {{ if (done) return; done = true; w.focus(); w.print(); }};
  w.onload = go;
  setTimeout(go, 600);
}};
</script>""", height=44)
    with p2:
        st.download_button("보고서 저장 (HTML)", report_html.encode("utf-8"),
                           file_name=f"빌라시세_{dong}_{date.today():%Y%m%d}.html",
                           mime="text/html", use_container_width=True)
