#!/usr/bin/env python3
"""신호 생성 및 방향 테스트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime
from src.strategies import MovingAverageCrossover

def test_signal_generation_detailed():
    """상세한 신호 생성 테스트"""
    print("=== 상세 신호 생성 테스트 ===\n")
    
    # 이동평균 교차가 확실히 발생하는 데이터 생성
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
    
    # 단순한 V자 패턴 생성
    prices = []
    for i in range(100):
        if i < 50:
            # 하락 구간
            price = 60000 - i * 200
        else:
            # 상승 구간
            price = 60000 - 50 * 200 + (i - 50) * 300
        prices.append(price)
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p + 50 for p in prices],
        'low': [p - 50 for p in prices],
        'close': prices,
        'volume': [1000] * len(prices)
    }, index=dates)
    
    # 전략 생성 (짧은 기간으로 설정)
    strategy = MovingAverageCrossover(short_period=3, long_period=10)
    df_with_signals = strategy.generate_signals(df)
    
    # 결과 분석
    print("1. 가격 데이터 요약:")
    print(f"   - 시작 가격: {prices[0]:,.0f}")
    print(f"   - 최저 가격: {min(prices):,.0f} (인덱스: {prices.index(min(prices))})")
    print(f"   - 종료 가격: {prices[-1]:,.0f}")
    
    print("\n2. 이동평균 분석:")
    print("   최근 10개 데이터:")
    print(df_with_signals[['close', 'short_ma', 'long_ma', 'signal', 'position']].tail(10))
    
    print("\n3. 신호 발생 지점:")
    signal_changes = df_with_signals[df_with_signals['signal'] != df_with_signals['signal'].shift(1)]
    if len(signal_changes) > 0:
        print(f"   - 총 신호 변화: {len(signal_changes)}회")
        for idx, row in signal_changes.iterrows():
            print(f"   - {idx}: signal={row['signal']}, close={row['close']:,.0f}")
    
    print("\n4. Position 변화 지점:")
    position_changes = df_with_signals[df_with_signals['position'] != 0]
    if len(position_changes) > 0:
        print(f"   - 총 position 변화: {len(position_changes)}회")
        for idx, row in position_changes.iterrows():
            print(f"   - {idx}: position={row['position']}, signal={row['signal']}")
            
        # TradeSignal 생성 테스트
        print("\n5. TradeSignal 생성 테스트:")
        portfolio = {'total_balance': 10000, 'available_balance': 10000}
        
        # 마지막 position 변화에서 신호 생성
        last_change_idx = position_changes.index[-1]
        df_subset = df_with_signals.loc[:last_change_idx]
        
        # generate_signal 호출을 위해 position을 확인
        last_position = df_subset['position'].iloc[-1]
        last_signal = df_subset['signal'].iloc[-1]
        
        print(f"   - 마지막 position: {last_position}")
        print(f"   - 마지막 signal: {last_signal}")
        
        # 수동으로 direction 계산
        if last_position > 0:
            direction = 'long' if last_signal > 0 else 'short'
        elif last_position < 0:
            direction = 'close'
        else:
            direction = None
            
        print(f"   - 예상 direction: {direction}")
        
        # 실제 신호 생성
        signal = strategy.generate_signal(
            df_subset,
            df_subset['close'].iloc[-1],
            portfolio
        )
        
        if signal:
            print(f"\n   실제 생성된 TradeSignal:")
            print(f"   - Direction: {signal.direction}")
            print(f"   - Price: {signal.price:,.2f}")
            print(f"   - Confidence: {signal.confidence:.2f}")
            
            if signal.direction == direction:
                print("   ✅ Direction이 예상과 일치합니다!")
            else:
                print(f"   ❌ Direction 불일치 - 예상: {direction}, 실제: {signal.direction}")
    else:
        print("   - Position 변화 없음")
        
        # signal 값 확인
        unique_signals = df_with_signals['signal'].unique()
        print(f"\n   Signal 값 분포: {unique_signals}")
        
        # 이동평균 교차 확인
        crossovers = []
        for i in range(1, len(df_with_signals)):
            if (df_with_signals['short_ma'].iloc[i-1] <= df_with_signals['long_ma'].iloc[i-1] and
                df_with_signals['short_ma'].iloc[i] > df_with_signals['long_ma'].iloc[i]):
                crossovers.append(('상향', i))
            elif (df_with_signals['short_ma'].iloc[i-1] >= df_with_signals['long_ma'].iloc[i-1] and
                  df_with_signals['short_ma'].iloc[i] < df_with_signals['long_ma'].iloc[i]):
                crossovers.append(('하향', i))
        
        print(f"\n   이동평균 교차 감지: {len(crossovers)}회")
        for direction, idx in crossovers[:5]:  # 처음 5개만
            print(f"   - 인덱스 {idx}: {direction} 교차")

if __name__ == "__main__":
    test_signal_generation_detailed()
    print("\n=== 테스트 완료 ===")
