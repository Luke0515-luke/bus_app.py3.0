// ══════════════════════════════════════════════════════════
// 台南公車 AI 助理 — 前端邏輯
// ══════════════════════════════════════════════════════════

const ROUTE_COLOR_MAP = [
  ['黃', '#F1C40F'], ['棕', '#8B4513'], ['綠', '#27AE60'], ['橘', '#E67E22'],
  ['藍', '#2980B9'], ['紅', '#E74C3C'], ['H', '#9B59B6'],
  ['0', '#1ABC9C'],
  ['101', '#673AB7'], ['102', '#673AB7'], ['103', '#673AB7'], ['107', '#673AB7'],
  ['111', '#00BCD4'], ['168', '#00BCD4'],
  ['10', '#FF5722'], ['11', '#FF5722'], ['14', '#FF5722'], ['15', '#FF5722'],
  ['18', '#FF9800'], ['19', '#FF9800'], ['20', '#FF9800'], ['21', '#FF9800'],
  ['31', '#795548'], ['32', '#795548'], ['33', '#795548'],
  ['62', '#607D8B'], ['70', '#3F51B5'], ['77', '#009688'], ['98', '#F44336'],
  ['901', '#8BC34A'], ['902', '#8BC34A'], ['904', '#8BC34A'], ['905', '#8BC34A'],
  ['6', '#E91E63'], ['7', '#E91E63'], ['9', '#E91E63'],
  ['東山', '#FF6F00'], ['梅嶺', '#AD1457'], ['菱波', '#00838F'], ['雙層', '#BF360C'],
];
function getRouteColor(name) {
  for (const [prefix, color] of ROUTE_COLOR_MAP) {
    if (name.startsWith(prefix)) return color;
  }
  return '#7F8C8D';
}

const state = {
  fontLarge: false,
  currentPage: 'query',
  selectedFilters: new Set(),
  routeChoice: '',
  dirToggle: '去程',
  destNames: { 去程: '去程', 回程: '回程' },
  favorites: [],
  recent: [],
  mapInited: false,
  mapFilterRoutes: [],
  mapActiveRoutes: new Set(),
  mapAllRoutes: [],
  mapBusData: [],
  mapShapeData: [],
  mapStopData: [],
  savedRoutes: [],
  busListOpen: false,
  leafletMap: null,
  busLayer: null,
  shapeLayer: null,
  stopLayer: null,
  ttsText: '',
};

async function api(url, opts) {
  const res = await fetch(url, opts);
  let data = {};
  try { data = await res.json(); } catch (e) { /* noop */ }
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { data });
  return data;
}
function el(id) { return document.getElementById(id); }
function esc(s) {
  return (s || '').toString().replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
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
});

function bindStaticEvents() {
  el('btn-font-toggle').addEventListener('click', toggleFont);
  el('btn-page-toggle').addEventListener('click', togglePage);
  el('btn-map-home').addEventListener('click', () => switchPage('query'));
  el('btn-back-home').addEventListener('click', showHome);

  el('yellow-bus-select').addEventListener('change', () => {
    const route = el('yellow-bus-select').value;
    if (route) selectRouteByName(route);
  });
  el('btn-show-timetable').addEventListener('click', () => {
    const box = el('timetable-box');
    if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }
    if (state.routeChoice) loadTimetable(state.routeChoice);
  });

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const f = btn.dataset.f;
      // 多選：點一下切換這個篩選條件的選取狀態，其他已選的條件維持不變
      if (state.selectedFilters.has(f)) {
        state.selectedFilters.delete(f);
        btn.classList.remove('active');
      } else {
        state.selectedFilters.add(f);
        btn.classList.add('active');
      }
      loadFilterRoutes([...state.selectedFilters]);
    });
  });
  el('btn-clear-filter').addEventListener('click', () => {
    state.selectedFilters.clear();
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    loadFilterRoutes([]);
  });

  el('route-select').addEventListener('change', onRouteSelect);
  el('btn-fav-toggle').addEventListener('click', toggleFavoriteCurrent);
  el('start-select').addEventListener('change', () => loadRouteStatus());
  el('end-select').addEventListener('change', () => loadRouteStatus());
  el('btn-dir0').addEventListener('click', () => setDirection('去程'));
  el('btn-dir1').addEventListener('click', () => setDirection('回程'));
  el('btn-refresh-status').addEventListener('click', () => loadRouteStatus());

  el('btn-gps').addEventListener('click', gpsLocate);
  el('btn-search-nearby').addEventListener('click', searchNearby);

  el('btn-chat-history-toggle').addEventListener('click', () => {
    el('chat-history-panel').classList.toggle('hidden');
  });
  el('btn-new-chat').addEventListener('click', async () => {
    await api('/api/chat/sessions/new', { method: 'POST' });
    await loadChatSessions();
    await loadChatCurrent();
  });

  el('btn-adv-search').addEventListener('click', advancedSearch);
  el('ic-operator').addEventListener('change', onIntercityOperatorChange);
  el('ic-dep').addEventListener('input', renderIntercityMatches);
  el('ic-dest').addEventListener('input', renderIntercityMatches);

  el('btn-update-cache').addEventListener('click', updateCache);

  el('btn-chat-send').addEventListener('click', sendChat);
  el('chat-input').addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

  el('btn-tts-speak').addEventListener('click', () => {
    if (!state.ttsText) return;
    const u = new SpeechSynthesisUtterance(state.ttsText);
    u.lang = 'zh-TW'; u.rate = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  });
  el('btn-tts-stop').addEventListener('click', () => window.speechSynthesis.cancel());

  el('btn-map-refresh').addEventListener('click', () => loadMapData(true));
  el('map-route-input').addEventListener('keydown', e => { if (e.key === 'Enter') loadMapData(true); });
  el('btn-toggle-map-panel').addEventListener('click', () => {
    const panel = el('map-panel');
    const btn = el('btn-toggle-map-panel');
    const expanded = panel.classList.toggle('expanded');
    btn.textContent = expanded ? '✕ 收合設定' : '☰ 更多設定';
  });
  el('btn-toggle-bus-list').addEventListener('click', () => {
    state.busListOpen = !state.busListOpen;
    renderMapBusList();
  });
  el('map-search-box').addEventListener('input', e => renderMapPanel(e.target.value));
  el('btn-save-route-coords').addEventListener('click', saveRouteCoords);

  el('btn-mobile-menu').addEventListener('click', () => {
    document.body.classList.toggle('sidebar-open');
  });
  el('sidebar-backdrop').addEventListener('click', () => {
    document.body.classList.remove('sidebar-open');
  });

  document.querySelectorAll('.home-tile').forEach(tile => {
    tile.addEventListener('click', () => handleHomeTile(tile.dataset.action));
  });
}

