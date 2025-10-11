#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Flask EC App Python ローカルセットアップ ===${NC}"

# 仮想環境の作成
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}仮想環境を作成中...${NC}"
    python3 -m venv venv
fi

# 仮想環境の有効化
echo -e "${YELLOW}仮想環境を有効化中...${NC}"
source venv/bin/activate

# 依存関係のインストール
echo -e "${YELLOW}依存関係をインストール中...${NC}"
pip install -r requirements.txt

# .env ファイルの作成
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}.env ファイルを作成中...${NC}"
    cat > .env << EOF
SECRET_KEY=dev-secret-key-for-local
FLASK_ENV=development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecdb
EOF
fi

# PostgreSQL がローカルで起動しているか確認
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${YELLOW}PostgreSQL が起動していません。Docker Compose で起動します...${NC}"
    docker-compose up -d postgres
    sleep 5
fi

# データベースマイグレーション
echo -e "${YELLOW}データベースマイグレーション実行中...${NC}"
flask db init || true
flask db migrate -m "Initial migration" || true
flask db upgrade

# サンプルデータ投入
echo -e "${YELLOW}サンプルデータ投入中...${NC}"
python scripts/init-db.py

echo -e "${GREEN}=== セットアップ完了 ===${NC}"
echo -e "${GREEN}アプリケーションを起動するには:${NC}"
echo -e "  python run.py"
echo ""
echo -e "${YELLOW}テストユーザー:${NC}"
echo -e "  Email: test@example.com"
echo -e "  Password: password123"
