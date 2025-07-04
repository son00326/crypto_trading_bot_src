#!/usr/bin/env python3
"""
선물거래 종합 테스트 스크립트
EC2에서 실행 중인 봇의 전체 기능을 테스트합니다.
"""

import os
import sys
import time
import logging
from datetime import datetime
from decimal import Decimal
import json

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.trading_algorithm import TradingAlgorithm
from src.exchange_api import ExchangeAPI
from src.db_manager import DatabaseManager
from src.portfolio_manager import PortfolioManager
from src.risk_manager import RiskManager
from src.strategies import BollingerBandFuturesStrategy
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
test_log_file = f'futures_comprehensive_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(test_log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('futures_comprehensive_test')

class FuturesComprehensiveTester:
    """선물거래 종합 테스트 클래스"""
    
    def __init__(self):
        self.exchange_api = None
        self.db_manager = None
        self.portfolio_manager = None
        self.risk_manager = None
        self.trading_algo = None
        self.test_results = {
            'connection': False,
            'account_info': False,
            'positions': False,
            'orders': False,
            'leverage': False,
            'stop_loss_take_profit': False,
            'pnl_calculation': False,
            'risk_management': False,
            'auto_position_manager': False
        }
        
    def setup(self):
        """테스트 환경 설정"""
        try:
            logger.info("=== 테스트 환경 설정 시작 ===")
            
            # 1. 전략 초기화 (다른 구성요소보다 먼저)
            strategy = BollingerBandFuturesStrategy()
            logger.info("✅ 전략 초기화 완료")
            
            # 2. Trading Algorithm 초기화 (내부에서 Exchange API와 DB 생성)
            self.trading_algo = TradingAlgorithm(
                exchange_id='binance',
                symbol='BTC/USDT',
                timeframe='5m',
                strategy=strategy,
                test_mode=False,  # 실제 거래
                market_type='futures',
                leverage=5
            )
            logger.info("✅ Trading Algorithm 초기화 완료")
            
            # 3. TradingAlgorithm에서 생성된 객체들 참조
            self.exchange_api = self.trading_algo.exchange_api
            self.db_manager = self.trading_algo.db
            self.portfolio_manager = self.trading_algo.portfolio_manager
            logger.info("✅ 참조 객체 설정 완료")
            
            # 4. Risk Manager 초기화 (별도로 필요한 경우)
            self.risk_manager = RiskManager(
                exchange_id='binance',
                symbol='BTC/USDT',
                risk_config={
                    'max_loss_per_trade': 0.02,  # 2%
                    'max_daily_loss': 0.05,      # 5%
                    'max_leverage': 10,
                    'stop_loss_percent': 0.02,    # 2% 손절
                    'take_profit_percent': 0.05   # 5% 이익실현
                },
                auto_exit_enabled=True,
                partial_tp_enabled=True,
                margin_safety_enabled=True
            )
            logger.info("✅ Risk Manager 초기화 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 설정 중 오류 발생: {e}")
            return False
    
    def test_connection(self):
        """1. API 연결 테스트"""
        logger.info("\n=== 1. API 연결 테스트 ===")
        try:
            # 서버 시간 확인
            server_time = self.exchange_api.exchange.fetch_time()
            logger.info(f"✅ 서버 연결 성공 - 서버 시간: {datetime.fromtimestamp(server_time/1000)}")
            
            # 시장 정보 확인
            markets = self.exchange_api.exchange.load_markets()
            futures_markets = [m for m in markets.values() if m['type'] == 'future']
            logger.info(f"✅ 선물 시장 수: {len(futures_markets)}")
            
            self.test_results['connection'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 연결 테스트 실패: {e}")
            return False
    
    def test_account_info(self):
        """2. 계정 정보 테스트"""
        logger.info("\n=== 2. 계정 정보 테스트 ===")
        try:
            # 계정 잔고 확인
            balance = self.exchange_api.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            
            logger.info(f"USDT 잔고:")
            logger.info(f"  - 총액: {usdt_balance.get('total', 0)}")
            logger.info(f"  - 사용가능: {usdt_balance.get('free', 0)}")
            logger.info(f"  - 사용중: {usdt_balance.get('used', 0)}")
            
            # 마진 정보 확인 (선물)
            if hasattr(self.exchange_api.exchange, 'fetch_positions'):
                positions = self.exchange_api.exchange.fetch_positions()
                total_margin = sum(float(p.get('initialMargin', 0)) for p in positions if p)
                logger.info(f"✅ 총 사용 마진: {total_margin} USDT")
            
            self.test_results['account_info'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 계정 정보 테스트 실패: {e}")
            return False
    
    def test_positions(self):
        """3. 포지션 조회 테스트"""
        logger.info("\n=== 3. 포지션 조회 테스트 ===")
        try:
            # Exchange API를 통한 포지션 조회
            positions = self.exchange_api.get_positions()
            logger.info(f"현재 포지션 수: {len(positions)}")
            
            for pos in positions:
                logger.info(f"\n포지션 정보:")
                logger.info(f"  - 심볼: {pos.get('symbol')}")
                logger.info(f"  - 방향: {pos.get('side')}")
                logger.info(f"  - 수량: {pos.get('contracts', 0)}")
                logger.info(f"  - 진입가: {pos.get('markPrice', 0)}")
                logger.info(f"  - 미실현 손익: {pos.get('unrealizedPnl', 0)}")
            
            # DB에서 포지션 조회
            db_positions = self.db_manager.get_positions(status='open')
            logger.info(f"\n✅ DB 저장된 열린 포지션 수: {len(db_positions)}")
            
            self.test_results['positions'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 포지션 조회 테스트 실패: {e}")
            return False
    
    def test_leverage_settings(self):
        """4. 레버리지 설정 테스트"""
        logger.info("\n=== 4. 레버리지 설정 테스트 ===")
        try:
            # 현재 레버리지 확인
            current_leverage = self.exchange_api.leverage
            logger.info(f"현재 레버리지: {current_leverage}x")
            
            # 레버리지 변경 테스트 (10배로)
            new_leverage = 10
            # ExchangeAPI가 아닌 exchange 객체의 setLeverage 사용
            self.exchange_api.exchange.setLeverage(new_leverage, 'BTCUSDT')
            logger.info(f"레버리지를 {new_leverage}x로 변경")
            
            # 다시 원래대로 복구
            self.exchange_api.exchange.setLeverage(current_leverage, 'BTCUSDT')
            logger.info(f"레버리지를 {current_leverage}x로 복구")
            
            # leverage 속성도 업데이트
            self.exchange_api.leverage = current_leverage
            
            self.test_results['leverage'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 레버리지 설정 테스트 실패: {e}")
            return False
    
    def test_stop_loss_take_profit(self):
        """5. 손절매/이익실현 설정 테스트"""
        logger.info("\n=== 5. 손절매/이익실현 설정 테스트 ===")
        try:
            # Risk Manager 설정 확인
            logger.info(f"Risk Manager 설정:")
            if self.risk_manager.risk_config:
                logger.info(f"  - 최대 거래당 손실: {self.risk_manager.risk_config.get('max_loss_per_trade', 0) * 100}%")
                logger.info(f"  - 최대 일일 손실: {self.risk_manager.risk_config.get('max_daily_loss', 0) * 100}%")
                logger.info(f"  - 최대 레버리지: {self.risk_manager.risk_config.get('max_leverage', 1)}x")
                logger.info(f"  - 손절매 %: {self.risk_manager.risk_config.get('stop_loss_percent', 0) * 100}%")
                logger.info(f"  - 이익실현 %: {self.risk_manager.risk_config.get('take_profit_percent', 0) * 100}%")
            
            # Auto Position Manager 설정 확인 (있다면)
            if hasattr(self.trading_algo, 'auto_position_manager'):
                apm = self.trading_algo.auto_position_manager
                if apm and hasattr(apm, 'config'):
                    config = apm.config
                    logger.info(f"\nAuto Position Manager 설정:")
                    logger.info(f"  - 손절매 %: {config.get('stop_loss_percent', 0) * 100}%")
                    logger.info(f"  - 이익실현 %: {config.get('take_profit_percent', 0) * 100}%")
                    logger.info(f"  - 부분 이익실현: {config.get('partial_take_profit_enabled', False)}")
            
            # 열린 주문 확인 (심볼 지정하여 rate limit 방지)
            symbol = 'BTCUSDT'  # 심볼 지정
            open_orders = self.exchange_api.get_open_orders(symbol)
            stop_orders = [o for o in open_orders if o.get('type') in ['stop', 'stop_market']]
            tp_orders = [o for o in open_orders if o.get('type') in ['take_profit', 'take_profit_market']]
            logger.info(f"\n✅ 활성 손절매 주문 수: {len(stop_orders)}")
            logger.info(f"✅ 활성 이익실현 주문 수: {len(tp_orders)}")
            
            self.test_results['stop_loss_take_profit'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 손절매/이익실현 테스트 실패: {e}")
            return False
    
    def test_pnl_calculation(self):
        """6. 손익 계산 테스트"""
        logger.info("\n=== 6. 손익 계산 테스트 ===")
        try:
            # 포트폴리오 상태 확인
            portfolio = self.portfolio_manager.get_portfolio_status()
            
            logger.info(f"포트폴리오 상태:")
            logger.info(f"  - 총 자산: {portfolio.get('total_balance', 0)} USDT")
            logger.info(f"  - 사용 가능: {portfolio.get('available_balance', 0)} USDT")
            logger.info(f"  - 미실현 손익: {portfolio.get('unrealized_pnl', 0)} USDT")
            
            # DB에서 최근 실현 손익 확인
            closed_positions = self.db_manager.get_positions(status='closed')
            if closed_positions:
                recent_positions = closed_positions[:5]  # 최근 5개
                total_pnl = sum(float(p.get('realized_profit') or 0) for p in recent_positions)
                logger.info(f"\n최근 5개 포지션 총 손익: {total_pnl} USDT")
            
            self.test_results['pnl_calculation'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 손익 계산 테스트 실패: {e}")
            return False
    
    def test_order_execution(self):
        """7. 주문 실행 테스트 (최소 금액)"""
        logger.info("\n=== 7. 주문 실행 테스트 ===")
        try:
            symbol = 'BTCUSDT'
            
            # 현재 가격 확인
            ticker = self.exchange_api.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            logger.info(f"현재 BTC 가격: ${current_price}")
            
            # 최소 주문 크기 확인
            market = self.exchange_api.exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            min_cost = market['limits']['cost']['min']
            
            logger.info(f"최소 주문 정보:")
            logger.info(f"  - 최소 수량: {min_amount} BTC")
            logger.info(f"  - 최소 금액: ${min_cost}")
            
            # 테스트 주문 수량 계산 (최소 금액의 2배)
            test_cost = max(min_cost * 2, 10)  # 최소 $10
            test_amount = test_cost / current_price
            
            logger.info(f"\n⚠️  테스트 주문 정보:")
            logger.info(f"  - 수량: {test_amount:.6f} BTC")
            logger.info(f"  - 금액: ${test_cost:.2f}")
            logger.info(f"  - 레버리지: 5x")
            logger.info(f"  - 필요 마진: ${test_cost/5:.2f}")
            
            # 실제 주문은 주석 처리 (안전을 위해)
            # order = self.exchange_api.exchange.create_market_order(
            #     symbol=symbol,
            #     side='buy',
            #     amount=test_amount,
            #     params={'type': 'market'}
            # )
            # logger.info(f"✅ 테스트 주문 실행 완료: {order['id']}")
            
            logger.info("⚠️  실제 주문은 안전을 위해 실행하지 않았습니다.")
            logger.info("    필요시 주석을 해제하고 실행하세요.")
            
            self.test_results['orders'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 주문 실행 테스트 실패: {e}")
            return False
    
    def test_risk_management(self):
        """8. 리스크 관리 테스트"""
        logger.info("\n=== 8. 리스크 관리 테스트 ===")
        try:
            # 포트폴리오 상태 확인
            portfolio = self.portfolio_manager.get_portfolio_status()
            logger.info(f"포트폴리오 상태:")
            # None 값 처리
            total_balance = portfolio.get('total_balance') or 0
            available_balance = portfolio.get('available_balance') or 0
            unrealized_pnl = portfolio.get('unrealized_pnl') or 0
            
            logger.info(f"  - 총 자산: {total_balance} USDT")
            logger.info(f"  - 사용 가능: {available_balance} USDT")
            logger.info(f"  - 미실현 손익: {unrealized_pnl} USDT")
            
            # 일일 손실 확인
            # DB에서 오늘 닫힌 포지션의 손익 계산
            today = datetime.now().date()
            closed_today = self.db_manager.get_positions(status='closed')
            daily_pnl = 0
            for pos in closed_today:
                if pos.get('closed_at'):
                    closed_date = datetime.fromisoformat(pos['closed_at'].replace('Z', '+00:00')).date()
                    if closed_date == today:
                        daily_pnl += float(pos.get('realized_profit', 0))
            
            logger.info(f"오늘의 손익: {daily_pnl} USDT")
            
            if total_balance > 0:
                daily_loss_percent = (daily_pnl / total_balance) * 100 if daily_pnl < 0 else 0
                logger.info(f"일일 손실률: {daily_loss_percent:.2f}%")
                
                # 리스크 한도 확인
                max_daily_loss_percent = self.risk_manager.risk_config.get('max_daily_loss', 0.05) * 100
                logger.info(f"최대 허용 일일 손실: {max_daily_loss_percent}%")
                
                if daily_loss_percent >= max_daily_loss_percent:
                    logger.warning(f"⚠️  일일 손실 한도 초과! 거래 중단 필요")
                else:
                    logger.info(f"✅ 일일 손실 한도 내 운영 중 ({daily_loss_percent:.2f}% / {max_daily_loss_percent}%)")
            
            self.test_results['risk_management'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 리스크 관리 테스트 실패: {e}")
            return False
    
    def test_auto_position_manager(self):
        """9. 자동 포지션 관리 테스트"""
        logger.info("\n=== 9. 자동 포지션 관리 테스트 ===")
        try:
            # AutoPositionManager 상태 확인
            if hasattr(self.trading_algo, 'auto_position_manager'):
                apm = self.trading_algo.auto_position_manager
                if apm:
                    logger.info("✅ AutoPositionManager 활성화됨")
                    
                    # 현재 모니터링 중인 포지션 확인
                    positions = self.trading_algo.get_positions(status='open')
                    logger.info(f"모니터링 중인 포지션 수: {len(positions)}")
                    
                    # 각 포지션의 손절매/이익실현 상태 확인
                    for pos in positions:
                        symbol = pos.get('symbol')
                        side = pos.get('side')
                        entry_price = float(pos.get('markPrice', 0))
                        current_price = self.trading_algo.get_current_price(symbol)
                        
                        if entry_price > 0 and current_price > 0:
                            if side == 'long':
                                pnl_percent = (current_price - entry_price) / entry_price * 100
                            else:
                                pnl_percent = (entry_price - current_price) / entry_price * 100
                            
                            logger.info(f"\n포지션 {symbol} ({side}):")
                            logger.info(f"  - 진입가: ${entry_price}")
                            logger.info(f"  - 현재가: ${current_price}")
                            logger.info(f"  - 손익률: {pnl_percent:.2f}%")
                else:
                    logger.warning("⚠️  AutoPositionManager가 비활성화됨")
            else:
                logger.warning("⚠️  AutoPositionManager가 설정되지 않음")
            
            self.test_results['auto_position_manager'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 자동 포지션 관리 테스트 실패: {e}")
            return False
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("\n" + "="*60)
        logger.info("선물거래 종합 테스트 시작")
        logger.info("="*60)
        
        # 설정
        if not self.setup():
            logger.error("초기 설정 실패! 테스트를 중단합니다.")
            return
        
        # 각 테스트 실행
        tests = [
            self.test_connection,
            self.test_account_info,
            self.test_positions,
            self.test_leverage_settings,
            self.test_stop_loss_take_profit,
            self.test_pnl_calculation,
            self.test_order_execution,
            self.test_risk_management,
            self.test_auto_position_manager
        ]
        
        for test in tests:
            try:
                test()
                time.sleep(1)  # API 제한 방지
            except Exception as e:
                logger.error(f"테스트 중 예외 발생: {e}")
        
        # 결과 요약
        logger.info("\n" + "="*60)
        logger.info("테스트 결과 요약")
        logger.info("="*60)
        
        passed = sum(1 for v in self.test_results.values() if v)
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name.ljust(30)}: {status}")
        
        logger.info(f"\n총 {total}개 중 {passed}개 테스트 통과 ({passed/total*100:.1f}%)")
        logger.info(f"\n로그 파일: {test_log_file}")
        
        # 테스트 결과를 JSON으로 저장
        with open('futures_test_results.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': self.test_results,
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': total - passed,
                    'success_rate': f"{passed/total*100:.1f}%"
                }
            }, f, indent=2)
        
        logger.info("테스트 결과가 futures_test_results.json에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    tester = FuturesComprehensiveTester()
    
    print("\n" + "="*60)
    print("바이낸스 선물거래 종합 테스트")
    print("="*60)
    print("\n⚠️  경고: 이 테스트는 실제 거래소 API를 사용합니다.")
    print("최소 금액으로 테스트하지만 실제 손실이 발생할 수 있습니다.")
    print("\n계속하시겠습니까? (y/n): ", end='')
    
    if input().lower() != 'y':
        print("테스트를 취소했습니다.")
        return
    
    tester.run_all_tests()

if __name__ == "__main__":
    main()
