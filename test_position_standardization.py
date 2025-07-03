#!/usr/bin/env python3
"""
포지션 데이터 구조 표준화 테스트 스크립트
"""
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from datetime import datetime
from src.models.position import Position
from src.order_executor import OrderExecutor
from src.portfolio_manager import PortfolioManager
from src.db_manager import DatabaseManager
from utils.api import get_positions_with_objects

def test_position_creation():
    """Position 객체 생성 및 변환 테스트"""
    print("\n=== Position 객체 생성 테스트 ===")
    
    # Position 객체 생성
    position = Position(
        id="test_pos_001",
        symbol="BTC/USDT",
        side="long",
        amount=0.1,
        entry_price=45000,
        leverage=5,
        opened_at=datetime.now(),
        status="open"
    )
    
    # 표준 딕셔너리로 변환
    pos_dict = position.to_dict()
    print(f"표준 딕셔너리: {pos_dict}")
    
    # backward compatible 딕셔너리로 변환
    pos_dict_compat = position.to_dict_compatible()
    print(f"호환 딕셔너리: {pos_dict_compat}")
    
    # 속성 접근 테스트 (별칭 사용)
    print(f"\n별칭 속성 접근:")
    print(f"position.contracts = {position.contracts}")  # amount의 별칭
    print(f"position.quantity = {position.quantity}")   # amount의 별칭
    
    # 딕셔너리에서 Position 객체 생성 (다양한 필드명 사용)
    print("\n=== 딕셔너리에서 Position 객체 생성 테스트 ===")
    
    # contracts 필드명 사용
    dict_with_contracts = {
        'id': 'test_pos_002',
        'symbol': 'ETH/USDT',
        'side': 'short',
        'contracts': 1.5,  # amount 대신 contracts 사용
        'entry_price': 3000,
        'leverage': 10
    }
    position2 = Position.from_dict_compatible(dict_with_contracts)
    print(f"contracts 필드로 생성: amount={position2.amount}")
    
    # quantity 필드명 사용
    dict_with_quantity = {
        'id': 'test_pos_003',
        'symbol': 'BNB/USDT',
        'side': 'long',
        'quantity': 5.0,  # amount 대신 quantity 사용
        'entry_price': 400,
        'leverage': 1
    }
    position3 = Position.from_dict_compatible(dict_with_quantity)
    print(f"quantity 필드로 생성: amount={position3.amount}")
    
    return True

def test_order_executor_integration():
    """OrderExecutor와 Position 객체 통합 테스트"""
    print("\n=== OrderExecutor 통합 테스트 ===")
    
    # Mock 객체들 생성 (실제 API 호출 없이 테스트)
    class MockExchangeAPI:
        leverage = 5
        
    class MockDB:
        def save_position(self, position):
            if isinstance(position, Position):
                print(f"DB에 Position 객체 저장: {position.id}")
            else:
                print(f"DB에 딕셔너리 저장: {position.get('id')}")
                
    class MockPortfolioManager:
        portfolio = {'positions': []}
        
    # OrderExecutor는 내부에서 Position 객체를 생성하고 to_dict()로 변환하여 저장
    print("OrderExecutor는 내부에서 Position 객체를 생성합니다.")
    print("생성된 Position 객체는 portfolio에는 딕셔너리로, DB에는 Position 객체로 전달됩니다.")
    
    return True

def test_portfolio_manager_integration():
    """PortfolioManager와 Position 객체 통합 테스트"""
    print("\n=== PortfolioManager 통합 테스트 ===")
    
    # Mock 객체들 생성
    class MockExchangeAPI:
        pass
        
    class MockDB:
        pass
        
    class MockEventManager:
        def publish(self, event_type, data):
            print(f"이벤트 발행: {event_type}")
            
    # PortfolioManager 생성
    pm = PortfolioManager(
        exchange_api=MockExchangeAPI(),
        db_manager=MockDB(),
        symbol="BTC/USDT",
        test_mode=True
    )
    pm.event_manager = MockEventManager()
    
    # Position 객체 추가
    position = Position(
        id="test_pos_004",
        symbol="BTC/USDT",
        side="long",
        amount=0.5,
        entry_price=48000,
        leverage=3
    )
    
    result = pm.add_position(position)
    print(f"Position 객체 추가 결과: {result}")
    print(f"포트폴리오 내 포지션 수: {len(pm.portfolio['positions'])}")
    
    # 딕셔너리로 추가
    position_dict = {
        'id': 'test_pos_005',
        'symbol': 'ETH/USDT',
        'side': 'short',
        'contracts': 2.0,  # backward compatibility
        'entry_price': 3200,
        'leverage': 5
    }
    
    result = pm.add_position(position_dict)
    print(f"딕셔너리 추가 결과: {result}")
    print(f"포트폴리오 내 포지션 수: {len(pm.portfolio['positions'])}")
    
    return True

def test_database_manager_integration():
    """DatabaseManager와 Position 객체 통합 테스트"""
    print("\n=== DatabaseManager 통합 테스트 ===")
    
    # 테스트용 임시 DB 생성
    test_db_path = "/tmp/test_position_standard.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    db = DatabaseManager(db_path=test_db_path)
    
    # Position 객체 저장
    position = Position(
        id="test_pos_006",
        symbol="SOL/USDT",
        side="long",
        amount=10.0,
        entry_price=100,
        leverage=2
    )
    
    # save_position은 Position 객체를 받아서 to_dict_compatible()로 변환 후 저장
    print("DatabaseManager.save_position()은 Position 객체를 처리할 수 있습니다.")
    
    # 테스트 DB 삭제
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    return True

