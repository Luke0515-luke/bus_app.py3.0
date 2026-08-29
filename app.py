import os
import json
import math
import time
import uuid
import concurrent.futures
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
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
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # 可依需求替換模型
            messages=[{"role": "user", "content": "你的提示詞或使用者輸入"}],
            temperature=0.2,  # 可調整創造性（0 到 1 之間）
            max_tokens=1024,
            )
    except Exception:
        client = None
        print("找不到 GROQ_API_KEY，AI 功能將受限。")
else:
    print("找不到 GROQ_API_KEY，AI 功能將受限。")

AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TAINAN_LAT, TAINAN_LON = 22.9997, 120.2270
UBIKE_SPEED_KMH = 15  # 估算騎車速度（OSRM 失敗時備用）
# 路線原始資料（站牌 StopOfRoute ＋ 軌跡 Shape）的正式儲存位置。
# 這個資料夾在 /opt/render/project/data 底下，會被排程每 10 分鐘備份到 GitHub 的
# backup 分支，即使 Render 重啟、清空硬碟，資料也不會不見——不再使用會消失在
# Render 硬碟根目錄、不會被備份的暫存快取檔。
ROUTE_DATA_SAVE_DIR = "/opt/render/project/data/route"
_route_file_lock = threading.Lock()

# 使用者帳號資料（登入系統）。跟路線原始資料放在同一個會被排程備份到 GitHub 的
# /opt/render/project/data 底下，Render 重啟、清空硬碟也不會遺失已註冊的帳號。
USERS_FILE = "/opt/render/project/data/users.json"
_users_lock = threading.Lock()


def _load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(users):
    with _users_lock:
        try:
            os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 寫入使用者資料失敗：{e}")


def _route_stop_file_path(route_name):
    return os.path.join(ROUTE_DATA_SAVE_DIR, f"{route_name}_route_stop.json")


def _route_shape_file_path(route_name):
    return os.path.join(ROUTE_DATA_SAVE_DIR, f"{route_name}_route_shape.json")


def _route_timetable_file_path(route_name):
    return os.path.join(ROUTE_DATA_SAVE_DIR, f"{route_name}_route_timetable.json")


