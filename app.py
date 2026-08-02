import os
import json
import math
import time
import uuid
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

import requests
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from groq import Groq
except ImportError:
    Groq = None

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# ── 付費 / 帳號相關設定 ───────────────────────────────────────
ECPAY_MERCHANT_ID = os.environ.get("ECPAY_MERCHANT_ID", "2000132")   # 測試用預設
ECPAY_HASH_KEY    = os.environ.get("ECPAY_HASH_KEY",    "5294y06JbISpM5x9")
ECPAY_HASH_IV     = os.environ.get("ECPAY_HASH_IV",     "v77hoKGq4kWxNNIS")
ECPAY_IS_TEST     = os.environ.get("ECPAY_IS_TEST", "1") == "1"
USERS_FILE        = os.path.join(os.path.dirname(__file__), "users.json")
MAP_STATIC_FILE   = os.path.join(os.path.dirname(__file__), "map_static_cache.json")

# ── 環境變數 / 認證資訊 ───────────────────────────────────
app_id = os.environ.get("CLIENT_ID")
app_key = os.environ.get("CLIENT_SECRET")
groq_api_key = os.environ.get("GROQ_API_KEY")

client = None
if Groq and groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception:
        client = None
        print("找不到 GROQ_API_KEY，AI 功能將受限。")
else:
    print("找不到 GROQ_API_KEY，AI 功能將受限。")

AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TAINAN_LAT, TAINAN_LON = 22.9997, 120.2270
UBIKE_SPEED_KMH = 15  # 估算騎車速度（OSRM 失敗時備用）
CACHE_FILE = os.path.join(os.path.dirname(__file__), "tainan_stops_cache.json")

# ── 常數與對照表（與原始 Streamlit 版本完全一致） ─────────
ROUTE_CATEGORIES = {
    "黃線": ["黃幹線", "黃1", "黃2", "黃3", "黃4", "黃5", "黃6", "黃6-1", "黃7", "黃9", "黃10", "黃11", "黃11-1", "黃12", "黃13", "黃14", "黃14-1", "黃15", "黃16", "黃20", "黃22", "黃23", "黃24", "黃25"],
    "棕線": ["棕幹線", "棕1", "棕2", "棕3", "棕3-1", "棕4", "棕5", "棕6", "棕20", "棕10", "棕11"],
    "綠線": ["綠幹線", "綠1", "綠2", "綠2-1", "綠3", "綠4", "綠5", "綠6", "綠7", "綠10", "綠11", "綠12", "綠12-1", "綠12-2", "綠13", "綠14", "綠15", "綠16", "綠17", "綠20", "綠20-1", "綠21", "綠22", "綠23", "綠24", "綠25", "綠26", "綠27", "綠28", "綠29", "綠30", "綠30-1", "綠31", "綠32"],
    "橘線": ["橘幹線", "橘1", "橘2", "橘3", "橘4", "橘4-1", "橘5", "橘6", "橘9", "橘9-1", "橘10", "橘10-1", "橘11", "橘11-1", "橘12", "橘13", "橘14", "橘20"],
    "藍線": ["藍幹線", "藍1", "藍2", "藍3", "藍4", "藍10", "藍11", "藍13", "藍14", "藍15", "藍20", "藍21", "藍22", "藍23", "藍24", "藍25", "藍26", "藍27", "藍28", "藍29", "藍30"],
    "紅線": ["紅幹線", "紅1", "紅2", "紅3", "紅4", "紅10", "紅11", "紅12", "紅13", "紅14"],
    "市區": ["0左", "0右", "6", "7", "9", "10", "11", "14", "15", "18", "19", "20", "21", "31", "32", "33", "62", "70左", "70右", "77", "98", "101", "102", "103", "107", "111", "168", "901", "902", "904", "905"],
    "高鐵快捷": ["H31"],
    "觀光": ["東山咖啡線", "梅嶺線", "菱波官田線", "雙層巴士"]
}

ROUTE_COLOR_MAP = {
    "黃": "#F1C40F", "棕": "#8B4513", "綠": "#27AE60", "橘": "#E67E22",
    "藍": "#2980B9", "紅": "#E74C3C", "H": "#9B59B6",
    "0": "#1ABC9C",
    "6": "#E91E63", "7": "#E91E63", "9": "#E91E63",
    "10": "#FF5722", "11": "#FF5722", "14": "#FF5722", "15": "#FF5722",
    "18": "#FF9800", "19": "#FF9800", "20": "#FF9800", "21": "#FF9800",
    "31": "#795548", "32": "#795548", "33": "#795548",
    "62": "#607D8B", "70": "#3F51B5", "77": "#009688", "98": "#F44336",
    "101": "#673AB7", "102": "#673AB7", "103": "#673AB7", "107": "#673AB7",
    "111": "#00BCD4", "168": "#00BCD4",
    "901": "#8BC34A", "902": "#8BC34A", "904": "#8BC34A", "905": "#8BC34A",
    "東山": "#FF6F00", "梅嶺": "#AD1457", "菱波": "#00838F", "雙層": "#BF360C",
}

