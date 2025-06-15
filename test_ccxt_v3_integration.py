#!/usr/bin/env python3
"""
CCXT v3 및 Binance API v2 통합 테스트
이 스크립트는 업그레이드 후 모든 주요 기능이 정상 작동하는지 확인합니다.
"""

import os
import sys
import json
import time
import asyncio
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.exchange_api import ExchangeAPI
from src.trading_algorithm import TradingAlgorithm
from src.strategies import MovingAverageCrossover
from src.models import TradeSignal

# 로깅 설정
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_exchange_api_connection():
    """거래소 API 연결 테스트"""
    logger.info("="*50)
    logger.info("1. 거래소 API 연결 테스트")
    logger.info("="*50)
    
    try:
        # ExchangeAPI 인스턴스 생성
        exchange_api = ExchangeAPI(
            exchange='binance',
            symbol='BTC/USDT',
            market_type='futures',
            leverage=1
        )
        
        logger.info(f"✅ ExchangeAPI 인스턴스 생성 성공")
        logger.info(f"   - 거래소: {exchange_api.exchange_id}")
        logger.info(f"   - 심볼: {exchange_api.symbol}")
        logger.info(f"   - 시장 타입: {exchange_api.market_type}")
        
        # CCXT 버전 확인
        import ccxt
        logger.info(f"   - CCXT 버전: {ccxt.__version__}")
        
        # API URL 확인
        if hasattr(exchange_api.exchange, 'urls') and 'api' in exchange_api.exchange.urls:
            api_urls = exchange_api.exchange.urls['api']
            if 'fapiPublic' in api_urls:
                logger.info(f"   - Binance Futures API URL: {api_urls['fapiPublic']}")
        
        return exchange_api
        
    except Exception as e:
        logger.error(f"❌ 거래소 API 연결 실패: {str(e)}")
        return None

def test_market_data(exchange_api):
    """시장 데이터 조회 테스트"""
    logger.info("\n" + "="*50)
    logger.info("2. 시장 데이터 조회 테스트")
    logger.info("="*50)
    
    try:
        # 현재 가격 조회
        current_price = exchange_api.get_current_price()
        logger.info(f"✅ 현재 가격 조회 성공: ${current_price:,.2f}")
        
        # OHLCV 데이터 조회
        ohlcv_data = exchange_api.get_ohlcv(timeframe='1h', limit=100)
        if ohlcv_data is not None and len(ohlcv_data) > 0:
            logger.info(f"✅ OHLCV 데이터 조회 성공: {len(ohlcv_data)}개 캔들")
            latest = ohlcv_data.iloc[-1]
            logger.info(f"   - 최신 캔들: Open=${latest['open']:,.2f}, High=${latest['high']:,.2f}, Low=${latest['low']:,.2f}, Close=${latest['close']:,.2f}")
        else:
            logger.error("❌ OHLCV 데이터 조회 실패")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ 시장 데이터 조회 실패: {str(e)}")
        return False

