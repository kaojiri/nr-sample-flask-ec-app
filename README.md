# Flask EC Application

EKS と RDS を使用した本格的な EC（電子商取引）アプリケーション

## 機能

- ユーザー認証（登録・ログイン）
- 商品一覧・詳細表示
- ショッピングカート
- 注文機能
- レスポンシブデザイン

## 技術スタック

### アプリケーション
- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL (AWS RDS)
- **ORM**: SQLAlchemy
- **認証**: Flask-Login
- **WSGI Server**: Gunicorn
- **監視**: New Relic APM

### インフラ
- **Container**: Docker
- **Orchestration**: Kubernetes (Amazon EKS)
- **Database**: Amazon RDS (PostgreSQL)
- **Container Registry**: Amazon ECR
- **IaC**: Terraform

## プロジェクト構造

```
flask-ec-app/
├── app/                    # アプリケーションコード
│   ├── models/            # データモデル
│   ├── routes/            # ルート定義
│   ├── templates/         # HTMLテンプレート
│   └── static/            # 静的ファイル
├── k8s/                   # Kubernetes マニフェスト
├── terraform/             # Terraform 設定
├── scripts/               # デプロイメントスクリプト
├── Dockerfile             # Docker イメージ定義
├── requirements.txt       # Python 依存関係
└── run.py                 # アプリケーションエントリーポイント
```

## セットアップ

### ローカル環境での起動（推奨：まずはこちら）

#### 方法1: Docker Compose を使う（最も簡単）

```bash
cd flask-ec-app

# ワンコマンドでセットアップ＆起動
./scripts/local-setup.sh
```

これで http://localhost:5001 でアプリケーションが起動します。

> **Note**: ポート5000が使用中のため5001番ポートを使用します。変更したい場合は `docker-compose.yml` の `ports` セクションを編集してください。

**テストユーザー**:
- Email: test@example.com
- Password: password123

**便利なコマンド**:
```bash
# ログを見る
docker-compose logs -f

# 停止
docker-compose down

# 再起動
docker-compose restart

# 完全削除（データベース含む全て）
./scripts/local-cleanup.sh
```

#### 方法2: Python 仮想環境を使う

```bash
cd flask-ec-app

# PostgreSQL だけ Docker で起動
docker-compose up -d postgres

# Python 環境セットアップ
./scripts/local-python-setup.sh

# アプリケーション起動
source venv/bin/activate
python run.py
```

### AWS 環境へのデプロイ

#### 前提条件

- AWS CLI 設定済み
- Docker インストール済み
- kubectl インストール済み
- Terraform インストール済み

#### 1. インフラのデプロイ

```bash
cd terraform

# terraform.tfvars ファイルを作成
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集してパスワードなどを設定

# Terraform 初期化
terraform init

# インフラのデプロイ
terraform apply
```

#### 2. EKS へのデプロイ

```bash
# デプロイスクリプトに実行権限を付与
chmod +x scripts/deploy.sh

# デプロイ実行
./scripts/deploy.sh
```

## Kubernetes マニフェスト

- `namespace.yaml`: Namespace 定義
- `secret.yaml`: シークレット（DB接続情報など）
- `deployment.yaml`: アプリケーションのデプロイメント
- `service.yaml`: Service 定義
- `ingress.yaml`: Ingress (ALB) 定義
- `hpa.yaml`: Horizontal Pod Autoscaler
- `migration-job.yaml`: DB マイグレーションジョブ

## デプロイ後の確認

```bash
# Pod の状態確認
kubectl get pods -n flask-ec-app

# Service の確認
kubectl get svc -n flask-ec-app

# ログの確認
kubectl logs -f deployment/flask-ec-app -n flask-ec-app
```

## テストユーザー

サンプルデータを投入した場合、以下のユーザーでログインできます：

- Email: test@example.com
- Password: password123

## 環境変数

- `SECRET_KEY`: Flask のシークレットキー
- `DATABASE_URL`: PostgreSQL 接続URL
- `FLASK_ENV`: 実行環境 (development/production)
- `NEW_RELIC_LICENSE_KEY`: New Relic ライセンスキー
- `NEW_RELIC_APP_NAME`: New Relic アプリケーション名
- `NEW_RELIC_ENVIRONMENT`: New Relic 環境名

## New Relic 監視

このアプリケーションは New Relic APM による監視が設定されています。

- **自動収集される情報**: リクエスト/レスポンスタイム、エラー率、データベースクエリ、分散トレーシング
- **ダッシュボード**: https://one.newrelic.com/
- **ライセンスキー**: 環境変数 `NEW_RELIC_LICENSE_KEY` で設定

詳細は [NEW_RELIC_SETUP.md](NEW_RELIC_SETUP.md) を参照してください。

## セキュリティ考慮事項

1. **本番環境では必ず変更すべき項目**:
   - `SECRET_KEY`
   - データベースパスワード
   - RDS のセキュリティグループ設定

2. **推奨設定**:
   - HTTPS の有効化（ACM証明書の使用）
   - RDS の暗号化（デフォルトで有効）
   - ECR のイメージスキャン（デフォルトで有効）

## スケーリング

- HPA により CPU/メモリ使用率に応じて自動スケール（3〜10 Pod）
- RDS は必要に応じて手動でスケールアップ可能

## クリーンアップ

### ローカル環境の完全削除

```bash
# ローカル環境を完全削除（コンテナ、ボリューム、venv、キャッシュ等）
./scripts/local-cleanup.sh
```

削除されるもの:
- Docker コンテナとイメージ
- Docker ボリューム（データベースデータ）
- Python 仮想環境 (venv/)
- データベースファイル
- マイグレーションファイル
- 環境変数ファイル (.env)
- Python キャッシュ

### AWS 環境の削除

```bash
# Kubernetes リソースの削除
kubectl delete namespace flask-ec-app

# Terraform リソースの削除
cd terraform
terraform destroy
```

## トラブルシューティング

### Pod が起動しない場合

```bash
kubectl describe pod <pod-name> -n flask-ec-app
kubectl logs <pod-name> -n flask-ec-app
```

### データベース接続エラー

- RDS のエンドポイントが正しく設定されているか確認
- セキュリティグループで EKS からの接続が許可されているか確認

## ライセンス

MIT License