INTERCITY_OPERATORS = {
    "（請選擇）": None,
    "統聯客運": "851",
    "國光客運": "805",
    "和欣客運": "822",
    "阿羅哈客運": "826",
    "嘉義客運": "602",
    "台南客運": "646",
    "興南客運": "647",
    "新營客運": "648",
    "豐原客運": "717",
    "中壢客運": "719",
}

# ── in-memory 快取（等同於 st.cache_data）────────────────
_cache_store = {}


def cached(ttl_seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            hit = _cache_store.get(key)
            if hit and time.time() - hit["time"] < ttl_seconds:
                return hit["data"]
            result = func(*args, **kwargs)
            _cache_store[key] = {"time": time.time(), "data": result}
            return result
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


# ── in-memory 使用者 session store（等同於 st.session_state）──
SESSION_STORE = {}


def get_uid():
    if "uid" not in session:
        session["uid"] = str(uuid.uuid4())
    uid = session["uid"]
    if uid not in SESSION_STORE:
        SESSION_STORE[uid] = {
            "recent_routes": [],
            "favorite_routes": [],
            "chat_sessions": {},
            "current_session_id": None,
            "current_weather": "尚未查詢",
            "bus_status": "尚未查詢路線",
        }
    return uid


def get_state():
    return SESSION_STORE[get_uid()]


# ── 基礎工具 ──────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def get_route_color(route_name):
    for prefix in sorted(ROUTE_COLOR_MAP.keys(), key=len, reverse=True):
        if route_name.startswith(prefix):
            return ROUTE_COLOR_MAP[prefix]
    return "#7F8C8D"


def get_osrm_travel_time(start_lat, start_lon, end_lat, end_lon, mode="bike"):
    try:
        url = (f"http://router.project-osrm.org/route/v1/{mode}/"
               f"{start_lon},{start_lat};{end_lon},{end_lat}?overview=false")
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            route = res.json()["routes"][0]
            dist_m = route["distance"]
            dur_min = round(route["duration"] / 60)
            dist_text = f"{round(dist_m/1000,1)} 公里" if dist_m >= 1000 else f"{round(dist_m)} 公尺"
            return dist_text, dur_min
    except Exception:
        pass
    return None, None


def parse_wkt_linestring(geo):
    points = []
    try:
        coords_str = geo.replace("LINESTRING (", "").replace("LINESTRING(", "").replace(")", "")
        for pair in coords_str.split(","):
            parts = pair.strip().split()
            if len(parts) >= 2:
                points.append([float(parts[1]), float(parts[0])])
    except Exception:
        pass
    return points


def add_recent_route(state, route):
    lst = state["recent_routes"]
    if route in lst:
        lst.remove(route)
    lst.insert(0, route)
    state["recent_routes"] = lst[:5]


def new_chat_session(state):
    sid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    state["chat_sessions"][sid] = {
        "title": f"對話 {datetime.now().strftime('%m/%d %H:%M')}",
        "history": []
    }
    state["current_session_id"] = sid
    return sid


# ── TDX 認證 ──────────────────────────────────────────────
@cached(3600)
def get_tdx_token():
    try:
        res = requests.post(AUTH_URL, data={
            'content-type': 'application/x-www-form-urlencoded',
            'grant_type': 'client_credentials',
            'client_id': app_id,
            'client_secret': app_key
        }, timeout=10)
        return res.json().get("access_token", "")
    except Exception:
        return ""


def tdx_headers():
    return {'authorization': f'Bearer {get_tdx_token()}', 'Accept-Encoding': 'gzip'}


# ── TDX / 第三方資料存取（皆對應原本 st.cache_data 函數）───
@cached(3600)
def fetch_route_stops(route_name):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            c = json.load(f)
            if route_name in c and c[route_name]:
                return c[route_name]
    except FileNotFoundError:
        pass
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data:
                return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except Exception:
        pass
    return []


@cached(30)
def fetch_bus_data(route_name):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


@cached(600)
def fetch_weather():
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={TAINAN_LAT}&longitude={TAINAN_LON}"
               f"&current=temperature_2m,weathercode,windspeed_10m&timezone=Asia%2FTaipei")
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            cur = res.json().get("current", {})
            temp = cur.get("temperature_2m", "?")
            wind = cur.get("windspeed_10m", "?")
            wmap = {0: "晴天☀️", 1: "大致晴朗🌤️", 2: "部分多雲⛅", 3: "陰天☁️", 45: "有霧🌫️",
                     51: "毛毛雨🌦️", 61: "小雨🌧️", 63: "中雨🌧️", 65: "大雨🌧️", 80: "陣雨🌦️", 95: "雷雨⛈️"}
            desc = wmap.get(cur.get("weathercode", -1), "未知天氣")
            return f"{desc}，氣溫 {temp}°C，風速 {wind} km/h"
    except Exception:
        pass
    return "無法取得天氣"


@cached(60)
def fetch_ubike_all():
    stations, avail_map = [], {}
    try:
        r1 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Tainan?%24format=JSON",
                           headers=tdx_headers(), timeout=8)
        r2 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Tainan?%24format=JSON",
                           headers=tdx_headers(), timeout=8)
        if r1.status_code == 200:
            stations = r1.json()
        if r2.status_code == 200:
            for av in r2.json():
                avail_map[av["StationUID"]] = av
    except Exception:
        pass
    return stations, avail_map


@cached(300)
def fetch_all_bus_stops():
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


