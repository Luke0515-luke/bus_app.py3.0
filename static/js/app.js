// ══════════════════════════════════════════════════════════
// 台南公車 AI 助理 — app.js
// ══════════════════════════════════════════════════════════

const ROUTE_COLOR_MAP = [
  ['黃','#F1C40F'],['棕','#8B4513'],['綠','#27AE60'],['橘','#E67E22'],
  ['藍','#2980B9'],['紅','#E74C3C'],['H','#9B59B6'],['0','#1ABC9C'],
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
function getRouteColor(name) {
  for (const [p, c] of ROUTE_COLOR_MAP) if (name.startsWith(p)) return c;
  return '#7F8C8D';
}

const state = {
  fontLarge: false, currentPage: 'query',
  selectedFilter: null, routeChoice: '', dirToggle: '去程',
  destNames: { '去程': '去程', '回程': '回程' },
  favorites: [], recent: [],
  mapInited: false,
  mapActiveRoutes: new Set(), mapAllRoutes: [],
  mapBusData: [], mapStaticLoaded: false,
  leafletMap: null, busLayer: null, shapeLayer: null, stopLayer: null,
  ttsText: '',
  currentUser: null,
};

async function api(url, opts) {
  const res = await fetch(url, opts);
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { data });
  return data;
}
function el(id) { return document.getElementById(id); }
function esc(s) {
  return (s || '').toString().replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── 初始化 ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  bindStaticEvents();
  loadFilterRoutes(null);
  loadFavorites();
  loadRecent();
  loadChatSessions();
  loadChatCurrent();
  loadAdvancedStops();
  checkAuthState();
});

function bindStaticEvents() {
  el('btn-font-toggle').addEventListener('click', toggleFont);
  el('btn-page-toggle').addEventListener('click', togglePage);
  el('btn-map-home').addEventListener('click', () => switchPage('query'));
  el('btn-map-refresh').addEventListener('click', () => loadMapBuses());

  // 地圖圖層切換
  el('map-show-stops').addEventListener('change', () => {
    if (state.stopLayer) {
      if (el('map-show-stops').checked) state.stopLayer.addTo(state.leafletMap);
      else state.leafletMap.removeLayer(state.stopLayer);
    }
  });
  el('map-show-shapes').addEventListener('change', () => {
    if (state.shapeLayer) {
      if (el('map-show-shapes').checked) state.shapeLayer.addTo(state.leafletMap);
      else state.leafletMap.removeLayer(state.shapeLayer);
    }
  });

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedFilter = btn.dataset.f;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadFilterRoutes(state.selectedFilter);
      el('filter-status').textContent = `篩選：【${state.selectedFilter}】`;
    });
  });

  el('btn-clear-filter').addEventListener('click', () => {
    state.selectedFilter = null;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    loadFilterRoutes(null);
    el('filter-status').textContent = '顯示：全部路線';
  });

  el('route-select').addEventListener('change', e => {
    if (e.target.value) selectRoute(e.target.value);
  });

  el('btn-fav-toggle').addEventListener('click', toggleFavorite);
  el('btn-refresh-status').addEventListener('click', refreshStatus);
  el('btn-dir0').addEventListener('click', () => setDirection('去程'));
  el('btn-dir1').addEventListener('click', () => setDirection('回程'));
  el('btn-gps').addEventListener('click', getGPSLocation);
  el('btn-search-nearby').addEventListener('click', searchNearbyStops);
  el('btn-chat-history-toggle').addEventListener('click', () => el('chat-history-panel').classList.toggle('hidden'));
  el('btn-new-chat').addEventListener('click', newChatSession);
  el('btn-chat-send').addEventListener('click', sendChat);
  el('chat-input').addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
  el('ic-operator').addEventListener('change', loadIntercityRoutes);
  el('ic-dep').addEventListener('input', renderIntercityMatches);
  el('ic-dest').addEventListener('input', renderIntercityMatches);
  el('btn-update-cache').addEventListener('click', updateCache);
  el('btn-build-map-cache').addEventListener('click', buildMapCache);
  el('btn-adv-search').addEventListener('click', searchAdvanced);
  el('map-search-box').addEventListener('input', e => renderMapPanel(e.target.value));

  // 手機漢堡
  const mobileBtn = el('btn-mobile-menu');
  const backdrop  = el('sidebar-backdrop');
  const sidebar   = el('sidebar');
  if (mobileBtn) {
    mobileBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      backdrop.classList.toggle('visible');
    });
    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('open');
      backdrop.classList.remove('visible');
    });
  }
}

