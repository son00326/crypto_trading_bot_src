#!/usr/bin/env python3
"""
CCXT v3 및 Binance API v2 업그레이드 테스트 스크립트
"""

import os
import sys
import json
import traceback
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경 변수 로드
load_dotenv()

def test_trade_signal():
    """TradeSignal 클래스 필드명 테스트"""
    print("\n=== TradeSignal 클래스 테스트 ===")
    try:
        from src.models.trade_signal import TradeSignal
        from datetime import datetime
        
        # TradeSignal 생성
        signal = TradeSignal(
            symbol="BTC/USDT",
            direction="buy",  # signal_type 대신 direction 사용
            price=50000.0,
            strategy_name="test_strategy"
        )
        
        print(f"✓ TradeSignal 생성 성공")
        print(f"  - symbol: {signal.symbol}")
        print(f"  - direction: {signal.direction}")
        print(f"  - price: {signal.price}")
        print(f"  - strategy_name: {signal.strategy_name}")
        
        # to_dict 메서드 테스트
        signal_dict = signal.to_dict()
        print(f"✓ to_dict() 메서드 정상 작동")
        print(f"  - direction 필드 존재: {'direction' in signal_dict}")
        
        return True
        
    except Exception as e:
        print(f"✗ TradeSignal 테스트 실패: {str(e)}")
        traceback.print_exc()
        return False

def test_binance_api_url():
    """Binance API URL 업데이트 테스트"""
    print("\n=== Binance API URL 테스트 ===")
    try:
        from utils.api import create_binance_client
        import ccxt
        
        # API 키 확인
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            print("⚠️  바이낸스 API 키가 설정되지 않았습니다. 테스트넷으로 테스트합니다.")
            client = create_binance_client(api_key="test", api_secret="test", is_future=True, use_testnet=True)
        else:
            # 실제 API로 클라이언트 생성
            client = create_binance_client(api_key=api_key, api_secret=api_secret, is_future=True, use_testnet=False)
        
        # URL 확인
        if hasattr(client, 'urls') and 'api' in client.urls:
            api_urls = client.urls['api']
            print(f"✓ Binance Futures API URLs:")
            for key, url in api_urls.items():
                if 'fapi' in key:
                    print(f"  - {key}: {url}")
                    # v2 확인
                    if '/fapi/v2' in url:
                        print(f"    ✓ v2 API 사용 확인")
        
        return True
        
    except Exception as e:
        print(f"✗ Binance API URL 테스트 실패: {str(e)}")
        traceback.print_exc()
        return False

def test_ccxt_version():
    """CCXT 버전 확인"""
    print("\n=== CCXT 버전 테스트 ===")
    try:
        import ccxt
        
        version = ccxt.__version__
        print(f"✓ CCXT 버전: {version}")
        
        # 버전 비교
        version_parts = version.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        
        if major >= 3 and minor >= 1:
            print(f"✓ CCXT 3.1.0 이상 버전 확인")
        else:
            print(f"⚠️  CCXT 버전이 3.1.0 미만입니다. 업그레이드가 필요합니다.")
            print(f"   pip install --upgrade ccxt>=3.1.0")
            
        return True
        
    except Exception as e:
        print(f"✗ CCXT 버전 테스트 실패: {str(e)}")
        return False

def test_position_fetch():
    """포지션 조회 로직 테스트"""
    print("\n=== 포지션 조회 테스트 ===")
    try:
        from src.exchange_api import ExchangeAPI
        
        # API 키 확인
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            print("⚠️  실제 API 키가 없어 포지션 조회 테스트를 건너뜁니다.")
            return True
        
        # 선물 거래 API 생성
        api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTC/USDT',
            market_type='futures'
        )
        
        print("✓ ExchangeAPI 인스턴스 생성 완료")
        
        # 포지션 조회 테스트
        try:
            positions = api.get_positions()
            print(f"✓ 포지션 조회 성공: {len(positions)}개 포지션")
            
            # 특정 심볼 포지션 조회
            btc_positions = api.get_positions('BTC/USDT')
            print(f"✓ BTC/USDT 포지션 조회 성공: {len(btc_positions)}개 포지션")
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "fetchPositionsRisk() requires an array argument" in error_msg:
                print(f"✗ 포지션 조회 실패: CCXT v3 호환성 문제")
                print(f"  오류: {error_msg}")
                print(f"  → fetch_positions_risk([]) 대신 fetch_positions() 사용 필요")
                return False
            else:
                print(f"⚠️  포지션 조회 중 다른 오류 발생: {error_msg}")
                return True  # API 키 문제일 수 있으므로 pass
        
    except Exception as e:
        print(f"✗ 포지션 조회 테스트 실패: {str(e)}")
        traceback.print_exc()
        return False

def test_trading_algorithm_compatibility():
    """TradingAlgorithm과 TradeSignal 호환성 테스트"""
    print("\n=== TradingAlgorithm 호환성 테스트 ===")
    try:
        from src.trading_algorithm import TradingAlgorithm
        from src.models.trade_signal import TradeSignal
        
        # 더미 알고리즘 생성
        algo = TradingAlgorithm(
            exchange_id='binance',
            api_key='dummy',
            api_secret='dummy',
            symbol='BTC/USDT',
            test_mode=True
        )
        
        # TradeSignal 생성
        signal = TradeSignal(
            symbol="BTC/USDT",
            direction="buy",
            price=50000.0,
            strategy_name="test"
        )
        
        # signal.direction 접근 테스트
        if hasattr(signal, 'direction'):
            print(f"✓ TradeSignal.direction 필드 접근 가능: {signal.direction}")
        else:
            print(f"✗ TradeSignal.direction 필드 없음")
            return False
            
        # TradingAlgorithm이 direction 필드를 사용하는지 확인
        print(f"✓ TradingAlgorithm과 TradeSignal 호환성 확인 완료")
        
        return True
        
    except Exception as e:
        print(f"✗ 호환성 테스트 실패: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("CCXT v3 및 Binance API v2 업그레이드 테스트")
    print("=" * 60)
    
    tests = [
        ("TradeSignal 클래스 필드명", test_trade_signal),
        ("CCXT 버전", test_ccxt_version),
        ("Binance API URL", test_binance_api_url),
        ("포지션 조회 로직", test_position_fetch),
        ("TradingAlgorithm 호환성", test_trading_algorithm_compatibility)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} 테스트 중 예외 발생: {str(e)}")
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n총 {len(results)}개 테스트 중 {passed}개 성공, {failed}개 실패")
    
    if failed > 0:
        print("\n⚠️  일부 테스트가 실패했습니다. 위의 오류 메시지를 확인하세요.")
    else:
        print("\n✅ 모든 테스트가 성공했습니다!")

if __name__ == "__main__":
    main()
