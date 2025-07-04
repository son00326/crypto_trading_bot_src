#!/usr/bin/env python3
"""이동평균 교차 전략 디버깅 스크립트"""

import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.strategies import MovingAverageCrossover
from src.exchange_api import ExchangeAPI
from src.backtesting import Backtester
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_simple_ma_crossover():
    """필터 없는 단순 이동평균 교차 테스트"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        market_type='futures',
        leverage=2
    )
    
    # 간단한 이동평균 교차 전략 생성 (짧은 기간으로 더 많은 신호 생성)
    strategy = MovingAverageCrossover(
        short_period=5,
        long_period=20,
        ma_type='ema'
    )
    
    # 백테스트 실행
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)  # 60일간 테스트
    
    logger.info(f"백테스트 시작: {strategy.name}")
    logger.info(f"기간: {start_date} ~ {end_date}")
    
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000,
        commission=0.001,
        market_type='futures',
        leverage=2
    )
    
    # 결과 출력
    logger.info(f"\n백테스트 결과:")
    logger.info(f"총 거래 횟수: {result.total_trades}")
    logger.info(f"최종 수익률: {result.total_return:.2f}%")
    logger.info(f"승률: {result.win_rate:.2f}%")
    logger.info(f"샤프 비율: {result.sharpe_ratio:.2f}")
    logger.info(f"최대 낙폭: {result.max_drawdown:.2f}%")
    
    # 거래 내역 확인
    if result.trades:
        logger.info(f"\n처음 10개 거래:")
        for i, trade in enumerate(result.trades[:10]):
            logger.info(f"  {i+1}. {trade}")
    else:
        logger.info("\n거래가 발생하지 않았습니다.")
        
        # 백테스트 데이터 분석
        if hasattr(backtester, 'df') and backtester.df is not None:
            df = backtester.df
            
            # 이동평균 교차 지점 확인
            if 'short_ma' in df.columns and 'long_ma' in df.columns:
                df['ma_diff'] = df['short_ma'] - df['long_ma']
                df['ma_diff_prev'] = df['ma_diff'].shift(1)
                
                # 교차 지점 찾기
                crossovers = df[
                    ((df['ma_diff_prev'] <= 0) & (df['ma_diff'] > 0)) |
                    ((df['ma_diff_prev'] >= 0) & (df['ma_diff'] < 0))
                ]
                
                logger.info(f"\n이동평균 교차 지점: {len(crossovers)}개")
                
                if len(crossovers) > 0:
                    logger.info("처음 5개 교차 지점:")
                    for idx in crossovers.index[:5]:
                        row = df.loc[idx]
                        cross_type = '상향' if row['ma_diff'] > 0 else '하향'
                        logger.info(f"  {row.name}: {cross_type} 교차")
                        if 'signal' in row:
                            logger.info(f"    신호: {row['signal']}")
                        if 'rsi' in row:
                            logger.info(f"    RSI: {row['rsi']:.2f}")
                        if 'volume' in row and 'volume_ma' in row:
                            logger.info(f"    볼륨/볼륨MA: {row['volume']/row['volume_ma']:.2f}")

if __name__ == "__main__":
    test_simple_ma_crossover()
