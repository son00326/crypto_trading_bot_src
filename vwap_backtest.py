#!/usr/bin/env python3
"""VWAP 전략 백테스트 스크립트
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester, BacktestResult
from src.strategies import VWAPBreakoutStrategy

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vwap_backtest')

def run_vwap_backtest():
    """VWAP 돌파 전략 백테스트 실행"""
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='15m',  # 15분봉 사용
        market_type='futures',  # 선물 거래
        leverage=5  # 레버리지 5배
    )
    
    # 백테스트 기간 설정 (최근 3개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    # 초기 자산
    initial_balance = 10000  # USDT
    
    # VWAP 전략 설정 - 고급 필터 및 위험 관리 기능 포함
    vwap_strategy = VWAPBreakoutStrategy(
        vwap_period=1,  # 1일 VWAP
        vwap_reset_hours=24,  # 24시간마다 리셋
        bb_period=20,  # 볼린저 밴드 20기간
        bb_std=2.0,  # 표준편차 2배
        stop_loss_pct=5.0,  # 손절 5% (더 타이트하게 설정)
        take_profit_pct=15.0,  # 이익실현 15% (더 높게 설정)
        leverage=3,  # 레버리지 3배
        use_bollinger=True,  # 볼린저 밴드 필터 활성화
        bandwidth_threshold=0.04,  # 볼린저 밴드폭 임계값 4%
        vwap_slope_period=5,  # VWAP 기울기 계산 기간 5
        adx_period=14,  # ADX 기간 14
        adx_threshold=25,  # ADX 임계값 25
        ma_period=200,  # 장기 이동평균 200기간
        use_trailing_stop=True,  # 트레일링 스톱 활성화
        trailing_stop_activation=3.0  # 3% 수익 달성 시 트레일링 스톱 시작
    )
    
    print("\n=== 강화된 VWAP 돌파 전략 백테스트 시작 ===")
    print(f"심볼: BTC/USDT")
    print(f"타임프레임: 15분")
    print(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"초기 자산: ${initial_balance:,.2f}")
    print("\n=== 전략 파라미터 ===")
    print(f"레버리지: 3x")
    print(f"손절: 5%, 이익실현: 15%")
    print(f"트레일링 스톱: 활성화 (3% 수익 달성 시 시작)")
    print("\n=== 추가 필터 ===")
    print(f"볼린저 밴드: 활성화 (밴드폭 임계값 4%)")
    print(f"VWAP 기울기: 기간 5, 임계값 0.1%")
    print(f"ADX: 기간 14, 임계값 25")
    print(f"장기 이동평균: 200기간")
    print("=" * 50)
    
    try:
        # 백테스트 실행
        result = backtester.run_backtest(
            strategy=vwap_strategy,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_balance=initial_balance,
            commission=0.001,  # 0.1% 수수료
            market_type='futures',
            leverage=3
        )
        
            # 결과 출력
        print("\n===== 백테스트 결과 상세 출력 =====\n")
        try:
            # 안전하게 결과 메트릭 출력
            if hasattr(result, 'metrics'):
                # 주요 지표 안전하게 출력
                metrics = result.metrics
                print(f"[주요 성과 지표]")
                print(f"총 수익: ${metrics.get('net_profit', 0):.2f}")
                print(f"총 수익률: {metrics.get('percent_return', 0):.2f}%")
                print(f"연간 수익률: {metrics.get('annual_return', 0):.2f}%")
                print(f"최대 낙폭: {metrics.get('max_drawdown', 0):.2f}%")
                print(f"샤프 비율: {metrics.get('sharpe_ratio', 0):.4f}")
                print(f"승률: {metrics.get('win_rate', 0):.2f}%")
                print(f"수익:손실 비율: {metrics.get('profit_factor', 0):.2f}")
                print(f"총 거래 횟수: {metrics.get('total_trades', 0)}")
                
                winning_trades = metrics.get('winning_trades', 0)
                losing_trades = metrics.get('losing_trades', 0)
                print(f"승리 거래: {winning_trades} | 손실 거래: {losing_trades}")
                
                # 거래 세부 정보 출력
                print("\n[상위 5개 거래 상세 정보]")
                if result.trades and len(result.trades) > 0:
                    # 최대 5개의 거래 출력
                    for i, trade in enumerate(result.trades[:5]):
                        print(f"\n거래 #{i+1}:")
                        print(f"  진입시간: {trade.get('entry_time', 'N/A')}")
                        print(f"  청산시간: {trade.get('exit_time', 'N/A')}")
                        print(f"  진입가격: ${trade.get('entry_price', 0):.2f}")
                        print(f"  청산가격: ${trade.get('exit_price', 0):.2f}")
                        print(f"  수량: {trade.get('quantity', 0):.6f}")
                        print(f"  손익: ${trade.get('profit', 0):.2f} ({trade.get('profit_percent', 0):.2f}%)")
                        if trade.get('market_type') == 'futures':
                            print(f"  레버리지: {trade.get('leverage', 1)}x")
                else:
                    print("  거래 기록이 없습니다.")
                    
                print("\n[거래 통계 요약]")
                print(f"평균 수익률: {metrics.get('avg_profit_percent', 0):.2f}%")
                print(f"최대 수익 거래: {metrics.get('max_profit_percent', 0):.2f}%")
                print(f"최대 손실 거래: {metrics.get('max_loss_percent', 0):.2f}%")
                
                # 전략 파라미터 재확인
                print("\n[전략 파라미터 설정]")
                print(f"레버리지: {result.leverage}x")
                print(f"손절: {vwap_strategy.stop_loss_pct}%, 이익실현: {vwap_strategy.take_profit_pct}%")
                print(f"볼린저 밴드: {'사용' if vwap_strategy.use_bollinger else '사용 안 함'}")
            else:
                print("백테스트 결과에 지표 정보가 없습니다.")
                
        except Exception as e:
            print(f"결과 출력 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
            # 포트폴리오 내역 출력
            if result.portfolio_history:
                final_balance = result.portfolio_history[-1].get('total_balance', 0)
                print(f"\n최종 잔액: ${final_balance:.2f}")
                
            # 거래 요약 출력
            if result.trades:
                print(f"\n거래 요약 (최근 5건):")
                for i, trade in enumerate(result.trades[-5:]):
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    pnl = trade.get('pnl', 0)
                    pnl_pct = trade.get('pnl_percent', 0)
                    print(f"거래 #{len(result.trades)-5+i+1}: 진입: ${entry_price:.2f}, 청산: ${exit_price:.2f}, PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
        
        # 성능 곡선 표시 (안전하게)
        try:
            plt.figure(figsize=(12, 8))
            if hasattr(result, 'plot_equity_curve'):
                result.plot_equity_curve(show=True)
        except Exception as e:
            logger.error(f"성능 곡선 표시 중 오류: {e}")
        
        # 월별 수익 표시 (안전하게)
        try:
            if hasattr(result, 'plot_monthly_returns'):
                result.plot_monthly_returns(show=True)
        except Exception as e:
            logger.error(f"월별 수익 표시 중 오류: {e}")
        
        # 거래 분포 표시 (안전하게)
        try:
            if hasattr(result, 'plot_trade_analysis'):
                result.plot_trade_analysis(show=True)
        except Exception as e:
            logger.error(f"거래 분포 표시 중 오류: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"백테스트 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    try:
        result = run_vwap_backtest()
    except KeyboardInterrupt:
        print("\n사용자에 의해 백테스트가 중지되었습니다.")
    except Exception as e:
        print(f"\n백테스트 실행 중 오류 발생: {e}")
        # 자세한 오류 추적 정보 출력
        import traceback
        traceback.print_exc()
