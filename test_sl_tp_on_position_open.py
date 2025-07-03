#!/usr/bin/env python3
"""
포지션 생성 시 손절/익절 자동 설정 확인 테스트
"""
import os
import sys
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.db_manager import DatabaseManager
from src.strategies import MovingAverageCrossover
from src.portfolio_manager import PortfolioManager
from src.order_executor import OrderExecutor
from src.risk_manager import RiskManager
from src.models.trade_signal import TradeSignal
from utils.api import get_positions, get_open_orders

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_stop_loss_take_profit_orders(symbol):
    """손절/익절 주문 확인"""
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("API 키가 설정되지 않았습니다.")
        return
    
    print("\n=== 현재 손절/익절 주문 확인 ===")
    
    # 1. 현재 포지션 확인
    positions = get_positions(api_key, api_secret, symbol)
    if positions:
        print(f"\n현재 포지션:")
        for pos in positions:
            print(f"  - {pos['symbol']}: {pos['side']} {pos['contracts']} @ ${pos['entry_price']:,.2f}")
    else:
        print("\n열린 포지션이 없습니다.")
    
    # 2. 열린 주문 확인
    open_orders = get_open_orders(api_key, api_secret, symbol)
    
    stop_orders = []
    take_profit_orders = []
    
    for order in open_orders:
        order_type = order.get('type', '').lower()
        if 'stop' in order_type and 'profit' not in order_type:
            stop_orders.append(order)
        elif 'take_profit' in order_type or 'profit' in order_type:
            take_profit_orders.append(order)
    
    print(f"\n손절 주문: {len(stop_orders)}개")
    for order in stop_orders:
        print(f"  - {order.get('symbol')}: {order.get('side')} @ ${order.get('stopPrice', 0):,.2f}")
    
    print(f"\n익절 주문: {len(take_profit_orders)}개")
    for order in take_profit_orders:
        print(f"  - {order.get('symbol')}: {order.get('side')} @ ${order.get('stopPrice', 0):,.2f}")
    
    return {
        'positions': positions,
        'stop_orders': stop_orders,
        'take_profit_orders': take_profit_orders
    }

def test_position_creation_with_sl_tp():
    """포지션 생성 시 손절/익절 자동 설정 테스트"""
    print("\n=== 포지션 생성 시 손절/익절 자동 설정 테스트 ===")
    
    # 환경 변수 로드
    load_dotenv()
    
    # DB 매니저 생성
    db_manager = DatabaseManager()
    
    # 필수 컴포넌트 생성
    strategy = MovingAverageCrossover()
    portfolio_manager = PortfolioManager(db_manager=db_manager)
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
    
    print("\n1. TradingAlgorithm 초기화 완료")
    
    # 현재 상태 확인
    current_state = check_stop_loss_take_profit_orders('BTC/USDT')
    
    if current_state['positions']:
        print("\n이미 열린 포지션이 있습니다. 테스트를 종료합니다.")
        return
    
    # 테스트 신호 생성
    print("\n2. 테스트용 Long 신호 생성")
    test_signal = TradeSignal(
        symbol='BTC/USDT',
        direction='long',
        strength=1.0,
        strategy='test',
        timestamp=datetime.now()
    )
    
    print(f"   - 신호 방향: {test_signal.direction}")
    print(f"   - 신호 강도: {test_signal.strength}")
    
    # 사용자 확인
    user_input = input("\n이 신호로 포지션을 생성하시겠습니까? (y/n): ")
    if user_input.lower() != 'y':
        print("테스트를 취소합니다.")
        return
    
    # 신호 실행
    print("\n3. 신호 실행 중...")
    result = trading_algo.execute_signal(test_signal)
    
    if result:
        print("\n✅ 포지션 생성 성공!")
        
        # 잠시 대기 (API 반영 시간)
        print("\n4. API 반영을 위해 3초 대기...")
        time.sleep(3)
        
        # 손절/익절 주문 확인
        print("\n5. 손절/익절 주문 확인")
        final_state = check_stop_loss_take_profit_orders('BTC/USDT')
        
        # DB에서도 확인
        print("\n6. DB 저장 내용 확인")
        latest_position = db_manager.get_open_positions(symbol='BTC/USDT')
        if latest_position:
            pos = latest_position[0]
            print(f"   - 포지션 ID: {pos.get('id')}")
            print(f"   - 손절가: ${pos.get('stop_loss_price', 0):,.2f}")
            print(f"   - 익절가: ${pos.get('take_profit_price', 0):,.2f}")
            print(f"   - 손절 주문 ID: {pos.get('stop_loss_order_id')}")
            print(f"   - 익절 주문 ID: {pos.get('take_profit_order_id')}")
        
        # 결과 분석
        print("\n7. 결과 분석:")
        if final_state['stop_orders'] or final_state['take_profit_orders']:
            print("   ✅ 손절/익절 주문이 자동으로 생성되었습니다!")
        else:
            print("   ❌ 손절/익절 주문이 생성되지 않았습니다.")
            print("   체크포인트:")
            print("   - API 키 설정 확인")
            print("   - 거래소 API 권한 확인")
            print("   - 로그 확인 필요")
    else:
        print("\n❌ 포지션 생성 실패!")

def analyze_trading_algorithm_sl_tp_logic():
    """TradingAlgorithm의 손절/익절 로직 분석"""
    print("\n=== TradingAlgorithm 손절/익절 로직 분석 ===")
    
    # 코드 위치 확인
    print("\n1. 손절/익절 자동 설정 코드 위치:")
    print("   - 파일: src/trading_algorithm.py")
    print("   - 라인: 1000-1065 (execute_signal 메서드 내)")
    
    print("\n2. 실행 조건:")
    print("   - market_type이 'futures'인 경우")
    print("   - risk_assessment에 stop_loss/take_profit 가격이 있는 경우")
    print("   - API 키가 설정된 경우")
    
    print("\n3. 실행 흐름:")
    print("   1) RiskManager가 손절/익절 가격 계산")
    print("   2) execute_order로 포지션 생성")
    print("   3) set_stop_loss_take_profit 함수 호출")
    print("   4) DB에 주문 정보 저장")

if __name__ == "__main__":
    print("손절/익절 자동 설정 통합 테스트")
    print("=" * 50)
    
    # 1. 현재 상태 확인
    check_stop_loss_take_profit_orders('BTC/USDT')
    
    # 2. 로직 분석
    analyze_trading_algorithm_sl_tp_logic()
    
    # 3. 실제 테스트 (선택적)
    user_input = input("\n\n실제 포지션 생성 테스트를 진행하시겠습니까? (y/n): ")
    if user_input.lower() == 'y':
        test_position_creation_with_sl_tp()
    
    print("\n\n테스트 완료!")