// ── 主頁圖示／子頁面導覽 ─────────────────────────────────────
function openSidebar() {
  document.body.classList.add('sidebar-open');
}

function showHome() {
  el('mobile-home-grid').classList.remove('hidden');
  el('subpage-container').classList.add('hidden');
  document.querySelectorAll('.subpage').forEach(s => s.classList.add('hidden'));
  el('yellow-bus-picker').classList.add('hidden');
}

function showSubpage(id, anchorId) {
  el('mobile-home-grid').classList.add('hidden');
  el('subpage-container').classList.remove('hidden');
  document.querySelectorAll('.subpage').forEach(s => s.classList.toggle('hidden', s.id !== id));
  window.scrollTo({ top: 0, behavior: 'auto' });
  if (anchorId) {
    requestAnimationFrame(() => {
      const target = el(anchorId);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
}

async function handleHomeTile(action) {
  switch (action) {
    case 'map':
      switchPage('map');
      break;
    case 'filter':
      el('yellow-bus-picker').classList.add('hidden');
      showSubpage('subpage-route', 'filter-anchor');
      break;
    case 'nearby':
      el('yellow-bus-picker').classList.add('hidden');
      showSubpage('subpage-route', 'nearby-anchor');
      break;
    case 'chat':
      showSubpage('subpage-chat', 'chat-anchor');
      break;
    case 'yellow-bus':
      showSubpage('subpage-route', 'yellow-bus-anchor');
      el('yellow-bus-picker').classList.remove('hidden');
      loadYellowBusRoutes();
      break;
    case 'favorites':
      openSidebar();
      el('favorites-section').classList.remove('hidden');
      break;
    case 'intercity':
      openSidebar();
      el('details-intercity').setAttribute('open', '');
      requestAnimationFrame(() => el('details-intercity').scrollIntoView({ behavior: 'smooth', block: 'start' }));
      break;
    case 'advsearch':
      openSidebar();
      el('details-advsearch').setAttribute('open', '');
      requestAnimationFrame(() => el('details-advsearch').scrollIntoView({ behavior: 'smooth', block: 'start' }));
      break;
    case 'more':
      openSidebar();
      break;
  }
}

// ── 小黃公車 ─────────────────────────────────────────────
let _yellowBusLoaded = false;
async function loadYellowBusRoutes() {
  if (_yellowBusLoaded) return;
  const sel = el('yellow-bus-select');
  const statusBox = el('yellow-bus-status');
  statusBox.textContent = '路線清單載入中...';
  try {
    const data = await api('/api/yellow_bus_routes');
    sel.innerHTML = '<option value="">請選擇路線...</option>' +
      data.routes.map(r => `<option value="${esc(r.route_name)}">${esc(r.route_name)}</option>`).join('');
    statusBox.textContent = `共 ${data.total} 條小黃公車路線（資料來自 TDX，依營運業者自動判斷）`;
    _yellowBusLoaded = true;
  } catch (e) {
    statusBox.textContent = `❌ 路線清單載入失敗：${e.message}`;
  }
}

// ── 固定時刻表 ────────────────────────────────────────────
async function loadTimetable(route) {
  const box = el('timetable-box');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="caption">時刻表載入中...</div>';
  try {
    const data = await api(`/api/timetable?route=${encodeURIComponent(route)}`);
    if (!data.has_data) {
      box.innerHTML = `<div class="warning-box">${esc(data.message || '查無這條路線的固定時刻表')}</div>`;
      return;
    }
    box.innerHTML = data.directions.map(d => `
      <div class="timetable-direction">
        <div class="timetable-dir-title">${d.direction === 0 ? '➡️ 去程' : '⬅️ 回程'}${d.destination ? '　往 ' + esc(d.destination) : ''}</div>
        ${d.groups.map(g => `
          <div class="timetable-group">
            <div class="timetable-days">${esc(g.days)}</div>
            <div class="timetable-times">${g.times.map(t => `<span class="timetable-time">${esc(t)}</span>`).join('')}</div>
          </div>`).join('')}
      </div>`).join('') || '<div class="info-box">這條路線目前沒有公告固定時刻表</div>';
  } catch (e) {
    box.innerHTML = `<div class="error-box">❌ 時刻表載入失敗：${esc(e.message)}</div>`;
  }
}

// ── 字體 / 頁面切換 ─────────────────────────────────────────
function toggleFont() {
  state.fontLarge = !state.fontLarge;
  document.body.classList.toggle('font-large', state.fontLarge);
  el('btn-font-toggle').textContent = state.fontLarge ? '🔡 縮小字體' : '🔠 放大字體（視障輔助）';
}

function togglePage() {
  switchPage(state.currentPage === 'map' ? 'query' : 'map');
}
function switchPage(page) {
  state.currentPage = page;
  el('page-query').classList.toggle('hidden', page !== 'query');
  el('page-map').classList.toggle('hidden', page !== 'map');
  el('btn-page-toggle').textContent = page === 'map' ? '🚌 回到查詢頁面' : '🗺️ 公車即時地圖';
  document.body.classList.remove('sidebar-open');
  if (page === 'map') initMapPageIfNeeded();
}

// ── 路線篩選 / 選擇 ───────────────────────────────────────
async function loadFilterRoutes(filterVals) {
  const list = Array.isArray(filterVals) ? filterVals : (filterVals ? [filterVals] : []);
  const url = list.length ? `/api/filter_routes?filter=${encodeURIComponent(list.join(','))}` : '/api/filter_routes';
  const data = await api(url);
  const sel = el('route-select');
  const prev = sel.value;
  sel.innerHTML = '<option value="">請選擇或輸入路線...</option>' +
    data.routes.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
  if (data.routes.includes(prev)) sel.value = prev;
  el('filter-status').textContent = list.length
    ? `篩選：【${list.join('、')}】（共 ${data.routes.length} 條）`
    : '顯示：全部路線';

  // 直接把篩選結果列成一排可點的路線標籤，不用打開下拉選單也看得出來真的有篩選、篩到哪些路線
  const chipsBox = el('filter-route-chips');
  if (!list.length) {
    chipsBox.innerHTML = '';
  } else if (!data.routes.length) {
    chipsBox.innerHTML = '<div class="warning-box">這個篩選條件下沒有符合的路線</div>';
  } else {
    chipsBox.innerHTML = data.routes.map(r =>
      `<button type="button" class="route-chip" data-route="${esc(r)}" style="background:${getRouteColor(r)}">${esc(r)}</button>`
    ).join('');
    chipsBox.querySelectorAll('.route-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        sel.value = chip.dataset.route;
        onRouteSelect();
      });
    });
  }
}

