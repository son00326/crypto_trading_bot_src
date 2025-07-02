#!/usr/bin/env python3
"""
Binance Futures 실제 거래 테스트 스크립트

안전한 테스트를 위해:
1. 매우 작은 금액으로 테스트 (최소 주문 크기)
2. 모든 거래 로그 기록
3. 긴급 정지 기능 포함
4. 테스트넷 사용 옵션
"""

import os
import sys
import time
import logging
import json
from datetime import datetime
from typing import Dict, Any

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
from src.strategies import BollingerBandFuturesStrategy
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'futures_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('futures_test')

class FuturesTradingTester:
    """안전한 Futures 거래 테스트 클래스"""
    
    def __init__(self, test_mode=True, use_testnet=False):
        self.test_mode = test_mode
        self.use_testnet = use_testnet
        self.exchange_api = None
        self.trading_algo = None
        
        # 안전 설정
        self.max_position_size = 0.001  # 최대 0.001 BTC (약 $30-60)
        self.max_loss_usd = 10  # 최대 손실 $10
        self.emergency_stop = False
        
        logger.info(f"테스터 초기화 - 테스트모드: {test_mode}, 테스트넷: {use_testnet}")
    
    def initialize_exchange(self):
        """거래소 API 초기화"""
        try:
            # API 키 확인
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
            
            if not api_key or not api_secret:
                raise ValueError("API 키가 설정되지 않았습니다")
            
            # ExchangeAPI 초기화
            self.exchange_api = ExchangeAPI(
                exchange_id='binance',
                api_key=api_key,
                api_secret=api_secret,
                testnet=self.use_testnet,
                market_type='futures'
            )
            
            # 연결 테스트
            balance = self.exchange_api.get_balance()
            logger.info(f"거래소 연결 성공 - USDT 잔액: {balance.get('USDT', {}).get('free', 0)}")
            
            return True
            
        except Exception as e:
            logger.error(f"거래소 초기화 실패: {e}")
            return False
    
    def check_minimum_requirements(self):
        """최소 거래 요구사항 확인"""
        try:
            # 현재 BTC 가격 확인
            ticker = self.exchange_api.get_ticker('BTC/USDT')
            btc_price = ticker.get('last', 0)
            
            # 최소 주문 크기 확인 (바이낸스 BTC/USDT futures: 0.001 BTC)
            min_order_size = 0.001
            min_order_value = min_order_size * btc_price
            
            logger.info(f"BTC 가격: ${btc_price:.2f}")
            logger.info(f"최소 주문 크기: {min_order_size} BTC (${min_order_value:.2f})")
            
            # 잔액 확인
            balance = self.exchange_api.get_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < min_order_value * 2:  # 여유있게 2배
                logger.warning(f"잔액 부족: ${usdt_balance:.2f} < ${min_order_value * 2:.2f}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"요구사항 확인 실패: {e}")
            return False
    
    def test_futures_position_lifecycle(self):
        """Futures 포지션 전체 생명주기 테스트"""
        logger.info("\n=== Futures 포지션 생명주기 테스트 시작 ===")
        
        try:
            # 1. 현재 포지션 확인
            logger.info("\n1. 현재 포지션 확인")
            positions = self.exchange_api.get_positions('BTC/USDT')
            logger.info(f"현재 포지션: {json.dumps(positions, indent=2)}")
            
            # 2. 전략 초기화
            logger.info("\n2. 전략 초기화")
            strategy = BollingerBandFuturesStrategy(
                bb_period=20,
                bb_std=2.0,
                leverage=5,  # 안전한 레버리지
                risk_per_trade=0.5  # 0.5% 리스크
            )
            
            # 3. TradingAlgorithm 초기화
            logger.info("\n3. TradingAlgorithm 초기화")
            self.trading_algo = TradingAlgorithm(
                exchange_api=self.exchange_api,
                strategy=strategy,
                symbol='BTC/USDT',
                timeframe='1m',  # 빠른 테스트를 위해 1분봉
                test_mode=self.test_mode,
                market_type='futures',
                leverage=5,
                strategy_params={
                    'bb_period': 20,
                    'bb_std': 2.0,
                    'leverage': 5,
                    'risk_per_trade': 0.5
                }
            )
            
            # 4. 시뮬레이션: 작은 포지션 열기
            if not self.test_mode:
                logger.info("\n4. 실제 포지션 열기 테스트")
                
                # 매수 신호 강제 생성 (테스트용)
                ticker = self.exchange_api.get_ticker('BTC/USDT')
                current_price = ticker['last']
                
                # 최소 크기로 매수
                order_result = self.trading_algo.execute_buy(
                    symbol='BTC/USDT',
                    price=current_price,
                    quantity=0.001,  # 최소 크기
                    additional_info={
                        'reason': 'futures_test',
                        'test_trade': True
                    }
                )
                
                logger.info(f"매수 주문 결과: {json.dumps(order_result, indent=2)}")
                
                # 5초 대기
                time.sleep(5)
                
                # 5. 포지션 확인
                positions = self.exchange_api.get_positions('BTC/USDT')
                logger.info(f"매수 후 포지션: {json.dumps(positions, indent=2)}")
                
                # 6. 포지션 청산
                if positions:
                    logger.info("\n5. 포지션 청산 테스트")
                    close_result = self.trading_algo.close_position(
                        symbol='BTC/USDT',
                        percentage=100  # 전량 청산
                    )
                    logger.info(f"청산 결과: {json.dumps(close_result, indent=2)}")
            
            else:
                logger.info("\n4. 테스트 모드 - 실제 거래 없음")
                # 테스트 모드에서는 시뮬레이션만
                self.trading_algo.run_once()
                
            logger.info("\n=== 테스트 완료 ===")
            return True
            
        except Exception as e:
            logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)
            return False
    
    def monitor_safety(self):
        """안전 모니터링"""
        try:
            # 현재 손실 확인
            positions = self.exchange_api.get_positions()
            total_pnl = sum(pos.get('unrealizedPnl', 0) for pos in positions)
            
            if abs(total_pnl) > self.max_loss_usd:
                logger.error(f"최대 손실 초과: ${abs(total_pnl):.2f}")
                self.emergency_stop = True
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"안전 모니터링 실패: {e}")
            return False

