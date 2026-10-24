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

import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import altair as alt
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

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
    "deposit": "deposit", "보증금액": "deposit",
    "monthlyRent": "rent", "월세금액": "rent",
    "contractType": "ctype", "계약구분": "ctype",
    "contractTerm": "term", "계약기간": "term",
}


# ───────────────────────── 데이터 수집 ─────────────────────────

def parse_rt_xml(text: str) -> list[dict]:
    root = ET.fromstring(text)
    auth = root.findtext(".//returnAuthMsg")
    if auth:
        raise RuntimeError(auth)
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
def fetch_month(service_key: str, lawd_cd: str, ymd: str, url: str = RT_URL) -> list[dict]:
    rows, page = [], 1
    while True:
        r = requests.get(url, params={
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
    ad = d.get("address") or {}
    b_code = ad.get("b_code", "")
    jb = ad.get("main_address_no", "")
    if ad.get("sub_address_no") not in (None, "", "0"):
        jb += f"-{ad['sub_address_no']}"
    if ad.get("mountain_yn") == "Y":
        jb = "산" + jb
    return [float(d["y"]), float(d["x"]), b_code, jb]


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
PRICE_LABELS = ["5천 미만", "5천–1억", "1억–1.5억", "1.5억–2억", "2억–3억", "3억 이상"]
AREA_BINS = [0, 10, 15, 20, 25, 1e9]
AREA_LABELS = ["10평 미만", "10–15평", "15–20평", "20–25평", "25평 이상"]
AGE_BINS = [-1, 5, 12, 20, 30, 1e9]
AGE_LABELS = ["5년 이하", "6–12년", "13–20년", "21–30년", "30년 초과"]
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


# ───────────────────────── 동·호수 추정 (건축물대장 전유부) ─────────────────────────

BLD_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"


@st.cache_resource
def expos_store() -> dict:
    """건물별 호실 목록 캐시 (서버가 켜져 있는 동안 유지)"""
    return {}


def bld_items(service_key: str, op: str, b_code: str, jibun: str):
    """건축물대장 API 공통 호출 → item(dict) 목록, 실패하면 오류 문자열"""
    jb = jibun.replace("산", "").strip()
    bun, _, ji = jb.partition("-")
    if not bun.isdigit() or (ji and not ji.isdigit()) or len(b_code) != 10:
        return []
    out, page = [], 1
    while page <= 10:
        try:
            r = requests.get(f"https://apis.data.go.kr/1613000/BldRgstHubService/{op}", params={
                "serviceKey": service_key, "sigunguCd": b_code[:5], "bjdongCd": b_code[5:],
                "platGbCd": "1" if jibun.strip().startswith("산") else "0",
                "bun": bun.zfill(4), "ji": (ji or "0").zfill(4),
                "numOfRows": 500, "pageNo": page}, timeout=20)
            root = ET.fromstring(r.text)
        except Exception as e:
            return f"연결 실패: {e}"
        err = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg")
        code = root.findtext(".//resultCode")
        if err or (code not in (None, "00", "000")):
            return err or f"{code} {root.findtext('.//resultMsg')}"
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
        out += items
        if len(items) < 500:
            break
        page += 1
    return out


def fetch_units(service_key: str, b_code: str, jibun: str):
    """지번 → [(동, 호, 층, 전용면적, 용도)] 목록. 실패하면 오류 문자열"""
    items = bld_items(service_key, "getBrExposPubuseAreaInfo", b_code, jibun)
    if isinstance(items, str):
        return items
    units, purpose = {}, {}
    for g in items:
        if g.get("exposPubuseGbCd") not in ("1", "") and "전유" not in g.get("exposPubuseGbCdNm", ""):
            continue
        try:
            flr = int(float(g.get("flrNo") or 0))
            area = float(g.get("area") or 0)
        except ValueError:
            continue
        if "지하" in g.get("flrGbCdNm", ""):
            flr = -flr
        key = (g.get("dongNm", ""), g.get("hoNm", ""), flr)
        units[key] = units.get(key, 0.0) + area      # 한 호실의 전유면적 합산
        main_p, etc_p = g.get("mainPurpsCdNm", ""), g.get("etcPurps", "")
        purpose.setdefault(key, f"{main_p}({etc_p})" if main_p and etc_p and etc_p != main_p
                           else main_p or etc_p)
    return [(d, h, f, a, purpose[(d, h, f)]) for (d, h, f), a in units.items()]


def ho_name(d: str, h: str) -> str:
    h = h if h.endswith("호") else f"{h}호"
    d = (d or "").strip()
    # 동 이름 칸에 '3층'처럼 층이 잘못 적힌 건물이 있어 걸러냄
    if not d or d in ("주동", "0") or d.endswith("층"):
        return h
    return f"{d} {h}"


def guess_ho(units, floor, area_m2) -> str:
    """같은 층 + 전용면적이 맞는 호실 후보"""
    if not isinstance(units, list) or not units or pd.isna(floor):
        return ""
    for tol in (0.05, 0.5):
        hits = [(u[0], u[1]) for u in units if u[2] == int(floor) and abs(u[3] - area_m2) <= tol]
        if hits:
            break
    if not hits:
        return ""
    names = sorted({ho_name(d, h) for d, h in hits})
    return names[0] if len(names) == 1 else " / ".join(names[:3]) + (" 등" if len(names) > 3 else "") + "?"


# ───────────────────────── 전월세 · 입지 ─────────────────────────

RENT_URLS = [  # 포털 버전에 따라 주소 끝에 2가 붙기도 해서 차례로 시도
    "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent2/getRTMSDataSvcRHRent2",
]


def find_rent_url(service_key: str, lawd_cd: str, ymd: str):
    """작동하는 전월세 API 주소를 찾음 → (주소, 오류문구)"""
    last = ""
    for url in RENT_URLS:
        try:
            fetch_month(service_key, lawd_cd, ymd, url)
            return url, ""
        except PermissionError:
            last = "403 접근 거부(활용신청 필요)"
        except Exception as e:
            last = str(e).split(" for url")[0]
    return None, last


def clean_rents(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ["jibun", "name", "dong", "ctype", "rent", "deposit", "floor", "build_year"]:
        if c not in df:
            df[c] = ""
    df["deposit"] = pd.to_numeric(df["deposit"].astype(str).str.replace(",", ""), errors="coerce")
    df["rent"] = pd.to_numeric(df["rent"].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    for c in ["area_m2", "build_year", "floor", "year", "month", "day"]:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df = df.dropna(subset=["deposit", "area_m2"])
    df["area_py"] = df["area_m2"] / PYEONG
    df["age"] = date.today().year - df["build_year"]
    df["deal_date"] = pd.to_datetime(dict(year=df["year"], month=df["month"], day=df["day"]), errors="coerce")
    df["jibun"] = df["jibun"].fillna("").astype(str).str.strip()
    df["ctype"] = df["ctype"].fillna("").astype(str).str.strip()
    df["kind"] = ["전세" if r == 0 else "월세" for r in df["rent"]]
    df["dep_ppy"] = df["deposit"] / df["area_py"]
    return df.reset_index(drop=True)


# 입지: 카카오 장소 검색 (카테고리 코드 또는 키워드)
PLACES = [
    ("초등학교", dict(query="초등학교", category_group_code="SC4"), "3–4인 가구"),
    ("중학교", dict(query="중학교", category_group_code="SC4"), "3–4인 가구"),
    ("어린이집·유치원", dict(category_group_code="PS3"), "신혼·영유아 가구"),
    ("지하철역", dict(category_group_code="SW8"), "1–2인 직장인"),
    ("버스정류장", dict(query="버스정류장"), "전 가구"),
    ("대형마트", dict(category_group_code="MT1"), "3–4인 가구"),
    ("편의점", dict(category_group_code="CS2"), "1–2인 가구"),
    ("병원", dict(category_group_code="HP8"), "노인 가구"),
    ("약국", dict(category_group_code="PM9"), "노인 가구"),
    ("공원", dict(query="공원"), "영유아·노인 가구"),
]


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def nearest_place(kakao_key: str, lat: float, lon: float, params_json: str, radius: int = 2000):
    params = json.loads(params_json)
    url = ("https://dapi.kakao.com/v2/local/search/keyword.json" if "query" in params
           else "https://dapi.kakao.com/v2/local/search/category.json")
    try:
        r = requests.get(url, params={**params, "x": lon, "y": lat, "radius": radius,
                                      "sort": "distance", "size": 5},
                         headers={"Authorization": f"KakaoAK {kakao_key.strip()}"}, timeout=10)
        docs = r.json().get("documents", [])
    except Exception:
        return None
    q = params.get("query", "")
    for d in docs:   # 키워드 검색은 '초등학교 앞 문구점' 같은 결과가 섞여 이름으로 한 번 더 거름
        name = d.get("place_name", "")
        if q in ("초등학교", "중학교") and not name.endswith(q):
            continue
        return dict(name=name, lat=float(d["y"]), lon=float(d["x"]), dist=int(d.get("distance") or 0))
    return None


# ───────────────────────── 임장 계획: 날씨 · 맛집 ─────────────────────────

WMO = {0: ("☀️", "맑음"), 1: ("🌤", "대체로 맑음"), 2: ("⛅", "구름 조금"), 3: ("☁️", "흐림"),
       45: ("🌫", "안개"), 48: ("🌫", "안개"), 51: ("🌦", "약한 이슬비"), 53: ("🌦", "이슬비"), 55: ("🌧", "강한 이슬비"),
       56: ("🌧", "어는 이슬비"), 57: ("🌧", "어는 이슬비"), 61: ("🌧", "약한 비"), 63: ("🌧", "비"), 65: ("🌧", "강한 비"),
       66: ("🌧", "어는 비"), 67: ("🌧", "어는 비"), 71: ("🌨", "약한 눈"), 73: ("🌨", "눈"), 75: ("❄️", "강한 눈"),
       77: ("🌨", "싸락눈"), 80: ("🌦", "소나기"), 81: ("🌧", "소나기"), 82: ("⛈", "강한 소나기"),
       85: ("🌨", "눈 소나기"), 86: ("❄️", "강한 눈 소나기"), 95: ("⛈", "뇌우"), 96: ("⛈", "뇌우·우박"), 99: ("⛈", "뇌우·우박")}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_weather(lat: float, lon: float):
    """Open-Meteo 7일 예보 (키 필요 없음)"""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "timezone": "Asia/Seoul", "forecast_days": 7,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,precipitation_sum,wind_speed_10m_max"}, timeout=10)
        d = r.json()["daily"]
    except Exception as e:
        return str(e)
    out = []
    for i, day in enumerate(d["time"]):
        code = int(d["weather_code"][i] or 0)
        icon, desc = WMO.get(code, ("🌡", "-"))
        pop = d["precipitation_probability_max"][i]
        rain = d["precipitation_sum"][i] or 0
        wind = (d["wind_speed_10m_max"][i] or 0) / 3.6          # km/h → m/s
        tmax, tmin = d["temperature_2m_max"][i], d["temperature_2m_min"][i]
        good = (pop is None or pop < 30) and rain < 1 and code < 51 and wind < 9 and -5 <= (tmax or 0) <= 32
        out.append(dict(date=day, icon=icon, desc=desc, tmax=tmax, tmin=tmin, pop=pop, rain=rain,
                        wind=wind, good=good))
    return out


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def nearby_food(kakao_key: str, lat: float, lon: float, kind: str, radius: int = 1000) -> list[dict]:
    """카카오맵 '맛집'('카페') 검색에 잡힌 곳만 (가까운 아무 가게는 넣지 않음)"""
    code = "FD6" if kind == "음식점" else "CE7"
    head = {"Authorization": f"KakaoAK {kakao_key.strip()}"}
    found, seen = [], set()
    calls = [("https://dapi.kakao.com/v2/local/search/keyword.json",
              {"query": "맛집" if kind == "음식점" else "카페 맛집", "category_group_code": code,
               "sort": "accuracy"})]
    for url, p in calls:
        try:
            docs = requests.get(url, params={**p, "x": lon, "y": lat, "radius": radius, "size": 15},
                                headers=head, timeout=10).json().get("documents", [])
        except Exception:
            continue
        for d in docs:
            if d.get("id") in seen:
                continue
            seen.add(d.get("id"))
            cat = (d.get("category_name") or "").split(">")
            found.append(dict(name=d.get("place_name", ""), cat=cat[-1].strip() if cat else "",
                              dist=int(d.get("distance") or 0), phone=d.get("phone", ""),
                              lat=float(d.get("y") or 0), lon=float(d.get("x") or 0),
                              url=d.get("place_url", ""), pick=url.endswith("keyword.json")))
    return found[:20]


# ───────────────────────── 임장 동선 ─────────────────────────

WALK_FACTOR = 1.3      # 직선거리 → 실제 걸음거리 보정
WALK_M_PER_MIN = 67    # 시속 4km
STAY_MIN = 10          # 건물당 확인 시간(분)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def nearest_stations(kakao_key: str, lat: float, lon: float, radius: int = 2000) -> list[dict]:
    """카카오 장소 검색(지하철역 SW8)으로 가까운 역 목록"""
    try:
        r = requests.get("https://dapi.kakao.com/v2/local/search/category.json",
                         params={"category_group_code": "SW8", "x": lon, "y": lat,
                                 "radius": radius, "sort": "distance", "size": 5},
                         headers={"Authorization": f"KakaoAK {kakao_key.strip()}"}, timeout=10)
        docs = r.json().get("documents", [])
    except Exception:
        return []
    return [dict(name=d["place_name"], lat=float(d["y"]), lon=float(d["x"]),
                 dist=int(d.get("distance") or 0)) for d in docs]


def walk_m(a: dict, b: dict) -> float:
    return haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) * WALK_FACTOR


def plan_route(start: dict, stops: list[dict], back: bool) -> list[dict]:
    """출발역에서 모든 건물을 가장 짧게 도는 순서 (8곳 이하는 전수 탐색)"""
    from itertools import permutations

    def total(order):
        pts = [start] + [stops[i] for i in order] + ([start] if back else [])
        return sum(walk_m(p, q) for p, q in zip(pts, pts[1:]))

    idx = list(range(len(stops)))
    if len(stops) <= 8:
        best = min(permutations(idx), key=total)
    else:  # 가까운 곳부터 → 2-opt 개선
        best, cur, left = [], start, set(idx)
        while left:
            nxt = min(left, key=lambda i: walk_m(cur, stops[i]))
            best.append(nxt); left.remove(nxt); cur = stops[nxt]
        improved = True
        while improved:
            improved = False
            for i in range(len(best) - 1):
                for j in range(i + 1, len(best)):
                    cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                    if total(cand) < total(best) - 1:
                        best, improved = cand, True
    return [stops[i] for i in best]


def link_html(url: str, text: str) -> str:
    """새 탭으로 열리는 링크 (스트림릿 사이트 보안상 같은 창 이동은 막혀 있음)"""
    from html import escape
    return (f"<a href='{escape(url, quote=True)}' target='_blank' rel='noopener'>{escape(text)}</a>"
            if url else "")


def html_table(rows: list[dict], links: dict | None = None) -> str:
    """링크를 넣을 수 있는 간단한 표. links = {열이름: (url 키, 표시 글자)}"""
    from html import escape
    links = links or {}
    if not rows:
        return ""
    cols = [c for c in rows[0] if not c.startswith("_")]
    head = "".join(f"<th>{escape(c)}</th>" for c in cols)
    body = ""
    for r in rows:
        cells = []
        for c in cols:
            if c in links:
                cells.append(f"<td>{link_html(r.get(links[c][0]) or '', links[c][1])}</td>")
            else:
                cells.append(f"<td>{escape(str(r.get(c, '')))}</td>")
        body += "<tr>" + "".join(cells) + "</tr>"
    return ("<div style='overflow-x:auto'><table style='border-collapse:collapse;width:100%;font-size:14px'>"
            "<style>.vt th,.vt td{border-bottom:1px solid #e3e6ea;padding:6px 8px;text-align:left;white-space:nowrap}"
            ".vt th{background:#f3f6fa}.vt a{font-weight:600}</style>"
            f"<thead class='vt'><tr>{head}</tr></thead><tbody class='vt'>{body}</tbody></table></div>")


def kakao_map_link(name: str, lat: float, lon: float) -> str:
    from urllib.parse import quote
    name = "".join(ch for ch in str(name) if ch not in ",/")
    return f"https://map.kakao.com/link/map/{quote(name)},{lat:.6f},{lon:.6f}"


def kakao_roadview_link(lat: float, lon: float) -> str:
    return f"https://map.kakao.com/link/roadview/{lat:.6f},{lon:.6f}"


def kakao_route_link(a: dict, b: dict) -> str:
    from urllib.parse import quote
    def pt(p):
        name = "".join(ch for ch in p["name"] if ch not in ",/")
        return f"{quote(name)},{p['lat']:.6f},{p['lon']:.6f}"
    return f"https://map.kakao.com/link/from/{pt(a)}/to/{pt(b)}"


# ───────────────────────── 임장 체크리스트 ─────────────────────────

CHECKLIST = [
    ("집에서 손품 (출발 전)", [
        ("p1", "매각물건명세서: 대항력 있는 임차인, 인수되는 권리, 비고란(위반건축물·유치권 신고) 확인"),
        ("p2", "등기부 갑구·을구에서 말소기준권리와 그보다 앞선 권리 확인"),
        ("p3", "건물 정보 탭: 근생 호실·주차·엘리베이터 확인, 정부24 건축물대장으로 위반건축물 표시 확인"),
        ("p4", "예상 매도가를 집에서 먼저 정하기 (부동산에 \"얼마에 팔려요?\"부터 묻지 않기)"),
        ("p5", "로드뷰로 골목 경사, 계단, 주차 공간, 주변 건물 상태 미리 보기"),
        ("p6", "비교사례 중 임장할 곳을 체크해 동선 짜기 (비교 평가 2–3곳)"),
    ]),
    ("건물 외부", [
        ("o1", "외벽 균열, 하얀 백화 자국(누수 흔적), 보수 공사 흔적"),
        ("o2", "옥상 방수 상태, 옥탑·불법 증축 여부 (최상층이면 특히)"),
        ("o3", "실제 주차 가능 대수와 진입로 폭 (대장상 대수와 비교)"),
        ("o4", "공용 계단·복도 청결, 조명, 쓰레기 관리 → 관리 수준"),
        ("o5", "1층 상가·필로티 여부, 소음·냄새 나는 업종"),
    ]),
    ("호실 (가능한 범위에서)", [
        ("u1", "우편함: 점유자 이름, 체납 고지서, 우편물 쌓임 → 점유 상태 추정"),
        ("u2", "전기·가스·수도 계량기가 도는지 → 공실 여부"),
        ("u3", "현관문 상태, 전단지 쌓임"),
        ("u4", "창호(샷시) 상태, 결로·곰팡이 흔적 (지하·북향이면 특히)"),
        ("u5", "보일러 연통으로 보일러 연식 추정"),
        ("u6", "윗집·아랫집에 누수 이력 물어보기"),
    ]),
    ("동네와 수요 (누구에게 팔까)", [
        ("n1", "평형이 이 동네 매수층(가구원 수)과 맞는지"),
        ("n2", "초등학교, 마트, 버스·지하철까지 실제로 걸어 보기"),
        ("n3", "같은 골목 비교 매물 2–3곳과 외관·층·주차 비교"),
        ("n4", "주변 신축 공급(경쟁 매물)과 재개발·모아타운 등 이슈"),
    ]),
    ("부동산 방문 (선택)", [
        ("r1", "내 예상가를 먼저 정하고 \"이 가격이면 얼마나 걸려요?\"로 확인"),
        ("r2", "급매 가격, 대기 매물 수, 전세 시세(전세가율)"),
        ("r3", "사장님이 직접 입찰한다고 하면 한 번 의심하기 (단독 입찰일 수도 있음)"),
    ]),
    ("입찰 전 마지막 확인", [
        ("b1", "최대 입찰가 = 예상 매도가 − (수리비 + 부대비용 + 희망 수익) 재계산"),
        ("b2", "대출 가능 여부 확인 (근생·위반건축물은 대출이 어려움)"),
        ("b3", "입찰보증금 준비 (보통 최저가의 10%, 재매각은 20%)"),
        ("b4", "명도 계획: 점유자 유형(소유자·임차인·공실)별 예상 비용과 기간"),
    ]),
]

KEY_NOTES = """
- **싸다고 사지 말고, 팔리는 물건을 싸게 산다.** 시세보다 싸다는 사실만으로는 팔리지 않습니다.
- **잘 팔리는 빌라는 동네마다 다르다.** 동네 프로필 탭에서 가격대·평수·연식·층을 먼저 확인합니다.
- **손품이 임장보다 중요하다.** 잘 팔릴 가능성이 높은 물건만 골라 임장 가고, 현장에서는 확인만 합니다.
- **경매 낙찰자 매물이 많은 동네는 조심한다.** 낙찰자끼리 급매 경쟁을 하게 되고, 이건 내가 바꿀 수 없는 변수입니다.
- **매물 소화 기간은 바꿀 수 있다.** 더 싸게 받고 수리를 잘하면 내 물건 순서를 앞당길 수 있습니다.
- **평단가 편차가 크면 업계약을 의심한다.** 예상 매도가 탭의 경고를 보고 이상치는 빼고 판단합니다.
- **세후 수익은 역산한다.** 매매사업자 6–15% 구간 기준 대략 차익 2,500만 → 세후 1천만, 4,000만 → 2천만, 5,000만 → 3천만 정도입니다(강의 기준 어림값, 실제 세율로 다시 계산).
- **처음엔 작게 한 사이클을 완주한다.** 낙찰 → 명도 → 수리 → 매도까지 세후 1천만 원 목표로 경험을 쌓습니다.
"""


# ───────────────────────── 계산기 (중개보수·취득세·대출·경매 수익) ─────────────────────────

# 공인중개사법 시행규칙 별표1 (주택) — (구간 상한 원, 상한요율, 한도액 원)
FEE_SALE = [(5e7, 0.006, 250_000), (2e8, 0.005, 800_000), (9e8, 0.004, None),
            (12e8, 0.005, None), (15e8, 0.006, None), (float("inf"), 0.007, None)]
FEE_LEASE = [(5e7, 0.005, 200_000), (1e8, 0.004, 300_000), (6e8, 0.003, None),
             (12e8, 0.004, None), (15e8, 0.005, None), (float("inf"), 0.006, None)]


def brokerage_fee(amount: float, table) -> tuple[float, float, float | None]:
    """거래금액(원) → (상한 중개보수, 상한요율, 한도액)"""
    for upper, rate, cap in table:
        if amount < upper:
            fee = amount * rate
            return (min(fee, cap) if cap else fee), rate, cap
    return 0.0, 0.0, None


def monthly_rent_base(deposit: float, rent: float) -> float:
    """월세 거래금액 환산: 보증금 + 월세×100, 5천만 원 미만이면 월세×70"""
    base = deposit + rent * 100
    return base if base >= 5e7 else deposit + rent * 70


def acq_tax(price: float, houses_after: int, adjusted: bool, over85: bool,
            corp: bool = False, low_value: bool = False) -> dict:
    """주택 유상취득 취득세 (지방세법 §11·§13의2 기준 어림)"""
    def basic():
        if price <= 6e8:
            return 1.0
        if price <= 9e8:
            return round(price / 1e8 * 2 / 3 - 3, 2)
        return 3.0
    if low_value:                      # 시가표준액 1억 원 이하 → 중과 제외
        rate, why = basic(), "시가표준액 1억 원 이하 주택이라 중과 제외, 일반세율"
    elif corp:
        rate, why = 12.0, "법인 취득 중과"
    elif houses_after <= 1 or (houses_after == 2 and not adjusted):
        rate, why = basic(), "일반세율(1–3%)"
    elif adjusted:
        rate, why = (8.0, "조정대상지역 2주택 중과") if houses_after == 2 else (12.0, "조정대상지역 3주택 이상 중과")
    else:
        rate, why = (8.0, "비조정지역 3주택 중과") if houses_after == 3 else (12.0, "비조정지역 4주택 이상 중과")
    heavy = rate >= 8
    edu = 0.4 if heavy else rate / 10
    agri = (0.6 if rate == 8 else 1.0 if rate == 12 else 0.2) if over85 else 0.0
    tax, e, a = price * rate / 100, price * edu / 100, price * agri / 100
    return dict(rate=rate, edu=edu, agri=agri, tax=tax, edu_tax=e, agri_tax=a,
                total=tax + e + a, total_rate=rate + edu + agri, why=why)


# 종합소득세 기본세율 (2023년 귀속부터) — (과세표준 상한 원, 세율, 누진공제 원)
INCOME_TAX = [(14e6, 0.06, 0), (50e6, 0.15, 1_260_000), (88e6, 0.24, 5_760_000),
              (150e6, 0.35, 15_440_000), (300e6, 0.38, 19_940_000), (500e6, 0.40, 25_940_000),
              (1e9, 0.42, 35_940_000), (float("inf"), 0.45, 65_940_000)]


def progressive_tax(base: float) -> float:
    if base <= 0:
        return 0.0
    for upper, rate, ded in INCOME_TAX:
        if base <= upper:
            return base * rate - ded
    return 0.0


def loan_schedule(principal: float, annual_rate: float, months: int, method: str) -> dict:
    r = annual_rate / 100 / 12
    if months <= 0 or principal <= 0:
        return dict(first=0, total_interest=0)
    if method == "만기일시":
        return dict(first=principal * r, total_interest=principal * r * months)
    if method == "원금균등":
        interest = sum((principal - principal / months * i) * r for i in range(months))
        return dict(first=principal / months + principal * r, total_interest=interest)
    pay = principal / months if r == 0 else principal * r / (1 - (1 + r) ** -months)
    return dict(first=pay, total_interest=pay * months - principal)


def auction_profit(bid_w, sell_w, extra_w, loan_w, irate, months, houses, adj, over85, low, taxmode) -> dict:
    """낙찰가 하나에 대한 세전·세후 수익 (모두 원 단위)"""
    t = acq_tax(bid_w, houses, adj, over85, False, low)
    sale_fee = brokerage_fee(sell_w, FEE_SALE)[0] * 1.1          # 부가세 포함
    interest = loan_w * irate / 100 / 12 * months
    costs = t["total"] + extra_w + sale_fee + interest
    gap = sell_w - bid_w
    pre = gap - costs
    if taxmode.startswith("매매사업자"):
        tax = progressive_tax(pre) * 1.1                          # 지방소득세 10% 포함
        note = "다른 소득이 없다고 보고 종합소득세 기본세율(6–45%)과 지방소득세를 적용"
    else:
        base = max(pre + interest - 2.5e6, 0)                     # 양도세는 대출이자를 필요경비로 인정 안 함
        if months < 12:
            tax, note = base * 0.70 * 1.1, "1년 미만 보유 주택 70% + 지방세"
        elif months < 24:
            tax, note = base * 0.60 * 1.1, "2년 미만 보유 주택 60% + 지방세"
        else:
            tax, note = progressive_tax(base) * 1.1, "2년 이상 보유, 기본세율 + 지방세"
    after = pre - tax
    cash = bid_w + t["total"] + extra_w - loan_w
    return dict(t=t, sale_fee=sale_fee, interest=interest, gap=gap, pre=pre, tax=tax, note=note,
                after=after, cash=cash)


# ───────────────────────── 읽는 법 (도움말) ─────────────────────────

GUIDE_ALL = """
**이 앱이 하는 일**
빌라 경매에서 가장 어려운 시세 조사를 돕습니다. 핵심 질문은 두 가지입니다.
**① 누구에게 팔 수 있을까? ② 얼마에 팔 수 있을까?**
싸게 사는 것보다 **이 동네에서 실제로 팔리는 빌라를 싸게 사는 것**이 중요하다는 원칙에 맞춰 만들었습니다.

**추천 순서**
1. **왼쪽 메뉴**에 경매 물건의 지번 주소, 전용면적, 건축년도, 층, 최저가(호수는 선택)를 넣고 **시세 조회**를 누릅니다.
2. **동네 프로필**: 이 동네에서 잘 팔리는 빌라 유형에 이 물건이 맞는지 봅니다. 안 맞으면 여기서 거릅니다.
3. **비교사례**: 주변 비슷한 빌라의 실제 거래가를 보고, 임장할 곳을 체크해 동선을 짭니다.
4. **예상 매도가**: 팔 수 있는 가격을 정하고, 최대 입찰가를 역산합니다.
5. **전월세**: 안 팔릴 때 전세로 버틸 수 있는지, 투자금이 얼마나 묶이는지 봅니다.
6. **건물·입지**: 근생·주차·엘리베이터와 주변 학교·역·병원으로 매수층을 확인합니다.
7. **임장 체크**: 현장에서 확인할 것을 체크하고, **인쇄**로 뽑아 들고 갑니다.
8. **계산기**: 세후 수익과 입찰가별 수익표로 입찰가를 최종 결정합니다.

**데이터 출처**
- 매매·전월세: 국토교통부 실거래가 (계약 후 30일 안에 신고되어 최근 1–2달은 덜 잡힘)
- 동·호수, 건물 정보: 건축물대장 (호수는 층·면적으로 맞춘 추정)
- 위치, 주변 시설, 지하철역: 카카오 지도

**알아둘 점**
- 데이터는 **방향을 잡는 도구**이고, 확인은 현장에서 합니다. 앱 결과만 믿고 입찰하지 마세요.
- 위반건축물, 권리관계(등기부·매각물건명세서)는 앱에 나오지 않으니 직접 확인합니다.
- 입력과 체크는 새로고침해도 유지됩니다. 새 물건을 볼 때는 **처음부터 다시(리셋)**를 누르세요.
"""

GUIDES = {
"동네 프로필": """
**왜 보나요?** 잘 팔리는 빌라는 **동네마다 다릅니다.** 어떤 동네는 2억대 20평대 준신축이, 어떤 동네는 1억 미만 10평대 30년 넘은 저층이 잘 팔립니다. 실제 매수자들이 돈을 주고 산 빌라의 특징을 먼저 봅니다.

**읽는 법**
- 그래프 4개(매매금액·전용평수·연식·층)는 이 동네에서 최근 팔린 빌라의 분포입니다. **막대가 높을수록 잘 팔리는 구간**입니다.
- **빨간 막대**가 이 물건이 속한 구간입니다. 아래 '거래 비중'과 '순위'를 봅니다. 1–2위면 잘 팔리는 구간입니다.
- 매매금액은 **최저가 기준**이라 실제 매도가와 구간이 다를 수 있습니다.
- 4개 중 3개 이상 맞으면 임장 후보, 2개 이하면 손품 단계에서 거르는 것을 권합니다.

**동네 시장 온도**
- 막대는 월별 거래 건수, 빨간 선은 평단가입니다. 최근 3개월을 직전 3개월과 비교합니다.
- 거래가 줄고 가격이 내려가면(❄️) 예상 매도가를 보수적으로, 거래가 늘면(🌤·🔥) 매도가 수월합니다.
- 이번 달과 지난달은 신고가 덜 들어와 건수가 낮게 보일 수 있습니다.

**평수로 매수층 짐작하기**: 10–15평은 1–2인(노인 부부·신혼), 15–20평은 2–3인, 20–25평은 3–4인 가구가 주로 삽니다.
""",
"비교사례": """
**왜 보나요?** 예상 매도가는 부동산 사장님께 묻는 게 아니라 **집에서 정하고 가는 것**입니다. 그 근거가 주변의 비슷한 빌라 실거래입니다.

**읽는 법**
- 왼쪽 메뉴의 **반경·전용평수 범위·연식 범위** 조건에 맞는 최근 거래만 모았습니다. 건수가 너무 적으면 조건을 넓힙니다.
- 지도: **빨간 테두리**가 경매 물건, **파란 점**이 거래(클수록 같은 건물 거래가 많음)입니다. 파란 점이 많고 촘촘할수록 이 물건도 팔릴 가능성이 높습니다.
- **동·호**는 층·면적을 건축물대장과 맞춘 추정입니다. '?'가 붙으면 후보가 여러 개입니다.
- 거리가 0m인 거래는 **같은 건물의 다른 호수**라 가장 중요한 비교 대상입니다.
- **층**도 봅니다. 같은 건물이라도 지하·1층·고층은 가격이 다릅니다. 이 물건과 같은 층이 팔린 적이 있는지 확인합니다.
- **카카오맵·로드뷰** 링크로 건물 외관, 골목 경사, 주차를 미리 봅니다.

**임장 동선**: '임장' 칸을 체크하면 가까운 지하철역에서 출발하는 최단 방문 순서를 짜 줍니다. 비교 임장은 2–3곳이 적당합니다.
""",
"예상 매도가": """
**왜 보나요?** 입찰가는 **예상 매도가에서 거꾸로** 계산합니다.
**최대 입찰가 = 예상 매도가 − (수리비 + 부대비용 + 희망 차익)**

**읽는 법**
- 예상 매도가 = 비교사례 **평단가 중앙값 × 이 물건 전용평수**입니다.
- **평단가 편차 경고**: 같은 조건인데 평단가가 2배 이상 차이 나면, 컨설팅 업체가 실거래가를 부풀려 신고한 **업계약** 가능성이 있습니다. 이상치는 자동으로 빼고 계산합니다.
- **적용 평단가**는 직접 고칠 수 있습니다. 같은 층·비슷한 상태의 거래를 보고 현실적인 값으로 조정하세요.
- 평단가 그래프에서 빨간 막대가 적용 평단가 구간입니다. 가장 많이 몰린 구간과 비교해 봅니다.

**희망 차익의 기준(강의 어림값, 매매사업자 6–15% 구간)**: 차익 2,500만 → 세후 약 1천만, 4,000만 → 약 2천만, 5,000만 → 약 3천만. 정확한 값은 계산기 탭에서 봅니다.
""",
"전월세": """
**왜 보나요?** 빌라는 아파트보다 매도에 시간이 걸릴 수 있습니다. **안 팔리면 전세로 버틸 수 있는지**, 그때 투자금이 얼마나 묶이는지 미리 봐야 합니다.

**읽는 법**
- **예상 전세가** = 주변 비슷한 빌라의 전세 평단가 중앙값 × 전용평수입니다.
- **전세가율** = 예상 전세가 ÷ 예상 매도가
  - 50–80%: 안 팔리면 전세로 투자금 일부를 회수하며 버틸 수 있는 구간
  - 80% 이상: 회수는 쉽지만 매매가가 떨어지면 역전세 위험, 세입자가 보증보험 가입을 따질 수 있음
  - 50% 미만: 전세를 놓아도 묶이는 돈이 많아 매도 위주로 계획
- **전세 후 남는 투자금** = 최대 입찰가 − 예상 전세가 (취득세·수리비는 따로 더하세요)
- **월세 수익률** = 월세×12 ÷ (입찰가 − 보증금)
- **신규 계약만 보기**를 켜 두세요. 갱신 계약은 인상률 5% 상한 때문에 시세보다 낮게 잡힙니다.
""",
"건물·입지": """
**왜 보나요?** 같은 가격이라도 **주차·엘리베이터·학교·역**에 따라 살 사람이 달라집니다. 서류상 문제(근생)는 대출과 매도를 막습니다.

**건물 정보 읽는 법**
- **근생빌라**: 서류상 '근린생활시설'인데 주거로 쓰는 호실입니다. 대출이 잘 안 나오고 이행강제금 위험이 있습니다. 빨간 경고가 뜨면 특히 주의합니다.
- **엘리베이터 없는 4층 이상**: 고층 호실은 노인·어린 자녀 가구가 꺼립니다.
- **주차**: 세대당 0.5대 미만이면 차가 있는 3–4인 가구에게 팔기 어렵습니다. 노인 가구 대상이면 덜 중요합니다.
- **호수 입력** 시 그 호실의 서류상 용도와 면적을 확인합니다. 입력한 면적과 다르면 경매 정보를 다시 봅니다.
- **위반건축물**은 이 자료에 없습니다. 정부24에서 건축물대장 첫 장 오른쪽 위 '위반건축물' 표시와 매각물건명세서 비고란을 확인하세요.

**입지 읽는 법**
- 경매 물건에서 가장 가까운 시설까지의 거리와 도보 시간입니다(직선거리 기준 추정).
- 매수층별로 중요한 시설이 다릅니다.
  - 3–4인 가구: 초등학교, 대형마트
  - 1–2인 직장인: 지하철역, 버스정류장, 편의점
  - 노인 가구: 병원, 약국 (+저층)
  - 신혼·영유아: 어린이집, 공원
- 아래 '누구에게 팔까'는 거리로 본 참고 의견입니다. 언덕, 큰길 건너기는 로드뷰로 확인합니다.
""",
"임장 체크": """
**왜 보나요?** **손품이 임장보다 중요합니다.** 집에서 걸러낸 물건만 임장 가고, 현장에서는 미리 정한 내용을 **확인만** 합니다. 그래야 하루에 여러 곳을 볼 수 있습니다.

**읽는 법**
- 맨 위 **'이 물건에서 특히 볼 것'**은 다른 탭의 경고(근생, 엘리베이터, 주차, 업계약, 지하층, 노후 건물)를 모은 것입니다. 현장에서 가장 먼저 확인합니다.
- 체크리스트는 출발 전 → 건물 외부 → 호실 → 동네 → 부동산 → 입찰 전 순서입니다.
- 체크한 항목은 새로고침해도 남고, **인쇄**하면 ☑/☐로 나와 현장에서 들고 다닐 수 있습니다.
- **부동산 방문 요령**: "얼마에 팔려요?"가 아니라 "이 가격에 내놓으면 얼마나 걸려요?"로 묻습니다. 기준 없이 가면 사장님 말에 끌려갑니다.
""",
"계산기": """
**왜 보나요?** 같은 차익이라도 세금·이자·중개보수를 빼면 남는 돈이 크게 달라집니다. 입찰가는 **세후 수익**으로 정합니다.

**경매 수익 읽는 법**
- 낙찰가·예상 매도가는 예상 매도가 탭 값으로 처음 채워집니다. 수리비·명도비·대출·보유 기간을 넣습니다.
- **세금 방식**: 매매사업자(종합소득세 6–45%)와 개인 양도세(1년 미만 70%, 2년 미만 60%)를 바꿔 보며 비교합니다. 단기 매도는 매매사업자가 훨씬 유리한 경우가 많습니다.
- **입찰가별 수익표**: 목표 세후 수익을 넣으면 **그 목표를 지키는 최고 입찰가**를 알려 줍니다. ✅가 붙은 줄까지가 목표 달성 범위입니다.
- **필요 현금** = 낙찰가 + 취득세 + 수리·명도·기타 − 대출금. 수익률은 이 현금 대비입니다.

**다른 계산기**: 중개보수(법정 상한요율), 취득세(주택 수·조정지역·85㎡·공시가 1억 이하 중과 제외), 대출 이자(상환 방식별).

**주의**: 법정 세율 기준 어림값입니다. 매매사업자도 중과 대상 주택은 양도세와 비교해 과세(비교과세)될 수 있으니, 실제 입찰 전 세무사와 확인하세요.
""",
}


# ───────────────────────── 지역 찾기 (구를 고르면 동 순위) ─────────────────────────

REGIONS = {
    "서울": ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
             "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
             "관악구", "서초구", "강남구", "송파구", "강동구"],
    "인천": ["중구", "동구", "미추홀구", "연수구", "남동구", "부평구", "계양구", "서구", "강화군"],
    "경기": ["수원시 장안구", "수원시 권선구", "수원시 팔달구", "수원시 영통구", "성남시 수정구", "성남시 중원구",
             "성남시 분당구", "의정부시", "안양시 만안구", "안양시 동안구", "부천시 원미구", "부천시 소사구",
             "부천시 오정구", "광명시", "평택시", "안산시 상록구", "안산시 단원구", "고양시 덕양구",
             "고양시 일산동구", "고양시 일산서구", "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시",
             "의왕시", "하남시", "용인시 처인구", "용인시 기흥구", "용인시 수지구", "파주시", "이천시", "안성시",
             "김포시", "화성시", "광주시", "양주시", "포천시", "동두천시", "여주시"],
}
SIDO_FULL = {"서울": "서울특별시", "인천": "인천광역시", "경기": "경기도"}


@st.cache_data(ttl=60 * 60 * 24 * 30, show_spinner=False)
def region_info(kakao_key: str, full_name: str):
    """'서울특별시 구로구' → (시군구코드 5자리, 위도, 경도). 코드는 카카오 주소 검색 결과에서 가져옴"""
    try:
        r = requests.get(KAKAO_URL, params={"query": full_name},
                         headers={"Authorization": f"KakaoAK {kakao_key.strip()}"}, timeout=10)
        docs = r.json().get("documents", [])
    except Exception:
        return None
    for d in docs:
        ad = d.get("address") or {}
        code = (ad.get("b_code") or ad.get("h_code") or "")[:5]
        if code:
            return code, float(d["y"]), float(d["x"])
    return None


def rank_dongs(trades: pd.DataFrame, rents: pd.DataFrame, min_n: int) -> pd.DataFrame:
    """법정동별 거래량·추세·전세가율·시세 안정성 → 종합 점수"""
    if trades.empty:
        return pd.DataFrame()
    cur = pd.Timestamp(date.today()).to_period("M")
    t = trades.dropna(subset=["deal_date"]).copy()
    t["ym"] = t["deal_date"].dt.to_period("M")
    done = t[t["ym"] < cur]                                  # 이번 달(신고 덜 됨) 제외
    rec_m = [cur - i for i in (1, 2, 3)]
    prev_m = [cur - i for i in (4, 5, 6)]
    rows = []
    for (region, dong), g in t.groupby(["region", "dong"]):
        if len(g) < min_n:
            continue
        gd = done[(done["region"] == region) & (done["dong"] == dong)]
        r_n, p_n = gd["ym"].isin(rec_m).sum(), gd["ym"].isin(prev_m).sum()
        c_chg = (r_n / p_n - 1) * 100 if p_n else (100.0 if r_n else 0.0)
        r_p, p_p = gd[gd["ym"].isin(rec_m)]["ppy"].median(), gd[gd["ym"].isin(prev_m)]["ppy"].median()
        # 직전 3개월이나 최근 3개월에 거래가 없으면 가격 비교를 하지 않음(0으로 둠)
        p_chg = (r_p / p_p - 1) * 100 if (not pd.isna(p_p) and p_p and not pd.isna(r_p)) else 0.0
        ppy = g["ppy"].median()
        q1, q3 = g["ppy"].quantile(0.25), g["ppy"].quantile(0.75)
        cv = (q3 - q1) / ppy if ppy and not pd.isna(ppy) else 1.0
        j_ratio = None
        if not rents.empty:
            rj = rents[(rents["region"] == region) & (rents["dong"] == dong) & (rents["kind"] == "전세")]
            if rj["ctype"].str.contains("신규").any():
                rj = rj[rj["ctype"].str.contains("신규")]
            if len(rj) >= 3 and ppy:
                j_ratio = rj["dep_ppy"].median() / ppy
        rows.append(dict(region=region, dong=dong, n=len(g), c_chg=c_chg, p_chg=p_chg, ppy=ppy,
                         price=g["price"].median(), cv=cv, j_ratio=j_ratio))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    vol_s = df["n"].rank(pct=True) * 100
    trend_s = (df["c_chg"].clip(-100, 200) + df["p_chg"].clip(-20, 20) * 3).rank(pct=True) * 100
    stab_s = (-df["cv"]).rank(pct=True) * 100
    jeonse_s = df["j_ratio"].map(lambda r: 50.0 if r is None or pd.isna(r)
                                 else max(0.0, 100 - abs(r * 100 - 70) * 3))
    df["score"] = (vol_s * 0.4 + trend_s.fillna(50) * 0.2 + jeonse_s * 0.2
                   + stab_s.fillna(50) * 0.2).round(0).fillna(0)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


GUIDE_REGION = """
**왜 보나요?** 빌라는 **팔리는 동네**에서 사야 합니다. 같은 구 안에서도 동마다 거래량과 분위기가 크게 다릅니다.

**읽는 법**
- **점수**(100점) = 거래량 40% + 시장 추세 20% + 전세가율 20% + 시세 안정성 20%
- **거래**: 예산·평수 조건에 맞는 최근 거래 건수입니다. 많을수록 내 물건도 팔기 쉽습니다.
- **거래 추세·가격 추세**: 최근 3개월을 직전 3개월과 비교합니다(이번 달 제외).
- **전세가율**: 70% 근처를 가장 높게 칩니다. 너무 높으면 역전세 위험, 너무 낮으면 전세로 회수가 어렵습니다.
- **시세 안정**: 평단가가 고르게 분포할수록 '높음'입니다. '낮음'이면 업계약·시세 왜곡을 조심하세요.

**활용 순서**: 마음에 드는 동을 고르고 **'이 동 분석하기'**를 누르면 그 동의 동네 프로필(잘 팔리는 유형)로 넘어갑니다.

**한계**: 경매 낙찰가율·경쟁률·경매 낙찰자 매물 비율은 자료가 없어 반영하지 않았습니다.
"""


# ───────────────────────── 생활권 (상가정보) ─────────────────────────

STORE_URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def stores_in_radius(service_key: str, lat: float, lon: float, radius: int):
    """반경 안 상가업소 전체 → DataFrame, 실패하면 오류 문자열"""
    items, page = [], 1
    while page <= 20:
        try:
            r = requests.get(STORE_URL, params={"serviceKey": service_key, "radius": radius, "cx": lon, "cy": lat,
                                                "type": "json", "numOfRows": 1000, "pageNo": page}, timeout=20)
            js = r.json()
        except Exception as e:
            txt = locals().get("r").text[:200] if locals().get("r") is not None else str(e)
            return f"상가정보 조회 실패: {txt}"
        head = js.get("header", {})
        if head.get("resultCode") not in ("00", None):
            if head.get("resultCode") == "03":        # 데이터 없음
                break
            return f"{head.get('resultCode')} {head.get('resultMsg')}"
        body = js.get("body", {})
        chunk = body.get("items") or []
        items += chunk
        if len(items) >= int(body.get("totalCount") or 0) or not chunk:
            break
        page += 1
    df = pd.DataFrame(items)
    if df.empty:
        return df
    for c in ["indsLclsNm", "indsMclsNm", "indsSclsNm", "bizesNm"]:
        df[c] = df.get(c, "").fillna("").astype(str).str.strip()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return df.dropna(subset=["lat", "lon"])


def store_counts(df: pd.DataFrame) -> dict:
    l, m, sc = df["indsLclsNm"], df["indsMclsNm"], df["indsSclsNm"]
    return {
        "전체": len(df),
        "학원": int(((l == "교육") & (m.str.contains("학원") | sc.str.contains("학원"))).sum()),
        "병·의원": int(((l == "보건의료") & ~sc.str.contains("약국")).sum()),
        "약국": int(sc.str.contains("약국").sum()),
        "음식점": int(((l == "음식") & ~sc.str.contains("카페")).sum()),
        "카페": int(sc.str.contains("카페").sum()),
        "편의점": int(sc.str.contains("편의점").sum()),
        "슈퍼·마트": int(sc.str.contains("슈퍼|마트|식료품").sum()),
        "부동산": int((l == "부동산").sum()),
    }


# ───────────────────────── 지형·경사 (Open-Meteo 고도, 키 필요 없음) ─────────────────────────

@st.cache_data(ttl=60 * 60 * 24 * 30, show_spinner=False)
def fetch_elev(lats: tuple, lons: tuple):
    """좌표들의 해발 높이(m). 약 90m 간격 지형 자료라 큰 언덕은 잡지만 골목 하나의 경사는 못 잡음"""
    out = []
    for i in range(0, len(lats), 100):
        try:
            r = requests.get("https://api.open-meteo.com/v1/elevation", params={
                "latitude": ",".join(f"{v:.5f}" for v in lats[i:i + 100]),
                "longitude": ",".join(f"{v:.5f}" for v in lons[i:i + 100])}, timeout=15)
            out += r.json()["elevation"]
        except Exception:
            return None
    return out


def slope_label(pct: float) -> str:
    a = abs(pct)
    return "평지" if a < 3 else "완만" if a < 8 else "가파름" if a < 12 else "매우 가파름"


def offset(lat: float, lon: float, dist_m: float, bearing_deg: float):
    b = math.radians(bearing_deg)
    return (lat + dist_m * math.cos(b) / 111_000,
            lon + dist_m * math.sin(b) / (111_000 * math.cos(math.radians(lat))))


# ───────────────────────── 브이월드: 토지특성 (지형높이·도로접면·용도지역·공시지가) ─────────────────────────

VW_DOMAIN_DEFAULT = "https://villa-scan.streamlit.app"


def vworld_get(path: str, params: dict, domain: str):
    """브이월드 호출 → (dict, 오류문구). 브라우저처럼 요청해야 응답하는 경우가 있어 헤더를 붙임"""
    try:
        r = requests.get(f"https://api.vworld.kr/ned/data/{path}", params=params, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": domain})
    except Exception as e:
        if "RemoteDisconnected" in str(e) or "Connection aborted" in str(e) or "timed out" in str(e):
            return None, ("브이월드가 해외 서버의 접속을 막고 있어 조회되지 않습니다"
                          "(스트림릿 사이트는 미국 서버에서 실행됨). 컴퓨터에서 실행하면 조회됩니다")
        return None, f"연결 실패: {e}"
    try:
        return r.json(), ""
    except ValueError:
        txt = " ".join(r.text.split())[:160]
        return None, f"응답 형식 오류(HTTP {r.status_code}): {txt}"


def make_pnu(b_code: str, jibun: str) -> str:
    """법정동코드10 + 산여부(1 일반, 2 산) + 본번4 + 부번4"""
    jb = (jibun or "").strip()
    mountain = jb.startswith("산")
    bun, _, ji = jb.replace("산", "").strip().partition("-")
    if len(b_code) != 10 or not bun.isdigit() or (ji and not ji.isdigit()):
        return ""
    return f"{b_code}{'2' if mountain else '1'}{bun.zfill(4)}{(ji or '0').zfill(4)}"


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def fetch_land(vkey: str, domain: str, pnu: str):
    """토지특성 최신 1건(dict). 실패하면 오류 문자열"""
    yr = date.today().year
    last_err = ""
    for y in (None, yr, yr - 1, yr - 2):
        params = {"key": vkey.strip(), "domain": domain, "pnu": pnu, "format": "json", "numOfRows": 100, "pageNo": 1}
        if y:
            params["stdrYear"] = y
        js, err = vworld_get("getLandCharacteristics", params, domain)
        if err:
            last_err = err
            if "해외 서버" in err:
                break
            continue
        body = next(iter(js.values()), {}) if isinstance(js, dict) else {}
        rows = body.get("field") or []
        if isinstance(rows, dict):
            rows = [rows]
        if rows:
            return max(rows, key=lambda r: (r.get("stdrYear", ""), r.get("lastUpdtDt", "")))
        last_err = body.get("resultMsg") or body.get("error", {}).get("text", "") or "자료 없음"
    return last_err or "자료 없음"


ROAD_SIDE_HELP = [
    ("광대", "폭 25m 이상 큰길에 접함"), ("중로", "폭 12–25m 길에 접함"), ("소로", "폭 8–12m 길에 접함"),
    ("세로", "폭 8m 미만 골목에 접함"), ("맹지", "길에 접하지 않은 땅(건축·대출에 불리)"),
]


def road_help(name: str) -> str:
    base = next((t for k, t in ROAD_SIDE_HELP if k in name), "")
    if "(가)" in name:
        base += ", 차가 다닐 수 있음"
    elif "(불)" in name:
        base += ", 차가 다니기 어려움"
    if "각지" in name:
        base += ", 모퉁이 땅"
    return base


# ───────────────────────── 브이월드: 공동주택 공시가격 ─────────────────────────

GUARANTEE_RATE = 1.26   # 전세보증보험 전세금 한도 ≈ 공시가격 × 140% × 전세가율 90% (기준은 바뀔 수 있음)


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def fetch_aphus(vkey: str, domain: str, pnu: str):
    """이 지번 공동주택의 연도별·호별 공시가격 전체. 실패하면 오류 문자열"""
    rows, page = [], 1
    while page <= 10:
        js, err = vworld_get("getApartHousingPriceAttr", {
            "key": vkey.strip(), "domain": domain, "pnu": pnu, "format": "json",
            "numOfRows": 1000, "pageNo": page}, domain)
        if err:
            return err
        body = next(iter(js.values()), {}) if isinstance(js, dict) else {}
        chunk = body.get("field") or []
        if isinstance(chunk, dict):
            chunk = [chunk]
        if not chunk and not rows:
            return body.get("resultMsg") or "자료 없음"
        rows += chunk
        if len(rows) >= int(body.get("totalCount") or 0) or not chunk:
            break
        page += 1
    df = pd.DataFrame(rows)
    df["price"] = pd.to_numeric(df.get("pblntfPc"), errors="coerce")
    df["area"] = pd.to_numeric(df.get("prvuseAr"), errors="coerce")
    df["year"] = pd.to_numeric(df.get("stdrYear"), errors="coerce")
    df["ho"] = df.get("hoNm", "").fillna("").astype(str).str.replace("호", "").str.strip()
    df["dong_nm"] = df.get("dongNm", "").fillna("").astype(str).str.strip()
    return df.dropna(subset=["price", "year"])


def norm_ho(h: str) -> str:
    return str(h).replace("호", "").strip().lstrip("0").upper()


def target_aphus(df: pd.DataFrame, ho: str, area_m2: float) -> dict:
    """최신 연도 공시가격에서 이 물건 호실(또는 같은 면적 후보) 찾기"""
    yr = int(df["year"].max())
    latest = df[df["year"] == yr].copy()
    if ho:
        mine = latest[latest["ho"].map(norm_ho) == norm_ho(ho)]
        how = "호수 일치"
    else:
        mine = latest[(latest["area"] - area_m2).abs() <= 0.5]
        how = "전용면적이 같은 호실"
    hist = df[df["ho"].isin(mine["ho"])].groupby("year")["price"].median() if len(mine) else pd.Series(dtype=float)
    return dict(year=yr, latest=latest, mine=mine, how=how, hist=hist)


# ───────────────────────── 카카오맵 (앱 안에 표시, JavaScript 키 필요) ─────────────────────────

KAKAO_MAP_TEMPLATE = r"""
<style>
  html,body{margin:0;padding:0;font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif}
  #wrap{position:relative;width:100%;height:__H__px;border-radius:10px;overflow:hidden;border:1px solid #dde3ea}
  #map{position:absolute;top:0;left:0;width:100%;height:100%}
  #rvbox{position:absolute;top:0;left:0;width:100%;height:100%;display:none;z-index:5;background:#000}
  #rv{width:100%;height:100%}
  .ctl{position:absolute;z-index:6;padding:6px 10px;border-radius:8px;border:1px solid #c5daf3;background:#fff;
       font-size:13px;font-weight:600;color:#1c4f8a;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.15)}
  #mv{left:8px;top:8px} #back{left:8px;top:8px;display:none}
  .dot{border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.35);cursor:pointer}
  .blue{background:#1C7ED6} .yellow{background:#FAB005} .green{background:#2F9E44}
  .ring{width:30px;height:30px;border-radius:50%;border:4px solid #E03131;background:rgba(224,49,49,.08);cursor:pointer}
  .num{background:#fff;border:2px solid #2F9E44;color:#2F9E44;font-weight:800;font-size:12px;border-radius:10px;
       padding:0 6px;pointer-events:none}
  .info{background:#fff;border:1px solid #c9d2dc;border-radius:10px;padding:8px 10px;font-size:12.5px;line-height:1.45;
        max-width:240px;box-shadow:0 2px 8px rgba(0,0,0,.2);color:#222;white-space:normal}
  .info b{font-size:13.5px} .info .btns{margin-top:6px;display:flex;gap:6px}
  .info button{flex:1;white-space:nowrap;min-width:56px;padding:4px 0;border-radius:6px;border:1px solid #1C7ED6;background:#1C7ED6;color:#fff;font-size:12px}
  .info button.x{background:#fff;color:#1C7ED6}
  #err{display:none;padding:12px;color:#c92a2a;font-size:13px}
</style>
<div id="wrap"><div id="map"></div><div id="rvbox"><div id="rv"></div></div>
  <button class="ctl" id="mv"></button><button class="ctl" id="back">← 지도로 돌아가기</button></div>
<div id="err"></div>
<script>
const D = __DATA__;
function esc(t){return String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function fail(m){const e=document.getElementById('err');e.style.display='block';e.textContent=m;
  document.getElementById('wrap').style.display='none';}
// 어디서 실행 중인지(카카오가 확인하는 주소) 보여주기 위한 정보
function where(){let r=document.referrer||'(없음)';let a='';
  try{a=Array.from(location.ancestorOrigins||[]).join(', ');}catch(e){}
  return ' [확인 주소: '+r+(a?' / 상위: '+a:'')+']';}
const sdk=document.createElement('script');
sdk.src='https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false';
sdk.onerror=()=>fail('카카오 지도 파일을 받지 못했습니다(인터넷 연결 또는 키 오류).'+where());
sdk.onload=()=>{
  if(!window.kakao||!kakao.maps){fail('카카오가 이 주소에서의 사용을 거절했습니다. JavaScript 키가 맞는지, '
    +'JavaScript SDK 도메인에 아래 주소가 등록·저장됐는지 확인하세요.'+where());return;}
  start();};
document.head.appendChild(sdk);
function start(){ kakao.maps.load(function(){
  const LL=(a,o)=>new kakao.maps.LatLng(a,o);
  const map=new kakao.maps.Map(document.getElementById('map'),{center:LL(D.target.lat,D.target.lon),level:3});
  map.addControl(new kakao.maps.ZoomControl(),kakao.maps.ControlPosition.RIGHT);
  map.addControl(new kakao.maps.MapTypeControl(),kakao.maps.ControlPosition.TOPRIGHT);
  let movable=D.movable; const mvb=document.getElementById('mv');
  function setMove(v){movable=v;map.setDraggable(v);map.setZoomable(v);
    mvb.textContent=v?'🔓 지도 움직이기 켜짐':'🔒 지도 고정 (누르면 움직이기)';}
  setMove(movable); mvb.onclick=()=>setMove(!movable);
  const rvBox=document.getElementById('rvbox'), back=document.getElementById('back');
  const rvc=new kakao.maps.RoadviewClient(); let rv=null;
  function openRV(lat,lon){const p=LL(lat,lon);
    rvc.getNearestPanoId(p,80,function(id){
      if(id===null){alert('근처 80m 안에 로드뷰가 없습니다.');return;}
      if(info)info.setMap(null);
      rvBox.style.display='block';back.style.display='block';mvb.style.display='none';
      // 로드뷰는 보이는 상태에서 만들어야 크기를 제대로 잡음
      setTimeout(()=>{ if(!rv)rv=new kakao.maps.Roadview(document.getElementById('rv'));
        rv.setPanoId(id,p); rv.relayout(); },30);});}
  back.onclick=()=>{rvBox.style.display='none';back.style.display='none';mvb.style.display='block';map.relayout();};
  let info=null;
  function showInfo(pt){
    if(info)info.setMap(null);
    const box=document.createElement('div');box.className='info';
    box.innerHTML='<b>'+esc(pt.title)+'</b><br>'+esc(pt.label).replace(/\n/g,'<br>');
    const btns=document.createElement('div');btns.className='btns';
    const b1=document.createElement('button');b1.textContent='로드뷰';
    b1.onclick=(ev)=>{ev.stopPropagation();openRV(pt.lat,pt.lon);};
    const b2=document.createElement('button');b2.className='x';b2.textContent='닫기';
    b2.onclick=(ev)=>{ev.stopPropagation();info.setMap(null);};
    box.addEventListener('mousedown',ev=>ev.stopPropagation());
    box.addEventListener('touchstart',ev=>ev.stopPropagation());
    btns.appendChild(b1);btns.appendChild(b2);box.appendChild(btns);
    info=new kakao.maps.CustomOverlay({position:LL(pt.lat,pt.lon),content:box,yAnchor:1.12,zIndex:20});
    info.setMap(map);}
  const bounds=new kakao.maps.LatLngBounds();
  function addEl(pt,el,z){el.onclick=(ev)=>{ev.stopPropagation();showInfo(pt);};
    new kakao.maps.CustomOverlay({position:LL(pt.lat,pt.lon),content:el,xAnchor:.5,yAnchor:.5,zIndex:z}).setMap(map);
    bounds.extend(LL(pt.lat,pt.lon));}
  (D.route||[]).length&&new kakao.maps.Polyline({map:map,path:D.route.map(p=>LL(p[0],p[1])),
    strokeWeight:4,strokeColor:'#2F9E44',strokeOpacity:.85});
  D.points.forEach(pt=>{const el=document.createElement('div');el.className='dot '+(pt.sel?'yellow':'blue');
    el.style.width=el.style.height=pt.size+'px';addEl(pt,el,pt.sel?4:3);});
  (D.stops||[]).forEach(s=>{const el=document.createElement('div');el.className='num';el.textContent=s.num;
    // 번호표는 점 위쪽에 띄우고, 눌러도 아래 점이 반응하도록 클릭을 통과시킴
    new kakao.maps.CustomOverlay({position:LL(s.lat,s.lon),content:el,xAnchor:.5,yAnchor:1.9,zIndex:6}).setMap(map);});
  if(D.station){const el=document.createElement('div');el.className='dot green';el.style.width=el.style.height='16px';
    addEl(D.station,el,5);}
  const t=document.createElement('div');t.className='ring';addEl(D.target,t,7);
  // 스트림릿이 지도 칸 크기를 나중에 정하거나(처음 0px), 다른 메뉴에서 열었다가 돌아오면
  // 카카오맵이 크기를 잘못 계산해 엉뚱한 곳(전국 지도)을 보여주므로, 크기가 바뀔 때마다 다시 맞춤
  let userMoved=false;
  kakao.maps.event.addListener(map,'dragstart',()=>{userMoved=true;});
  kakao.maps.event.addListener(map,'zoom_start',()=>{userMoved=true;});
  function fit(){
    map.relayout();
    if(userMoved)return;
    if(D.fit&&!bounds.isEmpty())map.setBounds(bounds,30,30,30,30);
    else map.setCenter(LL(D.target.lat,D.target.lon));
  }
  fit(); setTimeout(fit,250); setTimeout(fit,1000);
  const wrapEl=document.getElementById('wrap');
  if(window.ResizeObserver){new ResizeObserver(()=>{if(wrapEl.offsetWidth>0&&wrapEl.offsetHeight>0)fit();})
    .observe(wrapEl);}
  else window.addEventListener('resize',fit);
}); }
</script>
"""


def kakao_map_html(js_key: str, data: dict, height: int = 400) -> str:
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (KAKAO_MAP_TEMPLATE.replace("__KEY__", js_key.strip()).replace("__DATA__", js)
            .replace("__H__", str(height)))


# ───────────────────────── 차트 ─────────────────────────

def bin_chart(dist: pd.Series, highlight=None, height=200):
    """구간 순서를 지키고, 이 물건의 구간은 빨간색으로 표시.
    확대/이동 기능을 빼서 휴대폰에서 손가락으로 스크롤해도 그래프가 움직이지 않음"""
    df = pd.DataFrame({"구간": [str(i) for i in dist.index], "거래": dist.values})
    hl = str(highlight) if highlight is not None else ""
    return (alt.Chart(df).mark_bar().encode(
        x=alt.X("구간:N", sort=list(df["구간"]), title=None,
                axis=alt.Axis(labelAngle=-35, labelFontSize=11)),
        y=alt.Y("거래:Q", title=None),
        color=alt.condition(alt.datum["구간"] == hl, alt.value("#E03131"), alt.value("#1C7ED6")),
        tooltip=["구간", "거래"],
    ).properties(height=height))


# ───────────────────────── 화면 ─────────────────────────

def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:  # secrets.toml이 없을 때
        return ""


st.set_page_config(page_title="빌라 시세조사", page_icon="🏘️", layout="wide")
st.title("빌라 시세조사")
st.caption("이 동네에서 실제로 팔리는 빌라인지, 얼마에 팔 수 있는지 확인합니다.")

# 휴대폰에서 맨 위에서 아래로 당길 때 페이지가 새로고침되지 않게 막음
st.markdown("""<style>
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
  overscroll-behavior-y: contain;
}
/* 숫자 카드(metric) 글자를 본문과 어울리게 줄임 */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {
  font-size: 1.25rem !important; line-height: 1.4 !important; font-weight: 600 !important;
}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p { font-size: 0.85rem !important; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] div { font-size: 0.8rem !important; }
[data-testid="stMetric"] { padding: 2px 0 !important; }
/* 탭 메뉴 강조: 색 배경 + 버튼 모양, 휴대폰에서도 모든 탭이 보이도록 줄바꿈
   (스트림릿 버전마다 구조가 달라 여러 이름으로 지정) */
[data-testid="stTabs"] [role="tablist"], div[data-baseweb="tab-list"] {
  flex-wrap: wrap !important; gap: 6px !important; padding: 8px !important;
  border-radius: 12px !important; background: #e7f0fb !important; border: 1px solid #c5daf3 !important;
  overflow: visible !important;
}
[data-testid="stTabs"] [role="tablist"] > div:has(> button[role="tab"]) { display: contents; }
[data-testid="stTabs"] button[role="tab"], button[data-baseweb="tab"] {
  padding: 6px 14px !important; margin: 0 !important; height: auto !important; flex: 0 0 auto !important;
  border-radius: 999px !important; background: #ffffff !important; border: 1px solid #c5daf3 !important;
}
[data-testid="stTabs"] button[role="tab"] *, button[data-baseweb="tab"] * {
  color: #1c4f8a !important; font-weight: 600 !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] {
  background: #1C7ED6 !important; border-color: #1C7ED6 !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] *,
button[data-baseweb="tab"][aria-selected="true"] * { color: #ffffff !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"],
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
/* 탭 줄 오른쪽의 '>' 스크롤 화살표 숨김 (줄바꿈으로 모두 보이므로) */
[data-testid="stTabs"] [role="tablist"] ~ button, [data-testid="stTabs"] button[aria-label*="scroll" i] { display: none !important; }
</style>""", unsafe_allow_html=True)

# 조회 조건을 주소창(URL)에 저장 → 새로고침돼도 같은 조건으로 자동 재조회
qp = st.query_params


def qnum(key, default, lo, hi, cast=int):
    try:
        v = cast(float(qp.get(key, default)))
    except (TypeError, ValueError):
        v = default
    return min(max(v, lo), hi)


# 처음 열릴 때만 주소창 값으로 입력칸을 채움 (이후에는 사용자가 바꾼 값 유지)
_r = qnum("r", 300, 300, 1000)
for k, v in {
    "w_addr": qp.get("addr", ""),
    "w_area": qnum("area", 42.0, 10.0, 200.0, float),
    "w_year": qnum("year", 1990, 1960, date.today().year),
    "w_floor": qnum("floor", 2, -2, 30),
    "w_bid": qnum("bid", 6664, 0, 200000),
    "w_ho": qp.get("ho", ""),
    "w_m": qnum("m", 12, 6, 24),
    "w_r": _r if _r in (300, 500, 700, 1000) else 300,
    "w_at": qnum("at", 3, 1, 6),
    "w_yt": qnum("yt", 5, 2, 15),
    "w_rp": qnum("rp", 500, 0, 10000),
    "w_ex": qnum("ex", 400, 0, 10000),
    "w_pf": qnum("pf", 2500, 0, 20000),
    "w_it": qp.get("it", "1") == "1",
    "w_bk": qp.get("bk", "1") == "1",
    "w_stn": qnum("stn", 0, 0, 4),
    "w_mv": qp.get("mv", "0") == "1",
    "w_fk": qp.get("fk", "음식점"),
    "w_fb": qp.get("fb", "경매 물건 주변"),
    "w_tab": qp.get("tab", "동네 프로필"),
    "w_mode": qp.get("mode", "물건 분석"),
    "w_sr": qnum("sr", 500, 300, 1000),
    "w_slp": qp.get("slp", "지하철역"),
    "rf_sel": [x for x in qp.get("rf", "").split("|") if x],
    "rf_pmin": qnum("rfp0", 5000, 0, 200000), "rf_pmax": qnum("rfp1", 20000, 0, 200000),
    "rf_amin": qnum("rfa0", 8, 0, 60), "rf_amax": qnum("rfa1", 25, 0, 60),
    "rf_minn": qnum("rfn", 5, 1, 50), "rf_rent": qp.get("rfj", "1") == "1",
    "sel_cur": set(filter(None, qp.get("sel", "").split(","))),
    "ck_done": set(filter(None, qp.get("ck", "").split(","))),
}.items():
    st.session_state.setdefault(k, v)
if "ppy" in qp and "w_ppy" not in st.session_state:
    st.session_state["w_ppy"] = qnum("ppy", 1000, 0, 100000)


def reset_all():
    st.query_params.clear()
    st.session_state.clear()
    st.session_state["_reset"] = True


# ── 최근 본 물건: 홈 화면 아이콘처럼 주소가 고정된 링크로 열어도 이어서 볼 수 있게 서버에 기록
RECENT_FILE = "recent_views.json"


@st.cache_resource
def recent_store() -> dict:
    try:
        with open(RECENT_FILE, encoding="utf-8") as f:
            return {"items": json.load(f)}
    except Exception:
        return {"items": []}


def push_recent(params: dict):
    store = recent_store()
    addr = params.get("addr", "")
    if not addr:
        return
    items = [it for it in store["items"] if it["params"].get("addr") != addr]
    old = next((it for it in store["items"] if it["params"].get("addr") == addr), None)
    if old and old["params"] == params:
        return  # 바뀐 게 없으면 저장 안 함
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M")
    store["items"] = ([{"params": params, "time": now}] + items)[:8]
    try:
        with open(RECENT_FILE, "w", encoding="utf-8") as f:
            json.dump(store["items"], f, ensure_ascii=False)
    except Exception:
        pass


def open_recent(params: dict):
    st.session_state.clear()
    st.query_params.from_dict(params)


# 리셋 직후: 브라우저에 기억한 탭 위치도 지움
if st.session_state.pop("_reset", False):
    pass


def sgg_of(address: str) -> str:
    """주소에서 '시도 시군구' 부분만 (예: 경기도 부천시 오정구 고강동 123-4 → 경기도 부천시 오정구)"""
    toks = address.split()
    idx = [i for i, t in enumerate(toks) if t.endswith(("구", "시", "군"))]
    return " ".join(toks[:idx[-1] + 1]) if idx else " ".join(toks[:-2])


def _to_analysis():
    st.session_state["w_mode"] = "물건 분석"


with st.sidebar:
    if st.session_state.get("w_mode") not in ("물건 분석", "지역 찾기"):
        st.session_state["w_mode"] = "물건 분석"
    st.radio("모드", ["물건 분석", "지역 찾기"], key="w_mode", horizontal=True,
             help="지역 찾기: 구를 고르면 빌라 거래가 활발한 동을 순위로 보여줍니다.")
    # API 키는 secrets.toml(또는 스트림릿 Secrets)에 있으면 화면에 보이지 않음. 빠진 키만 입력칸을 보여줌
    data_key, kakao_key, vworld_key = secret("DATA_GO_KR_KEY"), secret("KAKAO_REST_KEY"), secret("VWORLD_KEY")
    vworld_domain = secret("VWORLD_DOMAIN") or VW_DOMAIN_DEFAULT
    if not (data_key and kakao_key and vworld_key):
        with st.expander("API 키 설정", expanded=not (data_key and kakao_key)):
            if not data_key:
                data_key = st.text_input("공공데이터포털 인증키", type="password")
            if not kakao_key:
                kakao_key = st.text_input("카카오 REST API 키", type="password")
            if not vworld_key:
                vworld_key = st.text_input("브이월드 인증키 (선택)", type="password",
                                           help="넣으면 공시가격·지형높이·도로접면·용도지역·공시지가가 나옵니다.")
            st.caption("secrets.toml에 넣어 두면 이 칸은 사라집니다.")

    st.subheader("경매 물건")
    addr = st.text_input("주소 (지번 주소 권장)", key="w_addr",
                         help="예: 경기도 부천시 오정구 고강동 123-4")
    c1, c2 = st.columns(2)
    area_m2 = c1.number_input("전용면적 ㎡", 10.0, 200.0, step=0.1, key="w_area")
    build_year = c2.number_input("건축년도", 1960, date.today().year, key="w_year")
    c3, c4 = st.columns(2)
    floor = c3.number_input("층", -2, 30, key="w_floor")
    min_bid = c4.number_input("최저가 (만원)", 0, 200000, step=10, key="w_bid")
    ho_in = st.text_input("호수 (선택)", key="w_ho",
                          help="예: 301. 넣으면 건물 정보 탭에서 그 호실의 서류상 용도와 면적을 확인합니다.")

    st.subheader("조회 조건")
    months = st.slider("기간 (개월)", 6, 24, key="w_m")
    radius = st.select_slider("반경", [300, 500, 700, 1000], key="w_r", format_func=lambda v: f"{v}m")
    area_tol = st.slider("전용평수 허용 범위 (±평)", 1, 6, key="w_at")
    age_tol = st.slider("연식 허용 범위 (±년)", 2, 15, key="w_yt")
    run = st.button("시세 조회", type="primary", use_container_width=True, on_click=_to_analysis)
    st.button("처음부터 다시 (리셋)", on_click=reset_all, use_container_width=True,
              help="입력값, 선택한 임장지, 조정한 값을 모두 지우고 새로 시작합니다.")

# ───────────────────────── 지역 찾기 화면 ─────────────────────────
def _analyze_dong(full_region: str, dong: str):
    ss_ = st.session_state
    for k in ["trades", "rents", "rent_key", "comps", "w_dong", "ppy_sig", "w_ppy"]:
        ss_.pop(k, None)
    ss_["w_mode"] = "물건 분석"
    ss_["w_addr"] = f"{full_region} {dong}"
    ss_["w_tab"] = "동네 프로필"
    st.query_params["addr"] = f"{full_region} {dong}"
    st.query_params["mode"] = "물건 분석"
    st.query_params.pop("dong", None)


if st.session_state.get("w_mode") == "지역 찾기" and not run:
    ss = st.session_state
    st.subheader("지역 찾기: 빌라 거래가 활발한 동")
    with st.expander("📖 지역 찾기 읽는 법"):
        st.markdown(GUIDE_REGION)
    if not (data_key and kakao_key):
        st.error("왼쪽 메뉴에 API 키 두 개를 넣어 주세요.")
        st.stop()

    options = [f"{sd} {g}" for sd, gs in REGIONS.items() for g in gs]
    ss.rf_sel = [x for x in ss.rf_sel if x in options]
    st.multiselect("지역 (여러 개 선택 가능, 3개 이하 권장)", options, key="rf_sel",
                   placeholder="예: 서울 구로구")
    with st.expander("조건 (예산·평수)", expanded=False):
        c1, c2 = st.columns(2)
        c1.number_input("매매가 최소 (만원)", 0, 200000, step=1000, key="rf_pmin")
        c2.number_input("매매가 최대 (만원)", 0, 200000, step=1000, key="rf_pmax")
        c3, c4 = st.columns(2)
        c3.number_input("전용평수 최소", 0, 60, key="rf_amin")
        c4.number_input("전용평수 최대", 0, 60, key="rf_amax")
        c5, c6 = st.columns(2)
        c5.number_input("동별 최소 거래 건수", 1, 50, key="rf_minn")
        c6.checkbox("전세가율 포함", key="rf_rent", help="전월세 API가 승인되어 있어야 합니다.")
    st.query_params.update({
        "mode": "지역 찾기", "rf": "|".join(ss.rf_sel), "rfp0": str(ss.rf_pmin), "rfp1": str(ss.rf_pmax),
        "rfa0": str(ss.rf_amin), "rfa1": str(ss.rf_amax), "rfn": str(ss.rf_minn),
        "rfj": "1" if ss.rf_rent else "0"})

    if not ss.rf_sel:
        st.info("위에서 지역(구)을 고르면 그 안의 동을 순위로 보여줍니다.")
        st.stop()

    trs, rts, info, fails = [], [], {}, []
    prog = st.progress(0.0, text="실거래 불러오는 중")
    rent_url = None
    for i, name in enumerate(ss.rf_sel):
        sd, g = name.split(" ", 1)
        full = f"{SIDO_FULL[sd]} {g}"
        ri = region_info(kakao_key, full)
        if not ri:
            fails.append(name)
            continue
        code, rlat, rlon = ri
        info[name] = dict(full=full, lat=rlat, lon=rlon)
        rows = []
        for ym in recent_months(12):
            try:
                rows += fetch_month(data_key, code, ym)
            except Exception:
                pass
        df_ = clean_trades(rows)
        if not df_.empty:
            df_["region"] = name
            trs.append(df_)
        if ss.rf_rent:
            if rent_url is None:
                rent_url, _ = find_rent_url(data_key, code, recent_months(1)[0])
                rent_url = rent_url or ""
            if rent_url:
                rrows = []
                for ym in recent_months(12):
                    try:
                        rrows += fetch_month(data_key, code, ym, rent_url)
                    except Exception:
                        pass
                rd = clean_rents(rrows)
                if not rd.empty:
                    rd["region"] = name
                    rts.append(rd)
        prog.progress((i + 1) / len(ss.rf_sel), text=f"{name} 완료")
    prog.empty()
    if fails:
        st.warning(f"지역 코드를 찾지 못했습니다: {', '.join(fails)}")
    if ss.rf_rent and rent_url == "":
        st.caption("전월세 API 승인이 확인되지 않아 전세가율은 빼고 계산했습니다.")
    if not trs:
        st.error("고른 지역의 빌라 실거래를 불러오지 못했습니다.")
        st.stop()

    T = pd.concat(trs, ignore_index=True)
    T = T[T["price"].between(ss.rf_pmin, ss.rf_pmax) & T["area_py"].between(ss.rf_amin, ss.rf_amax)]
    R = pd.concat(rts, ignore_index=True) if rts else pd.DataFrame()
    if not R.empty:
        R = R[R["area_py"].between(ss.rf_amin, ss.rf_amax)]
    rk = rank_dongs(T, R, ss.rf_minn)
    if rk.empty:
        st.warning("조건에 맞는 동이 없습니다. 예산·평수 범위를 넓히거나 최소 거래 건수를 낮춰 보세요.")
        st.stop()

    def arrow(v, unit="%"):
        return f"▲{v:.0f}{unit}" if v >= 5 else f"▼{abs(v):.0f}{unit}" if v <= -5 else "–"

    st.write(f"조건: {won(ss.rf_pmin)}–{won(ss.rf_pmax)} · 전용 {ss.rf_amin}–{ss.rf_amax}평 · "
             f"최근 12개월 · 동 **{len(rk)}곳**")
    table = pd.DataFrame({
        "순위": range(1, len(rk) + 1),
        "지역": rk["region"], "동": rk["dong"], "점수": rk["score"].astype(int),
        "거래": rk["n"], "거래 추세": rk["c_chg"].map(arrow),
        "가격 추세": rk["p_chg"].map(lambda v: f"▲{v:.1f}%" if v >= 1 else f"▼{abs(v):.1f}%" if v <= -1 else "–"),
        "중앙 매매가": rk["price"].map(won), "평단가(만)": rk["ppy"].round(0).fillna(0).astype(int),
        "전세가율": rk["j_ratio"].map(lambda r: "-" if r is None or pd.isna(r) else f"{r * 100:.0f}%"),
        "시세 안정": rk["cv"].map(lambda c: "높음" if c < 0.25 else "보통" if c < 0.45 else "낮음"),
    })
    st.dataframe(table, hide_index=True, use_container_width=True)

    # 지도: 동 위치에 원 (크기 = 거래량, 색 = 거래 추세)
    qs = [f"{info[r]['full']} {d}" for r, d in zip(rk["region"], rk["dong"])]
    geo_d = geocode_many(kakao_key, qs)
    rk["lat"] = [(geo_d.get(q) or [None])[0] for q in qs]
    rk["lon"] = [(geo_d.get(q) or [None, None])[1] for q in qs]
    mp = rk.dropna(subset=["lat", "lon"]).copy()
    if len(mp):
        import pydeck as pdk
        mp["color"] = [[47, 158, 68, 190] if c >= 5 else [224, 49, 49, 170] if c <= -5 else [134, 142, 150, 170]
                       for c in mp["c_chg"]]
        mp["radius"] = (mp["n"] / mp["n"].max() * 600 + 150).astype(float)
        mp["label"] = [f"{i + 1}위 {r} {d}\n점수 {sc:.0f} · 거래 {n}건\n평단가 {p:,.0f}만"
                       for i, (r, d, sc, n, p) in enumerate(zip(mp["region"], mp["dong"], mp["score"],
                                                                 mp["n"], mp["ppy"]))]
        span = max(mp["lat"].max() - mp["lat"].min(), (mp["lon"].max() - mp["lon"].min()) * 0.8)
        zoom = 13 if span < 0.03 else 12 if span < 0.07 else 11 if span < 0.15 else 10
        st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer("ScatterplotLayer", mp, get_position="[lon, lat]", get_fill_color="color",
                              get_radius="radius", pickable=True, stroked=True, get_line_color=[255, 255, 255],
                              line_width_min_pixels=1)],
            initial_view_state=pdk.ViewState(latitude=mp["lat"].mean(), longitude=mp["lon"].mean(), zoom=zoom),
            tooltip={"text": "{label}"}, map_style=LIGHT_MAP,
            views=[pdk.View(type="MapView", controller=False)]), use_container_width=True)
        st.caption("원 크기: 거래량 · 초록: 거래 늘어남 · 빨강: 거래 줄어듦 · 회색: 비슷함. 원을 누르면 정보가 보입니다.")

    st.markdown("#### 이 동 분석하기")
    pick = st.selectbox("동 선택", range(len(rk)),
                        format_func=lambda i: f"{i + 1}위 · {rk['region'][i]} {rk['dong'][i]} (점수 {rk['score'][i]:.0f})")
    st.button("이 동의 동네 프로필 보기 →", type="primary", use_container_width=True, on_click=_analyze_dong,
              args=(info[rk["region"][pick]]["full"], rk["dong"][pick]))
    st.caption("넘어가면 그 동에서 잘 팔리는 빌라 유형을 볼 수 있습니다. 실제 물건을 볼 때는 지번 주소를 넣어 다시 조회하세요.")
    st.stop()


