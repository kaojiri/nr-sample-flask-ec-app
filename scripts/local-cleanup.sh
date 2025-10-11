#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Flask EC App ローカル環境完全削除 ===${NC}"
echo ""
echo -e "${RED}以下のものが削除されます:${NC}"
echo "  - Docker コンテナとイメージ"
echo "  - Docker ボリューム（データベースデータ）"
echo "  - Python 仮想環境 (venv/)"
echo "  - データベースファイル (*.db, *.sqlite3)"
echo "  - マイグレーションファイル"
echo "  - 環境変数ファイル (.env)"
echo "  - Python キャッシュ (__pycache__/)"
echo ""

read -p "本当に削除しますか？ (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "キャンセルしました"
    exit 1
fi

# Docker Compose のコンテナとボリュームを停止・削除
echo -e "${YELLOW}Docker コンテナとボリュームを削除中...${NC}"
if [ -f "docker-compose.yml" ]; then
    docker-compose down -v --remove-orphans 2>/dev/null || true
fi

# Docker イメージの削除
echo -e "${YELLOW}Docker イメージを削除中...${NC}"
docker rmi flask-ec-app:latest 2>/dev/null || true
docker rmi flask-ec-app-web:latest 2>/dev/null || true
docker rmi $(docker images -q flask-ec-app_web) 2>/dev/null || true

# Python 仮想環境の削除
if [ -d "venv" ]; then
    echo -e "${YELLOW}Python 仮想環境を削除中...${NC}"
    rm -rf venv
fi

# データベースファイルの削除
echo -e "${YELLOW}データベースファイルを削除中...${NC}"
rm -f *.db *.sqlite3

# マイグレーションファイルの削除
if [ -d "migrations" ]; then
    echo -e "${YELLOW}マイグレーションファイルを削除中...${NC}"
    rm -rf migrations
fi

# 環境変数ファイルの削除
if [ -f ".env" ]; then
    echo -e "${YELLOW}環境変数ファイルを削除中...${NC}"
    rm -f .env
fi

# Python キャッシュの削除
echo -e "${YELLOW}Python キャッシュを削除中...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Flask キャッシュの削除
rm -rf .pytest_cache .coverage htmlcov 2>/dev/null || true

# ログファイルの削除
rm -f *.log 2>/dev/null || true

echo ""
echo -e "${GREEN}=== 完全削除完了 ===${NC}"
echo ""
echo -e "${GREEN}再度セットアップするには:${NC}"
echo -e "  ./scripts/local-setup.sh"
