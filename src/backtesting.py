"""
백테스팅 프레임워크 모듈 - 암호화폐 자동매매 봇

이 모듈은 거래 전략의 성능을 과거 데이터로 평가하는 백테스팅 기능을 제공합니다.
다양한 전략과 파라미터를 테스트하고 성능 지표를 계산합니다.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import os
import json
from datetime import datetime, timedelta
from tqdm import tqdm

from src.data_manager import DataManager
from src.data_collector import DataCollector
from src.strategies import (
    Strategy, MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, StochasticStrategy, BreakoutStrategy,
    VolatilityBreakoutStrategy, CombinedStrategy
)
from src.config import DATA_DIR, BACKTEST_PARAMS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtesting')

class BacktestResult:
    """백테스트 결과를 저장하고 분석하는 클래스"""
    
    def __init__(self, strategy_name, symbol, timeframe, start_date, end_date, initial_balance, market_type='spot', leverage=1):
        """
        백테스트 결과 초기화
        
        Args:
            strategy_name (str): 전략 이름
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
            start_date (str): 시작 날짜
            end_date (str): 종료 날짜
            initial_balance (float): 초기 자산
            market_type (str): 시장 유형 ('spot' 또는 'futures')
            leverage (int): 레버리지 배수 (선물 거래에만 적용)
        """
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.market_type = market_type
        self.leverage = leverage if market_type == 'futures' else 1
        
        # 거래 기록
        self.trades = []
        
        # 포트폴리오 기록
        self.portfolio_history = []
        
        # 성과 지표
        self.metrics = {}
        
        # 결과 저장 디렉토리
        self.results_dir = os.path.join(DATA_DIR, 'backtest_results')
        os.makedirs(self.results_dir, exist_ok=True)
    
    def add_trade(self, trade):
        """
        거래 기록 추가
        
        Args:
            trade (dict): 거래 정보
        """
        self.trades.append(trade)
    
    def add_portfolio_snapshot(self, snapshot):
        """
        포트폴리오 스냅샷 추가
        
        Args:
            snapshot (dict): 포트폴리오 스냅샷
        """
        self.portfolio_history.append(snapshot)
        
    # GUI에서 사용하는 속성들을 property로 정의
    @property
    def total_return(self):
        """총 수익률 (%)"""
        return self.metrics.get('percent_return', 0.0)
        
    @property
    def annual_return(self):
        """연간 수익률 (%)"""
        return self.metrics.get('annual_return', 0.0)
        
    @property
    def max_drawdown(self):
        """최대 낙폭 (%)"""
        return self.metrics.get('max_drawdown', 0.0)
        
    @property
    def win_rate(self):
        """승률 (%)"""
        return self.metrics.get('win_rate', 0.0)
        
    @property
    def total_trades(self):
        """총 거래 횟수"""
        return self.metrics.get('total_trades', 0)
        
    @property
    def average_holding_period(self):
        """평균 보유 기간 (일)"""
        return self.metrics.get('avg_holding_period', 0.0)
        
    @property
    def sharpe_ratio(self):
        """샤프 비율"""
        return self.metrics.get('sharpe_ratio', 0.0)
        
    @property
    def profit_factor(self):
        """손익비"""
        return self.metrics.get('profit_factor', 0.0)
        
    @property
    def max_consecutive_losses(self):
        """최대 연속 손실"""
        return self.metrics.get('max_consecutive_losses', 0)
        
    @property
    def max_consecutive_wins(self):
        """최대 연속 이익"""
        return self.metrics.get('max_consecutive_wins', 0)
        
    @property
    def equity_curve(self):
        """수익률 곡선 데이터프레임"""
        if hasattr(self, '_equity_curve') and self._equity_curve is not None:
            return self._equity_curve
        # 포트폴리오 히스토리가 있는 경우 수익률 곡선 만들기
        if self.portfolio_history:
            df = pd.DataFrame(self.portfolio_history)
            # 수익률 곡선 계산
            df['equity_curve'] = df['total_balance'] / self.initial_balance - 1
            
            # buy & hold 전략과 비교를 위한 계산
            # 'close' 컬럼이 있는지 확인하고 없으면 대안 사용
            if 'close' in df.columns:
                df['buy_hold_return'] = df['close'] / df['close'].iloc[0] - 1
            elif 'price' in df.columns:
                df['buy_hold_return'] = df['price'] / df['price'].iloc[0] - 1
            else:
                # close나 price 컬럼이 없을 경우, buy_hold_return은 계산하지 않음
                df['buy_hold_return'] = 0.0
                logger.warning("포트폴리오 데이터에 가격 정보가 없어 Buy & Hold 수익률을 계산할 수 없습니다.")
            
            self._equity_curve = df
            return df
        # 빈 데이터프레임 반환
        return pd.DataFrame(columns=['timestamp', 'equity_curve', 'buy_hold_return'])
        
    @property
    def trade_records(self):
        """거래 기록 데이터프레임"""
        if hasattr(self, '_trade_records') and self._trade_records is not None:
            return self._trade_records
        # 트레이드 기록이 있는 경우 데이터프레임 만들기
        if self.trades:
            df = pd.DataFrame(self.trades)
            # 수익률 계산
            df['return'] = df['profit'] / df['entry_amount']
            self._trade_records = df
            return df
        # 빈 데이터프레임 반환
        return pd.DataFrame(columns=['timestamp', 'type', 'entry_price', 'exit_price', 'amount', 'profit', 'return'])
        
    @property
    def final_balance(self):
        """최종 자산"""
        return self.metrics.get('final_balance', self.initial_balance)
    
    def calculate_metrics(self):
        """성과 지표 계산"""
        try:
            if not self.portfolio_history:
                logger.warning("포트폴리오 기록이 없어 성과 지표를 계산할 수 없습니다.")
                return
            
            # 포트폴리오 기록을 데이터프레임으로 변환
            df = pd.DataFrame(self.portfolio_history)
            
            # 기본 지표
            self.metrics['total_trades'] = len(self.trades)
            self.metrics['winning_trades'] = len([t for t in self.trades if t['profit'] > 0])
            self.metrics['losing_trades'] = len([t for t in self.trades if t['profit'] <= 0])
            
            if self.metrics['total_trades'] > 0:
                self.metrics['win_rate'] = self.metrics['winning_trades'] / self.metrics['total_trades'] * 100
            else:
                self.metrics['win_rate'] = 0
            
            # 수익성 지표
            self.metrics['initial_balance'] = self.initial_balance
            self.metrics['final_balance'] = df['total_balance'].iloc[-1] if not df.empty else self.initial_balance
            self.metrics['absolute_return'] = self.metrics['final_balance'] - self.metrics['initial_balance']
            self.metrics['percent_return'] = (self.metrics['final_balance'] / self.metrics['initial_balance'] - 1) * 100
            
            # 일일 수익률 계산
            df['daily_return'] = df['total_balance'].pct_change()
            
            # 연간 수익률 (CAGR)
            days = (pd.to_datetime(self.end_date) - pd.to_datetime(self.start_date)).days
            if days > 0:
                self.metrics['annual_return'] = ((1 + self.metrics['percent_return'] / 100) ** (365 / days) - 1) * 100
            else:
                self.metrics['annual_return'] = 0
            
            # 변동성 지표
            if len(df) > 1:
                self.metrics['volatility'] = df['daily_return'].std() * (252 ** 0.5) * 100  # 연간 변동성
                
                # 최대 낙폭 (MDD)
                df['cumulative_return'] = (1 + df['daily_return']).cumprod()
                df['cumulative_max'] = df['cumulative_return'].cummax()
                df['drawdown'] = (df['cumulative_max'] - df['cumulative_return']) / df['cumulative_max'] * 100
                self.metrics['max_drawdown'] = df['drawdown'].max()
                
                # 샤프 비율
                risk_free_rate = 0.02  # 2% 무위험 수익률 가정
                if self.metrics['volatility'] > 0:
                    self.metrics['sharpe_ratio'] = (self.metrics['annual_return'] - risk_free_rate) / self.metrics['volatility']
                else:
                    self.metrics['sharpe_ratio'] = 0
                
                # 칼마 비율
                if self.metrics['max_drawdown'] > 0:
                    self.metrics['calmar_ratio'] = self.metrics['annual_return'] / self.metrics['max_drawdown']
                else:
                    self.metrics['calmar_ratio'] = 0
            
            # 거래 지표
            if self.metrics['total_trades'] > 0:
                profits = [t['profit'] for t in self.trades]
                self.metrics['avg_profit'] = sum(profits) / len(profits)
                self.metrics['avg_profit_percent'] = sum(t['profit_percent'] for t in self.trades) / len(self.trades)
                
                winning_trades = [t for t in self.trades if t['profit'] > 0]
                losing_trades = [t for t in self.trades if t['profit'] <= 0]
                
                if winning_trades:
                    self.metrics['avg_win'] = sum(t['profit'] for t in winning_trades) / len(winning_trades)
                    self.metrics['avg_win_percent'] = sum(t['profit_percent'] for t in winning_trades) / len(winning_trades)
                    self.metrics['max_win'] = max(t['profit'] for t in winning_trades)
                    self.metrics['max_win_percent'] = max(t['profit_percent'] for t in winning_trades)
                
                if losing_trades:
                    self.metrics['avg_loss'] = sum(t['profit'] for t in losing_trades) / len(losing_trades)
                    self.metrics['avg_loss_percent'] = sum(t['profit_percent'] for t in losing_trades) / len(losing_trades)
                    self.metrics['max_loss'] = min(t['profit'] for t in losing_trades)
                    self.metrics['max_loss_percent'] = min(t['profit_percent'] for t in losing_trades)
                
                if winning_trades and losing_trades:
                    self.metrics['profit_factor'] = abs(sum(t['profit'] for t in winning_trades) / sum(t['profit'] for t in losing_trades)) if sum(t['profit'] for t in losing_trades) != 0 else float('inf')
            
            logger.info(f"성과 지표 계산 완료: {self.strategy_name}")
        
        except Exception as e:
            logger.error(f"성과 지표 계산 중 오류 발생: {e}")
    
    def plot_equity_curve(self, save_path=None, show=True):
        """
        자산 곡선 시각화
        
        Args:
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            if not self.portfolio_history:
                logger.warning("포트폴리오 기록이 없어 자산 곡선을 그릴 수 없습니다.")
                return
            
            # 포트폴리오 기록을 데이터프레임으로 변환
            df = pd.DataFrame(self.portfolio_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 자산 곡선 그리기
            plt.figure(figsize=(14, 8))
            
            # 총 자산 곡선
            plt.subplot(2, 1, 1)
            plt.plot(df.index, df['total_balance'], label='총 자산', color='blue', linewidth=2)
            plt.title(f"{self.symbol} {self.strategy_name} 백테스트 결과 ({self.start_date} ~ {self.end_date})", fontsize=14)
            plt.ylabel('자산 (USDT)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # 수익률 곡선
            plt.subplot(2, 1, 2)
            returns = (df['total_balance'] / self.initial_balance - 1) * 100
            plt.plot(df.index, returns, label='누적 수익률 (%)', color='green', linewidth=2)
            plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)
            plt.ylabel('수익률 (%)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"자산 곡선을 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"자산 곡선 생성 중 오류 발생: {e}")
            plt.close()
    
    def plot_drawdown_chart(self, save_path=None, show=True):
        """
        낙폭 차트 시각화
        
        Args:
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            if not self.portfolio_history:
                logger.warning("포트폴리오 기록이 없어 낙폭 차트를 그릴 수 없습니다.")
                return
            
            # 포트폴리오 기록을 데이터프레임으로 변환
            df = pd.DataFrame(self.portfolio_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 일일 수익률 계산
            df['daily_return'] = df['total_balance'].pct_change()
            
            # 누적 수익률 계산
            df['cumulative_return'] = (1 + df['daily_return']).cumprod()
            
            # 누적 최대값 계산
            df['cumulative_max'] = df['cumulative_return'].cummax()
            
            # 낙폭 계산
            df['drawdown'] = (df['cumulative_max'] - df['cumulative_return']) / df['cumulative_max'] * 100
            
            # 낙폭 차트 그리기
            plt.figure(figsize=(14, 6))
            plt.plot(df.index, df['drawdown'], color='red', linewidth=2)
            plt.fill_between(df.index, df['drawdown'], 0, color='red', alpha=0.3)
            plt.title(f"{self.symbol} {self.strategy_name} 낙폭 차트 ({self.start_date} ~ {self.end_date})", fontsize=14)
            plt.ylabel('낙폭 (%)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"낙폭 차트를 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"낙폭 차트 생성 중 오류 발생: {e}")
            plt.close()
    
    def plot_monthly_returns(self, save_path=None, show=True):
        """
        월별 수익률 히트맵 시각화
        
        Args:
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            if not self.portfolio_history:
                logger.warning("포트폴리오 기록이 없어 월별 수익률을 그릴 수 없습니다.")
                return
            
            # 포트폴리오 기록을 데이터프레임으로 변환
            df = pd.DataFrame(self.portfolio_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 일일 수익률 계산
            df['daily_return'] = df['total_balance'].pct_change()
            
            # 월별 수익률 계산
            monthly_returns = df['daily_return'].resample('M').apply(lambda x: (1 + x).prod() - 1) * 100
            
            # 연도와 월로 피벗 테이블 생성
            monthly_returns.index = monthly_returns.index.to_period('M')
            monthly_returns_table = monthly_returns.reset_index()
            monthly_returns_table['Year'] = monthly_returns_table['timestamp'].dt.year
            monthly_returns_table['Month'] = monthly_returns_table['timestamp'].dt.month
            monthly_returns_pivot = monthly_returns_table.pivot(index='Year', columns='Month', values='daily_return')
            
            # 월 이름 설정
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            monthly_returns_pivot.columns = [month_names[i-1] for i in monthly_returns_pivot.columns]
            
            # 히트맵 그리기
            plt.figure(figsize=(12, 8))
            sns.heatmap(monthly_returns_pivot, annot=True, fmt=".2f", cmap="RdYlGn", center=0, linewidths=1, cbar_kws={"label": "수익률 (%)"})
            plt.title(f"{self.symbol} {self.strategy_name} 월별 수익률 (%)", fontsize=14)
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"월별 수익률 히트맵을 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"월별 수익률 히트맵 생성 중 오류 발생: {e}")
            plt.close()
    
    def save_results(self):
        """백테스트 결과 저장"""
        try:
            # 결과 디렉토리 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_dir = os.path.join(self.results_dir, f"{self.symbol.replace('/', '_')}_{self.strategy_name}_{timestamp}")
            os.makedirs(result_dir, exist_ok=True)
            
            # 성과 지표 계산
            if not self.metrics:
                self.calculate_metrics()
            
            # 성과 지표 저장
            metrics_path = os.path.join(result_dir, 'metrics.json')
            with open(metrics_path, 'w') as f:
                json.dump(self.metrics, f, indent=4)
            
            # 거래 기록 저장
            trades_path = os.path.join(result_dir, 'trades.json')
            with open(trades_path, 'w') as f:
                json.dump(self.trades, f, indent=4)
            
            # 포트폴리오 기록 저장
            portfolio_path = os.path.join(result_dir, 'portfolio_history.json')
            with open(portfolio_path, 'w') as f:
                json.dump(self.portfolio_history, f, indent=4)
            
            # 차트 저장
            equity_curve_path = os.path.join(result_dir, 'equity_curve.png')
            self.plot_equity_curve(save_path=equity_curve_path, show=False)
            
            drawdown_path = os.path.join(result_dir, 'drawdown.png')
            self.plot_drawdown_chart(save_path=drawdown_path, show=False)
            
            monthly_returns_path = os.path.join(result_dir, 'monthly_returns.png')
            self.plot_monthly_returns(save_path=monthly_returns_path, show=False)
            
            logger.info(f"백테스트 결과를 {result_dir}에 저장했습니다.")
            return result_dir
        
        except Exception as e:
            logger.error(f"백테스트 결과 저장 중 오류 발생: {e}")
            return None

class Backtester:
    """거래 전략 백테스팅을 위한 클래스"""
    
    def __init__(self, exchange_id='binance', symbol='BTC/USDT', timeframe='1h', market_type='spot', leverage=1):
        """
        백테스터 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
            market_type (str): 시장 유형 ('spot' 또는 'futures')
            leverage (int): 레버리지 배수 (선물 거래에만 적용)
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.market_type = market_type
        self.leverage = leverage if market_type == 'futures' else 1
        
        # 데이터 관련 객체 초기화
        self.data_manager = DataManager(exchange_id=exchange_id, symbol=symbol)
        self.data_collector = DataCollector(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 백테스터가 초기화되었습니다. 시장 유형: {market_type}{', 레버리지: ' + str(leverage) + '배' if market_type == 'futures' else ''}")
    
    def prepare_data(self, start_date, end_date):
        """
        백테스트용 데이터 준비
        
        Args:
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
        
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            logger.info(f"{start_date}부터 {end_date}까지의 백테스트 데이터를 준비합니다.")
            
            # 데이터 로드
            # start_date와 end_date를 datetime 형식으로 변환
            start_date_dt = pd.to_datetime(start_date)
            end_date_dt = pd.to_datetime(end_date)
            
            logger.info(f"백테스트 기간: {start_date} ~ {end_date}")
            
            df = self.data_manager.load_ohlcv_data(timeframe=self.timeframe)
            
            if df is None or df.empty:
                logger.info("저장된 데이터가 없습니다. 과거 데이터를 가져옵니다.")
                df = self.data_collector.fetch_historical_data(start_date=start_date, end_date=end_date)
            else:
                # 날짜 형식이 일치하는지 확인
                if not isinstance(df.index, pd.DatetimeIndex):
                    logger.info("인덱스를 datetime 형식으로 변환합니다.")
                    df.index = pd.to_datetime(df.index)
                
                # 날짜 필터링 - datetime 객체로 비교
                df = df[(df.index >= start_date_dt) & (df.index <= end_date_dt)]
                
                # 데이터가 부족하면 추가 데이터 가져오기
                if df.empty or df.index.min() > start_date_dt or df.index.max() < end_date_dt:
                    logger.info("저장된 데이터가 부족합니다. 과거 데이터를 가져옵니다.")
                    df = self.data_collector.fetch_historical_data(start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                logger.warning("백테스트용 데이터를 준비하지 못했습니다.")
                return None
            
            logger.info(f"백테스트용 데이터 준비 완료: {len(df)}개의 데이터")
            return df
        
        except Exception as e:
            logger.error(f"백테스트용 데이터 준비 중 오류 발생: {e}")
            return None
    
    def run_backtest(self, strategy, start_date, end_date, initial_balance=10000, commission=0.001, market_type=None, leverage=None):
        """
        백테스트 실행
        
        Args:
            strategy: 거래 전략 객체
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
            initial_balance (float): 초기 자산
            commission (float): 수수료율
            market_type (str): 시장 유형 ('spot' 또는 'futures'), None이면 백테스터 초기화 값 사용
            leverage (int): 레버리지 배수, None이면 백테스터 초기화 값 사용
        
        Returns:
            BacktestResult: 백테스트 결과
        """
        try:
            # market_type과 leverage 값 처리
            actual_market_type = market_type if market_type is not None else self.market_type
            actual_leverage = leverage if leverage is not None else self.leverage
            
            logger.info(f"{strategy.name} 전략의 백테스트를 시작합니다. 시장 유형: {actual_market_type}{', 레버리지: ' + str(actual_leverage) + '배' if actual_market_type == 'futures' else ''}")
            
            # 데이터 준비
            df = self.prepare_data(start_date, end_date)
            
            if df is None or df.empty:
                logger.warning("백테스트를 실행할 데이터가 없습니다.")
                return None
            
            # 백테스트 결과 객체 초기화
            result = BacktestResult(
                strategy_name=strategy.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                market_type=actual_market_type,
                leverage=actual_leverage
            )
            
            # 전략에 따른 신호 생성
            df_with_signals = strategy.generate_signals(df)
            df_with_signals = strategy.calculate_positions(df_with_signals)
            
            # 백테스트 변수 초기화
            balance = initial_balance  # 현금 잔고
            position = 0  # 보유 수량
            position_value = 0  # 포지션 가치
            total_balance = initial_balance  # 총 자산
            
            # 거래 기록
            trades = []
            
            # 포트폴리오 기록
            portfolio_history = []
            
            # 현재 열린 거래
            current_trade = None
            
            # 각 캔들에 대해 백테스트 실행
            for i in tqdm(range(1, len(df_with_signals)), desc="백테스팅 진행 중"):
                # 현재 캔들
                current_candle = df_with_signals.iloc[i]
                prev_candle = df_with_signals.iloc[i-1]
                
                # 현재 가격
                current_price = current_candle['close']
                
                # 포지션 변경 확인
                position_change = current_candle['position']
                
                # 시장 유형과 레버리지 확인
                is_futures = actual_market_type == 'futures'
                leverage_multiplier = actual_leverage if is_futures else 1
                
                # 매수 신호
                if position_change > 0:
                    # 이미 포지션이 있는 경우 무시
                    if position > 0:
                        pass
                    else:
                        # 매수 가능한 수량 계산 (선물일 경우 레버리지 고려)
                        if is_futures:
                            # 선물일 경우 레버리지를 적용하여 더 큰 포지션 가능
                            buy_amount = (balance * leverage_multiplier) / current_price
                        else:
                            buy_amount = balance / current_price
                            
                        buy_value = buy_amount * current_price
                        fee = buy_value * commission
                        
                        # 수수료를 고려한 실제 매수 수량
                        actual_buy_amount = (balance - fee) / current_price
                        
                        # 포지션 업데이트
                        position = actual_buy_amount
                        position_value = position * current_price
                        balance = 0  # 모든 현금을 사용
                        
                        # 거래 기록
                        current_trade = {
                            'entry_time': current_candle.name.isoformat(),
                            'entry_price': current_price,
                            'quantity': position,
                            'entry_amount': buy_value,  # 매수 금액 추가 (수익률 계산에 필요)
                            'side': 'long',
                            'status': 'open',
                            'entry_balance': total_balance
                        }
                
                # 매도 신호
                elif position_change < 0:
                    # 포지션이 없는 경우 무시
                    if position == 0:
                        pass
                    else:
                        # 매도 가치 계산
                        sell_value = position * current_price
                        fee = sell_value * commission
                        
                        # 수수료를 고려한 실제 매도 가치
                        actual_sell_value = sell_value - fee
                        
                        # 포지션 업데이트
                        balance = actual_sell_value
                        position_value = 0
                        
                        # 거래 기록 업데이트
                        if current_trade:
                            current_trade['exit_time'] = current_candle.name.isoformat()
                            current_trade['exit_price'] = current_price
                            current_trade['status'] = 'closed'
                            current_trade['exit_balance'] = balance
                            current_trade['profit'] = balance - current_trade['entry_balance']
                            
                            # 기본 수익률 계산
                            base_profit_percent = (balance / current_trade['entry_balance'] - 1) * 100
                            
                            # 선물 거래의 경우 레버리지를 고려한 수익률 표시
                            if is_futures:
                                current_trade['leverage'] = leverage_multiplier
                                current_trade['market_type'] = 'futures'
                            else:
                                current_trade['market_type'] = 'spot'
                                
                            current_trade['profit_percent'] = base_profit_percent
                            
                            trades.append(current_trade)
                            result.add_trade(current_trade)
                            
                            current_trade = None
                        
                        position = 0
                
                # 포트폴리오 가치 업데이트 (NumPy 배열 기반으로 계산)
                # 변수들이 pandas 시리즈인 경우를 대비하여 NumPy 값으로 변환
                position_float = float(position) if hasattr(position, '__iter__') else position
                current_price_float = float(current_price) if hasattr(current_price, '__iter__') else current_price
                balance_float = float(balance) if hasattr(balance, '__iter__') else balance
                
                position_value = position_float * current_price_float
                total_balance = balance_float + position_value
                
                # 포트폴리오 스냅샷 저장
                portfolio_snapshot = {
                    'timestamp': current_candle.name.isoformat(),
                    'open': current_candle['open'],
                    'high': current_candle['high'],
                    'low': current_candle['low'],
                    'close': current_price,  # 'close'로 정확히 저장
                    'volume': current_candle['volume'] if 'volume' in current_candle else 0,
                    'price': current_price,  # 후방 호환성을 위해 'price'도 유지
                    'balance': balance,
                    'position': position,
                    'position_value': position_value,
                    'total_balance': total_balance,
                    'signal': current_candle['signal'] if 'signal' in current_candle else 0,
                    'position_change': position_change,
                    'market_type': actual_market_type,
                    'leverage': leverage_multiplier
                }
                
                portfolio_history.append(portfolio_snapshot)
                result.add_portfolio_snapshot(portfolio_snapshot)
            
            # 백테스트 결과 계산
            result.calculate_metrics()
            
            logger.info(f"{strategy.name} 전략의 백테스트가 완료되었습니다.")
            return result
        
        except Exception as e:
            logger.error(f"백테스트 실행 중 오류 발생: {e}")
            return None
    
    def optimize_strategy(self, strategy_class, param_grid, start_date, end_date, initial_balance=10000, commission=0.001):
        """
        전략 파라미터 최적화
        
        Args:
            strategy_class: 전략 클래스
            param_grid (dict): 파라미터 그리드
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
            initial_balance (float): 초기 자산
            commission (float): 수수료율
        
        Returns:
            tuple: (최적 파라미터, 최적 결과)
        """
        try:
            logger.info(f"{strategy_class.__name__} 전략의 파라미터 최적화를 시작합니다.")
            
            # 데이터 준비
            df = self.prepare_data(start_date, end_date)
            
            if df is None or df.empty:
                logger.warning("최적화를 실행할 데이터가 없습니다.")
                return None, None
            
            # 파라미터 조합 생성
            import itertools
            param_names = list(param_grid.keys())
            param_values = list(param_grid.values())
            param_combinations = list(itertools.product(*param_values))
            
            logger.info(f"총 {len(param_combinations)}개의 파라미터 조합을 테스트합니다.")
            
            # 최적 결과 초기화
            best_result = None
            best_params = None
            best_metric = -float('inf')  # 최대화할 지표 (예: 수익률)
            
            # 각 파라미터 조합에 대해 백테스트 실행
            for i, param_combination in enumerate(param_combinations):
                # 파라미터 딕셔너리 생성
                params = dict(zip(param_names, param_combination))
                
                # 전략 객체 생성
                strategy = strategy_class(**params)
                
                # 백테스트 실행
                result = self.run_backtest(
                    strategy=strategy,
                    start_date=start_date,
                    end_date=end_date,
                    initial_balance=initial_balance,
                    commission=commission
                )
                
                if result:
                    # 최적화 지표 (예: 샤프 비율)
                    metric = result.metrics.get('sharpe_ratio', 0)
                    
                    logger.info(f"파라미터 {params}: 샤프 비율 = {metric:.4f}, 수익률 = {result.metrics.get('percent_return', 0):.2f}%")
                    
                    # 최적 결과 업데이트
                    if metric > best_metric:
                        best_metric = metric
                        best_result = result
                        best_params = params
            
            if best_result:
                logger.info(f"최적 파라미터: {best_params}, 샤프 비율: {best_metric:.4f}")
                return best_params, best_result
            else:
                logger.warning("최적화에 실패했습니다.")
                return None, None
        
        except Exception as e:
            logger.error(f"전략 최적화 중 오류 발생: {e}")
            return None, None
    
    def compare_strategies(self, strategies, start_date, end_date, initial_balance=10000, commission=0.001):
        """
        여러 전략 비교
        
        Args:
            strategies (list): 전략 객체 리스트
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str): 종료 날짜 (YYYY-MM-DD 형식)
            initial_balance (float): 초기 자산
            commission (float): 수수료율
        
        Returns:
            dict: 전략별 백테스트 결과
        """
        try:
            logger.info(f"{len(strategies)}개 전략의 비교를 시작합니다.")
            
            # 결과 저장
            results = {}
            
            # 각 전략에 대해 백테스트 실행
            for strategy in strategies:
                result = self.run_backtest(
                    strategy=strategy,
                    start_date=start_date,
                    end_date=end_date,
                    initial_balance=initial_balance,
                    commission=commission
                )
                
                if result:
                    results[strategy.name] = result
            
            if results:
                # 결과 비교
                comparison = {}
                for name, result in results.items():
                    comparison[name] = {
                        'return': result.metrics.get('percent_return', 0),
                        'sharpe': result.metrics.get('sharpe_ratio', 0),
                        'max_drawdown': result.metrics.get('max_drawdown', 0),
                        'win_rate': result.metrics.get('win_rate', 0)
                    }
                
                # 결과 출력
                comparison_df = pd.DataFrame(comparison).T
                logger.info(f"전략 비교 결과:\n{comparison_df}")
                
                # 전략 성능 시각화
                self.plot_strategy_comparison(results)
                
                return results
            else:
                logger.warning("비교할 결과가 없습니다.")
                return {}
        
        except Exception as e:
            logger.error(f"전략 비교 중 오류 발생: {e}")
            return {}
    
    def plot_strategy_comparison(self, results, save_path=None, show=True):
        """
        여러 전략의 성능 비교 시각화
        
        Args:
            results (dict): 전략별 백테스트 결과
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            if not results:
                logger.warning("비교할 결과가 없습니다.")
                return
            
            # 자산 곡선 비교
            plt.figure(figsize=(14, 8))
            
            for name, result in results.items():
                if result.portfolio_history:
                    df = pd.DataFrame(result.portfolio_history)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    
                    # 수익률 계산
                    returns = (df['total_balance'] / result.initial_balance - 1) * 100
                    plt.plot(df.index, returns, label=name, linewidth=2)
            
            plt.title(f"전략 비교: 누적 수익률 ({list(results.values())[0].start_date} ~ {list(results.values())[0].end_date})", fontsize=14)
            plt.ylabel('누적 수익률 (%)', fontsize=12)
            plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"전략 비교 차트를 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
            
            # 성과 지표 비교
            metrics = ['percent_return', 'annual_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
            metrics_data = {}
            
            for name, result in results.items():
                metrics_data[name] = {metric: result.metrics.get(metric, 0) for metric in metrics}
            
            metrics_df = pd.DataFrame(metrics_data)
            
            # 성과 지표 시각화
            plt.figure(figsize=(14, 10))
            
            for i, metric in enumerate(metrics):
                plt.subplot(len(metrics), 1, i+1)
                plt.bar(metrics_df.columns, metrics_df.loc[metric], color='skyblue')
                plt.title(f"{metric}", fontsize=12)
                plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                metrics_path = save_path.replace('.png', '_metrics.png')
                plt.savefig(metrics_path, dpi=300, bbox_inches='tight')
                logger.info(f"성과 지표 비교 차트를 {metrics_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"전략 비교 시각화 중 오류 발생: {e}")
            plt.close()

# 테스트 코드
if __name__ == "__main__":
    # 백테스터 초기화
    backtester = Backtester(exchange_id='binance', symbol='BTC/USDT', timeframe='1d')
    
    # 백테스트 기간 설정
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')  # 1년 전
    
    # 전략 생성
    strategies = [
        MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'),
        RSIStrategy(period=14, overbought=70, oversold=30),
        MACDStrategy(),
        BollingerBandsStrategy()
    ]
    
    # 단일 전략 백테스트
    result = backtester.run_backtest(
        strategy=strategies[0],
        start_date=start_date,
        end_date=end_date,
        initial_balance=10000,
        commission=0.001
    )
    
    if result:
        # 결과 시각화
        result.plot_equity_curve()
        result.plot_drawdown_chart()
        result.plot_monthly_returns()
        
        # 결과 저장
        result.save_results()
        
        # 성과 지표 출력
        print("\n백테스트 결과:")
        for key, value in result.metrics.items():
            print(f"  {key}: {value}")
    
    # 전략 비교
    results = backtester.compare_strategies(
        strategies=strategies,
        start_date=start_date,
        end_date=end_date
    )
    
    # 전략 최적화
    param_grid = {
        'short_period': [5, 9, 14],
        'long_period': [20, 26, 50],
        'ma_type': ['sma', 'ema']
    }
    
    best_params, best_result = backtester.optimize_strategy(
        strategy_class=MovingAverageCrossover,
        param_grid=param_grid,
        start_date=start_date,
        end_date=end_date
    )
    
    if best_result:
        print("\n최적 파라미터:")
        for key, value in best_params.items():
            print(f"  {key}: {value}")
        
        print("\n최적 전략 성과:")
        for key, value in best_result.metrics.items():
            print(f"  {key}: {value}")
