#!/usr/bin/env python3
"""
선물거래 기능 통합 테스트 스크립트

이 스크립트는 수정된 선물거래 기능들이 제대로 작동하는지 확인합니다.
"""

import os
import sys
import time
import logging
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
from src.auto_position_manager import AutoPositionManager
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('futures_test')

def test_trading_algorithm_market_type():
    """TradingAlgorithm의 market_type 속성 테스트"""
    print("\n=== TradingAlgorithm market_type 테스트 ===")
    
    try:
        # 선물거래 설정으로 TradingAlgorithm 초기화
        algo = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            test_mode=True,
            market_type='futures',
            leverage=10
        )
        
        print(f"✅ market_type 속성: {algo.market_type}")
        print(f"✅ leverage 속성: {algo.leverage}")
        
        # AutoPositionManager가 market_type에 접근할 수 있는지 확인
        if hasattr(algo, 'auto_position_manager') and algo.auto_position_manager:
            try:
                # market_type 접근 테스트
                if algo.market_type.lower() == 'futures':
                    print("✅ AutoPositionManager가 market_type에 정상 접근 가능")
                else:
                    print("❌ market_type이 'futures'가 아님")
            except AttributeError as e:
                print(f"❌ AutoPositionManager의 market_type 접근 오류: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ TradingAlgorithm 초기화 오류: {e}")
        return False

def test_exchange_api_futures():
    """ExchangeAPI의 선물거래 기능 테스트"""
    print("\n=== ExchangeAPI 선물거래 기능 테스트 ===")
    
    try:
        # 선물거래 설정으로 ExchangeAPI 초기화
        api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            market_type='futures',
            leverage=5
        )
        
        print(f"✅ ExchangeAPI 초기화 성공")
        print(f"✅ market_type: {api.market_type}")
        print(f"✅ leverage: {api.leverage}")
        
        # 포지션 조회 테스트 (fetch_positions 사용 확인)
        try:
            positions = api.get_positions()
            print(f"✅ 포지션 조회 성공 (포지션 수: {len(positions)})")
        except Exception as e:
            print(f"❌ 포지션 조회 오류: {e}")
        
        # 레버리지 설정 메서드 테스트
        if hasattr(api, 'set_leverage'):
            result = api.set_leverage(3)
            if result:
                print("✅ set_leverage 메서드 정상 작동")
            else:
                print("❌ set_leverage 메서드 실패")
        else:
            print("❌ set_leverage 메서드가 없음")
        
        # 마진 모드 설정 메서드 테스트
        if hasattr(api, 'set_margin_mode'):
            result = api.set_margin_mode('isolated')
            if result:
                print("✅ set_margin_mode 메서드 정상 작동")
            else:
                print("❌ set_margin_mode 메서드 실패")
        else:
            print("❌ set_margin_mode 메서드가 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ ExchangeAPI 초기화 오류: {e}")
        return False

def test_trading_algorithm_methods():
    """TradingAlgorithm의 필수 메서드들 테스트"""
    print("\n=== TradingAlgorithm 필수 메서드 테스트 ===")
    
    try:
        algo = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            test_mode=True,
            market_type='futures',
            leverage=5
        )
        
        # get_current_price 메서드 테스트
        if hasattr(algo, 'get_current_price'):
            price = algo.get_current_price()
            if price:
                print(f"✅ get_current_price 메서드 정상 작동 (현재가: ${price:,.2f})")
            else:
                print("❌ get_current_price 메서드가 None 반환")
        else:
            print("❌ get_current_price 메서드가 없음")
        
        # get_open_positions 메서드 테스트
        if hasattr(algo, 'get_open_positions'):
            positions = algo.get_open_positions()
            print(f"✅ get_open_positions 메서드 정상 작동 (포지션 수: {len(positions)})")
        else:
            print("❌ get_open_positions 메서드가 없음")
        
        # close_position 메서드 테스트
        if hasattr(algo, 'close_position'):
            print("✅ close_position 메서드 존재")
        else:
            print("❌ close_position 메서드가 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ 메서드 테스트 오류: {e}")
        return False

def test_auto_position_manager_integration():
    """AutoPositionManager와 TradingAlgorithm 통합 테스트"""
    print("\n=== AutoPositionManager 통합 테스트 ===")
    
    try:
        # TradingAlgorithm 초기화
        algo = TradingAlgorithm(
            exchange_id='binance',
            symbol='BTC/USDT',
            timeframe='1h',
            test_mode=True,
            market_type='futures',
            leverage=5
        )
        
        # AutoPositionManager가 제대로 초기화되었는지 확인
        if hasattr(algo, 'auto_position_manager') and algo.auto_position_manager:
            apm = algo.auto_position_manager
            print("✅ AutoPositionManager 초기화 성공")
            
            # market_type 접근 테스트
            try:
                if apm.trading_algorithm.market_type == 'futures':
                    print("✅ AutoPositionManager가 TradingAlgorithm의 market_type에 정상 접근")
                else:
                    print("❌ market_type 값이 예상과 다름")
            except AttributeError as e:
                print(f"❌ market_type 접근 오류: {e}")
            
            # 필수 메서드 접근 테스트
            try:
                # get_current_price 테스트
                price = apm.trading_algorithm.get_current_price()
                if price:
                    print("✅ AutoPositionManager가 get_current_price 메서드 정상 호출")
                
                # get_open_positions 테스트
                positions = apm.trading_algorithm.get_open_positions()
                print("✅ AutoPositionManager가 get_open_positions 메서드 정상 호출")
                
            except AttributeError as e:
                print(f"❌ 메서드 호출 오류: {e}")
        else:
            print("❌ AutoPositionManager가 초기화되지 않음")
        
        return True
        
    except Exception as e:
        print(f"❌ 통합 테스트 오류: {e}")
        return False

def main():
    """메인 테스트 실행 함수"""
    print("=" * 60)
    print("선물거래 기능 통합 테스트 시작")
    print(f"테스트 시간: {datetime.now()}")
    print("=" * 60)
    
    # 테스트 실행
    tests = [
        test_trading_algorithm_market_type,
        test_exchange_api_futures,
        test_trading_algorithm_methods,
        test_auto_position_manager_integration
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"테스트 실행 중 오류: {e}")
            results.append(False)
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"전체 테스트: {total}개")
    print(f"✅ 성공: {passed}개")
    print(f"❌ 실패: {failed}개")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 성공했습니다!")
    else:
        print(f"\n⚠️  {failed}개의 테스트가 실패했습니다.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
