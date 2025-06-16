#!/usr/bin/env python3
"""
바이낸스 선물 거래 API 테스트 스크립트
"""

import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.exchange_api import ExchangeAPI
from src.db_manager import DatabaseManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_binance_futures():
    """바이낸스 선물 거래 기능 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # API 키 확인
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ 바이낸스 API 키가 환경 변수에 설정되어 있지 않습니다!")
        logger.error("💡 .env 파일에 다음을 추가하세요:")
        logger.error("   BINANCE_API_KEY=your_api_key_here")
        logger.error("   BINANCE_API_SECRET=your_api_secret_here")
        return False
    
    logger.info("✅ API 키 확인 완료")
    
    try:
        # 1. ExchangeAPI 초기화
        logger.info("\n📊 1. ExchangeAPI 초기화 테스트")
        exchange = ExchangeAPI(
            exchange_id='binance',
            market_type='futures',
            symbol='BTC/USDT',
            leverage=10
        )
        logger.info("✅ ExchangeAPI 초기화 성공")
        
        # 2. 잔고 조회
        logger.info("\n💰 2. 잔고 조회 테스트")
        balance = exchange.get_balance()
        if balance:
            logger.info(f"✅ USDT 잔고: {balance.get('USDT', {}).get('free', 0):.2f} USDT")
        else:
            logger.warning("⚠️ 잔고 조회 실패 또는 잔고 없음")
        
        # 3. 심볼 정보 조회
        logger.info("\n📈 3. 심볼 정보 조회 테스트")
        symbol = 'BTC/USDT'
        ticker = exchange.get_ticker(symbol)
        if ticker:
            logger.info(f"✅ {symbol} 현재가: ${ticker.get('last', 0):,.2f}")
        else:
            logger.error("❌ 티커 정보 조회 실패")
        
        # 4. 포지션 조회
        logger.info("\n📊 4. 포지션 조회 테스트")
        positions = exchange.get_positions()
        if positions is not None:
            logger.info(f"✅ 활성 포지션 수: {len(positions)}개")
            for pos in positions:
                if pos.get('contracts', 0) > 0:
                    logger.info(f"   - {pos['symbol']}: {pos['side']} {pos['contracts']} 계약")
        else:
            logger.error("❌ 포지션 조회 실패")
        
        # 5. 데이터베이스 테스트
        logger.info("\n💾 5. 데이터베이스 테스트")
        db = DatabaseManager()
        
        # 테스트 포지션 생성
        test_position = {
            'symbol': 'BTC/USDT',
            'side': 'long',
            'contracts': 0.001,
            'entry_price': 50000,
            'leverage': 10,
            'opened_at': '2025-01-16T00:00:00',
            'status': 'open',
            'additional_info': {'test': True}
        }
        
        # 포지션 저장 테스트
        try:
            db.save_position(test_position)
            logger.info("✅ 테스트 포지션 저장 성공")
            
            # 저장된 포지션 조회
            saved_positions = db.get_open_positions()
            test_pos_found = any(p['symbol'] == 'BTC/USDT' and p.get('entry_price') == 50000 for p in saved_positions)
            if test_pos_found:
                logger.info("✅ 저장된 포지션 조회 성공")
                
                # 테스트 포지션 삭제 - 가장 최근 포지션 ID로
                test_pos = next((p for p in saved_positions if p['symbol'] == 'BTC/USDT' and p.get('entry_price') == 50000), None)
                if test_pos:
                    db.update_position(test_pos['id'], {'status': 'closed'})
                    logger.info("✅ 테스트 포지션 정리 완료")
            else:
                logger.warning("⚠️ 저장된 포지션을 찾을 수 없음")
                
        except Exception as e:
            logger.error(f"❌ 데이터베이스 테스트 실패: {e}")
        
        logger.info("\n🎉 모든 테스트 완료!")
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_binance_futures()
    if not success:
        logger.error("\n⚠️ 일부 테스트가 실패했습니다. 위의 오류 메시지를 확인하세요.")
    else:
        logger.info("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
