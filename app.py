import os
import json
import math
import time
import uuid
import concurrent.futures
from datetime import datetime

import requests
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:
    Groq = None

from pull_backup import pull_backup
from push_backup import git_push_backup
import asyncio
import threading
import shutil

load_dotenv()

def create_app():
    import traceback
    traceback.print_stack()   # 印出是哪一行呼叫了 create_app
    pull_backup()
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
    return app
app = create_app()

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
COORDS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "tainan_stops_coords_cache.json")
# 手動「儲存路線座標到檔案」功能專用的輸出目錄（依需求指定的固定路徑）
ROUTE_DATA_SAVE_DIR = "/opt/render/project/data/route"

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


async def backup():
        try:
            # 備份來源與儲存位置
            source_folder = '/opt/render/project/data'
            backup_folder = '/opt/render/project/backups'

            os.makedirs(backup_folder, exist_ok=True)

            # 備份檔案路徑
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"backup_{now}.zip"
            backup_path = os.path.join(backup_folder, backup_filename)

            # 壓縮成 zip
            #shutil.make_archive(backup_path.replace(".zip", ""), 'zip', source_folder)
            await asyncio.to_thread(
            shutil.make_archive, 
            backup_path.replace(".zip", ""),       # 對應原本的 backup_path.replace(".zip", "")
            'zip',           # 壓縮格式
            source_folder    # 來源資料夾
            )

            print(f"✅ 自動備份完成：{backup_path}")

            # 保留最新10個備份
            backups = sorted(
                [f for f in os.listdir(backup_folder) if f.endswith('.zip')],
                key=lambda f: os.path.getmtime(os.path.join(backup_folder, f)),
                reverse=True  # 最新的在前
            )
            for old_backup in backups[10:]:
                old_path = os.path.join(backup_folder, old_backup)
                os.remove(old_path)
                print(f"🗑️ 已刪除過舊備份：{old_backup}")

            git_push_backup(source_folder)
        except Exception as e:
            print(f"❌ 備份失敗: {e}")

async def backup_loop():
    """每 3 小時執行備份的非同步迴圈"""
    while True:
        await backup()
        await asyncio.sleep(3 * 60 * 60)