auto = (not run and "trades" not in st.session_state and bool(qp.get("addr"))
        and bool(data_key) and bool(kakao_key))
if run or auto:
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
    lat0, lon0, b_code = target[:3]
    t_jibun = target[3] if len(target) > 3 else ""
    lawd_cd = b_code[:5]

    with st.spinner(f"최근 {months}개월 실거래를 불러오는 중"):
        rows = []
        for ymd in recent_months(months):
            try:
                rows += fetch_month(data_key, lawd_cd, ymd)
            except PermissionError:
                st.error("공공데이터포털이 접근을 거부했습니다(403). 마이페이지 → 데이터활용 → 활용신청 현황에서 "
                         "'국토교통부_연립다세대 매매 실거래가 자료'가 승인 상태인지 확인하세요. "
                         "승인 직후라면 키가 반영되기까지 1–2시간 걸릴 수 있습니다.")
                st.stop()
            except Exception as e:
                st.warning(f"{ymd} 조회 실패: {str(e).split(' for url')[0]}")
        trades = clean_trades(rows)
    if trades.empty:
        st.error("이 지역의 빌라 실거래가 없습니다. 기간을 늘려 보세요.")
        st.stop()

    if run:  # 새로 조회하면 동네 선택은 새 주소 기준으로
        st.session_state.pop("w_dong", None)
        st.query_params.pop("dong", None)
    st.session_state.update(trades=trades, lat0=lat0, lon0=lon0, addr=addr, b_code=b_code, t_jibun=t_jibun,
                            sgg=sgg_of(addr))
    if run:
        # 시세 조회를 누르면 사이드 메뉴를 접어 결과 화면을 바로 보여줌
        # (매번 새로 실행되도록 시각값을 넣음)
        import time
        components.html(f"""<script>
(function () {{
  // {time.time()}
  let doc; try {{ doc = window.parent.document; }} catch (e) {{ return; }}
  let tries = 0;
  (function close() {{
    const bar = doc.querySelector('section[data-testid="stSidebar"]');
    if (bar && bar.getAttribute('aria-expanded') === 'false') return;      // 이미 접힘
    const btn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
             || doc.querySelector('[data-testid="stSidebarHeader"] button')
             || doc.querySelector('section[data-testid="stSidebar"] button[kind="headerNoPadding"]');
    if (btn) {{ btn.click(); return; }}
    if (++tries < 30) setTimeout(close, 100);
  }})();
}})();
</script>""", height=0)

