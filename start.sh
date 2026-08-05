#!/bin/bash
# 1. 先執行備份或下載資料
python3 pull_backup.py &
python3 app.py
