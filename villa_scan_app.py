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
        ("p6", "비교사례 중 임장할 곳을 체크해 동선 짜기 (비교 평가 2~3곳)"),
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
        ("n3", "같은 골목 비교 매물 2~3곳과 외관·층·주차 비교"),
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
- **세후 수익은 역산한다.** 매매사업자 6~15% 구간 기준 대략 차익 2,500만 → 세후 1천만, 4,000만 → 2천만, 5,000만 → 3천만 정도입니다(강의 기준 어림값, 실제 세율로 다시 계산).
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
        rate, why = basic(), "일반세율(1~3%)"
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


# 리셋 직후: 브라우저에 기억한 탭 위치도 지움
if st.session_state.pop("_reset", False):
    components.html("<script>try{localStorage.removeItem('villa_tab');window.parent.__villaRestored=false;}catch(e){}</script>",
                    height=0)


with st.sidebar:
    st.subheader("API 키")
    data_key = st.text_input("공공데이터포털 인증키", type="password",
                             value=secret("DATA_GO_KR_KEY"))
    kakao_key = st.text_input("카카오 REST API 키", type="password",
                              value=secret("KAKAO_REST_KEY"))

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
    run = st.button("시세 조회", type="primary", use_container_width=True)
    st.button("처음부터 다시 (리셋)", on_click=reset_all, use_container_width=True,
              help="입력값, 선택한 임장지, 조정한 값을 모두 지우고 새로 시작합니다.")

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
                         "승인 직후라면 키가 반영되기까지 1~2시간 걸릴 수 있습니다.")
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
if qp.get("dong") in dongs:
    guess = qp.get("dong")
if st.session_state.get("w_dong") not in dongs:
    st.session_state["w_dong"] = guess
dong = st.selectbox("동네", dongs, key="w_dong")

dong_df = trades[trades["dong"] == dong]
print_slot = st.container()

# 마지막으로 보던 탭을 기억했다가 새로고침 후 다시 열어 줌
components.html("""<script>
(function () {
  const KEY = 'villa_tab';
  let doc; try { doc = window.parent.document; } catch (e) { return; }
  function setup(tries) {
    const tabs = [...doc.querySelectorAll('button[role="tab"]')];
    if (!tabs.length) { if (tries < 40) setTimeout(() => setup(tries + 1), 150); return; }
    tabs.forEach(t => { if (!t.dataset.vs) { t.dataset.vs = 1;
      t.addEventListener('click', () => localStorage.setItem(KEY, t.innerText.trim())); } });
    if (!window.parent.__villaRestored) {
      window.parent.__villaRestored = true;
      const want = localStorage.getItem(KEY);
      const b = tabs.find(t => t.innerText.trim() === want);
      if (b && b.getAttribute('aria-selected') !== 'true') b.click();
    }
  }
  setup(0);
  // 화면이 다시 그려져 탭 버튼이 새로 생겨도 클릭을 계속 기억하도록
  setInterval(() => { [...doc.querySelectorAll('button[role="tab"]')].forEach(t => {
    if (!t.dataset.vs) { t.dataset.vs = 1;
      t.addEventListener('click', () => localStorage.setItem(KEY, t.innerText.trim())); } }); }, 1000);
})();
</script>""", height=0)
report = {"fit": [], "verdict": "", "comps": None, "est": None, "route": None, "bld": None, "ck": None,
          "calc": None}

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["동네 프로필", "비교사례", "예상 매도가", "건물 정보", "임장 체크", "계산기"])

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
        pos = list(ed_df.columns).index("동·호") + 1
        ed_df.insert(pos, "지도", [kakao_map_link(n, a, o) for n, a, o in
                                   zip(comps["name"], comps["lat"], comps["lon"])])
        ed_df.insert(pos + 1, "로드뷰", [kakao_roadview_link(a, o) for a, o in zip(comps["lat"], comps["lon"])])
        edited = st.data_editor(
            ed_df, key=ed_key, hide_index=True, use_container_width=True,
            disabled=[c for c in ed_df.columns if c != "임장"],
            column_config={
                "임장": st.column_config.CheckboxColumn("임장", width="small"),
                "지도": st.column_config.LinkColumn("지도", display_text="카카오맵", width="small"),
                "로드뷰": st.column_config.LinkColumn("로드뷰", display_text="보기", width="small"),
            })
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
            lines = [f"🚇 **출발** {station['name']}"]
            for i, (a, b, m) in enumerate(zip(pts, pts[1:], legs), start=1):
                to = f"**{i}. {b['name']}**" if i <= len(route) else f"🚇 **도착** {b['name']}"
                lines.append(f"{to} — 도보 약 {m / WALK_M_PER_MIN:.0f}분 ({m:,.0f}m) · "
                             f"[길찾기]({kakao_route_link(a, b)})")
            st.markdown("  \n".join(lines))
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
            st.markdown(f"경매 물건: [카카오맵에서 보기]({kakao_map_link('경매 물건', lat0, lon0)}) · "
                        f"[로드뷰]({kakao_roadview_link(lat0, lon0)})")
            move = st.toggle("지도 움직이기 (확대·이동)", key="w_mv",
                             help="끄면 지도 위에서 손가락으로 화면을 스크롤할 수 있습니다.")
            deck.views = [pdk.View(type="MapView", controller=True if move else False)]
            try:
                st.pydeck_chart(deck, use_container_width=True, height=380 if move else 300)
            except TypeError:  # 구버전 streamlit
                st.pydeck_chart(deck, use_container_width=True)
            st.caption("빨간 테두리: 경매 물건 · 파란 점: 최근 거래(클수록 거래 많음) · 노란 점: 선택한 임장지 · "
                       "초록: 출발역과 동선. 점을 누르면 건물명과 거래 내역이 보입니다.")

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
        b.metric("평단가 범위 (중간 50%)", f"{est['p25']:,.0f}~{est['p75']:,.0f}만")
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