if "trades" not in st.session_state:
    recents = recent_store()["items"]
    if recents:
        st.markdown("#### 최근 본 물건 이어서 보기")
        for n, it in enumerate(recents):
            p = it["params"]
            label = f"📍 {p.get('addr', '')}  ·  {p.get('tab', '동네 프로필')}  ·  {it['time']}"
            st.button(label, key=f"recent_{n}", on_click=open_recent, args=(p,), use_container_width=True)
        st.caption("누르면 그때의 입력값, 체크한 임장지, 보던 메뉴까지 그대로 열립니다.")
    st.info("왼쪽에 경매 물건 정보를 입력하고 시세 조회를 누르세요. (휴대폰은 왼쪽 위 >> 버튼)")
    with st.expander("📘 앱 전체 사용법 (처음이면 읽어 보세요)", expanded=True):
        st.markdown(GUIDE_ALL)
    st.stop()

trades = st.session_state.trades
lat0, lon0 = st.session_state.lat0, st.session_state.lon0
area_py = area_m2 / PYEONG
age = date.today().year - build_year

dongs = sorted(trades["dong"].dropna().unique())
guess = next((d for d in dongs if d in st.session_state.addr), dongs[0])
if qp.get("dong") in dongs:
    guess = qp.get("dong")
if st.session_state.get("w_dong") not in dongs:
    st.session_state["w_dong"] = guess
