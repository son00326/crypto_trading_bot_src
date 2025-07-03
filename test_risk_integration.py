#!/usr/bin/env python3
"""
리스크 관리 통합 테스트 스크립트
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# src 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategies import MovingAverageCrossover, RSIStrategy
from src.models import TradeSignal
from src.risk_manager import RiskManager

def create_sample_data(days=30):
    """샘플 OHLCV 데이터 생성"""
    dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
    
    # 가격 시뮬레이션
    np.random.seed(42)
    base_price = 50000
    returns = np.random.normal(0.0002, 0.01, len(dates))
    prices = base_price * (1 + returns).cumprod()
    
    # OHLCV 데이터프레임 생성
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.normal(0, 0.001, len(dates))),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.003, len(dates)))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.003, len(dates)))),
        'close': prices,
        'volume': np.random.uniform(100, 1000, len(dates))
    })
    
    df.set_index('timestamp', inplace=True)
    return df

def test_strategy_with_risk():
    """전략과 리스크 관리 통합 테스트"""
    print("=== 리스크 관리 통합 테스트 시작 ===\n")
    
    # 1. 샘플 데이터 생성
    df = create_sample_data(days=30)
    print(f"샘플 데이터 생성 완료: {len(df)}개 캔들\n")
    
    # 2. 전략 초기화 (리스크 파라미터 포함)
    strategy = MovingAverageCrossover(
        short_period=10,
        long_period=20,
        stop_loss_pct=2.0,  # 퍼센트 단위
        take_profit_pct=5.0,  # 퍼센트 단위
        max_position_size=0.1
    )
    print(f"전략 초기화: {strategy.name}")
    print(f"- 손절: {strategy.stop_loss_pct}%")
    print(f"- 익절: {strategy.take_profit_pct}%")
    print(f"- 최대 포지션: {strategy.max_position_size*100}%\n")
    
    # 3. 신호 생성
    df_with_signals = strategy.generate_signals(df)
    current_price = df['close'].iloc[-1]
    
    # 4. TradeSignal 객체 생성
    signal = strategy.generate_signal(
        market_data=df_with_signals,
        current_price=current_price,
        portfolio={'quote_balance': 10000}
    )
    
    if signal:
        print(f"거래 신호 생성됨:")
        print(f"- 방향: {signal.direction}")
        print(f"- 신뢰도: {signal.confidence:.2f}")
        print(f"- 제안 수량: {signal.suggested_quantity:.8f if signal.suggested_quantity else 'None'}\n")
        
        # 5. 리스크 관리자 초기화
        risk_config = {
            'max_position_size': 0.1,
            'risk_per_trade': 0.02,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.05,
            'min_signal_confidence': 0.3
        }
        risk_manager = RiskManager(risk_config)
        
        # 6. 리스크 평가
        portfolio_status = {
            'quote_balance': 10000,
            'open_positions': []
        }
        
        risk_assessment = risk_manager.assess_risk(
            signal=signal,
            portfolio_status=portfolio_status,
            current_price=current_price,
            leverage=1,
            market_type='spot'
        )
        
        print(f"리스크 평가 결과:")
        print(f"- 실행 가능: {risk_assessment['should_execute']}")
        print(f"- 최종 포지션 크기: {risk_assessment['position_size']:.8f}")
        print(f"- 손절가: {risk_assessment['stop_loss']:.2f}")
        print(f"- 익절가: {risk_assessment['take_profit']:.2f}")
        
        if not risk_assessment['should_execute']:
            print(f"- 거부 사유: {risk_assessment['reason']}")
            
        # 7. 비교 분석
        if signal.suggested_quantity and risk_assessment['position_size'] > 0:
            adjustment_ratio = risk_assessment['position_size'] / signal.suggested_quantity
            print(f"\n포지션 크기 조정 비율: {adjustment_ratio:.2%}")
            if adjustment_ratio < 1:
                print("(리스크 관리자가 전략 제안보다 보수적으로 조정)")
    else:
        print("거래 신호 없음 (HOLD)")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_strategy_with_risk()