def run_scheduler():
    """在獨立執行緒中跑 asyncio 事件迴圈"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(backup_loop())

# 啟動排程執行緒
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()


# 所有設定過的路線（去重、保留順序），用來確保地圖「未篩選」時每條路線都會被繪製，
# 不會因為該路線目前沒有營運中的公車而被漏掉。
ALL_ROUTE_NAMES = []
_seen_route_names = set()
for _rl in ROUTE_CATEGORIES.values():
    for _r in _rl:
        if _r not in _seen_route_names:
            _seen_route_names.add(_r)
            ALL_ROUTE_NAMES.append(_r)

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


def tdx_get(url, timeout=8, retries=1):
    """帶重試的 TDX GET，減少大量平行請求時偶發逾時/限流造成的空白資料。"""
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, headers=tdx_headers(), timeout=timeout)
            if res.status_code == 200:
                return res
        except Exception:
            pass
        if attempt < retries:
            time.sleep(0.4)
    return None


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
    res = tdx_get(url, timeout=8, retries=1)
    if res is not None:
        try:
            return res.json()
        except Exception:
            pass
    return []


def _parse_stop_positions_from_stop_of_route(data):
    """把 StopOfRoute 回傳（合併去/回程、依站名去重）整理成 [{name, lat, lon}, ...]"""
    result = []
    seen = set()
    for dir_data in data:
        for s in dir_data.get("Stops", []):
            name = s.get("StopName", {}).get("Zh_tw", "")
            pos = s.get("StopPosition", {})
            lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
            if name and lat and lon and name not in seen:
                seen.add(name)
                result.append({"name": name, "lat": lat, "lon": lon})
    return result


@cached(3600)
def fetch_route_stop_positions(route_name):
    """回傳某路線所有站牌的座標，供地圖畫小圓點用。
    優先讀取本機座標快取（由「系統維護→更新站點快取」建立），
    這樣地圖頁不必每次都即時打 TDX、也不會因為單次請求逾時/限流而漏站。
    快取不存在或沒有該路線時才即時向 TDX 查詢（並附重試）。"""
    try:
        with open(COORDS_CACHE_FILE, "r", encoding="utf-8") as f:
            c = json.load(f)
            if route_name in c and c[route_name]:
                return c[route_name]
    except FileNotFoundError:
        pass

    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    res = tdx_get(url, timeout=8, retries=1)
    if res is not None:
        try:
            return _parse_stop_positions_from_stop_of_route(res.json())
        except Exception:
            pass
    return []


def fetch_shapes_and_stops_parallel(routes):
    """平行抓取多條路線的軌跡與站牌座標，避免地圖「顯示全部路線」時要序列等待上百次 API。"""
    shape_map, stop_map = {}, {}

    def worker(r):
        return r, fetch_route_shape(r), fetch_route_stop_positions(r)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, r) for r in routes]
        for fut in concurrent.futures.as_completed(futures):
            try:
                r, shapes, stops = fut.result()
                shape_map[r] = shapes
                stop_map[r] = stops
            except Exception:
                pass
    return shape_map, stop_map


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
    live_route_set = set()
    for bus in all_buses:
        pos = bus.get("BusPosition", {})
        lat, lon = pos.get("PositionLat"), pos.get("PositionLon")
        route = bus.get("RouteName", {}).get("Zh_tw", "")
        if not lat or not lon or not route:
            continue
        live_route_set.add(route)
        bus_features.append({
            "lat": lat, "lon": lon, "route": route,
            "plate": bus.get("PlateNumb", ""),
            "dir": "去程" if bus.get("Direction", 0) == 0 else "回程",
            "speed": bus.get("Speed", "?"),
            "color": get_route_color(route)
        })

    # 無論該路線目前有沒有營運中的公車，都要能顯示其路線軌跡與站牌，
    # 因此路線清單一律使用「使用者指定的篩選清單」或「系統設定的全部路線」，
    # 而不是只看目前有跑的公車有哪些路線。
    routes_to_draw = filter_list if filter_list else ALL_ROUTE_NAMES

    shape_map, stop_map = fetch_shapes_and_stops_parallel(routes_to_draw)

    shape_features = []
    stop_features = []
    for r in routes_to_draw:
        color = get_route_color(r)
        for sh in shape_map.get(r, []):
            pts = parse_wkt_linestring(sh.get("Geometry", ""))
            if pts:
                shape_features.append({"route": r, "color": color, "points": pts})
        for sp in stop_map.get(r, []):
            stop_features.append({
                "route": r, "name": sp["name"],
                "lat": sp["lat"], "lon": sp["lon"], "color": color
            })

    return jsonify({
        "buses": bus_features,
        "shapes": shape_features,
        "stops": stop_features,
        "routes": routes_to_draw,
        "live_routes": sorted(live_route_set),
        "now": datetime.now().strftime("%H:%M:%S"),
    })


@app.route('/api/save_route_data', methods=['POST'])
def api_save_route_data():
    """從 TDX 即時抓取指定路線的「路線軌跡（Shape）」與「站牌清單（StopOfRoute）」，
    把 TDX 回傳的原始 JSON 內容原封不動存成兩份檔案：
      /opt/render/project/data/route/{路線名稱}_route_shape.json
      /opt/render/project/data/route/{路線名稱}_route_stop.json
    """
    route = (request.json or {}).get('route', '').strip()
    if not route:
        return jsonify({"error": "請輸入路線名稱"}), 400

    shape_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Shape/City/Tainan/{route}?%24format=JSON"
    stop_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route}?%24format=JSON"

    shape_res = tdx_get(shape_url, timeout=10, retries=1)
    stop_res = tdx_get(stop_url, timeout=10, retries=1)

    shape_data = None
    stop_data = None
    try:
        if shape_res is not None:
            shape_data = shape_res.json()
    except Exception:
        shape_data = None
    try:
        if stop_res is not None:
            stop_data = stop_res.json()
    except Exception:
        stop_data = None

    if not shape_data and not stop_data:
        return jsonify({"error": f"無法從 TDX 取得路線「{route}」的軌跡或站牌資料，請確認路線名稱是否正確"}), 404

    try:
        os.makedirs(ROUTE_DATA_SAVE_DIR, exist_ok=True)
    except Exception as e:
        return jsonify({"error": f"無法建立儲存目錄 {ROUTE_DATA_SAVE_DIR}：{e}"}), 500

    shape_path = os.path.join(ROUTE_DATA_SAVE_DIR, f"{route}_route_shape.json")
    stop_path = os.path.join(ROUTE_DATA_SAVE_DIR, f"{route}_route_stop.json")

    try:
        with open(shape_path, "w", encoding="utf-8") as f:
            json.dump(shape_data if shape_data is not None else [], f, ensure_ascii=False, indent=2)
        with open(stop_path, "w", encoding="utf-8") as f:
            json.dump(stop_data if stop_data is not None else [], f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({"error": f"寫入檔案失敗：{e}"}), 500

    shape_segments = len(shape_data) if isinstance(shape_data, list) else 0
    stop_count = 0
    if isinstance(stop_data, list):
        for dir_data in stop_data:
            stop_count += len(dir_data.get("Stops", []))

    return jsonify({
        "status": "success",
        "route": route,
        "shape_file": shape_path,
        "stop_file": stop_path,
        "shape_segments": shape_segments,
        "stop_count": stop_count,
        "shape_ok": bool(shape_data),
        "stop_ok": bool(stop_data),
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
