#!/usr/bin/env python3
"""
거래 신호 강제 발생 테스트 스크립트

이 스크립트는 트레이딩 봇이 정상적으로 거래를 실행하는지 테스트하기 위해
수동으로 거래 신호를 발생시킵니다.
"""

import sys
import os
import time
import argparse
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models.trade_signal import TradeSignal
from src.trading_algorithm import TradingAlgorithm
from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL
from src.logging_config import get_logger

logger = get_logger('force_trade_test')

def create_test_signal(direction='buy', confidence=0.8):
    """
    테스트용 거래 신호 생성
    
    Args:
        direction (str): 'buy' 또는 'sell'
        confidence (float): 신호 신뢰도 (0.0 ~ 1.0)
    
    Returns:
        TradeSignal: 생성된 거래 신호
    """
    signal = TradeSignal(
        symbol='BTC/USDT',
        direction=direction,
        price=0.0,  # 실제 가격은 나중에 설정
        strategy_name='ForceTradeTest',
        confidence=confidence,
        strength=0.7 if confidence >= 0.7 else 0.5,
        timestamp=datetime.now()
    )
    # 기타 필드들은 dataclass 기본값으로 설정됨
    return signal

def test_buy_signal(trading_algo, confidence=0.8):
    """매수 신호 테스트"""
    logger.info("=" * 50)
    logger.info("매수 신호 테스트 시작")
    logger.info("=" * 50)
    
    # 현재 가격 확인
    try:
        ticker = trading_algo.exchange_api.get_ticker()
        current_price = ticker['last']
        logger.info(f"현재 가격: {current_price}")
    except Exception as e:
        logger.error(f"가격 조회 실패: {e}")
        return False
    
    # 테스트 신호 생성
    signal = create_test_signal('buy', confidence)
    logger.info(f"생성된 신호: {signal}")
    
    # 포트폴리오 상태 확인
    portfolio_status = trading_algo.portfolio_manager.get_portfolio_status()
    logger.info(f"포트폴리오 상태: 잔액={portfolio_status['quote_balance']}")
    
    # 리스크 평가
    risk_assessment = trading_algo.risk_manager.assess_risk(
        signal=signal,
        portfolio_status=portfolio_status,
        current_price=current_price
    )
    
    logger.info(f"리스크 평가 결과: {risk_assessment}")
    
    if not risk_assessment['should_execute']:
        logger.warning(f"리스크 평가 실패: {risk_assessment['reason']}")
        return False
    
    # 주문 실행
    if trading_algo.test_mode:
        logger.info("테스트 모드: 시뮬레이션 매수 주문 실행")
    else:
        logger.info("실제 매수 주문 실행")
    
    order_result = trading_algo.order_executor.execute_buy(
        symbol=trading_algo.symbol,
        amount=risk_assessment['position_size'],
        price=current_price,
        order_type='market',
        metadata={
            'signal': signal.to_dict(),
            'risk_assessment': risk_assessment
        }
    )
    
    logger.info(f"주문 결과: {order_result}")
    return order_result.get('success', False)

def test_sell_signal(trading_algo, confidence=0.8):
    """매도 신호 테스트"""
    logger.info("=" * 50)
    logger.info("매도 신호 테스트 시작")
    logger.info("=" * 50)
    
    # 현재 가격 확인
    try:
        ticker = trading_algo.exchange_api.get_ticker()
        current_price = ticker['last']
        logger.info(f"현재 가격: {current_price}")
    except Exception as e:
        logger.error(f"가격 조회 실패: {e}")
        return False
    
    # 포지션 확인
    positions = trading_algo.portfolio_manager.get_open_positions()
    if not positions:
        logger.warning("매도할 포지션이 없습니다")
        return False
    
    position = positions[0]  # 첫 번째 포지션 선택
    logger.info(f"매도할 포지션: {position}")
    
    # 테스트 신호 생성
    signal = create_test_signal('sell', confidence)
    logger.info(f"생성된 신호: {signal}")
    
    # 주문 실행
    if trading_algo.test_mode:
        logger.info("테스트 모드: 시뮬레이션 매도 주문 실행")
    else:
        logger.info("실제 매도 주문 실행")
    
    order_result = trading_algo.order_executor.execute_sell(
        symbol=trading_algo.symbol,
        amount=position.quantity,
        price=current_price,
        order_type='market',
        metadata={
            'signal': signal.to_dict(),
            'position_id': position.id
        }
    )
    
    logger.info(f"주문 결과: {order_result}")
    return order_result.get('success', False)

def main():
    parser = argparse.ArgumentParser(description='거래 신호 강제 발생 테스트')
    parser.add_argument('--signal', choices=['buy', 'sell', 'both'], default='buy',
                        help='테스트할 신호 유형')
    parser.add_argument('--confidence', type=float, default=0.8,
                        help='신호 신뢰도 (0.0 ~ 1.0)')
    parser.add_argument('--exchange', default=DEFAULT_EXCHANGE,
                        help='거래소 ID')
    parser.add_argument('--symbol', default=DEFAULT_SYMBOL,
                        help='거래 심볼')
    parser.add_argument('--test-mode', action='store_true',
                        help='테스트 모드로 실행 (실제 거래 안함)')
    parser.add_argument('--delay', type=int, default=5,
                        help='신호 간 대기 시간 (초)')
    
    args = parser.parse_args()
    
    logger.info("거래 신호 강제 발생 테스트 시작")
    logger.info(f"설정: {args}")
    
    # 트레이딩 알고리즘 초기화
    try:
        trading_algo = TradingAlgorithm(
            exchange_id=args.exchange,
            symbol=args.symbol,
            test_mode=args.test_mode
        )
        logger.info("트레이딩 알고리즘 초기화 완료")
    except Exception as e:
        logger.error(f"초기화 실패: {e}")
        return 1
    
    # 신호 테스트 실행
    try:
        if args.signal in ['buy', 'both']:
            success = test_buy_signal(trading_algo, args.confidence)
            if success:
                logger.info("✅ 매수 신호 테스트 성공")
            else:
                logger.error("❌ 매수 신호 테스트 실패")
            
            if args.signal == 'both':
                logger.info(f"{args.delay}초 대기...")
                time.sleep(args.delay)
        
        if args.signal in ['sell', 'both']:
            success = test_sell_signal(trading_algo, args.confidence)
            if success:
                logger.info("✅ 매도 신호 테스트 성공")
            else:
                logger.error("❌ 매도 신호 테스트 실패")
        
        logger.info("모든 테스트 완료")
        return 0
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        logger.exception("상세 오류:")
        return 1

if __name__ == "__main__":
    sys.exit(main())
