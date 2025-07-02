#!/usr/bin/env python3
"""
볼린저 밴드 복합 선물 전략 백테스트 (15분봉, 3개월)
BollingerBandFuturesStrategy 사용
"""

import os
import sys
from datetime import datetime, timedelta

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtesting import Backtester
from src.strategies import BollingerBandFuturesStrategy

def run_bollinger_futures_backtest():
    """볼린저 밴드 복합 선물 전략 백테스트 실행"""
    
    print("\n=== 볼린저 밴드 복합 선물 전략 백테스트 시작 ===")
    print("전략: BollingerBandFuturesStrategy")
    print("구성: 볼린저 밴드 + RSI + MACD + 헤이킨 아시")
    print("시장: Binance Futures")
    print("심볼: BTC/USDT")
    print("타임프레임: 15분")
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='15m'  # 15분봉
    )
    
    # 백테스트 기간 설정 (최근 3개월)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"초기 자산: $10,000 USDT")
    print("=" * 70)
    
    # 다양한 파라미터 조합 테스트
    test_configs = [
        {
            'name': '기본 설정',
            'params': {
                'bb_period': 20,
                'bb_std': 2.0,
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'leverage': 5,
                'stop_loss_pct': 2.0,
                'take_profit_pct': 4.0,
                'timeframe': '15m'
            }
        },
        {
            'name': '공격적 설정',
            'params': {
                'bb_period': 14,
                'bb_std': 1.5,
                'rsi_period': 9,
                'rsi_overbought': 75,
                'rsi_oversold': 25,
                'leverage': 10,
                'stop_loss_pct': 1.5,
                'take_profit_pct': 3.0,
                'timeframe': '15m'
            }
        },
        {
            'name': '보수적 설정',
            'params': {
                'bb_period': 30,
                'bb_std': 2.5,
                'rsi_period': 21,
                'rsi_overbought': 65,
                'rsi_oversold': 35,
                'leverage': 3,
                'stop_loss_pct': 3.0,
                'take_profit_pct': 6.0,
                'timeframe': '15m'
            }
        }
    ]
    
    results = []
    
    for config in test_configs:
        try:
            print(f"\n📊 테스트 중: {config['name']}")
            print(f"   볼린저: {config['params']['bb_period']}일 / {config['params']['bb_std']}σ")
            print(f"   RSI: {config['params']['rsi_period']}일 / {config['params']['rsi_oversold']}-{config['params']['rsi_overbought']}")
            print(f"   레버리지: {config['params']['leverage']}x")
            print(f"   손절/익절: {config['params']['stop_loss_pct']}% / {config['params']['take_profit_pct']}%")
            
            # 전략 생성
            strategy = BollingerBandFuturesStrategy(**config['params'])
            
            # 백테스트 실행
            result = backtester.run_backtest(
                strategy=strategy,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                initial_balance=10000,
                commission=0.0005,  # 0.05% Maker 수수료
                market_type='futures',
                leverage=config['params']['leverage']
            )
            
            if result:
                # 결과 저장
                results.append({
                    'name': config['name'],
                    'params': config['params'],
                    'result': result
                })
                
                # 결과 출력
                print(f"\n💰 최종 잔액: ${result.final_balance:,.2f}")
                print(f"📈 총 수익률: {result.total_return:.2f}%")
                print(f"📅 연환산 수익률: {result.total_return * 4:.2f}%")
                print(f"🎯 승률: {result.win_rate:.2f}%")
                print(f"📉 최대 낙폭(MDD): {result.max_drawdown:.2f}%")
                print(f"📊 샤프 비율: {result.sharpe_ratio:.2f}")
                print(f"🔄 총 거래 횟수: {result.total_trades}")
                
                # 거래 분석
                if hasattr(result, 'trades') and result.trades:
                    winning_trades = [t for t in result.trades if t.get('profit', 0) > 0]
                    losing_trades = [t for t in result.trades if t.get('profit', 0) < 0]
                    
                    if winning_trades:
                        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades)
                        print(f"✅ 평균 수익: {avg_win:.2f}%")
                    
                    if losing_trades:
                        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades)
                        print(f"❌ 평균 손실: {avg_loss:.2f}%")
                
        except Exception as e:
            print(f"❗ 백테스트 오류: {e}")
            import traceback
            traceback.print_exc()
    
    # 결과 비교
    if results:
        print("\n\n=== 📊 백테스트 결과 종합 비교 ===")
        print(f"{'설정':20} {'수익률':>12} {'연환산':>12} {'MDD':>10} {'샤프':>10} {'승률':>10} {'거래수':>10}")
        print("-" * 95)
        
        for r in results:
            name = r['name']
            result = r['result']
            annual_return = result.total_return * 4
            print(f"{name:20} {result.total_return:>11.2f}% {annual_return:>11.2f}% "
                  f"{result.max_drawdown:>9.2f}% {result.sharpe_ratio:>9.2f} "
                  f"{result.win_rate:>9.2f}% {result.total_trades:>10}")
        
        # 최고 성과 찾기
        best_return = max(results, key=lambda x: x['result'].total_return)
        best_sharpe = max(results, key=lambda x: x['result'].sharpe_ratio)
        lowest_mdd = min(results, key=lambda x: x['result'].max_drawdown)
        
        print(f"\n🏆 최고 수익률: {best_return['name']} ({best_return['result'].total_return:.2f}%)")
        print(f"📊 최고 샤프비율: {best_sharpe['name']} ({best_sharpe['result'].sharpe_ratio:.2f})")
        print(f"🛡️ 최저 MDD: {lowest_mdd['name']} ({lowest_mdd['result'].max_drawdown:.2f}%)")
        
        # 최적 설정으로 차트 생성
        try:
            print("\n차트 생성 중...")
            best_result = best_return['result']
            best_result.plot_equity_curve(save_path='bollinger_futures_equity_curve.png')
            print("✅ 잔액 곡선 차트 저장: bollinger_futures_equity_curve.png")
            
            # 추가 차트 생성 시도
            try:
                best_result.plot_drawdown(save_path='bollinger_futures_drawdown.png')
                print("✅ 낙폭 차트 저장: bollinger_futures_drawdown.png")
            except:
                pass
                
        except Exception as e:
            print(f"차트 생성 실패: {e}")
    
    # 실전 거래 추천 사항
    print("\n\n=== 💡 실전 거래 추천 사항 ===")
    print("1. 15분봉은 노이즈가 많으므로 복합 지표 사용이 효과적")
    print("2. 레버리지는 5-10배 사이에서 변동성에 따라 조절")
    print("3. 손절매는 반드시 설정 (권장: 1.5-2%)")
    print("4. 익절은 손절의 2배 이상으로 설정하여 손익비 관리")
    print("5. 거래량이 많은 시간대(미국/유럽 시장)에 집중")
    print("6. 급격한 변동성 시장에서는 거래 자제")
    print("7. 데모 계정에서 충분히 테스트 후 실거래 시작")
    
    print("\n백테스트 완료! 🎉")

if __name__ == "__main__":
    run_bollinger_futures_backtest()
