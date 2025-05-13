#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 - 관리자 외 사용자 삭제 스크립트
import os
import sys
import sqlite3

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 데이터베이스 경로 설정
db_dir = os.path.join(os.path.dirname(__file__), 'data', 'db')
db_path = os.path.join(db_dir, 'trading_bot.db')

def delete_non_admin_users():
    """
    admin 계정을 제외한 모든 사용자 삭제
    """
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 사용자 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("사용자 테이블이 존재하지 않습니다.")
            return
        
        # 삭제 전 사용자 수 확인
        cursor.execute("SELECT COUNT(*) FROM users")
        total_before = cursor.fetchone()[0]
        
        # admin이 아닌 사용자 삭제
        cursor.execute("DELETE FROM users WHERE username != 'admin'")
        conn.commit()
        
        # 삭제 후 사용자 수 확인
        cursor.execute("SELECT COUNT(*) FROM users")
        total_after = cursor.fetchone()[0]
        
        deleted_count = total_before - total_after
        print(f"총 {deleted_count}개의 계정이 삭제되었습니다.")
        print(f"남은 계정 수: {total_after}")
        
        # 관리자 계정 정보 출력
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()
        if admin:
            print("\n===== 관리자 계정 정보 =====")
            print(f"ID: {admin[0]}")
            print(f"사용자명: {admin[1]}")
            print(f"관리자 권한: {'예' if admin[4] else '아니오'}")
        
    except sqlite3.Error as e:
        print(f"데이터베이스 오류: {e}")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    delete_non_admin_users()
