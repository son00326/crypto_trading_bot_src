#!/usr/bin/env python3
"""레버리지 전체 통합 흐름 테스트"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def test_leverage_flow():
    """레버리지가 전체 시스템에서 올바르게 전달되는지 테스트"""
    
    print("=== 레버리지 통합 플로우 테스트 ===\n")
    
    # 테스트 설정
    test_leverage = 10
    test_symbol = "BTC/USDT"
    test_exchange = "binance"
    test_timeframe = "15m"
    
    print(f"테스트 설정:")
    print(f"- 레버리지: {test_leverage}배")
    print(f"- 심볼: {test_symbol}")
    print(f"- 거래소: {test_exchange}")
    print(f"- 시간프레임: {test_timeframe}")
    print(f"- 마켓 타입: futures\n")
    
    # 1. TradingAlgorithm 초기화
    print("1. TradingAlgorithm 초기화...")
    try:
        algo = TradingAlgorithm(
            exchange_id=test_exchange,
            symbol=test_symbol,
            timeframe=test_timeframe,
            strategy="BollingerBandFuturesStrategy",
            strategy_params={
                'period': 20,
                'std_dev': 2.0,
                'rsi_period': 14
            },
            test_mode=True,  # 테스트 모드
            market_type='futures',
            leverage=test_leverage
        )
        print(f"✓ TradingAlgorithm 초기화 성공")
        print(f"  - algo.leverage: {algo.leverage}")
        print(f"  - algo.market_type: {algo.market_type}")
    except Exception as e:
        print(f"✗ TradingAlgorithm 초기화 실패: {e}")
        return
    
    # 2. Exchange API 확인
    print("\n2. Exchange API 레버리지 확인...")
    try:
        print(f"✓ Exchange API 레버리지: {algo.exchange_api.leverage}")
        print(f"  - market_type: {algo.exchange_api.market_type}")
        print(f"  - exchange_id: {algo.exchange_api.exchange_id}")
    except Exception as e:
        print(f"✗ Exchange API 확인 실패: {e}")
    
    # 3. 전략 레버리지 확인
    print("\n3. 전략 레버리지 확인...")
    try:
        if hasattr(algo.strategy, 'leverage'):
            print(f"✓ 전략 레버리지: {algo.strategy.leverage}")
        else:
            print(f"✗ 전략에 leverage 속성 없음")
    except Exception as e:
        print(f"✗ 전략 확인 실패: {e}")
    
    # 4. 리스크 매니저 확인
    print("\n4. Risk Manager 확인...")
    try:
        if hasattr(algo, 'risk_manager') and algo.risk_manager:
            print(f"✓ Risk Manager 존재")
            if hasattr(algo.risk_manager, 'max_position_size'):
                print(f"  - max_position_size: {algo.risk_manager.max_position_size}")
        else:
            print(f"✗ Risk Manager 없음")
    except Exception as e:
        print(f"✗ Risk Manager 확인 실패: {e}")
    
    # 5. 주문 실행 시뮬레이션
    print("\n5. 주문 실행 시뮬레이션...")
    try:
        # 더미 데이터 생성
        dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
        dummy_data = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(100).cumsum() + 50000,
            'high': np.random.randn(100).cumsum() + 50100,
            'low': np.random.randn(100).cumsum() + 49900,
            'close': np.random.randn(100).cumsum() + 50000,
            'volume': np.random.randint(100, 1000, 100)
        })
        
        # 신호 생성
        signals = algo.strategy.generate_signals(dummy_data)
        print(f"✓ 신호 생성 완료")
        
        # 마지막 신호 확인
        last_signal = signals['signal'].iloc[-1] if 'signal' in signals else 0
        last_position = signals['position'].iloc[-1] if 'position' in signals else 0
        
        print(f"  - 마지막 신호: {last_signal}")
        print(f"  - 마지막 포지션: {last_position}")
        
    except Exception as e:
        print(f"✗ 주문 시뮬레이션 실패: {e}")
    
    # 6. 레버리지 적용 플로우 요약
    print("\n=== 레버리지 적용 플로우 요약 ===")
    print("\n1. UI/CLI 입력:")
    print("   - 웹 UI: 레버리지 입력 → /api/start_bot → bot.leverage 설정")
    print("   - CLI: --leverage 10 → argparse → leverage 파라미터")
    
    print("\n2. TradingAlgorithm 초기화:")
    print("   - TradingAlgorithm(leverage=10)")
    print("   - self.leverage = 10 저장")
    
    print("\n3. Exchange API 초기화:")
    print("   - ExchangeAPI(leverage=10)")
    print("   - self.leverage = 10 저장")
    
    print("\n4. 전략 초기화:")
    print("   - StrategyClass(leverage=10)")
    print("   - 모든 전략이 leverage 파라미터 수신")
    
    print("\n5. 주문 실행:")
    print("   - exchange_api.create_market_buy_order()")
    print("   - params['leverage'] = self.leverage")
    print("   - Binance Futures API에 leverage 전달")
    
    print("\n6. 포지션 크기 계산:")
    print("   - RiskManager가 leverage 고려하여 포지션 크기 결정")
    print("   - 실제 마진 = 포지션 크기 / leverage")
    
    print("\n=== 테스트 완료 ===")
    
    # 추가 검증 사항
    print("\n권장 추가 검증:")
    print("1. 실제 Binance Futures API 호출 시 leverage 파라미터 확인")
    print("2. 포지션 개설 후 실제 적용된 레버리지 확인")
    print("3. 청산 가격 계산 시 레버리지 반영 확인")
    print("4. 리스크 관리 시 레버리지 기반 포지션 크기 제한 확인")

if __name__ == "__main__":
    test_leverage_flow()
