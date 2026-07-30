import json
import math
import streamlit as st
import requests
from groq import Groq
from datetime import datetime

app_id = st.secrets["CLIENT_ID"]
app_key = st.secrets["CLIENT_SECRET"]

if "GROQ_API_KEY" in st.secrets:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
else:
    st.error("找不到 GROQ_API_KEY，請檢查 Secrets！")

ROUTE_CATEGORIES = {
    "黃線": ["黃幹線","黃1","黃2","黃3","黃4","黃5","黃6","黃6-1","黃7","黃9","黃10","黃11","黃11-1","黃12","黃13","黃14","黃14-1","黃15","黃16","黃20","黃22","黃23","黃24","黃25"],
    "棕線": ["棕幹線","棕1","棕2","棕3","棕3-1","棕4","棕5","棕6","棕20","棕10","棕11"],
    "綠線": ["綠幹線","綠1","綠2","綠2-1","綠3","綠4","綠5","綠6","綠7","綠10","綠11","綠12","綠12-1","綠12-2","綠13","綠14","綠15","綠16","綠17","綠20","綠20-1","綠21","綠22","綠23","綠24","綠25","綠26","綠27","綠28","綠29","綠30","綠30-1","綠31","綠32"],
    "橘線": ["橘幹線","橘1","橘2","橘3","橘4","橘4-1","橘5","橘6","橘9","橘9-1","橘10","橘10-1","橘11","橘11-1","橘12","橘13","橘14","橘20"],
    "藍線": ["藍幹線","藍1","藍2","藍3","藍4","藍10","藍11","藍13","藍14","藍15","藍20","藍21","藍22","藍23","藍24","藍25","藍26","藍27","藍28","藍29","藍30"],
    "紅線": ["紅幹線","紅1","紅2","紅3","紅4","紅10","紅11","紅12","紅13","紅14"],
    "市區": ["0左","0右","6","7","9","10","11","14","15","18","19","20","21","31","32","33","62","70左","70右","77","98","101","102","103","107","111","168","901","902","904","905"],
    "高鐵快捷": ["H31"],
    "觀光": ["東山咖啡線","梅嶺線","菱波官田線","雙層巴士"]
}

auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TAINAN_LAT, TAINAN_LON = 22.9997, 120.2270
UBIKE_SPEED_KMH = 15  # 估算騎車速度（OSRM 失敗時備用）

# ── OSRM 免費路由 ─────────────────────────────────────────
def get_osrm_travel_time(start_lat, start_lon, end_lat, end_lon, mode="bike"):
    """mode: 'bike' 或 'foot'，回傳 (距離文字, 分鐘數) 或 (None, None)"""
    try:
        url = (f"http://router.project-osrm.org/route/v1/{mode}/"
               f"{start_lon},{start_lat};{end_lon},{end_lat}?overview=false")
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            route = res.json()["routes"][0]
            dist_m  = route["distance"]
            dur_min = round(route["duration"] / 60)
            dist_text = f"{round(dist_m/1000,1)} 公里" if dist_m >= 1000 else f"{round(dist_m)} 公尺"
            return dist_text, dur_min
    except:
        pass
    return None, None

# ── 路線顏色對照 ──────────────────────────────────────────
ROUTE_COLOR_MAP = {
    "黃":"#F1C40F","棕":"#8B4513","綠":"#27AE60","橘":"#E67E22",
    "藍":"#2980B9","紅":"#E74C3C","H":"#9B59B6",
    "0":"#1ABC9C",
    "6":"#E91E63","7":"#E91E63","9":"#E91E63",
    "10":"#FF5722","11":"#FF5722","14":"#FF5722","15":"#FF5722",
    "18":"#FF9800","19":"#FF9800","20":"#FF9800","21":"#FF9800",
    "31":"#795548","32":"#795548","33":"#795548",
    "62":"#607D8B","70":"#3F51B5","77":"#009688","98":"#F44336",
    "101":"#673AB7","102":"#673AB7","103":"#673AB7","107":"#673AB7",
    "111":"#00BCD4","168":"#00BCD4",
    "901":"#8BC34A","902":"#8BC34A","904":"#8BC34A","905":"#8BC34A",
    "東山":"#FF6F00","梅嶺":"#AD1457","菱波":"#00838F","雙層":"#BF360C",
}

def get_route_color(route_name):
    # 長前綴優先，避免 "10" 被 "1" 誤匹配
    for prefix in sorted(ROUTE_COLOR_MAP.keys(), key=len, reverse=True):
        if route_name.startswith(prefix):
            return ROUTE_COLOR_MAP[prefix]
    return "#7F8C8D"

# ── 即時公車位置 API ──────────────────────────────────────
def fetch_bus_realtime_positions(token, route_name=None):
    """抓全台南或指定路線的即時公車位置"""
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    if route_name:
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeByFrequency/City/Tainan/{route_name}?%24format=JSON"
    else:
        url = "https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeByFrequency/City/Tainan?%24format=JSON"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []

@st.cache_data(ttl=3600)
def fetch_route_shape(route_name, token):
    """抓路線的 GPS 軌跡線段（Geometry）"""
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Shape/City/Tainan/{route_name}?%24format=JSON"
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []

def parse_wkt_linestring(geo):
    """把 TDX WKT LINESTRING 轉成 [[lat,lon],...] 的列表"""
    points = []
    try:
        coords_str = geo.replace("LINESTRING (","").replace("LINESTRING(","").replace(")","")
        for pair in coords_str.split(","):
            parts = pair.strip().split()
            if len(parts) >= 2:
                points.append([float(parts[1]), float(parts[0])])
    except:
        pass
    return points

