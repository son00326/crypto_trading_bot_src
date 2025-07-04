#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BollingerBandFuturesStrategy 백테스트 결과 검증 스크립트
정확한 결과값을 확인하기 위한 단순화된 버전
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from src.backtesting import Backtester
from src.strategies import BollingerBandFuturesStrategy
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('verify_bollinger')

def run_single_backtest(timeframe='4h'):
    """단일 백테스트 실행 및 결과 검증"""
    
    logger.info(f"Bollinger Band Futures 백테스트 시작 ({timeframe})")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe=timeframe,
        market_type='futures',  # futures 모드
        leverage=3  # 3배 레버리지
    )
    
    # 백테스트 기간 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6개월
    
    # 초기 자산
    initial_balance = 10000  # 10,000 USDT
    
    # BollingerBandFutures 전략 설정
    strategy = BollingerBandFuturesStrategy(
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
        stop_loss_pct=4.0,
        take_profit_pct=8.0,
        leverage=3,
        max_position_size=0.95
    )
    
    # 백테스트 실행
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        commission=0.0005
    )
    
    # 결과 출력
    logger.info("\n백테스트 결과:")
    logger.info(f"초기 자산: ${initial_balance:,.2f}")
    logger.info(f"최종 자산: ${result.final_balance:,.2f}")
    
    # result.total_return이 이미 백분율인지 확인
    if hasattr(result, 'percent_return'):
        logger.info(f"총 수익률: {result.percent_return:.2f}%")
    else:
        # total_return이 소수점 형태인 경우
        if abs(result.total_return) < 10:  # -1.0 ~ 1.0 범위
            logger.info(f"총 수익률: {result.total_return * 100:.2f}%")
        else:  # 이미 백분율
            logger.info(f"총 수익률: {result.total_return:.2f}%")
    
    # 다른 지표들도 동일하게 처리
    if hasattr(result, 'sharpe_ratio'):
        logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
    
    if hasattr(result, 'max_drawdown'):
        if abs(result.max_drawdown) < 10:
            logger.info(f"최대 낙폭: {result.max_drawdown * 100:.2f}%")
        else:
            logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
    
    if hasattr(result, 'win_rate'):
        if result.win_rate < 10:
            logger.info(f"승률: {result.win_rate * 100:.2f}%")
        else:
            logger.info(f"승률: {result.win_rate:.2f}%")
    
    logger.info(f"총 거래 횟수: {result.total_trades}")
    
    # 추가 속성 확인
    attrs_to_check = ['winning_trades', 'losing_trades', 'average_win', 'average_loss', 
                      'profit_loss_ratio', 'profit_factor']
    
    for attr in attrs_to_check:
        if hasattr(result, attr):
            value = getattr(result, attr)
            logger.info(f"{attr}: {value}")
    
    return result

if __name__ == "__main__":
    # 4시간 봉 백테스트만 실행
    result = run_single_backtest('4h')
    
    # result 객체의 모든 속성 출력
    logger.info("\n=== BacktestResult 객체의 모든 속성 ===")
    for attr in dir(result):
        if not attr.startswith('_'):
            value = getattr(result, attr)
            if not callable(value):
                logger.info(f"{attr}: {value}")
