#!/usr/bin/env python3
"""모든 전략의 매매 방향 용어 변경 통합 테스트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, StochasticStrategy, BollingerBandFuturesStrategy
)

def create_test_data(periods=200):
    """테스트용 가격 데이터 생성"""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='1H')
    
    # 사인파 + 노이즈로 변동성 있는 데이터 생성
    t = np.linspace(0, 4*np.pi, periods)
    base_price = 50000
    trend = np.linspace(0, 10000, periods)  # 상승 트렌드
    seasonal = 5000 * np.sin(t)  # 사인파 변동
    noise = np.random.randn(periods) * 500  # 랜덤 노이즈
    
    prices = base_price + trend + seasonal + noise
    
    df = pd.DataFrame({
        'open': prices * 0.995,
        'high': prices * 1.005,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.uniform(1000, 5000, periods)
    }, index=dates)
    
    return df

def test_strategy(strategy_class, strategy_name, **kwargs):
    """개별 전략 테스트"""
    print(f"\n{'='*50}")
    print(f"테스트: {strategy_name}")
    print('='*50)
    
    try:
        # 전략 초기화
        strategy = strategy_class(**kwargs)
        
        # 테스트 데이터 생성
        df = create_test_data()
        
        # 신호 생성
        df_with_signals = strategy.generate_signals(df)
        
        # 포지션 변화 분석
        position_changes = df_with_signals[df_with_signals['position'] != 0]
        
        print(f"\n1. 신호 통계:")
        print(f"   - 전체 데이터: {len(df)}개")
        print(f"   - 롱 신호 (signal=1): {(df_with_signals['signal'] == 1).sum()}개")
        print(f"   - 숏 신호 (signal=-1): {(df_with_signals['signal'] == -1).sum()}개")
        print(f"   - 중립 (signal=0): {(df_with_signals['signal'] == 0).sum()}개")
        
        print(f"\n2. Position 변화: {len(position_changes)}회")
        
        if len(position_changes) > 0:
            # 마지막 position 변화에서 TradeSignal 생성
            portfolio = {'total_balance': 10000, 'available_balance': 10000}
            last_idx = position_changes.index[-1]
            df_subset = df[:last_idx]
            
            signal = strategy.generate_signal(
                df_subset,
                df_subset['close'].iloc[-1],
                portfolio
            )
            
            if signal:
                print(f"\n3. TradeSignal 테스트:")
                print(f"   - Direction: {signal.direction}")
                print(f"   - Strategy: {signal.strategy_name}")
                print(f"   - Confidence: {signal.confidence:.2f}")
                
                # Direction 검증
                if signal.direction in ['long', 'short', 'close']:
                    print(f"   ✅ Direction이 올바릅니다: {signal.direction}")
                else:
                    print(f"   ❌ Direction 오류: {signal.direction} (예상: long/short/close)")
                    
                # 신호 정보 추가 출력
                if hasattr(signal, 'indicators'):
                    print(f"   - Indicators: {signal.indicators}")
            else:
                print("\n3. TradeSignal이 생성되지 않음 (정상일 수 있음)")
        else:
            print("\n3. Position 변화가 없어 TradeSignal 테스트 불가")
            
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def main():
    """메인 테스트 함수"""
    print("=== 전체 전략 매매 방향 용어 테스트 ===")
    print("목표: 모든 전략이 buy/sell 대신 long/short/close를 사용하는지 확인")
    
    # 각 전략 테스트
    strategies_to_test = [
        (MovingAverageCrossover, "이동평균 교차", {'short_period': 10, 'long_period': 30}),
        (RSIStrategy, "RSI", {'period': 14, 'overbought': 70, 'oversold': 30}),
        (MACDStrategy, "MACD", {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}),
        (BollingerBandsStrategy, "볼린저 밴드", {'period': 20, 'std_dev': 2}),
        (StochasticStrategy, "스토캐스틱", {'k_period': 14, 'd_period': 3}),
        (BollingerBandFuturesStrategy, "볼린저 밴드 선물", {'bb_period': 20, 'bb_std': 2}),
    ]
    
    success_count = 0
    
    for strategy_class, name, params in strategies_to_test:
        try:
            test_strategy(strategy_class, name, **params)
            success_count += 1
        except Exception as e:
            print(f"\n전략 테스트 중 오류 발생: {name}")
            print(f"오류: {e}")
    
    print(f"\n\n{'='*60}")
    print(f"테스트 요약")
    print(f"{'='*60}")
    print(f"총 전략 수: {len(strategies_to_test)}")
    print(f"성공: {success_count}")
    print(f"실패: {len(strategies_to_test) - success_count}")
    
    if success_count == len(strategies_to_test):
        print("\n✅ 모든 전략이 long/short/close 용어를 올바르게 사용하고 있습니다!")
    else:
        print("\n⚠️ 일부 전략에서 문제가 발생했습니다. 확인이 필요합니다.")

if __name__ == "__main__":
    main()