@cached(3600)
def fetch_route_shape(route_name):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Shape/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def fetch_bus_realtime_positions(route_name=None):
    if route_name:
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeByFrequency/City/Tainan/{route_name}?%24format=JSON"
    else:
        url = "https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeByFrequency/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def find_nearby_stops(all_stops, lat, lon, radius_km=0.5):
    nearby, seen = [], set()
    for stop in all_stops:
        pos = stop.get("StopPosition", {})
        s_lat, s_lon = pos.get("PositionLat"), pos.get("PositionLon")
        name = stop.get("StopName", {}).get("Zh_tw", "")
        if s_lat and s_lon and name and name not in seen:
            dist = haversine(lat, lon, s_lat, s_lon)
            if dist <= radius_km:
                seen.add(name)
                nearby.append({"name": name, "dist": dist})
    nearby.sort(key=lambda x: x["dist"])
    return nearby[:15]


def get_ubike_near(s_lat, s_lon, stations, avail_map, radius_km=0.3):
    result = []
    for ub in stations:
        pos = ub.get("StationPosition", {})
        u_lat, u_lon = pos.get("PositionLat"), pos.get("PositionLon")
        if u_lat and u_lon and haversine(s_lat, s_lon, u_lat, u_lon) <= radius_km:
            uid = ub.get("StationUID", "")
            av = avail_map.get(uid, {})
            result.append({
                "name": ub.get("StationName", {}).get("Zh_tw", ""),
                "available": av.get("AvailableRentBikes", 0),
                "empty": av.get("AvailableReturnBikes", 0),
                "lat": u_lat, "lon": u_lon
            })
    return result