def _save_route_json(path, data):
    """把某路線的 TDX 原始 JSON 寫進 /opt/render/project/data/route，
    會跟著現有的排程一起被備份到 GitHub，不會因為 Render 重啟而消失。"""
    with _route_file_lock:
        try:
            os.makedirs(ROUTE_DATA_SAVE_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 寫入路線資料失敗（{path}）：{e}")


def _entry_route_name(entry):
    """從 TDX 回傳的單筆資料（StopOfRoute 或 Shape 的其中一筆）取出真正的路線名稱。"""
    try:
        return (entry.get("RouteName") or {}).get("Zh_tw", "")
    except Exception:
        return ""


def _filter_route_entries(data, route_name):
    """只保留『真的屬於 route_name 這條路線』的資料。
    TDX 有些端點對路線名稱是用「包含比對」而不是完全比對，例如查詢路線「0」時，
    可能會把名稱裡有「0」的其他路線（10、70右、0左…）的站牌／軌跡資料也一併回傳，
    如果不過濾就直接存檔，就會出現『存到其他路線』的錯誤資料。
    這裡強制比對 RouteName 是否與查詢的 route_name 完全相同，不符的一律捨棄。"""
    if not isinstance(data, list):
        return data
    filtered = [d for d in data if isinstance(d, dict) and _entry_route_name(d) == route_name]
    return filtered


def _fetch_and_save_stop_data(route_name):
    """即時向 TDX 查詢某路線的 StopOfRoute 原始資料，驗證路線名稱後才存檔。"""
    data = _fetch_route_endpoint_json("StopOfRoute", route_name, timeout=10, retries=1)
    if data:
        _save_route_json(_route_stop_file_path(route_name), data)
    return data


def _fetch_and_save_shape_data(route_name):
    """即時向 TDX 查詢某路線的 Shape 原始資料，驗證路線名稱後才存檔。"""
    data = _fetch_route_endpoint_json("Shape", route_name, timeout=10, retries=1)
    if data:
        _save_route_json(_route_shape_file_path(route_name), data)
    return data


def _fetch_and_save_timetable_data(route_name):
    """即時向 TDX 查詢某路線的固定時刻表（Bus/Schedule）原始資料，驗證路線名稱後才存檔。
    跟站牌／軌跡走同一套「查一次、之後都吃檔案」的邏輯，避免每次打開時刻表都要
    重新等 TDX 回應（TDX 這支端點常常比較慢，手機在訊號不穩時容易直接 fetch 失敗）。"""
    data = _fetch_route_endpoint_json("Schedule", route_name, timeout=15, retries=1)
    if data:
        _save_route_json(_route_timetable_file_path(route_name), data)
    return data


def load_route_stop_data(route_name):
    """優先讀取已存檔的 StopOfRoute 資料（會被自動備份到 GitHub）；
    檔案不存在、損毀，或內容其實是其他路線的資料（舊版沒有驗證時可能存錯），
    都會視同快取失效，重新向 TDX 查一次並用驗證過的新資料覆蓋舊檔。"""
    path = _route_stop_file_path(route_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid = _filter_route_entries(data, route_name)
        if valid:
            return valid
        if data:
            print(f"⚠️「{route_name}」的存檔資料與路線名稱不符（疑似存到其他路線），將重新查詢並覆蓋。")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _fetch_and_save_stop_data(route_name) or []


def load_route_shape_data(route_name):
    """優先讀取已存檔的 Shape 資料（會被自動備份到 GitHub）；
    檔案不存在、損毀，或內容其實是其他路線的資料，都會重新向 TDX 查一次並覆蓋舊檔。"""
    path = _route_shape_file_path(route_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid = _filter_route_entries(data, route_name)
        if valid:
            return valid
        if data:
            print(f"⚠️「{route_name}」的存檔資料與路線名稱不符（疑似存到其他路線），將重新查詢並覆蓋。")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _fetch_and_save_shape_data(route_name) or []


def load_route_timetable_data(route_name):
    """優先讀取已存檔的固定時刻表資料（會被自動備份到 GitHub）；
    檔案不存在、損毀，或內容其實是其他路線的資料，都會重新向 TDX 查一次並覆蓋舊檔。"""
    path = _route_timetable_file_path(route_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid = _filter_route_entries(data, route_name)
        if valid:
            return valid
        if data:
            print(f"⚠️「{route_name}」的時刻表存檔與路線名稱不符（疑似存到其他路線），將重新查詢並覆蓋。")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return _fetch_and_save_timetable_data(route_name) or []


def _cleanup_known_bad_route_files():
    """開機時清掉已知的壞檔：路線名稱字面上是「0」的存檔（0_route_stop.json / 0_route_shape.json /
    0_route_timetable.json）。系統裡從來沒有一條路線正式名稱就叫「0」（實際上是「0左」「0右」），
    這個檔案如果存在，幾乎可以確定是之前查詢時把其他路線的資料混進來、存錯的殘留檔案。"""
    for bad_name in ("0",):
        for path in (_route_stop_file_path(bad_name), _route_shape_file_path(bad_name),
                     _route_timetable_file_path(bad_name)):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"🗑️ 已刪除錯誤殘留檔案：{path}")
            except Exception as e:
                print(f"⚠️ 刪除殘留檔案失敗（{path}）：{e}")


def _invalidate_route_cache(route_name):
    """清掉某條路線在記憶體暫存（in-memory cache）裡的舊資料，
    讓下一次查詢立即讀到剛存好的檔案。"""
    for fn in ("fetch_route_stops", "fetch_route_shape", "fetch_route_stop_positions", "fetch_route_schedule"):
        _cache_store.pop(f"{fn}:({route_name!r},):{{}}", None)
    _stop_route_index_cache["data"] = None
    _stop_route_index_cache["time"] = 0


_cleanup_known_bad_route_files()

# ── 常數與對照表（與原始 Streamlit 版本完全一致） ─────────
ROUTE_CATEGORIES = {
    "黃線": ["黃幹線", "黃1", "黃2", "黃3", "黃4", "黃5", "黃6", "黃6-1", "黃7", "黃9", "黃10", "黃11", "黃11-1", "黃12", "黃13", "黃14", "黃14-1", "黃15", "黃16", "黃20", "黃22", "黃23", "黃24", "黃25"],
    "棕線": ["棕幹線", "棕1", "棕2", "棕3", "棕3-1", "棕4", "棕5", "棕6", "棕20", "棕10", "棕11"],
    "綠線": ["綠幹線", "綠1", "綠2", "綠2-1", "綠3", "綠4", "綠5", "綠6", "綠7", "綠10", "綠11", "綠12", "綠12-1", "綠12-2", "綠13", "綠14", "綠15", "綠16", "綠17", "綠20", "綠20-1", "綠21", "綠22", "綠23", "綠24", "綠25", "綠26", "綠27", "綠28", "綠29", "綠30", "綠30-1", "綠31", "綠32"],
    "橘線": ["橘幹線", "橘1", "橘2", "橘3", "橘4", "橘4-1", "橘5", "橘6", "橘9", "橘9-1", "橘10", "橘10-1", "橘11", "橘11-1", "橘12", "橘13", "橘14", "橘20"],
    "藍線": ["藍幹線", "藍1", "藍2", "藍3", "藍4", "藍10", "藍11", "藍13", "藍14", "藍15", "藍20", "藍21", "藍22", "藍23", "藍24", "藍25", "藍26", "藍27", "藍28", "藍29", "藍30"],
    "紅線": ["紅幹線", "紅1", "紅2", "紅3", "紅4", "紅10", "紅11", "紅12", "紅13", "紅14"],
    "市區": ["0左", "0右", "6", "7", "9", "10", "11", "14", "15", "18", "19", "20", "21", "31", "32", "62", "70左", "70右", "77", "98", "101", "102", "103", "107", "111", "901", "902", "904", "905"],
    "高鐵快捷": ["H31"],
    "觀光": ["東山咖啡線", "梅嶺線", "菱波官田線", "雙層巴士", "33 關子嶺線", "168 虎埤老街線"]
}

ROUTE_COLOR_MAP = {
    "黃": "#F1C40F", "棕": "#8B4513", "綠": "#27AE60", "橘": "#E67E22",
    "藍": "#2980B9", "紅": "#E74C3C", "H": "#9B59B6",
    "0": "#1ABC9C",
    "6": "#E91E63", "7": "#E91E63", "9": "#E91E63",
    "10": "#FF5722", "11": "#FF5722", "14": "#FF5722", "15": "#FF5722",
    "18": "#FF9800", "19": "#FF9800", "20": "#FF9800", "21": "#FF9800",
    "31": "#795548", "32": "#795548", "33 關子嶺線": "#795548",
    "62": "#607D8B", "70": "#3F51B5", "77": "#009688", "98": "#F44336",
    "101": "#673AB7", "102": "#673AB7", "103": "#673AB7", "107": "#673AB7",
    "111": "#00BCD4", "168 虎埤老街線": "#00BCD4",
    "901": "#8BC34A", "902": "#8BC34A", "904": "#8BC34A", "905": "#8BC34A",
    "東山": "#FF6F00", "梅嶺": "#AD1457", "菱波": "#00838F", "雙層": "#BF360C",
}

# 「觀光」分類（東山咖啡線、梅嶺線、菱波官田線、雙層巴士、33 關子嶺線、168 虎埤老街線……）
# 在 TDX 上其實是登記在「公路客運／台灣好行（InterCity）」底下，不是市區公車，
# 路徑要用 .../InterCity/{route_name}，不能用 .../City/Tainan/{route_name}，
# 用錯路徑會讓這幾條路線不管怎麼查都查不到任何站牌／軌跡／時刻表資料。
INTERCITY_SIGHTSEEING_ROUTES = set(ROUTE_CATEGORIES.get("觀光", []))


def _is_intercity_route(route_name):
    """判斷這條路線在 TDX 上是否屬於公路客運（InterCity），而不是市區公車。"""
    return route_name in INTERCITY_SIGHTSEEING_ROUTES


def _bus_api_city_segment(route_name):
    """回傳這條路線在 TDX 公車 API 網址裡『City/縣市』或『InterCity』那一段路徑。"""
    return "InterCity" if _is_intercity_route(route_name) else "City/Tainan"


def _fetch_route_endpoint_json(api_name, route_name, timeout=10, retries=1):
    """向 TDX 查某個公車端點（StopOfRoute／Shape／Schedule…）＋某路線的原始資料，並做過濾。
    依路線分類判斷的路徑去查一次：市區公車走 City/Tainan，觀光的台灣好行路線走 InterCity。"""
    segment = _bus_api_city_segment(route_name)
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/{api_name}/{segment}/{route_name}?%24format=JSON"
    res = tdx_get(url, timeout=timeout, retries=retries)
    if res is None:
        return None
    try:
        data = res.json()
    except Exception:
        return None
    return _filter_route_entries(data, route_name)

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
        await asyncio.sleep(10 * 60)

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

def get_saved_route_names():
    """掃描 /opt/render/project/data/route，回傳『站牌（StopOfRoute）與軌跡（Shape）
    兩份資料都真的存在』的路線名稱（不管是不是在系統設定的 ROUTE_CATEGORIES 裡）。
    兩者缺一都不算——只有其中一份存在，代表地圖顯示時另一份還是得即時向 TDX 查，
    不能顯示 💾 讓人誤以為這條路線已經完整存好、只需要查公車定位就好。"""
    has_stop, has_shape = set(), set()
    try:
        for fn in os.listdir(ROUTE_DATA_SAVE_DIR):
            if fn.endswith("_route_stop.json"):
                has_stop.add(fn[: -len("_route_stop.json")])
            elif fn.endswith("_route_shape.json"):
                has_shape.add(fn[: -len("_route_shape.json")])
    except FileNotFoundError:
        pass
    return has_stop & has_shape


def get_all_known_routes():
    """系統設定的全部路線（ALL_ROUTE_NAMES）＋ 實際上已經存檔的路線，去重合併。
    確保就算某條路線不在預設分類表裡，只要曾經存過資料，一樣會被畫在地圖上、
    出現在『已儲存路線』清單裡。"""
    combined = list(ALL_ROUTE_NAMES)
    seen = set(combined)
    for r in sorted(get_saved_route_names()):
        if r and r not in seen:
            seen.add(r)
            combined.append(r)
    return combined


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


def _default_state():
    return {
        "recent_routes": [],
        "favorite_routes": [],
        "chat_sessions": {},
        "current_session_id": None,
        "current_weather": "尚未查詢",
        "bus_status": "尚未查詢路線",
    }


def get_uid():
    # 已登入的話用「使用者帳號」當作 key，這樣最愛路線／最近查詢／對話記錄
    # 才會綁定在帳號上，換裝置、換瀏覽器登入同一個帳號都看得到；
    # 沒登入則照舊用瀏覽器 session 產生的匿名 uid。
    if session.get("username"):
        uid = f"user:{session['username']}"
    else:
        if "uid" not in session:
            session["uid"] = str(uuid.uuid4())
        uid = session["uid"]
    if uid not in SESSION_STORE:
        SESSION_STORE[uid] = _default_state()
    return uid


def get_state():
    return SESSION_STORE[get_uid()]


def _login_user(username):
    """把目前瀏覽器的匿名資料（如果有的話）搬到帳號底下，再切換 session 成已登入狀態，
    這樣登入前查過的最愛／最近路線不會直接消失不見。"""
    old_uid = session.get("uid")
    session["username"] = username
    session.pop("uid", None)
    new_uid = f"user:{username}"
    if new_uid not in SESSION_STORE:
        SESSION_STORE[new_uid] = _default_state()
    if old_uid and old_uid in SESSION_STORE:
        old_state = SESSION_STORE[old_uid]
        new_state = SESSION_STORE[new_uid]
        if not new_state.get("favorite_routes") and old_state.get("favorite_routes"):
            new_state["favorite_routes"] = old_state["favorite_routes"]
        if not new_state.get("recent_routes") and old_state.get("recent_routes"):
            new_state["recent_routes"] = old_state["recent_routes"]


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
    data = load_route_stop_data(route_name)
    try:
        if data:
            return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except Exception:
        pass
    return []


def fetch_route_stops_by_direction(route_name, direction):
    """回傳某路線『指定方向』（去程=0／回程=1）的完整站序清單。
    跟 fetch_route_stops 不同：那支函式不管方向一律回傳 data[0]（TDX 通常把去程放在第一筆，
    但不保證每條路線都這樣）。如果查的是回程，卻拿去程的站序去跟『只過濾回程』的即時動態
    （EstimatedTimeOfArrival）逐站比對站名，兩邊站序、站名很多都對不上，會讓回程幾乎每一站
    都比對失敗、被誤判成『尚未發車』——這是『查詢常常顯示尚未發車，但實際上有車』的主因之一，
    所以查即時動態時一定要用這支，確保站序清單跟過濾出來的方向一致。"""
    data = load_route_stop_data(route_name)
    try:
        if data:
            for entry in data:
                if entry.get("Direction", 0) == direction:
                    return [s['StopName']['Zh_tw'] for s in entry.get('Stops', [])]
            # 少數路線的存檔資料裡找不到完全符合的方向，退回用第一筆，
            # 至少還能顯示站名，總比整條路線直接顯示「無法載入站點」好
            return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except Exception:
        pass
    return []


@cached(30)
def fetch_bus_data(route_name):
    segment = _bus_api_city_segment(route_name)
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/{segment}/{route_name}?%24format=JSON"
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
def fetch_all_route_meta():
    """取得 TDX 上台南市『所有』公車路線的正式登記資料（含正確的 RouteName）。
    用來在使用者輸入的路線名稱查不到資料時，反查 TDX 真正登記的名稱是什麼，
    而不是憑猜測去改設定檔。"""
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=tdx_headers(), timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


@cached(3600)
def fetch_route_shape(route_name):
    return load_route_shape_data(route_name)


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
    優先讀取 /opt/render/project/data/route 底下已存檔的 StopOfRoute 資料
    （會自動被排程備份到 GitHub），沒有的話即時查 TDX 並自動存檔。"""
    data = load_route_stop_data(route_name)
    try:
        return _parse_stop_positions_from_stop_of_route(data)
    except Exception:
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
        segment = _bus_api_city_segment(route_name)
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeByFrequency/{segment}/{route_name}?%24format=JSON"
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
def _fetch_all_route_stops_parallel(routes):
    """平行為多條路線取得站名清單。內部走 fetch_route_stops，
    每條路線都會優先讀 data/route 裡的存檔，沒有才即時查並自動存檔。"""
    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_route_stops, r): r for r in routes}
        for fut in concurrent.futures.as_completed(futures):
            r = futures[fut]
            try:
                result[r] = fut.result()
            except Exception:
                result[r] = []
    return result


_stop_route_index_cache = {"data": None, "time": 0}


def build_stop_route_index():
    """建立「站名 → 可搭乘路線」索引，供進階查詢（站到站）使用。
    這裡刻意跟即時地圖用同一份路線清單（get_all_known_routes，系統設定的路線 ∪
    地圖頁「已儲存路線」），不是只看系統設定的固定清單，才不會漏掉只在地圖那邊
    存過站牌資料的路線（例如小黃公車、自訂儲存的路線）。
    不依賴手動按「系統維護」：自動走遍全部路線，data/route 裡有存檔的直接用，
    沒有的即時查詢並自動存檔（存到 /opt/render/project/data/route，會被排程備份）。

    這裡刻意不用一般的 @cached(3600)：那樣會把「這次剛好一堆路線來不及查到
    （TDX 暫時卡住、或伺服器剛啟動還沒把全部路線都存過檔）」的不完整結果直接
    快取一整個小時，導致『進階查詢很多站不在清單裡』要卡一小時才會自己恢復。
    改成只有在幾乎所有路線都成功查到站牌時，才把結果快取住；查詢不完整的話
    直接回傳這次盡量湊到的結果，但不快取，讓下一次請求可以重新補齊缺漏的路線。"""
    now = time.time()
    cached_entry = _stop_route_index_cache["data"]
    if cached_entry is not None and now - _stop_route_index_cache["time"] < 3600:
        return cached_entry

    all_routes = get_all_known_routes()
    stops_map = _fetch_all_route_stops_parallel(all_routes)
    index = {}
    for route_name, stops in stops_map.items():
        for stop in stops:
            if stop not in index:
                index[stop] = []
            if route_name not in index[stop]:
                index[stop].append(route_name)

    missing = [r for r, s in stops_map.items() if not s]
    if all_routes and len(missing) <= max(3, len(all_routes) * 0.05):
        _stop_route_index_cache["data"] = index
        _stop_route_index_cache["time"] = now
    elif missing:
        print(f"⚠️ 進階查詢站名索引尚未完整（{len(missing)} 條路線暫時查不到站牌），本次結果先不快取。")
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
    """對應時間軸上的狀態文字與 badge 樣式。
    原則：只要 TDX 有給實際預估時間（eta 不是 None），就一定要顯示出來，
    不能因為 StopStatus 剛好不是 0（例如 TDX 資料本身標記怪怪的）就被蓋成「尚未發車」。
    只有真的完全沒有 eta 資料時，才退回用 StopStatus 判斷文字。"""
    if eta is not None:
        if eta <= 120:
            return "即將進站", "ts-orange"
        return f"{eta // 60} 分鐘", "ts-green"
    if status == 1:
        return "尚未發車", "ts-gray"
    elif status == 2:
        return "交管不停靠", "ts-gray"
    elif status == 3:
        return "末班車已過", "ts-red"
    elif status == 4:
        return "今日停駛", "ts-red"
    elif status == 0:
        # TDX 標記這站是正常營運狀態，只是暫時沒有可用的預估到站時間（不代表沒發車）
        return "營運中（無預估時間）", "ts-gray"
    return "尚未發車", "ts-gray"


_WEEKDAY_KEYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _timetable_departure_time(t):
    """從一筆 Timetables（一個班次）取得這班車實際的發車時間。
    TDX 的 Bus/Schedule 資料結構裡，Timetables 物件本身並沒有 DepartureTime 欄位；
    真正的發車時間是藏在 StopTimes 裡「站序（StopSequence）為 1」那一站的 DepartureTime
    （官方文件：取 Timetables 裡每個 Trip 的 StopTimes，找 StopSequence=1 的離站時間，
    即為該班車的發車時間）。之前直接取 t.get('DepartureTime') 一定拿到空字串，
    導致時刻表畫面上每個時間格都是空的。"""
    stop_times = t.get("StopTimes") or []
    if stop_times:
        first = min(stop_times, key=lambda s: s.get("StopSequence", 999))
        dt = first.get("DepartureTime") or first.get("ArrivalTime") or ""
        if dt:
            return dt
    # 保險：萬一哪天 TDX 格式又改了、真的有頂層 DepartureTime，還是讀得到
    return t.get("DepartureTime", "")


def _schedule_departure_times(route, direction):
    """回傳某路線／方向，「今天」（依星期幾比對服務日曆）所有固定班次的發車時間
    （today 的 datetime 物件）。沒有固定時刻表資料就回傳空 list。
    只在即時動態／GPS 都查不到資料時，拿來當備援估算用，不是每次都查。"""
    raw = fetch_route_schedule(route)
    if not raw:
        return []
    now = datetime.now()
    weekday_key = _WEEKDAY_KEYS[now.weekday()]
    times = []
    for entry in raw:
        if entry.get("Direction", 0) != direction:
            continue
        for t in entry.get("Timetables", []):
            svc = t.get("ServiceDay") or {}
            # 有 ServiceDay 資訊的話要符合今天星期幾；完全沒標示服務日曆的視為每天都有發車
            if svc and not svc.get(weekday_key, False):
                continue
            dep_str = _timetable_departure_time(t)
            if not dep_str:
                continue
            try:
                parts = dep_str.split(":")
                dep_dt = now.replace(hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0)
            except Exception:
                continue
            times.append(dep_dt)
    return times


def estimate_eta_from_schedule(dep_times, stop_index):
    """即時動態／GPS 都沒有這站的資料時，退回用固定時刻表概估到站時間：
    「發車時間 ＋ 每站約 2 分鐘（跟轉乘建議用的估算基準一致）」。
    僅供參考用的備援估算，不是真正的即時動態，所以呼叫端要另外標示清楚。"""
    if not dep_times:
        return None
    now = datetime.now()
    offset = timedelta(seconds=stop_index * 120)
    best = None
    for dep_dt in dep_times:
        diff = (dep_dt + offset - now).total_seconds()
        if diff < -60:
            # 這班車照時刻表推算應該早就過站了，不列入（可能是今天已經跑完的班次）
            continue
        diff = max(diff, 0)
        if best is None or diff < best:
            best = diff
    return best


# ══════════════════════════════════════════════════════════
# 頁面路由
# ══════════════════════════════════════════════════════════
@app.route('/')
def index():
    get_uid()
    return render_template('index.html',
                            route_categories=ROUTE_CATEGORIES)


# ══════════════════════════════════════════════════════════
# API：帳號登入
# ══════════════════════════════════════════════════════════
@app.route('/api/auth/status')
def api_auth_status():
    return jsonify({"username": session.get("username")})


@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({"error": "請輸入帳號與密碼"}), 400
    if len(username) < 2:
        return jsonify({"error": "帳號至少需要 2 個字"}), 400
    if len(password) < 4:
        return jsonify({"error": "密碼至少需要 4 碼"}), 400
    users = _load_users()
    if username in users:
        return jsonify({"error": "這個帳號已經被註冊了，請直接登入或換一個帳號"}), 400
    users[username] = {
        "password_hash": generate_password_hash(password),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_users(users)
    _login_user(username)
    return jsonify({"username": username})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    users = _load_users()
    u = users.get(username)
    if not u or not check_password_hash(u.get("password_hash", ""), password):
        return jsonify({"error": "帳號或密碼錯誤"}), 401
    _login_user(username)
    return jsonify({"username": username})


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.pop("username", None)
    session.pop("uid", None)
    return jsonify({"ok": True})


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
    """依照顏色／數字／分類篩選路線。支援一次選取多個篩選條件（用逗號分隔），
    只要符合任一個條件的路線都會列出（OR 邏輯），不是原本只能單選一種顏色/數字。"""
    raw_param = request.args.get('filter', '').strip()
    cf_list = [c.strip() for c in raw_param.replace('，', ',').split(',') if c.strip()]

    all_routes = []
    for rl in ROUTE_CATEGORIES.values():
        all_routes.extend(rl)
    seen_s = set()
    all_routes = [x for x in all_routes if not (x in seen_s or seen_s.add(x))]

    def match_one(cf):
        if cf == "市區":
            return ROUTE_CATEGORIES["市區"]
        if cf == "高鐵":
            return ROUTE_CATEGORIES["高鐵快捷"]
        if cf == "觀光":
            return ROUTE_CATEGORIES["觀光"]
        raw = [r for r in all_routes if cf in r]
        if cf.isdigit():
            def nsort(rs):
                nums = ''.join(c for c in rs if c.isdigit())
                return (0 if rs.startswith(cf) else 1, int(nums) if nums else 999, rs)
            return sorted(raw, key=nsort)
        return raw

    if not cf_list:
        filtered = all_routes
    else:
        # 多個篩選條件取聯集（符合任一個就列出），並保留 all_routes 原本的排序
        matched_set = set()
        for cf in cf_list:
            matched_set.update(match_one(cf))
        filtered = [r for r in all_routes if r in matched_set]
        # 「市區」「高鐵」「觀光」這幾類本身不在 all_routes 排序裡的路線，另外補上
        extra = [r for cf in cf_list for r in match_one(cf) if r not in filtered]
        seen_extra = set(filtered)
        for r in extra:
            if r not in seen_extra:
                filtered.append(r)
                seen_extra.add(r)

    return jsonify({"routes": filtered})


@app.route('/api/route_stops')
def api_route_stops():
    route = request.args.get('route', '')
    direction_label = request.args.get('direction', '')
    if not route:
        return jsonify({"stops": []})
    if direction_label in ('去程', '回程'):
        stops = fetch_route_stops_by_direction(route, 0 if direction_label == '去程' else 1)
    else:
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

    # 站點座標：改用跟站牌／地圖同一套「查一次、長期存檔」的資料來源，不要每次查即時動態
    # 都額外發一支獨立、沒有快取也沒有重試的即時 TDX 請求。原本那支請求只要剛好逾時或
    # TDX 忙線失敗，stop_coord_map 就會整個變空字典，GPS 定位備援（判斷『站上有車』）
    # 就會整組悄悄失效，這也是『明明有車在跑卻常常顯示尚未發車』的另一個主因。
    stop_coord_map = {}
    for sp in fetch_route_stop_positions(route):
        stop_coord_map[sp["name"]] = (sp["lat"], sp["lon"])

    ub_stations, ub_avail = fetch_ubike_all()
    realtime_map = {item.get("StopName", {}).get("Zh_tw", ""): item for item in active_list}
    all_stops_raw = fetch_route_stops_by_direction(route, target_dir)
    full_stop_list = all_stops_raw or [item.get("StopName", {}).get("Zh_tw", "") for item in active_list]

    if not full_stop_list:
        return jsonify({"dest0": dest_0, "dest1": dest_1, "stops": [], "empty": True})

    # TDX 的「逐站預估到站時間」（EstimatedTimeOfArrival）資料常常有缺口，
    # 尤其班次少、或車輛剛好在兩站中間時，容易讓明明有車在跑的站被判定成「尚未發車」。
    # 這裡另外抓「即時公車 GPS 定位」（RealTimeByFrequency，跟地圖用的是同一支端點），
    # 用最近站的方式回頭比對，確保只要 TDX 查得到這班車，時間軸上就不會漏掉它。
    gps_buses = fetch_bus_realtime_positions(route)
    gps_dir_buses = [b for b in gps_buses if b.get("Direction", 0) == target_dir]
    active_bus_count = len(gps_dir_buses)
    gps_near_stop = {}
    for b in gps_dir_buses:
        pos = b.get("BusPosition", {})
        b_lat, b_lon = pos.get("PositionLat"), pos.get("PositionLon")
        if not b_lat or not b_lon or not stop_coord_map:
            continue
        best_name, best_dist = None, None
        for name, (s_lat, s_lon) in stop_coord_map.items():
            d = haversine(b_lat, b_lon, s_lat, s_lon)
            if best_dist is None or d < best_dist:
                best_dist, best_name = d, name
        if best_name and best_dist is not None and best_dist <= 0.5:  # 500 公尺內才採信
            gps_near_stop.setdefault(best_name, []).append(b)

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
    main_dest = dest_0 if direction == "去程" else dest_1
    # 即時動態／GPS 都查不到資料時的最後備援：用固定時刻表概估到站時間（例如「尚未發車」
    # 但其實時刻表上等一下就有一班車），這裡只查一次，下面逐站比對時重複使用。
    schedule_dep_times = _schedule_departure_times(route, target_dir)

    for idx, s_name in enumerate(full_stop_list):
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

        # ETA 端點沒有這站的資料，但 GPS 定位確認附近真的有車在跑 → 用 GPS 資料補正，
        # 不要讓使用者看到「尚未發車」卻其實漏掉了一班查得到的車
        gps_here = gps_near_stop.get(s_name)
        if eta is None and status in (0, 1) and gps_here:
            gps_bus = gps_here[0]
            if not plate:
                plate = gps_bus.get("PlateNumb", "")
            time_text, badge_class = "進站中", "ts-red"

        # 即時動態、GPS 都完全查不到資料 → 最後退回用固定時刻表概估（僅供參考），
        # 避免像「新營站其實再 44 分鐘有車」卻一直顯示「尚未發車」什麼資訊都沒有。
        est_from_schedule = None
        if eta is None and not gps_here and status in (0, 1):
            est_from_schedule = estimate_eta_from_schedule(schedule_dep_times, idx)
            if est_from_schedule is not None:
                mins = int(est_from_schedule // 60)
                time_text = "即將進站（時刻表估計）" if mins <= 0 else f"約 {mins} 分鐘（時刻表估計）"
                badge_class = "ts-blue"

        # 支線／繞道：這一班車實際開往的目的地跟這條路線平常公告的方向不一樣時，
        # 特別標示出來，不要讓人誤以為所有車都開到同一個終點站。
        sub_route = (item.get("SubRouteName") or {}).get("Zh_tw", "") if item else ""
        dest_stop = (item.get("DestinationStopNameZh") or "") if item else ""
        if not dest_stop and not sub_route and gps_here:
            gb = gps_here[0]
            dest_stop = gb.get("DestinationStopNameZh", "") or ""
            sub_route = (gb.get("SubRouteName") or {}).get("Zh_tw", "")
        branch_label = ""
        if dest_stop and dest_stop != main_dest:
            branch_label = dest_stop
        elif sub_route and sub_route != route:
            branch_label = sub_route

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
            "branch": branch_label,
            "is_schedule_estimate": est_from_schedule is not None,
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
        "active_bus_count": active_bus_count,
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
        return jsonify({"error": "暫時無法取得站點資料，請稍後再試"}), 400
    directs = find_direct_routes(stop_index, start, end)
    transfers = find_transfer_routes(stop_index, start, end)
    return jsonify({"directs": directs, "transfers": transfers})


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
        # 有些車是繞道／支線行駛，實際終點跟路線平常公告的不一樣，這裡一併帶出來，
        # 前端才能在地圖上特別標示「這班車是開去哪裡」。
        sub_route = (bus.get("SubRouteName") or {}).get("Zh_tw", "")
        dest_stop = bus.get("DestinationStopNameZh", "") or ""
        branch = dest_stop or (sub_route if sub_route and sub_route != route else "")
        bus_features.append({
            "lat": lat, "lon": lon, "route": route,
            "plate": bus.get("PlateNumb", ""),
            "dir": "去程" if bus.get("Direction", 0) == 0 else "回程",
            "speed": bus.get("Speed", "?"),
            "color": get_route_color(route),
            "branch": branch,
        })

    # 無論該路線目前有沒有營運中的公車，都要能顯示其路線軌跡與站牌，
    # 因此路線清單一律使用「使用者指定的篩選清單」或「系統設定的全部路線＋已存檔路線」，
    # 而不是只看目前有跑的公車有哪些路線。這樣即使某條路線不在預設分類表裡，
    # 只要之前用「抓取並儲存路線原始資料」存過，也會出現在地圖與路線清單中。
    routes_to_draw = filter_list if filter_list else get_all_known_routes()

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
        "saved_routes": sorted(get_saved_route_names()),
        "live_routes": sorted(live_route_set),
        "now": datetime.now().strftime("%H:%M:%S"),
    })


@app.route('/api/saved_routes')
def api_saved_routes():
    """列出目前 /opt/render/project/data/route 底下實際已經存檔（Shape 或 StopOfRoute）
    的路線清單。用於地圖頁面顯示『已儲存路線』按鈕清單——只列出真的有資料的路線，
    而不是系統設定裡的全部路線清單。"""
    return jsonify({"routes": sorted(get_saved_route_names())})


_YELLOW_BUS_OPERATOR_KEYWORDS = ("大車隊", "皇冠交通", "衛星")  # 台一大車隊／中華衛星台南車隊（皇冠交通）


@app.route('/api/yellow_bus_routes')
def api_yellow_bus_routes():
    """列出台南『小黃公車』的路線清單。
    小黃公車本質上是用計程車營運一般公車路線，用的仍然是同一套 TDX 公車 API
    （StopOfRoute／Shape／即時動態），差別只在營運業者是台一大車隊／中華衛星台南車隊
    （皇冠交通），所以這裡直接用 TDX 路線清單的『營運業者』欄位反查，
    不用另外接一套 API，路線異動時也不用手動維護清單。"""
    routes = fetch_all_route_meta()
    result = []
    seen = set()
    for r in routes:
        name = (r.get("RouteName") or {}).get("Zh_tw", "")
        ops = r.get("Operators") or []
        op_names = [(op.get("OperatorName") or {}).get("Zh_tw", "") for op in ops]
        if not name or name in seen:
            continue
        if any(any(kw in on for kw in _YELLOW_BUS_OPERATOR_KEYWORDS) for on in op_names):
            seen.add(name)
            result.append({"route_name": name, "operators": [o for o in op_names if o]})
    result.sort(key=lambda x: x["route_name"])
    return jsonify({"routes": result, "total": len(result)})


def fetch_route_schedule(route_name):
    """取得某路線的固定時刻表（TDX Bus/Schedule）。
    小黃公車、支線公車大多是固定班次時刻，跟幹線那種『依班距發車』不一樣，
    所以另外用這支端點取時刻表，而不是即時動態。
    跟站牌／軌跡資料走同一套「查一次、長期存檔」的邏輯（load_route_timetable_data
    本身就會優先讀取已存檔的資料），這裡刻意不再疊加額外的短 TTL 記憶體快取——
    之前疊了一層 10 分鐘的快取，會連『TDX 暫時查詢頻率過高、這次剛好查空了』的
    空結果都一起快取住，導致明明時刻表存檔還在，畫面卻有 10 分鐘看起來像沒有
    時刻表資料。拿掉這層之後行為才會跟站牌資料一致：查得到就直接長期沿用存檔，
    查不到就下一次請求時重試，不會被自己快取卡住。"""
    return load_route_timetable_data(route_name)


@app.route('/api/timetable')
def api_timetable():
    """回傳某路線的固定時刻表，依方向（去程/回程）＋平日/假日整理成班次時間清單。"""
    route = request.args.get('route', '').strip()
    if not route:
        return jsonify({"error": "缺少路線名稱"}), 400
    raw = fetch_route_schedule(route)
    if not raw:
        return jsonify({"route": route, "directions": [], "has_data": False,
                         "message": "TDX 目前查不到這條路線的固定時刻表（可能是依班距發車的幹線，沒有公告時刻表）"})

    directions = []
    for entry in raw:
        try:
            direction = entry.get("Direction", 0)
            dest = (entry.get("DestinationStopNameZh") or
                    (entry.get("SubRouteName") or {}).get("Zh_tw") or "")
            timetables = entry.get("Timetables", [])
            # 依服務日曆（平日/假日/全週…）分組，每組列出所有發車時間
            groups = {}
            for t in timetables:
                svc = (t.get("ServiceDay") or {})
                label_bits = []
                for k, zh in (("Monday", "一"), ("Tuesday", "二"), ("Wednesday", "三"),
                              ("Thursday", "四"), ("Friday", "五"), ("Saturday", "六"), ("Sunday", "日")):
                    if svc.get(k):
                        label_bits.append(zh)
                label = "、".join(label_bits) if label_bits else "每日"
                dep_str = _timetable_departure_time(t)
                if not dep_str:
                    continue
                groups.setdefault(label, []).append(dep_str)
            for label, times in groups.items():
                times.sort()
            directions.append({
                "direction": direction,
                "destination": dest,
                "groups": [{"days": k, "times": v} for k, v in groups.items()],
            })
        except Exception:
            continue

    return jsonify({"route": route, "directions": directions, "has_data": bool(directions)})


@app.route('/api/route_lookup')
def api_route_lookup():
    """反查 TDX 上『真正登記』的路線名稱是什麼。
    當某條路線用系統設定的名稱查不到即時定位、也查不到 Shape/StopOfRoute 時，
    很可能是這個名稱跟 TDX 實際登記的不完全一樣（例如改名、整併過），
    這裡直接去 TDX 的路線清單裡做包含比對，讓使用者確認正確名稱，而不是用猜的。"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"matches": []})
    routes = fetch_all_route_meta()
    matches = []
    seen = set()
    for r in routes:
        name = (r.get("RouteName") or {}).get("Zh_tw", "")
        if name and q in name and name not in seen:
            seen.add(name)
            ops = r.get("Operators") or []
            op_names = [(op.get("OperatorName") or {}).get("Zh_tw", "") for op in ops]
            matches.append({
                "route_name": name,
                "route_uid": r.get("RouteUID", ""),
                "operators": [o for o in op_names if o],
            })
    return jsonify({"query": q, "matches": matches, "total_routes_checked": len(routes)})


@app.route('/api/save_route_data', methods=['POST'])
def api_save_route_data():
    """從 TDX 即時抓取指定路線的「路線軌跡（Shape）」與「站牌清單（StopOfRoute）」，
    強制重新查詢並把 TDX 回傳的原始 JSON 內容原封不動存成兩份檔案：
      /opt/render/project/data/route/{路線名稱}_route_shape.json
      /opt/render/project/data/route/{路線名稱}_route_stop.json
    （一般情況下不需要手動按這顆按鈕——每條路線第一次被查詢或在地圖上顯示時，
    就會自動存檔；這顆按鈕只是用來強制刷新單一路線的最新資料。）
    """
    route = (request.json or {}).get('route', '').strip()
    if not route:
        return jsonify({"error": "請輸入路線名稱"}), 400

    shape_data = _fetch_and_save_shape_data(route)
    stop_data = _fetch_and_save_stop_data(route)

    if not shape_data and not stop_data:
        # 查不到資料時，順便反查 TDX 上名稱相近的路線，幫忙抓出可能是「名稱對不起來」的狀況
        keyword = route[0] if route else route
        suggestions = []
        try:
            for r in fetch_all_route_meta():
                name = (r.get("RouteName") or {}).get("Zh_tw", "")
                if name and keyword in name and name != route and name not in suggestions:
                    suggestions.append(name)
        except Exception:
            pass
        msg = f"無法從 TDX 取得路線「{route}」的軌跡或站牌資料，請確認路線名稱是否正確"
        if suggestions:
            msg += f"。TDX 上名稱相近的路線有：{'、'.join(suggestions[:8])}"
        return jsonify({"error": msg, "suggestions": suggestions[:8]}), 404

    _invalidate_route_cache(route)

    shape_segments = len(shape_data) if isinstance(shape_data, list) else 0
    stop_count = 0
    if isinstance(stop_data, list):
        for dir_data in stop_data:
            stop_count += len(dir_data.get("Stops", []))

    return jsonify({
        "status": "success",
        "route": route,
        "shape_file": _route_shape_file_path(route),
        "stop_file": _route_stop_file_path(route),
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
    """強制重新抓取『全部路線』的站牌資料並存檔到 /opt/render/project/data/route。
    一般情況下不需要手動按這顆按鈕——每條路線第一次被查詢或在地圖上顯示時，
    就會自動存檔；這顆按鈕只是用來一次性強制刷新全部路線的最新資料。"""
    count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_and_save_stop_data, r): r for r in get_all_known_routes()}
        for fut in concurrent.futures.as_completed(futures):
            try:
                if fut.result():
                    count += 1
            except Exception:
                pass
    # 清除相關記憶體快取，讓下一次查詢立即反映新資料
    _cache_store.clear()
    return jsonify({"status": "success", "count": count})


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

    # Groq 三不五時會下架／改名模型（例如 2026/06 就把 llama-3.3-70b-versatile 整個下架），
    # 一旦主要模型剛好被下架，直接整個 AI 功能掛掉太可惜，這裡準備幾個備援模型依序嘗試。
    candidate_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]
    resp = None
    last_err = None
    for m in candidate_models:
        try:
            resp = client.chat.completions.create(messages=msgs, model=m, max_tokens=1024)
            break
        except Exception as e:
            last_err = e
            continue

    try:
        if resp is None:
            raise last_err or RuntimeError("AI 模型目前都無法使用")
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
