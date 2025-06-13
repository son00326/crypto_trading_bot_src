#!/usr/bin/env python3
"""
거래 사이클 실행 테스트
전략 기반 매수/매도가 정상 작동하는지 확인하는 스크립트
"""
from src.trading_algorithm import TradingAlgorithm
from src.strategies import BollingerBandsStrategy
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_trading_cycle')

def test_trading_cycle_execution():
    """전략 기반 거래 사이클 테스트"""
    logger.info("테스트 모드에서 거래 사이클 테스트 시작...")
    
    # 테스트 모드로 알고리즘 초기화 (실제 주문은 실행되지 않음)
    # 볼린저 밴드 전략 파라미터 설정
    strategy_params = {
        'BollingerBandsStrategy': {
            'period': 20,
            'std_dev': 2.0
        }
    }
    
    algo = TradingAlgorithm(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='5m',  # 5분봉 사용
        test_mode=True,  # 테스트 모드 설정
        restore_state=False,
        strategy='BollingerBandsStrategy',
        strategy_params=strategy_params
    )
    
    logger.info(f"알고리즘 초기화 완료: 거래소={algo.exchange_id}, 심볼={algo.symbol}")
    
    # OHLCV 데이터 가져오기 테스트 - 여기서 데코레이터가 정상 작동하는지 확인
    try:
        logger.info("OHLCV 데이터 가져오기 테스트...")
        ohlcv_data = algo.data_collector.fetch_recent_data(
            limit=50  # limit 파라미터만 전달
        )
        logger.info(f"OHLCV 데이터 {len(ohlcv_data)}개 가져옴")
    except Exception as e:
        logger.error(f"OHLCV 데이터 가져오기 실패: {e}")
        return
    
    # 현재 가격 가져오기 테스트
    try:
        logger.info("현재 가격 가져오기 테스트...")
        current_price = algo.get_current_price(algo.symbol)
        logger.info(f"현재 {algo.symbol} 가격: {current_price}")
    except Exception as e:
        logger.error(f"현재 가격 가져오기 실패: {e}")
        return
    
    # 포트폴리오 정보 가져오기
    try:
        portfolio_status = algo.portfolio_manager.get_portfolio_status()
        logger.info(f"포트폴리오 상태: {portfolio_status}")
    except Exception as e:
        logger.error(f"포트폴리오 상태 가져오기 실패: {e}")
    
    # 거래 사이클 실행 테스트 (매매 신호 생성 및 주문 실행 과정)
    logger.info("거래 사이클 실행 테스트 시작...")
    try:
        for i in range(3):  # 3번의 거래 사이클 테스트
            logger.info(f"거래 사이클 {i+1} 실행 중...")
            algo.execute_trading_cycle()  # 매매 알고리즘 실행
            time.sleep(1)  # 간격 두기
    except Exception as e:
        logger.error(f"거래 사이클 실행 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # 테스트 후 결과 리포트
    logger.info("\n=== 테스트 결과 요약 ===")
    logger.info(f"사용 전략: {algo.strategy.__class__.__name__}")
    logger.info(f"전략 파라미터: {strategy_params}")
    
    # 마지막으로 포트폴리오 정보 다시 확인
    try:
        portfolio_status = algo.portfolio_manager.get_portfolio_status()
        logger.info(f"테스트 후 포트폴리오 상태: {portfolio_status}")
    except Exception as e:
        logger.error(f"포트폴리오 상태 가져오기 실패: {e}")
    
    logger.info("테스트 완료")

if __name__ == "__main__":
    test_trading_cycle_execution()