// ── 字體 / 頁面切換 ───────────────────────────────────────
function toggleFont() {
  state.fontLarge = !state.fontLarge;
  document.body.classList.toggle('large-font', state.fontLarge);
  el('btn-font-toggle').textContent = state.fontLarge ? '🔡 縮小字體' : '🔠 放大字體（視障輔助）';
}

function togglePage() {
  switchPage(state.currentPage === 'query' ? 'map' : 'query');
}

function switchPage(page) {
  state.currentPage = page;
  el('page-query').classList.toggle('hidden', page !== 'query');
  el('page-map').classList.toggle('hidden', page !== 'map');
  el('btn-page-toggle').textContent = page === 'map' ? '🔍 回查詢頁' : '🗺️ 公車即時地圖';
  if (page === 'map') initMapPageIfNeeded();
}

// ── 路線篩選 ──────────────────────────────────────────────
async function loadFilterRoutes(filter) {
  const params = filter ? `?filter=${encodeURIComponent(filter)}` : '';
  const data = await api(`/api/filter_routes${params}`);
  const sel = el('route-select');
  sel.innerHTML = '<option value="">請選擇或輸入路線...</option>' +
    data.routes.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  if (state.routeChoice) sel.value = state.routeChoice;
}

// ── 路線選擇 ──────────────────────────────────────────────
async function selectRoute(route) {
  state.routeChoice = route;
  const stopsData = await api(`/api/route_stops?route=${encodeURIComponent(route)}`);
  el('stop-select-body').classList.remove('hidden');
  el('route-hint').classList.add('hidden');
  const ss = el('start-select');
  const es = el('end-select');
  ss.innerHTML = stopsData.stops.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  es.innerHTML = stopsData.stops.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  if (stopsData.stops.length > 1) es.selectedIndex = stopsData.stops.length - 1;
  const favBtn = el('btn-fav-toggle');
  favBtn.classList.remove('hidden');
  favBtn.textContent = state.favorites.includes(route) ? '⭐ 已加入最愛' : '☆ 加入最愛';
  await loadStatus(route, state.dirToggle);
}

async function loadStatus(route, direction) {
  const ss = el('start-select').value;
  const es = el('end-select').value;
  const params = new URLSearchParams({ route, direction, start_st: ss, end_st: es });
  const data = await api(`/api/route_status?${params}`);
  if (data.empty) return;
  state.destNames['去程'] = data.dest0;
  state.destNames['回程'] = data.dest1;
  el('btn-dir0').textContent = `➡️ 往 ${data.dest0}`;
  el('btn-dir1').textContent = `⬅️ 往 ${data.dest1}`;
  el('btn-dir0').classList.toggle('active', direction === '去程');
  el('btn-dir1').classList.toggle('active', direction === '回程');
  el('status-title').textContent = `🚌 ${route} 全線即時動態看板`;
  el('status-box').classList.remove('hidden');
  el('status-empty').classList.add('hidden');
  el('weather-box').textContent = `🌡️ 當前天氣：${data.weather}`;
  el('weather-box').classList.remove('hidden');
  if (data.ubike_suggestion) {
    el('ubike-suggestion').textContent = data.ubike_suggestion;
    el('ubike-suggestion').classList.remove('hidden');
  } else {
    el('ubike-suggestion').classList.add('hidden');
  }
  state.ttsText = data.tts_text || '';
  renderTimeline(data.stops);
}