async function onRouteSelect() {
  const route = el('route-select').value;
  state.routeChoice = route;
  el('stop-select-body').classList.add('hidden');
  el('status-box').classList.add('hidden');
  el('weather-box').classList.add('hidden');
  el('status-empty').classList.remove('hidden');
  el('timetable-box').classList.add('hidden');
  el('timetable-box').innerHTML = '';

  if (!route) {
    el('btn-fav-toggle').classList.add('hidden');
    el('btn-show-timetable').classList.add('hidden');
    el('route-hint').textContent = '請選擇路線';
    el('route-hint').classList.remove('hidden');
    return;
  }
  el('route-hint').classList.add('hidden');
  el('btn-fav-toggle').classList.remove('hidden');
  el('btn-show-timetable').classList.remove('hidden');
  el('btn-show-timetable').textContent = '📅 查看固定時刻表';
  refreshFavToggleLabel();

  const data = await api(`/api/route_stops?route=${encodeURIComponent(route)}`);
  loadRecent();
  if (!data.stops || data.stops.length === 0) {
    el('route-hint').textContent = `⚠️ 無法載入【${route}】站點。`;
    el('route-hint').className = 'warning-box';
    el('route-hint').classList.remove('hidden');
    return;
  }
  const startSel = el('start-select');
  const endSel = el('end-select');
  startSel.innerHTML = data.stops.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  endSel.innerHTML = data.stops.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  startSel.selectedIndex = 0;
  endSel.selectedIndex = data.stops.length - 1;
  el('stop-select-body').classList.remove('hidden');

  await loadRouteStatus();
}

function refreshFavToggleLabel() {
  const isFav = state.favorites.includes(state.routeChoice);
  el('btn-fav-toggle').textContent = isFav ? '⭐ 已加入最愛' : '☆ 加入最愛';
}
async function toggleFavoriteCurrent() {
  if (!state.routeChoice) return;
  const data = await api('/api/favorites/toggle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ route: state.routeChoice })
  });
  state.favorites = data.favorites;
  refreshFavToggleLabel();
  renderFavorites();
}

function setDirection(dir) {
  state.dirToggle = dir;
  el('btn-dir0').classList.toggle('active', dir === '去程');
  el('btn-dir1').classList.toggle('active', dir === '回程');
  loadRouteStatus();
}

async function loadRouteStatus() {
  if (!state.routeChoice) return;
  const startSt = el('start-select').value;
  const endSt = el('end-select').value;
  let data;
  try {
    const params = new URLSearchParams({
      route: state.routeChoice, direction: state.dirToggle,
      start_st: startSt || '', end_st: endSt || ''
    });
    data = await api(`/api/route_status?${params.toString()}`);
  } catch (e) {
    el('status-box').classList.add('hidden');
    el('status-empty').textContent = '無法取得即時動態。';
    el('status-empty').className = 'error-box';
    el('status-empty').classList.remove('hidden');
    return;
  }

  el('status-empty').classList.add('hidden');
  el('weather-box').textContent = `🌡️ 台南目前天氣：${data.weather}`;
  el('weather-box').classList.remove('hidden');

  state.destNames = { 去程: data.dest0, 回程: data.dest1 };
  el('status-title').textContent = `🚌 ${state.routeChoice} 全線即時動態`;
  el('btn-dir0').textContent = `➡️ 往 ${data.dest0}`;
  el('btn-dir1').textContent = `⬅️ 往 ${data.dest1}`;
  el('btn-dir0').classList.toggle('active', state.dirToggle === '去程');
  el('btn-dir1').classList.toggle('active', state.dirToggle === '回程');

  const ubBox = el('ubike-suggestion');
  if (data.ubike_suggestion) {
    ubBox.textContent = data.ubike_suggestion;
    ubBox.classList.remove('hidden');
  } else {
    ubBox.classList.add('hidden');
  }

  const container = el('timeline-container');
  container.innerHTML = data.stops.map(s => {
    let busHtml = '';
    if (s.has_bus) {
      const wc = s.is_low
        ? '<span class="wheelchair-tag">♿ 無障礙</span>'
        : '<span class="no-wheelchair-tag">🚌 一般車</span>';
      const ev = s.is_ev ? '<span class="ev-tag">⚡ 電動</span>' : '';
      busHtml = `<span class="bus-tag">🚌 ${esc(s.plate)} (${esc(s.car_size)})</span>${wc}${ev}`;
    }
    const ubikeHtml = (s.ubikes || []).map(u =>
      `<span class="ubike-tag">🚲 可借:${u.available} 可還:${u.empty}</span>`).join('');
    return `
<div class="timeline-item ${s.is_waiting_stop ? 'waiting-stop' : ''}">
  <div class="timeline-circle"></div>
  <div class="station-box">
    <div class="station-info">
      <div class="station-info-top">
        <span class="station-name">${esc(s.name)}</span>
        ${busHtml}
      </div>
      ${ubikeHtml ? `<div class="station-info-ubike">${ubikeHtml}</div>` : ''}
    </div>
    <span class="time-badge ${s.badge_class}">${esc(s.eta_text)}</span>
  </div>
</div>`;
  }).join('');

  state.ttsText = data.tts_text || '';
  el('status-box').classList.remove('hidden');
}

