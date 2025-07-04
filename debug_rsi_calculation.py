#!/usr/bin/env python3
"""RSI 계산 디버깅 스크립트"""

import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.indicators import relative_strength_index
from src.backtesting import Backtester
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_rsi_calculation():
    """RSI 계산 과정 디버깅"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        market_type='futures',
        leverage=2
    )
    
    # 데이터 준비
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)  # 10일간의 데이터로 테스트
    
    logger.info(f"데이터 준비: {start_date} ~ {end_date}")
    
    df = backtester.prepare_data(start_date, end_date)
    
    logger.info(f"데이터 shape: {df.shape}")
    logger.info(f"데이터 컬럼: {list(df.columns)}")
    
    # RSI 계산 (직접 계산 과정 확인)
    period = 14
    column = 'close'
    
    # 가격 변화 계산
    df['delta'] = df[column].diff()
    
    # 상승/하락 구분
    df['gain'] = df['delta'].clip(lower=0)
    df['loss'] = -df['delta'].clip(upper=0)
    
    logger.info(f"\n=== 가격 변화 분석 ===")
    logger.info(f"delta 통계: min={df['delta'].min():.2f}, max={df['delta'].max():.2f}, mean={df['delta'].mean():.2f}")
    logger.info(f"gain 통계: min={df['gain'].min():.2f}, max={df['gain'].max():.2f}, mean={df['gain'].mean():.2f}")
    logger.info(f"loss 통계: min={df['loss'].min():.2f}, max={df['loss'].max():.2f}, mean={df['loss'].mean():.2f}")
    
    # 초기 평균 값 확인
    if len(df) >= period:
        first_avg_gain = df['gain'].rolling(window=period).mean().iloc[period-1]
        first_avg_loss = df['loss'].rolling(window=period).mean().iloc[period-1]
        
        logger.info(f"\n=== 초기 평균 값 ===")
        logger.info(f"첫 평균 상승: {first_avg_gain:.4f}")
        logger.info(f"첫 평균 하락: {first_avg_loss:.4f}")
    else:
        logger.warning(f"데이터가 부족합니다. 필요: {period}개, 실제: {len(df)}개")
    
    # indicators.py의 relative_strength_index 함수 호출
    try:
        rsi = relative_strength_index(df, period=period)
        
        logger.info(f"\n=== RSI 계산 결과 ===")
        logger.info(f"RSI shape: {rsi.shape}")
        logger.info(f"RSI NaN 개수: {rsi.isna().sum()}")
        logger.info(f"RSI 통계: min={rsi.min():.2f}, max={rsi.max():.2f}, mean={rsi.mean():.2f}")
        
        # NaN이 아닌 첫 번째 RSI 값들 출력
        valid_rsi = rsi[~rsi.isna()]
        if len(valid_rsi) > 0:
            logger.info(f"\n유효한 RSI 값 (처음 10개):")
            for i, (idx, val) in enumerate(valid_rsi.head(10).items()):
                logger.info(f"  {idx}: RSI={val:.2f}")
        else:
            logger.warning("유효한 RSI 값이 없습니다!")
            
        # 데이터프레임에 RSI 추가
        df['rsi'] = rsi
        
        # 이동평균 교차 지점에서의 RSI 확인
        from src.indicators import exponential_moving_average
        
        df['short_ma'] = exponential_moving_average(df, period=12)
        df['long_ma'] = exponential_moving_average(df, period=26)
        
        # 교차 지점 찾기
        short_ma = df['short_ma'].values
        long_ma = df['long_ma'].values
        
        crossover_indices = []
        for i in range(1, len(df)):
            prev_diff = short_ma[i-1] - long_ma[i-1]
            curr_diff = short_ma[i] - long_ma[i]
            
            if (prev_diff <= 0 and curr_diff > 0) or (prev_diff >= 0 and curr_diff < 0):
                crossover_indices.append(i)
        
        logger.info(f"\n=== 교차 지점에서의 RSI 값 ===")
        logger.info(f"총 교차 횟수: {len(crossover_indices)}")
        
        if crossover_indices:
            logger.info("교차 지점 RSI 값:")
            for idx in crossover_indices[:5]:  # 처음 5개만
                date = df.index[idx]
                rsi_val = df.iloc[idx]['rsi']
                logger.info(f"  {date}: RSI={rsi_val:.2f if not pd.isna(rsi_val) else 'NaN'}")
                
    except Exception as e:
        logger.error(f"RSI 계산 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    debug_rsi_calculation()
