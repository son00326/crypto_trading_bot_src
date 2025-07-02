#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
리팩토링된 코드 테스트 스크립트
"""

import logging
import sys
import time
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('TEST')

# 필요한 모듈 임포트
from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
from src.db_manager import DatabaseManager
from src.risk_manager import RiskManager
from src.strategies import Strategy

class DummyStrategy(Strategy):
    """테스트용 전략 클래스"""
    def __init__(self):
        super().__init__(name="DummyStrategy")
        self.params = {"param1": 10, "param2": 20}
    
    def analyze_market(self, data):
        # 테스트를 위해 항상 매수 신호 반환
        return {'signal': 'buy', 'confidence': 0.8, 'reason': '테스트 신호'}
    
    def calculate_indicators(self, data):
        return {'ma': 100, 'rsi': 60}

def main():
    logger.info("리팩토링된 코드 테스트 시작")
    
    # 테스트 환경 설정
    exchange_api = ExchangeAPI(api_key="test", api_secret="test", test_mode=True)
    db_manager = DatabaseManager(db_path=":memory:")
    risk_manager = RiskManager(risk_percentage=2.0)
    strategy = DummyStrategy()
    
    # TradingAlgorithm 인스턴스 생성
    trading_algorithm = TradingAlgorithm(
        exchange_api=exchange_api,
        db_manager=db_manager,
        risk_manager=risk_manager,
        strategy=strategy,
        symbol="BTC/USDT",
        test_mode=True
    )
    
    # 테스트 1: 포트폴리오 정보 초기화
    logger.info("테스트 1: 포트폴리오 정보 초기화")
    # 테스트용 잔고 설정
    trading_algorithm.portfolio_manager.portfolio['base_balance'] = 1.0  # 1 BTC
    trading_algorithm.portfolio_manager.portfolio['quote_balance'] = 50000.0  # 50,000 USDT
    
    # 포트폴리오 정보 업데이트 후 조회
    trading_algorithm.update_portfolio()
    logger.info(f"현재 포트폴리오: {trading_algorithm.portfolio}")
    
    # 테스트 2: 시장 가격 조회
    logger.info("테스트 2: 시장 가격 조회")
    # 테스트 모드에서는 모의 가격 반환
    current_price = trading_algorithm.get_current_price()
    logger.info(f"현재 BTC/USDT 가격: {current_price}")
    
    # 테스트 3: 매수 주문 실행
    logger.info("테스트 3: 매수 주문 실행")
    buy_result = trading_algorithm.execute_buy(
        price=50000,  # 가정된 가격
        quantity=0.1,  # 0.1 BTC 매수
        additional_info={"test": "buy_order"}
    )
    logger.info(f"매수 주문 결과: {buy_result}")
    
    # 업데이트된 포트폴리오 확인
    logger.info(f"매수 후 포트폴리오: {trading_algorithm.portfolio}")
    
    # 열린 포지션 확인
    open_positions = trading_algorithm.get_open_positions()
    logger.info(f"현재 열린 포지션: {open_positions}")
    
    # 포지션 ID 저장
    if open_positions:
        position_id = open_positions[0]['id']
        
        # 테스트 4: 매도 주문 실행 (부분 청산)
        logger.info("테스트 4: 매도 주문 실행 (부분 청산)")
        sell_result = trading_algorithm.execute_sell(
            price=55000,  # 가정된 가격 (10% 상승)
            quantity=0.05,  # 포지션의 절반만 청산
            additional_exit_info={"reason": "부분 이익 실현"},
            percentage=0.5,
            position_id=position_id
        )
        logger.info(f"매도 주문 결과: {sell_result}")
        
        # 업데이트된 포지션 확인
        open_positions = trading_algorithm.get_open_positions()
        logger.info(f"부분 청산 후 열린 포지션: {open_positions}")
        
        # 테스트 5: 포지션 완전 종료
        logger.info("테스트 5: 포지션 완전 종료")
        close_result = trading_algorithm.close_position(
            position_id=position_id,
            reason="테스트 완전 종료"
        )
        logger.info(f"포지션 종료 결과: {close_result}")
        
        # 종료 후 포지션 확인
        open_positions = trading_algorithm.get_open_positions()
        logger.info(f"종료 후 열린 포지션: {open_positions}")
    
    # 테스트 6: 상태 저장
    logger.info("테스트 6: 상태 저장")
    save_result = trading_algorithm.save_state()
    logger.info(f"상태 저장 결과: {save_result}")
    
    logger.info("모든 테스트 완료!")

if __name__ == "__main__":
    main()