dong = st.selectbox("동네", dongs, key="w_dong")

dong_df = trades[trades["dong"] == dong]
print_slot = st.container()

report = {"fit": [], "verdict": "", "comps": None, "est": None, "route": None, "bld": None, "ck": None,
          "calc": None, "rent": None, "loc": None, "weather": None, "food": None, "life": None, "slope": None, "land": None,
          "aphus": None}

with st.expander("📘 앱 전체 사용법"):
    st.markdown(GUIDE_ALL)

SECTIONS = ["동네 프로필", "비교사례", "예상 매도가", "전월세", "건물·입지", "임장 체크", "계산기"]
if st.session_state.get("w_tab") not in SECTIONS:
    st.session_state["w_tab"] = SECTIONS[0]
st.session_state.setdefault("_last_tab", st.session_state["w_tab"])


def _keep_tab():
    # 선택된 메뉴를 다시 눌러 선택이 풀리면 직전 메뉴로 되돌림
    ss_ = st.session_state
    if ss_.get("w_tab") not in SECTIONS:
        ss_["w_tab"] = ss_.get("_last_tab", SECTIONS[0])
    ss_["_last_tab"] = ss_["w_tab"]


# 메뉴: 선택값을 주소창에 저장하므로 새로고침·다른 앱 다녀와도 같은 화면으로 돌아옴
with st.container(key="nav_menu"):
    if hasattr(st, "segmented_control"):
        st.segmented_control("메뉴", SECTIONS, key="w_tab", on_change=_keep_tab,
                             label_visibility="collapsed")
    else:
        st.radio("메뉴", SECTIONS, key="w_tab", horizontal=True, label_visibility="collapsed")
cur_tab = st.session_state.get("w_tab") or st.session_state.get("_last_tab", SECTIONS[0])

# 모든 화면을 계산은 하되(인쇄 보고서용), 고른 화면만 보이게 함
tab1, tab2, tab3, tab_rent, tab4, tab5, tab6 = [st.container(key=f"sec_{i}") for i in range(len(SECTIONS))]
_hide = ", ".join(f".st-key-sec_{i}" for i, n in enumerate(SECTIONS) if n != cur_tab)
st.markdown("<style>" + _hide + " { display: none !important; }"
            ".st-key-nav_menu { background:#e7f0fb; border:1px solid #c5daf3; border-radius:12px; padding:8px; }"
            ".st-key-nav_menu button { font-weight:600; }"
            ".st-key-nav_menu button[data-testid*='Active'], .st-key-nav_menu button[kind*='Active'] "
            "{ background:#1C7ED6 !important; color:#fff !important; border-color:#1C7ED6 !important; }"
            ".st-key-nav_menu button[data-testid*='Active'] *, .st-key-nav_menu button[kind*='Active'] * "
            "{ color:#fff !important; }"
            "</style>", unsafe_allow_html=True)

# 각 탭 맨 위에 '읽는 법' 접힘 메뉴
for _tb, _name in [(tab1, "동네 프로필"), (tab2, "비교사례"), (tab3, "예상 매도가"), (tab_rent, "전월세"),
                   (tab4, "건물·입지"), (tab5, "임장 체크"), (tab6, "계산기")]:
    with _tb:
        with st.expander(f"📖 {_name} 탭 읽는 법"):
            st.markdown(GUIDES[_name])

