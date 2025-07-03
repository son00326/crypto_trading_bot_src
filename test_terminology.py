#!/usr/bin/env python3
"""매매 방향 용어 변경 테스트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.strategies import MovingAverageCrossover
from src.models.trade_signal import TradeSignal

def test_signal_generation():
    """전략의 신호 생성 테스트"""
    print("=== 매매 방향 용어 변경 테스트 ===\n")
    
    # 테스트 데이터 생성
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
    
    # 상승 추세 데이터 생성 (이동평균 교차 발생)
    prices = []
    base_price = 50000
    for i in range(100):
        if i < 50:
            # 하락 추세
            price = base_price - i * 100 + np.random.randn() * 50
        else:
            # 상승 추세 (교차 발생)
            price = base_price - 50 * 100 + (i - 50) * 200 + np.random.randn() * 50
        prices.append(price)
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p + np.random.rand() * 100 for p in prices],
        'low': [p - np.random.rand() * 100 for p in prices],
        'close': prices,
        'volume': [1000 + np.random.rand() * 100 for _ in prices]
    }, index=dates)
    
    # 전략 테스트
    strategy = MovingAverageCrossover(short_period=10, long_period=20)
    
    # 신호 생성
    df_with_signals = strategy.generate_signals(df)
    
    # 결과 확인
    print("1. 신호 생성 결과:")
    print(f"   - 총 데이터 수: {len(df_with_signals)}")
    print(f"   - 롱 신호 (1): {(df_with_signals['signal'] == 1).sum()}개")
    print(f"   - 숏 신호 (-1): {(df_with_signals['signal'] == -1).sum()}개")
    print(f"   - 중립 신호 (0): {(df_with_signals['signal'] == 0).sum()}개")
    
    # 마지막 몇 개 신호 확인
    print("\n2. 최근 5개 신호:")
    recent_signals = df_with_signals[['signal', 'position', 'suggested_position_size']].tail(5)
    print(recent_signals)
    
    # TradeSignal 생성 테스트
    print("\n3. TradeSignal 생성 테스트:")
    portfolio = {'total_balance': 10000, 'available_balance': 10000}
    signal = strategy.generate_signal(df, df['close'].iloc[-1], portfolio)
    
    if signal:
        print(f"   - Direction: {signal.direction}")
        print(f"   - Price: {signal.price}")
        print(f"   - Confidence: {signal.confidence}")
        print(f"   - Strategy: {signal.strategy_name}")
        
        # Direction 확인
        if signal.direction in ['long', 'short', 'close', 'hold']:
            print("   ✅ Direction 값이 올바르게 변경되었습니다!")
        else:
            print(f"   ❌ Direction 값이 예상과 다릅니다: {signal.direction}")
    else:
        print("   - 신호 없음 (HOLD)")
    
    print("\n4. 용어 매핑 확인:")
    print("   - 전략 신호: long(롱 진입), short(숏 진입), close(청산)")
    print("   - 주문 실행: buy(매수), sell(매도)")
    print("   - 포지션 방향: long(롱), short(숏)")

if __name__ == "__main__":
    test_signal_generation()
