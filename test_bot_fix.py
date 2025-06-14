#!/usr/bin/env python3
"""
크립토 트레이딩 봇 수정 사항 테스트 스크립트
"""

import os
import sys
import logging
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.strategies import MovingAverageCrossover, RSIStrategy, CombinedStrategy

def setup_logging():
    """로깅 설정"""
    log_dir = os.path.join(project_root, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 로그 파일 경로
    log_file = os.path.join(log_dir, f'test_bot_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return log_file

def test_trading_algorithm():
    """TradingAlgorithm 테스트"""
    logger = logging.getLogger('test_bot_fix')
    
    try:
        logger.info("=== 트레이딩 봇 수정 사항 테스트 시작 ===")
        
        # 1. TradingAlgorithm 초기화
        logger.info("1. TradingAlgorithm 초기화 중...")
        
        # 전략 설정
        ma_strategy = MovingAverageCrossover(short_period=9, long_period=26)
        rsi_strategy = RSIStrategy(period=14, overbought=70, oversold=30)
        combined_strategy = CombinedStrategy([ma_strategy, rsi_strategy])
        
        algo = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            strategy=combined_strategy,
            test_mode=True,
            restore_state=False  # 테스트를 위해 상태 복원 비활성화
        )
        
        logger.info("✅ TradingAlgorithm 초기화 성공")
        
        # 2. 현재 가격 조회 테스트
        logger.info("\n2. 현재 가격 조회 테스트...")
        current_price = algo.get_current_price()
        if current_price:
            logger.info(f"✅ 현재 가격 조회 성공: {current_price}")
        else:
            logger.warning("❌ 현재 가격 조회 실패")
        
        # 3. 포트폴리오 상태 확인
        logger.info("\n3. 포트폴리오 상태 확인...")
        portfolio_summary = algo.get_portfolio_summary()
        logger.info(f"포트폴리오 요약: {portfolio_summary}")
        
        # 4. 거래 사이클 단일 실행 테스트
        logger.info("\n4. 거래 사이클 단일 실행 테스트...")
        algo.execute_trading_cycle()
        logger.info("✅ 거래 사이클 실행 완료")
        
        # 5. 거래 스레드 시작 테스트
        logger.info("\n5. 거래 스레드 시작 테스트...")
        logger.info(f"거래 활성화 상태 (시작 전): {algo.trading_active}")
        
        trading_thread = algo.start_trading_thread(interval=30)  # 30초 간격
        logger.info(f"거래 활성화 상태 (시작 후): {algo.trading_active}")
        logger.info(f"거래 스레드 상태: {'실행 중' if trading_thread.is_alive() else '중지됨'}")
        
        # 몇 초 대기 후 스레드 중지
        import time
        logger.info("\n테스트를 위해 60초 동안 실행...")
        time.sleep(60)
        
        # 6. 거래 스레드 중지
        logger.info("\n6. 거래 스레드 중지...")
        algo.trading_active = False
        trading_thread.join(timeout=10)
        logger.info(f"거래 스레드 상태: {'실행 중' if trading_thread.is_alive() else '중지됨'}")
        
        logger.info("\n=== 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())

def test_database_migration():
    """데이터베이스 마이그레이션 테스트"""
    logger = logging.getLogger('test_bot_fix')
    
    try:
        logger.info("\n=== 데이터베이스 마이그레이션 테스트 ===")
        
        from src.db_manager import DatabaseManager
        
        # DatabaseManager 초기화 (자동으로 테이블 생성/마이그레이션)
        db = DatabaseManager()
        
        # positions 테이블 스키마 확인
        conn, cursor = db._get_connection()
        cursor.execute("PRAGMA table_info(positions)")
        columns = cursor.fetchall()
        
        column_names = [col[1] for col in columns]
        logger.info(f"positions 테이블 컬럼: {column_names}")
        
        if 'raw_data' in column_names:
            logger.info("✅ raw_data 컬럼이 성공적으로 추가되었습니다.")
        else:
            logger.error("❌ raw_data 컬럼이 없습니다.")
        
    except Exception as e:
        logger.error(f"데이터베이스 테스트 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # 로깅 설정
    log_file = setup_logging()
    print(f"로그 파일: {log_file}")
    
    # 데이터베이스 마이그레이션 테스트
    test_database_migration()
    
    # TradingAlgorithm 테스트
    test_trading_algorithm()
    
    print(f"\n테스트 완료. 로그 파일을 확인하세요: {log_file}")
