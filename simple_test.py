#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
리팩토링된 코드의 간단한 테스트 스크립트
"""

import logging
import sys
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger('TEST')

# 모듈 로드 확인 테스트
def test_import_modules():
    logger.info("모듈 로드 테스트 시작")
    try:
        from src.portfolio_manager import PortfolioManager
        logger.info("PortfolioManager 모듈 로드 성공")
        
        from src.order_executor import OrderExecutor
        logger.info("OrderExecutor 모듈 로드 성공")
        
        from src.trading_algorithm import TradingAlgorithm
        logger.info("TradingAlgorithm 모듈 로드 성공")
        
        return True
    except ImportError as e:
        logger.error(f"모듈 로드 실패: {e}")
        return False

# 기본 모듈 메서드 테스트
def test_basic_methods():
    logger.info("기본 메서드 테스트 시작")
    try:
        from src.portfolio_manager import PortfolioManager
        from src.order_executor import OrderExecutor
        
        # 목(Mock) 객체 생성
        class MockExchangeAPI:
            def __init__(self):
                self.is_futures = False
                self.leverage = 1
            
            def get_ticker(self, symbol):
                return {"last": 50000.0}
            
            def get_balance(self):
                return {"free": {"BTC": 1.0, "USDT": 50000.0}}
        
        class MockDBManager:
            def save_balance(self, currency, amount, metadata=None):
                logger.info(f"잔고 저장: {currency}={amount}")
                return True
            
            def get_open_positions(self, symbol=None):
                return []
        
        # 객체 생성 테스트
        exchange_api = MockExchangeAPI()
        db_manager = MockDBManager()
        
        # PortfolioManager 테스트
        portfolio_manager = PortfolioManager(
            exchange_api=exchange_api,
            db_manager=db_manager,
            symbol="BTC/USDT",
            test_mode=True
        )
        
        # 포트폴리오 초기화 테스트
        portfolio_manager.portfolio["base_currency"] = "BTC"
        portfolio_manager.portfolio["quote_currency"] = "USDT"
        portfolio_manager.portfolio["base_balance"] = 1.0
        portfolio_manager.portfolio["quote_balance"] = 50000.0
        
        logger.info(f"포트폴리오 초기화: {portfolio_manager.portfolio}")
        
        # OrderExecutor 테스트
        order_executor = OrderExecutor(
            exchange_api=exchange_api,
            db_manager=db_manager,
            symbol="BTC/USDT",
            test_mode=True
        )
        
        # 현재 가격 조회 테스트
        current_price = order_executor.get_current_price()
        logger.info(f"현재 가격: {current_price}")
        
        return True
    except Exception as e:
        logger.error(f"기본 메서드 테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    logger.info("===== 리팩토링된 코드 간단 테스트 시작 =====")
    
    # 모듈 로드 테스트
    if not test_import_modules():
        logger.error("모듈 로드 테스트 실패. 테스트를 중단합니다.")
        return
    
    # 기본 메서드 테스트
    if not test_basic_methods():
        logger.error("기본 메서드 테스트 실패. 테스트를 중단합니다.")
        return
    
    logger.info("===== 모든 테스트가 완료되었습니다 =====")

if __name__ == "__main__":
    main()
