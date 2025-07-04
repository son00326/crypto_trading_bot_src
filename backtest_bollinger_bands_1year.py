#!/usr/bin/env python
"""
볼린저 밴드 전략의 1년치 백테스트 스크립트

다음 세 가지 시나리오로 테스트:
1. 레버리지 3배, 손절 4%, 이익실현 8% 
2. 레버리지 20배, 손절 10%, 이익실현 10%
3. 레버리지 40배, 손절 10%, 이익실현 10%
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
from tabulate import tabulate

from src.backtesting import Backtester
from src.strategies import BollingerBandsStrategy

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest_bollinger_bands')

def run_bollinger_bands_backtest(symbol="BTCUSDT", timeframe="4h", 
                              start_date=None, end_date=None,
                              leverage=3, stop_loss_pct=4.0, take_profit_pct=8.0,
                              scenario_name="기본 설정"):
    """
    볼린저 밴드 전략에 대한 백테스트를 실행하고 결과를 반환합니다.
    
    Args:
        symbol (str): 거래 심볼
        timeframe (str): 백테스트할 타임프레임
        start_date (str): 시작 날짜 (None이면 1년 전)
        end_date (str): 종료 날짜 (None이면 오늘)
        leverage (int): 레버리지 배수
        stop_loss_pct (float): 손절 비율(%)
        take_profit_pct (float): 이익실현 비율(%)
        scenario_name (str): 시나리오 이름
        
    Returns:
        object: 백테스트 결과
    """
    # 기간 설정 (기본값: 최근 1년)
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
    logger.info(f"===== 시나리오: {scenario_name} =====")
    logger.info(f"백테스트 기간: {start_date} ~ {end_date}")
    logger.info(f"레버리지: {leverage}x, 손절: {stop_loss_pct}%, 이익실현: {take_profit_pct}%")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance', 
        symbol=symbol, 
        timeframe=timeframe,
        market_type="futures",
        leverage=leverage
    )
    
    # 볼린저 밴드 전략 객체 생성
    strategy = BollingerBandsStrategy(
        stop_loss_pct=stop_loss_pct, 
        take_profit_pct=take_profit_pct, 
        leverage=leverage
    )
    
    logger.info(f"백테스트 실행 중...")
    
    # 백테스트 실행
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000,
        commission=0.001,
        market_type="futures",
        leverage=leverage
    )
    
    if result:
        logger.info(f"백테스트 완료!")
        return result
    else:
        logger.error(f"백테스트 실패!")
        return None

def format_result_summary(result, scenario_name):
    """
    백테스트 결과를 요약하여 출력합니다.
    
    Args:
        result: 백테스트 결과 객체
        scenario_name: 시나리오 이름
    """
    if result is None:
        return {
            'Scenario': scenario_name,
            'Total Return (%)': 'N/A',
            'Win Rate (%)': 'N/A',
            'Total Trades': 'N/A',
            'Max Drawdown (%)': 'N/A',
            'Sharpe Ratio': 'N/A',
            'Profit Factor': 'N/A',
            'Final Balance': 'N/A'
        }
    
    return {
        'Scenario': scenario_name,
        'Total Return (%)': f"{result.total_return:.2f}",
        'Win Rate (%)': f"{result.win_rate:.2f}",
        'Total Trades': result.total_trades,
        'Max Drawdown (%)': f"{result.max_drawdown:.2f}",
        'Sharpe Ratio': f"{result.sharpe_ratio:.2f}",
        'Profit Factor': f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else 'inf',
        'Final Balance': f"{result.final_balance:.2f}"
    }

def run_all_scenarios():
    """
    세 가지 시나리오 모두 실행하고 결과를 비교합니다.
    """
    scenarios = [
        {
            "name": "시나리오 1: 레버리지 3배, 손절 4%, 이익실현 8%",
            "leverage": 3,
            "stop_loss_pct": 4.0,
            "take_profit_pct": 8.0
        },
        {
            "name": "시나리오 2: 레버리지 3배, 손절 8%, 이익실현 10%",
            "leverage": 3,
            "stop_loss_pct": 8.0,
            "take_profit_pct": 10.0
        },
        {
            "name": "시나리오 3: 레버리지 20배, 손절 10%, 이익실현 10%",
            "leverage": 20,
            "stop_loss_pct": 10.0,
            "take_profit_pct": 10.0
        }
    ]
    
    results = []
    summary_data = []
    
    for scenario in scenarios:
        result = run_bollinger_bands_backtest(
            leverage=scenario['leverage'],
            stop_loss_pct=scenario['stop_loss_pct'],
            take_profit_pct=scenario['take_profit_pct'],
            scenario_name=scenario['name']
        )
        
        results.append(result)
        summary_data.append(format_result_summary(result, scenario['name']))
    
    # 결과 테이블 출력
    print("\n===== 백테스트 결과 요약 =====")
    print(tabulate(summary_data, headers="keys", tablefmt="grid"))
    
    # 상세 거래 정보 분석
    for i, result in enumerate(results):
        if result is not None and hasattr(result, 'trades') and result.trades is not None:
            print(f"\n===== {scenarios[i]['name']} 상세 분석 =====")
            
            # 수익/손실 거래 분리
            profit_trades = [trade.get('profit_percent', 0) for trade in result.trades if trade.get('profit_percent', 0) > 0]
            loss_trades = [trade.get('profit_percent', 0) for trade in result.trades if trade.get('profit_percent', 0) < 0]
            
            # 평균 수익/손실 계산
            avg_profit = sum(profit_trades) / len(profit_trades) if profit_trades else 0
            avg_loss = sum(loss_trades) / len(loss_trades) if loss_trades else 0
            print(f"평균 수익 거래: {avg_profit:.2f}%")
            print(f"평균 손실 거래: {avg_loss:.2f}%")
            
            # 최대 수익/손실 거래
            max_profit = max(profit_trades) if profit_trades else 0
            max_loss = min(loss_trades) if loss_trades else 0
            print(f"최대 수익 거래: {max_profit:.2f}%")
            print(f"최대 손실 거래: {max_loss:.2f}%")
            
            # 성과 지표 추가
            print(f"평균 거래당 수익: {result.total_return / result.total_trades:.2f}%")
            print(f"연간 수익률: {result.annual_return:.2f}%") if hasattr(result, 'annual_return') else None
    
    return results

if __name__ == "__main__":
    run_all_scenarios()
