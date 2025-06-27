#!/usr/bin/env python3
"""
SL/TP 기능을 포함한 DB 재초기화
"""

import os
import sys

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.db_manager import DatabaseManager

def reinit_db():
    """DB 재초기화"""
    print("=== DB 재초기화 (SL/TP 테이블 포함) ===\n")
    
    try:
        # DB 매니저 초기화 - 이때 테이블들이 생성됨
        db = DatabaseManager()
        print("✅ DatabaseManager 초기화 및 테이블 생성 완료")
        
        # 테이블 확인
        import sqlite3
        conn = sqlite3.connect('crypto_trading.db')
        cursor = conn.cursor()
        
        # 생성된 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        print("\n생성된 테이블 목록:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # positions 테이블 구조 확인
        cursor.execute("PRAGMA table_info(positions)")
        columns = cursor.fetchall()
        
        print("\n=== positions 테이블 구조 ===")
        sl_tp_columns = []
        for col in columns:
            print(f"  {col[1]} - {col[2]}")
            if 'stop_loss' in col[1] or 'take_profit' in col[1]:
                sl_tp_columns.append(col[1])
        
        if sl_tp_columns:
            print(f"\n✅ SL/TP 관련 컬럼 발견: {sl_tp_columns}")
        else:
            print("\n❌ SL/TP 관련 컬럼이 없습니다!")
        
        # stop_loss_orders 테이블 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stop_loss_orders'")
        if cursor.fetchone():
            print("\n✅ stop_loss_orders 테이블이 존재합니다.")
            cursor.execute("PRAGMA table_info(stop_loss_orders)")
            columns = cursor.fetchall()
            print("\n=== stop_loss_orders 테이블 구조 ===")
            for col in columns:
                print(f"  {col[1]} - {col[2]}")
        else:
            print("\n❌ stop_loss_orders 테이블이 존재하지 않습니다.")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ DB 재초기화 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reinit_db()