# ── 進階路線查詢：直達 + 一次轉乘 ───────────────────────────
@cached(3600)
def build_stop_route_index():
    index = {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        for route_name, stops in cache.items():
            for stop in stops:
                if stop not in index:
                    index[stop] = []
                if route_name not in index[stop]:
                    index[stop].append(route_name)
    except FileNotFoundError:
        pass
    return index


def find_direct_routes(stop_index, start_stop, end_stop):
    start_routes = set(stop_index.get(start_stop, []))
    end_routes = set(stop_index.get(end_stop, []))
    return sorted(start_routes & end_routes)


def find_transfer_routes(stop_index, start_stop, end_stop, max_results=10):
    start_routes = stop_index.get(start_stop, [])
    end_routes = stop_index.get(end_stop, [])

    start_route_stops = {}
    for r in start_routes:
        for stop, routes in stop_index.items():
            if r in routes:
                start_route_stops.setdefault(r, set()).add(stop)

    end_route_stops = {}
    for r in end_routes:
        for stop, routes in stop_index.items():
            if r in routes:
                end_route_stops.setdefault(r, set()).add(stop)

    results = []
    for rA, stopsA in start_route_stops.items():
        for rB, stopsB in end_route_stops.items():
            if rA == rB:
                continue
            transfer_stops = stopsA & stopsB
            if transfer_stops:
                for ts in sorted(transfer_stops)[:3]:
                    results.append({"routeA": rA, "transfer": ts, "routeB": rB})
                    if len(results) >= max_results:
                        return results
    return results


# ── UBike 騎車建議 ────────────────────────────────────────
def check_ubike_suggestion(start_st, end_st, stop_coord_map, ub_stations, ub_avail, bus_wait_sec, bus_travel_sec):
    if start_st not in stop_coord_map or end_st not in stop_coord_map:
        return None
    s_lat, s_lon = stop_coord_map[start_st]
    e_lat, e_lon = stop_coord_map[end_st]

    start_ub = [u for u in get_ubike_near(s_lat, s_lon, ub_stations, ub_avail, 0.4) if u["available"] > 0]
    end_ub = [u for u in get_ubike_near(e_lat, e_lon, ub_stations, ub_avail, 0.4) if u["empty"] > 0]

    if not start_ub or not end_ub:
        return None

    dist_text, bike_min = get_osrm_travel_time(s_lat, s_lon, e_lat, e_lon, mode="bike")
    if bike_min is None:
        dist_km = haversine(s_lat, s_lon, e_lat, e_lon)
        bike_min = (dist_km / UBIKE_SPEED_KMH) * 60
        dist_text = f"{dist_km:.1f} 公里（直線估算）"

    bus_total_min = (bus_wait_sec + bus_travel_sec) / 60

    if bike_min < bus_total_min * 0.85:
        best_start = start_ub[0]
        best_end = end_ub[0]
        return (
            f"🚲 UBike 更快！實際騎車約 {bike_min} 分鐘（{dist_text}），"
            f"比等公車+搭車（約 {bus_total_min:.0f} 分鐘）更省時。\n"
            f"- 起點 UBike：{best_start['name']}（可借 {best_start['available']} 輛）\n"
            f"- 終點 UBike：{best_end['name']}（可還 {best_end['empty']} 格）"
        )
    return None


def eta_status_text(eta, status):
    """對應原本時間軸上的狀態文字與 badge 樣式"""
    if eta is not None and status == 0:
        if eta <= 120:
            return "即將進站", "ts-orange"
        return f"{eta // 60} 分鐘", "ts-green"
    elif status == 1:
        return "尚未發車", "ts-gray"
    elif status == 2:
        return "交管不停靠", "ts-gray"
    elif status == 3:
        return "末班車已過", "ts-red"
    elif status == 4:
        return "今日停駛", "ts-red"
    return "尚未發車", "ts-gray"


# ══════════════════════════════════════════════════════════
# 頁面路由
# ══════════════════════════════════════════════════════════
@app.route('/')
def index():
    get_uid()
    return render_template('index.html',
                            route_categories=ROUTE_CATEGORIES,
                            intercity_operators=INTERCITY_OPERATORS)


# ══════════════════════════════════════════════════════════
# API：基礎資料
# ══════════════════════════════════════════════════════════
@app.route('/api/weather')
def api_weather():
    w = fetch_weather()
    get_state()["current_weather"] = w
    return jsonify({"weather": w})


@app.route('/api/route_categories')
def api_route_categories():
    return jsonify({"categories": ROUTE_CATEGORIES, "colors": ROUTE_COLOR_MAP})


@app.route('/api/filter_routes')
def api_filter_routes():
    cf = request.args.get('filter', '').strip()
    all_routes = []
    for rl in ROUTE_CATEGORIES.values():
        all_routes.extend(rl)
    seen_s = set()
    all_routes = [x for x in all_routes if not (x in seen_s or seen_s.add(x))]

    if not cf:
        filtered = all_routes
    elif cf == "市區":
        filtered = ROUTE_CATEGORIES["市區"]
    elif cf == "高鐵":
        filtered = ROUTE_CATEGORIES["高鐵快捷"]
    elif cf == "觀光":
        filtered = ROUTE_CATEGORIES["觀光"]
    else:
        raw = [r for r in all_routes if cf in r]
        if cf.isdigit():
            def nsort(rs):
                nums = ''.join(c for c in rs if c.isdigit())
                return (0 if rs.startswith(cf) else 1, int(nums) if nums else 999, rs)
            filtered = sorted(raw, key=nsort)
        else:
            filtered = raw
    return jsonify({"routes": filtered})


@app.route('/api/route_stops')
def api_route_stops():
    route = request.args.get('route', '')
    if not route:
        return jsonify({"stops": []})
    stops = fetch_route_stops(route)
    state = get_state()
    add_recent_route(state, route)
    return jsonify({"stops": stops})


@app.route('/api/route_status')
def api_route_status():
    route = request.args.get('route', '')
    direction = request.args.get('direction', '去程')
    start_st = request.args.get('start_st') or None
    end_st = request.args.get('end_st') or None
    if not route:
        return jsonify({"error": "缺少路線"}), 400

    state = get_state()
    weather_info = fetch_weather()
    state["current_weather"] = weather_info

    bus_list = fetch_bus_data(route)
    if bus_list is None:
        return jsonify({"error": "無法取得即時動態"}), 502

    dir0 = sorted([x for x in bus_list if x.get("Direction") == 0], key=lambda x: x.get('StopSequence', 0))
    dir1 = sorted([x for x in bus_list if x.get("Direction") == 1], key=lambda x: x.get('StopSequence', 0))
    dest_0 = dir0[-1].get("StopName", {}).get("Zh_tw", "去程") if dir0 else "去程"
    dest_1 = dir1[-1].get("StopName", {}).get("Zh_tw", "回程") if dir1 else "回程"

    active_list = dir0 if direction == "去程" else dir1
    target_dir = 0 if direction == "去程" else 1

    # 站點座標
    stop_coord_map = {}
    try:
        cr = requests.get(
            f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route}?%24format=JSON",
            headers=tdx_headers(), timeout=8)
        if cr.status_code == 200:
            for rd in cr.json():
                if rd.get("Direction") == target_dir:
                    for s in rd.get("Stops", []):
                        name = s.get("StopName", {}).get("Zh_tw", "")
                        pos = s.get("StopPosition", {})
                        if name and pos.get("PositionLat"):
                            stop_coord_map[name] = (pos["PositionLat"], pos["PositionLon"])
    except Exception:
        pass

    ub_stations, ub_avail = fetch_ubike_all()
    realtime_map = {item.get("StopName", {}).get("Zh_tw", ""): item for item in active_list}
    all_stops_raw = fetch_route_stops(route)
    full_stop_list = all_stops_raw or [item.get("StopName", {}).get("Zh_tw", "") for item in active_list]

    if not full_stop_list:
        return jsonify({"dest0": dest_0, "dest1": dest_1, "stops": [], "empty": True})

    # UBike 建議
    ubike_suggestion = None
    if start_st and end_st and start_st != end_st:
        start_item = realtime_map.get(start_st, {})
        bus_wait = start_item.get("EstimateTime") or 0
        if start_st in full_stop_list and end_st in full_stop_list:
            idx_s = full_stop_list.index(start_st)
            idx_e = full_stop_list.index(end_st)
            bus_travel = abs(idx_e - idx_s) * 120
        else:
            bus_travel = 600
        ubike_suggestion = check_ubike_suggestion(
            start_st, end_st, stop_coord_map, ub_stations, ub_avail, bus_wait, bus_travel)

    tts_lines = [f"路線 {route}，往 {dest_0 if direction == '去程' else dest_1}方向。"]
    stops_out = []
    ai_log_list = []
    seen_plates = set()  # 用來讓同一輛實體公車只在最接近的站顯示一次（依目前位置單一顯示）

    for s_name in full_stop_list:
        item = realtime_map.get(s_name, {})
        eta = item.get("EstimateTime")
        status = item.get("StopStatus", 1)
        plate = item.get("PlateNumb", "")
        v_type = item.get("VehicleType")
        is_ev = item.get("IsElectric", False) or (v_type == 5)

        # 無障礙判斷（大巴預設有，小巴/中巴看 IsLowFloor）
        if v_type == 1:
            is_low, car_size = True, "大巴"
        elif v_type == 2:
            is_low, car_size = item.get("IsLowFloor", False), "中巴"
        elif v_type == 3:
            is_low, car_size = item.get("IsLowFloor", False), "小巴"
        else:
            is_low, car_size = item.get("IsLowFloor", False), "大巴"

        time_text, badge_class = eta_status_text(eta, status)

        ubikes_near = []
        if s_name in stop_coord_map:
            s_lat, s_lon = stop_coord_map[s_name]
            for ub in get_ubike_near(s_lat, s_lon, ub_stations, ub_avail):
                ubikes_near.append(ub)

        raw_has_bus = bool(plate) and plate not in ("🧱", "無車牌")
        # 同一車牌只在最先出現（也就是離該車目前位置最近）的站顯示公車標籤，
        # 避免同一輛車因為連續多站都被列為「下一班」而重複顯示。
        show_bus_tag = False
        if raw_has_bus:
            if plate not in seen_plates:
                seen_plates.add(plate)
                show_bus_tag = True

        stops_out.append({
            "name": s_name,
            "eta_text": time_text,
            "badge_class": badge_class,
            "plate": plate if show_bus_tag else "",
            "car_size": car_size,
            "is_low": bool(is_low),
            "is_ev": bool(is_ev),
            "has_bus": show_bus_tag,
            "ubikes": ubikes_near,
            "is_waiting_stop": bool(start_st and s_name == start_st),
        })

        if start_st and s_name == start_st:
            ai_log_list.append({"站": s_name, "動態": time_text, "車牌": plate or "無",
                                 "無障礙": "是" if is_low else "否", "電動": "是" if is_ev else "否"})
            tts_lines.append(f"等候站 {s_name}，{time_text}。{'無障礙低底盤。' if is_low else ''}{'電動公車。' if is_ev else ''}")

    bus_status = f"路線：{route}（往{direction}）。等候站動態：{json.dumps(ai_log_list, ensure_ascii=False)}"
    state["bus_status"] = bus_status

    return jsonify({
        "dest0": dest_0, "dest1": dest_1,
        "weather": weather_info,
        "stops": stops_out,
        "ubike_suggestion": ubike_suggestion,
        "tts_text": "".join(tts_lines),
        "empty": False,
    })


