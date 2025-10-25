# Design Document

## Overview

ユーザーログイン後にユーザーIDとユーザー名を表示する機能を実装します。既存のFlask-Loginシステムを活用し、`current_user`オブジェクトから情報を取得してナビゲーションバーに表示します。

## Architecture

### 現在のシステム構成
- Flask-Loginによる認証システム
- Userモデル（id, username, email属性を持つ）
- Jinjaテンプレートエンジン
- Bootstrap 5によるUI

### 実装アプローチ
- テンプレート層での表示実装（サーバーサイドレンダリング）
- 既存のナビゲーションバーを拡張
- セッション状態に基づく動的表示

## Components and Interfaces

### 1. Template Layer
**ファイル**: `app/templates/base.html`
- **役割**: ユーザー情報表示UIの実装
- **入力**: `current_user`オブジェクト（Flask-Loginから提供）
- **出力**: ユーザーID、ユーザー名を含むHTML

### 2. User Model
**ファイル**: `app/models/user.py`
- **現在の状態**: 既に適切に実装済み
- **提供データ**: `current_user.id`, `current_user.username`

### 3. Authentication Routes
**ファイル**: `app/routes/auth.py`
- **現在の状態**: 既に適切に実装済み
- **機能**: ログイン/ログアウト処理

## Data Models

### User Information Display
```python
# 既存のUserモデルから取得可能なデータ
current_user.id          # ユーザーID (整数)
current_user.username    # ユーザー名 (文字列)
current_user.is_authenticated  # 認証状態 (ブール値)
```

### Template Context
```html
<!-- Jinjaテンプレートで利用可能 -->
{{ current_user.id }}
{{ current_user.username }}
{{ current_user.is_authenticated }}
```

## Error Handling

### 1. 未認証状態
- **状況**: `current_user.is_authenticated`がFalse
- **対応**: ユーザー情報を表示しない
- **実装**: 既存の条件分岐を活用

### 2. セッション無効化
- **状況**: ログアウト時やセッション期限切れ
- **対応**: Flask-Loginが自動的に`current_user`を更新
- **実装**: 追加実装不要（既存機能で対応）

### 3. ユーザーデータ不整合
- **状況**: ユーザーIDやユーザー名がNone
- **対応**: テンプレートでの安全な表示（デフォルト値使用）
- **実装**: Jinjaテンプレートのフィルターを使用

## Testing Strategy

### 1. 表示テスト
- ログイン後のページでユーザー情報が表示されることを確認
- ログアウト後にユーザー情報が非表示になることを確認

### 2. セッション状態テスト
- 複数ページ間でのユーザー情報表示の一貫性を確認
- セッション期限切れ時の動作確認

### 3. UI/UXテスト
- 表示位置とスタイリングの適切性を確認
- レスポンシブデザインでの表示確認

## Implementation Details

### ナビゲーションバー拡張
現在のナビゲーションバー構造：
```html
<ul class="navbar-nav ms-auto">
    <!-- 商品一覧リンク -->
    {% if current_user.is_authenticated %}
        <!-- カート、ログアウトリンク -->
    {% else %}
        <!-- ログイン、会員登録リンク -->
    {% endif %}
</ul>
```

拡張後の構造：
```html
<ul class="navbar-nav ms-auto">
    <!-- 商品一覧リンク -->
    {% if current_user.is_authenticated %}
        <!-- ユーザー情報表示 -->
        <!-- カート、ログアウトリンク -->
    {% else %}
        <!-- ログイン、会員登録リンク -->
    {% endif %}
</ul>
```

### スタイリング方針
- Bootstrap 5のnavbar-textクラスを使用
- 既存のデザインとの一貫性を保持
- モバイル表示での適切な配置

### セキュリティ考慮事項
- XSS対策：Jinjaテンプレートの自動エスケープを活用
- ユーザーIDの表示：管理上必要な場合のみ表示
- セッション管理：Flask-Loginの既存機能を信頼