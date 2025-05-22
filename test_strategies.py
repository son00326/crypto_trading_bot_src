#!/usr/bin/env python3
"""
트레이딩 전략 테스트 스크립트
"""
import pandas as pd
import numpy as np
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, CombinedStrategy
)

def create_test_data():
    """테스트용 OHLCV 데이터 생성"""
    print("테스트 데이터 생성...")
    
    # 날짜 인덱스 생성
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    
    # 기본 가격 데이터 생성
    np.random.seed(42)  # 재현성을 위한 시드 설정
    
    # 시작 가격
    start_price = 50000
    
    # 가격 변동 시뮬레이션
    returns = np.random.normal(0, 0.02, 100)  # 평균 0, 표준편차 2%의 일일 수익률
    prices = start_price * np.exp(np.cumsum(returns))  # 누적 수익률을 지수 함수에 적용
    
    # OHLCV 데이터프레임 생성
    data = pd.DataFrame({
        'open': prices * np.random.uniform(0.99, 1.0, 100),
        'high': prices * np.random.uniform(1.0, 1.05, 100),
        'low': prices * np.random.uniform(0.95, 1.0, 100),
        'close': prices,
        'volume': np.random.randint(100, 10000, 100) * prices / 10000
    }, index=dates)
    
    # 일부 데이터 출력
    print(f"생성된 데이터 (처음 5행):\n{data.head()}")
    
    return data

def test_moving_average_crossover():
    """이동평균 교차 전략 테스트"""
    print("\n1. 이동평균 교차 전략 테스트")
    
    # 테스트 데이터
    data = create_test_data()
    
    # 전략 인스턴스 생성
    ma_strategy = MovingAverageCrossover(short_period=5, long_period=20, ma_type='ema')
    print(f"전략 생성: {ma_strategy.name}")
    
    # 신호 생성
    try:
        signals = ma_strategy.generate_signals(data)
        
        # 포지션 계산 (필요한 경우)
        try:
            if hasattr(ma_strategy, 'calculate_positions') and callable(getattr(ma_strategy, 'calculate_positions')):
                signals = ma_strategy.calculate_positions(signals)
                print("포지션 계산 완료")
        except Exception as e:
            print(f"포지션 계산 중 오류: {e}")
        
        # 결과 요약
        buy_signals = signals[signals['signal'] == 1].shape[0]
        sell_signals = signals[signals['signal'] == -1].shape[0]
        neutral_signals = signals[signals['signal'] == 0].shape[0]
        
        print(f"생성된 신호: 매수({buy_signals}), 매도({sell_signals}), 중립({neutral_signals})")
        
        # 신호 컬럼만 표시
        columns_to_show = ['close', 'signal']
        if 'position' in signals.columns:
            columns_to_show.append('position')
            
        print(f"첫 5개 신호:\n{signals[columns_to_show].head()}")
        print(f"마지막 5개 신호:\n{signals[columns_to_show].tail()}")
        
        return True
    except Exception as e:
        print(f"이동평균 교차 전략 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rsi_strategy():
    """RSI 전략 테스트"""
    print("\n2. RSI 전략 테스트")
    
    # 테스트 데이터
    data = create_test_data()
    
    # 전략 인스턴스 생성
    rsi_strategy = RSIStrategy(period=14, overbought=70, oversold=30)
    print(f"전략 생성: {rsi_strategy.name}")
    
    # 신호 생성
    try:
        signals = rsi_strategy.generate_signals(data)
        
        # 포지션 계산 (필요한 경우)
        try:
            if hasattr(rsi_strategy, 'calculate_positions') and callable(getattr(rsi_strategy, 'calculate_positions')):
                signals = rsi_strategy.calculate_positions(signals)
                print("포지션 계산 완료")
        except Exception as e:
            print(f"포지션 계산 중 오류: {e}")
            
        # 결과 요약
        buy_signals = signals[signals['signal'] == 1].shape[0]
        sell_signals = signals[signals['signal'] == -1].shape[0]
        neutral_signals = signals[signals['signal'] == 0].shape[0]
        
        print(f"생성된 신호: 매수({buy_signals}), 매도({sell_signals}), 중립({neutral_signals})")
        
        # 신호 컬럼만 표시
        columns_to_show = ['close', 'signal']
        if 'position' in signals.columns:
            columns_to_show.append('position')
        if 'rsi' in signals.columns:
            columns_to_show.append('rsi')
            
        print(f"첫 5개 신호:\n{signals[columns_to_show].head()}")
        print(f"마지막 5개 신호:\n{signals[columns_to_show].tail()}")
        
        return True
    except Exception as e:
        print(f"RSI 전략 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_combined_strategy():
    """복합 전략 테스트"""
    print("\n3. 복합 전략 테스트")
    
    # 테스트 데이터
    data = create_test_data()
    
    # 개별 전략 인스턴스 생성
    ma_strategy = MovingAverageCrossover(short_period=5, long_period=20, ma_type='ema')
    rsi_strategy = RSIStrategy(period=14, overbought=70, oversold=30)
    
    # 복합 전략 생성
    combined_strategy = CombinedStrategy([ma_strategy, rsi_strategy])
    print(f"전략 생성: {combined_strategy.name}")
    
    # 신호 생성
    try:
        signals = combined_strategy.generate_signals(data)
        
        # 포지션 계산 (필요한 경우)
        try:
            if hasattr(combined_strategy, 'calculate_positions') and callable(getattr(combined_strategy, 'calculate_positions')):
                signals = combined_strategy.calculate_positions(signals)
                print("포지션 계산 완료")
        except Exception as e:
            print(f"포지션 계산 중 오류: {e}")
        
        # 결과 요약
        buy_signals = signals[signals['signal'] == 1].shape[0]
        sell_signals = signals[signals['signal'] == -1].shape[0]
        neutral_signals = signals[signals['signal'] == 0].shape[0]
        
        print(f"생성된 신호: 매수({buy_signals}), 매도({sell_signals}), 중립({neutral_signals})")
        
        # 신호 컬럼만 표시
        columns_to_show = ['close', 'signal']
        if 'position' in signals.columns:
            columns_to_show.append('position')
            
        print(f"첫 5개 신호:\n{signals[columns_to_show].head()}")
        print(f"마지막 5개 신호:\n{signals[columns_to_show].tail()}")
        
        return True
    except Exception as e:
        print(f"복합 전략 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== 트레이딩 전략 테스트 시작 ===")
    print("주의: 이 테스트는 생성된 신호를 확인하는 것이 목적입니다.")
    print("position 열이 없는 경우에도 signal 열만 확인하여 테스트를 진행합니다.")
    
    # 개별 전략 테스트
    ma_success = test_moving_average_crossover()
    rsi_success = test_rsi_strategy()
    combined_success = test_combined_strategy()
    
    # 테스트 결과 요약
    print("\n=== 트레이딩 전략 테스트 결과 ===")
    print(f"이동평균 교차 전략: {'성공' if ma_success else '실패'}")
    print(f"RSI 전략: {'성공' if rsi_success else '실패'}")
    print(f"복합 전략: {'성공' if combined_success else '실패'}")
    
    print("\n=== 트레이딩 전략 테스트 완료 ===")
