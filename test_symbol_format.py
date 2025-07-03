#!/usr/bin/env python3
"""
심볼 형식 테스트 스크립트
DB와 API 간의 심볼 형식 일관성을 테스트합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db_manager import DatabaseManager
from src.exchange_api import ExchangeAPI
from src.models.position import Position
from datetime import datetime
import json

def test_symbol_formats():
    """심볼 형식 테스트"""
    print("=== 심볼 형식 테스트 시작 ===\n")
    
    # 1. DB 테스트
    print("1. DB 저장 테스트")
    db = DatabaseManager()
    
    # 테스트용 포지션 생성
    test_position = Position(
        symbol="BTC/USDT",  # 슬래시 포함
        side="long",
        amount=0.001,
        entry_price=50000.0,
        opened_at=datetime.now(),
        status="open",
        leverage=5,
        additional_info=json.dumps({"market_type": "futures"})
    )
    
    print(f"  - 원본 심볼: {test_position.symbol}")
    
    # DB에 저장
    position_id = db.save_position(test_position)
    print(f"  - 포지션 저장 완료 (ID: {position_id})")
    
    # DB에서 조회
    saved_positions = db.get_open_positions()
    if saved_positions:
        saved_position = saved_positions[-1]  # 가장 최근 포지션
        print(f"  - DB에 저장된 심볼: {saved_position['symbol']}")
    
    # 직접 SQL로 확인
    import sqlite3
    conn = sqlite3.connect('data/trading_bot.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT symbol FROM positions WHERE id = ?", (position_id,))
    row = cursor.fetchone()
    if row:
        print(f"  - SQL 직접 조회 결과: {row[0]}")
    conn.close()
    
    print("\n2. Exchange API 테스트")
    # ExchangeAPI 초기화
    try:
        api = ExchangeAPI(
            exchange_id='binance',
            symbol='BTCUSDT',  # 슬래시 없음
            market_type='futures',
            leverage=5
        )
        
        # get_market_info 테스트
        print("  - get_market_info() 테스트:")
        market_info = api.get_market_info('BTCUSDT')
        if market_info:
            print(f"    -> 성공: {market_info.get('symbol')}")
        else:
            print("    -> 실패: 심볼을 찾을 수 없음")
            
        # BTC/USDT 형식으로도 테스트
        market_info2 = api.get_market_info('BTC/USDT')
        if market_info2:
            print(f"    -> BTC/USDT도 성공: {market_info2.get('symbol')}")
            
    except Exception as e:
        print(f"  - ExchangeAPI 초기화 오류: {e}")
    
    print("\n3. 심볼 변환 테스트")
    from src.utils.symbol_utils import normalize_symbol, convert_symbol_format
    
    test_symbols = ['BTC/USDT', 'BTCUSDT', 'BTC/USDT:USDT']
    for symbol in test_symbols:
        normalized = normalize_symbol(symbol, 'binance', 'futures')
        print(f"  - {symbol} -> {normalized}")
    
    print("\n=== 테스트 완료 ===")
    
    # 테스트 포지션 삭제
    if saved_positions:
        # 7. 포지션 정리
        db.update_position(position_id, {'status': 'closed'})
        print("테스트 포지션을 closed로 변경했습니다.")

if __name__ == "__main__":
    test_symbol_formats()