// ── GPS 附近站牌 ─────────────────────────────────────────
function gpsLocate() {
  if (!navigator.geolocation) { alert('瀏覽器不支援定位'); return; }
  navigator.geolocation.getCurrentPosition(pos => {
    el('lat-disp').value = pos.coords.latitude.toFixed(6);
    el('lon-disp').value = pos.coords.longitude.toFixed(6);
    el('gps-lat-in').value = pos.coords.latitude.toFixed(6);
    el('gps-lon-in').value = pos.coords.longitude.toFixed(6);
  }, () => alert('請允許瀏覽器定位權限'));
}

async function searchNearby() {
  const lat = parseFloat(el('gps-lat-in').value);
  const lon = parseFloat(el('gps-lon-in').value);
  const box = el('nearby-result');
  if (isNaN(lat) || isNaN(lon)) {
    box.innerHTML = '<div class="error-box">請輸入有效數字</div>';
    return;
  }
  box.innerHTML = '<div class="caption">搜尋中...</div>';
  try {
    const data = await api(`/api/nearby_stops?lat=${lat}&lon=${lon}`);
    if (!data.nearby || data.nearby.length === 0) {
      box.innerHTML = '<div class="warning-box">附近 500m 內無公車站牌</div>';
      return;
    }
    box.innerHTML = `<div class="caption">找到 ${data.nearby.length} 個站牌（500m內）：</div>` +
      data.nearby.map(n => `<div class="stop-item">🚏 <b>${esc(n.name)}</b>（${Math.round(n.dist * 1000)}m）</div>`).join('');
  } catch (e) {
    box.innerHTML = '<div class="error-box">無法載入站牌資料</div>';
  }
}

// ── 最愛 / 最近查詢 ──────────────────────────────────────
async function loadFavorites() {
  const data = await api('/api/favorites');
  state.favorites = data.favorites;
  renderFavorites();
}
function renderFavorites() {
  const sec = el('favorites-section');
  const list = el('favorites-list');
  if (!state.favorites.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  list.innerHTML = state.favorites.map(fav => `
    <div class="fav-row">
      <button class="btn fav-main" data-r="${esc(fav)}">🚌 ${esc(fav)}</button>
      <button class="btn fav-remove" data-r="${esc(fav)}">✕</button>
    </div>`).join('');
  list.querySelectorAll('.fav-main').forEach(b => b.addEventListener('click', () => selectRouteByName(b.dataset.r)));
  list.querySelectorAll('.fav-remove').forEach(b => b.addEventListener('click', async () => {
    const data = await api('/api/favorites/toggle', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ route: b.dataset.r })
    });
    state.favorites = data.favorites;
    renderFavorites();
    if (state.routeChoice === b.dataset.r) refreshFavToggleLabel();
  }));
  refreshFavToggleLabel();
}