def test_account_info(exchange_api):
    """계정 정보 조회 테스트"""
    logger.info("\n" + "="*50)
    logger.info("3. 계정 정보 조회 테스트")
    logger.info("="*50)
    
    try:
        # 잔고 조회
        balance = exchange_api.get_balance()
        if balance:
            logger.info(f"✅ 잔고 조회 성공")
            if 'USDT' in balance:
                logger.info(f"   - USDT 잔고: ${balance['USDT'].get('total', 0):,.2f}")
            if 'BTC' in balance:
                logger.info(f"   - BTC 잔고: {balance['BTC'].get('total', 0):.8f}")
        
        # 포지션 조회 (선물만)
        if exchange_api.market_type == 'futures':
            positions = exchange_api.get_positions('BTC/USDT')
            logger.info(f"✅ 포지션 조회 성공: {len(positions)}개 포지션")
            for pos in positions:
                if pos.get('contracts', 0) != 0:
                    logger.info(f"   - 심볼: {pos.get('symbol')}, 수량: {pos.get('contracts')}, 미실현 손익: ${pos.get('unrealizedPnl', 0):,.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 계정 정보 조회 실패: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_trade_signal_generation():
    """거래 신호 생성 테스트"""
    logger.info("\n" + "="*50)
    logger.info("4. 거래 신호 생성 테스트")
    logger.info("="*50)
    
    try:
        # 전략 생성
        strategy = MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema')
        logger.info(f"✅ 전략 생성 성공: {strategy.name}")
        
        # 더미 시장 데이터 생성
        import pandas as pd
        import numpy as np
        
        # 100개의 캔들 데이터 생성
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
        base_price = 50000
        prices = base_price + np.cumsum(np.random.randn(100) * 100)
        
        market_data = pd.DataFrame({
            'timestamp': dates,
            'open': prices + np.random.randn(100) * 50,
            'high': prices + abs(np.random.randn(100) * 100),
            'low': prices - abs(np.random.randn(100) * 100),
            'close': prices,
            'volume': np.random.uniform(100, 1000, 100),
            'symbol': 'BTC/USDT'
        })
        
        # 신호 생성
        current_price = prices[-1]
        signal = strategy.generate_signal(market_data, current_price)
        
        if signal:
            logger.info(f"✅ 거래 신호 생성 성공")
            logger.info(f"   - 방향: {signal.direction}")
            logger.info(f"   - 가격: ${signal.price:,.2f}")
            logger.info(f"   - 신뢰도: {signal.confidence:.2%}")
            logger.info(f"   - 전략: {signal.strategy_name}")
        else:
            logger.info("ℹ️  현재 거래 신호 없음 (정상)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 거래 신호 생성 실패: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_trading_algorithm():
    """TradingAlgorithm 통합 테스트"""
    logger.info("\n" + "="*50)
    logger.info("5. TradingAlgorithm 통합 테스트")
    logger.info("="*50)
    
    try:
        # TradingAlgorithm 인스턴스 생성
        config = {
            'exchange': 'binance',
            'symbol': 'BTC/USDT',
            'market_type': 'futures',
            'leverage': 1,
            'strategy': {
                'name': 'MovingAverageCrossover',
                'params': {
                    'short_period': 9,
                    'long_period': 26,
                    'ma_type': 'ema'
                }
            },
            'risk_management': {
                'max_position_size': 0.1,
                'stop_loss_pct': 2.0,
                'take_profit_pct': 5.0
            }
        }
        
        trading_algo = TradingAlgorithm(config)
        logger.info(f"✅ TradingAlgorithm 인스턴스 생성 성공")
        
        # 포트폴리오 정보 확인
        portfolio = trading_algo.portfolio_manager.get_portfolio_status()
        logger.info(f"✅ 포트폴리오 상태 조회 성공")
        logger.info(f"   - 총 자산: ${portfolio.get('total_value', 0):,.2f}")
        logger.info(f"   - 현금: ${portfolio.get('cash', 0):,.2f}")
        logger.info(f"   - 포지션 수: {len(portfolio.get('positions', []))}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ TradingAlgorithm 테스트 실패: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """메인 테스트 함수"""
    logger.info("CCXT v3 및 Binance API v2 통합 테스트 시작")
    logger.info(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 환경 변수 확인
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ 환경 변수 BINANCE_API_KEY, BINANCE_API_SECRET가 설정되지 않았습니다.")
        logger.info("다음 명령으로 환경 변수를 설정하세요:")
        logger.info("export BINANCE_API_KEY='your_api_key'")
        logger.info("export BINANCE_API_SECRET='your_api_secret'")
        return
    
    # 테스트 실행
    test_results = {}
    
    # 1. 거래소 API 연결 테스트
    exchange_api = test_exchange_api_connection()
    test_results['API 연결'] = exchange_api is not None
    
    if exchange_api:
        # 2. 시장 데이터 조회 테스트
        test_results['시장 데이터'] = test_market_data(exchange_api)
        
        # 3. 계정 정보 조회 테스트
        test_results['계정 정보'] = test_account_info(exchange_api)
    
    # 4. 거래 신호 생성 테스트
    test_results['신호 생성'] = test_trade_signal_generation()
    
    # 5. TradingAlgorithm 통합 테스트
    test_results['통합 테스트'] = test_trading_algorithm()
    
    # 테스트 결과 요약
    logger.info("\n" + "="*50)
    logger.info("테스트 결과 요약")
    logger.info("="*50)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    
    for test_name, result in test_results.items():
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n총 {total_tests}개 테스트 중 {passed_tests}개 성공")
    
    if passed_tests == total_tests:
        logger.info("\n🎉 모든 테스트가 성공했습니다! CCXT v3 및 Binance API v2 업그레이드가 정상적으로 완료되었습니다.")
    else:
        logger.warning(f"\n⚠️  일부 테스트가 실패했습니다. 로그를 확인하여 문제를 해결하세요.")

if __name__ == "__main__":
    main()
