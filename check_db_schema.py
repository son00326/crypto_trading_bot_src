#!/usr/bin/env python3
"""
데이터베이스 스키마 확인 스크립트
"""

import sqlite3
import os

def check_schema():
    """데이터베이스 스키마 확인"""
    # data/db 디렉토리의 DB 파일 확인
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'db', 'trading_bot.db')
    
    if not os.path.exists(db_path):
        print(f"DB 파일을 찾을 수 없습니다: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # positions 테이블 스키마 확인
    print("=== Positions 테이블 스키마 ===")
    cursor.execute("PRAGMA table_info(positions)")
    columns = cursor.fetchall()
    
    for col in columns:
        print(f"컬럼: {col[1]}, 타입: {col[2]}, NotNull: {col[3]}, 기본값: {col[4]}")
    
    # contractSize 컬럼 확인
    column_names = [col[1] for col in columns]
    if 'contractSize' in column_names:
        print("\n✅ contractSize 컬럼이 존재합니다!")
    else:
        print("\n❌ contractSize 컬럼이 없습니다!")
    
    conn.close()

if __name__ == "__main__":
    check_schema()
