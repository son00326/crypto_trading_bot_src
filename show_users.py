#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 데이터베이스 사용자 조회 스크립트
import os
import sys
import sqlite3
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 데이터베이스 경로 설정
db_dir = os.path.join(os.path.dirname(__file__), 'data', 'db')
db_path = os.path.join(db_dir, 'trading_bot.db')

def list_all_users():
    """
    데이터베이스에 저장된 모든 사용자 정보 조회
    """
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 사용자 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("사용자 테이블이 존재하지 않습니다.")
            return
        
        # 사용자 목록 조회
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        if not users:
            print("등록된 사용자가 없습니다.")
            return
        
        # 결과 출력
        print(f"\n===== 총 {len(users)}명의 사용자가 등록되어 있습니다 =====\n")
        for user in users:
            created_time = datetime.fromisoformat(user['created_at']) if user['created_at'] else "Unknown"
            formatted_time = created_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(created_time, datetime) else created_time
            
            print(f"ID: {user['id']}")
            print(f"사용자명: {user['username']}")
            print(f"이메일: {user['email'] or '없음'}")
            print(f"관리자 권한: {'예' if user['is_admin'] else '아니오'}")
            print(f"생성 시간: {formatted_time}")
            print("-" * 40)
            
    except sqlite3.Error as e:
        print(f"데이터베이스 오류: {e}")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_all_users()
