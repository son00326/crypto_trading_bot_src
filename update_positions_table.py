#!/usr/bin/env python3
"""
positions 테이블 스키마 업데이트 스크립트
기존 데이터를 보존하면서 스키마를 수정합니다.
"""

import sqlite3
import json
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_positions_table():
    """positions 테이블 스키마 업데이트"""
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()
        
        # positions 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='positions'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # 1. 기존 positions 테이블 이름 변경
            logger.info("기존 positions 테이블을 positions_old로 이름 변경")
            cursor.execute("ALTER TABLE positions RENAME TO positions_old")
            
            # 2. 새로운 positions 테이블 생성 (수정된 스키마)
            logger.info("새로운 positions 테이블 생성")
        else:
            logger.info("positions 테이블이 없으므로 새로 생성")
            
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            contracts REAL NOT NULL,
            notional REAL,
            entry_price REAL NOT NULL,
            mark_price REAL,
            liquidation_price REAL,
            unrealized_pnl REAL,
            margin_mode TEXT DEFAULT 'isolated',
            leverage INTEGER DEFAULT 1,
            opened_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            pnl REAL,
            status TEXT NOT NULL,
            additional_info TEXT,
            raw_data TEXT
        )
        ''')
        
        if table_exists:
            # 3. 기존 데이터 마이그레이션
            logger.info("기존 데이터 마이그레이션 시작")
            cursor.execute("SELECT * FROM positions_old")
            old_positions = cursor.fetchall()
            
            # 기존 테이블 컬럼 정보 가져오기
            cursor.execute("PRAGMA table_info(positions_old)")
            old_columns = [col[1] for col in cursor.fetchall()]
            logger.info(f"기존 컬럼: {old_columns}")
            
            migrated_count = 0
            for old_pos in old_positions:
                # 딕셔너리로 변환
                pos_dict = dict(zip(old_columns, old_pos))
                
                # 컬럼 매핑
                new_pos = {
                    'id': pos_dict.get('id'),
                    'symbol': pos_dict.get('symbol'),
                    'side': pos_dict.get('side'),
                    'contracts': pos_dict.get('amount') or pos_dict.get('contracts', 0),  # amount를 contracts로 매핑
                    'notional': pos_dict.get('notional'),
                    'entry_price': pos_dict.get('entry_price', 0),
                    'mark_price': pos_dict.get('mark_price'),
                    'liquidation_price': pos_dict.get('liquidation_price'),
                    'unrealized_pnl': pos_dict.get('unrealized_pnl'),
                    'margin_mode': pos_dict.get('margin_mode', 'isolated'),
                    'leverage': pos_dict.get('leverage', 1),
                    'opened_at': pos_dict.get('opened_at'),
                    'closed_at': pos_dict.get('closed_at'),
                    'pnl': pos_dict.get('pnl'),
                    'status': pos_dict.get('status', 'open'),
                    'additional_info': pos_dict.get('additional_info'),
                    'raw_data': pos_dict.get('raw_data')
                }
                
                # NULL 값 제거
                new_pos = {k: v for k, v in new_pos.items() if v is not None}
                
                # 새 테이블에 삽입
                columns = ', '.join(new_pos.keys())
                placeholders = ', '.join(['?' for _ in new_pos])
                values = list(new_pos.values())
                
                cursor.execute(f"INSERT INTO positions ({columns}) VALUES ({placeholders})", values)
                migrated_count += 1
            
            logger.info(f"{migrated_count}개의 포지션 데이터 마이그레이션 완료")
            
            # 4. 기존 테이블 삭제
            logger.info("기존 positions_old 테이블 삭제")
            cursor.execute("DROP TABLE positions_old")
        
        # 5. 커밋
        conn.commit()
        logger.info("positions 테이블 스키마 업데이트 완료!")
        
        # 6. 업데이트된 스키마 확인
        cursor.execute("PRAGMA table_info(positions)")
        new_columns = cursor.fetchall()
        logger.info("새로운 positions 테이블 스키마:")
        for col in new_columns:
            logger.info(f"  - {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'} {f'DEFAULT {col[4]}' if col[4] else ''}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"positions 테이블 업데이트 중 오류 발생: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    update_positions_table()