def build_map_page(token):
    """Leaflet.js 純 HTML 地圖，Python 負責抓資料，不閃爍、可篩選、15秒更新"""

    st.subheader("🗺️ 台南公車即時位置地圖")

    # ── 控制列 ──────────────────────────────────────────
    col_f, col_r, col_u = st.columns([3, 1, 1])
    with col_f:
        route_input = st.text_input(
            "篩選路線（留空=全部，多條用逗號分隔）",
            value=", ".join(st.session_state.map_filter_routes),
            placeholder="例：藍幹線, 綠1, 橘2",
            key="map_route_input"
        )
    with col_r:
        st.write(""); st.write("")
        refresh = st.button("🔄 更新", use_container_width=True)
    with col_u:
        st.write(""); st.write("")
        if st.button("🏠 回查詢頁", use_container_width=True):
            st.session_state.current_page = "query"
            st.rerun()

    # 解析篩選清單
    if route_input.strip():
        filter_list = [r.strip() for r in route_input.replace("，",",").split(",") if r.strip()]
    else:
        filter_list = []
    st.session_state.map_filter_routes = filter_list

    now_str = datetime.now().strftime("%H:%M:%S")
    if refresh or not st.session_state.map_last_updated:
        st.session_state.map_last_updated = now_str

    st.caption(f"資料時間：{st.session_state.map_last_updated}　｜　每次按「🔄 更新」重抓最新位置")

    # ── 抓公車即時位置 ───────────────────────────────────
    with st.spinner("抓取公車位置中..."):
        if filter_list:
            all_buses = []
            for r in filter_list:
                all_buses.extend(fetch_bus_realtime_positions(token, r))
        else:
            try:
                with open("tainan_stops_cache.json","r",encoding="utf-8") as f:
                    cached_routes = list(json.load(f).keys())
            except:
                cached_routes = []
            all_buses = []
            for r in cached_routes[:60]:
                all_buses.extend(fetch_bus_realtime_positions(token, r))

    # ── 整理公車資料 → JSON ──────────────────────────────
    bus_features = []
    route_set = set()
    for bus in all_buses:
        pos   = bus.get("BusPosition", {})
        lat   = pos.get("PositionLat")
        lon   = pos.get("PositionLon")
        route = bus.get("RouteName", {}).get("Zh_tw", "")
        plate = bus.get("PlateNumb", "")
        direc = "去程" if bus.get("Direction", 0) == 0 else "回程"
        speed = bus.get("Speed", "?")
        if not lat or not lon or not route:
            continue
        color = get_route_color(route)
        route_set.add(route)
        bus_features.append({
            "lat": lat, "lon": lon,
            "route": route, "plate": plate,
            "dir": direc, "speed": speed,
            "color": color
        })

    # ── 抓路線軌跡 → JSON ───────────────────────────────
    shape_features = []
    routes_to_draw = filter_list if filter_list else sorted(route_set)[:30]
    with st.spinner("載入路線軌跡中..."):
        for r in routes_to_draw:
            color  = get_route_color(r)
            shapes = fetch_route_shape(r, token)
            for sh in shapes:
                pts = parse_wkt_linestring(sh.get("Geometry",""))
                if pts:
                    shape_features.append({"route": r, "color": color, "points": pts})

    # ── 路線清單（左側面板用）───────────────────────────
    all_routes_sorted = sorted(route_set)

    # 序列化成 JS 變數
    bus_json   = json.dumps(bus_features,   ensure_ascii=False)
    shape_json = json.dumps(shape_features, ensure_ascii=False)
    routes_json= json.dumps(all_routes_sorted, ensure_ascii=False)

    # ── 建立 Leaflet HTML ────────────────────────────────
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Noto Sans TC', sans-serif; }}
  body {{ display: flex; height: 100vh; overflow: hidden; background: #1a1a2e; }}

  /* 左側面板 */
  #panel {{
    width: 220px; min-width: 220px;
    background: #16213e;
    color: #eee;
    display: flex; flex-direction: column;
    overflow: hidden;
    border-right: 1px solid #0f3460;
  }}
  #panel-header {{
    padding: 12px;
    background: #0f3460;
    font-weight: bold;
    font-size: 14px;
    color: #fff;
  }}
  #panel-stats {{
    padding: 8px 12px;
    font-size: 12px;
    color: #aaa;
    border-bottom: 1px solid #0f3460;
  }}
  #search-box {{
    margin: 8px;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid #0f3460;
    background: #1a1a2e;
    color: #eee;
    font-size: 12px;
    width: calc(100% - 16px);
  }}
  #route-list {{
    flex: 1;
    overflow-y: auto;
    padding: 4px 0;
  }}
  .route-item {{
    display: flex;
    align-items: center;
    padding: 6px 12px;
    cursor: pointer;
    font-size: 13px;
    border-bottom: 1px solid #0f3460;
    transition: background 0.15s;
  }}
  .route-item:hover {{ background: #0f3460; }}
  .route-item.active {{ background: #0f3460; }}
  .route-dot {{
    width: 12px; height: 12px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
    border: 2px solid rgba(255,255,255,0.3);
  }}
  .route-count {{
    margin-left: auto;
    font-size: 11px;
    color: #888;
    background: #0f3460;
    padding: 1px 5px;
    border-radius: 8px;
  }}

  /* 地圖 */
  #map {{ flex: 1; }}

  /* 彈出資訊卡 */
  .bus-popup b {{ font-size: 15px; color: #333; }}
  .bus-popup .tag {{
    display: inline-block;
    padding: 2px 6px; border-radius: 4px;
    font-size: 11px; color: white;
    margin-top: 4px; margin-right: 2px;
  }}
  .leaflet-popup-content {{ min-width: 160px; }}
</style>
</head>
<body>

<div id="panel">
  <div id="panel-header">🚌 台南公車即時地圖</div>
  <div id="panel-stats" id="stats">載入中...</div>
  <input id="search-box" type="text" placeholder="搜尋路線..." oninput="filterPanel(this.value)"/>
  <div id="route-list"></div>
</div>

<div id="map"></div>

<script>
// ── 資料（由 Python 注入）──────────────────────────
const BUS_DATA    = {bus_json};
const SHAPE_DATA  = {shape_json};
const ALL_ROUTES  = {routes_json};

// ── 初始化地圖 ─────────────────────────────────────
const map = L.map('map', {{ zoomControl: true }}).setView([22.9997, 120.2270], 13);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '© OpenStreetMap © CARTO',
  subdomains: 'abcd',
  maxZoom: 19
}}).addTo(map);

// ── 狀態 ───────────────────────────────────────────
let activeRoutes = new Set(ALL_ROUTES);  // 預設全部顯示
let busMarkers   = L.layerGroup().addTo(map);
let shapeLines   = L.layerGroup().addTo(map);

// ── 畫路線軌跡 ─────────────────────────────────────
function drawShapes() {{
  shapeLines.clearLayers();
  SHAPE_DATA.forEach(sh => {{
    if (!activeRoutes.has(sh.route)) return;
    const latlngs = sh.points.map(p => [p[0], p[1]]);
    L.polyline(latlngs, {{
      color: sh.color,
      weight: 3,
      opacity: 0.75
    }}).bindTooltip(sh.route, {{sticky: true}}).addTo(shapeLines);
  }});
}}

// ── 畫公車標記 ─────────────────────────────────────
function makeBusIcon(color) {{
  return L.divIcon({{
    className: '',
    html: `<div style="
      width:18px; height:18px;
      background:${{color}};
      border:2.5px solid rgba(255,255,255,0.85);
      border-radius:50%;
      box-shadow: 0 0 6px ${{color}};
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  }});
}}

// 統計每條路線的車輛數
function countByRoute() {{
  const cnt = {{}};
  BUS_DATA.forEach(b => {{
    if (activeRoutes.has(b.route))
      cnt[b.route] = (cnt[b.route] || 0) + 1;
  }});
  return cnt;
}}

function drawBuses() {{
  busMarkers.clearLayers();
  let total = 0;
  BUS_DATA.forEach(b => {{
    if (!activeRoutes.has(b.route)) return;
    const marker = L.marker([b.lat, b.lon], {{ icon: makeBusIcon(b.color) }});
    marker.bindPopup(`
      <div class="bus-popup">
        <b>🚌 ${{b.route}}</b><br>
        <span class="tag" style="background:${{b.color}}">車牌：${{b.plate}}</span>
        <span class="tag" style="background:#555">方向：${{b.dir}}</span>
        <span class="tag" style="background:#333">速度：${{b.speed}} km/h</span>
      </div>
    `, {{ maxWidth: 200 }});
    marker.addTo(busMarkers);
    total++;
  }});

  // 更新統計
  const shown = activeRoutes.size;
  document.getElementById('panel-stats').textContent =
    `顯示 ${{shown}} 條路線・${{total}} 台公車`;
}}

// ── 左側路線面板 ───────────────────────────────────
function buildPanel(filterText) {{
  const list = document.getElementById('route-list');
  list.innerHTML = '';
  const cnt = countByRoute();

  // 全選/取消
  const allItem = document.createElement('div');
  const allActive = activeRoutes.size === ALL_ROUTES.length;
  allItem.className = 'route-item' + (allActive ? ' active' : '');
  allItem.innerHTML = `
    <div class="route-dot" style="background:#fff;"></div>
    <span>全部路線</span>
    <span class="route-count">${{ALL_ROUTES.length}}</span>
  `;
  allItem.onclick = () => {{
    if (activeRoutes.size === ALL_ROUTES.length)
      activeRoutes.clear();
    else
      ALL_ROUTES.forEach(r => activeRoutes.add(r));
    buildPanel(filterText);
    drawShapes(); drawBuses();
  }};
  list.appendChild(allItem);

  ALL_ROUTES.forEach(route => {{
    if (filterText && !route.includes(filterText)) return;
    const color = getRouteColor(route);
    const n = cnt[route] || 0;
    const item = document.createElement('div');
    item.className = 'route-item' + (activeRoutes.has(route) ? ' active' : '');
    item.innerHTML = `
      <div class="route-dot" style="background:${{color}};"></div>
      <span>${{route}}</span>
      <span class="route-count">${{n}}</span>
    `;
    item.onclick = () => {{
      if (activeRoutes.has(route)) activeRoutes.delete(route);
      else activeRoutes.add(route);
      item.classList.toggle('active');
      drawShapes(); drawBuses();
      buildPanel(filterText);
    }};
    list.appendChild(item);
  }});
}}

function filterPanel(text) {{
  buildPanel(text);
}}

// ── 路線顏色（與 Python 同步，長前綴優先）────────
function getRouteColor(name) {{
  const colorMap = [
    ['黃','#F1C40F'],['棕','#8B4513'],['綠','#27AE60'],['橘','#E67E22'],
    ['藍','#2980B9'],['紅','#E74C3C'],['H','#9B59B6'],
    ['0','#1ABC9C'],
    ['101','#673AB7'],['102','#673AB7'],['103','#673AB7'],['107','#673AB7'],
    ['111','#00BCD4'],['168','#00BCD4'],
    ['10','#FF5722'],['11','#FF5722'],['14','#FF5722'],['15','#FF5722'],
    ['18','#FF9800'],['19','#FF9800'],['20','#FF9800'],['21','#FF9800'],
    ['31','#795548'],['32','#795548'],['33','#795548'],
    ['62','#607D8B'],['70','#3F51B5'],['77','#009688'],['98','#F44336'],
    ['901','#8BC34A'],['902','#8BC34A'],['904','#8BC34A'],['905','#8BC34A'],
    ['6','#E91E63'],['7','#E91E63'],['9','#E91E63'],
    ['東山','#FF6F00'],['梅嶺','#AD1457'],['菱波','#00838F'],['雙層','#BF360C'],
  ];
  // 陣列已按長前綴優先排列
  for (const [prefix, color] of colorMap) {{
    if (name.startsWith(prefix)) return color;
  }}
  return '#7F8C8D';
}}

// ── 初始化 ─────────────────────────────────────────
drawShapes();
drawBuses();
buildPanel('');
</script>
</body>
</html>
"""
    st.components.v1.html(html, height=680, scrolling=False)

    if bus_features:
        st.success(f"✅ 共 {len(bus_features)} 台公車・{len(route_set)} 條路線")
    else:
        st.warning("目前無即時位置資料（可能是非營運時段）")

class Auth():
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key
    def get_auth_header(self):
        return {'content-type':'application/x-www-form-urlencoded','grant_type':'client_credentials','client_id':self.app_id,'client_secret':self.app_key}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2-lat1)
    d_lon = math.radians(lon2-lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(d_lon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def init_session():
    defaults = {
        "selected_filter": None,
        "search_clicked": False,
        "dir_toggle": "去程",
        "user_lat": None,
        "user_lon": None,
        "recent_routes": [],
        "favorite_routes": [],
        "chat_sessions": {},
        "current_session_id": None,
        "show_chat_history": False,
        "font_large": False,
        "current_page": "query",
        "map_last_updated": None,
        "map_filter_routes": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ── 快取函數 ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_route_stops(route_name, token):
    try:
        with open("tainan_stops_cache.json","r",encoding="utf-8") as f:
            c = json.load(f)
            if route_name in c and c[route_name]:
                return c[route_name]
    except FileNotFoundError:
        pass
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_name}?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data:
                return [s['StopName']['Zh_tw'] for s in data[0]['Stops']]
    except:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_bus_data(route_name, token):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Tainan/{route_name}?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

@st.cache_data(ttl=600)
def fetch_weather():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={TAINAN_LAT}&longitude={TAINAN_LON}&current=temperature_2m,weathercode,windspeed_10m&timezone=Asia%2FTaipei"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            cur = res.json().get("current", {})
            temp = cur.get("temperature_2m","?")
            wind = cur.get("windspeed_10m","?")
            wmap = {0:"晴天☀️",1:"大致晴朗🌤️",2:"部分多雲⛅",3:"陰天☁️",45:"有霧🌫️",51:"毛毛雨🌦️",61:"小雨🌧️",63:"中雨🌧️",65:"大雨🌧️",80:"陣雨🌦️",95:"雷雨⛈️"}
            desc = wmap.get(cur.get("weathercode",-1),"未知天氣")
            return f"{desc}，氣溫 {temp}°C，風速 {wind} km/h"
    except:
        pass
    return "無法取得天氣"

@st.cache_data(ttl=60)
def fetch_ubike_all(token):
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    stations, avail_map = [], {}
    try:
        r1 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Tainan?%24format=JSON", headers=headers, timeout=8)
        r2 = requests.get("https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Tainan?%24format=JSON", headers=headers, timeout=8)
        if r1.status_code == 200: stations = r1.json()
        if r2.status_code == 200:
            for av in r2.json(): avail_map[av["StationUID"]] = av
    except:
        pass
    return stations, avail_map

@st.cache_data(ttl=300)
def fetch_all_bus_stops(token):
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Stop/City/Tainan?%24format=JSON"
    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.warning(f"站牌 API 錯誤：{e}")
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
            uid = ub.get("StationUID","")
            av = avail_map.get(uid, {})
            result.append({
                "name": ub.get("StationName",{}).get("Zh_tw",""),
                "available": av.get("AvailableRentBikes", 0),
                "empty": av.get("AvailableReturnBikes", 0),
                "lat": u_lat, "lon": u_lon
            })
    return result

def add_recent_route(route):
    lst = st.session_state.recent_routes
    if route in lst: lst.remove(route)
    lst.insert(0, route)
    st.session_state.recent_routes = lst[:5]

def new_chat_session():
    sid = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.chat_sessions[sid] = {
        "title": f"對話 {datetime.now().strftime('%m/%d %H:%M')}",
        "history": []
    }
    st.session_state.current_session_id = sid
    return sid

# ── 進階路線查詢：直達 + 一次轉乘 ───────────────────────────
@st.cache_data(ttl=3600)
def build_stop_route_index(token):
    """
    建立「站名 → [路線列表]」的索引，用於進階查詢
    需要先跑過快取才有資料
    """
    index = {}  # {站名: [路線名, ...]}
    try:
        with open("tainan_stops_cache.json","r",encoding="utf-8") as f:
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
    """找出同時經過起點和終點的路線（直達）"""
    start_routes = set(stop_index.get(start_stop, []))
    end_routes   = set(stop_index.get(end_stop, []))
    return sorted(start_routes & end_routes)

def find_transfer_routes(stop_index, start_stop, end_stop, max_results=10):
    """
    找出一次轉乘方案：
    起點 → 中繼站（搭路線A）→ 終點（搭路線B）
    """
    start_routes = stop_index.get(start_stop, [])
    end_routes   = stop_index.get(end_stop, [])

    # 起點各路線經過的所有站
    start_route_stops = {}  # {路線A: set(站名)}
    for r in start_routes:
        for stop, routes in stop_index.items():
            if r in routes:
                start_route_stops.setdefault(r, set()).add(stop)

    # 終點各路線經過的所有站
    end_route_stops = {}  # {路線B: set(站名)}
    for r in end_routes:
        for stop, routes in stop_index.items():
            if r in routes:
                end_route_stops.setdefault(r, set()).add(stop)

    results = []
    for rA, stopsA in start_route_stops.items():
        for rB, stopsB in end_route_stops.items():
            if rA == rB:
                continue
            transfer_stops = stopsA & stopsB  # 共同經過的站 = 可轉乘站
            if transfer_stops:
                for ts in sorted(transfer_stops)[:3]:  # 每組方案最多列3個轉乘站
                    results.append({
                        "routeA": rA, "transfer": ts, "routeB": rB
                    })
                    if len(results) >= max_results:
                        return results
    return results

# ── UBike 騎車建議 ────────────────────────────────────────
def check_ubike_suggestion(start_st, end_st, stop_coord_map, ub_stations, ub_avail, bus_wait_sec, bus_travel_sec):
    """
    比較公車總耗時 vs UBike 騎車時間
    bus_wait_sec: 等車時間(秒)
    bus_travel_sec: 預估公車行駛時間(秒，從start到end的站數 × 平均2分鐘)
    回傳建議字串或 None
    """
    if start_st not in stop_coord_map or end_st not in stop_coord_map:
        return None
    s_lat, s_lon = stop_coord_map[start_st]
    e_lat, e_lon = stop_coord_map[end_st]

    # 找起點附近 UBike（可借）
    start_ub = [u for u in get_ubike_near(s_lat, s_lon, ub_stations, ub_avail, 0.4) if u["available"] > 0]
    # 找終點附近 UBike（可還）
    end_ub   = [u for u in get_ubike_near(e_lat, e_lon, ub_stations, ub_avail, 0.4) if u["empty"] > 0]

    if not start_ub or not end_ub:
        return None

    # 用 OSRM 計算實際騎車時間，失敗才用直線估算
    dist_text, bike_min = get_osrm_travel_time(s_lat, s_lon, e_lat, e_lon, mode="bike")
    if bike_min is None:
        dist_km  = haversine(s_lat, s_lon, e_lat, e_lon)
        bike_min = (dist_km / UBIKE_SPEED_KMH) * 60
        dist_text = f"{dist_km:.1f} 公里（直線估算）"

    bus_total_min = (bus_wait_sec + bus_travel_sec) / 60

    if bike_min < bus_total_min * 0.85:
        best_start = start_ub[0]
        best_end   = end_ub[0]
        return (
            f"🚲 **UBike 更快！** 實際騎車約 **{bike_min} 分鐘**（{dist_text}），"
            f"比等公車+搭車（約 {bus_total_min:.0f} 分鐘）更省時。\n"
            f"- 起點 UBike：**{best_start['name']}**（可借 {best_start['available']} 輛）\n"
            f"- 終點 UBike：**{best_end['name']}**（可還 {best_end['empty']} 格）"
        )
    return None

# ── CSS ──────────────────────────────────────────────────
def get_timeline_css(large_font=False):
    base_size = "17px" if large_font else "15px"
    badge_size = "14px" if large_font else "12px"
    tag_size = "13px" if large_font else "11px"
    return f"""
<style>
* {{ box-sizing: border-box; font-family: 'Noto Sans TC', sans-serif; }}
body {{ margin: 0; padding: 8px; background: transparent; }}
.timeline-container {{ position: relative; padding-left: 35px; margin-left: 15px; border-left: 4px solid #4A90E2; padding-top: 10px; padding-bottom: 10px; }}
.timeline-item {{ position: relative; margin-bottom: 18px; }}
.timeline-circle {{ position: absolute; left: -44px; top: 12px; width: 14px; height: 14px; background-color: white; border: 4px solid #4A90E2; border-radius: 50%; z-index: 2; }}
.station-box {{ display: flex; justify-content: space-between; align-items: center; background-color: #FAFAFA; padding: 10px 15px; border-radius: 8px; border: 1px solid #EAEAEA; min-height: 55px; }}
.station-info {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.station-name {{ font-size: {base_size}; font-weight: bold; color: #333333; }}
.bus-tag {{ background-color: #FF5A5F; color: white; padding: 3px 8px; border-radius: 4px; font-size: {tag_size}; font-weight: bold; display: inline-flex; align-items: center; }}
.wheelchair-tag {{ background-color: #2ECC71; color: white; padding: 3px 6px; border-radius: 4px; font-size: {tag_size}; font-weight: bold; display: inline-flex; align-items: center; }}
.no-wheelchair-tag {{ background-color: #95a5a6; color: white; padding: 3px 6px; border-radius: 4px; font-size: {tag_size}; display: inline-flex; align-items: center; }}
.ev-tag {{ background-color: #8e44ad; color: white; padding: 3px 6px; border-radius: 4px; font-size: {tag_size}; font-weight: bold; display: inline-flex; align-items: center; }}
.ubike-tag {{ background-color: #007bff; color: white; padding: 3px 8px; border-radius: 4px; font-size: {tag_size}; font-weight: bold; display: inline-flex; align-items: center; gap: 4px; }}
.time-badge {{ padding: 6px 12px; border-radius: 20px; color: white; font-weight: bold; font-size: {badge_size}; min-width: 90px; text-align: center; display: inline-block; }}
.ts-gray   {{ background-color: #BDBDBD; }}
.ts-orange {{ background-color: #FFA726; animation: pulse 1s infinite; }}
.ts-green  {{ background-color: #66BB6A; }}
.ts-blue   {{ background-color: #5DADE2; }}
.ts-red    {{ background-color: #E74C3C; }}
@keyframes pulse {{ 0%{{opacity:.8}} 50%{{opacity:1}} 100%{{opacity:.8}} }}
</style>
"""

# ── 語音朗讀 JS ──────────────────────────────────────────
def make_tts_html(text):
    safe = text.replace("'", "\\'").replace("\n", " ")
    return f"""
<button onclick="
  var u = new SpeechSynthesisUtterance('{safe}');
  u.lang = 'zh-TW'; u.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
" style="padding:6px 14px;border-radius:6px;background:#6c5ce7;color:white;border:none;cursor:pointer;font-size:13px;margin:4px 0;">
🔊 朗讀公車資訊
</button>
<button onclick="window.speechSynthesis.cancel();"
style="padding:6px 14px;border-radius:6px;background:#b2bec3;color:white;border:none;cursor:pointer;font-size:13px;margin:4px 4px;">
⏹ 停止
</button>
"""

# ══════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    st.set_page_config(page_title="台南公車 AI 助理", page_icon="🚌", layout="wide")
    init_session()

    try:
        a = Auth(app_id, app_key)
        auth_res = requests.post(auth_url, data=a.get_auth_header())
        token = auth_res.json().get("access_token","")
        h = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}

        current_weather = "尚未查詢"
        bus_status = "尚未查詢路線"

        # ════════════════════════════════
        # 側邊欄
        # ════════════════════════════════
        with st.sidebar:
            st.title("🚌 台南公車助理")

            # 字體大小切換
            font_label = "🔡 縮小字體" if st.session_state.font_large else "🔠 放大字體（視障輔助）"
            if st.button(font_label, use_container_width=True):
                st.session_state.font_large = not st.session_state.font_large
                st.rerun()

            # 頁面切換
            is_map = st.session_state.current_page == "map"
            map_btn_label = "🚌 回到查詢頁面" if is_map else "🗺️ 公車即時地圖"
            if st.button(map_btn_label, use_container_width=True):
                st.session_state.current_page = "map" if not is_map else "query"
                st.rerun()

            st.divider()

            # AI 對話記錄
            if st.button("💬 AI 對話記錄", use_container_width=True):
                st.session_state.show_chat_history = not st.session_state.show_chat_history

            if st.session_state.show_chat_history:
                st.subheader("📋 對話記錄")
                if st.button("➕ 新對話", use_container_width=True):
                    new_chat_session()
                    st.session_state.show_chat_history = False
                    st.rerun()
                if st.session_state.chat_sessions:
                    for sid, sess in sorted(st.session_state.chat_sessions.items(), reverse=True):
                        col_t, col_d = st.columns([4,1])
                        with col_t:
                            label = ("▶ " if sid==st.session_state.current_session_id else "") + sess["title"]
                            if st.button(label, key=f"sess_{sid}", use_container_width=True):
                                st.session_state.current_session_id = sid
                                st.session_state.show_chat_history = False
                                st.rerun()
                        with col_d:
                            if st.button("🗑", key=f"del_{sid}"):
                                del st.session_state.chat_sessions[sid]
                                if st.session_state.current_session_id == sid:
                                    st.session_state.current_session_id = None
                                st.rerun()
                else:
                    st.info("尚無對話記錄")
                st.divider()

            # 最愛路線
            if st.session_state.favorite_routes:
                st.subheader("⭐ 最愛路線")
                for fav in st.session_state.favorite_routes:
                    col_f, col_r = st.columns([3,1])
                    with col_f:
                        if st.button(f"🚌 {fav}", key=f"fav_{fav}", use_container_width=True):
                            st.session_state.bus_route_select = fav
                            st.session_state.search_clicked = True
                            add_recent_route(fav)
                            st.rerun()
                    with col_r:
                        if st.button("✕", key=f"unfav_{fav}"):
                            st.session_state.favorite_routes.remove(fav)
                            st.rerun()
                st.divider()

            # 最近查詢
            if st.session_state.recent_routes:
                st.subheader("🕐 最近查詢")
                for r in st.session_state.recent_routes:
                    if st.button(f"🔁 {r}", key=f"recent_{r}", use_container_width=True):
                        st.session_state.bus_route_select = r
                        st.session_state.search_clicked = True
                        add_recent_route(r)
                        st.rerun()
                st.divider()

            # 進階路線查詢
            with st.expander("🔍 進階查詢（站到站）"):
                st.caption("輸入起站與終點，找出直達或轉乘一次的路線")

                stop_index = build_stop_route_index(token)
                all_stop_names = sorted(stop_index.keys()) if stop_index else []

                if not all_stop_names:
                    st.warning("請先到「系統維護」建立站點快取才能使用進階查詢")
                else:
                    adv_start = st.selectbox("出發站", all_stop_names, index=None,
                        placeholder="請選擇或輸入站名...", key="adv_start")
                    adv_end   = st.selectbox("目的站", all_stop_names, index=None,
                        placeholder="請選擇或輸入站名...", key="adv_end")

                    if st.button("🔎 查詢路線", use_container_width=True, key="adv_search"):
                        if not adv_start or not adv_end:
                            st.error("請選擇出發站和目的站")
                        elif adv_start == adv_end:
                            st.error("出發站和目的站不能相同")
                        else:
                            # 直達
                            directs = find_direct_routes(stop_index, adv_start, adv_end)
                            if directs:
                                st.success(f"✅ 直達路線（共 {len(directs)} 條）")
                                for r in directs:
                                    col_r, col_b = st.columns([3,2])
                                    col_r.write(f"🚌 **{r}**")
                                    if col_b.button("查此路線", key=f"adv_go_{r}"):
                                        st.session_state.bus_route_select = r
                                        st.session_state.search_clicked = True
                                        add_recent_route(r)
                                        st.rerun()
                            else:
                                st.info("無直達路線")

                            # 轉乘一次
                            st.write("---")
                            with st.spinner("搜尋轉乘方案中..."):
                                transfers = find_transfer_routes(stop_index, adv_start, adv_end)
                            if transfers:
                                st.warning(f"🔄 轉乘一次方案（共 {len(transfers)} 個）")
                                for t in transfers:
                                    st.write(
                                        f"搭 **{t['routeA']}** → 在 **{t['transfer']}** 轉 **{t['routeB']}**"
                                    )
                            else:
                                st.error("找不到一次轉乘方案，請考慮其他方式")

            # 客運查詢
            with st.expander("🚍 客運查詢"):
                st.caption("選擇業者與起訖站查詢班次")

                # ── 客運 API 函數 ─────────────────────────
                @st.cache_data(ttl=3600)
                def fetch_intercity_routes_by_op(op_id, token):
                    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
                    url = (f"https://tdx.transportdata.tw/api/basic/v2/Bus/Route/InterCity"
                           f"?%24filter=OperatorIDs/any(o:o%20eq%20'{op_id}')&%24format=JSON")
                    try:
                        res = requests.get(url, headers=headers, timeout=10)
                        if res.status_code == 200:
                            return res.json()
                    except:
                        pass
                    return []

                @st.cache_data(ttl=60)
                def fetch_intercity_eta(route_id, token):
                    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
                    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/InterCity/{route_id}?%24format=JSON"
                    try:
                        res = requests.get(url, headers=headers, timeout=8)
                        if res.status_code == 200:
                            return res.json()
                    except:
                        pass
                    return []

                @st.cache_data(ttl=3600)
                def fetch_intercity_stops(route_id, token):
                    headers = {'authorization': f'Bearer {token}', 'Accept-Encoding': 'gzip'}
                    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/InterCity/{route_id}?%24format=JSON"
                    try:
                        res = requests.get(url, headers=headers, timeout=8)
                        if res.status_code == 200:
                            return res.json()
                    except:
                        pass
                    return []

                # ── 業者選單 ──────────────────────────────
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

                op_name = st.selectbox(
                    "選擇客運業者",
                    list(INTERCITY_OPERATORS.keys()),
                    key="ic_operator"
                )
                op_id = INTERCITY_OPERATORS.get(op_name)

                if op_id:
                    with st.spinner(f"載入 {op_name} 路線中..."):
                        ic_routes = fetch_intercity_routes_by_op(op_id, token)

                    if ic_routes:
                        # 建立「起點→終點」選單
                        route_options = {}
                        for r in ic_routes:
                            dep  = r.get("DepartureStopNameZh","")
                            dest = r.get("DestinationStopNameZh","")
                            rname= r.get("RouteName",{}).get("Zh_tw","")
                            rid  = r.get("RouteUID","")
                            label= f"{dep} → {dest}（{rname}）"
                            route_options[label] = rid

                        ic_dep = st.text_input(
                            "起點站（含關鍵字即可）",
                            placeholder="例：台南、嘉義",
                            key="ic_dep"
                        )
                        ic_dest = st.text_input(
                            "目的站（含關鍵字即可）",
                            placeholder="例：台北、高雄",
                            key="ic_dest"
                        )

                        # 過濾符合的路線
                        matched = {
                            label: rid for label, rid in route_options.items()
                            if (not ic_dep  or ic_dep  in label)
                            and (not ic_dest or ic_dest in label)
                        }

                        if ic_dep or ic_dest:
                            if matched:
                                st.success(f"找到 {len(matched)} 條符合路線")
                                for label, rid in list(matched.items())[:10]:
                                    with st.expander(f"🚍 {label}"):
                                        stops_data = fetch_intercity_stops(rid, token)
                                        eta_data   = fetch_intercity_eta(rid, token)
                                        eta_map = {}
                                        for e in eta_data:
                                            sn = e.get("StopName",{}).get("Zh_tw","")
                                            eta_map[sn] = (
                                                e.get("EstimateTime"),
                                                e.get("StopStatus",1)
                                            )
                                        if stops_data:
                                            st.write("**停靠站與到站時間：**")
                                            for dir_data in stops_data[:1]:
                                                for s in dir_data.get("Stops",[]):
                                                    sn = s.get("StopName",{}).get("Zh_tw","")
                                                    eta_s, status = eta_map.get(sn,(None,1))
                                                    if eta_s is not None and status == 0:
                                                        t = "即將進站" if eta_s <= 120 else f"{eta_s//60} 分鐘"
                                                        st.write(f"🟢 **{sn}** — {t}")
                                                    elif status == 3:
                                                        st.write(f"⚫ {sn} — 末班車已過")
                                                    elif status == 4:
                                                        st.write(f"🔴 {sn} — 今日停駛")
                                                    else:
                                                        st.write(f"⚪ {sn} — 尚未發車")
                                        else:
                                            st.info("無站點資料")
                            else:
                                st.warning("找不到符合的路線，請調整關鍵字")
                        else:
                            st.info(f"{op_name} 共有 {len(ic_routes)} 條路線，請輸入起點或目的站篩選")
                    else:
                        st.warning(f"目前查不到 {op_name} 的路線資料")

            # 系統維護
            with st.expander("⚙️ 系統維護"):
                if st.button("🔄 更新全台南站點快取", use_container_width=True):
                    with st.spinner("離線化中..."):
                        all_cache = {}
                        pb = st.progress(0)
                        all_r = list(set(r for rl in ROUTE_CATEGORIES.values() for r in rl))
                        for idx, r_name in enumerate(all_r):
                            s_url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{r_name}?%24format=JSON"
                            try:
                                rr = requests.get(s_url, headers=h)
                                if rr.status_code == 200:
                                    dj = rr.json()
                                    if dj: all_cache[r_name] = [s['StopName']['Zh_tw'] for s in dj[0]['Stops']]
                            except:
                                all_cache[r_name] = []
                            pb.progress((idx+1)/len(all_r))
                        with open("tainan_stops_cache.json","w",encoding="utf-8") as f:
                            json.dump(all_cache, f, ensure_ascii=False, indent=4)
                        st.success("🎉 快取建立成功！")

        # 大字體全局 CSS
        if st.session_state.font_large:
            st.markdown("""
<style>
body, .stMarkdown, .stText, label, .stSelectbox, .stButton button {
    font-size: 19px !important;
}
</style>""", unsafe_allow_html=True)

        # ── 地圖頁面 ──────────────────────────────────────
        if st.session_state.current_page == "map":
            build_map_page(token)
            st.stop()

        # ── 查詢頁面 ──────────────────────────────────────
        st.header("🚌 台南公車即時時刻查詢")

        left_col, right_col = st.columns([1, 3])

        # ════════════════════════════════
        # 左欄
        # ════════════════════════════════
        with left_col:
            st.subheader("🔍 路線篩選")

            def reset_search():
                st.session_state.search_clicked = False

            st.caption("點選顏色或數字篩選：")
            cols1 = st.columns(4)
            if cols1[0].button("綠", use_container_width=True): st.session_state.selected_filter="綠"; reset_search()
            if cols1[1].button("橘", use_container_width=True): st.session_state.selected_filter="橘"; reset_search()
            if cols1[2].button("1",  use_container_width=True): st.session_state.selected_filter="1";  reset_search()
            if cols1[3].button("2",  use_container_width=True): st.session_state.selected_filter="2";  reset_search()

            cols2 = st.columns(4)
            if cols2[0].button("棕", use_container_width=True): st.session_state.selected_filter="棕"; reset_search()
            if cols2[1].button("藍", use_container_width=True): st.session_state.selected_filter="藍"; reset_search()
            if cols2[2].button("3",  use_container_width=True): st.session_state.selected_filter="3";  reset_search()
            if cols2[3].button("4",  use_container_width=True): st.session_state.selected_filter="4";  reset_search()

            cols3 = st.columns(4)
            if cols3[0].button("紅", use_container_width=True): st.session_state.selected_filter="紅"; reset_search()
            if cols3[1].button("黃", use_container_width=True): st.session_state.selected_filter="黃"; reset_search()
            if cols3[2].button("5",  use_container_width=True): st.session_state.selected_filter="5";  reset_search()
            if cols3[3].button("6",  use_container_width=True): st.session_state.selected_filter="6";  reset_search()

            cols4 = st.columns(4)
            if cols4[0].button("市區", use_container_width=True): st.session_state.selected_filter="市區"; reset_search()
            if cols4[1].button("高鐵", use_container_width=True): st.session_state.selected_filter="高鐵"; reset_search()
            if cols4[2].button("7",    use_container_width=True): st.session_state.selected_filter="7";    reset_search()
            if cols4[3].button("8",    use_container_width=True): st.session_state.selected_filter="8";    reset_search()

            cols5 = st.columns(4)
            if cols5[0].button("觀光", use_container_width=True): st.session_state.selected_filter="觀光"; reset_search()
            if cols5[1].button("9",    use_container_width=True): st.session_state.selected_filter="9";    reset_search()
            if cols5[2].button("0",    use_container_width=True): st.session_state.selected_filter="0";    reset_search()

            if st.button("❌ 清除篩選", use_container_width=True):
                st.session_state.selected_filter = None; reset_search()

            cf = st.session_state.selected_filter
            if cf: st.success(f"篩選：【{cf}】")
            else:  st.info("顯示：全部路線")

            # 路線清單
            all_routes = []
            for rl in ROUTE_CATEGORIES.values(): all_routes.extend(rl)
            seen_s = set()
            all_routes = [x for x in all_routes if not (x in seen_s or seen_s.add(x))]

            if cf is None: filtered_routes = all_routes
            elif cf == "市區": filtered_routes = ROUTE_CATEGORIES["市區"]
            elif cf == "高鐵": filtered_routes = ROUTE_CATEGORIES["高鐵快捷"]
            elif cf == "觀光": filtered_routes = ROUTE_CATEGORIES["觀光"]
            else:
                raw = [r for r in all_routes if cf in r]
                if cf.isdigit():
                    def nsort(rs):
                        nums = ''.join(c for c in rs if c.isdigit())
                        return (0 if rs.startswith(cf) else 1, int(nums) if nums else 999, rs)
                    filtered_routes = sorted(raw, key=nsort)
                else:
                    filtered_routes = raw

            route_choice = st.selectbox("選擇路線", filtered_routes, index=None,
                placeholder="請選擇或輸入路線...", key="bus_route_select", on_change=reset_search)

            # 最愛按鈕
            if route_choice:
                fav_list = st.session_state.favorite_routes
                is_fav = route_choice in fav_list
                if st.button("⭐ 已加入最愛" if is_fav else "☆ 加入最愛", use_container_width=True, key="fav_toggle"):
                    if is_fav: fav_list.remove(route_choice)
                    else: fav_list.append(route_choice)
                    st.session_state.favorite_routes = fav_list
                    st.rerun()

            start_st, end_st = None, None
            if route_choice:
                st.session_state.search_clicked = True
                add_recent_route(route_choice)
                all_stops = fetch_route_stops(route_choice, token)
                if all_stops:
                    start_st = st.selectbox("等候站", all_stops, index=0, key="start_select")
                    end_st   = st.selectbox("目的地", all_stops, index=len(all_stops)-1, key="end_select")
                else:
                    st.warning(f"⚠️ 無法載入【{route_choice}】站點。")
            else:
                st.info("請選擇路線")

            st.write("---")

            # GPS 附近站牌
            st.subheader("📍 附近公車站")
            gps_html = """
<button onclick="
  navigator.geolocation.getCurrentPosition(function(pos){
    document.getElementById('lat_disp').value = pos.coords.latitude.toFixed(6);
    document.getElementById('lon_disp').value = pos.coords.longitude.toFixed(6);
  }, function(){ alert('請允許瀏覽器定位權限'); });
" style="width:100%;padding:8px;border-radius:6px;background:#4A90E2;color:white;border:none;cursor:pointer;font-size:13px;font-weight:bold;margin-bottom:8px;">
📡 自動取得座標（複製後貼到下方）
</button>
<div style="font-size:12px;margin-bottom:4px;">緯度：<input id="lat_disp" readonly style="width:130px;padding:3px;border:1px solid #ccc;border-radius:4px;" placeholder="點上方取得"/></div>
<div style="font-size:12px;">經度：<input id="lon_disp" readonly style="width:130px;padding:3px;border:1px solid #ccc;border-radius:4px;" placeholder="點上方取得"/></div>
"""
            st.components.v1.html(gps_html, height=110)
            gps_lat_input = st.text_input("緯度", placeholder="例：22.9997", key="gps_lat_in")
            gps_lon_input = st.text_input("經度", placeholder="例：120.2270", key="gps_lon_in")

            if st.button("🔍 搜尋附近站牌", use_container_width=True):
                try:
                    st.session_state.user_lat = float(gps_lat_input)
                    st.session_state.user_lon = float(gps_lon_input)
                except ValueError:
                    st.error("請輸入有效數字")

            if st.session_state.user_lat and st.session_state.user_lon:
                st.success(f"📍 {st.session_state.user_lat:.5f}, {st.session_state.user_lon:.5f}")
                with st.spinner("搜尋中..."):
                    all_stops_data = fetch_all_bus_stops(token)
                if all_stops_data:
                    nearby = find_nearby_stops(all_stops_data, st.session_state.user_lat, st.session_state.user_lon)
                    if nearby:
                        st.write(f"**找到 {len(nearby)} 個站牌（500m內）：**")
                        for ns in nearby:
                            st.write(f"🚏 **{ns['name']}**（{ns['dist']*1000:.0f}m）")
                    else:
                        st.warning("附近 500m 內無公車站牌")
                else:
                    st.error("無法載入站牌資料")
                if st.button("🗑️ 清除定位", use_container_width=True):
                    st.session_state.user_lat = None
                    st.session_state.user_lon = None
                    st.rerun()

        # ════════════════════════════════
        # 右欄
        # ════════════════════════════════
        with right_col:
            if route_choice and st.session_state.get("search_clicked", False):
                weather_info = fetch_weather()
                current_weather = weather_info
                st.info(f"🌡️ 台南目前天氣：{weather_info}")

                bus_list = fetch_bus_data(route_choice, token)
                if bus_list is not None:
                    dir0 = sorted([x for x in bus_list if x.get("Direction")==0], key=lambda x: x.get('StopSequence',0))
                    dir1 = sorted([x for x in bus_list if x.get("Direction")==1], key=lambda x: x.get('StopSequence',0))
                    dest_0 = dir0[-1].get("StopName",{}).get("Zh_tw","去程") if dir0 else "去程"
                    dest_1 = dir1[-1].get("StopName",{}).get("Zh_tw","回程") if dir1 else "回程"

                    st.subheader(f"🚌 {route_choice} 全線即時動態")

                    cb1, cb2, cb3 = st.columns([1.5,1.5,1])
                    with cb1:
                        if st.button(f"➡️ 往 {dest_0}", use_container_width=True, type="primary" if st.session_state.dir_toggle=="去程" else "secondary"):
                            st.session_state.dir_toggle = "去程"
                    with cb2:
                        if st.button(f"⬅️ 往 {dest_1}", use_container_width=True, type="primary" if st.session_state.dir_toggle=="回程" else "secondary"):
                            st.session_state.dir_toggle = "回程"
                    with cb3:
                        if st.button("🔄 重新整理", use_container_width=True):
                            st.rerun()

                    active_list = dir0 if st.session_state.dir_toggle=="去程" else dir1

                    # 站點座標
                    stop_coord_map = {}
                    try:
                        cr = requests.get(
                            f"https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/Tainan/{route_choice}?%24format=JSON",
                            headers=h, timeout=5)
                        if cr.status_code == 200:
                            target_dir = 0 if st.session_state.dir_toggle=="去程" else 1
                            for rd in cr.json():
                                if rd.get("Direction") == target_dir:
                                    for s in rd.get("Stops",[]):
                                        name = s.get("StopName",{}).get("Zh_tw","")
                                        pos  = s.get("StopPosition",{})
                                        if name and pos.get("PositionLat"):
                                            stop_coord_map[name] = (pos["PositionLat"], pos["PositionLon"])
                    except:
                        pass

                    ub_stations, ub_avail = fetch_ubike_all(token)
                    realtime_map = {item.get("StopName",{}).get("Zh_tw",""): item for item in active_list}
                    all_stops_raw = fetch_route_stops(route_choice, token)
                    full_stop_list = all_stops_raw or [item.get("StopName",{}).get("Zh_tw","") for item in active_list]

                    if full_stop_list:
                        # 計算 UBike 建議
                        ubike_suggestion = None
                        if start_st and end_st and start_st != end_st:
                            # 估算等車時間（從 start_st 的 eta）
                            start_item = realtime_map.get(start_st, {})
                            bus_wait = start_item.get("EstimateTime") or 0
                            # 估算行駛時間（站數差 × 120秒）
                            if start_st in full_stop_list and end_st in full_stop_list:
                                idx_s = full_stop_list.index(start_st)
                                idx_e = full_stop_list.index(end_st)
                                bus_travel = abs(idx_e - idx_s) * 120
                            else:
                                bus_travel = 600
                            ubike_suggestion = check_ubike_suggestion(
                                start_st, end_st, stop_coord_map, ub_stations, ub_avail, bus_wait, bus_travel)

                        if ubike_suggestion:
                            st.success(ubike_suggestion)

                        # 建立朗讀文字
                        tts_lines = [f"路線 {route_choice}，往 {dest_0 if st.session_state.dir_toggle=='去程' else dest_1}方向。"]

                        html_buffer = get_timeline_css(st.session_state.font_large)
                        html_buffer += '<div class="timeline-container">'
                        ai_log_list = []

                        for s_name in full_stop_list:
                            item   = realtime_map.get(s_name, {})
                            eta    = item.get("EstimateTime")
                            status = item.get("StopStatus", 1)
                            plate  = item.get("PlateNumb","")
                            v_type = item.get("VehicleType")
                            is_ev  = item.get("IsElectric", False) or (v_type == 5)

                            # ── 無障礙判斷（大巴預設有，小巴/中巴看 IsLowFloor）──
                            if v_type == 1:   # 大巴 → 預設有無障礙
                                is_low = True
                                car_size = "大巴"
                            elif v_type == 2: # 中巴
                                is_low = item.get("IsLowFloor", False)
                                car_size = "中巴"
                            elif v_type == 3: # 小巴
                                is_low = item.get("IsLowFloor", False)
                                car_size = "小巴"
                            else:             # 未知/其他 → 看 IsLowFloor
                                is_low = item.get("IsLowFloor", False)
                                car_size = "大巴"

                            # ── StopStatus 對照 ──────────────────────
                            if eta is not None and status == 0:
                                if eta <= 30:
                                    time_text = "即將進站"; bc = "ts-orange"
                                elif eta <= 120:
                                    time_text = "即將進站"; bc = "ts-orange"
                                else:
                                    time_text = f"{eta//60} 分鐘"; bc = "ts-green"
                            elif status == 1:
                                time_text = "尚未發車"; bc = "ts-gray"
                            elif status == 2:
                                time_text = "交管不停靠"; bc = "ts-gray"
                            elif status == 3:
                                time_text = "末班車已過"; bc = "ts-red"
                            elif status == 4:
                                time_text = "今日停駛"; bc = "ts-red"
                            else:
                                time_text = "尚未發車"; bc = "ts-gray"

                            bus_html = ""
                            if plate and plate not in ("🧱","無車牌"):
                                wc_html = '<span class="wheelchair-tag">♿ 無障礙</span>' if is_low else '<span class="no-wheelchair-tag">🚌 一般車</span>'
                                ev_html = '<span class="ev-tag">⚡ 電動</span>' if is_ev else ''
                                bus_html = f'<span class="bus-tag">🚌 {plate} ({car_size})</span>{wc_html}{ev_html}'

                            ubike_html = ""
                            if s_name in stop_coord_map:
                                s_lat, s_lon = stop_coord_map[s_name]
                                for ub in get_ubike_near(s_lat, s_lon, ub_stations, ub_avail):
                                    ubike_html += f'<span class="ubike-tag">🚲 可借:{ub["available"]} 可還:{ub["empty"]}</span>'

                            html_buffer += f"""
<div class="timeline-item">
  <div class="timeline-circle"></div>
  <div class="station-box">
    <div class="station-info">
      <span class="station-name">{s_name}</span>
      {bus_html}{ubike_html}
    </div>
    <span class="time-badge {bc}">{time_text}</span>
  </div>
</div>
"""
                            if start_st and s_name == start_st:
                                ai_log_list.append({"站": s_name, "動態": time_text, "車牌": plate or "無", "無障礙": "是" if is_low else "否", "電動": "是" if is_ev else "否"})
                                tts_lines.append(f"等候站 {s_name}，{time_text}。{'無障礙低底盤。' if is_low else ''}{'電動公車。' if is_ev else ''}")

                        html_buffer += "</div>"
                        st.components.v1.html(html_buffer, height=600, scrolling=True)

                        # 朗讀按鈕
                        tts_text = "".join(tts_lines)
                        st.components.v1.html(make_tts_html(tts_text), height=60)

                        bus_status = f"路線：{route_choice}（往{st.session_state.dir_toggle}）。等候站動態：{json.dumps(ai_log_list, ensure_ascii=False)}"
                    else:
                        st.info("暫時無此方向站點資訊。")
                else:
                    st.error("無法取得即時動態。")
            else:
                st.info("👈 請從左側選擇路線開始查詢")

        # ════════════════════════════════
        # AI 問答區
        # ════════════════════════════════
        st.divider()
        st.subheader("🤖 AI 助理")

        if st.session_state.current_session_id is None or \
           st.session_state.current_session_id not in st.session_state.chat_sessions:
            new_chat_session()

        sid  = st.session_state.current_session_id
        sess = st.session_state.chat_sessions[sid]
        st.caption(f"目前對話：**{sess['title']}**")

        for msg in sess["history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_q = st.chat_input("有什麼我可以幫忙的嗎？")
        if user_q:
            with st.chat_message("user"):
                st.write(user_q)
            with st.spinner("思考中..."):
                try:
                    # ✅ 完整歷史都傳給 AI，確保記憶前幾句
                    system_msg = (
                        "你是一位專業友善的台南公車導遊，擁有完整的對話記憶。"
                        "請根據整段對話歷史，用流暢中文回答使用者問題。"
                        f"\n【目前天氣】{current_weather}"
                        f"\n【公車狀態】{bus_status}"
                    )
                    msgs = [{"role":"system","content": system_msg}]
                    # 傳入完整歷史（最多保留最近20則避免超過 token 限制）
                    history = sess["history"][-20:]
                    for hst in history:
                        msgs.append({"role": hst["role"], "content": hst["content"]})
                    msgs.append({"role":"user","content": user_q})

                    resp = client.chat.completions.create(
                        messages=msgs,
                        model="llama-3.3-70b-versatile",
                        max_tokens=1024
                    )
                    ai_text = resp.choices[0].message.content

                    if len(sess["history"]) == 0:
                        sess["title"] = user_q[:20] + ("..." if len(user_q)>20 else "")

                    with st.chat_message("assistant"):
                        st.write(ai_text)

                    sess["history"].append({"role":"user","content": user_q})
                    sess["history"].append({"role":"assistant","content": ai_text})
                except Exception as e:
                    st.error(f"AI 錯誤：{e}")

    except Exception as e:
        st.error(f"發生系統錯誤：{e}")