# 공동주택 공시가격: 여러 탭(전월세·건물·계산기)에서 쓰므로 먼저 계산
aph = None
_pnu = make_pnu(st.session_state.get("b_code", ""), st.session_state.get("t_jibun", ""))
if vworld_key and _pnu:
    _ap = fetch_aphus(vworld_key, vworld_domain, _pnu)
    if isinstance(_ap, pd.DataFrame) and not _ap.empty:
        aph = target_aphus(_ap, st.session_state.get("w_ho", ""), area_m2)
        if len(aph["mine"]):
            aph["price"] = aph["mine"]["price"].median()
            aph["low"] = aph["mine"]["price"].min()
            aph["high"] = aph["mine"]["price"].max()
            aph["cap"] = aph["price"] * GUARANTEE_RATE
        report["aphus"] = dict(year=aph["year"], how=aph["how"], price=aph.get("price"), low=aph.get("low"),
                               high=aph.get("high"), cap=aph.get("cap"), n=len(aph["mine"]))
    elif isinstance(_ap, str):
        aph = {"error": _ap}
        fetch_aphus.clear()   # 실패 결과는 기억하지 않고 다음에 다시 시도

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
            st.altair_chart(bin_chart(dist, targets[name]), use_container_width=True)
            if targets[name] is not None:
                st.caption(f"이 물건: {targets[name]} · 거래 비중 {share:.0f}% · {rank}위")
                report["fit"].append((name, str(targets[name]), share, rank,
                                      str(dist.idxmax()) if dist.sum() else "-"))
    st.caption("빨간 막대가 이 물건이 속한 구간입니다. 매매금액은 최저가 기준입니다.")
    verdict = {4: "네 항목 모두 이 동네에서 잘 팔리는 구간입니다.",
               3: "대부분 잘 팔리는 구간입니다. 벗어난 항목을 임장에서 확인하세요.",
               2: "절반만 맞습니다. 누구에게 팔지 다시 따져 보세요."}
    msg = verdict.get(hits, "이 동네 매수자들이 잘 사지 않는 유형입니다. 손품 단계에서 거르는 것을 권합니다.")
    (st.success if hits >= 3 else st.warning)(msg)
    report["verdict"] = msg
    report["n_dong"] = len(dong_df)

    # ── 동네 시장 온도: 월별 거래량과 평단가 추이
    st.markdown("#### 동네 시장 온도")
    mt = dong_df.dropna(subset=["deal_date"]).copy()
    if len(mt) >= 5:
        mt["ym"] = mt["deal_date"].dt.to_period("M")
        idx = pd.period_range(end=pd.Timestamp(date.today()).to_period("M"), periods=months, freq="M")
        g = mt.groupby("ym").agg(cnt=("price", "size"), ppy=("ppy", "median")).reindex(idx)
        g["cnt"] = g["cnt"].fillna(0).astype(int)
        g["월"] = [p.strftime("%y.%m") for p in g.index]
        base = alt.Chart(g.reset_index(drop=True)).encode(
            x=alt.X("월:N", sort=list(g["월"]), title=None, axis=alt.Axis(labelAngle=-45, labelFontSize=11)))
        bars = base.mark_bar(color="#a5c8ef").encode(
            y=alt.Y("cnt:Q", title="거래 건수"), tooltip=[alt.Tooltip("월"), alt.Tooltip("cnt", title="거래")])
        line = base.mark_line(color="#E03131", point=True).encode(
            y=alt.Y("ppy:Q", title="평단가(만원)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("월"), alt.Tooltip("ppy", title="평단가", format=",.0f")])
        st.altair_chart(alt.layer(bars, line).resolve_scale(y="independent").properties(height=230),
                        use_container_width=True)
        st.caption("막대: 월별 거래 건수 · 빨간 선: 월별 평단가 중앙값. 실거래 신고는 계약 후 30일 안에 하므로 "
                   "이번 달과 지난달은 건수가 더 늘어날 수 있습니다.")

        done = g.iloc[:-1]  # 이번 달(미완성) 제외
        if len(done) >= 6:
            recent, prev = done.iloc[-3:], done.iloc[-6:-3]
            c_chg = (recent["cnt"].sum() / prev["cnt"].sum() - 1) * 100 if prev["cnt"].sum() else None
            r_ppy = mt[mt["ym"].isin(recent.index)]["ppy"].median()
            p_ppy = mt[mt["ym"].isin(prev.index)]["ppy"].median()
            p_chg = (r_ppy / p_ppy - 1) * 100 if p_ppy and not pd.isna(r_ppy) else None
            t1, t2 = st.columns(2)
            t1.metric("거래량 (최근 3개월)", f"{int(recent['cnt'].sum())}건",
                      f"{c_chg:+.0f}% (직전 3개월 대비)" if c_chg is not None else None)
            t2.metric("평단가 (최근 3개월)", f"{r_ppy:,.0f}만" if not pd.isna(r_ppy) else "-",
                      f"{p_chg:+.1f}%" if p_chg is not None else None)
            if c_chg is not None and p_chg is not None:
                if c_chg >= 15 and p_chg >= 2:
                    temp = ("🔥 달아오르는 중", "거래도 늘고 가격도 오릅니다. 매도는 수월하지만 입찰 경쟁이 세질 수 있습니다.")
                elif c_chg >= 15:
                    temp = ("🌤 회복 중", "가격은 그대로인데 거래가 늘고 있습니다. 매도하기 좋은 흐름입니다.")
                elif c_chg <= -15 and p_chg <= -2:
                    temp = ("❄️ 식는 중", "거래도 줄고 가격도 내려갑니다. 예상 매도가를 보수적으로 잡으세요.")
                elif c_chg <= -15:
                    temp = ("🌥 주춤", "거래가 줄고 있습니다. 매도 기간이 길어질 수 있습니다.")
                else:
                    temp = ("🌡 보합", "거래량과 가격 모두 큰 변화가 없습니다.")
                st.info(f"**{temp[0]}** — {temp[1]}")
                report["temp"] = dict(label=temp[0], text=temp[1], cnt=int(recent["cnt"].sum()),
                                      c_chg=c_chg, ppy=r_ppy, p_chg=p_chg)
    else:
        st.info("거래가 적어 추이를 보기 어렵습니다. 조회 기간을 늘려 보세요.")

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
        # 동·호수 추정: 건물별 호실 목록을 받아 층·전용면적으로 대조
        store = expos_store()
        todo = {}
        for q, jb in zip(comps["q"], comps["jibun"]):
            bc = (geo.get(q) or [None, None, ""])[2] or ""
            if (bc, jb) not in store:
                todo[(bc, jb)] = None
        if todo:
            with st.spinner(f"건축물대장에서 {len(todo)}개 건물의 호실 확인 중"):
                with ThreadPoolExecutor(max_workers=6) as ex:
                    for k, res in zip(todo, ex.map(lambda k: fetch_units(data_key, k[0], k[1]), todo)):
                        store[k] = res
        units_of = {q: store.get(((geo.get(q) or [None, None, ""])[2] or "", jb), [])
                    for q, jb in zip(comps["q"], comps["jibun"])}
        errs = {v for v in units_of.values() if isinstance(v, str)}
        if errs:
            st.warning(f"동·호수를 확인하지 못했습니다: {next(iter(errs))}. "
                       "공공데이터포털에서 '건축HUB_건축물대장정보 서비스' 승인 상태를 확인하세요.")
            for k in [k for k, v in store.items() if isinstance(v, str)]:
                store.pop(k)  # 다음 조회 때 다시 시도
        comps["ho"] = [guess_ho(units_of[q], f, a)
                       for q, f, a in zip(comps["q"], comps["floor"], comps["area_m2"])]

        show = comps.assign(
            거래일=comps["deal_date"].dt.strftime("%y.%m.%d"),
            거리=comps["dist_m"].round().astype(int).astype(str) + "m",
            전용평=comps["area_py"].round(1),
            금액=comps["price"].map(won),
            평단가=comps["ppy"].round().astype(int),
        )[["거래일", "name", "ho", "jibun", "거리", "전용평", "build_year", "floor", "금액", "평단가"]]
        report["comps"] = show
        st.caption("임장할 곳의 '임장' 칸을 체크하면, 아래에 지하철역 기준 방문 순서가 나옵니다.")
        st.caption("동·호는 실거래의 층·전용면적을 건축물대장과 대조한 추정입니다. '?'가 붙으면 후보가 여러 개입니다.")
        ids = [hashlib.md5(f"{q}|{d}|{f}|{p}".encode()).hexdigest()[:6]
               for q, d, f, p in zip(comps["q"], comps["deal_date"], comps["floor"], comps["price"])]
        ed_key = "ed_" + hashlib.md5("|".join(ids).encode()).hexdigest()[:8]
        init = st.session_state.setdefault(
            "init_" + ed_key, [i in st.session_state.sel_cur for i in ids])
        ed_df = show.rename(columns={"name": "건물명", "ho": "동·호", "jibun": "지번",
                                     "build_year": "건축년도", "floor": "층"})
        ed_df.insert(0, "임장", init)
        edited = st.data_editor(
            ed_df, key=ed_key, hide_index=True, use_container_width=True,
            disabled=[c for c in ed_df.columns if c != "임장"],
            column_config={"임장": st.column_config.CheckboxColumn("임장", width="small")})
        # 건물별 카카오맵·로드뷰 (같은 창으로 열려 '뒤로가기'로 바로 돌아옴)
        with st.expander("🗺 건물별 카카오맵 · 로드뷰 (새 탭으로 열기)", expanded=not secret("KAKAO_JS_KEY")):
            blds = comps.drop_duplicates("q")
            st.markdown(html_table([
                {"건물": n, "거리": f"{d:.0f}m", "지도": "", "로드뷰": "",
                 "_map": kakao_map_link(n, a_, o_), "_rv": kakao_roadview_link(a_, o_)}
                for n, d, a_, o_ in zip(blds["name"], blds["dist_m"], blds["lat"], blds["lon"])],
                links={"지도": ("_map", "카카오맵"), "로드뷰": ("_rv", "보기")}), unsafe_allow_html=True)
            st.caption("링크는 새 탭으로 열립니다. 다 본 뒤 카카오맵 탭에서 '뒤로가기'로 탭을 닫거나, "
                       "크롬 위쪽 숫자(탭) 버튼에서 streamlit.app 탭을 고르면 이 화면으로 돌아옵니다.")
        sel_rows = [i for i, v in enumerate(edited["임장"].tolist()) if v]
        st.session_state.sel_cur = {ids[i] for i in sel_rows}
        sel_qs = list(dict.fromkeys(comps.loc[sel_rows, "q"]))  # 같은 건물 여러 거래는 한 곳으로

        # 같은 지번의 여러 거래를 한 점으로 묶고, 점을 누르면 내역이 보이게 함
        def summarize(g):
            g = g.sort_values("deal_date", ascending=False)
            name, jibun = str(g["name"].iloc[0]), str(g["jibun"].iloc[0])
            title = name if jibun in name else f"{name} ({jibun})"
            lines = "\n".join(
                f"{d:%y.%m.%d} · {ho or f'{f:.0f}층'} · {won(p)} (평당 {pp:,.0f}만)"
                for d, f, ho, p, pp in zip(g["deal_date"], g["floor"], g["ho"], g["price"], g["ppy"]))
            return pd.Series({
                "lat": g["lat"].iloc[0], "lon": g["lon"].iloc[0], "title": title,
                "label": f"{title} · {g['dist_m'].iloc[0]:.0f}m\n"
                         f"{g['build_year'].iloc[0]:.0f}년식 · 전용 {g['area_py'].iloc[0]:.1f}평\n"
                         f"{lines}",
                "n": len(g),
            })
        grouped = pd.DataFrame([summarize(g).rename(None) for _, g in comps.groupby("q")])
        grouped["q"] = [q for q, _ in comps.groupby("q")]
        grouped["lat"] = grouped["lat"].astype(float)
        grouped["lon"] = grouped["lon"].astype(float)
        grouped["color"] = [[250, 176, 5, 235] if q in sel_qs else [28, 126, 214, 200] for q in grouped["q"]]
        grouped["radius"] = [float(14 if q in sel_qs else 8 + 3 * min(n, 4))
                             for q, n in zip(grouped["q"], grouped["n"])]
        target_df = pd.DataFrame({"lat": [lat0], "lon": [lon0],
                                  "label": [f"경매 물건\n{st.session_state.addr}"]})

        # ── 임장 동선
        route, station = [], None
        if sel_qs:
            st.markdown("#### 임장 동선")
            r1, r2 = st.columns(2)
            include_target = r1.checkbox("경매 물건도 들르기", key="w_it")
            back = r2.checkbox("마지막에 역으로 돌아오기", key="w_bk")
            stops = [dict(name=row.title, lat=row.lat, lon=row.lon)
                     for row in grouped.set_index("q").loc[sel_qs].itertuples()]
            if include_target:
                stops.append(dict(name="경매 물건", lat=lat0, lon=lon0))
            clat = sum(p["lat"] for p in stops) / len(stops)
            clon = sum(p["lon"] for p in stops) / len(stops)
            stations = nearest_stations(kakao_key, round(clat, 4), round(clon, 4))
            if not stations:
                st.warning("2km 안에 지하철역이 없어 경매 물건에서 출발하는 순서로 짰습니다.")
                station = dict(name="경매 물건", lat=lat0, lon=lon0)
                stops = [p for p in stops if p["name"] != "경매 물건"] or stops
            else:
                cur = st.session_state.get("w_stn")
                if not isinstance(cur, int) or not 0 <= cur < len(stations):
                    st.session_state["w_stn"] = 0  # 저장된 값이 비었거나 역 목록이 바뀐 경우
                pick = st.selectbox("출발역", range(len(stations)), key="w_stn",
                                    format_func=lambda i: f"{stations[i]['name']} (중심에서 {stations[i]['dist']:,}m)")
                station = stations[pick]
            route = plan_route(station, stops, back)

            pts = [station] + route + ([station] if back else [])
            legs = [walk_m(a, b) for a, b in zip(pts, pts[1:])]
            total_m = sum(legs)
            total_min = total_m / WALK_M_PER_MIN + STAY_MIN * len(route)
            st.write(f"걷는 거리 약 **{total_m / 1000:.1f}km** · 이동 {total_m / WALK_M_PER_MIN:.0f}분 + "
                     f"확인 {STAY_MIN}분×{len(route)}곳 = 총 **{int(total_min // 60)}시간 {total_min % 60:.0f}분** 예상")
            from html import escape as _esc
            lines = [f"🚇 <b>출발</b> {_esc(station['name'])}"]
            for i, (a, b, m) in enumerate(zip(pts, pts[1:], legs), start=1):
                to = f"<b>{i}. {_esc(b['name'])}</b>" if i <= len(route) else f"🚇 <b>도착</b> {_esc(b['name'])}"
                lines.append(f"{to} — 도보 약 {m / WALK_M_PER_MIN:.0f}분 ({m:,.0f}m) · "
                             f"{link_html(kakao_route_link(a, b), '길찾기')}")
            st.markdown("<div style='line-height:1.9'>" + "<br>".join(lines) + "</div>", unsafe_allow_html=True)
            st.caption("거리는 직선거리에 1.3배를 곱한 추정치입니다. 길찾기를 누르면 카카오맵에서 실제 경로가 열립니다.")
            report["route"] = dict(station=station["name"], back=back, total_m=total_m, total_min=total_min,
                                   rows=[(i, b["name"], m) for i, (b, m) in enumerate(zip(pts[1:], legs), start=1)])

        import pydeck as pdk
        layers = [
            pdk.Layer("ScatterplotLayer", grouped, get_position="[lon, lat]",
                      get_fill_color="color", get_radius="radius",
                      radius_min_pixels=5, radius_max_pixels=20, pickable=True),
            # 경매 물건은 속이 빈 빨간 원 → 같은 자리의 거래 점이 가려지지 않음
            pdk.Layer("ScatterplotLayer", target_df, get_position="[lon, lat]",
                      filled=False, stroked=True, get_line_color=[224, 49, 49],
                      line_width_min_pixels=4, get_radius=25,
                      radius_min_pixels=12, radius_max_pixels=26, pickable=True),
        ]
        view_lat, view_lon, zoom = lat0, lon0, 16
        if route:
            path_pts = [station] + route + ([station] if back else [])
            layers.insert(0, pdk.Layer(
                "PathLayer", pd.DataFrame({"path": [[[p["lon"], p["lat"]] for p in path_pts]]}),
                get_path="path", get_color=[47, 158, 68, 200], width_min_pixels=4))
            nums = pd.DataFrame([dict(lat=p["lat"], lon=p["lon"], t=str(i)) for i, p in enumerate(route, 1)])
            layers.append(pdk.Layer("TextLayer", nums, get_position="[lon, lat]", get_text="t",
                                    get_size=18, get_color=[20, 20, 20], get_pixel_offset=[0, -22],
                                    font_weight=700, background=True, get_background_color=[255, 255, 255, 230]))
            st_df = pd.DataFrame([dict(lat=station["lat"], lon=station["lon"], label=f"출발역\n{station['name']}")])
            layers.append(pdk.Layer("ScatterplotLayer", st_df, get_position="[lon, lat]",
                                    get_fill_color=[47, 158, 68], get_radius=20,
                                    radius_min_pixels=9, radius_max_pixels=14, pickable=True))
            lats = [p["lat"] for p in path_pts]; lons = [p["lon"] for p in path_pts]
            view_lat, view_lon = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
            span = max(max(lats) - min(lats), (max(lons) - min(lons)) * 0.8)
            zoom = 16 if span < 0.004 else 15 if span < 0.009 else 14 if span < 0.018 else 13

        deck = pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=view_lat, longitude=view_lon, zoom=zoom),
            tooltip={"text": "{label}"},
            map_style=LIGHT_MAP,  # 컴퓨터가 다크 모드여도 항상 밝은 지도
        )
        with map_slot:
            if not secret("KAKAO_JS_KEY"):
                st.markdown(f"경매 물건: {link_html(kakao_map_link('경매 물건', lat0, lon0), '카카오맵에서 보기')} · "
                            f"{link_html(kakao_roadview_link(lat0, lon0), '로드뷰')}", unsafe_allow_html=True)
            kjs = secret("KAKAO_JS_KEY")
            if kjs:
                # 카카오맵: 건물명·상가가 보이고, 점을 누르면 정보창 → '로드뷰'로 앱 안에서 바로 확인
                kdata = {
                    "target": {"lat": lat0, "lon": lon0, "title": "경매 물건", "label": st.session_state.addr},
                    "points": [{"lat": float(r.lat), "lon": float(r.lon), "title": r.title,
                                "label": r.label.split("\n", 1)[1] if "\n" in r.label else r.label,
                                "sel": bool(r.q in sel_qs), "size": int(12 + 3 * min(r.n, 4))}
                               for r in grouped.itertuples()],
                    "movable": bool(st.session_state.get("w_mv", False)), "fit": True,
                }
                if route:
                    kdata["route"] = [[p["lat"], p["lon"]] for p in path_pts]
                    kdata["stops"] = [{"lat": p["lat"], "lon": p["lon"], "num": i} for i, p in enumerate(route, 1)]
                    kdata["station"] = {"lat": station["lat"], "lon": station["lon"], "title": "출발역",
                                        "label": station["name"]}
                components.html(kakao_map_html(kjs, kdata, 400), height=410)
                st.caption("빨간 원: 경매 물건 · 파란 점: 최근 거래(클수록 거래 많음) · 노란 점: 선택한 임장지 · "
                           "초록: 출발역과 동선. 점을 누르면 정보창이 뜨고 '로드뷰'로 앱 안에서 바로 볼 수 있습니다. "
                           "지도 왼쪽 위 버튼으로 지도를 움직일 수 있습니다.")
            else:
                move = st.toggle("지도 움직이기 (확대·이동)", key="w_mv",
                                 help="끄면 지도 위에서 손가락으로 화면을 스크롤할 수 있습니다.")
                deck.views = [pdk.View(type="MapView", controller=True if move else False)]
                try:
                    st.pydeck_chart(deck, use_container_width=True, height=380 if move else 300)
                except TypeError:  # 구버전 streamlit
                    st.pydeck_chart(deck, use_container_width=True)
                st.caption("빨간 테두리: 경매 물건 · 파란 점: 최근 거래(클수록 거래 많음) · 노란 점: 선택한 임장지 · "
                           "초록: 출발역과 동선. 점을 누르면 건물명과 거래 내역이 보입니다.")

# ── 임장 계획: 날씨 · 맛집 (비교사례 탭 아래쪽)
with tab2:
    st.markdown("#### 임장 계획: 날씨 · 식사")
    wx = fetch_weather(round(lat0, 3), round(lon0, 3))
    if isinstance(wx, str) or not wx:
        st.info("날씨를 불러오지 못했습니다. 잠시 후 다시 열어 보세요.")
    else:
        wdays = ["월", "화", "수", "목", "금", "토", "일"]
        # 휴대폰에서도 한 줄로 보이도록 가로 스크롤 카드
        cards = []
        for w in wx:
            d = pd.Timestamp(w["date"])
            pop = w["pop"] if w["pop"] is not None else "-"
            cards.append(
                f"<div style='flex:0 0 78px;text-align:center;padding:6px 2px;border-radius:10px;"
                f"background:{'#e6f4ea' if w['good'] else '#f6f7f9'};color:#222;font-size:13px;line-height:1.35'>"
                f"<b>{d.month}/{d.day}({wdays[d.weekday()]})</b><br><span style='font-size:22px'>{w['icon']}</span><br>"
                f"{w['desc']}<br>{w['tmax']:.0f}° / {w['tmin']:.0f}°<br>☔ {pop}%{'<br>👍' if w['good'] else ''}</div>")
        st.markdown("<div style='display:flex;gap:6px;overflow-x:auto;padding-bottom:4px'>"
                    + "".join(cards) + "</div>", unsafe_allow_html=True)
        good_days = [f"{pd.Timestamp(w['date']).month}/{pd.Timestamp(w['date']).day}"
                     f"({wdays[pd.Timestamp(w['date']).weekday()]})" for w in wx if w["good"]]
        st.caption(("임장하기 좋은 날(👍, 초록): " + ", ".join(good_days) + ". ") if good_days else
                   "이번 주는 비·바람 등으로 임장하기 좋은 날이 없습니다. ")
        st.caption("👍 기준: 강수확률 30% 미만, 비 거의 없음, 바람 초속 9m 미만, 기온 −5–32°. Open-Meteo 예보(경매 물건 위치 기준).")
        report["weather"] = wx

    route_now, station_now = globals().get("route"), globals().get("station")
    bases = ["경매 물건 주변"] + (["출발역 주변", "임장 동선 중간"] if route_now and station_now else [])
    if st.session_state.get("w_fb") not in bases:
        st.session_state["w_fb"] = bases[0]
    if st.session_state.get("w_fk") not in ("음식점", "카페"):
        st.session_state["w_fk"] = "음식점"
    f1, f2 = st.columns(2)
    f1.radio("찾을 곳", ["음식점", "카페"], key="w_fk", horizontal=True)
    f2.selectbox("기준 위치", bases, key="w_fb")
    if st.session_state.w_fb == "출발역 주변":
        flat, flon = station_now["lat"], station_now["lon"]
    elif st.session_state.w_fb == "임장 동선 중간":
        flat = sum(p["lat"] for p in route_now) / len(route_now)
        flon = sum(p["lon"] for p in route_now) / len(route_now)
    else:
        flat, flon = lat0, lon0
    foods = nearby_food(kakao_key, round(flat, 4), round(flon, 4), st.session_state.w_fk)
    if foods:
        foods = sorted(foods, key=lambda f: f["dist"])
        base_pt = dict(name="경매 물건" if st.session_state.w_fb == "경매 물건 주변" else st.session_state.w_fb,
                       lat=flat, lon=flon)
        food_rows = [{
            "이름": f["name"], "지도": "", "길찾기": "", "종류": f["cat"], "거리": f"{f['dist']:,}m",
            "도보": f"약 {f['dist'] * WALK_FACTOR / WALK_M_PER_MIN:.0f}분", "후기": "", "전화": f["phone"],
            "_map": kakao_map_link(f["name"], f["lat"], f["lon"]) if f.get("lat") else "",
            "_route": (kakao_route_link(base_pt, dict(name=f["name"], lat=f["lat"], lon=f["lon"]))
                       if f.get("lat") else ""),
            "_url": f["url"]} for f in foods]
        st.markdown(html_table(food_rows, links={"지도": ("_map", "위치 보기"), "길찾기": ("_route", "가는 길"),
                                                 "후기": ("_url", "별점·후기")}), unsafe_allow_html=True)
        st.caption("카카오맵 '맛집' 검색에 잡힌 곳만 가까운 순으로 보여줍니다. 별점과 후기는 '보기'를 눌러 확인하세요.")
        report["food"] = dict(base=st.session_state.w_fb, kind=st.session_state.w_fk, rows=foods[:10])
    else:
        st.info("1km 안에 카카오맵 맛집으로 잡힌 곳이 없습니다. 기준 위치를 바꿔 보세요.")