function renderTimeline(stops) {
  el('timeline-container').innerHTML = stops.map((s, i) => {
    let busTags = '';
    if (s.has_bus) {
      const wc = s.is_low
        ? `<span class="tag tag-wc">♿ 無障礙</span>`
        : `<span class="tag tag-wc2">一般車</span>`;
      const ev = s.is_ev ? `<span class="tag tag-ev">⚡ 電動</span>` : '';
      busTags = `
        <div class="bus-banner">
          🚌 <span class="bus-plate">${esc(s.plate)} (${esc(s.car_size)})</span>
          ${wc}${ev}
        </div>`;
    }
    const ubHtml = (s.ubikes || []).map(u =>
      `<span class="tag tag-ub">🚲 可借:${u.available} 可還:${u.empty}</span>`
    ).join('');
    const waitMark = s.is_waiting_stop ? ' waiting-stop' : '';
    return `
<div class="tl-row${waitMark}">
  <div class="tl-seq">${i + 1}</div>
  <div class="tl-mid">
    <div class="tl-name">${esc(s.name)}</div>
    ${busTags}
    ${ubHtml ? `<div class="tl-tags">${ubHtml}</div>` : ''}
  </div>
  <span class="tl-badge ${esc(s.badge_class)}">${esc(s.eta_text)}</span>
</div>`;
  }).join('');
}

async function refreshStatus() {
  if (state.routeChoice) await loadStatus(state.routeChoice, state.dirToggle);
}
function setDirection(dir) {
  state.dirToggle = dir;
  el('btn-dir0').classList.toggle('active', dir === '去程');
  el('btn-dir1').classList.toggle('active', dir === '回程');
  if (state.routeChoice) loadStatus(state.routeChoice, dir);
}

// ── 最愛 / 最近 ───────────────────────────────────────────
async function loadFavorites() {
  const data = await api('/api/favorites');
  state.favorites = data.favorites || [];
  const sec  = el('favorites-section');
  const list = el('favorites-list');
  if (!state.favorites.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  list.innerHTML = state.favorites.map(r =>
    `<button class="btn btn-block sidebar-route-btn" onclick="selectRouteFromSidebar('${esc(r)}')">${esc(r)}</button>`
  ).join('');
}
async function loadRecent() {
  const data = await api('/api/recent');
  state.recent = data.recent || [];
  const sec  = el('recent-section');
  const list = el('recent-list');
  if (!state.recent.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  list.innerHTML = state.recent.map(r =>
    `<button class="btn btn-block sidebar-route-btn" onclick="selectRouteFromSidebar('${esc(r)}')">${esc(r)}</button>`
  ).join('');
}
async function selectRouteFromSidebar(route) {
  el('route-select').value = route;
  await selectRoute(route);
  if (window.innerWidth <= 900) {
    el('sidebar').classList.remove('open');
    el('sidebar-backdrop').classList.remove('visible');
  }
}
async function toggleFavorite() {
  if (!state.routeChoice) return;
  const data = await api('/api/favorites/toggle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ route: state.routeChoice })
  });
  state.favorites = data.favorites || [];
  el('btn-fav-toggle').textContent = data.is_favorite ? '⭐ 已加入最愛' : '☆ 加入最愛';
  loadFavorites();
}

// ── GPS ───────────────────────────────────────────────────
function getGPSLocation() {
  if (!navigator.geolocation) { alert('您的瀏覽器不支援 GPS'); return; }
  navigator.geolocation.getCurrentPosition(pos => {
    const lat = pos.coords.latitude.toFixed(6);
    const lon = pos.coords.longitude.toFixed(6);
    el('lat-disp').value = lat; el('lon-disp').value = lon;
    el('gps-lat-in').value = lat; el('gps-lon-in').value = lon;
    doNearbySearch(lat, lon);
  }, () => alert('無法取得位置，請確認已授權定位'));
}
async function searchNearbyStops() {
  const lat = el('gps-lat-in').value.trim();
  const lon = el('gps-lon-in').value.trim();
  if (!lat || !lon) { alert('請輸入或取得座標'); return; }
  await doNearbySearch(lat, lon);
}
async function doNearbySearch(lat, lon) {
  const result = el('nearby-result');
  result.innerHTML = '<div class="caption">搜尋中...</div>';
  try {
    const data = await api(`/api/nearby_stops?lat=${lat}&lon=${lon}`);
    if (!data.nearby || !data.nearby.length) {
      result.innerHTML = '<div class="warning-box">附近 500m 內無公車站牌</div>';
      return;
    }
    result.innerHTML = '<div class="success-box">找到以下站牌：</div>' +
      data.nearby.map(s => `<div class="stop-item">🚏 <b>${esc(s.name)}</b>（${(s.dist * 1000).toFixed(0)}m）</div>`).join('');
  } catch (e) {
    result.innerHTML = `<div class="error-box">搜尋失敗：${esc(e.message)}</div>`;
  }
}

// ── TTS ───────────────────────────────────────────────────
el('btn-tts-speak') && document.addEventListener('DOMContentLoaded', () => {
  el('btn-tts-speak').addEventListener('click', () => {
    if (!state.ttsText) return;
    const utt = new SpeechSynthesisUtterance(state.ttsText);
    utt.lang = 'zh-TW'; utt.rate = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utt);
  });
  el('btn-tts-stop').addEventListener('click', () => window.speechSynthesis.cancel());
});