async function loadRecent() {
  const data = await api('/api/recent');
  state.recent = data.recent;
  renderRecent();
}
function renderRecent() {
  const sec = el('recent-section');
  const list = el('recent-list');
  if (!state.recent.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');
  list.innerHTML = state.recent.map(r => `<button class="btn" data-r="${esc(r)}">🔁 ${esc(r)}</button>`).join('');
  list.querySelectorAll('button').forEach(b => b.addEventListener('click', () => selectRouteByName(b.dataset.r)));
}

async function selectRouteByName(route) {
  document.body.classList.remove('sidebar-open');
  state.selectedFilters.clear();
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  await loadFilterRoutes(null);
  const sel = el('route-select');
  if (![...sel.options].some(o => o.value === route)) {
    sel.insertAdjacentHTML('beforeend', `<option value="${esc(route)}">${esc(route)}</option>`);
  }
  sel.value = route;
  await onRouteSelect();
}

// ── 進階查詢（站到站） ────────────────────────────────────
async function loadAdvancedStops() {
  const data = await api('/api/advanced_search/stops');
  el('adv-stops-datalist').innerHTML = data.stops.map(s => `<option value="${esc(s)}"></option>`).join('');
}
async function advancedSearch() {
  const start = el('adv-start').value;
  const end = el('adv-end').value;
  const box = el('adv-search-result');
  box.innerHTML = '';
  if (!start || !end) { box.innerHTML = '<div class="error-box">請選擇出發站和目的站</div>'; return; }
  if (start === end) { box.innerHTML = '<div class="error-box">出發站和目的站不能相同</div>'; return; }
  box.innerHTML = '<div class="caption">搜尋中...</div>';
  try {
    const data = await api(`/api/advanced_search?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
    let html = '';
    if (data.directs && data.directs.length) {
      html += `<div class="success-box">✅ 直達路線（共 ${data.directs.length} 條）</div>`;
      html += data.directs.map(r => `<div class="route-item"><button class="btn adv-go" data-r="${esc(r)}">🚌 ${esc(r)}</button></div>`).join('');
    } else {
      html += '<div class="info-box">無直達路線</div>';
    }
    if (data.transfers && data.transfers.length) {
      html += `<div class="warning-box">🔄 轉乘一次方案（共 ${data.transfers.length} 個）</div>`;
      html += data.transfers.map(t => `<div class="route-item">搭 <b>${esc(t.routeA)}</b> → 在 <b>${esc(t.transfer)}</b> 轉 <b>${esc(t.routeB)}</b></div>`).join('');
    } else {
      html += '<div class="error-box">找不到一次轉乘方案，請考慮其他方式</div>';
    }
    box.innerHTML = html;
    box.querySelectorAll('.adv-go').forEach(b => b.addEventListener('click', () => selectRouteByName(b.dataset.r)));
  } catch (e) {
    box.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}

// ── 客運查詢 ─────────────────────────────────────────────
let icRoutesCache = [];
async function onIntercityOperatorChange() {
  const opId = el('ic-operator').value;
  const body = el('ic-body');
  const result = el('ic-result');
  icRoutesCache = [];
  result.innerHTML = '';
  if (!opId) { body.classList.add('hidden'); return; }
  body.classList.remove('hidden');
  result.innerHTML = '<div class="caption">載入路線中...</div>';
  const data = await api(`/api/intercity/routes?op_id=${encodeURIComponent(opId)}`);
  icRoutesCache = data.routes;
  if (!icRoutesCache.length) {
    result.innerHTML = '<div class="warning-box">目前查不到該業者的路線資料</div>';
    return;
  }
  result.innerHTML = `<div class="info-box">共有 ${data.total} 條路線，請輸入起點或目的站篩選</div>`;

  // 把這個業者所有路線的起訖站名整理成清單，餵給 input 的 datalist，
  // 這樣 ic-dep / ic-dest 輸入框打字時就會跳出實際存在的站名選單可以直接點選。
  const depNames = new Set();
  const destNames = new Set();
  icRoutesCache.forEach(r => {
    if (r.dep) depNames.add(r.dep);
    if (r.dest) destNames.add(r.dest);
  });
  el('ic-dep-datalist').innerHTML = [...depNames].sort().map(s => `<option value="${esc(s)}"></option>`).join('');
  el('ic-dest-datalist').innerHTML = [...destNames].sort().map(s => `<option value="${esc(s)}"></option>`).join('');
}
function renderIntercityMatches() {
  const dep = el('ic-dep').value.trim();
  const dest = el('ic-dest').value.trim();
  const result = el('ic-result');
  if (!icRoutesCache.length) return;
  if (!dep && !dest) {
    result.innerHTML = `<div class="info-box">共有 ${icRoutesCache.length} 條路線，請輸入起點或目的站篩選</div>`;
    return;
  }
  const matched = icRoutesCache.filter(r =>
    (!dep || r.label.includes(dep)) && (!dest || r.label.includes(dest)));
  if (!matched.length) {
    result.innerHTML = '<div class="warning-box">找不到符合的路線，請調整關鍵字</div>';
    return;
  }
  result.innerHTML = `<div class="success-box">找到 ${matched.length} 條符合路線</div>` +
    matched.slice(0, 10).map(r => `
      <details class="expander ic-item">
        <summary>🚍 ${esc(r.label)}</summary>
        <div class="ic-detail" data-rid="${esc(r.rid)}"><div class="caption">點開後載入中...</div></div>
      </details>`).join('');
  result.querySelectorAll('details.ic-item').forEach(d => {
    d.addEventListener('toggle', async () => {
      if (!d.open) return;
      const detailBox = d.querySelector('.ic-detail');
      const rid = detailBox.dataset.rid;
      if (detailBox.dataset.loaded) return;
      const data = await api(`/api/intercity/detail?rid=${encodeURIComponent(rid)}`);
      detailBox.dataset.loaded = '1';
      if (!data.has_data || !data.stops.length) {
        detailBox.innerHTML = '<div class="info-box">無站點資料</div>';
        return;
      }
      detailBox.innerHTML = '<div class="caption"><b>停靠站與到站時間：</b></div>' +
        data.stops.map(s => `<div class="stop-item">${s.icon} <b>${esc(s.name)}</b> — ${esc(s.text)}</div>`).join('');
    });
  });
}

// ── 系統維護 ─────────────────────────────────────────────
async function updateCache() {
  const box = el('cache-status');
  const btn = el('btn-update-cache');
  btn.disabled = true;
  box.innerHTML = '<div class="caption">離線化中，請稍候（可能需要幾分鐘）...</div>';
  try {
    const data = await api('/api/update_cache', { method: 'POST' });
    box.innerHTML = `<div class="success-box">🎉 快取建立成功！共 ${data.count} 條路線</div>`;
  } catch (e) {
    box.innerHTML = `<div class="error-box">建立失敗：${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
}

// ── AI 助理 ──────────────────────────────────────────────
async function loadChatSessions() {
  const data = await api('/api/chat/sessions');
  renderChatSessions(data.sessions);
}
function renderChatSessions(sessions) {
  el('chat-session-list').innerHTML = sessions.map(s => `
    <div class="sess-item">
      <button class="btn sess-select ${s.is_current ? 'active' : ''}" data-sid="${esc(s.sid)}">${s.is_current ? '▶ ' : ''}${esc(s.title)}</button>
      <button class="btn sess-del" data-sid="${esc(s.sid)}">🗑</button>
    </div>`).join('');
  document.querySelectorAll('.sess-select').forEach(b => b.addEventListener('click', async () => {
    await api('/api/chat/sessions/switch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sid: b.dataset.sid })
    });
    el('chat-history-panel').classList.add('hidden');
    await loadChatSessions();
    await loadChatCurrent();
  }));
  document.querySelectorAll('.sess-del').forEach(b => b.addEventListener('click', async () => {
    await api('/api/chat/sessions/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sid: b.dataset.sid })
    });
    await loadChatSessions();
    await loadChatCurrent();
  }));
}
async function loadChatCurrent() {
  const data = await api('/api/chat/sessions/current');
  el('chat-current-title').textContent = data.title;
  renderChatMessages(data.history);
}
function renderChatMessages(history) {
  const box = el('chat-messages');
  box.innerHTML = history.map(m => `<div class="chat-msg ${m.role}">${esc(m.content)}</div>`).join('');
  box.scrollTop = box.scrollHeight;
}
async function sendChat() {
  const input = el('chat-input');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  const box = el('chat-messages');
  box.insertAdjacentHTML('beforeend', `<div class="chat-msg user">${esc(q)}</div>`);
  box.scrollTop = box.scrollHeight;
  box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant" id="chat-thinking">思考中...</div>`);
  box.scrollTop = box.scrollHeight;
  try {
    const data = await api('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q })
    });
    const thinking = el('chat-thinking');
    if (thinking) thinking.remove();
    if (data.error) {
      box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant">AI 錯誤：${esc(data.error)}</div>`);
    } else {
      box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant">${esc(data.reply)}</div>`);
      if (data.title) el('chat-current-title').textContent = data.title;
      loadChatSessions();
    }
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    const thinking = el('chat-thinking');
    if (thinking) thinking.remove();
    box.insertAdjacentHTML('beforeend', `<div class="chat-msg assistant">AI 錯誤：${esc(e.message)}</div>`);
  }
}

// ── 地圖頁面 ─────────────────────────────────────────────
function initMapPageIfNeeded() {
  if (state.mapInited) { loadMapData(false); return; }
  state.mapInited = true;
  state.leafletMap = L.map('leaflet-map', { zoomControl: true, preferCanvas: true }).setView([22.9997, 120.2270], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors', subdomains: 'abc', maxZoom: 19
  }).addTo(state.leafletMap);
  state.shapeLayer = L.layerGroup().addTo(state.leafletMap);
  state.stopLayer = L.layerGroup().addTo(state.leafletMap);
  state.busLayer = L.layerGroup().addTo(state.leafletMap);
  state.leafletMap.on('zoomend', updateStopLabelVisibility);
  // 「已儲存路線」清單先用一支很輕量的 API 立刻列出來，不用等整張地圖（公車＋路線＋站牌）
  // 全部抓完才顯示，使用者一打開地圖頁馬上就看得到已經存過檔的路線。
  loadSavedRoutesOnly();
  loadMapData(false);
}

