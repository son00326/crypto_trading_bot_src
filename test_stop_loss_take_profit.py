#!/usr/bin/env python3
"""
손절/익절 자동 설정 기능 테스트 스크립트
"""
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.risk_manager import RiskManager
from src.trading_algorithm import TradingAlgorithm
from src.db_manager import DatabaseManager
from utils.api import get_positions, set_stop_loss_take_profit

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_risk_manager_calculations():
    """RiskManager의 손절/익절 가격 계산 테스트"""
    print("\n=== RiskManager 가격 계산 테스트 ===")
    
    # 기본 설정으로 RiskManager 생성
    risk_config = {
        'max_position_size': 0.1,  # 10%
        'stop_loss_pct': 0.02,     # 2%
        'take_profit_pct': 0.04,   # 4%
        'max_leverage': 10,
        'margin_call_threshold': 0.2
    }
    
    risk_manager = RiskManager(risk_config=risk_config)
    
    # 테스트 케이스
    test_cases = [
        {'entry_price': 100000, 'side': 'long'},
        {'entry_price': 100000, 'side': 'short'},
        {'entry_price': 50000, 'side': 'long'},
        {'entry_price': 50000, 'side': 'short'},
    ]
    
    for test in test_cases:
        entry_price = test['entry_price']
        side = test['side']
        
        # 손절가 계산
        stop_loss = risk_manager.calculate_stop_loss_price(entry_price, side)
        
        # 익절가 계산
        take_profit = risk_manager.calculate_take_profit_price(entry_price, side)
        
        print(f"\n{side.upper()} 포지션 (진입가: ${entry_price:,.2f}):")
        print(f"  - 손절가: ${stop_loss:,.2f}")
        print(f"  - 익절가: ${take_profit:,.2f}")
        
        # 검증
        if side == 'long':
            assert stop_loss < entry_price, "Long 포지션의 손절가는 진입가보다 낮아야 함"
            assert take_profit > entry_price, "Long 포지션의 익절가는 진입가보다 높아야 함"
        else:
            assert stop_loss > entry_price, "Short 포지션의 손절가는 진입가보다 높아야 함"
            assert take_profit < entry_price, "Short 포지션의 익절가는 진입가보다 낮아야 함"

def test_live_stop_loss_take_profit():
    """실제 API를 통한 손절/익절 주문 테스트"""
    print("\n=== 실제 손절/익절 주문 테스트 ===")
    
    # 환경 변수 로드
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("API 키가 설정되지 않았습니다.")
        return
    
    # 현재 포지션 확인
    print("\n1. 현재 포지션 확인...")
    positions = get_positions(api_key, api_secret)
    
    if not positions:
        print("열린 포지션이 없습니다.")
        return
    
    # 첫 번째 포지션 선택
    position = positions[0]
    symbol = position['symbol']
    entry_price = float(position['entry_price'])
    side = position['side']
    contracts = float(position['contracts'])
    
    print(f"\n포지션 정보:")
    print(f"  - 심볼: {symbol}")
    print(f"  - 방향: {side}")
    print(f"  - 진입가: ${entry_price:,.2f}")
    print(f"  - 수량: {contracts}")
    
    # RiskManager로 손절/익절 가격 계산
    risk_manager = RiskManager()
    stop_loss_price = risk_manager.calculate_stop_loss_price(entry_price, side)
    take_profit_price = risk_manager.calculate_take_profit_price(entry_price, side)
    
    print(f"\n2. 계산된 손절/익절 가격:")
    print(f"  - 손절가: ${stop_loss_price:,.2f}")
    print(f"  - 익절가: ${take_profit_price:,.2f}")
    
    # 사용자 확인
    user_input = input("\n이 가격으로 손절/익절 주문을 설정하시겠습니까? (y/n): ")
    if user_input.lower() != 'y':
        print("테스트를 취소합니다.")
        return
    
    # 손절/익절 주문 설정
    print("\n3. 손절/익절 주문 설정 중...")
    result = set_stop_loss_take_profit(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        stop_loss=stop_loss_price,
        take_profit=take_profit_price
    )
    
    if result.get('success'):
        print("\n✅ 손절/익절 주문 설정 성공!")
        print(f"메시지: {result.get('message')}")
        
        if result.get('orders'):
            print("\n설정된 주문:")
            for order in result['orders']:
                print(f"  - {order['type']}: ${order['price']:,.2f} (ID: {order['order_id']})")
    else:
        print("\n❌ 손절/익절 주문 설정 실패!")
        print(f"오류: {result.get('message', result.get('error'))}")

def test_auto_position_manager_integration():
    """AutoPositionManager 통합 테스트"""
    print("\n=== AutoPositionManager 통합 테스트 ===")
    
    # 환경 변수 로드
    load_dotenv()
    
    # DB 매니저 생성
    db_manager = DatabaseManager()
    
    # TradingAlgorithm 생성을 위한 필수 요소
    from src.strategies import MovingAverageCrossover
    from src.portfolio_manager import PortfolioManager
    from src.order_executor import OrderExecutor
    from src.auto_position_manager import AutoPositionManager
    
    # 전략 생성
    strategy = MovingAverageCrossover()
    
    # 포트폴리오 매니저 생성
    portfolio_manager = PortfolioManager(db_manager=db_manager)
    
    # 주문 실행기 생성
    order_executor = OrderExecutor()
    
    # TradingAlgorithm 생성
    trading_algo = TradingAlgorithm(
        strategy=strategy,
        portfolio_manager=portfolio_manager,
        db_manager=db_manager,
        order_executor=order_executor,
        symbol='BTC/USDT',
        market_type='futures'
    )
    auto_manager = AutoPositionManager(trading_algo)
    
    print("AutoPositionManager가 생성되었습니다.")
    print("이제 포지션을 모니터링하고 손절/익절 조건을 확인합니다.")
    
    # 현재 포지션 확인
    positions = trading_algo.get_open_positions()
    
    if positions:
        print(f"\n{len(positions)}개의 열린 포지션을 발견했습니다.")
        
        # 첫 번째 포지션에 대해 exit 조건 확인
        position = positions[0]
        print(f"\n포지션 {position['id']} 확인 중...")
        
        # _check_position_exit_conditions 메서드 직접 호출
        exit_needed, exit_type, exit_params = auto_manager._check_position_exit_conditions(position)
        
        if exit_needed:
            print(f"\n⚠️ Exit 조건 충족! 타입: {exit_type}")
            print(f"Exit 파라미터: {exit_params}")
        else:
            print("\n✅ 현재 Exit 조건 없음")
    else:
        print("\n열린 포지션이 없습니다.")

if __name__ == "__main__":
    print("손절/익절 자동 설정 기능 테스트")
    print("=" * 50)
    
    # 1. RiskManager 계산 테스트
    test_risk_manager_calculations()
    
    # 2. 실제 API 테스트 (선택적)
    user_input = input("\n\n실제 API를 통한 테스트를 진행하시겠습니까? (y/n): ")
    if user_input.lower() == 'y':
        test_live_stop_loss_take_profit()
    
    # 3. AutoPositionManager 통합 테스트
    user_input = input("\n\nAutoPositionManager 통합 테스트를 진행하시겠습니까? (y/n): ")
    if user_input.lower() == 'y':
        test_auto_position_manager_integration()
    
    print("\n\n테스트 완료!")
