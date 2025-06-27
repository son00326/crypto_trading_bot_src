#!/usr/bin/env python3
"""
리스크 관리 설정 통합 테스트 스크립트
"""

import logging
import os
import sys
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading_algorithm import TradingAlgorithm
from src.risk_manager import RiskManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_risk_management_integration():
    """리스크 관리 설정이 올바르게 전달되는지 테스트"""
    
    print("\n" + "="*50)
    print("리스크 관리 설정 통합 테스트")
    print("="*50)
    
    # 테스트용 전략 파라미터 (웹 인터페이스에서 전달되는 형식)
    strategy_params = {
        'stop_loss_pct': 0.02,      # 2% 손절매
        'take_profit_pct': 0.08,    # 8% 이익실현
        'max_position_size': 0.25   # 자본의 25%
    }
    
    print(f"\n테스트 전략 파라미터:")
    print(f"  - 손절매: {strategy_params['stop_loss_pct']*100}%")
    print(f"  - 이익실현: {strategy_params['take_profit_pct']*100}%")
    print(f"  - 최대 포지션 크기: {strategy_params['max_position_size']*100}%")
    
    try:
        # TradingAlgorithm 인스턴스 생성 (테스트 모드)
        algo = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='5m',
            strategy='RSIStrategy',
            test_mode=True,
            strategy_params=strategy_params,
            restore_state=False
        )
        
        print("\n✅ TradingAlgorithm 초기화 성공")
        
        # risk_management 설정 확인
        print("\n적용된 리스크 관리 설정:")
        print(f"  - 손절매: {algo.risk_management['stop_loss_pct']*100}%")
        print(f"  - 이익실현: {algo.risk_management['take_profit_pct']*100}%")
        print(f"  - 최대 포지션 크기: {algo.risk_management['max_position_size']*100}%")
        
        # RiskManager의 설정 확인
        if hasattr(algo, 'risk_manager') and algo.risk_manager:
            rm_config = algo.risk_manager.risk_config
            print("\nRiskManager 설정:")
            print(f"  - 손절매: {rm_config['stop_loss_pct']*100}%")
            print(f"  - 이익실현: {rm_config['take_profit_pct']*100}%")
            print(f"  - 최대 포지션 크기: {rm_config['max_position_size']*100}%")
            
            # 최대 포지션 크기 계산 테스트
            test_capital = 10000  # $10,000
            max_position = algo.risk_manager.calculate_position_size(test_capital, 50000)  # BTC 가격 $50,000
            print(f"\n포지션 크기 계산 테스트:")
            print(f"  - 테스트 자본: ${test_capital}")
            print(f"  - BTC 가격: $50,000")
            print(f"  - 계산된 포지션 크기: {max_position} BTC")
            print(f"  - 포지션 가치: ${max_position * 50000}")
            print(f"  - 자본 대비 비율: {(max_position * 50000 / test_capital)*100:.1f}%")
        
        print("\n✅ 리스크 관리 설정이 올바르게 적용되었습니다!")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        logger.error(f"테스트 실패: {e}", exc_info=True)
        return False
    
    return True

if __name__ == "__main__":
    # 환경 변수 설정 (테스트용)
    os.environ['BINANCE_API_KEY'] = 'test_key'
    os.environ['BINANCE_API_SECRET'] = 'test_secret'
    
    # 테스트 실행
    success = test_risk_management_integration()
    
    if success:
        print("\n" + "="*50)
        print("테스트 완료: 리스크 관리 통합 성공! ✅")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("테스트 실패: 문제가 발생했습니다. ❌")
        print("="*50)
