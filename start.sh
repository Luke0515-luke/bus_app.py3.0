#!/bin/bash
# 1. 先執行備份或下載資料
python3 pull_backup.py

# 2. 切換到程式碼所在的資料夾
cd /opt/render/project/src

# 3. 啟動 Gunicorn 來跑你的 Flask 主程式
gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"