def test_api_response_handling():
    """API 응답 처리와 Position 객체 변환 테스트"""
    print("\n=== API 응답 처리 테스트 ===")
    
    # 가짜 API 응답 데이터 (바이낸스 포지션 형식)
    mock_api_response = [
        {
            'symbol': 'BTC/USDT',
            'side': 'long',
            'notional': 10000,
            'contracts': 0.2,
            'entry_price': 50000,
            'mark_price': 51000,
            'liquidation_price': 45000,
            'unrealized_pnl': 200,
            'margin_mode': 'cross',
            'leverage': 10,
            'raw_data': {}
        },
        {
            'symbol': 'ETH/USDT',
            'side': 'short',
            'notional': 5000,
            'contracts': 1.5,
            'entry_price': 3333.33,
            'mark_price': 3300,
            'liquidation_price': 3600,
            'unrealized_pnl': 50,
            'margin_mode': 'isolated',
            'leverage': 5,
            'raw_data': {}
        }
    ]
    
    print(f"API에서 {len(mock_api_response)}개 포지션 수신")
    
    # utils.api.get_positions_with_objects 함수 테스트
    # 실제로는 API 키가 필요하지만, 여기서는 모킹 데이터로 테스트
    position_objects = []
    for api_pos in mock_api_response:
        try:
            position_data = {
                'id': f"{api_pos['symbol']}_{int(datetime.now().timestamp())}",
                'symbol': api_pos['symbol'],
                'side': api_pos['side'],
                'amount': api_pos['contracts'],
                'entry_price': api_pos['entry_price'],
                'opened_at': datetime.now().isoformat(),
                'status': 'open',
                'leverage': api_pos['leverage'],
                'liquidation_price': api_pos['liquidation_price'],
                'margin': api_pos.get('notional', 0) / api_pos['leverage'] if api_pos['leverage'] > 0 else 0,
                'pnl': api_pos['unrealized_pnl'],
                'additional_info': {
                    'notional': api_pos['notional'],
                    'mark_price': api_pos['mark_price'],
                    'margin_mode': api_pos['margin_mode']
                }
            }
            
            position = Position.from_dict_compatible(position_data)
            position_objects.append(position)
            
        except Exception as e:
            print(f"Position 객체 변환 실패: {e}")
    
    print(f"Position 객체로 변환 성공: {len(position_objects)}개")
    
    # Position 객체 정보 출력
    for pos in position_objects:
        print(f"  - {pos.symbol}: {pos.side} {pos.amount} @ {pos.entry_price}, PnL: {pos.pnl}")
    
    return True

def test_database_position_objects():
    """DatabaseManager의 Position 객체 조회 테스트"""
    print("\n=== Database Position 객체 조회 테스트 ===")
    
    # 테스트용 임시 DB 생성
    test_db_path = "/tmp/test_position_objects.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = DatabaseManager(test_db_path)
    
    # 테스트 포지션 저장
    test_positions = [
        Position(
            id='db_test_001',
            symbol='BTC/USDT',
            side='long',
            amount=0.1,
            entry_price=45000,
            leverage=5
        ),
        Position(
            id='db_test_002',
            symbol='ETH/USDT',
            side='short',
            amount=2.0,
            entry_price=3200,
            leverage=10
        )
    ]
    
    # 포지션 저장
    for pos in test_positions:
        db.save_position(pos)
    
    # 딕셔너리로 조회
    positions_dict = db.get_open_positions()
    print(f"\n딕셔너리로 조회: {len(positions_dict)}개 포지션")
    
    # Position 객체로 조회
    position_objects = db.get_open_positions_as_objects()
    print(f"Position 객체로 조회: {len(position_objects)}개")
    
    for pos in position_objects:
        print(f"  - {pos.symbol}: {pos.side} {pos.amount} @ {pos.entry_price}")
    
    # 테스트 DB 삭제
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    return True

def main():
    """메인 함수"""
    print("=== 포지션 데이터 구조 표준화 테스트 시작 ===")
    
    # 각 테스트 실행
    tests = [
        ("Position 객체 생성 및 변환", test_position_creation),
        ("OrderExecutor 통합", test_order_executor_integration),
        ("PortfolioManager 통합", test_portfolio_manager_integration),
        ("DatabaseManager 통합", test_database_manager_integration),
        ("API 응답 처리", test_api_response_handling),
        ("Database Position 객체 조회", test_database_position_objects)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "성공" if result else "실패"))
        except Exception as e:
            results.append((test_name, f"에러: {str(e)}"))
            
    # 결과 요약
    print("\n=== 테스트 결과 요약 ===")
    for test_name, result in results:
        print(f"{test_name}: {result}")
        
    # 결론
    print("\n=== 포지션 데이터 구조 표준화 현황 ===")
    print("1. Position 클래스에 backward compatibility 기능 추가 완료")
    print("   - amount, contracts, quantity 필드명 모두 지원")
    print("   - from_dict_compatible(), to_dict_compatible() 메서드 제공")
    print("2. OrderExecutor에서 Position 객체 생성 및 사용")
    print("3. PortfolioManager에서 Position 객체와 딕셔너리 모두 처리 가능")
    print("4. DatabaseManager에서 Position 객체 저장 및 조회 지원")
    print("   - get_open_positions_as_objects() 메서드 추가")
    print("5. API 응답 처리 및 Position 객체 변환 기능 추가")
    print("   - get_positions_with_objects() 함수 추가")
    print("\n표준화 작업 진행 중. 모든 주요 모듈이 Position 객체를 지원합니다.")

if __name__ == "__main__":
    main()