// ── 進階查詢 ─────────────────────────────────────────────
async function loadAdvancedStops() {
  try {
    const data = await api('/api/advanced_search/stops');
    const opts = data.stops.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
    el('adv-start').innerHTML = '<option value="">請選擇或輸入站名...</option>' + opts;
    el('adv-end').innerHTML   = '<option value="">請選擇或輸入站名...</option>' + opts;
  } catch (e) {}
}
async function searchAdvanced() {
  const start = el('adv-start').value;
  const end   = el('adv-end').value;
  const result = el('adv-search-result');
  if (!start || !end) { result.innerHTML = '<div class="warning-box">請選擇出發站和目的站</div>'; return; }
  if (start === end)  { result.innerHTML = '<div class="warning-box">出發站和目的站不能相同</div>'; return; }
  result.innerHTML = '<div class="caption">查詢中...</div>';
  try {
    const data = await api(`/api/advanced_search?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
    let html = '';
    if (data.directs.length) {
      html += '<div class="success-box">✅ 直達路線：</div>';
      html += data.directs.map(r =>
        `<div class="stop-item">🚌 <b>${esc(r)}</b> <button class="btn btn-sm" onclick="selectRouteFromSidebar('${esc(r)}')">查詢</button></div>`
      ).join('');
    } else {
      html += '<div class="info-box">無直達路線</div>';
    }
    if (data.transfers.length) {
      html += '<div class="info-box" style="margin-top:6px;">🔄 轉乘一次方案：</div>';
      html += data.transfers.map(t =>
        `<div class="stop-item">搭 <b>${esc(t.routeA)}</b> → 在 <b>${esc(t.transfer)}</b> 轉 <b>${esc(t.routeB)}</b></div>`
      ).join('');
    }
    result.innerHTML = html;
  } catch (e) {
    result.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}

// ── 客運 ──────────────────────────────────────────────────
let icRoutesCache = [];
async function loadIntercityRoutes() {
  const opId = el('ic-operator').value;
  const body = el('ic-body'); const result = el('ic-result');
  icRoutesCache = []; result.innerHTML = '';
  if (!opId) { body.classList.add('hidden'); return; }
  body.classList.remove('hidden');
  result.innerHTML = '<div class="caption">載入路線中...</div>';
  const data = await api(`/api/intercity/routes?op_id=${encodeURIComponent(opId)}`);
  icRoutesCache = data.routes;
  result.innerHTML = `<div class="info-box">共有 ${data.total} 條路線，請輸入起點或目的站篩選</div>`;
}
function renderIntercityMatches() {
  const dep = el('ic-dep').value.trim(); const dest = el('ic-dest').value.trim();
  const result = el('ic-result');
  if (!icRoutesCache.length) return;
  if (!dep && !dest) { result.innerHTML = `<div class="info-box">共有 ${icRoutesCache.length} 條路線，請輸入起點或目的站篩選</div>`; return; }
  const matched = icRoutesCache.filter(r => (!dep || r.label.includes(dep)) && (!dest || r.label.includes(dest)));
  if (!matched.length) { result.innerHTML = '<div class="warning-box">找不到符合的路線</div>'; return; }
  result.innerHTML = `<div class="success-box">找到 ${matched.length} 條符合路線</div>` +
    matched.slice(0, 10).map(r => `
      <details class="expander ic-item">
        <summary>🚍 ${esc(r.label)}</summary>
        <div class="ic-detail" data-rid="${esc(r.rid)}"><div class="caption">點開後載入中...</div></div>
      </details>`).join('');
  result.querySelectorAll('details.ic-item').forEach(d => {
    d.addEventListener('toggle', async () => {
      if (!d.open) return;
      const box = d.querySelector('.ic-detail');
      if (box.dataset.loaded) return;
      const data = await api(`/api/intercity/detail?rid=${encodeURIComponent(box.dataset.rid)}`);
      box.dataset.loaded = '1';
      if (!data.has_data || !data.stops.length) { box.innerHTML = '<div class="info-box">無站點資料</div>'; return; }
      box.innerHTML = '<div class="caption"><b>停靠站與到站時間：</b></div>' +
        data.stops.map(s => `<div class="stop-item">${s.icon} <b>${esc(s.name)}</b> — ${esc(s.text)}</div>`).join('');
    });
  });
}

// ── 系統維護 ─────────────────────────────────────────────
async function updateCache() {
  const box = el('cache-status'); const btn = el('btn-update-cache');
  btn.disabled = true;
  box.innerHTML = '<div class="caption">離線化中，請稍候...</div>';
  try {
    const data = await api('/api/update_cache', { method: 'POST' });
    box.innerHTML = `<div class="success-box">🎉 快取建立成功！共 ${data.count} 條路線</div>`;
  } catch (e) {
    box.innerHTML = `<div class="error-box">建立失敗：${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
}
async function buildMapCache() {
  const box = el('cache-status'); const btn = el('btn-build-map-cache');
  btn.disabled = true;
  box.innerHTML = '<div class="caption">建立地圖靜態快取中（約 2-5 分鐘）...</div>';
  try {
    const data = await api('/api/map_static/build', { method: 'POST' });
    box.innerHTML = `<div class="success-box">🎉 地圖快取完成！${data.stops} 個站點、${data.routes} 條路線</div>`;
    state.mapStaticLoaded = false; // 強制重新載入
  } catch (e) {
    box.innerHTML = `<div class="error-box">建立失敗：${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
}

// ── AI 助理 ──────────────────────────────────────────────
async function loadChatSessions() {
  const data = await api('/api/chat/sessions');
  el('chat-session-list').innerHTML = data.sessions.map(s => `
    <div class="sess-item">
      <button class="btn sess-select ${s.is_current ? 'active' : ''}" data-sid="${esc(s.sid)}">${s.is_current ? '▶ ' : ''}${esc(s.title)}</button>
      <button class="btn sess-del" data-sid="${esc(s.sid)}">🗑</button>
    </div>`).join('');
  document.querySelectorAll('.sess-select').forEach(b => b.addEventListener('click', async () => {
    await api('/api/chat/sessions/switch', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ sid: b.dataset.sid }) });
    el('chat-history-panel').classList.add('hidden');
    await loadChatSessions(); await loadChatCurrent();
  }));
  document.querySelectorAll('.sess-del').forEach(b => b.addEventListener('click', async () => {
    await api('/api/chat/sessions/delete', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ sid: b.dataset.sid }) });
    await loadChatSessions(); await loadChatCurrent();
  }));
}
async function loadChatCurrent() {
  const data = await api('/api/chat/sessions/current');
  el('chat-current-title').textContent = data.title;
  const box = el('chat-messages');
  box.innerHTML = data.history.map(m => `<div class="chat-msg ${m.role}">${esc(m.content)}</div>`).join('');
  box.scrollTop = box.scrollHeight;
}
async function newChatSession() {
  await api('/api/chat/sessions/new', { method: 'POST' });
  await loadChatSessions(); await loadChatCurrent();
}
async function sendChat() {
  const input = el('chat-input'); const q = input.value.trim();
  if (!q) return; input.value = '';
  const box = el('chat-messages');
  box.insertAdjacentHTML('beforeend', `<div class="chat-msg user">${esc(q)}</div>`);
  box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant" id="chat-thinking">思考中...</div>`);
  box.scrollTop = box.scrollHeight;
  try {
    const data = await api('/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ query: q }) });
    const t = el('chat-thinking'); if (t) t.remove();
    box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant">${esc(data.reply || data.error || 'AI 錯誤')}</div>`);
    if (data.title) el('chat-current-title').textContent = data.title;
    loadChatSessions();
  } catch (e) {
    const t = el('chat-thinking'); if (t) t.remove();
    box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant">AI 錯誤：${esc(e.message)}</div>`);
  }
  box.scrollTop = box.scrollHeight;
}

// ══════════════════════════════════════════════════════════
// 地圖頁（電腦版和手機版完全相同邏輯）
// 靜態快取（站點+路線）從伺服器共用，只有公車位置才刷新
// ══════════════════════════════════════════════════════════
function initMapPageIfNeeded() {
  if (state.mapInited) { loadMapBuses(); return; }
  state.mapInited = true;
  state.leafletMap = L.map('leaflet-map', { zoomControl: true }).setView([22.9997, 120.2270], 13);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO', subdomains: 'abcd', maxZoom: 19
  }).addTo(state.leafletMap);
  state.busLayer   = L.layerGroup().addTo(state.leafletMap);
  state.shapeLayer = L.layerGroup().addTo(state.leafletMap);
  state.stopLayer  = L.layerGroup().addTo(state.leafletMap);
  // 先載入靜態快取（站點+路線），再載入公車位置
  loadMapStatic().then(() => loadMapBuses());
}

// ── 靜態快取：站點 + 路線軌跡（伺服器儲存，共用不重複抓）
async function loadMapStatic() {
  if (state.mapStaticLoaded) return;
  el('map-panel-stats').textContent = '載入站點與路線資料...';
  try {
    const data = await api('/api/map_static');
    state.mapStaticLoaded = true;

    // 畫路線軌跡
    state.shapeLayer.clearLayers();
    (data.shapes || []).forEach(sh => {
      if (!sh.points || !sh.points.length) return;
      L.polyline(sh.points.map(p => [p[0], p[1]]), { color: sh.color, weight: 3, opacity: 0.75 })
        .bindTooltip(sh.route, { sticky: true })
        .addTo(state.shapeLayer);
    });

    // 畫站點（小圓點 + 點選顯示站名）
    state.stopLayer.clearLayers();
    (data.stops || []).forEach(s => {
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:7px;height:7px;background:#fff;border:2px solid #4A90E2;border-radius:50%;opacity:0.85;"></div>`,
        iconSize: [7, 7], iconAnchor: [3, 3]
      });
      L.marker([s.lat, s.lon], { icon })
        .bindTooltip(s.name, { permanent: false, direction: 'top', offset: [0, -6] })
        .bindPopup(`<b>🚏 ${esc(s.name)}</b>`)
        .addTo(state.stopLayer);
    });

    state.mapAllRoutes = data.routes || [];
    state.mapActiveRoutes = new Set(state.mapAllRoutes);
    if (data.built_at) {
      el('map-caption').textContent = `站點資料：${data.built_at.slice(0,16).replace('T',' ')}`;
    }
  } catch (e) {
    el('map-panel-stats').textContent = '靜態快取尚未建立，請至系統維護建立';
    state.mapAllRoutes = [];
  }
}