# ── 예상 매도가
with tab3:
    comps = st.session_state.get("comps", pd.DataFrame())
    est = price_estimate(comps) if not comps.empty else {}
    if not est:
        st.info("비교사례가 있어야 예상 매도가를 계산할 수 있습니다.")
    else:
        if est["spread"] >= 2.0 or est["n_out"] > 0:
            st.warning(
                f"평단가가 {won(est['min'])}–{won(est['max'])}으로 {est['spread']:.1f}배 차이 납니다. "
                f"이상치 {est['n_out']}건은 업계약(컨설팅 작업) 가능성이 있어 계산에서 뺐습니다.")
        sig = (int(round(est["median"])), est["n"])
        if st.session_state.get("ppy_sig") != sig:
            # 비교사례가 바뀌면 새 중앙값으로, 주소창에서 복원한 값이 있으면 첫 번째에는 그대로 둠
            if not (st.session_state.get("ppy_sig") is None and "w_ppy" in st.session_state):
                st.session_state["w_ppy"] = sig[0]
            st.session_state["ppy_sig"] = sig
        ppy = st.number_input("적용 평단가 (만원)", step=10, key="w_ppy",
                              help="이상치를 뺀 중앙값이 기본값입니다. 현장 비교 후 조정하세요.")
        sell = ppy * area_py
        a, b, c = st.columns(3)
        a.metric("예상 매도가", won(sell))
        b.metric("평단가 범위 (중간 50%)", f"{est['p25']:,.0f}–{est['p75']:,.0f}만")
        c.metric("비교 거래", f"{est['n']}건")
        ppy_bins = list(range(int(comps["ppy"].min() // 100 * 100), int(comps["ppy"].max()) + 101, 100))
        ppy_dist = pd.cut(comps["ppy"], bins=ppy_bins, right=False).value_counts().sort_index()
        ppy_dist.index = [f"{int(i.left):,}" for i in ppy_dist.index]
        hl = next((lbl for lbl, iv in zip(ppy_dist.index, ppy_bins) if iv <= ppy < iv + 100), None)
        st.altair_chart(bin_chart(ppy_dist, hl, height=180), use_container_width=True)
        st.caption("평단가 분포(만원, 100만 단위). 빨간 막대가 적용 평단가 구간입니다.")

        st.markdown("**입찰가 역산**")
        x1, x2, x3 = st.columns(3)
        repair = x1.number_input("수리비 (만원)", 0, 10000, step=50, key="w_rp")
        extra = x2.number_input("부대비용 (취득세·명도·중개 등, 만원)", 0, 10000, step=50, key="w_ex")
        profit = x3.number_input("희망 차익 (세전, 만원)", 0, 20000, step=100, key="w_pf")
        bid = sell - repair - extra - profit
        st.metric("최대 입찰가", won(bid), delta=f"최저가 대비 {won(bid - min_bid)}" if bid >= min_bid
                  else f"최저가보다 {won(min_bid - bid)} 낮음", delta_color="normal" if bid >= min_bid else "inverse")
        report["est"] = dict(est=est, ppy=ppy, sell=sell, repair=repair, extra=extra,
                             profit=profit, bid=bid)
        st.caption("희망 차익은 매도가 − 낙찰가 기준입니다. 강의 기준으로 세후 1천만 원은 차익 약 2,500만 원이 필요합니다.")



# ── 전월세 (전세가율 · 투자금 회수)
with tab_rent:
    ss = st.session_state
    lawd = ss.get("b_code", "")[:5]
    rkey = (lawd, months)
    if ss.get("rent_key") != rkey:
        with st.spinner(f"최근 {months}개월 전월세 실거래를 불러오는 중"):
            url, err = find_rent_url(data_key, lawd, recent_months(1)[0])
            rows = []
            if url:
                for ym in recent_months(months):
                    try:
                        rows += fetch_month(data_key, lawd, ym, url)
                    except Exception:
                        pass
            ss.rents, ss.rent_err, ss.rent_key = clean_rents(rows), (err if not url else ""), rkey
    rents, rent_err = ss.get("rents", pd.DataFrame()), ss.get("rent_err", "")

    if rent_err:
        st.error(f"전월세 자료를 불러오지 못했습니다: {rent_err}. 공공데이터포털에서 "
                 "'국토교통부_연립다세대 전월세 실거래가 자료'를 활용신청하고, 승인 후 다시 열어 보세요.")
    elif rents.empty:
        st.info("이 지역의 빌라 전월세 실거래가 없습니다.")
    else:
        rc = rents[rents["area_py"].between(area_py - area_tol, area_py + area_tol)
                   & rents["age"].between(age - age_tol, age + age_tol) & (rents["jibun"] != "")].copy()
        rc["q"] = ss.sgg + " " + rc["dong"].astype(str) + " " + rc["jibun"]
        with st.spinner(f"{rc['q'].nunique()}개 주소 위치 확인 중"):
            geo_r = geocode_many(kakao_key, rc["q"].tolist())
        rc["lat"] = rc["q"].map(lambda q: (geo_r.get(q) or [None])[0])
        rc["lon"] = rc["q"].map(lambda q: (geo_r.get(q) or [None, None])[1])
        rc = rc.dropna(subset=["lat", "lon"])
        rc["dist_m"] = [haversine_m(lat0, lon0, a, b) for a, b in zip(rc["lat"], rc["lon"])]
        rc = rc[rc["dist_m"] <= radius].sort_values("deal_date", ascending=False)

        has_ctype = rc["ctype"].str.len().gt(0).any()
        new_only = st.toggle("신규 계약만 보기 (갱신 계약 제외)", value=bool(has_ctype), disabled=not has_ctype,
                             help="갱신 계약은 인상률 5% 상한 때문에 시세보다 낮게 잡힐 수 있습니다.")
        if new_only and has_ctype:
            rc = rc[rc["ctype"].str.contains("신규")]
        jeonse, wolse = rc[rc["kind"] == "전세"], rc[rc["kind"] == "월세"]
        st.write(f"반경 {radius}m · 전용 {area_py:.1f}±{area_tol}평 · 연식 {age}±{age_tol}년 → "
                 f"전세 **{len(jeonse)}건**, 월세 **{len(wolse)}건**")

        est3 = report.get("est") or {}
        sell = est3.get("sell")
        bid = est3.get("bid", min_bid)
        rent_rep = {}
        if len(jeonse):
            s_ppy = jeonse["dep_ppy"]
            q1, q3 = s_ppy.quantile(0.25), s_ppy.quantile(0.75)
            iq = s_ppy[(s_ppy >= q1 - 1.5 * (q3 - q1)) & (s_ppy <= q3 + 1.5 * (q3 - q1))]
            j_price = iq.median() * area_py
            m1, m2, m3 = st.columns(3)
            m1.metric("예상 전세가", won(j_price))
            m2.metric("전세가율", f"{j_price / sell * 100:.0f}%" if sell else "-",
                      help="예상 전세가 ÷ 예상 매도가")
            left = bid - j_price
            m3.metric("전세 후 남는 투자금", won(left) if left > 0 else f"{won(-left)} 회수 초과",
                      help="최대 입찰가 − 예상 전세가. 취득세·수리비는 따로 더해야 합니다.")
            st.caption(f"전세 평단가 중간 50% {iq.quantile(0.25):,.0f}–{iq.quantile(0.75):,.0f}만 · "
                       f"기준 낙찰가 {won(bid)}(예상 매도가 탭의 최대 입찰가)")
            if sell:
                ratio = j_price / sell
                if ratio >= 0.8:
                    st.warning("전세가율이 80% 이상입니다. 전세로 투자금 회수는 쉽지만, 매매가가 떨어지면 "
                               "역전세 위험이 크고 세입자가 전세보증보험 가입을 확인할 수 있습니다.")
                elif ratio < 0.5:
                    st.info("전세가율이 50% 미만입니다. 전세를 놓아도 묶이는 돈이 많아, 매도 위주로 계획하는 게 좋습니다.")
                else:
                    st.success("전세가율이 50–80%입니다. 안 팔리면 전세로 버티며 투자금 일부를 회수할 수 있는 구간입니다.")
            rent_rep.update(j_price=j_price, ratio=(j_price / sell if sell else None), left=left, nj=len(jeonse))
            if aph and aph.get("cap"):
                cap_m = aph["cap"] / 1e4
                if j_price > cap_m:
                    st.warning(f"전세보증보험 한도(공시가격 {won(aph['price'] / 1e4)} × 126% ≈ **{won(cap_m)}**)보다 "
                               f"예상 전세가가 높습니다. 요즘 세입자는 보증보험이 되는 집을 찾으므로, "
                               f"실제로는 {won(cap_m)} 이하로 전세를 놓아야 할 수 있습니다.")
                else:
                    st.success(f"예상 전세가가 전세보증보험 한도(≈ {won(cap_m)}) 안이라 세입자 구하기에 유리합니다.")
                rent_rep.update(cap=cap_m)
        else:
            st.info("조건에 맞는 전세 거래가 없습니다. 반경이나 허용 범위를 넓혀 보세요.")

        if len(wolse):
            dep_med, rent_med = wolse["deposit"].median(), wolse["rent"].median()
            invest = bid - dep_med
            yld = rent_med * 12 / invest * 100 if invest > 0 else None
            w1, w2 = st.columns(2)
            w1.metric("월세 시세 (중앙값)", f"{won(dep_med)} / {rent_med:,.0f}만")
            w2.metric("월세 수익률 (연)", f"{yld:.1f}%" if yld else "-",
                      help="월세×12 ÷ (최대 입찰가 − 보증금). 세금·공실·수리비 제외")
            rent_rep.update(dep_med=dep_med, rent_med=rent_med, yld=yld, nw=len(wolse))

        if len(rc):
            tbl = rc.assign(
                계약일=rc["deal_date"].dt.strftime("%y.%m.%d"), 구분=rc["kind"],
                거리=rc["dist_m"].round().astype(int).astype(str) + "m", 전용평=rc["area_py"].round(1),
                보증금=rc["deposit"].map(won), 월세=rc["rent"].map(lambda v: f"{v:,.0f}만" if v else "-"),
            )[["계약일", "구분", "name", "거리", "전용평", "build_year", "floor", "보증금", "월세", "ctype"]]
            st.dataframe(tbl.rename(columns={"name": "건물명", "build_year": "건축년도", "floor": "층",
                                             "ctype": "계약"}), hide_index=True, use_container_width=True)
        report["rent"] = rent_rep or None


# ── 건물 정보 (건축물대장)
def ymd(v: str) -> str:
    return f"{v[:4]}.{v[4:6]}.{v[6:8]}" if v and len(v) == 8 and v.isdigit() else "-"


def to_num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


with tab4:
    ss = st.session_state
    bc, tj = ss.get("b_code", ""), ss.get("t_jibun", "")
    store = expos_store()
    if not tj:
        st.info("이 주소의 지번을 확인하지 못해 건축물대장을 조회할 수 없습니다. 지번 주소로 다시 조회해 보세요.")
    else:
        for k, op in [(("title", bc, tj), "title"), ((bc, tj), "units")]:
            if k not in store:
                store[k] = (bld_items(data_key, "getBrTitleInfo", bc, tj) if op == "title"
                            else fetch_units(data_key, bc, tj))
        titles, units = store[("title", bc, tj)], store[(bc, tj)]
        for k in [("title", bc, tj), (bc, tj)]:
            if isinstance(store[k], str):
                st.warning(f"건축물대장 조회 실패: {store[k]}")
                store.pop(k)
        bld = {"rows": [], "checks": []}

        if isinstance(titles, list) and titles:
            mains = [t for t in titles if t.get("mainAtchGbCd", "0") == "0"] or titles
            if len(mains) > 1:
                st.caption(f"이 지번에 주건축물이 {len(mains)}동 있습니다.")
            for t in mains[:3]:
                appr = t.get("useAprDay", "")
                yrs = date.today().year - int(appr[:4]) if appr[:4].isdigit() else None
                hh = int(max(to_num(t.get("hhldCnt")), to_num(t.get("hoCnt")), to_num(t.get("fmlyCnt"))))
                park = int(sum(to_num(t.get(k)) for k in
                               ["indrMechUtcnt", "oudrMechUtcnt", "indrAutoUtcnt", "oudrAutoUtcnt"]))
                elev = int(to_num(t.get("rideUseElvtCnt")) + to_num(t.get("emgenUseElvtCnt")))
                grnd, ugrnd = int(to_num(t.get("grndFlrCnt"))), int(to_num(t.get("ugrndFlrCnt")))
                dn = t.get("dongNm", "").strip()
                st.markdown(f"**{t.get('newPlatPlc') or t.get('platPlc', '')}** {dn}")
                rows = [
                    ("사용승인", f"{ymd(appr)}" + (f" ({yrs}년차)" if yrs is not None else "")),
                    ("구조", t.get("strctCdNm") or "-"),
                    ("용도", t.get("etcPurps") or t.get("mainPurpsCdNm") or "-"),
                    ("층수", f"지상 {grnd}층" + (f" · 지하 {ugrnd}층" if ugrnd else "")),
                    ("세대수", f"{hh}세대" if hh else "-"),
                    ("엘리베이터", f"{elev}대" if elev else "없음"),
                    ("주차", f"{park}대" + (f" (세대당 {park / hh:.1f}대)" if hh else "")),
                    ("대지면적", f"{to_num(t.get('platArea')):,.1f}㎡"),
                    ("건폐율·용적률", f"{to_num(t.get('bcRat')):.1f}% · {to_num(t.get('vlRat')):.1f}%"),
                    ("내진설계", "적용" if t.get("rserthqkDsgnApplyYn") == "1" else "미적용·정보 없음"),
                ]
                st.table(pd.DataFrame(rows, columns=["항목", "내용"]).set_index("항목"))
                bld["rows"] += rows
                if not elev and grnd >= 4:
                    bld["checks"].append(("warn", f"엘리베이터 없는 지상 {grnd}층 건물입니다. 고층 호실은 노인·어린 자녀 가구가 꺼려 매수층이 좁습니다."))
                if hh and park / hh < 0.5:
                    bld["checks"].append(("warn", f"세대당 주차 {park / hh:.1f}대로 부족한 편입니다. 차가 있는 3–4인 가구에는 팔기 어려울 수 있습니다."))
                if "근린생활" in (t.get("mainPurpsCdNm", "") + t.get("etcPurps", "")):
                    bld["checks"].append(("err", "건물 주용도에 근린생활시설이 포함되어 있습니다. 호실별 용도를 꼭 확인하세요."))
        elif isinstance(titles, list):
            st.info("건축물대장 표제부를 찾지 못했습니다.")

        if isinstance(units, list) and units:
            geun = [u for u in units if "근린생활" in u[4]]
            if geun:
                names = ", ".join(sorted(ho_name(u[0], u[1]) for u in geun)[:8])
                bld["checks"].append(("err", f"근생 호실 {len(geun)}개: {names}. 서류상 상가인데 주거로 쓰면 "
                                             "대출이 어렵고 이행강제금 대상이 될 수 있습니다."))
            else:
                bld["checks"].append(("ok", f"전유부 {len(units)}개 호실 모두 주거용 용도입니다(근생 호실 없음)."))
            ho = ss.get("w_ho", "").strip().replace("호", "")
            if ho:
                mine = [u for u in units if u[1].replace("호", "").lstrip("0") == ho.lstrip("0")]
                if mine:
                    d, h, f, a, p = mine[0]
                    diff = a - area_m2
                    msg = (f"{ho_name(d, h)}: {f}층 · 전용 {a:.2f}㎡ · 서류상 용도 '{p or '-'}'")
                    if abs(diff) > 0.1:
                        msg += f" (입력한 전용면적 {area_m2:.2f}㎡과 {diff:+.2f}㎡ 차이)"
                    bld["checks"].append(("err" if "근린생활" in p else "ok", msg))
                else:
                    bld["checks"].append(("warn", f"{ho}호를 건축물대장 전유부에서 찾지 못했습니다. 호수 표기를 확인하세요."))

        bld["checks"].append(("info", "위반건축물 여부는 이 API에 나오지 않습니다. 정부24나 세움터에서 건축물대장을 열람해 "
                                      "첫 장 오른쪽 위 '위반건축물' 표시를 확인하고, 매각물건명세서의 비고란도 함께 보세요."))
        for kind, msg in bld["checks"]:
            {"ok": st.success, "warn": st.warning, "err": st.error, "info": st.info}[kind](msg)
        report["bld"] = bld

# ── 지형·경사 (건물·입지 탭, 입지 위)
with tab4:
    st.markdown("#### 공시가격 (공동주택)")
    if not vworld_key:
        st.caption("브이월드 키를 넣으면 호실별 공시가격이 나옵니다.")
    elif aph is None:
        st.caption("지번을 확인할 수 없어 공시가격을 조회하지 못했습니다.")
    elif "error" in aph:
        st.caption(f"공시가격 조회 실패: {aph['error']}")
    else:
        if not len(aph["mine"]):
            st.info(f"{aph['year']}년 공시가격에서 이 물건 호실을 찾지 못했습니다. 왼쪽 메뉴에 호수를 넣으면 정확히 찾습니다.")
        else:
            p = aph["price"]
            rng_txt = "" if aph["low"] == aph["high"] else f" (후보 {won(aph['low'] / 1e4)}–{won(aph['high'] / 1e4)})"
            hos = ", ".join(sorted({f"{h}호" for h in aph["mine"]["ho"]}))
            a1, a2, a3 = st.columns(3)
            a1.metric(f"{aph['year']}년 공시가격", won(p / 1e4))
            a2.metric("1억 이하", "예" if p <= 1e8 else "아니오",
                      help="공시가격 1억 이하 주택은 다주택 취득세 중과에서 빠집니다(정비구역 등 예외).")
            a3.metric("전세보증보험 한도", won(aph["cap"] / 1e4), help="공시가격 × 140% × 90% ≈ 126%. 기준은 바뀔 수 있습니다.")
            st.caption(f"{aph['how']}: {hos}{rng_txt}")
            est_ = report.get("est") or {}
            if est_.get("sell"):
                st.caption(f"예상 매도가는 공시가격의 **{est_['sell'] * 1e4 / p * 100:.0f}%** 수준입니다. "
                           "같은 동네 다른 빌라와 비교해 너무 높으면 예상 매도가를 다시 보세요.")
            if p <= 1e8:
                st.success("공시가격 1억 이하라 다주택자도 취득세 중과 없이 일반세율(1%대)로 살 수 있습니다. 계산기에 자동 반영했습니다.")
            if len(aph["hist"]) >= 2:
                hdf = aph["hist"].reset_index().rename(columns={"year": "연도", "price": "공시가격"})
                hdf["공시가격(만)"] = (hdf["공시가격"] / 1e4).round(0)
                st.altair_chart(alt.Chart(hdf).mark_line(point=True, color="#1C7ED6").encode(
                    x=alt.X("연도:O", title=None), y=alt.Y("공시가격(만):Q", scale=alt.Scale(zero=False)),
                    tooltip=["연도", "공시가격(만)"]).properties(height=180), use_container_width=True)
                st.caption("이 호실의 연도별 공시가격 추이")
        with st.expander(f"이 건물 전체 호실 공시가격 ({aph['year']}년)"):
            lt = aph["latest"].sort_values("ho", key=lambda c: c.map(lambda h: (len(h), h)))
            st.dataframe(pd.DataFrame({
                "호": (lt["dong_nm"] + " " + lt["ho"] + "호").str.strip(), "전용(㎡)": lt["area"],
                "공시가격": lt["price"].map(lambda v: won(v / 1e4))}), hide_index=True, use_container_width=True)

    st.markdown("#### 지형·경사")
    land = None
    pnu = make_pnu(st.session_state.get("b_code", ""), st.session_state.get("t_jibun", ""))
    if vworld_key and pnu:
        land = fetch_land(vworld_key, vworld_domain, pnu)
        if isinstance(land, str):
            st.caption(f"브이월드 토지특성 조회 실패: {land}")
            fetch_land.clear()   # 실패 결과는 기억하지 않고 다음에 다시 시도
            land = None
    if land:
        hg = land.get("tpgrphHgCodeNm", "-")
        rs = land.get("roadSideCodeNm", "-")
        price_m2 = to_num(land.get("pblntfPclnd"))
        l1, l2, l3 = st.columns(3)
        l1.metric("지형높이 (공식)", hg, help="개별공시지가 조사 때 필지마다 분류한 값: 저지·평지·완경사·급경사·고지")
        l2.metric("도로 접면", rs, help=road_help(rs))
        l3.metric("용도지역", land.get("prposArea1Nm", "-"))
        l4, l5, l6 = st.columns(3)
        l4.metric("공시지가", f"{price_m2 / 1e4:,.0f}만/㎡", f"평당 {price_m2 * PYEONG / 1e4:,.0f}만", delta_color="off")
        l5.metric("대지면적", f"{to_num(land.get('lndpclAr')):,.1f}㎡")
        l6.metric("지형 형상", land.get("tpgrphFrmCodeNm", "-"))
        land_note = f"{land.get('stdrYear', '')}년 기준 · 이용상황 {land.get('ladUseSittnNm', '-')} · 도로: {road_help(rs)}"
        # 세대당 대지지분 추정 (건축물대장 표제부의 대지면적 ÷ 세대수)
        tl = expos_store().get(("title", st.session_state.get("b_code", ""), st.session_state.get("t_jibun", "")))
        if isinstance(tl, list) and tl:
            hh = max(to_num(tl[0].get("hhldCnt")), to_num(tl[0].get("hoCnt")))
            if hh:
                share = to_num(land.get("lndpclAr")) / hh
                land_note += (f" · 세대당 대지지분 약 {share:.1f}㎡({share / PYEONG:.1f}평) → "
                              f"공시지가 기준 땅값 약 {won(share * price_m2 / 1e4)}")
        st.caption(land_note)
        if any(k in hg for k in ("급경사", "고지")):
            st.warning(f"공식 지형높이가 '{hg}'입니다. 노인·유모차 가구는 피할 수 있어 매수층이 좁아집니다.")
        if "맹지" in rs:
            st.error("길에 접하지 않은 땅(맹지)입니다. 재건축·대출에 불리할 수 있습니다.")
        report["land"] = dict(hg=hg, rs=rs, zone=land.get("prposArea1Nm", "-"), price=price_m2,
                              area=to_num(land.get("lndpclAr")), shape=land.get("tpgrphFrmCodeNm", "-"), note=land_note)
    elif not vworld_key:
        st.caption("브이월드 키를 넣으면 공식 지형높이·도로 접면·용도지역·공시지가도 함께 나옵니다.")
    # 1) 주변 지형: 물건 둘레 8방향(150m·300m) 높이와 비교
    ring_pts = [(lat0, lon0)] + [offset(lat0, lon0, d, b) for d in (150, 300) for b in range(0, 360, 45)]
    el = fetch_elev(tuple(p[0] for p in ring_pts), tuple(p[1] for p in ring_pts))
    slope_rep = {}
    if not el:
        st.info("높이 자료를 불러오지 못했습니다. 잠시 후 다시 열어 보세요.")
    else:
        h0, near, far = el[0], el[1:9], el[9:]
        higher = sum(1 for h in near if h0 - h > 3)
        lower = sum(1 for h in near if h - h0 > 3)
        rng = max(el) - min(el)
        if higher >= 6:
            terrain = "언덕 위 (주변보다 높음)"
        elif lower >= 6:
            terrain = "낮은 곳 (주변보다 낮음 · 침수 이력 확인)"
        elif rng < 8:
            terrain = "평지"
        else:
            terrain = "경사지 (한쪽이 높고 한쪽이 낮음)"
        steep_dir = max(range(8), key=lambda i: abs(near[i] - h0))
        dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
        t1, t2, t3 = st.columns(3)
        t1.metric("물건 해발", f"{h0:.0f}m")
        t2.metric("주변 지형", terrain.split(" (")[0])
        t3.metric("반경 300m 높이차", f"{rng:.0f}m")
        st.caption(f"{terrain}. 150m 안에서 높이 차이가 가장 큰 쪽은 **{dirs[steep_dir]}쪽**"
                   f"({near[steep_dir] - h0:+.0f}m)입니다.")
        slope_rep.update(h0=h0, terrain=terrain, rng=rng)

    # 2) 역·정류장·학교 → 물건 경사 그래프
    starts = {}
    for label, params, _ in PLACES:
        if label in ("지하철역", "버스정류장", "초등학교"):
            p = nearest_place(kakao_key, round(lat0, 5), round(lon0, 5), json.dumps(params, ensure_ascii=False))
            if p:
                starts[label] = p
    if starts:
        if st.session_state.get("w_slp") not in starts:
            st.session_state["w_slp"] = next(iter(starts))
        st.radio("어디서 걸어올 때?", list(starts), key="w_slp", horizontal=True)
        sp = starts[st.session_state.w_slp]
        dist = haversine_m(sp["lat"], sp["lon"], lat0, lon0)
        n = int(min(max(dist / 30, 5), 60))
        pts = [(sp["lat"] + (lat0 - sp["lat"]) * i / n, sp["lon"] + (lon0 - sp["lon"]) * i / n) for i in range(n + 1)]
        pe = fetch_elev(tuple(p[0] for p in pts), tuple(p[1] for p in pts))
        if pe:
            seg = dist / n
            prof = pd.DataFrame({"거리(m)": [round(seg * i) for i in range(n + 1)], "해발(m)": pe})
            grads = [(pe[i + 1] - pe[i]) / seg * 100 for i in range(n)]
            # 지형 자료가 90m 간격이라 3칸씩 묶어 평균 경사를 봄
            win = 3
            smooth = [(pe[min(i + win, n)] - pe[i]) / (seg * (min(i + win, n) - i)) * 100 for i in range(n)]
            prof["경사"] = ["가파름" if abs(g) >= 8 else "완만·평지" for g in smooth] + ["완만·평지"]
            climb = pe[-1] - pe[0]
            avg = climb / dist * 100 if dist else 0
            steep_i = next((i for i, g in enumerate(smooth) if g >= 8), None)
            g1, g2, g3 = st.columns(3)
            g1.metric(f"{sp['name']}에서", f"{climb:+.0f}m", "오르막" if climb > 2 else "내리막" if climb < -2 else "거의 평지",
                      delta_color="off")
            g2.metric("평균 경사", f"{avg:+.1f}%", slope_label(avg), delta_color="off")
            g3.metric("가장 가파른 구간", f"{max(smooth, key=abs):+.1f}%", slope_label(max(smooth, key=abs)),
                      delta_color="off")
            area = alt.Chart(prof).mark_area(opacity=0.25, color="#1C7ED6").encode(
                x=alt.X("거리(m):Q", title=f"{sp['name']} → 경매 물건 (직선 {dist:,.0f}m)"),
                y=alt.Y("해발(m):Q", scale=alt.Scale(zero=False)))
            line = alt.Chart(prof).mark_line(color="#1C7ED6").encode(x="거리(m):Q", y="해발(m):Q")
            dots = alt.Chart(prof).mark_circle(size=45).encode(
                x="거리(m):Q", y="해발(m):Q",
                color=alt.Color("경사:N", scale=alt.Scale(domain=["가파름", "완만·평지"],
                                                       range=["#E03131", "#1C7ED6"]), legend=None),
                tooltip=["거리(m)", "해발(m)", "경사"])
            st.altair_chart((area + line + dots).properties(height=200), use_container_width=True)
            if steep_i is not None:
                st.caption(f"빨간 점부터 오르막이 가팔라집니다: 출발 후 약 {seg * steep_i:,.0f}m 지점부터. "
                           "노인·유모차 가구에는 부담이 될 수 있습니다.")
            else:
                st.caption("큰 오르막 없이 걸어올 수 있는 길입니다(직선 기준).")
            slope_rep.update(start=sp["name"], climb=climb, avg=avg,
                             maxg=max(smooth, key=abs), steep_at=(seg * steep_i if steep_i is not None else None))
    st.caption("경사 기준: 3% 미만 평지 · 3–8% 완만 · 8–12% 가파름 · 12% 이상 매우 가파름. "
               "고도 자료가 약 90m 간격이고 직선으로 잰 값이라, 골목 계단·실제 길의 경사는 로드뷰로 꼭 확인하세요.")
    report["slope"] = slope_rep or None


# ── 입지 (건물·입지 탭 아래쪽)
with tab4:
    st.markdown("#### 입지: 가까운 생활 시설")
    rows_loc = []
    with st.spinner("주변 시설 확인 중"):
        for label, params, who in PLACES:
            p = nearest_place(kakao_key, round(lat0, 5), round(lon0, 5), json.dumps(params, ensure_ascii=False))
            if p:
                walk = p["dist"] * WALK_FACTOR / WALK_M_PER_MIN
                rows_loc.append(dict(시설=label, 이름=p["name"], 거리=f"{p['dist']:,}m",
                                     도보=f"약 {walk:.0f}분", 매수층=who,
                                     지도=kakao_map_link(p["name"], p["lat"], p["lon"]), _min=walk))
            else:
                rows_loc.append(dict(시설=label, 이름="2km 안에 없음", 거리="-", 도보="-", 매수층=who,
                                     지도=None, _min=None))
    loc_df = pd.DataFrame(rows_loc)
    st.markdown(html_table([{**{k: v for k, v in r.items() if k != "지도"}, "지도": "", "_url": r["지도"]}
                            for r in rows_loc], links={"지도": ("_url", "보기")}), unsafe_allow_html=True)
    mins = {r["시설"]: r["_min"] for r in rows_loc}

    def near(k, m):
        return mins.get(k) is not None and mins[k] <= m
    fits = []
    if near("초등학교", 10) and (near("대형마트", 20) or near("편의점", 5)):
        fits.append("**3–4인 가구**: 초등학교가 도보 10분 안이라 자녀 가구에게 팔기 좋습니다.")
    elif not near("초등학교", 15):
        fits.append("**3–4인 가구**: 초등학교가 멀어 자녀 가구에게는 약점입니다.")
    if near("지하철역", 10):
        fits.append("**1–2인 직장인**: 지하철역이 도보 10분 안이라 출퇴근 수요가 있습니다.")
    elif not near("지하철역", 15) and not near("버스정류장", 5):
        fits.append("**1–2인 직장인**: 지하철과 버스가 모두 멀어 차 없는 직장인에게 약점입니다.")
    if near("병원", 10) and near("약국", 10):
        fits.append("**노인 가구**: 병원·약국이 가까워 노인 부부에게 맞습니다. 저층이면 더 유리합니다.")
    if near("어린이집·유치원", 7) and near("공원", 10):
        fits.append("**신혼·영유아 가구**: 어린이집과 공원이 가까워 어린 자녀 가구에게 맞습니다.")
    if fits:
        st.markdown("**누구에게 팔까 (거리 기준 참고)**")
        for f in fits:
            st.markdown(f"- {f}")
    st.caption("거리는 직선거리, 도보 시간은 1.3배 보정한 추정입니다. 언덕·큰길 건너기 여부는 로드뷰로 확인하세요.")
    report["loc"] = dict(rows=[{k: v for k, v in r.items() if k not in ("지도", "_min")} for r in rows_loc],
                         fits=[f.replace("**", "") for f in fits])


# ── 생활권 분석 (건물·입지 탭 맨 아래)
with tab4:
    st.markdown("#### 생활권: 주변 상가")
    if st.session_state.get("w_sr") not in (300, 500, 1000):
        st.session_state["w_sr"] = 500
    sr = st.radio("반경", [300, 500, 1000], key="w_sr", horizontal=True, format_func=lambda v: f"{v}m")
    with st.spinner("주변 상가 확인 중"):
        sdf = stores_in_radius(data_key, round(lat0, 5), round(lon0, 5), sr)
    if isinstance(sdf, str):
        st.warning(f"{sdf}. 공공데이터포털 '소상공인시장진흥공단_상가(상권)정보' 승인 상태를 확인하세요.")
    elif sdf.empty:
        st.info("반경 안에 등록된 상가가 없습니다.")
    else:
        cnt = store_counts(sdf)
        keys = ["학원", "병·의원", "약국", "음식점", "카페", "편의점", "슈퍼·마트"]
        st.markdown(f"반경 {sr}m 안 점포 **{cnt['전체']:,}곳** · " +
                    " · ".join(f"{k} **{cnt[k]}**" for k in keys))

        # 상권 지도: 약 100m 칸으로 묶어 원 크기·색으로 밀집도 표시
        g = sdf.assign(cy=(sdf["lat"] / 0.0009).round() * 0.0009, cx=(sdf["lon"] / 0.0011).round() * 0.0011)
        cells = g.groupby(["cy", "cx"]).agg(n=("bizesNm", "size"),
                                             top=("indsLclsNm", lambda x: x.value_counts().index[0])).reset_index()
        cells = cells.rename(columns={"cy": "lat", "cx": "lon"})
        mx = cells["n"].max()
        cells["radius"] = (cells["n"] / mx * 55 + 8).astype(float)
        cells["color"] = [[224, 49, 49, int(60 + 170 * n / mx)] for n in cells["n"]]
        cells["label"] = [f"점포 {n}곳\n주요 업종: {t}" for n, t in zip(cells["n"], cells["top"])]
        hub = cells.sort_values("n", ascending=False).iloc[0]
        hub_m = haversine_m(lat0, lon0, hub["lat"], hub["lon"])
        import pydeck as pdk
        ring = pd.DataFrame({"lat": [lat0], "lon": [lon0], "label": ["경매 물건"]})
        z = 16 if sr <= 300 else 15 if sr <= 500 else 14
        st.pydeck_chart(pdk.Deck(
            layers=[
                pdk.Layer("ScatterplotLayer", ring, get_position="[lon, lat]", filled=False, stroked=True,
                          get_line_color=[28, 126, 214], line_width_min_pixels=2, get_radius=sr),
                pdk.Layer("ScatterplotLayer", cells, get_position="[lon, lat]", get_fill_color="color",
                          get_radius="radius", pickable=True),
                pdk.Layer("ScatterplotLayer", ring, get_position="[lon, lat]", filled=False, stroked=True,
                          get_line_color=[20, 20, 20], line_width_min_pixels=3, get_radius=12,
                          radius_min_pixels=8, pickable=True),
            ],
            initial_view_state=pdk.ViewState(latitude=lat0, longitude=lon0, zoom=z),
            tooltip={"text": "{label}"}, map_style=LIGHT_MAP,
            views=[pdk.View(type="MapView", controller=False)]), use_container_width=True)
        st.caption(f"빨간 원이 크고 진할수록 점포가 몰린 곳입니다. 파란 테두리는 반경 {sr}m, 검은 테두리가 경매 물건. "
                   f"가장 밀집한 곳(상권 중심)까지 약 {hub_m:,.0f}m, 도보 약 {hub_m * WALK_FACTOR / WALK_M_PER_MIN:.0f}분.")

        lc = sdf["indsLclsNm"].replace("", "기타").value_counts()
        st.altair_chart(bin_chart(lc, None, height=200), use_container_width=True)
        st.caption("업종 대분류별 점포 수")

        k = (500 / sr) ** 2          # 반경이 달라도 비교할 수 있게 500m 기준으로 환산
        life = []
        if cnt["학원"] * k >= 15:
            life.append(f"**학원가**: 학원 {cnt['학원']}곳 → 초·중등 자녀를 둔 3~4인 가구가 선호하는 동네입니다.")
        if (cnt["병·의원"] + cnt["약국"]) * k >= 15:
            life.append(f"**의료 편리**: 병·의원 {cnt['병·의원']}곳, 약국 {cnt['약국']}곳 → 노인 가구에 유리합니다.")
        food_share = (cnt["음식점"] + cnt["카페"]) / max(cnt["전체"], 1)
        if food_share >= 0.4 and cnt["편의점"] * k >= 5:
            life.append("**1~2인 생활권**: 음식점·카페·편의점 비중이 높아 혼자 사는 직장인·청년이 살기 편합니다.")
        if cnt["전체"] * k < 80:
            life.append("**조용한 주거지**: 상가가 적어 조용하지만, 생활 편의시설까지 걸어야 할 수 있습니다.")
        if hub_m <= 300:
            life.append(f"**상권과 가까움**: 상권 중심까지 {hub_m:,.0f}m라 생활은 편하지만, 1층·저층은 소음을 확인하세요.")
        for t in life:
            st.markdown(f"- {t}")
        st.caption(f"소상공인시장진흥공단 상가정보 기준(점포 등록 기준이라 실제와 조금 다를 수 있음).")
        report["life"] = dict(radius=sr, cnt=cnt, hub_m=hub_m, notes=[t.replace("**", "") for t in life])


# ── 임장 체크리스트
with tab5:
    ss = st.session_state
    # 이 물건에서 특히 볼 것: 다른 탭의 분석 결과에서 자동으로 뽑음
    focus = []
    bl = report.get("bld") or {}
    focus += [m for k, m in bl.get("checks", []) if k in ("warn", "err")]
    r_est = report.get("est")
    if r_est and (r_est["est"]["spread"] >= 2.0 or r_est["est"]["n_out"] > 0):
        focus.append("평단가 편차가 커서 업계약 가능성이 있습니다. 부동산에서 실제 거래 가능 가격을 꼭 확인하세요.")
    if report.get("verdict") and "모두" not in report["verdict"]:
        focus.append("동네 프로필과 맞지 않는 항목이 있습니다. 이 물건을 누구에게 팔지 현장에서 다시 따져 보세요.")
    if floor < 1:
        focus.append("지하·반지하 호실입니다. 습기·결로·곰팡이, 채광, 침수 이력을 꼭 확인하세요.")
    ld = report.get("land") or {}
    if any(k in ld.get("hg", "") for k in ("급경사", "고지")):
        focus.append(f"공식 지형높이 '{ld['hg']}' 필지입니다. 집까지 오르막을 직접 걸어 보세요.")
    if "맹지" in ld.get("rs", ""):
        focus.append("맹지(길에 접하지 않은 땅)입니다. 진입로와 통행 권리를 확인하세요.")
    sl = report.get("slope") or {}
    if sl.get("maxg") is not None and abs(sl["maxg"]) >= 8:
        focus.append(f"{sl['start']}에서 오는 길에 가파른 구간({sl['maxg']:+.0f}%)이 있습니다. "
                     "직접 걸어 보고 노인·유모차 가구에 부담이 될지 확인하세요.")
    if sl.get("terrain", "").startswith("언덕"):
        focus.append("언덕 위 물건입니다. 겨울 빙판길, 차량 진입, 마을버스 노선을 확인하세요.")
    if sl.get("terrain", "").startswith("낮은"):
        focus.append("주변보다 낮은 곳입니다. 침수 이력과 반지하·1층 습기를 꼭 확인하세요.")
    if age >= 30:
        focus.append(f"{age}년 된 건물입니다. 누수 흔적, 배관 교체 여부, 외벽 균열을 집중해서 보세요.")
    if focus:
        st.markdown("#### 이 물건에서 특히 볼 것")
        for m in focus:
            st.warning(m)

    total = sum(len(items) for _, items in CHECKLIST)
    for _, items in CHECKLIST:
        for cid, _ in items:
            st.session_state.setdefault(f"ck_{cid}", cid in ss.ck_done)
    done = sum(ss.get(f"ck_{cid}", False) for _, items in CHECKLIST for cid, _ in items)
    st.progress(done / total, text=f"체크리스트 {done}/{total}")

    for section, items in CHECKLIST:
        # 제목을 고정해야 체크할 때마다 펼친 칸이 접히지 않음
        with st.expander(section, expanded=False):
            for cid, text in items:
                st.checkbox(text, key=f"ck_{cid}")
    ss.ck_done = {cid for _, items in CHECKLIST for cid, _ in items if ss.get(f"ck_{cid}")}

    with st.expander("참고 중요사항 (강의 핵심 원칙)"):
        st.markdown(KEY_NOTES)
    st.caption("체크한 항목은 새로고침해도 유지되고, 리셋하면 지워집니다. 인쇄 보고서에도 들어갑니다.")
    report["ck"] = dict(focus=focus, done=ss.ck_done)

# ── 계산기 (네이버 부동산 계산기 참고)
with tab6:
    ss = st.session_state
    r_est = report.get("est") or {}
    # 처음 열 때 이 물건 값으로 채우고, 이후에는 주소창에 저장된 값을 씀
    c_defaults = {
        "c_kind": "경매 수익", "c_amt": max(0, int(r_est.get("sell", 10000))), "c_dep": 5000, "c_rent": 50,
        "c_deal": "매매", "c_rate": 0.0, "c_vat": False, "c_ptype": "주택",
        "c_price": max(0, int(r_est.get("bid", min_bid) or min_bid)), "c_houses": 1, "c_adj": False,
        "c_over85": area_m2 > 85, "c_corp": False,
        "c_low": bool(aph and aph.get("price") and aph["price"] <= 1e8),
        "c_loan": 0, "c_irate": 4.5, "c_months": 6, "c_method": "원리금균등",
        "c_bid": max(0, int(r_est.get("bid", min_bid) or min_bid)),
        "c_sell": max(0, int(r_est.get("sell", min_bid * 1.4))),
        "c_repair": int(ss.get("w_rp", 500)), "c_evict": 100, "c_etc": 100,
        "c_taxmode": "매매사업자(종합소득세)",
        "c_target": 1000,
    }
    for k, d in c_defaults.items():
        if k not in ss:
            raw = qp.get(k)
            try:
                ss[k] = (raw == "1" if isinstance(d, bool) else type(d)(float(raw)) if isinstance(d, (int, float))
                         else raw) if raw is not None else d
            except (TypeError, ValueError):
                ss[k] = d

    kinds = ["경매 수익", "중개보수", "취득세", "대출 이자"]
    if ss.c_kind not in kinds:
        ss.c_kind = kinds[0]
    st.radio("계산기", kinds, key="c_kind", horizontal=True, label_visibility="collapsed")
    st.caption("법정 상한·세율 기준 어림값입니다. 실제 금액은 감면·특례·협의에 따라 달라지니 계약·신고 전에 꼭 확인하세요.")

    if ss.c_kind == "중개보수":
        st.radio("거래 종류", ["매매", "전세", "월세"], key="c_deal", horizontal=True)
        if ss.c_ptype not in ("주택", "주택 외(상가·토지 등)"):
            ss.c_ptype = "주택"
        st.radio("매물 종류", ["주택", "주택 외(상가·토지 등)"], key="c_ptype", horizontal=True)
        if ss.c_deal == "월세":
            a1, a2 = st.columns(2)
            a1.number_input("보증금 (만원)", 0, 1_000_000, step=500, key="c_dep")
            a2.number_input("월세 (만원)", 0, 10_000, step=5, key="c_rent")
            amount = monthly_rent_base(ss.c_dep * 1e4, ss.c_rent * 1e4)
            st.caption(f"환산 거래금액 {won(amount / 1e4)} (보증금 + 월세×100, 5천만 원 미만이면 ×70)")
        else:
            st.number_input("거래금액 (만원)", 0, 10_000_000, step=500, key="c_amt")
            amount = ss.c_amt * 1e4
        b1, b2 = st.columns(2)
        b1.number_input("협의 요율 % (0이면 상한요율)", 0.0, 0.9, step=0.05, key="c_rate", format="%.2f")
        b2.checkbox("부가세 10% 포함 (일반과세자 중개사)", key="c_vat")
        if ss.c_ptype == "주택":
            fee, rate, cap = brokerage_fee(amount, FEE_SALE if ss.c_deal == "매매" else FEE_LEASE)
        else:
            fee, rate, cap = amount * 0.009, 0.009, None
        if ss.c_rate > 0:
            fee = amount * min(ss.c_rate / 100, rate) if ss.c_ptype == "주택" else amount * ss.c_rate / 100
            if cap:
                fee = min(fee, cap)
        vat = fee * 0.1 if ss.c_vat else 0
        m1, m2 = st.columns(2)
        m1.metric("중개보수 (1인 부담)", f"{fee + vat:,.0f}원")
        m2.metric("상한요율", f"{rate * 100:.1f}%" + (f" · 한도 {cap:,.0f}원" if cap else ""))
        st.caption("매매는 매도인·매수인이, 임대차는 임대인·임차인이 각자 부담합니다. 주택 외 부동산은 0.9% 이내에서 협의합니다.")

    elif ss.c_kind == "취득세":
        st.number_input("취득가액 (만원)", 0, 10_000_000, step=100, key="c_price")
        a1, a2 = st.columns(2)
        a1.number_input("취득 후 주택 수", 1, 10, key="c_houses")
        a2.checkbox("조정대상지역", key="c_adj")
        a3, a4 = st.columns(2)
        a3.checkbox("전용 85㎡ 초과", key="c_over85")
        a4.checkbox("법인 취득", key="c_corp")
        st.checkbox("시가표준액(공시가격) 1억 원 이하 주택 → 중과 제외", key="c_low",
                    help="정비구역 등으로 지정된 곳의 주택은 제외될 수 있습니다.")
        t = acq_tax(ss.c_price * 1e4, ss.c_houses, ss.c_adj, ss.c_over85, ss.c_corp, ss.c_low)
        st.metric("총 납부액", f"{t['total']:,.0f}원", f"합계 세율 {t['total_rate']:.2f}%", delta_color="off")
        st.table(pd.DataFrame([
            ("취득세", f"{t['rate']:.2f}%", f"{t['tax']:,.0f}원"),
            ("지방교육세", f"{t['edu']:.2f}%", f"{t['edu_tax']:,.0f}원"),
            ("농어촌특별세", f"{t['agri']:.2f}%", f"{t['agri_tax']:,.0f}원"),
        ], columns=["세목", "세율", "금액"]).set_index("세목"))
        st.caption(f"적용: {t['why']}. 일시적 2주택·생애최초 감면 등 특례는 반영하지 않았습니다.")

    elif ss.c_kind == "대출 이자":
        st.number_input("대출금 (만원)", 0, 10_000_000, step=500, key="c_loan")
        a1, a2 = st.columns(2)
        a1.number_input("연 금리 %", 0.0, 30.0, step=0.1, key="c_irate", format="%.2f")
        a2.number_input("기간 (개월)", 1, 480, key="c_months")
        if ss.c_method not in ("원리금균등", "원금균등", "만기일시"):
            ss.c_method = "원리금균등"
        st.radio("상환 방식", ["원리금균등", "원금균등", "만기일시"], key="c_method", horizontal=True)
        ln = loan_schedule(ss.c_loan * 1e4, ss.c_irate, ss.c_months, ss.c_method)
        m1, m2 = st.columns(2)
        m1.metric("첫 달 납입액", f"{ln['first']:,.0f}원")
        m2.metric("총 이자", f"{ln['total_interest']:,.0f}원")
        st.caption("경매 단기 보유라면 만기일시(이자만 납부)로 보유 개월 수만큼 넣어 이자 비용을 가늠하세요.")

    else:  # 경매 수익
        st.caption("예상 매도가 탭의 값으로 처음 채워집니다. 값을 바꾸면 그대로 기억합니다.")
        a1, a2 = st.columns(2)
        a1.number_input("낙찰가 (만원)", 0, 10_000_000, step=10, key="c_bid")
        a2.number_input("예상 매도가 (만원)", 0, 10_000_000, step=10, key="c_sell")
        a3, a4, a5 = st.columns(3)
        a3.number_input("수리비 (만원)", 0, 100_000, step=50, key="c_repair")
        a4.number_input("명도비 (만원)", 0, 100_000, step=50, key="c_evict")
        a5.number_input("법무사·기타 (만원)", 0, 100_000, step=10, key="c_etc")
        b1, b2, b3 = st.columns(3)
        b1.number_input("대출금 (만원)", 0, 10_000_000, step=500, key="c_loan")
        b2.number_input("연 금리 %", 0.0, 30.0, step=0.1, key="c_irate", format="%.2f")
        b3.number_input("보유 기간 (개월)", 1, 480, key="c_months")
        c1, c2 = st.columns(2)
        c1.number_input("취득 후 주택 수", 1, 10, key="c_houses")
        c2.checkbox("조정대상지역", key="c_adj")
        st.checkbox("시가표준액(공시가격) 1억 원 이하 주택 → 취득세 중과 제외", key="c_low")
        modes = ["매매사업자(종합소득세)", "개인 양도소득세"]
        if ss.c_taxmode not in modes:
            ss.c_taxmode = modes[0]
        st.radio("세금 계산", modes, key="c_taxmode", horizontal=True)

        bid_w, sell_w = ss.c_bid * 1e4, ss.c_sell * 1e4
        extra_w = (ss.c_repair + ss.c_evict + ss.c_etc) * 1e4
        args = (sell_w, extra_w, ss.c_loan * 1e4, ss.c_irate, ss.c_months, ss.c_houses, ss.c_adj,
                area_m2 > 85, ss.c_low, ss.c_taxmode)
        pf = auction_profit(bid_w, *args)
        t, sale_fee, interest, gap, pre_tax = pf["t"], pf["sale_fee"], pf["interest"], pf["gap"], pf["pre"]
        tax, tax_note, after, own_cash = pf["tax"], pf["note"], pf["after"], pf["cash"]
        m1, m2, m3 = st.columns(3)
        m1.metric("매매 차익 (매도가 − 낙찰가)", won(gap / 1e4))
        m2.metric("세전 순이익", won(pre_tax / 1e4))
        m3.metric("세후 순이익", won(after / 1e4))
        st.table(pd.DataFrame([
            ("취득세 등", f"{t['total']:,.0f}원 ({t['total_rate']:.2f}%, {t['why']})"),
            ("수리·명도·기타", f"{(ss.c_repair + ss.c_evict + ss.c_etc) * 1e4:,.0f}원"),
            ("매도 중개보수(부가세 포함)", f"{sale_fee:,.0f}원"),
            ("대출 이자", f"{interest:,.0f}원 ({ss.c_months}개월)"),
            ("세금", f"{tax:,.0f}원 ({tax_note})"),
            ("필요 현금(대출 제외)", f"{own_cash:,.0f}원"),
            ("현금 대비 세후 수익률", f"{after / own_cash * 100:.1f}%" if own_cash > 0 else "-"),
        ], columns=["항목", "금액"]).set_index("항목"))
        st.caption("매매사업자도 조정대상지역 다주택 등 중과 대상 주택은 양도세와 비교해 큰 쪽으로 과세될 수 있습니다(비교과세). "
                   "정확한 세금은 세무사와 확인하세요.")
        # ── 입찰가별 수익표
        st.markdown("#### 입찰가별 수익표")
        st.number_input("목표 세후 수익 (만원)", 0, 1_000_000, step=100, key="c_target")
        target_w = ss.c_target * 1e4
        # 목표를 맞추는 최고 낙찰가를 이분 탐색으로 찾음 (낙찰가가 오를수록 수익은 줄어듦)
        lo_b, hi_b = 0.0, sell_w
        if auction_profit(lo_b, *args)["after"] < target_w:
            max_bid = None
        else:
            for _ in range(40):
                mid = (lo_b + hi_b) / 2
                lo_b, hi_b = (mid, hi_b) if auction_profit(mid, *args)["after"] >= target_w else (lo_b, mid)
            max_bid = lo_b
        if max_bid is not None and max_bid >= min_bid * 1e4:
            st.success(f"세후 {won(ss.c_target)}을 남기려면 **최대 {won(max_bid / 1e4)}**까지 쓸 수 있습니다 "
                       f"(최저가 대비 {max_bid / (min_bid * 1e4) * 100:.0f}%).")
        elif max_bid is not None:
            st.error(f"세후 {won(ss.c_target)}을 남기려면 {won(max_bid / 1e4)} 이하로 낙찰받아야 하는데, "
                     f"최저가 {won(min_bid)}보다 낮습니다. 이 조건으로는 목표 달성이 어렵습니다.")
        else:
            st.error("예상 매도가로는 목표 세후 수익을 낼 수 없습니다.")

        start = min_bid * 1e4
        end = max(max_bid or start, bid_w, start) * 1.08
        steps = 8
        levels = sorted({round((start + (end - start) * i / steps) / 1e5) * 1e5 for i in range(steps + 1)}
                        | ({round(max_bid / 1e5) * 1e5} if max_bid and max_bid >= start else set()))
        rows_b = []
        for b_w in levels:
            p = auction_profit(b_w, *args)
            rows_b.append({
                "낙찰가": won(b_w / 1e4),
                "최저가 대비": f"{b_w / start * 100:.0f}%",
                "매도가 대비": f"{b_w / sell_w * 100:.0f}%" if sell_w else "-",
                "세전 순이익": won(p["pre"] / 1e4),
                "세후 순이익": won(p["after"] / 1e4),
                "필요 현금": won(p["cash"] / 1e4),
                "수익률": f"{p['after'] / p['cash'] * 100:.0f}%" if p["cash"] > 0 else "-",
                "목표": "✅" if p["after"] >= target_w else "",
            })
        st.dataframe(pd.DataFrame(rows_b), hide_index=True, use_container_width=True)
        st.caption("대출금은 위에 넣은 금액으로 고정해 계산합니다. 낙찰가에 비례해 대출이 늘면 필요 현금은 줄고 이자는 늘어납니다.")

        report["calc"] = dict(gap=gap, pre=pre_tax, after=after, tax=tax, note=tax_note,
                              acq=t["total"], fee=sale_fee, interest=interest, cash=own_cash,
                              target=ss.c_target, max_bid=max_bid, table=rows_b)


# ───────────────────────── 인쇄용 보고서 ─────────────────────────

def build_report_html() -> str:
    from html import escape as e
    today = date.today().strftime("%Y.%m.%d")
    parts = [f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>빌라 시세조사 - {e(st.session_state.addr)}</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  /* 오래된 프린터에서도 잘 보이도록: 검정 글자, 굵게, 크게, 굵은 선, 회색 배경 없음 */
  * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; color: #000;
         font-size: 14px; font-weight: 700; line-height: 1.45; }}
  h1 {{ font-size: 24px; font-weight: 900; margin: 0 0 4px; }}
  h2 {{ font-size: 18px; font-weight: 900; margin: 20px 0 6px; border-bottom: 3px solid #000; padding-bottom: 3px; }}
  b {{ font-weight: 900; }}
  .muted {{ color: #000; }}
  .box {{ background: #fff; border: 2px solid #000; padding: 8px 10px; border-radius: 4px; margin: 6px 0; }}
  .warn {{ border-width: 3px; border-style: double; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1.5px solid #000; padding: 5px 6px; text-align: left; color: #000; }}
  th {{ background: #fff; font-weight: 900; }}
  td.num {{ text-align: right; }} tr {{ page-break-inside: avoid; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .grid div {{ border: 2px solid #000; padding: 6px; border-radius: 4px; }} .grid b {{ display: block; font-size: 17px; }}
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
    tp = report.get("temp")
    if tp:
        parts.append(f"<div class='box'>시장 온도: <b>{e(tp['label'])}</b> — 최근 3개월 거래 {tp['cnt']}건 "
                     f"({tp['c_chg']:+.0f}%), 평단가 {tp['ppy']:,.0f}만 ({tp['p_chg']:+.1f}%). {e(tp['text'])}</div>")

    bl = report.get("bld")
    if bl and (bl["rows"] or bl["checks"]):
        parts.append("<h2>건물 정보 (건축물대장)</h2><table>")
        for i in range(0, len(bl["rows"]), 2):
            pair = bl["rows"][i:i + 2]
            parts.append("<tr>" + "".join(f"<th>{e(k)}</th><td>{e(v)}</td>" for k, v in pair) + "</tr>")
        parts.append("</table>")
        for kind, msg in bl["checks"]:
            parts.append(f"<div class='box{' warn' if kind in ('warn', 'err') else ''}'>{e(msg)}</div>")

    r = report.get("est")
    if r:
        est = r["est"]
        parts.append(f"""<h2>예상 매도가 · 입찰가</h2>
<div class="grid"><div>예상 매도가<b>{won(r['sell'])}</b></div><div>적용 평단가<b>{r['ppy']:,.0f}만</b></div>
<div>평단가 범위(중간 50%)<b>{est['p25']:,.0f}–{est['p75']:,.0f}만</b></div><div>최대 입찰가<b>{won(r['bid'])}</b></div></div>
<div class="box">예상 매도가 {won(r['sell'])} − 수리비 {won(r['repair'])} − 부대비용 {won(r['extra'])} − 희망 차익 {won(r['profit'])}
= 최대 입찰가 {won(r['bid'])} (최저가 {won(min_bid)} 대비 {'+' if r['bid'] >= min_bid else '−'}{won(abs(r['bid'] - min_bid))})</div>""")
        if est["spread"] >= 2.0 or est["n_out"] > 0:
            parts.append(f"<div class='box warn'>평단가 편차 {est['spread']:.1f}배, 이상치 {est['n_out']}건 제외 "
                         f"(업계약 가능성 확인 필요)</div>")

    rr = report.get("rent")
    if rr:
        parts.append("<h2>전월세</h2><table>")
        if rr.get("j_price"):
            ratio = f"{rr['ratio'] * 100:.0f}%" if rr.get("ratio") else "-"
            parts.append(f"<tr><th>예상 전세가</th><td>{won(rr['j_price'])} (전세 {rr['nj']}건)</td>"
                         f"<th>전세가율</th><td>{ratio}</td></tr>"
                         f"<tr><th>전세 후 남는 투자금</th><td colspan='3'>{won(rr['left']) if rr['left'] > 0 else '회수 초과'}</td></tr>")
        if rr.get("rent_med") is not None:
            yld = f"{rr['yld']:.1f}%" if rr.get("yld") else "-"
            parts.append(f"<tr><th>월세 시세</th><td>{won(rr['dep_med'])} / {rr['rent_med']:,.0f}만 ({rr['nw']}건)</td>"
                         f"<th>월세 수익률</th><td>{yld}</td></tr>")
        parts.append("</table>")

    wx_r = report.get("weather")
    if wx_r:
        wd = ["월", "화", "수", "목", "금", "토", "일"]
        parts.append("<h2>임장 날씨 (7일)</h2><table><tr>" + "".join(
            f"<th>{pd.Timestamp(w['date']).month}/{pd.Timestamp(w['date']).day}"
            f"({wd[pd.Timestamp(w['date']).weekday()]})</th>" for w in wx_r) + "</tr><tr>" + "".join(
            f"<td style='text-align:center'>{w['icon']} {e(w['desc'])}<br>{w['tmax']:.0f}°/{w['tmin']:.0f}°<br>"
            f"☔{w['pop'] if w['pop'] is not None else '-'}%{' 👍' if w['good'] else ''}</td>" for w in wx_r)
            + "</tr></table>")
    fd = report.get("food")
    if fd:
        parts.append(f"<h2>식사·휴식 ({e(fd['base'])} {e(fd['kind'])})</h2><table>"
                     "<tr><th>이름</th><th>종류</th><th>거리</th><th>전화</th></tr>")
        for f in fd["rows"]:
            parts.append(f"<tr><td>{e(f['name'])}</td><td>{e(f['cat'])}</td>"
                         f"<td class='num'>{f['dist']:,}m</td><td>{e(f['phone'])}</td></tr>")
        parts.append("</table>")

    lc = report.get("loc")
    if lc:
        parts.append("<h2>입지</h2><table><tr><th>시설</th><th>이름</th><th>거리</th><th>도보</th><th>매수층</th></tr>")
        for r in lc["rows"]:
            parts.append(f"<tr><td>{e(r['시설'])}</td><td>{e(r['이름'])}</td><td class='num'>{e(r['거리'])}</td>"
                         f"<td class='num'>{e(r['도보'])}</td><td>{e(r['매수층'])}</td></tr>")
        parts.append("</table>")
        for f in lc["fits"]:
            parts.append(f"<div class='box'>{e(f)}</div>")

    ap_ = report.get("aphus")
    if ap_ and ap_.get("price"):
        parts.append(f"<h2>공시가격 ({ap_['year']}년)</h2><table>"
                     f"<tr><th>공시가격</th><td>{won(ap_['price'] / 1e4)}</td><th>1억 이하</th>"
                     f"<td>{'예 (취득세 중과 제외)' if ap_['price'] <= 1e8 else '아니오'}</td></tr>"
                     f"<tr><th>전세보증보험 한도</th><td>{won(ap_['cap'] / 1e4)}</td><th>기준</th><td>{e(ap_['how'])}</td></tr>"
                     f"</table>")

    ld_ = report.get("land")
    if ld_:
        parts.append(f"<h2>토지 정보 (공식)</h2><table>"
                     f"<tr><th>지형높이</th><td>{e(ld_['hg'])}</td><th>도로 접면</th><td>{e(ld_['rs'])}</td></tr>"
                     f"<tr><th>용도지역</th><td>{e(ld_['zone'])}</td><th>공시지가</th>"
                     f"<td>{ld_['price'] / 1e4:,.0f}만/㎡ (평당 {ld_['price'] * PYEONG / 1e4:,.0f}만)</td></tr>"
                     f"<tr><th>대지면적</th><td>{ld_['area']:,.1f}㎡</td><th>지형 형상</th><td>{e(ld_['shape'])}</td></tr>"
                     f"</table><div class='box'>{e(ld_['note'])}</div>")

    sp_ = report.get("slope")
    if sp_:
        parts.append("<h2>지형·경사</h2><table>")
        if sp_.get("h0") is not None:
            parts.append(f"<tr><th>물건 해발</th><td>{sp_['h0']:.0f}m</td><th>주변 지형</th><td>{e(sp_['terrain'])}</td></tr>")
        if sp_.get("start"):
            stp = f"출발 후 약 {sp_['steep_at']:,.0f}m부터 가파름" if sp_.get("steep_at") is not None else "큰 오르막 없음"
            parts.append(f"<tr><th>{e(sp_['start'])}에서</th><td>{sp_['climb']:+.0f}m (평균 {sp_['avg']:+.1f}%)</td>"
                         f"<th>가장 가파른 구간</th><td>{sp_['maxg']:+.1f}% · {e(stp)}</td></tr>")
        parts.append("</table>")

    lf = report.get("life")
    if lf:
        c = lf["cnt"]
        parts.append(f"<h2>생활권 (반경 {lf['radius']}m 상가)</h2><table><tr>" +
                     "".join(f"<th>{e(k)}</th>" for k in c) + "</tr><tr>" +
                     "".join(f"<td class='num'>{v:,}</td>" for v in c.values()) + "</tr></table>")
        parts.append(f"<div class='box'>상권 중심까지 약 {lf['hub_m']:,.0f}m</div>")
        for n_ in lf["notes"]:
            parts.append(f"<div class='box'>{e(n_)}</div>")

    cl = report.get("calc")
    if cl:
        parts.append(f"""<h2>경매 수익 계산 (어림)</h2><table>
<tr><th>매매 차익</th><td>{won(cl['gap'] / 1e4)}</td><th>세전 순이익</th><td>{won(cl['pre'] / 1e4)}</td></tr>
<tr><th>취득세 등</th><td>{cl['acq']:,.0f}원</td><th>매도 중개보수</th><td>{cl['fee']:,.0f}원</td></tr>
<tr><th>대출 이자</th><td>{cl['interest']:,.0f}원</td><th>세금</th><td>{cl['tax']:,.0f}원</td></tr>
<tr><th>세후 순이익</th><td><b>{won(cl['after'] / 1e4)}</b></td><th>필요 현금</th><td>{cl['cash']:,.0f}원</td></tr>
</table><div class='box'>{e(cl['note'])}. 법정 세율 기준 어림값이며 실제 세금은 세무사와 확인하세요.</div>""")
        if cl.get("table"):
            mb = f"최대 {won(cl['max_bid'] / 1e4)}" if cl.get("max_bid") else "달성 어려움"
            parts.append(f"<p><b>입찰가별 수익표</b> (목표 세후 {won(cl['target'])} → {mb})</p><table><tr>"
                         + "".join(f"<th>{e(k)}</th>" for k in cl["table"][0]) + "</tr>")
            for row in cl["table"]:
                parts.append("<tr>" + "".join(f"<td class='num'>{e(str(v))}</td>" for v in row.values()) + "</tr>")
            parts.append("</table>")

    rt = report.get("route")
    if rt:
        parts.append(f"<h2>임장 동선 · {e(rt['station'])} 출발</h2><table><tr><th>순서</th><th>방문지</th>"
                     f"<th>도보</th><th>확인</th></tr>")
        for i, name, m in rt["rows"]:
            last = rt["back"] and i == len(rt["rows"])
            parts.append(f"<tr><td class='num'>{'도착' if last else i}</td><td>{e(name)}</td>"
                         f"<td class='num'>약 {m / WALK_M_PER_MIN:.0f}분 ({m:,.0f}m)</td><td>☐</td></tr>")
        parts.append(f"</table><div class='box'>걷는 거리 약 {rt['total_m'] / 1000:.1f}km · "
                     f"확인 시간 포함 약 {int(rt['total_min'] // 60)}시간 {rt['total_min'] % 60:.0f}분</div>")

    show = report.get("comps")
    if show is not None and len(show):
        parts.append(f"<h2>비교사례 {len(show)}건 · 반경 {radius}m · 전용 ±{area_tol}평 · 연식 ±{age_tol}년</h2><table><tr>")
        cols = [("거래일", "거래일", ""), ("name", "건물명", ""), ("ho", "동·호", ""), ("jibun", "지번", ""),
                ("거리", "거리", "num"), ("전용평", "전용평", "num1"), ("build_year", "건축년도", "num0"),
                ("floor", "층", "num0"), ("금액", "금액", "num"), ("평단가", "평단가(만)", "numc")]
        parts.append("".join(f"<th>{h}</th>" for _, h, _ in cols) + "</tr>")
        for _, row in show.iterrows():
            cells = []
            for c, _, kind in cols:
                v = row.get(c, "")
                if kind == "num1":
                    txt = f"{v:.1f}"
                elif kind == "num0":
                    txt = "" if pd.isna(v) else f"{v:.0f}"
                elif kind == "numc":
                    txt = f"{v:,}"
                else:
                    txt = e(str(v))
                cells.append(f"<td class='num'>{txt}</td>" if kind else f"<td>{txt}</td>")
            parts.append("<tr>" + "".join(cells) + "</tr>")
        parts.append("</table>")
    ck = report.get("ck")
    if ck is not None:
        parts.append("<h2>임장 체크리스트</h2>")
        for m in ck["focus"]:
            parts.append(f"<div class='box warn'>{e(m)}</div>")
        for section, items in CHECKLIST:
            parts.append(f"<p style='margin:8px 0 2px'><b>{e(section)}</b></p>")
            for cid, text in items:
                mark = "☑" if cid in ck["done"] else "☐"
                parts.append(f"<div style='margin:2px 0 2px 8px'>{mark} {e(text)}</div>")
    parts.append("</body></html>")
    return "".join(parts)


report_html = build_report_html()
with print_slot:
    p1, p2, _ = st.columns([1, 1, 3])
    with p1:
        import streamlit.components.v1 as components
        components.html(f"""
<style>html,body{{margin:0;padding:0;background:transparent}}
#pbtn{{width:100%;height:40px;border:1px solid rgba(49,51,63,.2);border-radius:8px;background:#fff;color:#31333f;
  font-size:14px;cursor:pointer;font-family:"Source Sans Pro",sans-serif;box-sizing:border-box}}
#pbtn:hover{{border-color:#ff4b4b;color:#ff4b4b}}</style>
<button id="pbtn">🖨️ 인쇄</button>
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
</script>""", height=40)
    with p2:
        st.download_button("보고서 저장 (HTML)", report_html.encode("utf-8"),
                           file_name=f"빌라시세_{dong}_{date.today():%Y%m%d}.html",
                           mime="text/html", use_container_width=True)


# ───────────────────────── 현재 상태를 주소창에 기록 ─────────────────────────
# 새로고침하거나 홈 화면 아이콘으로 열어도 같은 화면으로 복원됨
ss = st.session_state
st.query_params.update({
    "addr": ss.addr, "area": f"{area_m2:g}", "year": str(build_year), "floor": str(floor),
    "bid": str(min_bid), "ho": ss.get("w_ho", ""), "m": str(months), "r": str(radius), "at": str(area_tol), "yt": str(age_tol),
    "dong": dong, "sel": ",".join(sorted(ss.get("sel_cur", set()))),
    "ck": ",".join(sorted(ss.get("ck_done", set()))),
    **{k: ("1" if v else "0") if isinstance(v, bool) else str(v)
       for k, v in ss.items() if isinstance(k, str) and k.startswith("c_")},
    "it": "1" if ss.get("w_it", True) else "0", "bk": "1" if ss.get("w_bk", True) else "0",
    "stn": str(ss.get("w_stn", 0)), "mv": "1" if ss.get("w_mv") else "0",
    "fk": ss.get("w_fk", "음식점"), "fb": ss.get("w_fb", "경매 물건 주변"),
    "tab": ss.get("w_tab") or ss.get("_last_tab", "동네 프로필"), "mode": "물건 분석", "sr": str(ss.get("w_sr", 500)), "slp": ss.get("w_slp", "지하철역"),
    "rp": str(ss.get("w_rp", 500)), "ex": str(ss.get("w_ex", 400)), "pf": str(ss.get("w_pf", 2500)),
    **({"ppy": str(ss["w_ppy"])} if "w_ppy" in ss else {}),
})
push_recent({k: st.query_params.get(k) for k in st.query_params.keys()})
