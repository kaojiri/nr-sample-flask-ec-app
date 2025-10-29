#!/usr/bin/env python3
"""
PostgreSQL拡張機能確認テスト

New Relic監視用の拡張機能が正しく有効になっているかを確認します：
- pg_stat_statements
- pg_wait_sampling  
- pg_stat_monitor
"""
import psycopg2
import sys


def test_postgresql_extensions():
    """PostgreSQL拡張機能の確認テスト"""
    print("PostgreSQL拡張機能確認テスト開始")
    print("=" * 60)
    
    try:
        # PostgreSQLに接続
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='ecdb',
            user='postgres',
            password='postgres'
        )
        cursor = conn.cursor()
        
        print("✅ PostgreSQL接続成功")
        
        # 1. shared_preload_librariesの確認
        print("\n1. shared_preload_libraries設定確認:")
        cursor.execute("SHOW shared_preload_libraries;")
        shared_libs = cursor.fetchone()[0]
        print(f"   設定値: {shared_libs}")
        
        expected_libs = ['pg_stat_statements', 'pg_wait_sampling', 'pg_stat_monitor']
        for lib in expected_libs:
            if lib in shared_libs:
                print(f"   ✅ {lib}: 設定済み")
            else:
                print(f"   ❌ {lib}: 未設定")
        
        # 2. インストール済み拡張の確認
        print("\n2. インストール済み拡張確認:")
        cursor.execute("""
            SELECT 
                extname as extension_name,
                extversion as version,
                extrelocatable as relocatable
            FROM pg_extension 
            WHERE extname IN ('pg_stat_statements', 'pg_wait_sampling', 'pg_stat_monitor')
            ORDER BY extname;
        """)
        
        extensions = cursor.fetchall()
        if extensions:
            for ext in extensions:
                print(f"   ✅ {ext[0]}: バージョン {ext[1]}")
        else:
            print("   ❌ New Relic監視用拡張が見つかりません")
        
        # 3. pg_stat_statements設定確認
        print("\n3. pg_stat_statements設定確認:")
        pg_stat_settings = [
            'pg_stat_statements.max',
            'pg_stat_statements.track',
            'pg_stat_statements.save'
        ]
        
        for setting in pg_stat_settings:
            try:
                cursor.execute(f"SHOW {setting};")
                value = cursor.fetchone()[0]
                print(f"   ✅ {setting}: {value}")
            except Exception as e:
                print(f"   ❌ {setting}: 取得失敗 ({e})")
        
        # 4. pg_wait_sampling設定確認
        print("\n4. pg_wait_sampling設定確認:")
        cursor.execute("""
            SELECT 
                name,
                setting,
                unit,
                short_desc
            FROM pg_settings 
            WHERE name LIKE 'pg_wait_sampling%'
            ORDER BY name;
        """)
        
        wait_settings = cursor.fetchall()
        if wait_settings:
            for setting in wait_settings:
                unit = setting[2] if setting[2] else ''
                print(f"   ✅ {setting[0]}: {setting[1]}{unit}")
        else:
            print("   ❌ pg_wait_sampling設定が見つかりません")
        
        # 5. pg_stat_monitor設定確認
        print("\n5. pg_stat_monitor設定確認:")
        cursor.execute("""
            SELECT 
                name,
                setting,
                unit,
                short_desc
            FROM pg_settings 
            WHERE name LIKE 'pg_stat_monitor%'
            ORDER BY name;
        """)
        
        monitor_settings = cursor.fetchall()
        if monitor_settings:
            for setting in monitor_settings:
                unit = setting[2] if setting[2] else ''
                print(f"   ✅ {setting[0]}: {setting[1]}{unit}")
        else:
            print("   ❌ pg_stat_monitor設定が見つかりません")
        
        # 6. 拡張機能の動作確認
        print("\n6. 拡張機能動作確認:")
        
        # pg_stat_statementsのテスト
        try:
            cursor.execute("SELECT COUNT(*) FROM pg_stat_statements;")
            count = cursor.fetchone()[0]
            print(f"   ✅ pg_stat_statements: {count}件のクエリ統計")
        except Exception as e:
            print(f"   ❌ pg_stat_statements: 動作確認失敗 ({e})")
        
        # pg_wait_samplingのテスト
        try:
            cursor.execute("SELECT COUNT(*) FROM pg_wait_sampling_history LIMIT 1;")
            print("   ✅ pg_wait_sampling: 待機イベント履歴テーブル利用可能")
        except Exception as e:
            print(f"   ❌ pg_wait_sampling: 動作確認失敗 ({e})")
        
        # pg_stat_monitorのテスト
        try:
            cursor.execute("SELECT COUNT(*) FROM pg_stat_monitor;")
            count = cursor.fetchone()[0]
            print(f"   ✅ pg_stat_monitor: {count}件の詳細クエリ統計")
        except Exception as e:
            print(f"   ❌ pg_stat_monitor: 動作確認失敗 ({e})")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ PostgreSQL拡張機能確認テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        return False


if __name__ == '__main__':
    success = test_postgresql_extensions()
    sys.exit(0 if success else 1)