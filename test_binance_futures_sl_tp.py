#!/usr/bin/env python3
"""
바이낸스 선물 자동 손절매/이익실현 기능 테스트
"""

import os
import sys
from pathlib import Path
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

def test_binance_futures_sl_tp():
    """바이낸스 선물 손절/익절 테스트"""
    
    print("============================================================")
    print("바이낸스 선물 자동 손절매/이익실현 기능 테스트")
    print("============================================================")
    
    try:
        # 1. 바이낸스 선물 거래소 초기화
        print("\n1. 바이낸스 선물 거래소 API 초기화...")
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # 선물 거래 설정
                'adjustForTimeDifference': True,  # 시간 동기화
            }
        })
        
        # 시장 정보 로드
        exchange.load_markets()
        print("✅ 거래소 API 초기화 성공")
        
        # 2. 계정 잔고 확인
        print("\n2. 선물 계정 잔고 확인...")
        try:
            balance = exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            print(f"  - USDT 잔고: {usdt_balance.get('total', 0):.2f} USDT")
            print(f"  - 사용 가능: {usdt_balance.get('free', 0):.2f} USDT")
        except Exception as e:
            print(f"  - 잔고 조회 실패: {str(e)}")
        
        # 3. 포지션 조회 (새로운 방식)
        print("\n3. 현재 포지션 확인...")
        positions = []
        try:
            # 모든 포지션 조회
            all_positions = exchange.fapiPrivateGetPositionRisk()
            
            # 실제 포지션만 필터링 (포지션 수량이 0이 아닌 것)
            for pos in all_positions:
                if float(pos.get('positionAmt', 0)) != 0:
                    positions.append(pos)
                    symbol = pos.get('symbol', '')
                    amount = float(pos.get('positionAmt', 0))
                    entry_price = float(pos.get('entryPrice', 0))
                    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                    
                    print(f"  - 심볼: {symbol}")
                    print(f"    포지션: {amount} (진입가: ${entry_price:.2f})")
                    print(f"    미실현 손익: ${unrealized_pnl:.2f}")
                    
            if not positions:
                print("  - 현재 열린 포지션이 없습니다.")
                
        except Exception as e:
            print(f"  - 포지션 조회 실패: {str(e)}")
        
        # 4. 손절/익절 주문 테스트
        print("\n4. 손절/익절 주문 설정 테스트...")
        
        # 테스트할 심볼
        symbol = 'BTC/USDT'
        
        # 현재 가격 확인
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"  - 현재 {symbol} 가격: ${current_price:.2f}")
        
        # 가상의 롱 포지션에 대한 손절/익절 가격 계산
        test_entry_price = current_price  # 현재가를 진입가로 가정
        stop_loss_pct = 0.03  # 3% 손절
        take_profit_pct = 0.06  # 6% 익절
        
        stop_loss_price = test_entry_price * (1 - stop_loss_pct)
        take_profit_price = test_entry_price * (1 + take_profit_pct)
        
        print(f"  - 가상 진입가: ${test_entry_price:.2f}")
        print(f"  - 손절가 (-{stop_loss_pct*100}%): ${stop_loss_price:.2f}")
        print(f"  - 익절가 (+{take_profit_pct*100}%): ${take_profit_price:.2f}")
        
        # 5. 주문 파라미터 확인 (실제 주문은 포지션이 있을 때만)
        print("\n5. 주문 파라미터 확인...")
        
        # 최소 주문 단위 확인
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"  - 최소 주문 수량: {min_amount} BTC")
        
        # 손절 주문 파라미터
        print("\n  [손절 주문 파라미터]")
        print(f"  - 주문 타입: STOP_MARKET")
        print(f"  - 트리거 가격: ${stop_loss_price:.2f}")
        print(f"  - 방향: SELL (롱 포지션 기준)")
        
        # 익절 주문 파라미터
        print("\n  [익절 주문 파라미터]")
        print(f"  - 주문 타입: TAKE_PROFIT_MARKET")
        print(f"  - 트리거 가격: ${take_profit_price:.2f}")
        print(f"  - 방향: SELL (롱 포지션 기준)")
        
        # 6. 현재 미체결 주문 확인
        print("\n6. 현재 미체결 주문 확인...")
        try:
            open_orders = exchange.fetch_open_orders(symbol)
            if open_orders:
                print(f"  - {len(open_orders)}개의 미체결 주문이 있습니다:")
                for order in open_orders:
                    print(f"    • {order['type']} {order['side']} {order['amount']} @ ${order.get('stopPrice', order.get('price', 0)):.2f}")
            else:
                print("  - 미체결 주문이 없습니다.")
        except Exception as e:
            print(f"  - 주문 조회 실패: {str(e)}")
        
        # 7. 실제 포지션이 있다면 손절/익절 설정 예시
        if positions:
            print("\n7. 실제 포지션에 대한 손절/익절 설정 방법:")
            print("   exchange.create_order(")
            print("       symbol='BTC/USDT',")
            print("       type='stop_market',")
            print("       side='sell',  # 롱 포지션의 경우")
            print("       amount=position_amount,")
            print("       stopPrice=stop_loss_price,")
            print("       params={'stopPrice': stop_loss_price}")
            print("   )")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n============================================================")
    print("테스트 완료")

if __name__ == "__main__":
    test_binance_futures_sl_tp()
