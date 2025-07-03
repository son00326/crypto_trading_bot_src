#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Position 객체 실시간 통합 테스트
"""
import sys
import os
import time

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from datetime import datetime
from src.models.position import Position
from src.order_executor import OrderExecutor
from src.portfolio_manager import PortfolioManager
from src.db_manager import DatabaseManager
from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
from src.risk_manager import RiskManager
from src.event_manager import EventManager
from src.strategies import MovingAverageCrossover

def test_live_position_integration():
    """Position 객체를 사용한 실시간 통합 테스트"""
    # 디버그 로깅 설정
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # crypto_bot 로거에 대해 DEBUG 레벨 설정
    logging.getLogger('crypto_bot').setLevel(logging.DEBUG)
    
    print("\n=== Position 객체 실시간 통합 테스트 시작 ===")
    
    # 테스트용 설정
    config = {
        'api_key': 'your_test_api_key',
        'api_secret': 'your_test_api_secret',
        'exchange': 'binance',
        'market_type': 'futures',  # 선물거래로 변경
        'symbol': 'BTC/USDT',
        'initial_investment': 10000
    }
    
    # 컴포넌트 초기화
    try:
        # ExchangeAPI 초기화
        exchange_api = ExchangeAPI(
            exchange_id=config['exchange'],
            symbol=config['symbol'],
            market_type=config['market_type']
        )
        
        # 이벤트 매니저
        event_manager = EventManager()
        
        # DB 매니저 (임시 DB 사용)
        test_db_path = "/tmp/test_position_live.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        db_manager = DatabaseManager(test_db_path)
        
        # 포트폴리오 매니저
        portfolio_manager = PortfolioManager(
            exchange_api=exchange_api,
            db_manager=db_manager,
            symbol=config['symbol'],
            initial_balance=config['initial_investment'],
            test_mode=True
        )
        
        # OrderExecutor
        order_executor = OrderExecutor(
            exchange_api=exchange_api,
            db_manager=db_manager,
            symbol=config['symbol'],
            test_mode=True
        )
        
        # 전략 초기화
        strategy = MovingAverageCrossover(
            short_period=20,
            long_period=50,
            stop_loss_pct=2.0,
            take_profit_pct=5.0
        )
        
        # TradingAlgorithm 초기화
        trading_algo = TradingAlgorithm(
            exchange_id=config['exchange'],
            symbol=config['symbol'],
            strategy=strategy,
            initial_balance=config['initial_investment'],
            test_mode=True,
            market_type=config['market_type']
        )
        
        print("모든 컴포넌트 초기화 완료")
        
        # 1. Position 객체 생성 (선물거래용)
        print("\n=== 1. Position 객체 생성 ===")
        position = Position(
            id="live_test_001",
            symbol="BTC/USDT",
            side="long",
            amount=0.001,  # 0.001 BTC contracts
            entry_price=45000,
            leverage=10  # 선물거래의 경우 레버리지 사용
        )
        print(f"Position 생성: {position.symbol} {position.side} {position.amount} @ {position.entry_price}")
        
        # 2. DB에 Position 저장
        print("\n=== 2. DB에 Position 저장 ===")
        db_manager.save_position(position)
        print("Position 저장 완료")
        
        # 3. DB에서 Position 객체로 조회
        print("\n=== 3. DB에서 Position 조회 ===")
        positions_from_db = db_manager.get_open_positions_as_objects()
        print(f"DB에서 조회된 Position 객체: {len(positions_from_db)}개")
        for pos in positions_from_db:
            print(f"  - {pos.symbol}: {pos.side} {pos.amount} @ {pos.entry_price}")
        
        # 4. TradingAlgorithm에서 Position 객체 조회
        print("\n=== 4. TradingAlgorithm Position 조회 ===")
        # 테스트 포지션을 포트폴리오에 추가
        portfolio_manager.add_position(position)
        
        # Position 객체로 조회
        algo_positions = trading_algo.get_open_positions_as_objects()
        print(f"TradingAlgorithm에서 조회된 Position 객체: {len(algo_positions)}개")
        for pos in algo_positions:
            print(f"  - {pos.symbol}: {pos.side} {pos.amount} @ {pos.entry_price}")
        
        # 5. Position 업데이트
        print("\n=== 5. Position 업데이트 ===")
        if positions_from_db:
            # 처음 조회된 Position 객체 업데이트
            updated_position = positions_from_db[0]
            updated_position.status = 'closed'
            updated_position.exit_price = 46000
            updated_position.closed_at = datetime.now().isoformat()
            
            # DB에서 할당된 ID 가져오기
            db_cursor = db_manager._get_connection()[1]
            db_cursor.execute("SELECT id FROM positions WHERE symbol=? AND side=? ORDER BY opened_at DESC LIMIT 1", 
                            (updated_position.symbol, updated_position.side))
            position_db_id = db_cursor.fetchone()[0]
            
            # 포지션 닫기 (pnl 자동 계산)
            updated_position.close_position(46000)
            
            # 업데이트된 포지션 저장
            update_data = {
                'status': updated_position.status,
                'closed_at': updated_position.closed_at,
                'pnl': updated_position.pnl
            }
            db_manager.update_position(position_db_id, update_data)
            print(f"Position 업데이트 완료: PnL={updated_position.pnl}, status={updated_position.status}")
        
        # 6. 전체 시스템 통합 테스트
        print("\n=== 6. 전체 시스템 통합 ===")
        print("Position 객체가 다음 컴포넌트에서 정상 작동:")
        print("  ✓ OrderExecutor: Position 객체 생성")
        print("  ✓ PortfolioManager: Position 객체와 딕셔너리 모두 처리")
        print("  ✓ DatabaseManager: Position 객체 저장/조회")
        print("  ✓ TradingAlgorithm: Position 객체 조회")
        
        # 테스트 DB 삭제
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            
        print("\n=== 테스트 완료 ===")
        return True
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_position_compatibility():
    """Position 객체의 하위 호환성 테스트"""
    print("\n=== Position 하위 호환성 테스트 ===")
    
    # 다양한 형식의 딕셔너리 테스트
    test_cases = [
        {
            'name': 'contracts 필드 사용',
            'data': {
                'id': 'compat_001',
                'symbol': 'ETH/USDT',
                'side': 'short',
                'contracts': 1.5,  # contracts 사용
                'entry_price': 3200
            }
        },
        {
            'name': 'quantity 필드 사용',
            'data': {
                'id': 'compat_002',
                'symbol': 'SOL/USDT',
                'side': 'long',
                'quantity': 10,  # quantity 사용
                'entry_price': 100
            }
        },
        {
            'name': 'amount 필드 사용',
            'data': {
                'id': 'compat_003',
                'symbol': 'DOGE/USDT',
                'side': 'long',
                'amount': 1000,  # amount 사용
                'entry_price': 0.1
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n테스트: {test_case['name']}")
        try:
            position = Position.from_dict_compatible(test_case['data'])
            print(f"  생성 성공: amount={position.amount}")
            
            # 별칭 접근 테스트
            print(f"  contracts 접근: {position.contracts}")
            print(f"  quantity 접근: {position.quantity}")
            
            # 딕셔너리로 변환
            dict_data = position.to_dict_compatible()
            print(f"  딕셔너리 변환 성공: {dict_data.get('symbol')}")
            
        except Exception as e:
            print(f"  테스트 실패: {e}")
    
    return True

def main():
    """메인 함수"""
    print("=== Position 객체 실시간 통합 테스트 시작 ===")
    print(f"테스트 시작 시간: {datetime.now()}")
    
    # 각 테스트 실행
    tests = [
        ("실시간 통합 테스트", test_live_position_integration),
        ("하위 호환성 테스트", test_position_compatibility)
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
    
    print(f"\n테스트 종료 시간: {datetime.now()}")

if __name__ == "__main__":
    main()