// 只拉「已儲存路線」清單（不含地圖上的公車/路線/站牌），一開地圖頁就先顯示出來。
async function loadSavedRoutesOnly() {
  try {
    const data = await api('/api/saved_routes');
    state.savedRoutes = data.routes || [];
    renderMapPanel(el('map-search-box').value.trim());
  } catch (e) {
    // 忽略，等下面完整的 loadMapData() 回來一樣會補上
  }
}

async function saveRouteCoords() {
  const route = el('save-route-input').value.trim();
  const statusBox = el('save-route-status');
  const btn = el('btn-save-route-coords');
  if (!route) {
    statusBox.textContent = '⚠️ 請輸入路線名稱';
    return;
  }
  btn.disabled = true;
  statusBox.textContent = `抓取「${route}」的 Shape 與 StopOfRoute 資料中...`;
  try {
    const data = await api('/api/save_route_data', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ route })
    });
    statusBox.innerHTML =
      `✅ 已儲存<br>路線軌跡：${data.shape_ok ? `${data.shape_segments} 段` : '❌ 抓取失敗'} → ${esc(data.shape_file)}<br>` +
      `站牌清單：${data.stop_ok ? `${data.stop_count} 站` : '❌ 抓取失敗'} → ${esc(data.stop_file)}`;
    // 存檔成功後立即重新整理地圖資料，讓底下的「已儲存路線」清單馬上出現這條新路線
    if (data.shape_ok || data.stop_ok) await loadMapData(true);
  } catch (e) {
    let html = `❌ ${esc(e.message)}`;
    const suggestions = e.data && e.data.suggestions;
    if (suggestions && suggestions.length) {
      html += '<div class="caption" style="margin-top:6px;">點一下可直接改用這個名稱重新抓取：</div>' +
        suggestions.map(s => `<button class="btn btn-block route-suggest-save" data-name="${esc(s)}">🚌 ${esc(s)}</button>`).join('');
    }
    statusBox.innerHTML = html;
    statusBox.querySelectorAll('.route-suggest-save').forEach(b => {
      b.addEventListener('click', () => {
        el('save-route-input').value = b.dataset.name;
        saveRouteCoords();
      });
    });
  } finally {
    btn.disabled = false;
  }
}

