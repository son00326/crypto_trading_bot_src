#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db_manager import DatabaseManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_database():
    """데이터베이스 초기화"""
    try:
        logger.info("데이터베이스 초기화 시작...")
        db = DatabaseManager()
        logger.info("DatabaseManager 인스턴스 생성 완료")
        
        # create_tables 메서드는 __init__에서 자동 호출되므로
        # 추가 작업 없이 테이블이 생성됨
        logger.info("데이터베이스 초기화 완료!")
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 초기화 중 오류: {e}")
        return False

if __name__ == "__main__":
    if init_database():
        logger.info("데이터베이스가 성공적으로 초기화되었습니다.")
    else:
        logger.error("데이터베이스 초기화에 실패했습니다.")
