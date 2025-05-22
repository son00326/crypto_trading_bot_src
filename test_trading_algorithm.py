#!/usr/bin/env python3
"""
트레이딩 알고리즘 테스트 스크립트
"""
from src.trading_algorithm import TradingAlgorithm
import time

def test_order_executor_init():
    """OrderExecutor 초기화 문제 확인"""
    print("OrderExecutor 초기화 확인 중...")
    
    try:
        from src.order_executor import OrderExecutor
        from src.exchange_api import ExchangeAPI
        from src.db_manager import DatabaseManager
        
        # 필요한 객체 생성
        exchange_api = ExchangeAPI(exchange_id='binance', symbol='BTC/USDT')
        db_manager = DatabaseManager()
        
        # OrderExecutor 클래스 생성자 확인
        print("OrderExecutor.__init__ 함수 시그니처:")
        import inspect
        print(inspect.signature(OrderExecutor.__init__))
        
        # 직접 객체 생성 시도
        executor = OrderExecutor(exchange_api=exchange_api, db_manager=db_manager, symbol='BTC/USDT', test_mode=True)
        print("OrderExecutor 객체 성공적으로 생성됨")
        
    except Exception as e:
        print(f"OrderExecutor 초기화 오류: {str(e)}")
        import traceback
        traceback.print_exc()

def test_trading_algorithm():
    """트레이딩 알고리즘 테스트"""
    print("\n트레이딩 알고리즘 테스트 시작...")
    
    try:
        # TradingAlgorithm 초기화 시도 (restore_state=False로 상태 복원 과정 건너뛰기)
        algo = TradingAlgorithm(exchange_id='binance', symbol='BTC/USDT', test_mode=True, restore_state=False)
        print(f"알고리즘 초기화 성공: 거래소={algo.exchange_id}, 심볼={algo.symbol}")
        
        # 포트폴리오 요약 정보 가져오기
        try:
            portfolio_summary = algo.get_portfolio_summary()
            print(f"포트폴리오 요약: {portfolio_summary}")
        except Exception as e:
            print(f"포트폴리오 요약 정보 가져오기 실패: {str(e)}")
            
        # 자동 손절매/이익실현 기능 설정 테스트
        print("자동 손절매/이익실현 기능 활성화 상태:", algo.auto_sl_tp_enabled)
        algo.auto_position_manager.set_auto_sl_tp(True)
        print("자동 손절매/이익실현 기능 활성화 설정 후:", algo.auto_sl_tp_enabled)
    except Exception as e:
        print(f"TradingAlgorithm 초기화 오류: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 다음 테스트를 위한 공백
    # (이 섹션은 위에서 try-except 블록으로 이동되었습니다)
    
    # 포트폴리오 요약 정보 조회 테스트
    try:
        portfolio = algo.get_portfolio_summary()
        print(f"포트폴리오 요약 정보: {portfolio}")
    except Exception as e:
        print(f"포트폴리오 요약 정보 조회 중 오류: {str(e)}")
    
    # 포지션 안전장치 테스트
    try:
        margin_safety = algo.auto_position_manager.margin_safety_enabled
        print(f"마진 안전장치 활성화 상태: {margin_safety}")
    except Exception as e:
        print(f"마진 안전장치 상태 확인 중 오류: {str(e)}")
    
    print("트레이딩 알고리즘 테스트 완료")

if __name__ == "__main__":
    print("=== 트레이딩 알고리즘 테스트 시작 ===")
    test_order_executor_init()
    test_trading_algorithm()  # TradingAlgorithm 테스트 실행
    print("=== 트레이딩 알고리즘 테스트 완료 ===")