@app.route('/api/nearby_stops')
def api_nearby_stops():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "請輸入有效數字"}), 400
    all_stops_data = fetch_all_bus_stops()
    if not all_stops_data:
        return jsonify({"error": "無法載入站牌資料"}), 502
    nearby = find_nearby_stops(all_stops_data, lat, lon)
    return jsonify({"nearby": nearby})


# ══════════════════════════════════════════════════════════
# API：最愛 / 最近查詢
# ══════════════════════════════════════════════════════════
@app.route('/api/favorites', methods=['GET'])
def api_favorites_get():
    return jsonify({"favorites": get_state()["favorite_routes"]})


@app.route('/api/favorites/toggle', methods=['POST'])
def api_favorites_toggle():
    route = (request.json or {}).get('route')
    state = get_state()
    fav = state["favorite_routes"]
    if route in fav:
        fav.remove(route)
        is_fav = False
    else:
        fav.append(route)
        is_fav = True
    return jsonify({"favorites": fav, "is_favorite": is_fav})


@app.route('/api/recent', methods=['GET'])
def api_recent_get():
    return jsonify({"recent": get_state()["recent_routes"]})


# ══════════════════════════════════════════════════════════
# API：進階查詢（站到站）
# ══════════════════════════════════════════════════════════
@app.route('/api/advanced_search/stops')
def api_advanced_stops():
    stop_index = build_stop_route_index()
    return jsonify({"stops": sorted(stop_index.keys())})


@app.route('/api/advanced_search')
def api_advanced_search():
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    if not start or not end:
        return jsonify({"error": "請選擇出發站和目的站"}), 400
    if start == end:
        return jsonify({"error": "出發站和目的站不能相同"}), 400
    stop_index = build_stop_route_index()
    if not stop_index:
        return jsonify({"error": "請先到「系統維護」建立站點快取才能使用進階查詢"}), 400
    directs = find_direct_routes(stop_index, start, end)
    transfers = find_transfer_routes(stop_index, start, end)
    return jsonify({"directs": directs, "transfers": transfers})


# ══════════════════════════════════════════════════════════
# API：客運（跨縣市）查詢
# ══════════════════════════════════════════════════════════
@cached(3600)
def fetch_intercity_routes_by_op(op_id):
    url = (f"https://tdx.transportdata.tw/api/basic/v2/Bus/Route/InterCity"
           f"?%24filter=OperatorIDs/any(o:o%20eq%20'{op_id}')&%24format=JSON")
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


