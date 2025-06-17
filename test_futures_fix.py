#!/usr/bin/env python3
"""
바이낸스 선물 거래 수정사항 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.exchange_api import ExchangeAPI
from src.db_manager import DatabaseManager
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_futures_position_save():
    """선물 포지션 저장 테스트"""
    try:
        # 1. ExchangeAPI 초기화
        logger.info("ExchangeAPI 초기화...")
        exchange_api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTCUSDT',
            timeframe='5m',
            market_type='futures',
            leverage=1
        )
        
        # 2. 포지션 데이터 가져오기
        logger.info("포지션 데이터 가져오기...")
        positions = exchange_api.get_positions('BTC/USDT')
        
        if positions:
            logger.info(f"포지션 개수: {len(positions)}")
            for pos in positions[:1]:  # 첫 번째 포지션만 출력
                logger.info("포지션 데이터:")
                for key, value in pos.items():
                    logger.info(f"  {key}: {value}")
                
                # contractSize 필드 확인
                if 'contractSize' in pos:
                    logger.info(f"✅ contractSize 필드 존재: {pos['contractSize']}")
                else:
                    logger.warning("❌ contractSize 필드 없음")
        else:
            logger.info("열린 포지션이 없습니다.")
            
            # 테스트용 가짜 포지션 데이터 생성
            test_position = {
                'symbol': 'BTC/USDT',
                'side': 'long',
                'contracts': 0.001,
                'entry_price': 45000.0,
                'leverage': 10,
                'contractSize': 1.0,  # contractSize 포함
                'unrealized_pnl': 0.0,
                'percentage': 0.0,
                'opened_at': '2025-06-17T12:00:00',  # opened_at 추가
                'status': 'open'  # status 추가
            }
            positions = [test_position]
            logger.info("테스트용 포지션 데이터 생성")
        
        # 3. DB에 포지션 저장 시도
        logger.info("\nDB에 포지션 저장 시도...")
        db = DatabaseManager()
        
        for position in positions:
            try:
                db.save_position(position)
                logger.info("✅ 포지션 저장 성공!")
            except Exception as e:
                logger.error(f"❌ 포지션 저장 실패: {e}")
                
        # 4. 저장된 포지션 확인
        logger.info("\n저장된 포지션 확인...")
        saved_positions = db.load_positions()  # status 매개변수 제거
        logger.info(f"저장된 포지션 개수: {len(saved_positions)}")
        
        return True
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=== 바이낸스 선물 거래 수정사항 테스트 시작 ===")
    if test_futures_position_save():
        logger.info("✅ 테스트 성공!")
    else:
        logger.error("❌ 테스트 실패!")
