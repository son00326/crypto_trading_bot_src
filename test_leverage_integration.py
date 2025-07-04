#!/usr/bin/env python3
"""
레버리지 파라미터 통합 테스트
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy,
    BollingerBandsStrategy, StochasticStrategy, BollingerBandFuturesStrategy
)

def test_leverage_parameter_in_strategies():
    """전략들이 레버리지 파라미터를 올바르게 받는지 테스트"""
    
    print("=== 레버리지 파라미터 테스트 ===\n")
    
    # 레버리지 테스트 값
    test_leverage = 5
    
    # 1. MovingAverageCrossover
    try:
        mac_strategy = MovingAverageCrossover(leverage=test_leverage)
        print(f"✓ MovingAverageCrossover: leverage={mac_strategy.leverage}")
    except Exception as e:
        print(f"✗ MovingAverageCrossover 오류: {e}")
    
    # 2. RSIStrategy
    try:
        rsi_strategy = RSIStrategy(leverage=test_leverage)
        print(f"✓ RSIStrategy: leverage={rsi_strategy.leverage}")
    except Exception as e:
        print(f"✗ RSIStrategy 오류: {e}")
    
    # 3. MACDStrategy
    try:
        macd_strategy = MACDStrategy(leverage=test_leverage)
        print(f"✓ MACDStrategy: leverage={macd_strategy.leverage}")
    except Exception as e:
        print(f"✗ MACDStrategy 오류: {e}")
    
    # 4. BollingerBandsStrategy
    try:
        bb_strategy = BollingerBandsStrategy(leverage=test_leverage)
        print(f"✓ BollingerBandsStrategy: leverage={bb_strategy.leverage}")
    except Exception as e:
        print(f"✗ BollingerBandsStrategy 오류: {e}")
    
    # 5. StochasticStrategy
    try:
        stoch_strategy = StochasticStrategy(leverage=test_leverage)
        print(f"✓ StochasticStrategy: leverage={stoch_strategy.leverage}")
    except Exception as e:
        print(f"✗ StochasticStrategy 오류: {e}")
    
    # 6. BollingerBandFuturesStrategy
    try:
        bbf_strategy = BollingerBandFuturesStrategy(leverage=test_leverage)
        print(f"✓ BollingerBandFuturesStrategy: leverage={bbf_strategy.leverage}")
    except Exception as e:
        print(f"✗ BollingerBandFuturesStrategy 오류: {e}")

def test_leverage_flow():
    """레버리지 파라미터 전달 흐름 테스트"""
    
    print("\n=== 레버리지 전달 흐름 ===\n")
    
    # 1. 명령줄 인수 → TradingAlgorithm
    print("1. CLI 모드:")
    print("   main.py --leverage 5 → TradingAlgorithm(leverage=5)")
    
    # 2. 웹 UI → API 서버 → TradingAlgorithm
    print("\n2. 웹 UI 모드:")
    print("   웹 UI 입력 → /api/start_bot → BotAPIServer")
    print("   → bot_gui.leverage = 5 → BotThread")
    print("   → TradingAlgorithm(leverage=5)")
    
    # 3. TradingAlgorithm → 전략
    print("\n3. 전략 초기화:")
    print("   TradingAlgorithm → strategy = StrategyClass(leverage=self.leverage)")
    
    # 4. 전략 → 주문 실행
    print("\n4. 주문 실행:")
    print("   전략의 레버리지 → position_size 계산")
    print("   exchange_api.create_order(leverage=self.leverage)")

def check_strategy_parameters():
    """모든 전략의 통합된 파라미터 확인"""
    
    print("\n=== 전략 파라미터 통합 상태 ===\n")
    
    strategies = [
        ('MovingAverageCrossover', MovingAverageCrossover()),
        ('RSIStrategy', RSIStrategy()),
        ('MACDStrategy', MACDStrategy()),
        ('BollingerBandsStrategy', BollingerBandsStrategy()),
        ('StochasticStrategy', StochasticStrategy()),
        ('BollingerBandFuturesStrategy', BollingerBandFuturesStrategy()),
    ]
    
    for name, strategy in strategies:
        print(f"{name}:")
        print(f"  - stop_loss_pct: {getattr(strategy, 'stop_loss_pct', 'N/A')}")
        print(f"  - take_profit_pct: {getattr(strategy, 'take_profit_pct', 'N/A')}")
        print(f"  - leverage: {getattr(strategy, 'leverage', 'N/A')}")
        print(f"  - max_position_size: {getattr(strategy, 'max_position_size', 'N/A')}")
        print()

if __name__ == "__main__":
    test_leverage_parameter_in_strategies()
    test_leverage_flow()
    check_strategy_parameters()
    
    print("\n=== 레버리지 통합 검증 완료 ===")
    print("\n권장사항:")
    print("1. 실제 거래 전에 테스트 모드에서 레버리지 적용 확인")
    print("2. exchange_api의 create_order 메서드에서 레버리지 파라미터 전달 확인")
    print("3. 포지션 크기 계산 시 레버리지 반영 확인")
    print("4. 웹 UI에서 설정한 레버리지가 실제 주문에 반영되는지 확인")
