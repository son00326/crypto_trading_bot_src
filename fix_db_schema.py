#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sqlite3
import sys

def fix_positions_table():
    """positions 테이블에 created_at 컬럼 추가"""
    try:
        # 데이터베이스 파일 찾기
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/db/trading_bot.db')
        
        if not os.path.exists(db_path):
            print(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
            # 다른 위치에서 데이터베이스 찾기 시도
            possible_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app', 'database.db'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_app', 'data.db')
            ]
            
            for alt_path in possible_paths:
                if os.path.exists(alt_path):
                    db_path = alt_path
                    print(f"대체 위치에서 데이터베이스 파일을 찾았습니다: {db_path}")
                    break
            else:
                print("데이터베이스 파일을 찾을 수 없습니다.")
                return False
        
        print(f"데이터베이스 파일 위치: {db_path}")
        
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # positions 테이블 구조 확인
        cursor.execute("PRAGMA table_info(positions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"현재 positions 테이블 컬럼: {column_names}")
        
        # created_at 컬럼이 없으면 추가
        if 'created_at' not in column_names:
            print("created_at 컬럼 추가 중...")
            cursor.execute("ALTER TABLE positions ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            conn.commit()
            print("created_at 컬럼이 성공적으로 추가되었습니다.")
        else:
            print("created_at 컬럼이 이미 존재합니다.")
        
        # 변경 후 테이블 구조 확인
        cursor.execute("PRAGMA table_info(positions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        print(f"수정 후 positions 테이블 컬럼: {column_names}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = fix_positions_table()
    if success:
        print("데이터베이스 스키마 수정이 완료되었습니다.")
    else:
        print("데이터베이스 스키마 수정에 실패했습니다.")
        sys.exit(1)
