-- PostgreSQL初期化スクリプト
-- New Relic監視用拡張を有効にする

-- pg_stat_statements拡張をインストール（Query Performance Monitoring用）
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- pg_wait_sampling拡張をインストール（Wait Time Analysis用）
CREATE EXTENSION IF NOT EXISTS pg_wait_sampling;

-- pg_stat_monitorは使用しない（pg_stat_statementsで十分）

-- インストールされた拡張の確認
SELECT 
    extname as "Extension Name",
    extversion as "Version",
    extrelocatable as "Relocatable"
FROM pg_extension 
WHERE extname IN ('pg_stat_statements', 'pg_wait_sampling')
ORDER BY extname;

-- 設定の確認
SHOW shared_preload_libraries;
SHOW pg_stat_statements.max;
SHOW pg_stat_statements.track;

-- Wait sampling設定の確認
SELECT 
    name,
    setting,
    unit,
    short_desc
FROM pg_settings 
WHERE name LIKE 'pg_wait_sampling%'
ORDER BY name;

-- pg_stat_monitorは使用しない

-- 初期化完了メッセージ
SELECT 'New Relic monitoring extensions enabled successfully' as status;