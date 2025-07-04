#!/usr/bin/env python3
"""MovingAverageCrossover 전략의 필터 조건 디버깅"""

import sys
sys.path.append('/Users/yong/Desktop/crypto_trading_bot_src')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.strategies import MovingAverageCrossover
from src.backtesting import Backtester
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_ma_crossover_signals():
    """MA 교차 신호와 필터 조건 분석"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        market_type='futures',
        leverage=2
    )
    
    # 전략 생성
    strategy = MovingAverageCrossover(
        short_period=12,
        long_period=26,
        ma_type='ema'
    )
    
    # 백테스트 데이터 준비
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 30일간 분석
    
    logger.info(f"데이터 준비: {start_date} ~ {end_date}")
    
    df = backtester.prepare_data(start_date, end_date)
    
    # 신호 생성
    df_with_signals = strategy.generate_signals(df)
    
    # 교차 지점 분석
    short_ma = df_with_signals['short_ma'].values
    long_ma = df_with_signals['long_ma'].values
    rsi = df_with_signals['rsi'].values
    volume = df_with_signals['volume'].values
    volume_ma = df_with_signals['volume_ma'].values
    signals = df_with_signals['signal'].values
    
    # 교차 지점 찾기
    crossover_points = []
    filter_blocks = {
        'rsi_overbuyed': 0,
        'rsi_oversold': 0,
        'volume_low': 0,
        'total_crossovers': 0
    }
    
    for i in range(1, len(df_with_signals)):
        prev_diff = short_ma[i-1] - long_ma[i-1]
        curr_diff = short_ma[i] - long_ma[i]
        
        # 상향 교차
        if prev_diff <= 0 and curr_diff > 0:
            filter_blocks['total_crossovers'] += 1
            
            rsi_ok = rsi[i] < 70
            volume_ok = volume[i] > volume_ma[i] * 0.5
            
            if not rsi_ok:
                filter_blocks['rsi_overbuyed'] += 1
            if not volume_ok:
                filter_blocks['volume_low'] += 1
                
            crossover_points.append({
                'index': i,
                'date': df_with_signals.index[i],
                'type': 'bullish',
                'short_ma': short_ma[i],
                'long_ma': long_ma[i],
                'rsi': rsi[i],
                'rsi_ok': rsi_ok,
                'volume': volume[i],
                'volume_ma': volume_ma[i],
                'volume_ratio': volume[i] / volume_ma[i] if volume_ma[i] > 0 else 0,
                'volume_ok': volume_ok,
                'signal_generated': signals[i] == 1,
                'filters_passed': rsi_ok and volume_ok
            })
            
        # 하향 교차
        elif prev_diff >= 0 and curr_diff < 0:
            filter_blocks['total_crossovers'] += 1
            
            rsi_ok = rsi[i] > 30
            volume_ok = volume[i] > volume_ma[i] * 0.5
            
            if not rsi_ok:
                filter_blocks['rsi_oversold'] += 1
            if not volume_ok:
                filter_blocks['volume_low'] += 1
                
            crossover_points.append({
                'index': i,
                'date': df_with_signals.index[i],
                'type': 'bearish',
                'short_ma': short_ma[i],
                'long_ma': long_ma[i],
                'rsi': rsi[i],
                'rsi_ok': rsi_ok,
                'volume': volume[i],
                'volume_ma': volume_ma[i],
                'volume_ratio': volume[i] / volume_ma[i] if volume_ma[i] > 0 else 0,
                'volume_ok': volume_ok,
                'signal_generated': signals[i] == -1,
                'filters_passed': rsi_ok and volume_ok
            })
    
    # 결과 출력
    logger.info(f"\n=== 교차 지점 분석 결과 ===")
    logger.info(f"총 교차 횟수: {filter_blocks['total_crossovers']}")
    logger.info(f"RSI 과매수로 차단된 상향 교차: {filter_blocks['rsi_overbuyed']}")
    logger.info(f"RSI 과매도로 차단된 하향 교차: {filter_blocks['rsi_oversold']}")
    logger.info(f"볼륨 부족으로 차단된 교차: {filter_blocks['volume_low']}")
    
    # 필터를 통과한 교차 수
    passed_crossovers = [cp for cp in crossover_points if cp['filters_passed']]
    logger.info(f"필터를 통과한 교차: {len(passed_crossovers)}")
    
    # 상세 분석
    if crossover_points:
        logger.info(f"\n=== 교차 지점 상세 분석 (처음 10개) ===")
        for i, cp in enumerate(crossover_points[:10]):
            logger.info(f"\n{i+1}. {cp['date']} - {cp['type']} 교차")
            logger.info(f"   단기 MA: {cp['short_ma']:.2f}, 장기 MA: {cp['long_ma']:.2f}")
            logger.info(f"   RSI: {cp['rsi']:.2f} {'✓' if cp['rsi_ok'] else '✗ (차단됨)'}")
            logger.info(f"   볼륨 비율: {cp['volume_ratio']:.2f} {'✓' if cp['volume_ok'] else '✗ (차단됨)'}")
            logger.info(f"   필터 통과: {'예' if cp['filters_passed'] else '아니오'}")
            logger.info(f"   신호 생성: {'예' if cp['signal_generated'] else '아니오'}")
    
    # 신호 분포 확인
    unique_signals = np.unique(signals)
    logger.info(f"\n=== 신호 분포 ===")
    for sig in unique_signals:
        count = np.sum(signals == sig)
        logger.info(f"신호 {sig}: {count}개 ({count/len(signals)*100:.1f}%)")
    
    # position 확인
    if 'position' in df_with_signals.columns:
        positions = df_with_signals['position'].values
        position_changes = positions[positions != 0]
        logger.info(f"\n=== 포지션 변화 ===")
        logger.info(f"총 포지션 변화: {len(position_changes)}개")
        
        if len(position_changes) > 0:
            logger.info("처음 10개 포지션 변화:")
            change_indices = np.where(positions != 0)[0]
            for idx in change_indices[:10]:
                logger.info(f"  {df_with_signals.index[idx]}: position={positions[idx]}, signal={signals[idx]}")

if __name__ == "__main__":
    analyze_ma_crossover_signals()
