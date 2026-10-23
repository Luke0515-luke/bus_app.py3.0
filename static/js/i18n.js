(function () {
'use strict';
// 每一列：[中文原文（數字／時間／路線代號／「」內的名稱以 # 代替）, English, 日本語, 한국어]
// 譯文裡用 {1} {2}… 代表依序出現的 # 內容；沒有寫 {n} 時 # 依序原樣放回。
const ROWS = [
['🚌 台南公車 AI 助理','🚌 Tainan Bus AI Assistant','🚌 台南バス AIアシスタント','🚌 타이난 버스 AI 도우미'],
['開啟選單','Open menu','メニューを開く','메뉴 열기'],
['🚌 台南公車助理','🚌 Tainan Bus Assistant','🚌 台南バスアシスタント','🚌 타이난 버스 도우미'],
['🔠 放大字體（視障輔助）','🔠 Larger text (accessibility)','🔠 文字を拡大（視覚サポート）','🔠 글자 크게 (접근성)'],
['🔡 縮小字體','🔡 Smaller text','🔡 文字を縮小','🔡 글자 작게'],
['🗺️ 公車即時地圖','🗺️ Live Bus Map','🗺️ バスリアルタイムマップ','🗺️ 실시간 버스 지도'],
['🚌 回到查詢頁面','🚌 Back to search page','🚌 検索ページへ戻る','🚌 검색 페이지로 돌아가기'],
['💬 AI 對話記錄','💬 AI Chat History','💬 AIチャット履歴','💬 AI 대화 기록'],
['📋 對話記錄','📋 Chat History','📋 チャット履歴','📋 대화 기록'],
['➕ 新對話','➕ New chat','➕ 新しいチャット','➕ 새 대화'],
['⭐ 最愛路線','⭐ Favorite routes','⭐ お気に入り路線','⭐ 즐겨찾는 노선'],
['🕐 最近查詢','🕐 Recent searches','🕐 最近の検索','🕐 최근 검색'],
['🔔 到站鈴聲提醒','🔔 Arrival alert sound','🔔 到着アラーム','🔔 도착 알림음'],
['啟用鈴聲提醒（需要瀏覽器分頁保持開啟）','Enable alert sound (keep this browser tab open)','アラームを有効にする（ブラウザのタブを開いたままにしてください）','알림음 켜기 (브라우저 탭을 열어 두어야 합니다)'],
['🔍 進階查詢（站到站）','🔍 Advanced search (stop to stop)','🔍 詳細検索（停留所〜停留所）','🔍 상세 검색 (정류장 ↔ 정류장)'],
['輸入起站與終點，找出直達或轉乘一次的路線','Enter a start and a destination to find direct routes or routes with one transfer','出発地と目的地を入力して、直通または1回乗り換えの路線を探します','출발지와 도착지를 입력하면 직행 또는 1회 환승 노선을 찾아 드려요'],
['🔎 快速篩選站名（可不填，直接在下面欄位打字或選單找也可以）','🔎 Quick stop filter (optional — you can also type or pick in the fields below)','🔎 停留所をすばやく絞り込み（空欄でも可。下の欄に入力・選択もできます）','🔎 정류장 빠른 필터 (비워 두어도 되고, 아래 칸에 직접 입력하거나 목록에서 고를 수도 있어요)'],
['輸入關鍵字篩選下面的站名選單...','Type a keyword to filter the stop list below...','キーワードで下の停留所リストを絞り込み...','키워드를 입력해 아래 정류장 목록을 걸러 보세요...'],
['出發站','Start stop','出発停留所','출발 정류장'],
['請選擇或輸入站名...','Select or type a stop name...','停留所名を選択または入力...','정류장 이름을 선택하거나 입력하세요...'],
['目的站','Destination stop','目的停留所','도착 정류장'],
['🔎 查詢路線','🔎 Find routes','🔎 路線を検索','🔎 노선 검색'],
['👤 帳號登入','👤 Sign in','👤 アカウントログイン','👤 로그인'],
['登入後，最愛路線、最近查詢、AI 對話記錄都會綁定在帳號上，換裝置、換瀏覽器登入一樣看得到。','After signing in, your favorites, recent searches and AI chat history are tied to your account, so you can see them on any device or browser.','ログインすると、お気に入り路線・最近の検索・AIチャット履歴がアカウントに紐づき、端末やブラウザを変えても確認できます。','로그인하면 즐겨찾는 노선, 최근 검색, AI 대화 기록이 계정에 저장되어 기기나 브라우저를 바꿔도 볼 수 있어요.'],
['帳號','Username','アカウント','계정'],
['輸入帳號...','Enter username...','アカウントを入力...','계정을 입력하세요...'],
['密碼','Password','パスワード','비밀번호'],
['輸入密碼...','Enter password...','パスワードを入力...','비밀번호를 입력하세요...'],
['🔑 登入','🔑 Sign in','🔑 ログイン','🔑 로그인'],
['📝 註冊新帳號','📝 Create account','📝 新規登録','📝 새 계정 만들기'],
['已登入：','Signed in:','ログイン中：','로그인됨:'],
['已登入','Signed in','ログイン中','로그인됨'],
['🚪 登出','🚪 Sign out','🚪 ログアウト','🚪 로그아웃'],
['⚙️ 系統維護','⚙️ System maintenance','⚙️ システム保守','⚙️ 시스템 관리'],
['🔄 更新全台南站點快取','🔄 Refresh Tainan stop cache','🔄 台南の停留所キャッシュを更新','🔄 타이난 전체 정류장 캐시 갱신'],
['請輸入帳號與密碼','Please enter username and password','アカウントとパスワードを入力してください','계정과 비밀번호를 입력하세요'],
['帳號至少需要 # 個字','Username must be at least {1} characters','アカウントは{1}文字以上で入力してください','계정은 {1}자 이상이어야 합니다'],
['密碼至少需要 # 碼','Password must be at least {1} characters','パスワードは{1}文字以上で入力してください','비밀번호는 {1}자 이상이어야 합니다'],
['這個帳號已經被註冊了，請直接登入或換一個帳號','This username is already taken. Please sign in or choose another.','このアカウントは既に登録されています。ログインするか別のアカウントを使ってください','이미 사용 중인 계정입니다. 로그인하거나 다른 계정을 사용하세요'],
['帳號建立失敗，請稍後再試','Could not create the account. Please try again later.','アカウントを作成できませんでした。後でもう一度お試しください','계정을 만들지 못했습니다. 잠시 후 다시 시도하세요'],
['帳號或密碼錯誤','Wrong username or password','アカウントまたはパスワードが違います','계정 또는 비밀번호가 올바르지 않습니다'],
['處理中...','Processing...','処理中...','처리 중...'],
['🚌 台南公車即時時刻查詢','🚌 Tainan Bus Real-time Arrivals','🚌 台南バス リアルタイム時刻案内','🚌 타이난 버스 실시간 도착 정보'],
['📋 今日行程總覽','📋 Today at a glance','📋 本日のまとめ','📋 오늘의 요약'],
['台南市・今日天氣','Tainan · Today’s weather','台南市・今日の天気','타이난시・오늘 날씨'],
['即時到站','Live arrivals','リアルタイム到着','실시간 도착'],
['朗讀','Read aloud','読み上げ','음성 안내'],
['🔔 提醒已響起','🔔 Alert triggered','🔔 アラームが鳴りました','🔔 알림이 울렸어요'],
['動態公車','Live buses','バス位置','버스 위치'],
['路線篩選','Route filter','路線で絞り込み','노선 필터'],
['附近站牌','Nearby stops','近くの停留所','주변 정류장'],
['AI 對話','AI chat','AIチャット','AI 대화'],
['我的最愛','Favorites','お気に入り','즐겨찾기'],
['小黃公車','Yellow minibus','小黄バス','노란 미니버스'],
['站到站查詢','Stop to stop','停留所間検索','정류장 간 검색'],
['更多設定','More settings','その他の設定','설정 더보기'],
['← 返回主頁','← Back to home','← ホームへ戻る','← 홈으로'],
['🚕 小黃公車查詢','🚕 Yellow minibus search','🚕 小黄バス検索','🚕 노란 미니버스 검색'],
['小黃公車是用計程車營運的固定路線公車，查詢方式跟一般公車完全一樣。','Yellow minibuses are fixed-route buses run with taxis. You search for them exactly like regular buses.','小黄バスはタクシーで運行される定路線バスです。検索方法は通常のバスと同じです。','노란 미니버스는 택시로 운행하는 고정 노선 버스입니다. 검색 방법은 일반 버스와 같아요.'],
['選擇小黃公車路線','Select a yellow minibus route','小黄バスの路線を選択','노란 미니버스 노선 선택'],
['請選擇路線...','Select a route...','路線を選択...','노선을 선택하세요...'],
['共 # 條小黃公車路線（資料來自 TDX，依營運業者自動判斷）','{1} yellow minibus routes (data from TDX, detected by operator)','小黄バス路線 全{1}本（TDXのデータ、運行事業者で自動判定）','노란 미니버스 노선 총 {1}개 (TDX 데이터, 운영사 기준 자동 판별)'],
['路線清單載入中...','Loading route list...','路線リストを読み込み中...','노선 목록 불러오는 중...'],
['❌ 路線清單載入失敗','❌ Failed to load route list','❌ 路線リストの読み込みに失敗','❌ 노선 목록을 불러오지 못했습니다'],
['載入路線清單中...','Loading route list...','路線リストを読み込み中...','노선 목록 불러오는 중...'],
['路線清單載入失敗','Failed to load route list','路線リストの読み込みに失敗','노선 목록을 불러오지 못했습니다'],
['🔍 路線篩選','🔍 Route filter','🔍 路線フィルター','🔍 노선 필터'],
['點選顏色或數字篩選：','Tap a color or number to filter:','色または数字をタップして絞り込み：','색상이나 숫자를 눌러 걸러 보세요:'],
['綠','Green','緑','초록'],
['橘','Orange','橙','주황'],
['棕','Brown','茶','갈색'],
['藍','Blue','青','파랑'],
['紅','Red','赤','빨강'],
['黃','Yellow','黄','노랑'],
['市區','City','市区','시내'],
['高鐵','HSR','高鐵','고속철'],
['高鐵快捷','HSR Express','高鐵シャトル','고속철 급행'],
['觀光','Tourist','観光','관광'],
['東山','Dongshan','東山','둥산'],
['梅嶺','Meiling','梅嶺','메이링'],
['菱波','Lingbo','菱波','링보'],
['雙層','Double-decker','2階建て','2층버스'],
['雙層巴士','Double-decker bus','2階建てバス','2층 버스'],
['❌ 清除篩選','❌ Clear filter','❌ 絞り込み解除','❌ 필터 해제'],
['顯示：全部路線','Showing: all routes','表示：全路線','표시: 전체 노선'],
['篩選：【#】（共 # 條）','Filter: [{1}] ({2} routes)','絞り込み：【{1}】（全{2}本）','필터: 【{1}】 (총 {2}개 노선)'],
['這個篩選條件下沒有符合的路線','No routes match this filter','この条件に合う路線はありません','이 조건에 맞는 노선이 없습니다'],
['選擇路線','Select route','路線を選択','노선 선택'],
['請選擇或輸入路線...','Select or type a route...','路線を選択または入力...','노선을 선택하거나 입력하세요...'],
['☆ 加入最愛','☆ Add to favorites','☆ お気に入りに追加','☆ 즐겨찾기 추가'],
['⭐ 已加入最愛','⭐ In favorites','⭐ お気に入り登録済み','⭐ 즐겨찾기에 추가됨'],
['等候站','Waiting stop','乗車停留所','승차 정류장'],
['目的地','Destination','目的地','목적지'],
['🔔 到站前幾分鐘提醒（會有鈴聲）','🔔 Alert minutes before arrival (with sound)','🔔 到着の何分前に通知（音あり）','🔔 도착 몇 분 전에 알릴까요? (알림음 포함)'],
['🔔 加入到站提醒','🔔 Add arrival alert','🔔 到着アラームを追加','🔔 도착 알림 추가'],
['請選擇路線','Please select a route','路線を選択してください','노선을 선택하세요'],
['📅 查看固定時刻表','📅 View fixed timetable','📅 固定時刻表を見る','📅 고정 시간표 보기'],
['時刻表載入中...','Loading timetable...','時刻表を読み込み中...','시간표 불러오는 중...'],
['這條路線目前沒有公告固定時刻表','This route has no published fixed timetable','この路線には現在、固定時刻表の公開がありません','이 노선은 현재 공지된 고정 시간표가 없습니다'],
['❌ 時刻表載入失敗','❌ Failed to load timetable','❌ 時刻表の読み込みに失敗','❌ 시간표를 불러오지 못했습니다'],
['查無這條路線的固定時刻表','No fixed timetable found for this route','この路線の固定時刻表が見つかりません','이 노선의 고정 시간표를 찾을 수 없습니다'],
['TDX 目前查不到這條路線的固定時刻表（可能是依班距發車的幹線，沒有公告時刻表）','TDX has no fixed timetable for this route right now (it may be a trunk line that runs at intervals without a published timetable).','TDXにこの路線の固定時刻表がありません（運行間隔で走る幹線で、時刻表が公開されていない可能性があります）。','TDX에 이 노선의 고정 시간표가 없습니다 (배차 간격으로 운행하는 간선이라 시간표가 공개되지 않았을 수 있어요).'],
['一、二、三、四、五','Mon–Fri','月〜金','월~금'],
['六、日','Sat–Sun','土・日','토·일'],
['六','Sat','土','토'],
['日','Sun','日','일'],
['每日','Daily','毎日','매일'],
['⚠️ 尚未更新資料，目前顯示的可能是稍早的結果','⚠️ Data not updated yet — what you see may be earlier results','⚠️ データ未更新です。表示は少し前の結果の可能性があります','⚠️ 아직 데이터가 갱신되지 않았습니다. 표시된 내용은 조금 전 결과일 수 있어요'],
['➡️ 往','➡️ To','➡️ 行先：','➡️ 방면:'],
['⬅️ 往','⬅️ To','⬅️ 行先：','⬅️ 방면:'],
['🔄 重新整理','🔄 Refresh','🔄 更新','🔄 새로고침'],
['🔀 本路線目前有','🔀 This route currently has','🔀 この路線には現在','🔀 이 노선에는 현재'],
['班支線／繞道車輛','branch / detour bus(es)','台の支線・迂回車両があります','대의 지선·우회 차량이 있습니다'],
['🔊 朗讀公車資訊','🔊 Read bus info aloud','🔊 バス情報を読み上げ','🔊 버스 정보 음성 안내'],
['⏹ 停止','⏹ Stop','⏹ 停止','⏹ 중지'],
['👈 請從左側選擇路線開始查詢','👈 Choose a route on the left to start','👈 左側から路線を選んで検索を始めてください','👈 왼쪽에서 노선을 선택해 검색을 시작하세요'],
['去程','Outbound','往路','가는 방향'],
['回程','Return','復路','오는 방향'],
['（去程）','(Outbound)','（往路）','(가는 방향)'],
['（回程）','(Return)','（復路）','(오는 방향)'],
['➡️ 去程','➡️ Outbound','➡️ 往路','➡️ 가는 방향'],
['⬅️ 回程','⬅️ Return','⬅️ 復路','⬅️ 오는 방향'],
['✕ 收合設定','✕ Hide settings','✕ 設定を閉じる','✕ 설정 접기'],
['☰ 更多設定','☰ More settings','☰ その他の設定','☰ 설정 더보기'],
['⏱️ #s 後自動更新','⏱️ Auto-refresh in {1}s','⏱️ {1}秒後に自動更新','⏱️ {1}초 후 자동 갱신'],
['🤖 AI 助理','🤖 AI Assistant','🤖 AIアシスタント','🤖 AI 도우미'],
['目前對話：','Current chat:','現在のチャット：','현재 대화:'],
['有什麼我可以幫忙的嗎？','How can I help you?','何かお手伝いできますか？','무엇을 도와드릴까요?'],
['送出','Send','送信','보내기'],
['思考中...','Thinking...','考え中...','생각 중...'],
['AI 錯誤','AI error','AIエラー','AI 오류'],
['AI 模組未啟用，請檢查 GROQ_API_KEY。','The AI module is not enabled. Please check GROQ_API_KEY.','AIモジュールが有効になっていません。GROQ_API_KEYを確認してください。','AI 모듈이 활성화되어 있지 않습니다. GROQ_API_KEY를 확인하세요.'],
['缺少訊息內容','Message is empty','メッセージがありません','메시지가 비어 있습니다'],
['尚未查詢','Not searched yet','未検索','아직 검색하지 않음'],
['尚未查詢路線','No route searched yet','路線は未検索です','아직 검색한 노선이 없습니다'],
['📍 附近公車站','📍 Nearby bus stops','📍 近くのバス停','📍 주변 버스 정류장'],
['📡 自動取得座標','📡 Get my coordinates','📡 座標を自動取得','📡 내 좌표 가져오기'],
['緯度：','Latitude:','緯度：','위도:'],
['點上方取得','Tap above to get','上のボタンで取得','위 버튼으로 가져오기'],
['經度：','Longitude:','経度：','경도:'],
['緯度','Latitude','緯度','위도'],
['例：22.9997','e.g. 22.9997','例：22.9997','예: 22.9997'],
['經度','Longitude','経度','경도'],
['例：120.2270','e.g. 120.2270','例：120.2270','예: 120.2270'],
['🔍 搜尋附近站牌','🔍 Search nearby stops','🔍 近くの停留所を検索','🔍 주변 정류장 검색'],
['瀏覽器不支援定位','Geolocation not supported','位置情報に未対応です','위치 정보를 지원하지 않습니다'],
['瀏覽器不支援定位功能','This browser does not support geolocation','このブラウザは位置情報に対応していません','이 브라우저는 위치 정보를 지원하지 않습니다'],
['請允許瀏覽器定位權限','Please allow location permission in your browser','ブラウザの位置情報の許可を有効にしてください','브라우저의 위치 권한을 허용해 주세요'],
['請輸入有效數字','Please enter valid numbers','有効な数値を入力してください','올바른 숫자를 입력하세요'],
['搜尋中...','Searching...','検索中...','검색 중...'],
['附近 #m 內無公車站牌','No bus stops within {1} m','{1}m以内にバス停はありません','{1}m 이내에 버스 정류장이 없습니다'],
['找到 # 個站牌（#m內）：','Found {1} stops (within {2} m):','{1}か所の停留所が見つかりました（{2}m以内）：','정류장 {1}곳을 찾았습니다 ({2}m 이내):'],
['無法載入站牌資料','Could not load stop data','停留所データを読み込めません','정류장 데이터를 불러올 수 없습니다'],
['# 公尺','{1} m','{1}m','{1}m'],
['# 公里','{1} km','{1}km','{1}km'],
['# 公里（直線估算）','{1} km (straight-line estimate)','{1}km（直線距離の概算）','{1}km (직선거리 추정)'],
['🚌 台南公車即時地圖','🚌 Tainan Live Bus Map','🚌 台南バス リアルタイムマップ','🚌 타이난 실시간 버스 지도'],
['篩選路線（留空或輸入「#」＝顯示全部路線），例：#, #','Filter routes (leave blank or type “{1}” = show all routes), e.g. {2}, {3}','路線を絞り込み（空欄または「{1}」で全路線を表示）例：{2}, {3}','노선 필터 (비워 두거나 “{1}” 입력 = 전체 노선 표시) 예: {2}, {3}'],
['全部','All','全て','전체'],
['全部路線','All routes','全路線','전체 노선'],
['💡 可輸入多條路線（用逗號分隔），或直接點下面路線清單裡的項目累加選取','💡 Enter several routes separated by commas, or tap items in the list below to add them','💡 複数の路線をカンマ区切りで入力するか、下のリストの項目をタップして追加できます','💡 쉼표로 구분해 여러 노선을 입력하거나, 아래 목록의 항목을 눌러 추가하세요'],
['🔄 更新','🔄 Update','🔄 更新','🔄 갱신'],
['🏠 回查詢頁','🏠 Back to search','🏠 検索ページへ','🏠 검색 페이지로'],
['📍 定位我的位置','📍 Locate me','📍 現在地を表示','📍 내 위치 보기'],
['💾 抓取並儲存路線原始資料（Shape＋StopOfRoute）','💾 Fetch & save raw route data (Shape + StopOfRoute)','💾 路線の元データを取得・保存（Shape＋StopOfRoute）','💾 노선 원본 데이터 가져와 저장 (Shape + StopOfRoute)'],
['輸入路線名稱，例：#','Enter a route name, e.g. {1}','路線名を入力（例：{1}）','노선 이름을 입력하세요 (예: {1})'],
['💾 抓取並儲存到檔案','💾 Fetch & save to file','💾 取得してファイルに保存','💾 가져와서 파일로 저장'],
['載入中...','Loading...','読み込み中...','불러오는 중...'],
['💡 放大地圖至街道等級即可看到各站站名；任何縮放層級皆可點擊圓點查看站名','💡 Zoom in to street level to see stop names; at any zoom level you can tap a dot to see its name','💡 地図を道路レベルまで拡大すると停留所名が表示されます。どの縮尺でも点をタップすると名前を確認できます','💡 지도를 도로 수준까지 확대하면 정류장 이름이 보이고, 어떤 배율에서도 점을 누르면 이름을 볼 수 있어요'],
['搜尋路線...','Search routes...','路線を検索...','노선 검색...'],
['請點選路線，或按下方「#」載入公車動態與軌跡','Pick a route, or tap “{1}” below to load bus positions and route lines','路線を選ぶか、下の「{1}」を押してバスの位置と路線を読み込みます','노선을 선택하거나 아래 “{1}”를 눌러 버스 위치와 노선 경로를 불러오세요'],
['載入失敗','Failed to load','読み込みに失敗しました','불러오지 못했습니다'],
['地圖尚未載入完成，請稍後再試','The map is not ready yet. Please try again shortly.','地図がまだ読み込まれていません。しばらくしてからお試しください','지도가 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요'],
['定位中...','Locating...','位置を取得中...','위치 확인 중...'],
['📍 我的位置','📍 My location','📍 現在地','📍 내 위치'],
['已定位到你目前的位置','Moved to your current location','現在地に移動しました','현재 위치로 이동했습니다'],
['無法取得定位，請確認已允許瀏覽器的定位權限','Could not get your location. Please make sure location permission is allowed.','位置を取得できません。ブラウザの位置情報の許可を確認してください','위치를 가져올 수 없습니다. 브라우저의 위치 권한을 확인하세요'],
['⚠️ 請輸入路線名稱','⚠️ Please enter a route name','⚠️ 路線名を入力してください','⚠️ 노선 이름을 입력하세요'],
['抓取「#」的 Shape 與 StopOfRoute 資料中...','Fetching Shape and StopOfRoute data for “{1}”...','「{1}」のShapeとStopOfRouteデータを取得中...','“{1}”의 Shape와 StopOfRoute 데이터를 가져오는 중...'],
['✅ 已儲存','✅ Saved','✅ 保存しました','✅ 저장됨'],
['路線軌跡：','Route line: ','路線の軌跡：','노선 경로: '],
['站牌清單：','Stop list: ','停留所リスト：','정류장 목록: '],
['❌ 抓取失敗','❌ Fetch failed','❌ 取得に失敗','❌ 가져오기 실패'],
['點一下可直接改用這個名稱重新抓取：','Tap to retry with this name:','タップするとこの名前で再取得します：','눌러서 이 이름으로 다시 가져오기:'],
['TDX 上找不到名稱包含「#」的路線，可能是這個字首本身就不對','No route on TDX contains “{1}”. The prefix itself may be wrong.','TDXに「{1}」を含む路線が見つかりません。入力した文字が違うかもしれません','TDX에서 “{1}”이(가) 들어간 노선을 찾을 수 없습니다. 입력한 글자가 잘못되었을 수 있어요'],
['TDX 上名稱包含「#」的路線（點一下可直接改用這個名稱查詢）：','Routes on TDX containing “{1}” (tap one to search with that name):','TDX上で「{1}」を含む路線（タップするとその名前で検索）：','TDX에서 “{1}”이(가) 들어간 노선 (눌러서 그 이름으로 검색):'],
['查詢失敗','Search failed','検索に失敗しました','검색 실패'],
['顯示 # 條路線・# 台公車','Showing {1} routes · {2} buses','{1}路線・{2}台を表示','{1}개 노선・버스 {2}대 표시 중'],
['🔼 收合公車定位清單（共 # 台）','🔼 Hide bus position list ({1})','🔼 バス位置リストを閉じる（{1}台）','🔼 버스 위치 목록 접기 ({1}대)'],
['🚌 查看路線上每台公車的最新定位（共 # 台）','🚌 View the latest position of every bus on the route ({1})','🚌 路線上の各バスの最新位置を見る（{1}台）','🚌 노선 위 각 버스의 최신 위치 보기 ({1}대)'],
['目前查無這個篩選條件下的公車即時定位（該路線可能暫時沒有營運中的車輛，也可能是路線名稱跟 TDX 登記的不完全一樣）','No live bus positions for this filter (the route may have no buses running right now, or its name may differ from the one registered on TDX).','この条件に該当するバスの位置情報はありません（運行中の車両がないか、路線名がTDXの登録名と異なる可能性があります）。','이 조건에 해당하는 실시간 버스 위치가 없습니다 (운행 중인 차량이 없거나 노선 이름이 TDX 등록명과 다를 수 있어요).'],
['🔍 查詢 TDX 正確路線名稱','🔍 Look up the exact TDX route name','🔍 TDXの正確な路線名を検索','🔍 TDX 정확한 노선 이름 검색'],
['🚌 目前共 # 台公車最新定位（點項目可在地圖上定位）：','🚌 Latest positions of {1} buses (tap an item to find it on the map):','🚌 現在{1}台のバスの最新位置（項目をタップすると地図上に表示）：','🚌 현재 버스 {1}대의 최신 위치 (항목을 누르면 지도에 표시):'],
['車牌','Plate','ナンバー','번호판'],
['方向','Direction','方向','방향'],
['速度','Speed','速度','속도'],
['已儲存路線原始資料（Shape＋StopOfRoute）','Saved raw route data (Shape + StopOfRoute)','保存済みの路線元データ（Shape＋StopOfRoute）','저장된 노선 원본 데이터 (Shape + StopOfRoute)'],
['已儲存路線原始資料（Shape＋StopOfRoute）－目前不在篩選範圍內，點一下即可加入','Saved raw route data (Shape + StopOfRoute) – not in the current filter; tap to add','保存済みの路線元データ（Shape＋StopOfRoute）－現在の絞り込み外です。タップで追加','저장된 노선 원본 데이터 (Shape + StopOfRoute) – 현재 필터 밖입니다. 눌러서 추가'],
['# 條路線','{1} routes','{1}路線','{1}개 노선'],
['無法取得即時動態。','Could not get real-time information.','リアルタイム情報を取得できません。','실시간 정보를 가져올 수 없습니다.'],
['無法取得即時動態','Could not get real-time information','リアルタイム情報を取得できません','실시간 정보를 가져올 수 없습니다'],
['缺少路線','Route missing','路線が指定されていません','노선이 지정되지 않았습니다'],
['缺少路線名稱','Route name missing','路線名が指定されていません','노선 이름이 지정되지 않았습니다'],
['⚠️ 無法載入【#】站點。','⚠️ Could not load stops for [{1}].','⚠️ 【{1}】の停留所を読み込めませんでした。','⚠️ 【{1}】 정류장을 불러올 수 없습니다.'],
['🌙 末班車已收車','🌙 Last bus has departed','🌙 終バスは終了しました','🌙 막차가 운행을 마쳤습니다'],
['🌙 末班車已收車，明日 @ 恢復發車','🌙 Service has ended. Buses resume tomorrow at {1}.','🌙 本日の運行は終了しました。明日 {1} に再開します。','🌙 운행이 종료되었습니다. 내일 {1}에 다시 시작합니다.'],
['🌡️ 台南目前天氣','🌡️ Tainan weather now','🌡️ 台南の現在の天気','🌡️ 타이난 현재 날씨'],
['氣溫 #°C','{1}°C','気温 {1}°C','{1}°C'],
['風速 # km/h','wind {1} km/h','風速 {1}km/h','풍속 {1}km/h'],
['大致晴朗🌤️','Mostly clear 🌤️','おおむね晴れ🌤️','대체로 맑음🌤️'],
['晴天☀️','Sunny ☀️','晴れ☀️','맑음☀️'],
['有霧🌫️','Foggy 🌫️','霧🌫️','안개🌫️'],
['部分多雲⛅','Partly cloudy ⛅','一部曇り⛅','구름 조금⛅'],
['陰天☁️','Overcast ☁️','曇り☁️','흐림☁️'],
['中雨🌧️','Moderate rain 🌧️','雨🌧️','비🌧️'],
['大雨🌧️','Heavy rain 🌧️','大雨🌧️','폭우🌧️'],
['小雨🌧️','Light rain 🌧️','小雨🌧️','약한 비🌧️'],
['毛毛雨🌦️','Drizzle 🌦️','霧雨🌦️','이슬비🌦️'],
['陣雨🌦️','Showers 🌦️','にわか雨🌦️','소나기🌦️'],
['雷雨⛈️','Thunderstorm ⛈️','雷雨⛈️','뇌우⛈️'],
['未知天氣','Unknown weather','天気不明','날씨 정보 없음'],
['無法取得天氣','Weather unavailable','天気を取得できません','날씨를 가져올 수 없습니다'],
['晴朗舒適','Clear and comfortable','晴れて快適','맑고 쾌적함'],
['（目前共 # 台營運中）','({1} buses in service)','（現在 {1} 台が運行中）','(현재 {1}대 운행 중)'],
['🚌 # 全線即時動態','🚌 {1} — live status of the whole route','🚌 {1} 全線リアルタイム状況','🚌 {1} 전 구간 실시간 현황'],
['♿ 無障礙','♿ Accessible','♿ バリアフリー','♿ 저상버스'],
['🚌 一般車','🚌 Standard bus','🚌 一般車両','🚌 일반 차량'],
['⚡ 電動','⚡ Electric','⚡ 電気バス','⚡ 전기버스'],
['🚲 可借:# 可還:#','🚲 Rent: {1}  Return: {2}','🚲 貸出可:{1}  返却可:{2}','🚲 대여 {1}  반납 {2}'],
['－ 🚌 # 🔀 往','– 🚌 {1} 🔀 to','－ 🚌 {1} 🔀 行先','– 🚌 {1} 🔀 방면'],
['無障礙低底盤。','Low-floor accessible bus.','ノンステップバスです。','저상버스입니다.'],
['電動公車。','Electric bus.','電気バスです。','전기버스입니다.'],
['即將進站','Arriving soon','まもなく到着','곧 도착'],
['進站中','Arriving','到着中','도착 중'],
['# 分鐘','{1} min','{1}分','{1}분'],
['（時刻表估計）','(timetable estimate)','（時刻表による推定）','(시간표 기준 추정)'],
['即將進站（時刻表估計）','Arriving soon (timetable estimate)','まもなく到着（時刻表による推定）','곧 도착 (시간표 기준 추정)'],
['# 分鐘（時刻表估計）','{1} min (timetable estimate)','{1}分（時刻表による推定）','{1}분 (시간표 기준 추정)'],
['約 # 分鐘（時刻表估計）','≈ {1} min (timetable estimate)','約{1}分（時刻表による推定）','약 {1}분 (시간표 기준 추정)'],
['尚未發車','Not departed yet','未発車','출발 전'],
['交管不停靠','Skipped (traffic control)','交通規制で通過','교통통제로 통과'],
['末班車已過','Last bus has passed','終バスは通過済み','막차 지나감'],
['今日停駛','No service today','本日運休','오늘 운행 없음'],
['營運中（無預估時間）','In service (no estimate)','運行中（到着予測なし）','운행 중 (예상 시간 없음)'],
['無車牌','No plate','ナンバーなし','번호판 없음'],
['大巴','Large bus','大型バス','대형 버스'],
['中巴','Medium bus','中型バス','중형 버스'],
['小巴','Small bus','小型バス','소형 버스'],
['資料剛更新','Data just updated','データを今更新しました','데이터 방금 갱신됨'],
['資料 # 分鐘前','Data {1} min ago','データ {1}分前','데이터 {1}분 전'],
['📡 到站資料','📡 Arrival data fetched','📡 到着データ取得：','📡 도착 데이터 수집: '],
['抓取','','',''],
['剛更新','just updated','たった今更新','방금 갱신'],
['# 分鐘前','{1} min ago','{1}分前','{1}분 전'],
['# 小時 # 分鐘前','{1} h {2} min ago','{1}時間{2}分前','{1}시간 {2}분 전'],
['# 小時前','{1} h ago','{1}時間前','{1}시간 전'],
['（尖峰約每 # 分、平常約每 # 分更新；倒數是依時間推算，下次更新會校正）','(Updated about every {1} min at rush hour and {2} min otherwise; the countdown is estimated and corrected at the next update.)','（ラッシュ時は約{1}分、通常は約{2}分ごとに更新。カウントダウンは推定で、次回の更新で補正されます）','(혼잡 시간대에는 약 {1}분, 평소에는 약 {2}분마다 갱신됩니다. 카운트다운은 추정값이며 다음 갱신 때 보정됩니다)'],
['⚠️ 尚未更新資料','⚠️ Data not updated yet','⚠️ データ未更新','⚠️ 아직 데이터 갱신 전'],
['🚲 UBike 更快！實際騎車約 # 分鐘（#），比等公車+搭車（約 # 分鐘）更省時。','🚲 UBike is faster! Cycling takes about {1} min ({2}), vs. about {3} min waiting for and riding the bus.','🚲 UBikeの方が速い！自転車で約{1}分（{2}）、バスの待ち＋乗車は約{3}分です。','🚲 UBike가 더 빨라요! 자전거로 약 {1}분 ({2}), 버스 대기+탑승은 약 {3}분입니다.'],
['- 起點 UBike：#（可借 # 輛）','- Start UBike: {1} ({2} bikes available)','- 出発地のUBike：{1}（貸出可 {2}台）','- 출발지 UBike: {1} (대여 가능 {2}대)'],
['- 終點 UBike：#（可還 # 格）','- End UBike: {1} ({2} docks free)','- 目的地のUBike：{1}（返却可 {2}枠）','- 도착지 UBike: {1} (반납 가능 {2}칸)'],
['🔔 已設定：#（往#）到站前 # 分鐘提醒','🔔 Alert set: {1} (to {2}), {3} min before arrival','🔔 設定済み：{1}（{2}方面）到着{3}分前に通知','🔔 설정됨: {1} ({2} 방면) 도착 {3}분 전 알림'],
['（往#）－ #','(to {1}) – {2}','（{1}方面）－ {2}','({1} 방면) – {2}'],
['到站前 # 分鐘提醒','Alert {1} min before arrival','到着{1}分前に通知','도착 {1}분 전 알림'],
['查詢中...','Searching...','検索中...','검색 중...'],
['🔔 #（往#）即將抵達「#」','🔔 {1} (to {2}) is about to reach “{3}”','🔔 {1}（{2}方面）がまもなく「{3}」に到着','🔔 {1} ({2} 방면) 곧 “{3}” 도착'],
['公車到站提醒','Bus arrival alert','バス到着アラート','버스 도착 알림'],
['請先選擇路線與站牌，再加入到站提醒','Please choose a route and a stop before adding an alert','アラームを追加する前に、路線と停留所を選んでください','도착 알림을 추가하기 전에 노선과 정류장을 선택하세요'],
['最多只能設定 # 個到站提醒，請先刪除幾個舊的','You can set up to {1} alerts. Please delete some old ones first.','アラームは最大{1}件までです。古いものを削除してください','도착 알림은 최대 {1}개까지 설정할 수 있습니다. 오래된 알림을 먼저 삭제하세요'],
['離線化中，請稍候（可能需要幾分鐘）...','Building offline cache, please wait (may take a few minutes)...','オフライン化中です。しばらくお待ちください（数分かかる場合があります）...','오프라인 캐시를 만드는 중입니다. 잠시만 기다려 주세요 (몇 분 걸릴 수 있어요)...'],
['🎉 快取建立成功！共 # 條路線','🎉 Cache built! {1} routes','🎉 キャッシュを作成しました！全{1}路線','🎉 캐시를 만들었습니다! 총 {1}개 노선'],
['建立失敗','Build failed','作成に失敗しました','생성 실패'],
['24 小時內已經更新過了（為了節省 TDX 額度），請明天再試','Already refreshed within the last 24 hours (to save TDX quota). Please try again tomorrow.','24時間以内に更新済みです（TDXの利用枠を節約するため）。明日もう一度お試しください','24시간 이내에 이미 갱신했습니다 (TDX 사용량 절약). 내일 다시 시도하세요'],
['目前正在更新中，請稍後再看結果','An update is in progress. Please check back shortly.','更新中です。しばらくしてから結果をご確認ください','갱신 중입니다. 잠시 후 결과를 확인하세요'],
['請選擇出發站和目的站','Please select a start and a destination','出発停留所と目的停留所を選択してください','출발 정류장과 도착 정류장을 선택하세요'],
['出發站和目的站不能相同','Start and destination must be different','出発と目的地は別の停留所にしてください','출발 정류장과 도착 정류장은 달라야 합니다'],
['暫時無法取得站點資料，請稍後再試','Stop data is temporarily unavailable. Please try again later.','停留所データを一時的に取得できません。後でもう一度お試しください','정류장 데이터를 일시적으로 가져올 수 없습니다. 잠시 후 다시 시도하세요'],
['站序資料還沒準備好，請稍後再試','Stop sequence data is not ready yet. Please try again shortly.','停留所の順序データがまだ準備できていません。しばらくしてからお試しください','정류장 순서 데이터가 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요'],
['轉乘時間估算失敗，請稍後再試','Could not estimate trip times. Please try again later.','所要時間を見積もれませんでした。後でもう一度お試しください','소요 시간을 추정하지 못했습니다. 잠시 후 다시 시도하세요'],
['不到 # 分','Under {1} min','{1}分未満','{1}분 미만'],
['# 分','{1} min','{1}分','{1}분'],
['# 小時 # 分','{1} h {2} min','{1}時間{2}分','{1}시간 {2}분'],
['# 小時','{1} h','{1}時間','{1}시간'],
['無資料','No data','データなし','데이터 없음'],
['約 # 分','≈ {1} min','約{1}分','약 {1}분'],
['約 # 小時 # 分','≈ {1} h {2} min','約{1}時間{2}分','약 {1}시간 {2}분'],
['約 # 小時','≈ {1} h','約{1}時間','약 {1}시간'],
['@ 抵達','Arrive {1}','{1} 着','{1} 도착'],
['至少 # 分','At least {1} min','少なくとも{1}分','최소 {1}분'],
['至少 # 小時 # 分','At least {1} h {2} min','少なくとも{1}時間{2}分','최소 {1}시간 {2}분'],
['不含第二班等車','excl. wait for the 2nd bus','2本目の待ち時間を除く','두 번째 버스 대기 제외'],
['無法估算','Cannot estimate','見積もり不可','추정 불가'],
['下一班即將進站','Next bus arriving soon','次のバスはまもなく到着','다음 버스 곧 도착'],
['下一班約 # 分鐘','Next bus in about {1} min','次のバスは約{1}分後','다음 버스 약 {1}분 후'],
['下一班','Next bus','次のバス','다음 버스'],
['在「#」等車','Wait at “{1}”','「{1}」で待つ','“{1}”에서 대기'],
['搭 # 往','Take {1} to','{1} に乗車・行先','{1} 탑승 · 방면'],
['坐 # 站','Ride {1} stops','{1}停留所乗車','{1}정거장 탑승'],
['抵達「#」','Arrive at “{1}”','「{1}」に到着','“{1}” 도착'],
['直達・# 站','Direct · {1} stops','直通・{1}停留所','직행 · {1}정거장'],
['# 站','{1} stops','{1}停留所','{1}정거장'],
['步行約 # 公尺到「#」','Walk about {1} m to “{2}”','「{2}」まで約{1}m歩く','“{2}”까지 약 {1}m 도보'],
['在「#」下車後步行','Get off at “{1}” and walk','「{1}」で降りて徒歩','“{1}”에서 하차 후 도보'],
['在「#」下車轉乘','Get off at “{1}” and transfer','「{1}」で降りて乗り換え','“{1}”에서 하차 후 환승'],
['同站轉乘','Same-stop transfer','同じ停留所で乗り換え','같은 정류장에서 환승'],
['坐 # 站・到「#」','Ride {1} stops to “{2}”','{1}停留所乗車・「{2}」まで','{1}정거장 탑승 · “{2}”까지'],
['等 # 往','Wait for {1} to','{1} 待ち・行先','{1} 대기 · 방면'],
['第二班車','2nd bus','2本目のバス','두 번째 버스'],
['搭 #','Take {1}','{1} に乗車','{1} 탑승'],
['轉乘 # 次・# 站','Transfer ×{1} · {2} stops','乗換{1}回・{2}停留所','환승 {1}회 · {2}정거장'],
['🔄 重新計算時間','🔄 Recalculate times','🔄 時間を再計算','🔄 시간 다시 계산'],
['⏱ 運算轉乘時間','⏱ Calculate trip times','⏱ 所要時間を計算','⏱ 소요 시간 계산'],
['按下按鈕，估算每個方案的等車、搭乘、步行與抵達時間','Tap to estimate waiting, riding, walking and arrival times for each option','ボタンを押すと、各プランの待ち時間・乗車時間・徒歩・到着時刻を概算します','버튼을 누르면 각 경로의 대기·탑승·도보·도착 시간을 추정합니다'],
['現在 @・搭乘時間以每站約 # 分估算；等車依「#」到站、「#」或歷史「#」（平均等班距的一半）','Now {1} · Riding time is estimated at about {2} min per stop; waiting uses “{3}” arrivals, “{4}” or historical “{5}” (average wait = half the headway)','現在 {1}・乗車時間は1停留所あたり約{2}分で概算。待ち時間は「{3}」到着、「{4}」、または過去の「{5}」（平均待ち＝運行間隔の半分）を使用','현재 {1} · 탑승 시간은 정류장당 약 {2}분으로 추정하며, 대기 시간은 “{3}” 도착, “{4}” 또는 과거 “{5}” 기준입니다 (평균 대기 = 배차 간격의 절반)'],
['即時','Live','リアルタイム','실시간'],
['時刻表','Timetable','時刻表','시간표'],
['班距','Headway','運行間隔','배차 간격'],
['✅ 直達（共 # 個方案）','✅ Direct ({1} options)','✅ 直通（{1}プラン）','✅ 직행 ({1}개 경로)'],
['無直達路線','No direct route','直通路線なし','직행 노선 없음'],
['🔄 轉乘一次方案（共 # 個，依站數排序）','🔄 One-transfer options ({1}, sorted by number of stops)','🔄 1回乗り換えプラン（{1}件、停留所数順）','🔄 1회 환승 경로 ({1}개, 정거장 수 순)'],
['🔄 轉乘一次方案（共 # 個，依總時間排序）','🔄 One-transfer options ({1}, sorted by total time)','🔄 1回乗り換えプラン（{1}件、所要時間順）','🔄 1회 환승 경로 ({1}개, 총 소요 시간 순)'],
['※ 尚未運算時間，目前只列站數；「#」指的是第一段車。','※ Times not calculated yet; only stop counts are shown. “{1}” refers to the first bus.','※ 所要時間は未計算で、停留所数のみ表示しています。「{1}」は最初のバスを指します。','※ 소요 시간은 아직 계산되지 않아 정거장 수만 표시합니다. “{1}”은(는) 첫 번째 버스를 뜻합니다.'],
['找不到直達或一次轉乘方案，請考慮其他方式','No direct or one-transfer option found. Please consider other ways.','直通・1回乗り換えのプランが見つかりません。他の方法をご検討ください。','직행 또는 1회 환승 경로를 찾지 못했습니다. 다른 방법을 고려해 보세요.'],
['✅ 直達路線（共 # 條）','✅ Direct routes ({1})','✅ 直通路線（{1}本）','✅ 직행 노선 ({1}개)'],
['🔄 轉乘一次方案（共 # 個）','🔄 One-transfer options ({1})','🔄 1回乗り換えプラン（{1}件）','🔄 1회 환승 경로 ({1}개)'],
['搭','Take','乗車','탑승'],
['→ 在','→ at','→ ','→ '],
['轉','transfer to','乗換:','환승:'],
['找不到一次轉乘方案，請考慮其他方式','No one-transfer option found. Please consider other ways.','1回乗り換えのプランが見つかりません。他の方法をご検討ください。','1회 환승 경로를 찾지 못했습니다. 다른 방법을 고려해 보세요.'],
['運算中...','Calculating...','計算中...','계산 중...'],
['約 #','About {1}','約 {1}','약 {1}'],
['約 # 分鐘','≈ {1} min','約{1}分','약 {1}분'],
['🔗 分享這個站牌／路線（連結＋QR code）','🔗 Share this stop / route (link + QR code)','🔗 この停留所・路線を共有（リンク＋QRコード）','🔗 이 정류장/노선 공유 (링크 + QR 코드)'],
['QR code 產生中...','Generating QR code...','QRコードを生成中...','QR 코드 생성 중...'],
['📋 複製連結','📋 Copy link','📋 リンクをコピー','📋 링크 복사'],
['✕ 關閉','✕ Close','✕ 閉じる','✕ 닫기'],
['✅ 已複製','✅ Copied','✅ コピーしました','✅ 복사됨'],
['📤 分享','📤 Share','📤 共有','📤 공유'],
['台南公車','Tainan Bus','台南バス','타이난 버스'],
['🔗 #','🔗 {1}','🔗 {1}','🔗 {1}'],
['🔗 分享這一站','🔗 Share this stop','🔗 この停留所を共有','🔗 이 정류장 공유'],
['分享這一站','Share this stop','この停留所を共有','이 정류장 공유'],
['用手機掃描 QR code 或點連結，會直接打開這條路線。','Scan the QR code with your phone or tap the link to open this route directly.','スマホでQRコードを読み取るかリンクをタップすると、この路線が直接開きます。','휴대폰으로 QR 코드를 스캔하거나 링크를 누르면 이 노선이 바로 열립니다.'],
['用手機掃描 QR code 或點連結，會直接打開這條路線並停在這一站。','Scan the QR code with your phone or tap the link to open this route right at this stop.','スマホでQRコードを読み取るかリンクをタップすると、この停留所でこの路線が直接開きます。','휴대폰으로 QR 코드를 스캔하거나 링크를 누르면 이 정류장에서 이 노선이 바로 열립니다.'],
['QR code 載入失敗（網路問題），請直接複製連結。','Could not load the QR code (network issue). Please copy the link instead.','QRコードを読み込めませんでした（ネットワークの問題）。リンクをコピーしてください。','QR 코드를 불러오지 못했습니다 (네트워크 문제). 링크를 복사해 사용하세요.'],
['📊 歷史班距','📊 Typical headway','📊 過去の運行間隔','📊 평균 배차 간격'],
['📊 歷史班距（上班日・# 點）','📊 Typical headway (weekdays · {1}:00)','📊 過去の運行間隔（平日・{1}時）','📊 평균 배차 간격 (평일 · {1}시)'],
['📊 歷史班距（假日・# 點）','📊 Typical headway (weekends/holidays · {1}:00)','📊 過去の運行間隔（休日・{1}時）','📊 평균 배차 간격 (휴일 · {1}시)'],
['還沒有累積到統計資料（系統每次更新到站資料時會自動累積，約一兩天後會有數字）。','No statistics yet (collected automatically with every arrival update; numbers appear after a day or two).','統計データはまだありません（到着情報の更新ごとに自動で蓄積され、1〜2日ほどで表示されます）。','아직 통계가 없습니다 (도착 정보를 갱신할 때마다 자동으로 쌓이며 하루이틀 후 표시됩니다).'],
['約','About','約','약'],
['分鐘一班','min between buses','分間隔','분 간격'],
['（樣本 #）','(samples: {1})','（サンプル数 {1}）','(표본 {1}개)'],
['這個時段樣本還不夠','Not enough samples for this hour yet','この時間帯はサンプルがまだ不足しています','이 시간대는 표본이 아직 부족합니다'],
['# 點','{1}:00','{1}時','{1}시'],
['各時段班距（上班日）','Headway by hour (weekdays)','時間帯別の運行間隔（平日）','시간대별 배차 간격 (평일)'],
['各時段班距（假日）','Headway by hour (weekends/holidays)','時間帯別の運行間隔（休日）','시간대별 배차 간격 (휴일)'],
['以「#」為參考站，取每個時段最近的實際班距中位數。','Based on “{1}” as the reference stop; median of recent real headways for each hour.','「{1}」を基準停留所とし、時間帯ごとの最近の実測運行間隔の中央値を表示しています。','“{1}”을(를) 기준 정류장으로, 시간대별 최근 실제 배차 간격의 중앙값입니다.'],
['🕒 現在','🕒 Now','🕒 現在','🕒 현재'],
['📍 目前沒有公車定位資料','📍 No bus position data right now','📍 バスの位置データがありません','📍 현재 버스 위치 데이터가 없습니다'],
['📍 定位資料 @ 抓取：','📍 Position data fetched at {1}: ','📍 位置データ取得 {1}：','📍 위치 데이터 수집 {1}: '],
['・目前位置為依路線推算','· current positions are estimated along the route','・現在位置は路線上の推定です','· 현재 위치는 노선을 따라 추정한 값입니다'],
['定位時間不明','Position time unknown','位置データの時刻不明','위치 데이터 시각 불명'],
['圖上公車位置每 # 分鐘依路線推進一站（推算，非即時定位）','Bus icons advance one stop every {1} min along the route (estimated, not live GPS)','地図上のバスは{1}分ごとに路線に沿って1停留所ずつ進みます（推定で、リアルタイムGPSではありません）','지도의 버스 아이콘은 {1}분마다 노선을 따라 한 정거장씩 이동합니다 (추정값이며 실시간 GPS가 아닙니다)'],
['🔔 單次提醒','🔔 One-time alert','🔔 1回アラーム','🔔 1회 알림'],
['⏰ 定時提醒','⏰ Scheduled alert','⏰ 定時アラーム','⏰ 정시 알림'],
['單次提醒','One-time alert','1回アラーム','1회 알림'],
['定時提醒','Scheduled alert','定時アラーム','정시 알림'],
['提醒時間','Alert time','アラーム時刻','알림 시각'],
['📆 重複','📆 Repeat','📆 繰り返し','📆 반복'],
['平日（上班日）','Weekdays (working days)','平日（営業日）','평일 (근무일)'],
['假日（週末與國定假日）','Weekends & public holidays','休日（週末・祝日）','휴일 (주말·공휴일)'],
['每天','Every day','毎日','매일'],
['平日','Weekdays','平日','평일'],
['假日','Weekends / holidays','休日','휴일'],
['⏰ 平日','⏰ Weekdays','⏰ 平日','⏰ 평일'],
['⏰ 假日','⏰ Weekends / holidays','⏰ 休日','⏰ 휴일'],
['⏰ 每天','⏰ Every day','⏰ 毎日','⏰ 매일'],
['⏰ 到設定時間會提醒你預估到站時間，之後 # 分鐘內公車快到時再提醒一次。需要網頁保持開啟。','⏰ At the set time you get the estimated arrival time; if the bus is about to arrive within the next {1} minutes you get one more alert. The page must stay open.','⏰ 設定時刻に到着予想時刻をお知らせし、その後{1}分以内にバスが近づいたらもう一度お知らせします。ページを開いたままにしてください。','⏰ 설정한 시각에 도착 예상 시간을 알려 드리고, 이후 {1}분 안에 버스가 가까워지면 한 번 더 알려 드려요. 페이지를 열어 두어야 합니다.'],
['⏰ 加入定時提醒','⏰ Add scheduled alert','⏰ 定時アラームを追加','⏰ 정시 알림 추가'],
['請設定提醒時間','Please set an alert time','アラーム時刻を設定してください','알림 시각을 설정하세요'],
['提醒時間格式不正確','Invalid alert time','アラーム時刻の形式が正しくありません','알림 시각 형식이 올바르지 않습니다'],
['重複日設定不正確','Invalid repeat setting','繰り返しの設定が正しくありません','반복 설정이 올바르지 않습니다'],
['⏰ 已設定定時提醒','⏰ Scheduled alert set','⏰ 定時アラームを設定しました','⏰ 정시 알림이 설정되었습니다'],
['#（往#）','{1} (to {2})','{1}（{2}方面）','{1} ({2} 방면)'],
['準時提醒預估到站時間，之後 # 分鐘內公車剩 # 分鐘時再提醒一次','Alerts you on time with the estimated arrival; then once more if the bus is {2} min away within the next {1} min','時刻になると到着予想をお知らせし、その後{1}分以内にバスが{2}分前になったら、もう一度お知らせします','정시에 도착 예상 시간을 알려 주고, 이후 {1}분 안에 버스가 {2}분 전이 되면 한 번 더 알려 줍니다'],
['⏰ @ 定時提醒','⏰ {1} scheduled alert','⏰ {1} の定時アラーム','⏰ {1} 정시 알림'],
['#（往#）在「#」','{1} (to {2}) at “{3}”','{1}（{2}方面）「{3}」','{1} ({2} 방면) “{3}”'],
['目前沒有這一站的即時資料','No live data for this stop right now','この停留所のリアルタイム情報は現在ありません','이 정류장의 실시간 정보가 현재 없습니다'],
['最近查詢','Recent searches','最近の検索','최근 검색'],
['運算轉乘時間','Calculate trip times','所要時間を計算','소요 시간 계산'],
['❓ 使用教學','❓ Quick tour','❓ 使い方ガイド','❓ 사용 안내'],
['使用教學','Quick tour','使い方ガイド','사용 안내'],
['略過教學','Skip tour','スキップ','건너뛰기'],
['← 上一步','← Back','← 戻る','← 이전'],
['下一步 →','Next →','次へ →','다음 →'],
['開始使用','Get started','使ってみる','시작하기'],
['下次不要再顯示','Don’t show this again','次回から表示しない','다음부터 표시하지 않기'],
['先選擇你習慣的語言：','First, choose your language:','まず言語を選んでください：','먼저 사용할 언어를 선택하세요:'],
['步驟 # / #','Step {1} / {2}','ステップ {1} / {2}','{1} / {2} 단계'],
['歡迎使用台南公車助理','Welcome to Tainan Bus Assistant','台南バスアシスタントへようこそ','타이난 버스 도우미에 오신 것을 환영합니다'],
['這個網站可以查台南公車的即時到站時間、看公車在地圖上的位置、規劃轉乘，還能設定到站提醒。','Check real-time Tainan bus arrivals, see buses on the map, plan transfers, and set arrival alerts.','ここでは台南バスのリアルタイム到着情報、地図上のバス位置、乗り換え検索、到着アラームの設定ができます。','타이난 버스의 실시간 도착 정보를 확인하고, 지도에서 버스 위치를 보고, 환승을 검색하고, 도착 알림을 설정할 수 있어요.'],
['花不到 # 分鐘，帶你認識主要功能！','It takes less than {1} minute to see the main features!','{1}分もかからずに、主な機能をご案内します！','{1}분도 걸리지 않아요. 주요 기능을 안내해 드릴게요!'],
['查路線與到站時間','Find a route and arrival times','路線と到着時刻を調べる','노선과 도착 시간 찾기'],
['在「#」選一條路線（例如 #），再選你的「#」，就能看到每一站的預估到站時間。','Pick a route under “{1}” (e.g. {2}), then choose your “{3}” to see the estimated arrival time at every stop.','「{1}」で路線を選び（例：{2}）、「{3}」を選ぶと、各停留所の到着予想時刻が表示されます。','“{1}”에서 노선을 고르고 (예: {2}) “{3}”을 선택하면 모든 정류장의 도착 예상 시간을 볼 수 있어요.'],
['點一下「#」，會直接幫你查這條路線並展開固定時刻表。','Tap “{1}” to look up that route again and open its fixed timetable right away.','「{1}」をタップすると、その路線をすぐ検索し、固定時刻表も開きます。','“{1}”을 누르면 그 노선을 바로 검색하고 고정 시간표까지 열어 줘요.'],
['看懂資料更新時間','How data freshness works','データの更新タイミングについて','데이터 갱신 시각 이해하기'],
['為了節省 TDX 資料額度，到站資料尖峰時段約每 # 分鐘、平常約每 # 分鐘才更新一次。','To save TDX quota, arrival data refreshes about every {1} min at rush hour and about every {2} min otherwise.','TDXの利用枠を節約するため、到着データはラッシュ時で約{1}分ごと、通常は約{2}分ごとに更新されます。','TDX 사용량을 아끼기 위해 도착 데이터는 혼잡 시간대에 약 {1}분, 평소에는 약 {2}분마다 갱신됩니다.'],
['每筆預估旁邊會標示資料是幾分鐘前抓取的；倒數是依時間推算，下次更新時會自動校正。','Each estimate shows how many minutes ago the data was fetched. The countdown is calculated from elapsed time and is corrected at the next update.','各予想時刻の横に、データを取得してから何分経ったかが表示されます。カウントダウンは経過時間からの推定で、次回の更新で自動的に補正されます。','각 예상 시간 옆에 데이터를 몇 분 전에 가져왔는지 표시됩니다. 카운트다운은 경과 시간으로 계산한 추정값이며 다음 갱신 때 자동으로 보정됩니다.'],
['晚上 @ 到隔天 @ 公車收班，這段時間不更新。','Buses stop running from {1} to {2}, and data is not updated during that time.','{1}から翌{2}まではバスの運行がなく、データも更新されません。','{1}부터 다음 날 {2}까지는 버스 운행이 없으며 데이터도 갱신되지 않습니다.'],
['即時地圖','Live map','リアルタイムマップ','실시간 지도'],
['地圖上可以看到公車位置，上方會顯示現在時間與定位資料的年齡。','The map shows bus positions, with the current time and the age of the position data at the top.','地図上でバスの位置を確認できます。上部には現在時刻と位置データの経過時間が表示されます。','지도에서 버스 위치를 볼 수 있으며, 위쪽에 현재 시각과 위치 데이터의 경과 시간이 표시됩니다.'],
['定位資料約每小時更新一次，中間的移動是依路線推算（每 # 分鐘走一站），不是即時 GPS。','Position data refreshes about once an hour. Movement in between is estimated along the route (one stop every {1} min) and is not live GPS.','位置データは約1時間ごとに更新されます。その間の動きは路線に沿った推定（{1}分ごとに1停留所）で、リアルタイムGPSではありません。','위치 데이터는 약 1시간마다 갱신되며, 그 사이의 이동은 노선을 따라 추정한 값입니다 ({1}분마다 한 정거장). 실시간 GPS가 아닙니다.'],
['到站提醒與定時提醒','Arrival alerts and scheduled alerts','到着アラームと定時アラーム','도착 알림과 정시 알림'],
['「#」：公車快到站前會響鈴。','“{1}”: rings shortly before the bus arrives.','「{1}」：バスが到着する少し前にベルが鳴ります。','“{1}”: 버스가 도착하기 직전에 알림음이 울립니다.'],
['「#」：例如每天 @ 提醒你搭車的預估時間，可選平日、假日或每天。','“{1}”: for example, every day at {2} it tells you the estimated arrival time. Choose weekdays, weekends/holidays, or every day.','「{1}」：たとえば毎日{2}に乗車の到着予想時刻をお知らせします。平日・休日・毎日から選べます。','“{1}”: 예를 들어 매일 {2}에 탑승할 버스의 도착 예상 시간을 알려 줍니다. 평일, 휴일, 매일 중에서 고를 수 있어요.'],
['提醒需要網頁保持開啟，並請允許通知權限。','Alerts need this page to stay open, and please allow notification permission.','アラームを使うにはページを開いたままにし、通知を許可してください。','알림을 받으려면 페이지를 열어 두고 알림 권한을 허용해 주세요.'],
['站到站、轉乘與分享','Stop to stop, transfers and sharing','停留所間検索・乗り換え・共有','정류장 간 검색, 환승, 공유'],
['在「#」輸入起點與終點，找直達或轉乘一次的路線，再按「#」看每一段要多久。','Under “{1}”, enter a start and a destination to find direct or one-transfer routes, then tap “{2}” to see how long each leg takes.','「{1}」で出発地と目的地を入力すると直通または1回乗り換えの路線が見つかり、「{2}」を押すと各区間の所要時間がわかります。','“{1}”에서 출발지와 도착지를 입력하면 직행 또는 1회 환승 노선을 찾고, “{2}”를 누르면 구간별 소요 시간을 볼 수 있어요.'],
['每個站牌旁的 🔗 可以產生連結與 QR code，分享給朋友。','The 🔗 next to each stop creates a link and QR code to share with friends.','各停留所の横の 🔗 で、友達に共有できるリンクとQRコードを作れます。','각 정류장 옆의 🔗 로 친구에게 공유할 링크와 QR 코드를 만들 수 있어요.'],
['準備好了！','You’re all set!','準備完了！','준비 완료!'],
['之後想再看一次，可以點側邊欄的「#」。','To see this again later, tap “{1}” in the sidebar.','もう一度見たいときは、サイドバーの「{1}」をタップしてください。','나중에 다시 보고 싶다면 사이드바의 “{1}”을 누르세요.'],
['祝你搭車順利！','Have a great ride!','良い旅を！','즐거운 탑승 되세요!'],
['（往#）','(to {1})','（{1}方面）','({1} 방면)'],
];

// ══════════════════════════════════════════════════════════
// 多語系引擎（中文／English／日本語）
// 做法：程式照舊產生中文畫面，引擎在「畫面文字節點」上做即時翻譯。
//  - 原文都存在節點上（__orig），隨時可切回中文或換另一種語言。
//  - 邏輯用的字串（'去程'、路線名稱、API 參數）完全不動，只改顯示。
//  - 數字／時間／路線代號／「」內的名稱會先抽成 #，再比對上面的字典。
//  - 站名、路線名稱：英文版會用 TDX 本來就附的英文名稱（/api/name_map）。
// ══════════════════════════════════════════════════════════
const LANGS = {
  zh: { label: '中文',    locale: 'zh-TW', speech: 'zh-TW', html: 'zh-Hant' },
  en: { label: 'English', locale: 'en-GB', speech: 'en-US', html: 'en' },
  ja: { label: '日本語',   locale: 'ja-JP', speech: 'ja-JP', html: 'ja' },
  ko: { label: '한국어',   locale: 'ko-KR', speech: 'ko-KR', html: 'ko' },
};
const IDX = { en: 1, ja: 2, ko: 3 };
const CJK = /[\u3400-\u9fff]/;
const DICT = new Map(ROWS.map(r => [r[0], r]));
let lang = 'zh';
let nameMap = { all: {} };

const ROUTE_TOKEN = '(?:黃|棕|綠|橘|藍|紅)(?:\\d+(?:-\\d+)*|幹線|線)';
const CAP_RE = new RegExp(
  '(\\d{1,2}:\\d{2}(?::\\d{2})?)|「([^」]*)」|【([^】]*)】|（往([^）]*)）|(' + ROUTE_TOKEN + ')|(\\d+(?:\\.\\d+)?)', 'g');

function norm(s) {
  const caps = [];
  const key = s.replace(CAP_RE, (m, time, q1, q2, dest, route, num) => {
    if (time !== undefined) { caps.push({ t: 'v', v: time }); return '@'; }
    if (q1 !== undefined)   { caps.push({ t: 'n', v: q1 });   return '「#」'; }
    if (q2 !== undefined)   { caps.push({ t: 'n', v: q2 });   return '【#】'; }
    if (dest !== undefined) { caps.push({ t: 'n', v: dest }); return '（往#）'; }
    if (route !== undefined){ caps.push({ t: 'n', v: route });return '#'; }
    caps.push({ t: 'v', v: num }); return '#';
  });
  return { key, caps };
}

const COLOR = {
  en: { 黃: 'Yellow', 棕: 'Brown', 綠: 'Green', 橘: 'Orange', 藍: 'Blue', 紅: 'Red' },
  ko: { 黃: '노랑', 棕: '갈색', 綠: '초록', 橘: '주황', 藍: '파랑', 紅: '빨강' },
};
const ROUTE_SUFFIX = { en: { 幹線: ' Trunk', 線: ' Line' }, ko: { 幹線: ' 간선', 線: ' 노선' } };
function routeToken(v) {
  const m = v.match(/^(黃|棕|綠|橘|藍|紅)(.*)$/);
  if (!m || !COLOR[lang]) return v;
  let rest = m[2];
  if (ROUTE_SUFFIX[lang][rest] !== undefined) rest = ROUTE_SUFFIX[lang][rest]; else if (rest) rest = ' ' + rest;
  return COLOR[lang][m[1]] + rest;
}

function trName(v, depth) {
  if (lang === 'zh' || !v) return v;
  if (lang === 'en' || lang === 'ko') {
    if (nameMap.all[v]) return nameMap.all[v];
    if (new RegExp('^' + ROUTE_TOKEN + '$').test(v)) return routeToken(v);
  }
  if (CJK.test(v)) return trCore(v, (depth || 0) + 1);
  return v;
}

function fill(tpl, caps, depth) {
  if (tpl.indexOf('{') >= 0) {
    return tpl.replace(/\{(\d+)\}/g, (m, n) => {
      const c = caps[+n - 1];
      return c ? (c.t === 'n' ? trName(c.v, depth) : c.v) : '';
    });
  }
  let i = 0;
  return tpl.replace(/#/g, () => { const c = caps[i++]; return c ? (c.t === 'n' ? trName(c.v, depth) : c.v) : ''; });
}

const WEEK_EN = { 一: 'Mon', 二: 'Tue', 三: 'Wed', 四: 'Thu', 五: 'Fri', 六: 'Sat', 日: 'Sun' };
const WEEK_JA = { 一: '月', 二: '火', 三: '水', 四: '木', 五: '金', 六: '土', 日: '日' };
const WEEK_KO = { 一: '월', 二: '화', 三: '수', 四: '목', 五: '금', 六: '토', 日: '일' };
const WEEK_ORDER = '一二三四五六日';
const RULES = [
  { re: /^([一二三四五六日](?:、[一二三四五六日])+)$/, fn: m => {
    const ds = m[1].split('、');
    const consecutive = ds.length >= 3 && ds.every((d, i) => i === 0 || WEEK_ORDER.indexOf(d) === WEEK_ORDER.indexOf(ds[i - 1]) + 1);
    const W = lang === 'en' ? WEEK_EN : (lang === 'ko' ? WEEK_KO : WEEK_JA);
    if (consecutive) return W[ds[0]] + (lang === 'en' ? '–' : '〜') + W[ds[ds.length - 1]];
    return ds.map(d => W[d]).join(lang === 'ja' ? '・' : ', ');
  } },
  // UBike 建議（後端組好的三行文字；站名不在「」裡，所以用規則處理）
  { re: /^🚲 UBike 更快！實際騎車約 ([\d.]+) 分鐘（(.+)），比等公車\+搭車（約 ([\d.]+) 分鐘）更省時。$/, fn: m => {
    const d = trName(m[2], 1);
    if (lang === 'en') return `🚲 UBike is faster! Cycling takes about ${m[1]} min (${d}), vs. about ${m[3]} min waiting for and riding the bus.`;
    if (lang === 'ko') return `🚲 UBike가 더 빨라요! 자전거로 약 ${m[1]}분 (${d}), 버스 대기+탑승은 약 ${m[3]}분입니다.`;
    return `🚲 UBikeの方が速い！自転車で約${m[1]}分（${d}）、バスの待ち＋乗車は約${m[3]}分です。`;
  } },
  { re: /^- 起點 UBike：(.+)（可借 (\d+) 輛）$/, fn: m => lang === 'en'
      ? `- Start UBike: ${trName(m[1], 1)} (${m[2]} bikes available)` : (lang === 'ko'
      ? `- 출발지 UBike: ${trName(m[1], 1)} (대여 가능 ${m[2]}대)` : `- 出発地のUBike：${trName(m[1], 1)}（貸出可 ${m[2]}台）`) },
  { re: /^- 終點 UBike：(.+)（可還 (\d+) 格）$/, fn: m => lang === 'en'
      ? `- End UBike: ${trName(m[1], 1)} (${m[2]} docks free)` : (lang === 'ko'
      ? `- 도착지 UBike: ${trName(m[1], 1)} (반납 가능 ${m[2]}칸)` : `- 目的地のUBike：${trName(m[1], 1)}（返却可 ${m[2]}枠）`) },
  { re: /^(➡️ 去程|⬅️ 回程)　往 (.+)$/, fn: m => {
    const out = m[1].startsWith('➡️');
    const d = lang === 'en' ? (out ? '➡️ Outbound' : '⬅️ Return')
      : (lang === 'ko' ? (out ? '➡️ 가는 방향' : '⬅️ 오는 방향') : (out ? '➡️ 往路' : '⬅️ 復路'));
    return d + ' → ' + trName(m[2].trim(), 1);
  } },
];
const PREFIX = [
  ['➡️ 往 ', '➡️ To ', '➡️ 行先：', '➡️ 방면: '], ['⬅️ 往 ', '⬅️ To ', '⬅️ 行先：', '⬅️ 방면: '],
  ['🔀 往 ', '🔀 to ', '🔀 行先：', '🔀 방면: '], ['前往 ', 'To ', '行先：', '방면: '],
];
const SEP_RE = /(\n|[，、；：｜]|。(?=\s*\S)|・)/;
const SEP_OUT = {
  en: { '，': ', ', '、': ', ', '；': '; ', '：': ': ', '｜': ' | ', '。': '. ', '・': ' · ', '\n': '\n' },
  ko: { '，': ', ', '、': ', ', '；': '; ', '：': ': ', '｜': ' | ', '。': '. ', '・': ' · ', '\n': '\n' },
  ja: { '，': '、', '、': '、', '；': '；', '：': '：', '｜': ' | ', '。': '。', '・': '・', '\n': '\n' },
};
function cell_of(row) { return row[IDX[lang]] !== undefined ? row[IDX[lang]] : (lang === 'ko' ? row[1] : undefined); }
let glossaryCache = null;
function glossary() {
  if (glossaryCache) return glossaryCache;
  glossaryCache = ROWS.filter(r => r[0].length >= 2 && CJK.test(r[0]) && !/[#@{]/.test(r[0]) && r[1] !== '')
    .sort((a, b) => b[0].length - a[0].length);
  return glossaryCache;
}

function trCore(core, depth) {
  depth = depth || 0;
  const idx = IDX[lang];
  if (!idx) return core;
  if (lang === 'en' || lang === 'ko') {
    if (nameMap.all[core]) return nameMap.all[core];
    if (new RegExp('^' + ROUTE_TOKEN + '$').test(core)) return routeToken(core);
  }
  const n = norm(core);
  const row = DICT.get(n.key);
  const cell = row ? cell_of(row) : undefined;
  if (cell !== undefined) return fill(cell, n.caps, depth);
  if (core.indexOf('\n') >= 0) {            // 多行文字：一行一行翻
    return core.split('\n').map(l => (l.trim() && CJK.test(l)) ? trCore(l.trim(), depth + 1) : l).join('\n');
  }
  for (const r of RULES) { const m = core.match(r.re); if (m) return r.fn(m); }
  if (depth > 3) return core;
  for (const p of PREFIX) {
    if (core.startsWith(p[0])) return p[idx] + trName(core.slice(p[0].length).trim(), depth + 1);
  }
  const parts = core.split(SEP_RE);
  if (parts.length > 1) {
    let changed = false;
    const out = parts.map((p, i) => {
      if (i % 2 === 1) return SEP_OUT[lang][p] !== undefined ? SEP_OUT[lang][p] : p;
      if (!p.trim() || !CJK.test(p)) return p;
      const lead = p.match(/^\s*/)[0], trail = p.match(/\s*$/)[0];
      const t = trCore(p.trim(), depth + 1);
      if (t !== p.trim()) changed = true;
      return lead + t + trail;
    }).join('');
    if (changed) return out;
  }
  let out = core, hit = false;
  for (const r of glossary()) {
    if (out.indexOf(r[0]) >= 0) { out = out.split(r[0]).join(cell_of(r)); hit = true; }
  }
  return hit ? out : core;
}

function tr(text) {
  if (lang === 'zh' || typeof text !== 'string' || !CJK.test(text)) return text;
  const lead = text.match(/^\s*/)[0], trail = text.match(/\s*$/)[0];
  const core = text.trim();
  if (!core) return text;
  return lead + trCore(core, 0) + trail;
}

if (typeof document === 'undefined') { module.exports = { tr, setLang: l => { lang = l; }, setNames: n => { nameMap.all = n; }, ROWS, norm, DICT }; return; }

// ── 畫面：把文字節點／屬性即時翻譯，並可隨時還原 ──────────────────────
const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'NOSCRIPT', 'CODE']);

function skipNode(node) {
  const el = node.nodeType === 1 ? node : node.parentElement;
  if (!el) return true;
  if (SKIP_TAGS.has(el.tagName)) return true;
  if (el.closest('[data-no-i18n]')) return true;
  // AI 對話內容（使用者問題／AI 回覆）是別人說的話，不翻；只翻「思考中...」這類系統提示
  const msg = el.closest('.chat-msg');
  if (msg && msg.id !== 'chat-thinking') return true;
  return false;
}

function fixText(node) {
  if (skipNode(node)) return;
  let orig = node.__orig;
  if (orig === undefined || node.data !== node.__out) { orig = node.data; node.__orig = orig; node.__out = undefined; }
  if (!CJK.test(orig)) { node.__orig = undefined; return; }
  const out = tr(orig);
  node.__out = out;
  if (node.data !== out) node.data = out;
}

function fixAttrs(el) {
  if (skipNode(el)) return;
  for (const a of ATTRS) {
    if (!el.hasAttribute || !el.hasAttribute(a)) continue;
    const store = el.__attr || (el.__attr = {});
    const cur = el.getAttribute(a);
    const rec = store[a];
    let orig;
    if (rec && rec.out === cur) orig = rec.orig; else orig = cur;
    if (!CJK.test(orig)) { delete store[a]; continue; }
    const out = tr(orig);
    store[a] = { orig, out };
    if (cur !== out) el.setAttribute(a, out);
  }
}

function scan(root) {
  if (!root) return;
  if (root.nodeType === 3) { fixText(root); return; }
  if (root.nodeType !== 1 && root.nodeType !== 9) return;
  const start = root.nodeType === 9 ? root.body : root;
  if (start.nodeType === 1) fixAttrs(start);
  const walker = document.createTreeWalker(start, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n;
  while ((n = walker.nextNode())) {
    if (n.nodeType === 3) fixText(n); else fixAttrs(n);
  }
}

let observer = null;
function startObserver() {
  if (observer) return;
  observer = new MutationObserver(muts => {
    if (lang === 'zh') return;
    for (const m of muts) {
      if (m.type === 'childList') m.addedNodes.forEach(scan);
      else if (m.type === 'characterData') fixText(m.target);
      else if (m.type === 'attributes') fixAttrs(m.target);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ATTRS });
}

function restoreAll() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let n;
  while ((n = walker.nextNode())) {
    if (n.nodeType === 3) {
      if (n.__orig !== undefined && n.data === n.__out) { n.data = n.__orig; }
      n.__orig = undefined; n.__out = undefined;
    } else if (n.__attr) {
      for (const a of Object.keys(n.__attr)) {
        const rec = n.__attr[a];
        if (n.getAttribute(a) === rec.out) n.setAttribute(a, rec.orig);
      }
      n.__attr = undefined;
    }
  }
}

let nameMapPromise = null;
function loadNameMap() {
  if (nameMapPromise) return nameMapPromise;
  nameMapPromise = fetch('/api/name_map')
    .then(r => r.json())
    .then(d => { nameMap.all = Object.assign({}, d.routes || {}, d.stops || {}); })
    .catch(() => { nameMapPromise = null; });
  return nameMapPromise;
}

function applyLang() {
  const L = LANGS[lang];
  document.documentElement.lang = L.html;
  document.querySelectorAll('.lang-switch [data-lang]').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  if (lang === 'zh') {
    restoreAll();
    if (document.title.__orig) document.title = document.title.__orig;
  } else {
    scan(document.body);
  }
  const t = document.querySelector('title');
  if (t) {
    if (t.__orig === undefined) t.__orig = t.textContent;
    t.textContent = lang === 'zh' ? t.__orig : tr(t.__orig);
  }
  document.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang } }));
}

async function setLang(next) {
  if (!LANGS[next]) next = 'zh';
  lang = next;
  try { localStorage.setItem('lang', next); } catch (e) { /* noop */ }
  if (lang === 'en' || lang === 'ko') await loadNameMap();   // 英文站名：TDX 本來就附的 En 欄位（韓文版也用英文站名）
  applyLang();
}

function detectLang() {
  try { const s = localStorage.getItem('lang'); if (LANGS[s]) return s; } catch (e) { /* noop */ }
  const nav = (navigator.language || 'zh-TW').toLowerCase();
  if (nav.startsWith('ja')) return 'ja';
  if (nav.startsWith('ko')) return 'ko';
  if (nav.startsWith('en')) return 'en';
  return 'zh';
}

window.I18N = {
  lang: () => lang,
  set: setLang,
  t: tr,                                   // 翻譯任意一段中文字串（給朗讀、通知這類不在畫面上的文字用）
  locale: () => LANGS[lang].locale,
  speech: () => LANGS[lang].speech,
  langs: LANGS,
};

function initI18n() {
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.lang-switch [data-lang]');
    if (b) setLang(b.dataset.lang);
  });
  startObserver();
  setLang(detectLang());
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initI18n);
else initI18n();

})();