# ── 건물 정보 (건축물대장)
def ymd(v: str) -> str:
    return f"{v[:4]}.{v[4:6]}.{v[6:8]}" if v and len(v) == 8 and v.isdigit() else "-"


def to_num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


with tab4:
    with st.expander("빌라 경매에서 건물 정보를 보는 법"):
        st.markdown(
            "- **근생빌라 여부**: 건축물대장 전유부에 호실별 용도가 나옵니다. 서류상 '제2종근린생활시설'인데 "
            "주거로 쓰는 호실이면 대출이 잘 안 나오고 이행강제금 위험이 있습니다.\n"
            "- **건물 기본 정보(표제부)**: 사용승인일, 구조(철근콘크리트·벽돌 등), 세대수, 층수, 엘리베이터 수, "
            "주차대수, 대지면적과 용적률이 나옵니다. \"주차 자리가 있나\", \"엘리베이터가 있나\"처럼 "
            "누구에게 팔지 판단할 때 필요한 정보입니다.\n"
            "- **위반건축물 여부**: 건축물대장 API의 표제부에는 위반 여부 항목이 없습니다. 정부24에서 "
            "건축물대장을 떼어 첫 장 오른쪽 위의 '위반건축물' 표시를 확인하는 게 확실하고, "
            "매각물건명세서 비고란도 함께 보세요."
        )
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
                    bld["checks"].append(("warn", f"세대당 주차 {park / hh:.1f}대로 부족한 편입니다. 차가 있는 3~4인 가구에는 팔기 어려울 수 있습니다."))
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
        "c_over85": area_m2 > 85, "c_corp": False, "c_low": False,
        "c_loan": 0, "c_irate": 4.5, "c_months": 6, "c_method": "원리금균등",
        "c_bid": max(0, int(r_est.get("bid", min_bid) or min_bid)),
        "c_sell": max(0, int(r_est.get("sell", min_bid * 1.4))),
        "c_repair": int(ss.get("w_rp", 500)), "c_evict": 100, "c_etc": 100,
        "c_taxmode": "매매사업자(종합소득세)",
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
        t = acq_tax(bid_w, ss.c_houses, ss.c_adj, area_m2 > 85, False, ss.c_low)
        sale_fee = brokerage_fee(sell_w, FEE_SALE)[0] * 1.1      # 부가세 포함
        interest = ss.c_loan * 1e4 * ss.c_irate / 100 / 12 * ss.c_months
        costs = t["total"] + (ss.c_repair + ss.c_evict + ss.c_etc) * 1e4 + sale_fee + interest
        gap = sell_w - bid_w
        pre_tax = gap - costs
        if ss.c_taxmode.startswith("매매사업자"):
            tax = progressive_tax(pre_tax) * 1.1                  # 지방소득세 10% 포함
            tax_note = "다른 소득이 없다고 보고 종합소득세 기본세율(6~45%)과 지방소득세를 적용"
        else:
            base = max(pre_tax - interest - 2.5e6, 0)            # 양도세는 대출이자를 필요경비로 인정 안 함
            if ss.c_months < 12:
                tax, tax_note = base * 0.70 * 1.1, "1년 미만 보유 주택 70% + 지방세"
            elif ss.c_months < 24:
                tax, tax_note = base * 0.60 * 1.1, "2년 미만 보유 주택 60% + 지방세"
            else:
                tax, tax_note = progressive_tax(base) * 1.1, "2년 이상 보유, 기본세율 + 지방세"
        after = pre_tax - tax
        own_cash = bid_w + costs - sale_fee - interest - ss.c_loan * 1e4
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
        report["calc"] = dict(gap=gap, pre=pre_tax, after=after, tax=tax, note=tax_note,
                              acq=t["total"], fee=sale_fee, interest=interest, cash=own_cash)


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
<div>평단가 범위(중간 50%)<b>{est['p25']:,.0f}~{est['p75']:,.0f}만</b></div><div>최대 입찰가<b>{won(r['bid'])}</b></div></div>
<div class="box">예상 매도가 {won(r['sell'])} − 수리비 {won(r['repair'])} − 부대비용 {won(r['extra'])} − 희망 차익 {won(r['profit'])}
= 최대 입찰가 {won(r['bid'])} (최저가 {won(min_bid)} 대비 {'+' if r['bid'] >= min_bid else '−'}{won(abs(r['bid'] - min_bid))})</div>""")
        if est["spread"] >= 2.0 or est["n_out"] > 0:
            parts.append(f"<div class='box warn'>평단가 편차 {est['spread']:.1f}배, 이상치 {est['n_out']}건 제외 "
                         f"(업계약 가능성 확인 필요)</div>")

    cl = report.get("calc")
    if cl:
        parts.append(f"""<h2>경매 수익 계산 (어림)</h2><table>
<tr><th>매매 차익</th><td>{won(cl['gap'] / 1e4)}</td><th>세전 순이익</th><td>{won(cl['pre'] / 1e4)}</td></tr>
<tr><th>취득세 등</th><td>{cl['acq']:,.0f}원</td><th>매도 중개보수</th><td>{cl['fee']:,.0f}원</td></tr>
<tr><th>대출 이자</th><td>{cl['interest']:,.0f}원</td><th>세금</th><td>{cl['tax']:,.0f}원</td></tr>
<tr><th>세후 순이익</th><td><b>{won(cl['after'] / 1e4)}</b></td><th>필요 현금</th><td>{cl['cash']:,.0f}원</td></tr>
</table><div class='box'>{e(cl['note'])}. 법정 세율 기준 어림값이며 실제 세금은 세무사와 확인하세요.</div>""")

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
    "rp": str(ss.get("w_rp", 500)), "ex": str(ss.get("w_ex", 400)), "pf": str(ss.get("w_pf", 2500)),
    **({"ppy": str(ss["w_ppy"])} if "w_ppy" in ss else {}),
})