@cached(60)
def fetch_intercity_eta(route_id):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/InterCity/{route_id}?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


@cached(3600)
def fetch_intercity_stops(route_id):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/InterCity/{route_id}?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


@app.route('/api/intercity/operators')
def api_intercity_operators():
    return jsonify({"operators": INTERCITY_OPERATORS})


@app.route('/api/intercity/routes')
def api_intercity_routes():
    op_id = request.args.get('op_id', '')
    if not op_id:
        return jsonify({"routes": []})
    ic_routes = fetch_intercity_routes_by_op(op_id)
    route_options = []
    for r in ic_routes:
        dep = r.get("DepartureStopNameZh", "")
        dest = r.get("DestinationStopNameZh", "")
        rname = r.get("RouteName", {}).get("Zh_tw", "")
        rid = r.get("RouteUID", "")
        route_options.append({"label": f"{dep} → {dest}（{rname}）", "rid": rid, "dep": dep, "dest": dest})
    return jsonify({"routes": route_options, "total": len(ic_routes)})


@app.route('/api/intercity/detail')
def api_intercity_detail():
    rid = request.args.get('rid', '')
    if not rid:
        return jsonify({"error": "缺少路線代碼"}), 400
    stops_data = fetch_intercity_stops(rid)
    eta_data = fetch_intercity_eta(rid)
    eta_map = {}
    for e in eta_data:
        sn = e.get("StopName", {}).get("Zh_tw", "")
        eta_map[sn] = (e.get("EstimateTime"), e.get("StopStatus", 1))

    out = []
    for dir_data in stops_data[:1]:
        for s in dir_data.get("Stops", []):
            sn = s.get("StopName", {}).get("Zh_tw", "")
            eta_s, status = eta_map.get(sn, (None, 1))
            if eta_s is not None and status == 0:
                t = "即將進站" if eta_s <= 120 else f"{eta_s // 60} 分鐘"
                icon = "🟢"
            elif status == 3:
                t, icon = "末班車已過", "⚫"
            elif status == 4:
                t, icon = "今日停駛", "🔴"
            else:
                t, icon = "尚未發車", "⚪"
            out.append({"name": sn, "text": t, "icon": icon})
    return jsonify({"stops": out, "has_data": bool(stops_data)})


# ══════════════════════════════════════════════════════════
# API：地圖頁面
# ══════════════════════════════════════════════════════════
@app.route('/api/map_data')
def api_map_data():
    r_filter = request.args.get('routes', '')
    filter_list = [r.strip() for r in r_filter.replace("，", ",").split(',') if r.strip()] if r_filter else []
    # 若使用者輸入「全部」（或包含在清單中），視同未篩選，顯示全部路線的公車
    if any(x in ("全部", "全部路線") for x in filter_list):
        filter_list = []

    if filter_list:
        all_buses = []
        for r in filter_list:
            all_buses.extend(fetch_bus_realtime_positions(r))
    else:
        # 未篩選：一次性拉取全台南所有路線的即時公車位置
        all_buses = fetch_bus_realtime_positions()

    bus_features = []
    route_set = set()
    for bus in all_buses:
        pos = bus.get("BusPosition", {})
        lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
        route = bus.get("RouteName", {}).get("Zh_tw", "")
        if not lat or not lon or not route:
            continue
        route_set.add(route)
        bus_features.append({
            "lat": lat, "lon": lon, "route": route,
            "plate": bus.get("PlateNumb", ""),
            "dir": "去程" if bus.get("Direction", 0) == 0 else "回程",
            "speed": bus.get("Speed", "?"),
            "color": get_route_color(route)
        })

    shape_features = []
    routes_to_draw = filter_list if filter_list else sorted(route_set)[:30]
    for r in routes_to_draw:
        color = get_route_color(r)
        for sh in fetch_route_shape(r):
            pts = parse_wkt_linestring(sh.get("Geometry", ""))
            if pts:
                shape_features.append({"route": r, "color": color, "points": pts})

    return jsonify({
        "buses": bus_features,
        "shapes": shape_features,
        "routes": sorted(route_set),
        "now": datetime.now().strftime("%H:%M:%S"),
    })


# ══════════════════════════════════════════════════════════
# API：系統維護（重建站點快取）
# ══════════════════════════════════════════════════════════
@app.route('/api/update_cache', methods=['POST'])
def api_update_cache():
    all_cache = {}
    all_r = list(set(r for rl in ROUTE_CATEGORIES.values() for r in rl))
    for r_name in all_r:
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{r_name}?%24format=JSON"
        try:
            rr = requests.get(url, headers=tdx_headers(), timeout=10)
            if rr.status_code == 200:
                dj = rr.json()
                if dj:
                    all_cache[r_name] = [s['StopName']['Zh_tw'] for s in dj[0]['Stops']]
        except Exception:
            all_cache[r_name] = []
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_cache, f, ensure_ascii=False, indent=4)
    # 清除相關快取，讓下一次查詢立即反映新資料
    _cache_store.clear()
    return jsonify({"status": "success", "count": len(all_cache)})


