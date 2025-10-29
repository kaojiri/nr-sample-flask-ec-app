-- PostgreSQL初期化スクリプト
-- pg_stat_statements拡張を有効にする

-- pg_stat_statements拡張をインストール
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 拡張が正常にインストールされたことを確認
SELECT 
    extname as "Extension Name",
    extversion as "Version"
FROM pg_extension 
WHERE extname = 'pg_stat_statements';

-- pg_stat_statements設定の確認
SHOW shared_preload_libraries;
SHOW pg_stat_statements.max;
SHOW pg_stat_statements.track;

-- 初期化完了メッセージ
SELECT 'pg_stat_statements extension enabled successfully' as status;