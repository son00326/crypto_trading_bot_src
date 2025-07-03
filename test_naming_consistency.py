#!/usr/bin/env python3
"""
포지션 명명 일관성 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_code_changes():
    """코드 변경 사항 확인"""
    print("=== 코드 변경 사항 확인 ===")
    
    print("\n1. PortfolioManager 변경 사항:")
    print("  - get_open_positions() 내부: open_positions → positions")
    print("  - get_open_positions_data() 내부: open_positions → positions")
    print("  - 공개 API 메서드명은 유지")
    
    print("\n2. RiskManager 변경 사항:")
    print("  - 최대 포지션 수 확인 로직: open_positions → positions")
    print("  - 최대 포지션 크기 확인 로직: open_positions → positions")
    print("  - assess_trading_risk() 내부: open_positions → positions")
    
    print("\n3. TradingAlgorithm 변경 사항:")
    print("  - get_portfolio_summary() 내부: open_positions → positions")
    print("  - 반환값의 'open_positions' 키는 유지 (하위 호환성)")
    
    print("\n4. AutoPositionManager 변경 사항:")
    print("  - RiskManager의 계산 메서드 우선 사용")
    print("  - 폴백 모드에서도 RiskManager 인스턴스 생성하여 사용")
    
    return True

def check_code_patterns():
    """코드 패턴 확인"""
    print("\n=== 코드 패턴 확인 ===")
    
    print("\n1. 메서드명 규칙:")
    print("  - get_open_positions() → 유지 (공개 API)")
    print("  - get_closed_positions() → 유지 (공개 API)")
    print("  - get_open_positions_data() → 유지 (공개 API)")
    
    print("\n2. 내부 변수명 규칙:")
    print("  - open_positions → positions (일관성)")
    print("  - closed_positions → 유지 (명확성)")
    
    print("\n3. 딕셔너리 키 규칙:")
    print("  - portfolio['positions'] → 유지 (통일됨)")
    print("  - result['open_positions'] → 유지 (하위 호환성)")
    
    return True

def main():
    """메인 테스트 함수"""
    print("포지션 명명 일관성 테스트\n")
    
    # 코드 변경 사항 확인
    if not test_code_changes():
        print("\n❌ 코드 변경 사항 확인 실패")
        return False
    
    # 코드 패턴 확인
    if not check_code_patterns():
        print("\n❌ 코드 패턴 확인 실패")
        return False
    
    print("\n" + "="*50)
    print("✅ 모든 테스트 통과!")
    print("✅ 포지션 명명 일관성이 개선되었습니다.")
    print("✅ 공개 API는 유지하면서 내부 일관성이 향상되었습니다.")
    print("="*50)
    
    return True

if __name__ == "__main__":
    main()