def main():
    """메인 테스트 함수"""
    print("\n" + "="*60)
    print("Binance Futures 거래 테스트")
    print("="*60)
    
    # 테스트 옵션 선택
    while True:
        print("\n테스트 옵션:")
        print("1. 테스트 모드 (시뮬레이션)")
        print("2. 실제 거래 (매우 작은 금액)")
        print("3. 테스트넷 사용")
        print("0. 종료")
        
        choice = input("\n선택하세요 (0-3): ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            tester = FuturesTradingTester(test_mode=True, use_testnet=False)
        elif choice == '2':
            confirm = input("\n⚠️  실제 거래를 진행합니다. 계속하시겠습니까? (yes/no): ")
            if confirm.lower() != 'yes':
                continue
            tester = FuturesTradingTester(test_mode=False, use_testnet=False)
        elif choice == '3':
            tester = FuturesTradingTester(test_mode=False, use_testnet=True)
        else:
            print("잘못된 선택입니다.")
            continue
        
        # 테스트 실행
        print("\n테스트를 시작합니다...")
        
        # 1. 거래소 초기화
        if not tester.initialize_exchange():
            print("거래소 초기화 실패")
            continue
        
        # 2. 요구사항 확인
        if not tester.check_minimum_requirements():
            print("최소 요구사항을 만족하지 않습니다")
            continue
        
        # 3. 포지션 생명주기 테스트
        tester.test_futures_position_lifecycle()
        
        print("\n테스트가 완료되었습니다. 로그 파일을 확인하세요.")

if __name__ == "__main__":
    main()
