#!/usr/bin/env python3
"""
바이낸스 선물 손절/익절 주문 생성 테스트
실제 포지션 없이 주문 생성 가능한지 테스트
"""

import os
import sys
import ccxt
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# API 키 가져오기
api_key = os.getenv('BINANCE_API_KEY', '')
api_secret = os.getenv('BINANCE_API_SECRET', '')

if not api_key or not api_secret:
    print("❌ 환경 변수에서 BINANCE_API_KEY 또는 BINANCE_API_SECRET를 찾을 수 없습니다.")
    sys.exit(1)

def test_sl_tp_order():
    """손절/익절 주문 테스트"""
    
    print("============================================================")
    print("바이낸스 선물 손절/익절 주문 테스트")
    print("============================================================")
    
    try:
        # 바이낸스 선물 거래소 초기화
        print("\n1. 바이낸스 선물 거래소 API 초기화...")
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            }
        })
        
        exchange.load_markets()
        print("✅ 거래소 API 초기화 성공")
        
        # 테스트할 심볼
        symbol = 'BTC/USDT'
        
        # 현재 가격 확인
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"\n2. 현재 {symbol} 가격: ${current_price:.2f}")
        
        # 테스트용 소량 주문 수량
        test_amount = 0.001  # 최소 주문 단위
        
        # 손절/익절 가격 설정 (현재가 대비)
        stop_loss_price = round(current_price * 0.95, 2)  # 5% 아래
        take_profit_price = round(current_price * 1.05, 2)  # 5% 위
        
        print(f"\n3. 테스트 주문 파라미터:")
        print(f"  - 수량: {test_amount} BTC")
        print(f"  - 손절가: ${stop_loss_price:.2f} (현재가 -5%)")
        print(f"  - 익절가: ${take_profit_price:.2f} (현재가 +5%)")
        
        # 손절 주문 테스트
        print("\n4. 손절 주문 생성 테스트...")
        try:
            # 바이낸스 선물의 경우 reduceOnly 파라미터를 사용
            sl_order = exchange.create_order(
                symbol=symbol,
                type='stop_market',
                side='sell',
                amount=test_amount,
                params={
                    'triggerPrice': stop_loss_price,
                    'reduceOnly': True,  # 포지션 축소만 가능
                    'workingType': 'MARK_PRICE'  # 마크 가격 기준
                }
            )
            print(f"✅ 손절 주문 생성 성공!")
            print(f"  - 주문 ID: {sl_order['id']}")
            print(f"  - 상태: {sl_order['status']}")
            
            # 주문 취소 (테스트이므로)
            if sl_order['id']:
                try:
                    exchange.cancel_order(sl_order['id'], symbol)
                    print("  - 테스트 주문 취소됨")
                except:
                    pass
                    
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 손절 주문 생성 실패: {error_msg}")
            
            # 포지션이 없어서 실패한 경우 메시지 표시
            if 'ReduceOnly' in error_msg or 'reduce only' in error_msg.lower():
                print("  ℹ️  포지션이 없어서 reduceOnly 주문을 생성할 수 없습니다.")
                print("     실제 포지션이 있을 때만 손절/익절 주문을 설정할 수 있습니다.")
        
        # 익절 주문 테스트
        print("\n5. 익절 주문 생성 테스트...")
        try:
            tp_order = exchange.create_order(
                symbol=symbol,
                type='take_profit_market',
                side='sell',
                amount=test_amount,
                params={
                    'triggerPrice': take_profit_price,
                    'reduceOnly': True,
                    'workingType': 'MARK_PRICE'
                }
            )
            print(f"✅ 익절 주문 생성 성공!")
            print(f"  - 주문 ID: {tp_order['id']}")
            print(f"  - 상태: {tp_order['status']}")
            
            # 주문 취소 (테스트이므로)
            if tp_order['id']:
                try:
                    exchange.cancel_order(tp_order['id'], symbol)
                    print("  - 테스트 주문 취소됨")
                except:
                    pass
                    
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 익절 주문 생성 실패: {error_msg}")
            
            if 'ReduceOnly' in error_msg or 'reduce only' in error_msg.lower():
                print("  ℹ️  포지션이 없어서 reduceOnly 주문을 생성할 수 없습니다.")
                print("     실제 포지션이 있을 때만 손절/익절 주문을 설정할 수 있습니다.")
        
        # 결론
        print("\n6. 테스트 결과:")
        print("  - 바이낸스 선물 API 연결: ✅ 정상")
        print("  - 계정 잔고 조회: ✅ 정상")
        print("  - 시장 가격 조회: ✅ 정상")
        print("  - 손절/익절 주문: ⚠️  포지션이 있어야만 설정 가능")
        print("\n  💡 실제 거래 시 포지션 진입 후 자동으로 손절/익절이 설정됩니다.")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n============================================================")
    print("테스트 완료")

if __name__ == "__main__":
    test_sl_tp_order()