# ══════════════════════════════════════════════════════════
# API：AI 助理（對話記錄多分頁）
# ══════════════════════════════════════════════════════════
@app.route('/api/chat/sessions', methods=['GET'])
def api_chat_sessions():
    state = get_state()
    if state["current_session_id"] is None or state["current_session_id"] not in state["chat_sessions"]:
        new_chat_session(state)
    sessions = [{"sid": sid, "title": s["title"], "is_current": sid == state["current_session_id"]}
                for sid, s in sorted(state["chat_sessions"].items(), reverse=True)]
    return jsonify({"sessions": sessions, "current_session_id": state["current_session_id"]})


@app.route('/api/chat/sessions/current')
def api_chat_current():
    state = get_state()
    if state["current_session_id"] is None or state["current_session_id"] not in state["chat_sessions"]:
        new_chat_session(state)
    sid = state["current_session_id"]
    sess = state["chat_sessions"][sid]
    return jsonify({"sid": sid, "title": sess["title"], "history": sess["history"]})


@app.route('/api/chat/sessions/new', methods=['POST'])
def api_chat_new():
    state = get_state()
    sid = new_chat_session(state)
    return jsonify({"sid": sid, "title": state["chat_sessions"][sid]["title"]})


@app.route('/api/chat/sessions/switch', methods=['POST'])
def api_chat_switch():
    sid = (request.json or {}).get('sid')
    state = get_state()
    if sid in state["chat_sessions"]:
        state["current_session_id"] = sid
        return jsonify({"status": "ok"})
    return jsonify({"error": "找不到該對話"}), 404


@app.route('/api/chat/sessions/delete', methods=['POST'])
def api_chat_delete():
    sid = (request.json or {}).get('sid')
    state = get_state()
    if sid in state["chat_sessions"]:
        del state["chat_sessions"][sid]
        if state["current_session_id"] == sid:
            state["current_session_id"] = None
    return jsonify({"status": "ok"})


