"""
데이터베이스 연결 관리 헬퍼
SQLite 멀티스레드 환경에서 안전한 연결 관리를 위한 모듈
"""

import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger('crypto_bot')

@contextmanager
def get_db_connection(db_path):
    """
    데이터베이스 연결 컨텍스트 매니저
    
    Args:
        db_path: 데이터베이스 파일 경로
        
    Yields:
        tuple: (connection, cursor)
    """
    conn = None
    try:
        # check_same_thread=False로 멀티스레드 지원
        # timeout을 늘려서 동시 접근 시 대기
        conn = sqlite3.connect(
            db_path, 
            check_same_thread=False,
            timeout=30.0  # 30초 대기
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WAL 모드 활성화로 동시성 향상
        cursor.execute("PRAGMA journal_mode=WAL")
        
        yield conn, cursor
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"데이터베이스 연결 오류: {e}")
        raise
    finally:
        if conn:
            conn.close()