// 查不到某條路線的資料時，用字首（例如「藍幹線」取「藍」）反查 TDX 上名稱相近的路線，
// 讓使用者確認 TDX 真正登記的名稱，而不是憑猜測改設定。
async function lookupRouteName(routeText) {
  const resultBox = el('route-lookup-result');
  if (!resultBox) return;
  const keyword = (routeText || '').trim().charAt(0) || routeText;
  resultBox.innerHTML = '<div class="caption">查詢中...</div>';
  try {
    const data = await api(`/api/route_lookup?q=${encodeURIComponent(keyword)}`);
    if (!data.matches || !data.matches.length) {
      resultBox.innerHTML = `<div class="error-box">TDX 上找不到名稱包含「${esc(keyword)}」的路線，可能是這個字首本身就不對</div>`;
      return;
    }
    resultBox.innerHTML = `<div class="success-box">TDX 上名稱包含「${esc(keyword)}」的路線（點一下可直接改用這個名稱查詢）：</div>` +
      data.matches.map(m => `
        <button class="btn btn-block route-suggest" data-name="${esc(m.route_name)}">
          🚌 ${esc(m.route_name)}${m.operators && m.operators.length ? `（${esc(m.operators.join('、'))}）` : ''}
        </button>`).join('');
    resultBox.querySelectorAll('.route-suggest').forEach(b => {
      b.addEventListener('click', () => {
        el('map-route-input').value = b.dataset.name;
        state.busListOpen = true;
        loadMapData(true);
      });
    });
  } catch (e) {
    resultBox.innerHTML = `<div class="error-box">查詢失敗：${esc(e.message)}</div>`;
  }
}

async function loadMapData(forceRefresh) {
  const inputVal = el('map-route-input').value.trim();
  const stats = el('map-panel-stats');
  stats.textContent = '載入中...';
  const params = inputVal ? `?routes=${encodeURIComponent(inputVal)}` : '';
  try {
    const data = await api(`/api/map_data${params}`);
    state.mapBusData = data.buses;
    state.mapShapeData = data.shapes;
    state.mapStopData = data.stops || [];
    state.mapAllRoutes = data.routes;
    state.savedRoutes = data.saved_routes || [];
    state.mapActiveRoutes = new Set(data.routes); // 預設全部顯示
    el('map-caption').textContent = `資料時間：${data.now}　｜　每次按「🔄 更新」重抓最新位置`;
    drawMapShapes();
    drawMapStops();
    drawMapBuses();
    renderMapPanel(el('map-search-box').value);
  } catch (e) {
    stats.textContent = '載入失敗';
  }
}

function makeBusIcon(color) {
  return L.divIcon({
    className: '',
    html: `<div style="width:18px;height:18px;background:${color};border:2.5px solid rgba(255,255,255,0.85);border-radius:50%;box-shadow:0 0 6px ${color};"></div>`,
    iconSize: [18, 18], iconAnchor: [9, 9]
  });
}
function drawMapShapes() {
  state.shapeLayer.clearLayers();
  state.mapShapeData.forEach(sh => {
    if (!state.mapActiveRoutes.has(sh.route)) return;
    const latlngs = sh.points.map(p => [p[0], p[1]]);
    L.polyline(latlngs, { color: sh.color, weight: 3, opacity: 0.75 })
      .bindTooltip(sh.route, { sticky: true }).addTo(state.shapeLayer);
  });
}
function drawMapStops() {
  state.stopLayer.clearLayers();
  state.mapStopData.forEach(sp => {
    if (!state.mapActiveRoutes.has(sp.route)) return;
    L.circleMarker([sp.lat, sp.lon], {
      radius: 4, weight: 1, color: '#ffffff', opacity: 0.9,
      fillColor: sp.color, fillOpacity: 0.95
    })
      // 常駐標籤：放大到一定程度後才顯示，避免縮小檢視時上千個站名疊在一起看不清楚
      .bindTooltip(sp.name, {
        permanent: true, direction: 'right', offset: L.point(7, 0),
        className: 'stop-label', opacity: 0.9
      })
      // 不論目前是否放大，點擊/點選圓點都能直接看到站名（手機點按也適用）
      .bindPopup(`<b style="color:${sp.color}">${esc(sp.route)}</b><br>🚏 ${esc(sp.name)}`)
      .addTo(state.stopLayer);
  });
  updateStopLabelVisibility();
}

function updateStopLabelVisibility() {
  if (!state.leafletMap) return;
  const zoom = state.leafletMap.getZoom();
  state.leafletMap.getContainer().classList.toggle('stops-zoomed-in', zoom >= 15);
}
function countByRoute() {
  const cnt = {};
  state.mapBusData.forEach(b => { if (state.mapActiveRoutes.has(b.route)) cnt[b.route] = (cnt[b.route] || 0) + 1; });
  return cnt;
}
function drawMapBuses() {
  state.busLayer.clearLayers();
  let total = 0;
  state.mapBusData.forEach(b => {
    if (!state.mapActiveRoutes.has(b.route)) return;
    const marker = L.marker([b.lat, b.lon], { icon: makeBusIcon(b.color) });
    marker.bindPopup(`
      <div class="bus-popup">
        <b>🚌 ${esc(b.route)}</b><br>
        <span class="tag" style="background:${b.color}">車牌：${esc(b.plate)}</span>
        <span class="tag" style="background:#555">方向：${esc(b.dir)}</span>
        <span class="tag" style="background:#333">速度：${esc(String(b.speed))} km/h</span>
      </div>`, { maxWidth: 200 });
    marker.addTo(state.busLayer);
    total++;
  });
  el('map-panel-stats').textContent = `顯示 ${state.mapActiveRoutes.size} 條路線・${total} 台公車`;
  renderMapBusList();
}