@app.route('/api/chat', methods=['POST'])
def api_chat():
    if not client:
        return jsonify({"reply": "AI 模組未啟用，請檢查 GROQ_API_KEY。"})

    data = request.json or {}
    user_q = data.get('query', '')
    if not user_q:
        return jsonify({"error": "缺少訊息內容"}), 400

    state = get_state()
    if state["current_session_id"] is None or state["current_session_id"] not in state["chat_sessions"]:
        new_chat_session(state)
    sid = state["current_session_id"]
    sess = state["chat_sessions"][sid]

    system_msg = (
        "你是一位專業友善的台南公車導遊，擁有完整的對話記憶。"
        "請根據整段對話歷史，用流暢中文回答使用者問題。"
        f"\n【目前天氣】{state['current_weather']}"
        f"\n【公車狀態】{state['bus_status']}"
    )
    msgs = [{"role": "system", "content": system_msg}]
    for h in sess["history"][-20:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user_q})

    try:
        resp = client.chat.completions.create(
            messages=msgs, model="llama-3.3-70b-versatile", max_tokens=1024)
        ai_text = resp.choices[0].message.content

        if len(sess["history"]) == 0:
            sess["title"] = user_q[:20] + ("..." if len(user_q) > 20 else "")

        sess["history"].append({"role": "user", "content": user_q})
        sess["history"].append({"role": "assistant", "content": ai_text})

        return jsonify({"reply": ai_text, "title": sess["title"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════
# 使用者系統（檔案式）
# ══════════════════════════════════════════════════════════
def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def current_user():
    uid = session.get("user_id")
    if not uid: return None
    return load_users().get(uid)

def is_premium(user=None):
    u = user or current_user()
    if not u: return False
    exp = u.get("premium_until")
    if not exp: return False
    try:
        return datetime.fromisoformat(exp) > datetime.utcnow()
    except Exception:
        return False

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    pw    = data.get('password', '')
    if not email or not pw:
        return jsonify({"error": "請填寫電子郵件和密碼"}), 400
    if len(pw) < 6:
        return jsonify({"error": "密碼至少需要 6 個字元"}), 400
    users = load_users()
    for u in users.values():
        if u.get('email') == email:
            return jsonify({"error": "此電子郵件已被註冊"}), 400
    uid = str(uuid.uuid4())
    users[uid] = {
        "uid": uid, "email": email,
        "pw_hash": generate_password_hash(pw),
        "created_at": datetime.utcnow().isoformat(),
        "premium_until": None, "plan": None
    }
    save_users(users)
    session['user_id'] = uid
    return jsonify({"ok": True, "email": email})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data  = request.json or {}
    email = data.get('email', '').strip().lower()
    pw    = data.get('password', '')
    users = load_users()
    for uid, u in users.items():
        if u.get('email') == email:
            if not check_password_hash(u['pw_hash'], pw):
                return jsonify({"error": "密碼錯誤"}), 401
            session['user_id'] = uid
            exp = u.get('premium_until')
            return jsonify({
                "ok": True, "email": email,
                "is_premium": is_premium(u),
                "premium_until": exp, "plan": u.get('plan')
            })
    return jsonify({"error": "找不到此帳號"}), 404

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    return jsonify({"ok": True})

@app.route('/api/auth/me')
def api_me():
    u = current_user()
    if not u:
        return jsonify({"logged_in": False})
    return jsonify({
        "logged_in": True, "email": u['email'],
        "is_premium": is_premium(u),
        "premium_until": u.get('premium_until'),
        "plan": u.get('plan')
    })

# ══════════════════════════════════════════════════════════
# ECPay 付費
# ══════════════════════════════════════════════════════════
PLANS = {
    "monthly": {"amount": 20,  "desc": "月費方案 20元/月",  "days": 30},
    "yearly":  {"amount": 200, "desc": "年費方案 200元/年", "days": 365},
}

def ecpay_mac(params):
    """計算 ECPay CheckMacValue（SHA256）"""
    sorted_params = sorted((k, v) for k, v in params.items() if k != 'CheckMacValue')
    raw = '&'.join(f'{k}={v}' for k, v in sorted_params)
    raw = f"HashKey={ECPAY_HASH_KEY}&{raw}&HashIV={ECPAY_HASH_IV}"
    raw = urllib.parse.quote_plus(raw).lower()
    return hashlib.sha256(raw.encode()).hexdigest().upper()

@app.route('/api/payment/create', methods=['POST'])
def api_payment_create():
    u = current_user()
    if not u:
        return jsonify({"error": "請先登入"}), 401
    data = request.json or {}
    plan = data.get('plan')
    if plan not in PLANS:
        return jsonify({"error": "無效方案"}), 400
    p = PLANS[plan]
    trade_no = f"BUS{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
    base_url = request.host_url.rstrip('/')
    ecpay_url = ("https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
                 if ECPAY_IS_TEST else
                 "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5")
    params = {
        "MerchantID":        ECPAY_MERCHANT_ID,
        "MerchantTradeNo":   trade_no,
        "MerchantTradeDate": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType":       "aio",
        "TotalAmount":       str(p["amount"]),
        "TradeDesc":         p["desc"],
        "ItemName":          p["desc"],
        "ReturnURL":         f"{base_url}/api/payment/return",
        "ClientBackURL":     f"{base_url}/",
        "ChoosePayment":     "Credit",
        "EncryptType":       "1",
        "CustomField1":      u['uid'],
        "CustomField2":      plan,
    }
    params["CheckMacValue"] = ecpay_mac(params)
    # 產生自動送出表單
    fields = ''.join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in params.items())
    form_html = (f'<form id="ecpay_form" method="POST" action="{ecpay_url}">{fields}</form>'
                 f'<script>document.getElementById("ecpay_form").submit();</script>')
    return jsonify({"form_html": form_html})

@app.route('/api/payment/return', methods=['POST'])
def api_payment_return():
    """ECPay 付款完成伺服器回呼"""
    data  = request.form.to_dict()
    rtn   = data.get('RtnCode', '')
    given = data.get('CheckMacValue', '').upper()
    calc  = ecpay_mac(data)
    if rtn != '1' or given != calc:
        return "0|Error", 200
    uid  = data.get('CustomField1', '')
    plan = data.get('CustomField2', '')
    if uid and plan in PLANS:
        users = load_users()
        if uid in users:
            days = PLANS[plan]['days']
            u    = users[uid]
            cur_exp = u.get('premium_until')
            try:
                base = datetime.fromisoformat(cur_exp) if cur_exp and datetime.fromisoformat(cur_exp) > datetime.utcnow() else datetime.utcnow()
            except Exception:
                base = datetime.utcnow()
            u['premium_until'] = (base + timedelta(days=days)).isoformat()
            u['plan'] = plan
            save_users(users)
    return "1|OK", 200

# ══════════════════════════════════════════════════════════
# 地圖靜態快取（站點座標 + 路線軌跡，存在伺服器）
# ══════════════════════════════════════════════════════════
def load_map_static():
    try:
        with open(MAP_STATIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stops": [], "shapes": [], "routes": [], "built_at": None}

@app.route('/api/map_static')
def api_map_static():
    """回傳伺服器快取的站點+路線軌跡（每位訪客共用，不重複抓）"""
    return jsonify(load_map_static())

@app.route('/api/map_static/build', methods=['POST'])
def api_build_map_static():
    """管理員手動觸發：一次建立所有路線站點座標+路線軌跡"""
    all_routes = list(set(r for rl in ROUTE_CATEGORIES.values() for r in rl))

    # 1. 所有公車站點座標
    all_stops_raw = fetch_all_bus_stops()
    stops_out = []
    seen_names = set()
    for s in all_stops_raw:
        pos  = s.get("StopPosition", {})
        lat  = pos.get("PositionLat")
        lon  = pos.get("PositionLon")
        name = s.get("StopName", {}).get("Zh_tw", "")
        if lat and lon and name and name not in seen_names:
            seen_names.add(name)
            stops_out.append({"name": name, "lat": lat, "lon": lon})

    # 2. 路線軌跡
    shapes_out = []
    for rn in all_routes:
        color = get_route_color(rn)
        for sh in fetch_route_shape(rn):
            pts = parse_wkt_linestring(sh.get("Geometry", ""))
            if pts:
                shapes_out.append({"route": rn, "color": color, "points": pts})

    data = {
        "stops":    stops_out,
        "shapes":   shapes_out,
        "routes":   all_routes,
        "built_at": datetime.now().isoformat()
    }
    with open(MAP_STATIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return jsonify({"ok": True, "stops": len(stops_out), "shapes": len(shapes_out), "routes": len(all_routes)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
