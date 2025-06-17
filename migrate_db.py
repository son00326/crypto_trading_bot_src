#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 스크립트
기존 positions 테이블에 contractSize 컬럼 추가
"""

import sqlite3
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_database():
    """데이터베이스 마이그레이션 실행"""
    # 데이터베이스 경로
    db_path = os.path.join(os.path.dirname(__file__), 'trading_bot.db')
    
    if not os.path.exists(db_path):
        logger.error(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 현재 positions 테이블의 컬럼 확인
        cursor.execute("PRAGMA table_info(positions)")
        columns = [column[1] for column in cursor.fetchall()]
        logger.info(f"현재 positions 테이블 컬럼: {columns}")
        
        # contractSize 컬럼이 없으면 추가
        if 'contractSize' not in columns:
            cursor.execute('ALTER TABLE positions ADD COLUMN contractSize REAL DEFAULT 1.0')
            conn.commit()
            logger.info("contractSize 컬럼이 positions 테이블에 추가되었습니다.")
        else:
            logger.info("contractSize 컬럼이 이미 존재합니다.")
        
        # 마이그레이션 후 컬럼 재확인
        cursor.execute("PRAGMA table_info(positions)")
        columns_after = [column[1] for column in cursor.fetchall()]
        logger.info(f"마이그레이션 후 positions 테이블 컬럼: {columns_after}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"마이그레이션 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    logger.info("데이터베이스 마이그레이션 시작...")
    if migrate_database():
        logger.info("데이터베이스 마이그레이션 완료!")
    else:
        logger.error("데이터베이스 마이그레이션 실패!")
