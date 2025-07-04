#!/usr/bin/env python3
"""RSI 계산 문제 해결"""

import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.backtesting import Backtester
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fixed_rsi(df, period=14, column='close'):
    """수정된 RSI 계산 함수"""
    # 가격 변화 계산
    delta = df[column].diff()
    
    # 상승/하락 구분
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 첫 번째 평균 계산 (SMA)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # Wilder's smoothing 적용
    for i in range(period, len(df)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period-1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period-1) + loss.iloc[i]) / period
    
    # RS 계산
    rs = avg_gain / avg_loss
    
    # RSI 계산
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def test_rsi_fix():
    """RSI 계산 테스트 및 수정"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        market_type='futures',
        leverage=2
    )
    
    # 데이터 준비 (더 긴 기간)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 30일간의 데이터
    
    logger.info(f"데이터 준비: {start_date} ~ {end_date}")
    
    df = backtester.prepare_data(start_date, end_date)
    
    logger.info(f"데이터 shape: {df.shape}")
    logger.info(f"첫 20개 close 가격:")
    for i in range(min(20, len(df))):
        logger.info(f"  {df.index[i]}: {df.iloc[i]['close']:.2f}")
    
    # 원래 RSI 계산
    from src.indicators import relative_strength_index
    original_rsi = relative_strength_index(df, period=14)
    
    # 수정된 RSI 계산
    fixed_rsi_values = fixed_rsi(df, period=14)
    
    logger.info(f"\n=== RSI 계산 비교 ===")
    logger.info(f"원래 RSI - NaN 개수: {original_rsi.isna().sum()}")
    logger.info(f"수정된 RSI - NaN 개수: {fixed_rsi_values.isna().sum()}")
    
    # 첫 번째 유효한 RSI 값들 비교
    valid_fixed = fixed_rsi_values[~fixed_rsi_values.isna()]
    if len(valid_fixed) > 0:
        logger.info(f"\n수정된 RSI 값 (처음 10개):")
        for i, (idx, val) in enumerate(valid_fixed.head(10).items()):
            logger.info(f"  {idx}: RSI={val:.2f}")
    
    # 이동평균 교차와 함께 테스트
    from src.strategies import MovingAverageCrossover
    
    # RSI 필터 없는 버전으로 테스트
    strategy = MovingAverageCrossover(
        short_period=5,
        long_period=20,
        ma_type='ema'
    )
    
    # 전략에 수정된 RSI 적용 테스트
    df_test = df.copy()
    df_test['rsi_fixed'] = fixed_rsi_values
    
    # 신호 생성
    df_with_signals = strategy.generate_signals(df_test)
    
    logger.info(f"\n=== 신호 생성 결과 ===")
    signals = df_with_signals['signal'].values
    unique_signals = np.unique(signals)
    for sig in unique_signals:
        count = np.sum(signals == sig)
        logger.info(f"신호 {sig}: {count}개")
        
    # 포지션 변화 확인
    if 'position' in df_with_signals.columns:
        positions = df_with_signals['position'].values
        position_changes = positions[positions != 0]
        logger.info(f"\n포지션 변화: {len(position_changes)}개")

if __name__ == "__main__":
    test_rsi_fix()
