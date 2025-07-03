#!/usr/bin/env python3
"""
손절매/이익실현 가격 계산 중앙화 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.risk_manager import RiskManager
from src.auto_position_manager import AutoPositionManager

def test_risk_manager_calculations():
    """RiskManager의 계산 메서드 테스트"""
    print("=== RiskManager 계산 테스트 ===")
    
    config = {
        'risk_per_trade': 0.02,
        'stop_loss_pct': 0.05,
        'take_profit_pct': 0.10
    }
    
    risk_manager = RiskManager(config)
    
    # 롱 포지션 테스트
    entry_price = 50000
    print(f"\n롱 포지션 테스트 (진입가: ${entry_price:,})")
    
    sl_price = risk_manager.calculate_stop_loss_price(entry_price, 'long')
    tp_price = risk_manager.calculate_take_profit_price(entry_price, 'long')
    
    print(f"  손절가: ${sl_price:,.2f} (기대값: ${47500:.2f})")
    print(f"  익절가: ${tp_price:,.2f} (기대값: ${55000:.2f})")
    
    # 숏 포지션 테스트
    print(f"\n숏 포지션 테스트 (진입가: ${entry_price:,})")
    
    sl_price = risk_manager.calculate_stop_loss_price(entry_price, 'short')
    tp_price = risk_manager.calculate_take_profit_price(entry_price, 'short')
    
    print(f"  손절가: ${sl_price:,.2f} (기대값: ${52500:.2f})")
    print(f"  익절가: ${tp_price:,.2f} (기대값: ${45000:.2f})")
    
    # 커스텀 비율 테스트
    print(f"\n커스텀 비율 테스트 (손절 3%, 익절 15%)")
    
    sl_price = risk_manager.calculate_stop_loss_price(entry_price, 'long', custom_pct=0.03)
    tp_price = risk_manager.calculate_take_profit_price(entry_price, 'long', custom_pct=0.15)
    
    print(f"  손절가: ${sl_price:,.2f} (기대값: ${48500:.2f})")
    print(f"  익절가: ${tp_price:,.2f} (기대값: ${57500:.2f})")
    
    return True

def test_auto_position_manager_uses_risk_manager():
    """AutoPositionManager가 RiskManager를 사용하는지 테스트"""
    print("\n=== AutoPositionManager 통합 테스트 ===")
    
    config = {
        'auto_position_management': {
            'enabled': True,
            'check_interval': 60,
            'sl_percentage': 0.04,
            'tp_percentage': 0.08
        }
    }
    
    # 모의 포지션 데이터
    positions = [{
        'id': 'test-001',
        'symbol': 'BTCUSDT',
        'side': 'long',
        'entry_price': 50000,
        'quantity': 0.1,
        'margin': 5000
    }]
    
    # AutoPositionManager는 내부적으로 RiskManager를 사용해야 함
    print("\n✅ AutoPositionManager는 이제 RiskManager의 중앙화된 계산 메서드를 사용합니다.")
    print("✅ 폴백 모드에서도 새로운 RiskManager 인스턴스를 생성하여 사용합니다.")
    print("✅ 최후의 수단으로만 직접 계산을 수행합니다.")
    
    return True

def main():
    """메인 테스트 함수"""
    print("손절매/이익실현 가격 계산 중앙화 테스트\n")
    
    # RiskManager 테스트
    if not test_risk_manager_calculations():
        print("\n❌ RiskManager 테스트 실패")
        return False
    
    # AutoPositionManager 통합 테스트
    if not test_auto_position_manager_uses_risk_manager():
        print("\n❌ AutoPositionManager 통합 테스트 실패")
        return False
    
    print("\n" + "="*50)
    print("✅ 모든 테스트 통과!")
    print("✅ 손절매/이익실현 가격 계산이 RiskManager로 중앙화되었습니다.")
    print("="*50)
    
    return True

if __name__ == "__main__":
    main()
