#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Flask EC App ローカルセットアップ ===${NC}"

# Docker Compose で起動
echo -e "${YELLOW}Docker Compose でサービスを起動中...${NC}"
docker-compose up -d

# PostgreSQL が起動するまで待機
echo -e "${YELLOW}PostgreSQL の起動を待機中...${NC}"
sleep 5

# データベースマイグレーション
echo -e "${YELLOW}データベースマイグレーション実行中...${NC}"
docker-compose exec web flask db init || true
docker-compose exec web flask db migrate -m "Initial migration" || true
docker-compose exec web flask db upgrade

# サンプルデータ投入
echo -e "${YELLOW}サンプルデータ投入中...${NC}"
docker-compose exec web python scripts/init-db.py

# 管理者ユーザー作成
echo -e "${YELLOW}管理者ユーザー作成中...${NC}"
docker-compose exec web python scripts/create_admin.py

echo -e "${GREEN}=== セットアップ完了 ===${NC}"
echo -e "${GREEN}アプリケーションは http://localhost:5001 で起動しています${NC}"
echo -e "${YELLOW}管理者ユーザー:${NC}"
echo -e "  Email: admin@example.com"
echo -e "  Username: admin"
echo -e "  Password: admin123"
echo ""
echo -e "${YELLOW}テストユーザー:${NC}"
echo -e "  Email: test@example.com"
echo -e "  Password: password123"
echo ""
echo -e "${YELLOW}管理者ユーザー:${NC}"
echo -e "  Email: admin@example.com"
echo -e "  Username: admin"
echo -e "  Password: admin123"
echo ""
echo -e "${YELLOW}ログを見る: docker-compose logs -f${NC}"
echo -e "${YELLOW}停止する: docker-compose down${NC}"
