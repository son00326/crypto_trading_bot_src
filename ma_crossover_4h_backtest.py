#!/usr/bin/env python3
"""
Moving Average Crossover 4시간봉 백테스트
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import MovingAverageCrossover

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ma_crossover_backtest')

def run_ma_crossover_backtest():
    """MA Crossover 전략 백테스트"""
    
    logger.info("=" * 80)
    logger.info("Moving Average Crossover 백테스트 시작 (1시간봉)")
    logger.info("=" * 80)
    
    # 백테스터 초기화 (1시간봉, 선물 거래)
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',  # 1시간봉
        market_type='futures',  # 선물 거래 모드
        leverage=3  # 3배 레버리지
    )
    
    # 백테스트 기간 설정 (최근 6개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # 초기 자산
    initial_balance = 10000  # USDT
    
    # MA Crossover 전략 설정 (단기: 20, 장기: 50)
    strategy = MovingAverageCrossover(
        short_period=20,
        long_period=50,
        stop_loss_pct=0.04,      # 4% 손절
        take_profit_pct=0.08,    # 8% 익절
        max_position_size=0.95   # 95% 포지션
    )
    
    logger.info(f"전략: {strategy.name}")
    logger.info(f"단기 이평선: {strategy.short_period}")
    logger.info(f"장기 이평선: {strategy.long_period}")
    logger.info(f"손절매: {strategy.stop_loss_pct * 100:.0f}%")
    logger.info(f"이익실현: {strategy.take_profit_pct * 100:.0f}%")
    logger.info(f"레버리지: 3x")
    logger.info(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"초기 자산: {initial_balance} USDT")
    logger.info("=" * 80)
    
    try:
        # 백테스트 실행
        result = backtester.run_backtest(
            strategy=strategy,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_balance=initial_balance,
            commission=0.001  # 0.1% 수수료
        )
        
        # BacktestResult 객체를 dict로 변환
        if hasattr(result, '__dict__'):
            result_dict = result.__dict__
        else:
            result_dict = result
            
        # 결과 출력
        logger.info("\n백테스트 결과:")
        logger.info("=" * 80)
        logger.info(f"최종 자산: {result_dict.get('final_balance', 0):.2f} USDT")
        logger.info(f"총 수익률: {result_dict.get('total_return', 0):.2f}%")
        logger.info(f"샤프 비율: {result_dict.get('sharpe_ratio', 0):.2f}")
        logger.info(f"최대 낙폭: {result_dict.get('max_drawdown', 0):.2f}%")
        logger.info(f"승률: {result_dict.get('win_rate', 0):.2f}%")
        logger.info(f"총 거래 횟수: {result_dict.get('total_trades', 0)}")
        logger.info(f"승리 거래: {result_dict.get('winning_trades', 0)}")
        logger.info(f"패배 거래: {result_dict.get('losing_trades', 0)}")
        
        if result_dict.get('total_trades', 0) > 0:
            logger.info(f"평균 수익률: {result_dict.get('average_return', 0):.2f}%")
            logger.info(f"최대 연속 승리: {result_dict.get('max_consecutive_wins', 0)}")
            logger.info(f"최대 연속 패배: {result_dict.get('max_consecutive_losses', 0)}")
        
        # 매매 내역 확인
        if hasattr(result, 'trades') and result.trades:
            logger.info("\n최근 10개 거래:")
            logger.info("-" * 80)
            for i, trade in enumerate(result.trades[-10:], 1):
                logger.info(f"{i}. 시간: {trade.get('timestamp', 'N/A')}")
                logger.info(f"   방향: {trade.get('side', 'N/A')}")
                logger.info(f"   가격: ${trade.get('price', 0):.2f}")
                logger.info(f"   수량: {trade.get('amount', 0):.4f}")
                
        # 전략 성과 메트릭
        if hasattr(result, 'metrics'):
            logger.info("\n전략 성과 메트릭:")
            logger.info("-" * 80)
            for key, value in result.metrics.items():
                if isinstance(value, (int, float)):
                    logger.info(f"{key}: {value:.2f}")
                else:
                    logger.info(f"{key}: {value}")
        
        logger.info("=" * 80)
        logger.info("백테스트 완료!")
        
        return result
        
    except Exception as e:
        logger.error(f"백테스트 실행 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        result = run_ma_crossover_backtest()
    except KeyboardInterrupt:
        logger.info("백테스트가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"백테스트 실패: {e}")
        sys.exit(1)