// ── 即時公車位置（每次更新只抓這個）────────────────────────
async function loadMapBuses() {
  el('map-panel-stats').textContent = '更新公車位置中...';
  try {
    // 一次抓全台南所有路線公車（不傳 routes 參數 = 全部）
    const data = await api('/api/map_data');
    state.mapBusData = data.buses || [];

    // 合併靜態已知路線 + 這次實際有資料的路線
    const liveRoutes = new Set(data.routes || []);
    state.mapAllRoutes.forEach(r => liveRoutes.add(r));
    state.mapAllRoutes = [...liveRoutes].sort();
    // 維持原有選取狀態（全選或部分選取）
    if (state.mapActiveRoutes.size === 0) {
      state.mapActiveRoutes = new Set(state.mapAllRoutes);
    }

    drawMapBuses();
    renderMapPanel(el('map-search-box').value);
    el('map-caption').textContent = `公車位置更新：${data.now}`;
  } catch (e) {
    el('map-panel-stats').textContent = '更新失敗';
  }
}

function makeBusIcon(color) {
  return L.divIcon({
    className: '',
    html: `<div style="width:16px;height:16px;background:${color};border:2.5px solid rgba(255,255,255,0.9);border-radius:50%;box-shadow:0 0 5px ${color};"></div>`,
    iconSize: [16, 16], iconAnchor: [8, 8]
  });
}

