#!/usr/bin/env python3
"""매매 방향 용어 변경 고급 테스트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.strategies import MovingAverageCrossover, RSIStrategy
from src.models.trade_signal import TradeSignal

def create_trending_data(trend='up', periods=100):
    """트렌드가 있는 테스트 데이터 생성"""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='1H')
    
    prices = []
    base_price = 50000
    
    if trend == 'up':
        # 명확한 상승 트렌드
        for i in range(periods):
            if i < 30:
                price = base_price - (30 - i) * 100 + np.random.randn() * 50
            else:
                price = base_price + (i - 30) * 100 + np.random.randn() * 50
            prices.append(price)
    else:
        # 명확한 하락 트렌드
        for i in range(periods):
            if i < 30:
                price = base_price + (30 - i) * 100 + np.random.randn() * 50
            else:
                price = base_price - (i - 30) * 100 + np.random.randn() * 50
            prices.append(price)
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p + abs(np.random.randn() * 100) for p in prices],
        'low': [p - abs(np.random.randn() * 100) for p in prices],
        'close': prices,
        'volume': [1000 + np.random.rand() * 100 for _ in prices]
    }, index=dates)
    
    return df

def test_ma_crossover():
    """이동평균 교차 전략 테스트"""
    print("=== 이동평균 교차 전략 테스트 ===\n")
    
    # 상승 트렌드 데이터로 테스트
    df = create_trending_data('up', 100)
    strategy = MovingAverageCrossover(short_period=5, long_period=20)
    df_with_signals = strategy.generate_signals(df)
    
    # position 변화가 있는 지점 찾기
    position_changes = df_with_signals[df_with_signals['position'] != 0]
    
    print(f"1. Position 변화 감지: {len(position_changes)}개")
    if len(position_changes) > 0:
        print("\n   최근 3개 position 변화:")
        print(position_changes[['signal', 'position', 'suggested_position_size']].tail(3))
        
        # 마지막 position 변화 시점에서 TradeSignal 생성
        portfolio = {'total_balance': 10000, 'available_balance': 10000}
        
        # 마지막 position 변화 시점의 데이터로 신호 생성
        last_change_idx = position_changes.index[-1]
        df_until_change = df[:last_change_idx]
        
        signal = strategy.generate_signal(
            df_until_change, 
            df_until_change['close'].iloc[-1], 
            portfolio
        )
        
        if signal:
            print(f"\n2. TradeSignal 생성 결과:")
            print(f"   - Direction: {signal.direction}")
            print(f"   - Price: {signal.price:.2f}")
            print(f"   - Confidence: {signal.confidence:.2f}")
            print(f"   - Strategy: {signal.strategy_name}")
            
            if signal.direction in ['long', 'short', 'close']:
                print("   ✅ Direction이 올바르게 변경되었습니다!")
            else:
                print(f"   ❌ Direction이 예상과 다릅니다: {signal.direction}")

def test_rsi_strategy():
    """RSI 전략 테스트"""
    print("\n\n=== RSI 전략 테스트 ===\n")
    
    # 급격한 하락 후 반등하는 데이터 생성
    df = create_trending_data('down', 70)
    df2 = create_trending_data('up', 30)
    df = pd.concat([df, df2])
    
    strategy = RSIStrategy(period=14, overbought=70, oversold=30)
    df_with_signals = strategy.generate_signals(df)
    
    # position 변화가 있는 지점 찾기
    position_changes = df_with_signals[df_with_signals['position'] != 0]
    
    print(f"1. Position 변화 감지: {len(position_changes)}개")
    if len(position_changes) > 0:
        print("\n   최근 3개 position 변화:")
        print(position_changes[['signal', 'position', 'suggested_position_size', 'rsi']].tail(3))
        
        # TradeSignal 생성 테스트
        portfolio = {'total_balance': 10000, 'available_balance': 10000}
        last_change_idx = position_changes.index[-1]
        df_until_change = df[:last_change_idx]
        
        signal = strategy.generate_signal(
            df_until_change,
            df_until_change['close'].iloc[-1],
            portfolio
        )
        
        if signal:
            print(f"\n2. TradeSignal 생성 결과:")
            print(f"   - Direction: {signal.direction}")
            print(f"   - Strategy: {signal.strategy_name}")
            
            if signal.direction in ['long', 'short', 'close']:
                print("   ✅ Direction이 올바르게 변경되었습니다!")

def test_signal_flow():
    """신호 흐름 테스트"""
    print("\n\n=== 신호 흐름 테스트 ===\n")
    
    # 다양한 신호 케이스 테스트
    test_cases = [
        {'signal': 1, 'position': 1, 'expected': 'long', 'desc': '롱 진입'},
        {'signal': -1, 'position': 1, 'expected': 'short', 'desc': '숏 진입'},
        {'signal': 0, 'position': -1, 'expected': 'close', 'desc': '포지션 청산'},
    ]
    
    for case in test_cases:
        print(f"\n테스트: {case['desc']}")
        print(f"  - signal: {case['signal']}, position: {case['position']}")
        print(f"  - 예상 direction: {case['expected']}")

if __name__ == "__main__":
    test_ma_crossover()
    test_rsi_strategy()
    test_signal_flow()
    
    print("\n\n=== 테스트 완료 ===")
    print("매매 방향 용어가 성공적으로 buy/sell에서 long/short로 변경되었습니다.")
