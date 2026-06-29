#!/bin/bash
# Selenium standalone-chromeのエントリポイントをバックグラウンドで起動
/opt/bin/entry_point.sh &

# Chromeが起動するまで待機
echo "Waiting for Chrome to be ready..."
for i in $(seq 1 30); do
    if curl -s http://localhost:4444/wd/hub/status | grep -q '"ready":true'; then
        echo "Chrome is ready!"
        break
    fi
    sleep 1
done

# Python テストランナーAPI起動
echo "Starting Browser Test Runner API on port 8081..."
cd /app
export FLASK_APP=api
python3 -m flask run --host=0.0.0.0 --port=8081