function drawMapBuses() {
  state.busLayer.clearLayers();
  let total = 0;
  state.mapBusData.forEach(b => {
    if (!state.mapActiveRoutes.has(b.route)) return;
    L.marker([b.lat, b.lon], { icon: makeBusIcon(b.color) })
      .bindPopup(`<div class="bus-popup">
        <b>🚌 ${esc(b.route)}</b><br>
        <span class="tag" style="background:${b.color}">車牌：${esc(b.plate)}</span>
        <span class="tag" style="background:#555">方向：${esc(b.dir)}</span>
        <span class="tag" style="background:#333">速度：${esc(String(b.speed))} km/h</span>
      </div>`, { maxWidth: 200 })
      .bindTooltip(`${esc(b.route)} ${esc(b.plate)}`)
      .addTo(state.busLayer);
    total++;
  });
  el('map-panel-stats').textContent = `顯示 ${state.mapActiveRoutes.size} 條路線・${total} 台公車`;
}

function renderMapPanel(filterText) {
  const list = el('map-route-list');
  list.innerHTML = '';
  const cnt = {};
  state.mapBusData.forEach(b => { if (state.mapActiveRoutes.has(b.route)) cnt[b.route] = (cnt[b.route] || 0) + 1; });

  // 全選 / 取消全選
  const allItem = document.createElement('div');
  const allActive = state.mapActiveRoutes.size === state.mapAllRoutes.length;
  allItem.className = 'route-item' + (allActive ? ' active' : '');
  allItem.innerHTML = `<div class="route-dot" style="background:#fff;"></div><span>全部路線</span><span class="route-count">${state.mapAllRoutes.length}</span>`;
  allItem.onclick = () => {
    if (state.mapActiveRoutes.size === state.mapAllRoutes.length) state.mapActiveRoutes.clear();
    else state.mapAllRoutes.forEach(r => state.mapActiveRoutes.add(r));
    renderMapPanel(filterText); drawMapBuses();
  };
  list.appendChild(allItem);

  state.mapAllRoutes.forEach(route => {
    if (filterText && !route.includes(filterText)) return;
    const color = getRouteColor(route);
    const n = cnt[route] || 0;
    const item = document.createElement('div');
    item.className = 'route-item' + (state.mapActiveRoutes.has(route) ? ' active' : '');
    item.innerHTML = `<div class="route-dot" style="background:${color};"></div><span>${esc(route)}</span><span class="route-count">${n}</span>`;
    item.onclick = () => {
      if (state.mapActiveRoutes.has(route)) state.mapActiveRoutes.delete(route);
      else state.mapActiveRoutes.add(route);
      drawMapBuses(); renderMapPanel(filterText);
    };
    list.appendChild(item);
  });
}

