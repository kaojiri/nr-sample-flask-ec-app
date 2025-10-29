#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root directory (parent of scripts directory)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root directory to ensure relative paths work correctly
cd "$PROJECT_ROOT"

echo -e "${GREEN}=== Flask EC App 再ビルド＆起動 ===${NC}"

# 既存のコンテナを停止・削除
echo -e "${YELLOW}既存のコンテナを停止中...${NC}"
docker-compose down

# イメージを再ビルド（キャッシュなし）
echo -e "${YELLOW}Docker イメージを再ビルド中...${NC}"
docker-compose build --no-cache

# 起動
echo -e "${YELLOW}コンテナを起動中...${NC}"
docker-compose up -d

# PostgreSQL が起動するまで待機
echo -e "${YELLOW}PostgreSQL の起動を待機中...${NC}"
sleep 10

# ログを確認
echo -e "${YELLOW}起動ログを確認中...${NC}"
docker-compose logs web | tail -20

echo ""
echo -e "${GREEN}=== 起動完了 ===${NC}"
echo -e "${GREEN}アプリケーション: http://localhost:5001${NC}"
echo ""
echo -e "${YELLOW}New Relic の接続を確認:${NC}"
echo ""

# Send deployment marker to New Relic Change Tracking
if [ -f scripts/send-change-tracking.sh ]; then
    echo -e "${YELLOW}📈 New Relic Change Tracking にデプロイメントを記録中...${NC}"
    scripts/send-change-tracking.sh
    echo ""
fi
docker-compose logs web | grep -i "new relic" || echo -e "${RED}New Relic のログが見つかりません${NC}"
echo ""
echo -e "${YELLOW}リアルタイムログを見る:${NC}"
echo -e "  docker-compose logs -f web"
echo ""
echo -e "${YELLOW}データベースを初期化する場合:${NC}"
echo -e "  docker-compose exec web flask db upgrade"
echo -e "  docker-compose exec web python scripts/init-db.py"
echo -e "  docker-compose exec web python scripts/create_admin.py"
echo -e "  docker-compose exec web python scripts/create_admin.py"