// 最上面的查詢欄（篩選路線）除了在地圖上畫出公車圖示，
// 同時也可以把該路線（或該次篩選的每一條路線）上「每一台公車」的最新定位，
// 以文字清單的方式列出來，不用逐一點地圖上的圓點才看得到。
// 為了不要一查完就整塊清單直接撐開、把下面「抓取並儲存路線原始資料」的版面往下推，
// 預設是收合的，清單前面會有一顆按鈕，使用者按了才展開／收合。
function renderMapBusList() {
  const btn = el('btn-toggle-bus-list');
  const container = el('map-bus-list');
  if (!btn || !container) return;

  const inputVal = el('map-route-input').value.trim();
  const buses = state.mapBusData
    .filter(b => state.mapActiveRoutes.has(b.route))
    .sort((a, b) => a.route.localeCompare(b.route) || String(a.plate).localeCompare(String(b.plate)));

  if (!inputVal) {
    // 沒有輸入特定路線（顯示全部路線）時，公車數量太多不適合列清單，直接隱藏按鈕與清單
    btn.classList.add('hidden');
    container.classList.add('hidden');
    container.innerHTML = '';
    state.busListOpen = false;
    return;
  }

  btn.classList.remove('hidden');
  btn.textContent = state.busListOpen
    ? `🔼 收合公車定位清單（共 ${buses.length} 台）`
    : `🚌 查看路線上每台公車的最新定位（共 ${buses.length} 台）`;

  if (!state.busListOpen) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');
  if (!buses.length) {
    container.innerHTML = `
      <div class="warning-box">目前查無這個篩選條件下的公車即時定位（該路線可能暫時沒有營運中的車輛，也可能是路線名稱跟 TDX 登記的不完全一樣）</div>
      <button id="btn-route-name-lookup" class="btn btn-block">🔍 查詢 TDX 正確路線名稱</button>
      <div id="route-lookup-result"></div>`;
    el('btn-route-name-lookup').addEventListener('click', () => lookupRouteName(inputVal));
    return;
  }

  container.innerHTML = `<div class="caption">🚌 目前共 ${buses.length} 台公車最新定位（點項目可在地圖上定位）：</div>` +
    buses.map(b => `
      <div class="stop-item bus-list-item" style="cursor:pointer" data-lat="${b.lat}" data-lon="${b.lon}">
        <span class="tag" style="background:${b.color}">${esc(b.route)}</span>
        車牌 <b>${esc(b.plate || '未知')}</b>
        ・${esc(b.dir)}
        ・${esc(String(b.speed))} km/h
        ・📍 ${Number(b.lat).toFixed(5)}, ${Number(b.lon).toFixed(5)}
      </div>`).join('');

  container.querySelectorAll('.bus-list-item').forEach(item => {
    item.addEventListener('click', () => {
      const lat = parseFloat(item.dataset.lat);
      const lon = parseFloat(item.dataset.lon);
      if (state.leafletMap && !isNaN(lat) && !isNaN(lon)) {
        state.leafletMap.flyTo([lat, lon], 17);
      }
    });
  });
}
function renderMapPanel(filterText) {
  const list = el('map-route-list');
  list.innerHTML = '';
  const cnt = countByRoute();

  const allItem = document.createElement('div');
  const allActive = state.mapActiveRoutes.size === state.mapAllRoutes.length;
  allItem.className = 'route-item' + (allActive ? ' active' : '');
  allItem.innerHTML = `<div class="route-dot" style="background:#fff;"></div><span>全部路線</span><span class="route-count">${state.mapAllRoutes.length}</span>`;
  allItem.onclick = () => {
    if (state.mapActiveRoutes.size === state.mapAllRoutes.length) state.mapActiveRoutes.clear();
    else state.mapAllRoutes.forEach(r => state.mapActiveRoutes.add(r));
    renderMapPanel(filterText); drawMapShapes(); drawMapStops(); drawMapBuses();
  };
  list.appendChild(allItem);

  state.mapAllRoutes.forEach(route => {
    if (filterText && !route.includes(filterText)) return;
    const color = getRouteColor(route);
    const n = cnt[route] || 0;
    const isSaved = state.savedRoutes.includes(route);
    const item = document.createElement('div');
    item.className = 'route-item' + (state.mapActiveRoutes.has(route) ? ' active' : '');
    item.title = isSaved ? '已儲存路線原始資料（Shape＋StopOfRoute）' : '';
    item.innerHTML = `<div class="route-dot" style="background:${color};"></div><span>${esc(route)}</span><span class="route-count">${n}</span>`;
    item.onclick = () => {
      if (state.mapActiveRoutes.has(route)) state.mapActiveRoutes.delete(route);
      else state.mapActiveRoutes.add(route);
      drawMapShapes(); drawMapStops(); drawMapBuses(); renderMapPanel(filterText);
    };
    list.appendChild(item);
  });

  // 已經存檔過、但目前不在頂端篩選欄範圍內的路線，也一律列在這裡（前面加 💾），
  // 不會因為上面查詢欄篩選成只剩一條路線，就把其他已儲存的路線從清單裡藏起來。
  const extraSaved = state.savedRoutes.filter(r => !state.mapAllRoutes.includes(r));
  extraSaved.forEach(route => {
    if (filterText && !route.includes(filterText)) return;
    const color = getRouteColor(route);
    const item = document.createElement('div');
    item.className = 'route-item';
    item.title = '已儲存路線原始資料（Shape＋StopOfRoute）－目前不在篩選範圍內，點一下即可加入';
    item.innerHTML = `<div class="route-dot" style="background:${color};"></div><span>${esc(route)}</span><span class="route-count">－</span>`;
    item.onclick = () => {
      // 用「加入」而不是「取代」：把這條路線併進目前查詢欄的清單，
      // 這樣才能一次累加選取多條路線一起顯示，不會每點一條就把前面選的路線洗掉。
      const inp = el('map-route-input');
      const existing = inp.value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
      if (!existing.includes(route)) existing.push(route);
      inp.value = existing.join(', ');
      loadMapData(true);
    };
    list.appendChild(item);
  });
}