// ══════════════════════════════════════════════════════════
// 帳號系統
// ══════════════════════════════════════════════════════════
async function checkAuthState() {
  try {
    const data = await api('/api/auth/me');
    state.currentUser = data.logged_in ? data : null;
    renderAuthUI();
  } catch (e) {}
}

function renderAuthUI() {
  const u = state.currentUser;
  if (!u || !u.logged_in) {
    el('user-logged-out').classList.remove('hidden');
    el('user-logged-in').classList.add('hidden');
  } else {
    el('user-logged-out').classList.add('hidden');
    el('user-logged-in').classList.remove('hidden');
    el('user-email-display').textContent = u.email;
    const badge = el('user-badge');
    if (u.is_premium) badge.classList.remove('hidden');
    else badge.classList.add('hidden');
  }
}

function openAuthModal() {
  el('auth-modal').classList.remove('hidden');
}
function closeAuthModal() {
  el('auth-modal').classList.add('hidden');
}
function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach((t, i) =>
    t.classList.toggle('active', ['login','register'][i] === tab));
  el('auth-login').classList.toggle('hidden', tab !== 'login');
  el('auth-register').classList.toggle('hidden', tab !== 'register');
}

async function doLogin() {
  const email = el('login-email').value.trim();
  const pw    = el('login-pw').value;
  el('login-msg').textContent = '';
  try {
    const data = await api('/api/auth/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email, password: pw })
    });
    state.currentUser = data;
    renderAuthUI();
    closeAuthModal();
  } catch (e) {
    el('login-msg').textContent = e.data?.error || '登入失敗';
    el('login-msg').style.color = '#e74c3c';
  }
}

