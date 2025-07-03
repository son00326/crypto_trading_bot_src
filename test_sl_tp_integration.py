#!/usr/bin/env python3
"""
통합 테스트: TradingAlgorithm이 실제로 손절/익절 주문을 생성하는지 확인
"""
from src.trading_algorithm import TradingAlgorithm
from src.strategies import MovingAverageCrossover
from src.models.trade_signal import TradeSignal
from src.db_manager import DatabaseManager
from datetime import datetime
import os
import sys

def test_sl_tp_integration():
    print("=" * 60)
    print("Stop Loss/Take Profit 통합 테스트")
    print("=" * 60)
    
    # 1. 환경 변수 확인
    print("\n1. 환경 변수 확인")
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("   ❌ Binance API 키가 설정되지 않았습니다.")
        print("   환경 변수를 설정하세요: BINANCE_API_KEY, BINANCE_API_SECRET")
        return
    
    print("   ✅ API 키 확인됨")
    
    # 2. TradingAlgorithm 초기화
    print("\n2. TradingAlgorithm 초기화")
    strategy = MovingAverageCrossover(short_period=9, long_period=26)
    trading_algo = TradingAlgorithm(
        exchange_id='binance',
        symbol='BTC/USDT',
        strategy=strategy,
        test_mode=False,  # 실제 API 사용
        market_type='futures'
    )
    
    # Ensure markets are loaded
    if trading_algo.exchange_api:
        try:
            trading_algo.exchange_api.exchange.load_markets()
            print("   ✅ 시장 정보 로드 완료")
            
            # Debug: Check available symbols
            markets = trading_algo.exchange_api.exchange.markets
            if markets:
                # Find BTC/USDT related symbols
                btc_symbols = [s for s in markets.keys() if 'BTC' in s and 'USDT' in s]
                print(f"   📊 사용 가능한 BTC/USDT 관련 심볼: {btc_symbols[:5]}...")
                
                # 2. 시장 정보 확인 (futures 심볼)
                markets = trading_algo.exchange_api.exchange.markets
                btc_futures_symbols = [s for s in markets.keys() if 'BTC' in s and 'USDT' in s]
                print(f"   📊 사용 가능한 BTC/USDT 관련 심볼: {btc_futures_symbols[:5]}...")
                if 'BTC/USDT:USDT' in markets:
                    print("   ✅ BTC/USDT:USDT 심볼 존재 (선물)")
                    
                # 디버깅: 실제 markets 딕셔너리의 키들 확인
                print("\n   🔍 Markets 디버깅:")
                for symbol in ['BTCUSDT', 'BTC/USDT', 'BTC/USDT:USDT']:
                    exists = symbol in markets
                    print(f"      - {symbol}: {exists}")
                
                # format_symbol 메서드 테스트
                print("\n   🔧 Symbol 변환 테스트:")
                test_symbols = ['BTC/USDT', 'BTCUSDT', 'BTC/USDT:USDT']
                for sym in test_symbols:
                    formatted = trading_algo.exchange_api.format_symbol(sym)
                    print(f"      - {sym} -> {formatted}")
                if 'BTCUSDT' in markets:
                    print("   ✅ BTCUSDT 심볼 존재")
                elif 'BTC/USDT' in markets:
                    print("   ✅ BTC/USDT 심볼 존재")
                elif 'BTC/USDT:USDT' in markets:
                    print("   ✅ BTC/USDT:USDT 심볼 존재 (선물)")
            else:
                print("   ⚠️  로드된 시장 정보가 없습니다")
        except Exception as e:
            print(f"   ⚠️  시장 정보 로드 실패: {e}")
    
    print("   ✅ TradingAlgorithm 초기화 완료")
    
    # 3. 기존 열린 포지션 확인
    print("\n3. 기존 열린 포지션 확인")
    db_manager = trading_algo.db
    open_positions = db_manager.get_open_positions(symbol='BTC/USDT')
    print(f"   - 열린 포지션 {len(open_positions)}개 발견")
    for pos in open_positions:
        entry_price = pos.get('entry_price') or 0
        stop_loss = pos.get('stop_loss_price') or 0
        take_profit = pos.get('take_profit_price') or 0
        print(f"     ID: {pos['id']}, Entry: ${entry_price:,.0f}, SL: ${stop_loss:,.0f}, TP: ${take_profit:,.0f}")
    
    # 4. 현재 가격 확인
    print("\n4. 현재 BTC/USDT 가격 확인")
    current_price = trading_algo.get_current_price('BTC/USDT')
    if not current_price:
        print("   ❌ 현재 가격을 가져올 수 없습니다.")
        return
    print(f"   - 현재 가격: ${current_price:,.2f}")
    
    # 5. 테스트 신호 생성
    print("\n5. 테스트 신호 생성")
    test_signal = TradeSignal(
        symbol='BTC/USDT',
        direction='long',
        price=current_price,
        strategy_name='test_strategy',
        strength=0.7,
        confidence=0.8,
        timestamp=datetime.now()
    )
    print(f"   - 신호: {test_signal.direction.upper()} @ ${current_price:,.2f}")
    print(f"   - 강도: {test_signal.strength}")
    print(f"   - 신뢰도: {test_signal.confidence}")
    
    # 6. 신호 실행 (소량 테스트)
    print("\n6. 신호 실행 (소량 테스트)")
    try:
        # RiskManager를 사용하여 리스크 평가
        portfolio_status = trading_algo.portfolio_manager.get_portfolio_status()
        original_size = trading_algo.risk_manager.risk_config.get('position_size_pct', 0.1)
        
        risk_assessment = trading_algo.risk_manager.assess_risk(
            signal=test_signal,
            portfolio_status=portfolio_status,
            current_price=current_price,
            leverage=1.0,
            market_type='futures'
        )
        
        if not risk_assessment['should_execute']:
            print(f"   ⚠️ 리스크 평가 결과 거래 금지: {risk_assessment['reason']}")
        else:
            print(f"   - 리스크 평가 통과")
            print(f"   - 권장 포지션 크기: {risk_assessment['position_size']:.6f} BTC")
            print(f"   - Stop Loss: ${risk_assessment.get('stop_loss', 0):,.2f}")
            print(f"   - Take Profit: ${risk_assessment.get('take_profit', 0):,.2f}")
            
            # 시장 정보 확인
            market_info = trading_algo.exchange_api.get_market_info('BTC/USDT')
            if market_info:
                print("\n   시장 정보:")
                print(f"   - 최소 수량: {market_info.get('limits', {}).get('amount', {}).get('min', 'N/A')}")
                print(f"   - 수량 정밀도: {market_info.get('precision', {}).get('amount', 'N/A')}")
            
            # OrderExecutor를 사용하여 주문 실행
            # 바이낸스 선물 최소 주문 수량: 0.001 BTC
            position_size = max(0.001, risk_assessment['position_size'])  # 최소 0.001 BTC 보장
            
            # test_signal의 direction이 'long'이므로 execute_buy 사용
            result = trading_algo.order_executor.execute_buy(
                price=test_signal.price,
                quantity=position_size,
                portfolio=portfolio_status,
                additional_info={
                    'signal': test_signal.__dict__,
                    'risk_assessment': risk_assessment,
                    'stop_loss': risk_assessment.get('stop_loss'),
                    'take_profit': risk_assessment.get('take_profit')
                }
            )
            
            if result:
                print(f"   ✅ 주문 실행 성공!")
                print(f"   - 주문 ID: {result.get('id')}")
                
                # 7. 저장된 포지션 확인
                # OrderExecutor가 포지션을 생성할 때 position ID는 'pos_{주문ID}' 형식임
                position_id = f"pos_{result.get('id')}"
                if result.get('id'):
                    print("\n7. 저장된 포지션 확인")
                    import sqlite3
                    conn = sqlite3.connect(db_manager.db_path)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, symbol, side, entry_price, 
                               stop_loss_price, take_profit_price,
                               stop_loss_order_id, take_profit_order_id
                        FROM positions 
                        WHERE id = ?
                    """, (position_id,))
                    
                    pos = cursor.fetchone()
                    if pos:
                        print(f"   - ID: {pos[0]}")
                        print(f"   - Symbol: {pos[1]}")  
                        print(f"   - Side: {pos[2]}")
                        print(f"   - Entry Price: ${pos[3]:,.2f}")
                        print(f"   - Stop Loss Price: ${pos[4] or 0:,.2f}")
                        print(f"   - Take Profit Price: ${pos[5] or 0:,.2f}")
                        print(f"   - SL Order ID: {pos[6]}")
                        print(f"   - TP Order ID: {pos[7]}")
                    
                    conn.close()
                    
                    # 8. 실제 API 주문 확인
                    print("\n8. API 주문 확인")
                    try:
                        orders = trading_algo.exchange_api.exchange.fetch_open_orders('BTC/USDT')
                        if pos[6] or pos[7]:  # SL/TP order IDs exist
                            sl_tp_orders = [o for o in orders if o['id'] in [pos[6], pos[7]]]
                            if sl_tp_orders:
                                print(f"   ✅ 손절/익절 주문 {len(sl_tp_orders)}개 확인됨")
                                for order in sl_tp_orders:
                                    print(f"   - {order['type']} @ ${order['price']:,.2f}")
                            else:
                                print("   ⚠️  손절/익절 주문을 찾을 수 없음")
                    except Exception as e:
                        print(f"   ❌ 주문 조회 실패: {e}")
            else:
                print(f"   ❌ 주문 실행 실패: {result}")
    except Exception as e:
        print(f"   ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        trading_algo.risk_manager.risk_config['position_size_pct'] = original_size
    
    print("\n✅ 통합 테스트 완료!")

if __name__ == "__main__":
    test_sl_tp_integration()