async function doRegister() {
  const email = el('reg-email').value.trim();
  const pw    = el('reg-pw').value;
  el('reg-msg').textContent = '';
  try {
    const data = await api('/api/auth/register', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email, password: pw })
    });
    state.currentUser = data;
    renderAuthUI();
    closeAuthModal();
    el('reg-msg').textContent = '✅ 註冊成功！';
  } catch (e) {
    el('reg-msg').textContent = e.data?.error || '註冊失敗';
    el('reg-msg').style.color = '#e74c3c';
  }
}

async function doLogout() {
  await api('/api/auth/logout', { method: 'POST' });
  state.currentUser = null;
  renderAuthUI();
}

// ── 付費 ──────────────────────────────────────────────────
function openPayModal() {
  if (!state.currentUser || !state.currentUser.logged_in) {
    openAuthModal(); return;
  }
  el('pay-modal').classList.remove('hidden');
  el('pay-msg').textContent = '';
  el('pay-form-container').innerHTML = '';
}
function closePayModal() {
  el('pay-modal').classList.add('hidden');
}
async function selectPlan(plan) {
  el('pay-msg').textContent = '處理中...';
  try {
    const data = await api('/api/payment/create', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ plan })
    });
    // 把 ECPay 自動送出表單注入頁面
    const container = el('pay-form-container');
    container.innerHTML = data.form_html;
  } catch (e) {
    el('pay-msg').textContent = e.data?.error || '建立付款失敗，請稍後再試';
    el('pay-msg').style.color = '#e74c3c';
  }
}
