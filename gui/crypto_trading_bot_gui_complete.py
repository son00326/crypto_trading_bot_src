#!/usr/bin/env python3
# crypto_trading_bot_gui.py
# 암호화폐 자동 매매 봇 GUI 버전
import sys
import os

# 모듈 검색 경로에 상위 디렉토리 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import numpy as np
import ccxt
import time
import logging
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# 백테스팅 모듈 임포트
from src.backtesting import Backtester
from src.trading_algorithm import TradingAlgorithm
from src.db_manager import DatabaseManager
from src.strategies import (
    Strategy, MovingAverageCrossover, RSIStrategy, MACDStrategy, 
    BollingerBandsStrategy, StochasticStrategy, BollingerBandFuturesStrategy
)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
QHBoxLayout,
QLabel, QPushButton, QComboBox, QLineEdit, QTextEdit,
QCheckBox, QGroupBox, QFormLayout, QDoubleSpinBox,
QSpinBox, QScrollArea, QTableWidget, QTableWidgetItem,
QTabWidget, QFileDialog, QMessageBox, QDateEdit, QHeaderView, QSizePolicy)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QDate
from PyQt5.QtGui import QFont, QIcon

# 지갑 잔액 위젯 임포트
from gui.wallet_balance_widget import WalletBalanceWidget

# 로깅 설정
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
handlers=[
logging.FileHandler("trading_bot.log"),
logging.StreamHandler()
]
)
logger = logging.getLogger('trading_bot')

# 기술적 지표 함수들
def simple_moving_average(df, period=20, column='close'):
    return df[column].rolling(window=period).mean()

def exponential_moving_average(df, period=20, column='close'):
    return df[column].ewm(span=period, adjust=False).mean()

def relative_strength_index(df, period=14, column='close'):
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def moving_average_convergence_divergence(df, fast_period=12, slow_period=26,
signal_period=9, column='close'):
    fast_ema = exponential_moving_average(df, period=fast_period, column=column)
    slow_ema = exponential_moving_average(df, period=slow_period, column=column)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(df, period=20, std_dev=2, column='close'):
    middle_band = simple_moving_average(df, period=period, column=column)
    std = df[column].rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return middle_band, upper_band, lower_band

# src.strategies 모듈에서 이미 임포트된 전략 클래스들을 사용하므로 중복 정의 제거

class DataCollector:
    """데이터 수집 클래스"""
    def __init__(self, exchange='binance'):
        self.exchange_id = exchange
        self.exchange = getattr(ccxt, exchange)({
            'enableRateLimit': True,
        })
        logger.info(f"{exchange} 거래소에 연결되었습니다.")
    
    def get_historical_data(self, symbol, timeframe='1d', limit=500):
        """
        과거 OHLCV 데이터 가져오기
        Args:
            symbol (str): 거래 쌍 (예: 'BTC/USDT')
            timeframe (str): 타임프레임 (예: '1m', '1h', '1d')
            limit (int): 가져올 캔들 수
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            logger.info(f"{symbol} {timeframe} 데이터 {len(df)}개 수집 완료")
            return df
        except Exception as e:
            logger.error(f"데이터 수집 중 오류 발생: {e}")
            return pd.DataFrame()

class RiskManager:
    """위험 관리 클래스"""
    def __init__(self, stop_loss_pct=0.05, take_profit_pct=0.1, max_position_size=0.2):
        """
        위험 관리 초기화
        Args:
            stop_loss_pct (float): 손절매 비율 (예: 0.05 = 5%)
            take_profit_pct (float): 이익실현 비율 (예: 0.1 = 10%)
            max_position_size (float): 최대 포지션 크기 (계좌 자산의 비율)
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_position_size = max_position_size
        logger.info(f"위험 관리 설정: 손절매 {stop_loss_pct*100}%, 이익실현 {take_profit_pct*100}%, 최대 포지션 {max_position_size*100}%")
    
    def calculate_position_size(self, account_balance, current_price, risk_per_trade=0.01):
        """
        포지션 크기 계산
        Args:
            account_balance (float): 계좌 잔고
            current_price (float): 현재 가격
            risk_per_trade (float): 거래당 위험 비율 (예: 0.01 = 1%)
        Returns:
            float: 포지션 크기 (코인 수량)
        """
        risk_amount = account_balance * risk_per_trade
        position_size = risk_amount / (current_price * self.stop_loss_pct)
        
        # 최대 포지션 크기 제한
        max_size = (account_balance * self.max_position_size) / current_price
        position_size = min(position_size, max_size)
        
        return position_size
    
    def calculate_stop_loss(self, entry_price, position_type='long'):
        """
        손절매 가격 계산
        Args:
            entry_price (float): 진입 가격
            position_type (str): 포지션 유형 ('long' 또는 'short')
        Returns:
            float: 손절매 가격
        """
        if position_type.lower() == 'long':
            return entry_price * (1 - self.stop_loss_pct)
        else: # short
            return entry_price * (1 + self.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price, position_type='long'):
        """
        이익실현 가격 계산
        Args:
            entry_price (float): 진입 가격
            position_type (str): 포지션 유형 ('long' 또는 'short')
        Returns:
            float: 이익실현 가격
        """
        if position_type.lower() == 'long':
            return entry_price * (1 + self.take_profit_pct)
        else: # short
            return entry_price * (1 - self.take_profit_pct)
class TradingBot:
    """자동 매매 봇 클래스"""
    def __init__(self, exchange='binance', api_key=None, api_secret=None,
                 strategy=None, symbol='BTC/USDT', timeframe='1h',
                 risk_manager=None, test_mode=True, market_type='spot', leverage=1):
        """
        자동 매매 봇 초기화
        Args:
            exchange (str): 거래소 이름
            api_key (str): API 키
            api_secret (str): API 시크릿
            strategy (Strategy): 거래 전략
            symbol (str): 거래 쌍
            timeframe (str): 타임프레임
            risk_manager (RiskManager): 위험 관리 객체
            test_mode (bool): 테스트 모드 여부
            market_type (str): 시장 유형 ('spot' 또는 'futures')
            leverage (int): 레버리지 (선물 거래에만 적용)
        """
        self.exchange_id = exchange
        self.exchange = getattr(ccxt, exchange)({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.test_mode = test_mode
        self.market_type = market_type
        self.leverage = leverage
        
        if risk_manager is None:
            self.risk_manager = RiskManager()
        else:
            self.risk_manager = risk_manager
        
        self.data_collector = DataCollector(exchange)
        self.position = {
            'type': None, # 'long' 또는 'short'
            'size': 0,
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0
        }
        
        logger.info(f"자동 매매 봇 초기화 완료: {exchange}, {symbol}, {timeframe}, 테스트 모드: {test_mode}, 시장 유형: {market_type}, 레버리지: {leverage}")
    
    def get_account_balance(self):
        """계좌 잔고 조회"""
        try:
            if self.test_mode:
                return 10000  # 테스트 모드에서는 가상의 잔고 사용
            
            balance = self.exchange.fetch_balance()
            quote_currency = self.symbol.split('/')[1]
            return balance[quote_currency]['free']
        except Exception as e:
            logger.error(f"잔고 조회 중 오류 발생: {e}")
            return 0
    
    def get_current_price(self):
        """현재 가격 조회"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"가격 조회 중 오류 발생: {e}")
            return 0
    
    def execute_order(self, order_type, size):
        """주문 실행"""
        try:
            if self.test_mode:
                logger.info(f"[테스트 모드] {order_type} 주문 실행: {self.symbol}, 수량: {size}, 시장 유형: {self.market_type}, 레버리지: {self.leverage}")
                return {'id': 'test_order', 'price': self.get_current_price()}
            
            # 선물 거래일 경우 레버리지 파라미터 추가
            params = {}
            if self.market_type == 'futures':
                params['leverage'] = self.leverage
            
            if order_type == 'buy':
                order = self.exchange.create_market_buy_order(self.symbol, size, params=params)
            elif order_type == 'sell':
                order = self.exchange.create_market_sell_order(self.symbol, size, params=params)
            else:
                raise ValueError(f"지원하지 않는 주문 유형입니다: {order_type}")
            
            logger.info(f"주문 실행 완료: {order_type}, {self.symbol}, 수량: {size}, 주문 ID: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"주문 실행 중 오류 발생: {e}")
            return None
    
    def update_position(self, position_type, size, price):
        """포지션 업데이트"""
        self.position['type'] = position_type
        self.position['size'] = size
        self.position['entry_price'] = price
        
        if position_type == 'long':
            self.position['stop_loss'] = self.risk_manager.calculate_stop_loss(price, 'long')
            self.position['take_profit'] = self.risk_manager.calculate_take_profit(price, 'long')
        elif position_type == 'short':
            self.position['stop_loss'] = self.risk_manager.calculate_stop_loss(price, 'short')
            self.position['take_profit'] = self.risk_manager.calculate_take_profit(price, 'short')
        
        logger.info(f"포지션 업데이트: {position_type}, 수량: {size}, 가격: {price}, SL: {self.position['stop_loss']}, TP: {self.position['take_profit']}")
    
    def close_position(self):
        """포지션 종료"""
        if self.position['type'] is None or self.position['size'] == 0:
            return
        
        order_type = 'sell' if self.position['type'] == 'long' else 'buy'
        order = self.execute_order(order_type, self.position['size'])
        
        if order:
            logger.info(f"포지션 종료: {self.position['type']}, 수량: {self.position['size']}, 가격: {order['price']}")
            self.position = {
                'type': None,
                'size': 0,
                'entry_price': 0,
                'stop_loss': 0,
                'take_profit': 0
            }
    
    def check_exit_conditions(self, current_price):
        """종료 조건 확인"""
        if self.position['type'] is None or self.position['size'] == 0:
            return False
        
        # 손절매 확인
        if self.position['type'] == 'long' and current_price <= self.position['stop_loss']:
            logger.info(f"손절매 조건 충족: 현재 가격 {current_price} <= 손절매 가격 {self.position['stop_loss']}")
            return True
        if self.position['type'] == 'short' and current_price >= self.position['stop_loss']:
            logger.info(f"손절매 조건 충족: 현재 가격 {current_price} >= 손절매 가격 {self.position['stop_loss']}")
            return True
        
        # 이익실현 확인
        if self.position['type'] == 'long' and current_price >= self.position['take_profit']:
            logger.info(f"이익실현 조건 충족: 현재 가격 {current_price} >= 이익실현 가격 {self.position['take_profit']}")
            return True
        if self.position['type'] == 'short' and current_price <= self.position['take_profit']:
            logger.info(f"이익실현 조건 충족: 현재 가격 {current_price} <= 이익실현 가격 {self.position['take_profit']}")
            return True
        
        return False
    
    def run_once(self):
        """한 번의 거래 주기 실행"""
        try:
            # 데이터 수집
            df = self.data_collector.get_historical_data(self.symbol, self.timeframe)
            if df.empty:
                logger.error("데이터 수집 실패")
                return
            
            # 신호 생성
            df = self.strategy.generate_signals(df)
            
            # 현재 가격 조회
            current_price = self.get_current_price()
            if current_price == 0:
                logger.error("현재 가격 조회 실패")
                return
            
            # 종료 조건 확인
            if self.check_exit_conditions(current_price):
                self.close_position()
            
            # 마지막 신호 확인
            last_signal = df['signal'].iloc[-1]
            
            # 포지션이 없는 경우 신호에 따라 진입
            if self.position['type'] is None:
                if last_signal == 1:  # 매수 신호
                    account_balance = self.get_account_balance()
                    position_size = self.risk_manager.calculate_position_size(account_balance, current_price)
                    order = self.execute_order('buy', position_size)
                    if order:
                        self.update_position('long', position_size, current_price)
                elif last_signal == -1:  # 매도 신호 (숏 포지션)
                    # 현물 거래에서는 숏 포지션을 사용하지 않음
                    pass
            
            # 포지션이 있는 경우 반대 신호에 따라 종료
            elif self.position['type'] == 'long' and last_signal == -1:
                self.close_position()
            elif self.position['type'] == 'short' and last_signal == 1:
                self.close_position()
            
            logger.info(f"거래 주기 실행 완료: 현재 가격 {current_price}, 신호 {last_signal}, 포지션 {self.position['type']}")
        
        except Exception as e:
            logger.error(f"거래 주기 실행 중 오류 발생: {e}")
    
    def start(self, interval=3600):
        """자동 매매 시작"""
        logger.info(f"자동 매매 시작: {self.symbol}, {self.timeframe}, 간격: {interval}초")
        try:
            while True:
                self.run_once()
                logger.info(f"{interval}초 대기 중...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("사용자에 의해 자동 매매가 중지되었습니다.")
        except Exception as e:
            logger.error(f"자동 매매 중 오류 발생: {e}")
        finally:
            # 종료 시 포지션 정리
            if not self.test_mode and self.position['type'] is not None:
                logger.info("종료 전 포지션 정리 중...")
                self.close_position()

# 봇 실행을 위한 스레드
class BotThread(QThread):
    update_signal = pyqtSignal(str)
    
    def __init__(self, bot, interval, auto_sl_tp=False, partial_tp=False, strategy_params=None):
        super().__init__()
        self.bot = bot
        self.interval = interval
        self.running = True
        self.auto_sl_tp = auto_sl_tp
        self.partial_tp = partial_tp
        self.strategy_params = strategy_params or {}
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
        # 트레이딩 알고리즘 초기화
        self.algo = None
        if hasattr(self.bot, 'exchange_id') and hasattr(self.bot, 'symbol') and hasattr(self.bot, 'timeframe'):
            self.init_trading_algorithm()
    
    def init_trading_algorithm(self):
        """트레이딩 알고리즘 초기화"""
        try:
            # 봇에서 market_type과 leverage 가져오기 (없으면 기본값 사용)
            market_type = getattr(self.bot, 'market_type', 'spot')
            leverage = getattr(self.bot, 'leverage', 1)
            
            # 현재 봇의 설정을 사용하여 트레이딩 알고리즘 초기화
            self.algo = TradingAlgorithm(
                exchange_id=self.bot.exchange_id,
                symbol=self.bot.symbol,
                timeframe=self.bot.timeframe,
                strategy=self.bot.strategy,
                test_mode=self.bot.test_mode,
                restore_state=True,  # 이전 상태 복원
                strategy_params=self.strategy_params,  # 전략별 세부 파라미터 전달
                market_type=market_type,  # 시장 타입 추가
                leverage=leverage  # 레버리지 추가
            )
            
            # 적용된 전략 파라미터 로깅
            if self.strategy_params:
                self.update_signal.emit(f"전략 파라미터 적용: {self.strategy_params}")
            
            # 시장 타입과 레버리지 정보 로깅
            self.update_signal.emit(f"시장 타입: {market_type}, 레버리지: {leverage}x")
            
            # 자동 손절매/이익실현 설정
            if self.auto_sl_tp:
                # auto_position_manager가 초기화되었는지 확인
                if hasattr(self.algo, 'auto_position_manager') and self.algo.auto_position_manager is not None:
                    try:
                        self.algo.auto_position_manager.set_auto_sl_tp(True)
                        self.algo.auto_position_manager.set_partial_tp(self.partial_tp)
                        self.algo.auto_position_manager.start_monitoring()
                        self.update_signal.emit(f"자동 손절매/이익실현 기능 활성화 (부분 청산: {self.partial_tp})")
                    except Exception as e:
                        self.update_signal.emit(f"자동 손절매/이익실현 기능 활성화 오류: {e}")
                else:
                    self.update_signal.emit("경고: 자동 손절매/이익실현 기능을 활성화할 수 없습니다 (auto_position_manager 없음)")
            
            self.update_signal.emit(f"트레이딩 알고리즘 초기화 완료: {self.bot.symbol} ({self.bot.strategy})")
        except Exception as e:
            self.update_signal.emit(f"트레이딩 알고리즘 초기화 오류: {e}")
    
    def run(self):
        self.update_signal.emit("자동 매매 봇이 시작되었습니다.")
        
        # 이전 거래 상태 복원
        self.restore_trading_state()
        
        try:
            # TradingAlgorithm 초기화 확인
            if self.algo is None:
                self.update_signal.emit("트레이딩 알고리즘이 초기화되지 않았습니다. 재시도 중...")
                self.init_trading_algorithm()
                if self.algo is None:
                    self.update_signal.emit("트레이딩 알고리즘 초기화 실패")
                    return
            
            # TradingAlgorithm의 거래 스레드 시작
            self.algo.trading_active = True
            self.algo.start_trading_thread(interval=self.interval)
            self.update_signal.emit(f"트레이딩 알고리즘 거래 스레드 시작됨 (간격: {self.interval}초)")
            
            # 메인 루프 - 상태 모니터링 및 로그 업데이트
            while self.running:
                # 상태 업데이트 (간격을 더 짧게 설정하여 반응성 향상)
                monitoring_interval = min(self.interval, 60)  # 최대 60초마다 상태 체크
                
                # 현재 잔액 조회 및 업데이트
                try:
                    balance_info = self.algo.exchange_api.get_balance()
                    if balance_info and 'balance' in balance_info:
                        total_balance = balance_info['balance']
                        currency = balance_info.get('currency', 'USDT')
                        self.update_signal.emit(f"잔액: {total_balance:.2f} {currency}")
                except Exception as e:
                    logger.debug(f"잔액 조회 중 오류: {str(e)}")
                
                # 포지션 정보 업데이트
                try:
                    positions = self.algo.exchange_api.get_positions(self.algo.symbol)
                    if positions:
                        for pos in positions:
                            self.update_signal.emit(
                                f"포지션: {pos.get('symbol')} {pos.get('side')} "
                                f"수량: {pos.get('contracts', 0)} 진입가: {pos.get('entry_price', 0)}"
                            )
                except Exception as e:
                    logger.debug(f"포지션 조회 중 오류: {str(e)}")
                
                # 로그 업데이트
                try:
                    with open("trading_bot.log", "r") as f:
                        logs = f.readlines()
                        if logs:
                            # 최근 로그만 표시 (마지막 10줄)
                            recent_logs = logs[-10:]
                            for log in recent_logs:
                                if "거래 신호" in log or "주문 실행" in log or "ERROR" in log:
                                    self.update_signal.emit(f"[LOG] {log.strip()}")
                except:
                    pass
                
                # 거래 활성 상태 확인
                if not self.algo.trading_active:
                    self.update_signal.emit("거래 스레드가 중지되었습니다.")
                    break
                
                # 대기
                for i in range(monitoring_interval):
                    if not self.running:
                        break
                    self.sleep(1)
                
        except Exception as e:
            logger.error(f"봇 실행 중 오류 발생: {e}")
            self.update_signal.emit(f"오류: {str(e)}")
        
        finally:
            # 거래 스레드 중지
            if self.algo:
                self.algo.stop_trading_thread()
                self.update_signal.emit("거래 스레드 중지됨")
        
        self.update_signal.emit("자동 매매 봇이 중지되었습니다.")
    
    def restore_trading_state(self):
        """이전 거래 상태 복원"""
        try:
            if self.algo is not None:
                # 이미 초기화된 TradingAlgorithm이 있는 경우
                saved_state = self.algo.db.load_bot_state()
                if saved_state:
                    self.update_signal.emit("이전 거래 상태를 복원합니다.")
                    
                    # 트레이딩 활성화 상태 바로 적용
                    if 'is_running' in saved_state:
                        self.bot.is_running = saved_state['is_running']
                    
                    # 추가 상태 복원 로직 (필요시)
                    # ...
                    
                    # 포지션 복원
                    open_positions = self.algo.db.get_open_positions(self.bot.symbol)
                    if open_positions:
                        self.update_signal.emit(f"{len(open_positions)}개의 열린 포지션을 복원합니다.")
                        # 현재 봇의 포지션 업데이트
                        for pos in open_positions:
                            if pos['side'] == 'long':
                                position_type = 'long'
                            elif pos['side'] == 'short':
                                position_type = 'short'
                            else:
                                continue
                            
                            # 봇 포지션 업데이트
                            if hasattr(self.bot, 'update_position'):
                                self.bot.update_position(
                                    position_type=position_type,
                                    size=pos['amount'],
                                    price=pos['entry_price']
                                )
                                self.update_signal.emit(f"포지션 복원 완료: {position_type}, 가격: {pos['entry_price']}, 수량: {pos['amount']}")
                    
                    self.update_signal.emit("거래 상태 복원 완료")
                else:
                    self.update_signal.emit("저장된 이전 거래 상태가 없습니다.")
            else:
                self.update_signal.emit("트레이딩 알고리즘이 초기화되지 않았습니다.")
        except Exception as e:
            self.update_signal.emit(f"거래 상태 복원 오류: {e}")
    
    def save_trading_state(self):
        """현재 거래 상태 저장"""
        try:
            if self.algo is not None:
                # 현재 주요 상태 저장
                bot_state = {
                    'exchange_id': self.bot.exchange_id,
                    'symbol': self.bot.symbol,
                    'timeframe': self.bot.timeframe,
                    'strategy': self.bot.strategy.name if hasattr(self.bot.strategy, 'name') else 'unknown',
                    'market_type': getattr(self.bot, 'market_type', 'spot'),
                    'leverage': getattr(self.bot, 'leverage', 1),
                    'is_running': self.running,
                    'test_mode': self.bot.test_mode,
                    'updated_at': datetime.now().isoformat(),
                    'parameters': self.strategy_params,  # 전략 파라미터(리스크 설정 포함) 저장
                    'additional_info': {
                        'interval': self.interval
                    }
                }
                
                # 저장
                self.algo.db.save_bot_state(bot_state)
                
                # 포지션 정보 저장
                if hasattr(self.bot, 'position') and self.bot.position['type'] is not None:
                    position_data = {
                        'symbol': self.bot.symbol,
                        'side': self.bot.position['type'],
                        'amount': self.bot.position['size'],
                        'entry_price': self.bot.position['entry_price'],
                        'leverage': getattr(self.bot, 'leverage', 1),
                        'opened_at': datetime.now().isoformat(),
                        'status': 'open',
                        'additional_info': {
                            'stop_loss': self.bot.position.get('stop_loss', 0),
                            'take_profit': self.bot.position.get('take_profit', 0)
                        }
                    }
                    
                    # 새 포지션이면 추가, 기존 포지션이 있으면 업데이트
                    open_positions = self.algo.db.get_open_positions(self.bot.symbol)
                    if not open_positions:
                        self.algo.db.save_position(position_data)
                    else:
                        for pos in open_positions:
                            if pos['side'] == self.bot.position['type']:
                                update_data = {
                                    'amount': self.bot.position['size'],
                                    'entry_price': self.bot.position['entry_price'],
                                    'additional_info': position_data['additional_info']
                                }
                                self.algo.db.update_position(pos['id'], update_data)
                                break
                
                # 잔액 정보 저장 (새로운 잔액 정보가 있는 경우에만)
                if hasattr(self.bot, 'get_account_balance'):
                    balance = self.bot.get_account_balance()
                    if balance > 0:
                        quote_currency = self.bot.symbol.split('/')[1]  # USDT, USD 등
                        self.algo.db.save_balance(quote_currency, balance)
                
                self.update_signal.emit("현재 봇 상태 저장 완료")
            else:
                self.update_signal.emit("트레이딩 알고리즘이 초기화되지 않아 상태를 저장할 수 없습니다.")
        except Exception as e:
            self.update_signal.emit(f"거래 상태 저장 오류: {e}")
    
    def stop(self):
        self.running = False
        # 종료 전 상태 저장
        self.save_trading_state()
        
        # 포지션 정리 (필요시)
        if hasattr(self.bot, 'close_position'):
            self.bot.close_position()
        
        self.update_signal.emit("봇 종료 중...")
# 메인 윈도우
class CryptoTradingBotGUI(QMainWindow):
    """암호화폐 자동 매매 봇 GUI 클래스"""
    
    def __init__(self, headless=False):
        # 항상 QMainWindow 초기화 (헤드리스 모드와 상관없이)
        super().__init__()
        
        # 헤드리스 모드 설정
        self.headless = headless
        
        # 상태 변수
        self.bot_running = False
        self.bot_thread = None
        self.chart_thread = None
        
        # 웹 API 호출을 위한 데이터 저장 변수
        self.balance_data = None
        self.position_data = None
        self.trades_data = []
        self.current_strategy = 'Unknown'  # 현재 사용 중인 전략 저장 변수
        
        # 헤드리스 모드일 경우 기본 속성 설정
        if self.headless:
            # 기본 검색에 사용될 공통 속성들
            from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
            self.exchange_id = DEFAULT_EXCHANGE
            self.symbol = DEFAULT_SYMBOL
            self.timeframe = DEFAULT_TIMEFRAME
            self.strategy_name = 'ma_crossover'  # 기본 전략
        
        # GUI 모드인 경우에만 UI 초기화
        if not headless:
            # 기본 UI 설정인스턴스 생성
            self.wallet_widget = WalletBalanceWidget()
        
            self.initUI()
        
            # 환경 변수 로드
            load_dotenv()
        load_dotenv()
        
        # API 키 설정
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        # GUI 모드이고 API 키가 있는 경우에만 위젯 업데이트
        if not self.headless and api_key and api_secret:
            self.api_key_input.setText(api_key)
            self.api_secret_input.setText(api_secret)
            
            # API 키 설정 후 지갑 위젯 초기화
            self.wallet_widget.set_api(
                exchange_id=self.exchange_combo.currentText(),
                api_key=api_key,
                api_secret=api_secret,
                symbol=self.symbol_combo.currentText()
            )
    
    def initUI(self):
        self.setWindowTitle('암호화폐 자동 매매 봇')
        self.setGeometry(100, 100, 800, 600)
        
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 탭 위젯
        tabs = QTabWidget()
        
        # 설정 탭
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_content_layout = QVBoxLayout(settings_content)
        
        # API 설정 그룹
        api_group = QGroupBox("API 설정")
        api_layout = QFormLayout()
        
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(['binance', 'upbit', 'bithumb'])
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        
        api_layout.addRow("거래소:", self.exchange_combo)
        api_layout.addRow("API 키:", self.api_key_input)
        api_layout.addRow("API 시크릿:", self.api_secret_input)
        
        api_group.setLayout(api_layout)
        
        # 거래 설정 그룹
        trade_group = QGroupBox("거래 설정")
        trade_layout = QFormLayout()
        
        # 거래 쌍 드롭다운 메뉴 생성
        self.symbol_combo = QComboBox()
        # 초기 거래 타입에 맞는 심볼 목록 로딩
        market_type = 'spot'  # 기본값
        symbol_list = self.get_symbol_list(market_type)
        self.symbol_combo.addItems(symbol_list)
        self.symbol_combo.setCurrentText("BTC/USDT")  # 기본값 설정
        
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(['1m', '5m', '15m', '30m', '1h', '4h', '1d'])
        self.timeframe_combo.setCurrentText('1h')
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(60, 3600)
        self.interval_spin.setValue(300)
        self.interval_spin.setSuffix(" 초")
        
        self.test_mode_check = QCheckBox("테스트 모드 (실제 거래 없음)")
        self.test_mode_check.setChecked(True)
        
        # 자동 손절매/이익실현 기능
        self.auto_sl_tp_check = QCheckBox("자동 손절매/이익실현 활성화")
        self.auto_sl_tp_check.setChecked(False)
        self.auto_sl_tp_check.stateChanged.connect(self.on_auto_sl_tp_changed)
        
        # 부분 청산 기능
        self.partial_tp_check = QCheckBox("부분 청산 활성화")
        self.partial_tp_check.setChecked(False)
        self.partial_tp_check.setEnabled(False)  # 기본적으로 비활성화
        
        # 거래 타입 선택 (현물/선물)
        self.market_type_combo = QComboBox()
        self.market_type_combo.addItems(['spot', 'futures'])
        self.market_type_combo.setCurrentText('spot')
        self.market_type_combo.currentTextChanged.connect(self.on_market_type_changed)
        
        # 레버리지 설정
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 20)
        self.leverage_spin.setValue(2)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setVisible(False)  # 기본적으로 숨김 (현물 거래 선택시)
        
        trade_layout.addRow("거래 쌍:", self.symbol_combo)
        trade_layout.addRow("타임프레임:", self.timeframe_combo)
        trade_layout.addRow("거래 타입:", self.market_type_combo)
        trade_layout.addRow("레버리지:", self.leverage_spin)
        trade_layout.addRow("실행 간격:", self.interval_spin)
        trade_layout.addRow(self.test_mode_check)
        trade_layout.addRow(self.auto_sl_tp_check)
        trade_layout.addRow(self.partial_tp_check)
        
        trade_group.setLayout(trade_layout)
        
        # 전략 설정 그룹
        strategy_group = QGroupBox("전략 설정")
        strategy_layout = QVBoxLayout()
        
        # 이동평균 전략 설정
        ma_check = QCheckBox("이동평균 교차 전략")
        ma_check.setChecked(True)
        self.ma_check = ma_check
        
        ma_form = QFormLayout()
        
        self.ma_short_spin = QSpinBox()
        self.ma_short_spin.setRange(1, 50)
        self.ma_short_spin.setValue(9)
        
        self.ma_long_spin = QSpinBox()
        self.ma_long_spin.setRange(10, 200)
        self.ma_long_spin.setValue(26)
        
        self.ma_type_combo = QComboBox()
        self.ma_type_combo.addItems(['sma', 'ema'])
        self.ma_type_combo.setCurrentText('ema')
        
        self.ma_weight_spin = QDoubleSpinBox()
        self.ma_weight_spin.setRange(0, 1)
        self.ma_weight_spin.setValue(0.4)
        self.ma_weight_spin.setSingleStep(0.1)
        
        ma_form.addRow("단기 기간:", self.ma_short_spin)
        ma_form.addRow("장기 기간:", self.ma_long_spin)
        ma_form.addRow("이동평균 유형:", self.ma_type_combo)
        ma_form.addRow("가중치:", self.ma_weight_spin)
        
        ma_widget = QWidget()
        ma_widget.setLayout(ma_form)
        
        # RSI 전략 설정
        rsi_check = QCheckBox("RSI 전략")
        rsi_check.setChecked(True)
        self.rsi_check = rsi_check
        
        rsi_form = QFormLayout()
        
        self.rsi_period_spin = QSpinBox()
        self.rsi_period_spin.setRange(1, 50)
        self.rsi_period_spin.setValue(14)
        
        self.rsi_overbought_spin = QSpinBox()
        self.rsi_overbought_spin.setRange(50, 100)
        self.rsi_overbought_spin.setValue(70)
        
        self.rsi_oversold_spin = QSpinBox()
        self.rsi_oversold_spin.setRange(0, 50)
        self.rsi_oversold_spin.setValue(30)
        
        self.rsi_weight_spin = QDoubleSpinBox()
        self.rsi_weight_spin.setRange(0, 1)
        self.rsi_weight_spin.setValue(0.3)
        self.rsi_weight_spin.setSingleStep(0.1)
        
        rsi_form.addRow("기간:", self.rsi_period_spin)
        rsi_form.addRow("과매수 기준:", self.rsi_overbought_spin)
        rsi_form.addRow("과매도 기준:", self.rsi_oversold_spin)
        rsi_form.addRow("가중치:", self.rsi_weight_spin)
        
        rsi_widget = QWidget()
        rsi_widget.setLayout(rsi_form)
        
        # MACD 전략 설정
        macd_check = QCheckBox("MACD 전략")
        macd_check.setChecked(True)
        self.macd_check = macd_check
        
        macd_form = QFormLayout()
        
        self.macd_fast_spin = QSpinBox()
        self.macd_fast_spin.setRange(1, 50)
        self.macd_fast_spin.setValue(12)
        
        self.macd_slow_spin = QSpinBox()
        self.macd_slow_spin.setRange(10, 100)
        self.macd_slow_spin.setValue(26)
        
        self.macd_signal_spin = QSpinBox()
        self.macd_signal_spin.setRange(1, 50)
        self.macd_signal_spin.setValue(9)
        
        self.macd_weight_spin = QDoubleSpinBox()
        self.macd_weight_spin.setRange(0, 1)
        self.macd_weight_spin.setValue(0.2)
        self.macd_weight_spin.setSingleStep(0.1)
        
        macd_form.addRow("빠른 기간:", self.macd_fast_spin)
        macd_form.addRow("느린 기간:", self.macd_slow_spin)
        macd_form.addRow("시그널 기간:", self.macd_signal_spin)
        macd_form.addRow("가중치:", self.macd_weight_spin)
        
        macd_widget = QWidget()
        macd_widget.setLayout(macd_form)
        
        # 볼린저 밴드 전략 설정
        bb_check = QCheckBox("볼린저 밴드 전략")
        bb_check.setChecked(True)
        self.bb_check = bb_check
        
        bb_form = QFormLayout()
        
        self.bb_period_spin = QSpinBox()
        self.bb_period_spin.setRange(1, 50)
        self.bb_period_spin.setValue(20)
        
        self.bb_std_spin = QDoubleSpinBox()
        self.bb_std_spin.setRange(0.5, 5)
        self.bb_std_spin.setValue(2)
        self.bb_std_spin.setSingleStep(0.1)
        
        self.bb_weight_spin = QDoubleSpinBox()
        self.bb_weight_spin.setRange(0, 1)
        self.bb_weight_spin.setValue(0.1)
        self.bb_weight_spin.setSingleStep(0.1)
        
        bb_form.addRow("기간:", self.bb_period_spin)
        bb_form.addRow("표준편차:", self.bb_std_spin)
        bb_form.addRow("가중치:", self.bb_weight_spin)
        
        bb_widget = QWidget()
        bb_widget.setLayout(bb_form)
        
        # 전략 레이아웃에 추가
        strategy_layout.addWidget(ma_check)
        strategy_layout.addWidget(ma_widget)
        strategy_layout.addWidget(rsi_check)
        strategy_layout.addWidget(rsi_widget)
        strategy_layout.addWidget(macd_check)
        strategy_layout.addWidget(macd_widget)
        strategy_layout.addWidget(bb_check)
        strategy_layout.addWidget(bb_widget)

        strategy_group.setLayout(strategy_layout)

        # --- 선물 전략 그룹(별도) ---
        futures_group = QGroupBox("선물 전략 (Bollinger Band Futures)")
        futures_layout = QVBoxLayout()
        self.bbfutures_check = QCheckBox("Bollinger Band Futures 전략 사용")
        self.bbfutures_check.setChecked(False)
        futures_layout.addWidget(self.bbfutures_check)
        # 파라미터 입력 위젯
        futures_form = QFormLayout()
        self.bbfutures_bb_period_spin = QSpinBox()
        self.bbfutures_bb_period_spin.setRange(5, 100)
        self.bbfutures_bb_period_spin.setValue(20)
        self.bbfutures_bb_std_spin = QDoubleSpinBox()
        self.bbfutures_bb_std_spin.setRange(1.0, 5.0)
        self.bbfutures_bb_std_spin.setValue(2.0)
        self.bbfutures_bb_std_spin.setSingleStep(0.1)
        self.bbfutures_rsi_period_spin = QSpinBox()
        self.bbfutures_rsi_period_spin.setRange(5, 50)
        self.bbfutures_rsi_period_spin.setValue(14)
        self.bbfutures_rsi_overbought_spin = QSpinBox()
        self.bbfutures_rsi_overbought_spin.setRange(50, 100)
        self.bbfutures_rsi_overbought_spin.setValue(70)
        self.bbfutures_rsi_oversold_spin = QSpinBox()
        self.bbfutures_rsi_oversold_spin.setRange(0, 50)
        self.bbfutures_rsi_oversold_spin.setValue(30)
        self.bbfutures_macd_fast_spin = QSpinBox()
        self.bbfutures_macd_fast_spin.setRange(1, 50)
        self.bbfutures_macd_fast_spin.setValue(12)
        self.bbfutures_macd_slow_spin = QSpinBox()
        self.bbfutures_macd_slow_spin.setRange(10, 100)
        self.bbfutures_macd_slow_spin.setValue(26)
        self.bbfutures_macd_signal_spin = QSpinBox()
        self.bbfutures_macd_signal_spin.setRange(1, 50)
        self.bbfutures_macd_signal_spin.setValue(9)
        self.bbfutures_leverage_spin = QSpinBox()
        self.bbfutures_leverage_spin.setRange(1, 20)
        self.bbfutures_leverage_spin.setValue(3)
        futures_form.addRow("BB 기간:", self.bbfutures_bb_period_spin)
        futures_form.addRow("BB 표준편차:", self.bbfutures_bb_std_spin)
        futures_form.addRow("RSI 기간:", self.bbfutures_rsi_period_spin)
        futures_form.addRow("RSI 과매수:", self.bbfutures_rsi_overbought_spin)
        futures_form.addRow("RSI 과매도:", self.bbfutures_rsi_oversold_spin)
        futures_form.addRow("MACD Fast:", self.bbfutures_macd_fast_spin)
        futures_form.addRow("MACD Slow:", self.bbfutures_macd_slow_spin)
        futures_form.addRow("MACD Signal:", self.bbfutures_macd_signal_spin)
        futures_form.addRow("레버리지:", self.bbfutures_leverage_spin)
        futures_layout.addLayout(futures_form)
        futures_group.setLayout(futures_layout)
        
        # 위험 관리 설정 그룹
        risk_group = QGroupBox("위험 관리 설정")
        risk_layout = QFormLayout()
        
        # 자동 손절매/이익실현 활성화 체크박스 추가
        self.auto_exit_check = QCheckBox("자동 손절매/이익실현 활성화")
        self.auto_exit_check.setChecked(True)  # 기본값으로 활성화
        self.auto_exit_check.setToolTip("설정된 손절매/이익실현 비율에 따라 자동으로 포지션을 종료합니다")
        
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0.01, 0.5)
        self.stop_loss_spin.setValue(0.05)
        self.stop_loss_spin.setSingleStep(0.01)
        self.stop_loss_spin.setToolTip("진입가 대비 손실 비율이 이 값에 도달하면 자동으로 포지션을 종료합니다")
        
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0.01, 0.5)
        self.take_profit_spin.setValue(0.1)
        self.take_profit_spin.setSingleStep(0.01)
        self.take_profit_spin.setToolTip("진입가 대비 이익 비율이 이 값에 도달하면 자동으로 포지션을 종료합니다")
        
        self.max_position_spin = QDoubleSpinBox()
        self.max_position_spin.setRange(0.01, 1)
        self.max_position_spin.setValue(0.2)
        self.max_position_spin.setSingleStep(0.05)
        
        # 스핀박스 값 변경시 괄호 안의 퍼센트 값도 업데이트되도록 연결
        self.stop_loss_spin.valueChanged.connect(self.update_spin_suffix)
        self.take_profit_spin.valueChanged.connect(self.update_spin_suffix)
        self.max_position_spin.valueChanged.connect(self.update_spin_suffix)
        
        # 초기화 시 접미사 설정
        self.update_spin_suffix()
        
        # 자동 종료 체크박스는 별도 행으로 추가
        risk_layout.addRow(self.auto_exit_check)
        
        # 손절매/이익실현 비율 설정
        risk_layout.addRow("손절매 비율:", self.stop_loss_spin)
        risk_layout.addRow("이익실현 비율:", self.take_profit_spin)
        risk_layout.addRow("최대 포지션 크기:", self.max_position_spin)
        
        risk_group.setLayout(risk_layout)
        
        # 설정 탭에 그룹 추가
        settings_content_layout.addWidget(api_group)
        settings_content_layout.addWidget(self.wallet_widget)
        settings_content_layout.addWidget(trade_group)
        settings_content_layout.addWidget(risk_group)
        settings_content_layout.addWidget(strategy_group)
        settings_content_layout.addWidget(futures_group)
        
        settings_scroll.setWidget(settings_content)
        settings_layout.addWidget(settings_scroll)
        settings_tab.setLayout(settings_layout)
        
        # 로그 탭
        log_tab = QWidget()
        log_layout = QVBoxLayout()
        log_scroll = QScrollArea()
        log_scroll.setWidgetResizable(True)
        log_content = QWidget()
        log_content_layout = QVBoxLayout(log_content)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_content_layout.addWidget(self.log_text)
        log_scroll.setWidget(log_content)
        log_layout.addWidget(log_scroll)
        log_tab.setLayout(log_layout)
        
        # 백테스트 탭
        backtest_tab = QWidget()
        backtest_layout = QVBoxLayout()
        backtest_scroll = QScrollArea()
        backtest_scroll.setWidgetResizable(True)
        backtest_content = QWidget()
        backtest_content_layout = QVBoxLayout(backtest_content)
        
        # 백테스트 설정 그룹
        backtest_settings_group = QGroupBox("백테스트 설정")
        backtest_settings_layout = QFormLayout()
        
        # 거래소 및 심볼 설정
        self.backtest_exchange_combo = QComboBox()
        self.backtest_exchange_combo.addItems(['binance', 'upbit', 'bithumb'])
        self.backtest_symbol_edit = QLineEdit('BTC/USDT')
        self.backtest_timeframe_combo = QComboBox()
        self.backtest_timeframe_combo.addItems(['1m', '5m', '15m', '30m', '1h', '4h', '1d'])
        
        # 날짜 설정
        self.backtest_start_date = QDateEdit()
        self.backtest_start_date.setDate(QDate.currentDate().addMonths(-3))
        self.backtest_start_date.setCalendarPopup(True)
        self.backtest_end_date = QDateEdit()
        self.backtest_end_date.setDate(QDate.currentDate())
        self.backtest_end_date.setCalendarPopup(True)
        
        # 초기 자본 및 수수료 설정
        self.backtest_initial_balance = QDoubleSpinBox()
        self.backtest_initial_balance.setRange(100, 1000000)
        self.backtest_initial_balance.setValue(10000)
        self.backtest_initial_balance.setSingleStep(100)
        self.backtest_commission = QDoubleSpinBox()
        self.backtest_commission.setRange(0, 0.01)
        self.backtest_commission.setValue(0.001)
        self.backtest_commission.setSingleStep(0.0001)
        self.backtest_commission.setDecimals(5)
        
        # 전략 설정
        self.backtest_strategy_combo = QComboBox()
        self.backtest_strategy_combo.addItems([
            'moving_average', 'rsi', 'macd', 'bollinger_bands', 
            'stochastic', 'breakout', 'volatility_breakout', 'combined',
            'bollinger_band_futures'  # 선물 전략
        ])
        
        # 시장 타입 및 레버리지 설정
        self.backtest_market_type_combo = QComboBox()
        self.backtest_market_type_combo.addItems(['spot', 'futures'])
        self.backtest_market_type_combo.setCurrentText('spot')
        self.backtest_market_type_combo.currentTextChanged.connect(self.toggle_backtest_leverage_settings)
        
        self.backtest_leverage_widget = QWidget()
        leverage_layout = QHBoxLayout(self.backtest_leverage_widget)
        leverage_layout.setContentsMargins(0, 0, 0, 0)
        
        self.backtest_leverage_spin = QSpinBox()
        self.backtest_leverage_spin.setRange(1, 20)
        self.backtest_leverage_spin.setValue(1)
        self.backtest_leverage_label = QLabel("배")
        
        leverage_layout.addWidget(self.backtest_leverage_spin)
        leverage_layout.addWidget(self.backtest_leverage_label)
        
        # 폼 레이아웃에 위젯 추가
        backtest_settings_layout.addRow("거래소:", self.backtest_exchange_combo)
        backtest_settings_layout.addRow("심볼:", self.backtest_symbol_edit)
        backtest_settings_layout.addRow("타임프레임:", self.backtest_timeframe_combo)
        backtest_settings_layout.addRow("시장 타입:", self.backtest_market_type_combo)
        backtest_settings_layout.addRow("레버리지:", self.backtest_leverage_widget)
        backtest_settings_layout.addRow("시작일:", self.backtest_start_date)
        backtest_settings_layout.addRow("종료일:", self.backtest_end_date)
        backtest_settings_layout.addRow("초기 자본:", self.backtest_initial_balance)
        backtest_settings_layout.addRow("수수료 (%):", self.backtest_commission)
        backtest_settings_layout.addRow("전략:", self.backtest_strategy_combo)
        
        # 전략 파라미터 그룹 (초기값: 이동평균 전략)
        self.backtest_params_group = QGroupBox("전략 파라미터")
        self.backtest_params_layout = QFormLayout()
        
        # 이동평균 전략 파라미터
        self.backtest_ma_short = QSpinBox()
        self.backtest_ma_short.setRange(1, 50)
        self.backtest_ma_short.setValue(9)
        self.backtest_ma_long = QSpinBox()
        self.backtest_ma_long.setRange(10, 200)
        self.backtest_ma_long.setValue(26)
        
        self.backtest_params_layout.addRow("단기 이동평균선:", self.backtest_ma_short)
        self.backtest_params_layout.addRow("장기 이동평균선:", self.backtest_ma_long)
        self.backtest_params_group.setLayout(self.backtest_params_layout)
        
        # 전략 변경 시 파라미터 업데이트
        self.backtest_strategy_combo.currentTextChanged.connect(self.update_backtest_params)
        
        # 백테스트 실행 버튼
        self.run_backtest_button = QPushButton("백테스트 실행")
        self.run_backtest_button.clicked.connect(self.run_backtest)
        
        # 결과 표시 영역
        backtest_result_group = QGroupBox("백테스트 결과")
        backtest_result_layout = QVBoxLayout()
        
        # 결과 요약 테이블
        self.backtest_result_table = QTableWidget()
        self.backtest_result_table.setColumnCount(2)
        self.backtest_result_table.setHorizontalHeaderLabels(["항목", "값"])
        self.backtest_result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.backtest_result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.backtest_result_table.setRowCount(10)
        self.backtest_result_table.setMinimumHeight(300)  # 표 전체 높이 300px로 설정
        metrics = [
            "총 수익률 (%)", "연간 수익률 (%)", "최대 낙폭 (%)", "승률 (%)", 
            "총 거래 횟수", "평균 보유 기간", "샤프 비율", "손익비", "최대 연속 손실", "최대 연속 이익"
        ]
        for i, metric in enumerate(metrics):
            self.backtest_result_table.setItem(i, 0, QTableWidgetItem(metric))
            self.backtest_result_table.setItem(i, 1, QTableWidgetItem(""))
            self.backtest_result_table.setRowHeight(i, 48)  # 각 행 높이 48px로 설정
        
        # 차트 영역
        self.backtest_figure = Figure(figsize=(10, 8))
        self.backtest_canvas = FigureCanvas(self.backtest_figure)
        self.backtest_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 결과 저장 버튼
        self.save_backtest_button = QPushButton("결과 저장")
        self.save_backtest_button.clicked.connect(self.save_backtest_result)
        
        # 레이아웃에 추가
        backtest_result_layout.addWidget(self.backtest_result_table)
        backtest_result_layout.addWidget(self.backtest_canvas)
        backtest_result_layout.addWidget(self.save_backtest_button)
        backtest_result_group.setLayout(backtest_result_layout)
        
        # 백테스트 설정 그룹 완성
        backtest_settings_group.setLayout(backtest_settings_layout)
        
        # 모든 위젯 추가
        backtest_content_layout.addWidget(backtest_settings_group)
        backtest_content_layout.addWidget(self.backtest_params_group)
        backtest_content_layout.addWidget(self.run_backtest_button)
        backtest_content_layout.addWidget(backtest_result_group)
        
        backtest_scroll.setWidget(backtest_content)
        backtest_layout.addWidget(backtest_scroll)
        backtest_tab.setLayout(backtest_layout)
        
        # 탭 추가
        tabs.addTab(settings_tab, "설정")
        tabs.addTab(backtest_tab, "백테스트")
        tabs.addTab(log_tab, "로그")
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("시작")
        self.start_button.clicked.connect(self.start_bot)
        
        self.stop_button = QPushButton("중지")
        self.stop_button.clicked.connect(self.stop_bot)
        self.stop_button.setEnabled(False)
        
        self.save_button = QPushButton("설정 저장")
        self.save_button.clicked.connect(self.save_settings)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
        
        # 메인 레이아웃에 위젯 추가
        main_layout.addWidget(tabs)
        main_layout.addLayout(button_layout)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
    def on_market_type_changed(self, market_type):
        """거래 타입 변경 시 거래 쌍 목록 업데이트"""
        # 현재 선택된 심볼 저장 (있다면)
        current_symbol = self.symbol_combo.currentText() if self.symbol_combo.count() > 0 else ""
        
        # 심볼 목록 업데이트
        self.symbol_combo.clear()
        symbol_list = self.get_symbol_list(market_type)
        self.symbol_combo.addItems(symbol_list)
        
        # 현재 심볼을 새 형식으로 변환하여 선택 (이전에 선택된 심볼이 있었다면)
        if current_symbol:
            converted_symbol = self.convert_symbol_format(current_symbol, market_type)
            index = self.symbol_combo.findText(converted_symbol)
            if index >= 0:
                self.symbol_combo.setCurrentIndex(index)
        
        # 레버리지 설정 토글
        self.toggle_leverage_settings()
        
        logger.info(f"거래 타입 변경: {market_type}, 심볼 목록 업데이트")
        
    def on_auto_sl_tp_changed(self, state):
        """자동 손절매/이익실현 체크박스 상태 변경 처리"""
        # 부분 청산 체크박스 활성화/비활성화
        self.partial_tp_check.setEnabled(state == Qt.Checked)
        
        if state != Qt.Checked:
            self.partial_tp_check.setChecked(False)
    
    def toggle_leverage_settings(self):
        """선물거래 시 레버리지 설정 화면 표시"""
        market_type = self.market_type_combo.currentText()
        is_futures = market_type.lower() == 'futures'
        self.leverage_spin.setVisible(is_futures)
        
    def toggle_backtest_leverage_settings(self):
        """백테스트 시장 타입에 따라 레버리지 설정 표시 여부 토글"""
        market_type = self.backtest_market_type_combo.currentText()
        self.backtest_leverage_widget.setVisible(market_type == 'futures')
    
    def start_bot(self):
        # API 키 저장
        api_key = self.api_key_input.text()
        api_secret = self.api_secret_input.text()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self, "경고", "API 키와 시크릿을 입력해주세요.")
            return
        
        # .env 파일에 API 키 저장
        with open(".env", "w") as f:
            f.write(f"BINANCE_API_KEY={api_key}\n")
            f.write(f"BINANCE_API_SECRET={api_secret}\n")
        
        # 설정 가져오기
        exchange = self.exchange_combo.currentText()
        symbol = self.symbol_combo.currentText()
        timeframe = self.timeframe_combo.currentText()
        interval = self.interval_spin.value()
        test_mode = self.test_mode_check.isChecked()
        market_type = self.market_type_combo.currentText()
        leverage = self.leverage_spin.value() if market_type == 'futures' else 1
        
        # 자동 손절매/이익실현 옵션
        auto_sl_tp = self.auto_sl_tp_check.isChecked()
        partial_tp = self.partial_tp_check.isChecked() if auto_sl_tp else False
        
        # spot 전략 생성
        spot_strategies = []
        spot_weights = []
        if self.ma_check.isChecked():
            ma_strategy = MovingAverageCrossover(
                short_period=self.ma_short_spin.value(),
                long_period=self.ma_long_spin.value(),
                ma_type=self.ma_type_combo.currentText()
            )
            spot_strategies.append(ma_strategy)
            spot_weights.append(self.ma_weight_spin.value())
        if self.rsi_check.isChecked():
            rsi_strategy = RSIStrategy(
                period=self.rsi_period_spin.value(),
                overbought=self.rsi_overbought_spin.value(),
                oversold=self.rsi_oversold_spin.value()
            )
            spot_strategies.append(rsi_strategy)
            spot_weights.append(self.rsi_weight_spin.value())
        if self.macd_check.isChecked():
            macd_strategy = MACDStrategy(
                fast_period=self.macd_fast_spin.value(),
                slow_period=self.macd_slow_spin.value(),
                signal_period=self.macd_signal_spin.value()
            )
            spot_strategies.append(macd_strategy)
            spot_weights.append(self.macd_weight_spin.value())
        if self.bb_check.isChecked():
            bb_strategy = BollingerBandsStrategy(
                period=self.bb_period_spin.value(),
                std_dev=self.bb_std_spin.value()
            )
            spot_strategies.append(bb_strategy)
            spot_weights.append(self.bb_weight_spin.value())

        # futures 전략 생성
        use_futures = self.bbfutures_check.isChecked()
        if use_futures:
            futures_strategy = BollingerBandFuturesStrategy(
                bb_period=self.bbfutures_bb_period_spin.value(),
                bb_std=self.bbfutures_bb_std_spin.value(),
                rsi_period=self.bbfutures_rsi_period_spin.value(),
                rsi_overbought=self.bbfutures_rsi_overbought_spin.value(),
                rsi_oversold=self.bbfutures_rsi_oversold_spin.value(),
                macd_fast=self.bbfutures_macd_fast_spin.value(),
                macd_slow=self.bbfutures_macd_slow_spin.value(),
                macd_signal=self.bbfutures_macd_signal_spin.value(),
                leverage=self.bbfutures_leverage_spin.value(),
                timeframe=timeframe
            )

        # spot/futures 동시 선택 방지
        if spot_strategies and use_futures:
            QMessageBox.warning(self, "경고", "현물(spot) 전략과 선물(futures) 전략은 동시에 사용할 수 없습니다. 하나만 선택하세요.")
            return
        # spot만 선택
        if spot_strategies:
            weight_sum = sum(spot_weights)
            if weight_sum > 0:
                spot_weights = [w / weight_sum for w in spot_weights]
            strategy = CombinedStrategy(strategies=spot_strategies, weights=spot_weights)
            market_type = 'spot'
            leverage = 1
        # futures만 선택
        elif use_futures:
            strategy = futures_strategy
            market_type = 'futures'
            leverage = self.bbfutures_leverage_spin.value()
        else:
            QMessageBox.warning(self, "경고", "최소한 하나 이상의 전략을 선택해주세요.")
            return
        # 위험 관리 설정
        risk_manager = RiskManager(
            stop_loss_pct=self.stop_loss_spin.value(),
            take_profit_pct=self.take_profit_spin.value(),
            max_position_size=self.max_position_spin.value(),
            auto_exit_enabled=self.auto_exit_check.isChecked()  # 자동 손절매/이익실현 활성화 여부 전달
        )
        # 봇 생성
        bot = TradingBot(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            risk_manager=risk_manager,
            test_mode=test_mode,
            market_type=market_type,
            leverage=leverage
        )
        # 봇 스레드 시작
        self.bot_thread = BotThread(bot, interval, auto_sl_tp, partial_tp)
        self.bot_thread.update_signal.connect(self.update_log)
        self.bot_thread.start()
        # 버튼 상태 변경
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_text.append("자동 매매 봇이 시작되었습니다.")
    
    def stop_bot(self):
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
        
        # 버튼 상태 변경
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        self.log_text.append("자동 매매 봇이 중지되었습니다.")
    
    def update_log(self, message):
        self.log_text.append(message)
        # 스크롤을 항상 아래로 유지
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def get_symbol_list(self, market_type='spot'):
        """거래 타입에 따른 기본 거래 쌍 목록 반환"""
        spot_symbols = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", 
            "ADA/USDT", "DOT/USDT", "DOGE/USDT", "LINK/USDT",
            "MATIC/USDT", "LTC/USDT", "UNI/USDT", "AVAX/USDT"
        ]
        
        futures_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", 
            "ADAUSDT", "DOTUSDT", "DOGEUSDT", "LINKUSDT",
            "MATICUSDT", "LTCUSDT", "UNIUSDT", "AVAXUSDT"
        ]
        
        return spot_symbols if market_type.lower() == 'spot' else futures_symbols
    
    def fetch_available_symbols(self, market_type='spot'):
        """거래소에서 실제 거래 가능한 심볼 목록 가져오기"""
        try:
            exchange_id = self.exchange_combo.currentText().lower()
            exchange = getattr(ccxt, exchange_id)({'enableRateLimit': True})
            
            if market_type.lower() == 'spot':
                markets = exchange.load_markets()
                return [symbol for symbol in markets.keys() if '/USDT' in symbol]
            else:  # futures
                if exchange_id == 'binance':
                    markets = exchange.fetch_derivatives_markets()
                    return [market['id'] for market in markets if 'USDT' in market['id']]
                return self.get_symbol_list('futures')  # 기본값 반환
        except Exception as e:
            logger.error(f"심볼 목록 조회 중 오류: {e}")
            return self.get_symbol_list(market_type)  # 오류 시 기본값 반환
    
    def convert_symbol_format(self, symbol, target_market_type):
        """심볼 형식을 대상 마켓 타입에 맞게 변환"""
        if target_market_type.lower() == 'spot':
            # Futures -> Spot (BTCUSDT -> BTC/USDT)
            if '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT"
            return symbol
        else:
            # Spot -> Futures (BTC/USDT -> BTCUSDT)
            if '/' in symbol:
                base, quote = symbol.split('/')
                return f"{base}{quote}"
            return symbol
            
    def update_spin_suffix(self):
        """스핀박스의 값에 따라 괄호 안의 퍼센트 값을 업데이트"""
        # 손절매 스핀박스 업데이트
        loss_value = self.stop_loss_spin.value()
        self.stop_loss_spin.setSuffix(f" ({int(loss_value*100)}%)")
        
        # 이익실현 스핀박스 업데이트
        profit_value = self.take_profit_spin.value()
        self.take_profit_spin.setSuffix(f" ({int(profit_value*100)}%)")
        
        # 최대 포지션 스핀박스 업데이트
        position_value = self.max_position_spin.value()
        self.max_position_spin.setSuffix(f" ({int(position_value*100)}%)")
    
    def check_api_connection(self):
        """거래소 API 연결 테스트"""
        try:
            exchange_id = self.exchange_combo.currentText()
            api_key = self.api_key_input.text()
            api_secret = self.api_secret_input.text()
            symbol = self.symbol_combo.currentText()
            
            # 마켓 타입 및 레버리지 정보 가져오기
            market_type = self.market_type_combo.currentText().lower()
            leverage = self.leverage_spin.value() if market_type == 'futures' else 1
            
            if not (api_key and api_secret):
                self.status_label.setText("상태: API 키와 시크릿을 입력해주세요.")
                self.status_label.setStyleSheet("color: red;")
                return
            
            # 지갑 API 설정 및 테스트
            connection_result = self.wallet_widget.set_api(
                exchange_id=exchange_id,
                api_key=api_key,
                api_secret=api_secret,
                symbol=self.symbol_combo.currentText(),
                market_type=market_type
            )
            
            # 연결 결과 메시지
            msg = QMessageBox()
            if connection_result:
                msg.setIcon(QMessageBox.Information)
                msg.setText("API 연결에 성공했습니다.")
            else:
                msg.setIcon(QMessageBox.Warning)
                msg.setText("API 연결에 실패했습니다. API 키를 확인하세요.")
            
            msg.setWindowTitle("API 연결 테스트")
            msg.exec_()
        
        except Exception as e:
            self.status_label.setText("상태: 오류 발생")
            self.status_label.setStyleSheet("color: red;")
            print(f"오류 발생: {e}")
        
    def save_settings(self):
        # 설정 저장
        settings = {
            "exchange": self.exchange_combo.currentText(),
            "symbol": self.symbol_combo.currentText(),
            "timeframe": self.timeframe_combo.currentText(),
            "interval": self.interval_spin.value(),
            "test_mode": self.test_mode_check.isChecked(),
            "ma_enabled": self.ma_check.isChecked(),
            "ma_short_period": self.ma_short_spin.value(),
            "ma_long_period": self.ma_long_spin.value(),
            "ma_type": self.ma_type_combo.currentText(),
            "ma_weight": self.ma_weight_spin.value(),
            "rsi_enabled": self.rsi_check.isChecked(),
            "rsi_period": self.rsi_period_spin.value(),
            "rsi_overbought": self.rsi_overbought_spin.value(),
            "rsi_oversold": self.rsi_oversold_spin.value(),
            "rsi_weight": self.rsi_weight_spin.value(),
            "macd_enabled": self.macd_check.isChecked(),
            "macd_fast_period": self.macd_fast_spin.value(),
            "macd_slow_period": self.macd_slow_spin.value(),
            "macd_signal_period": self.macd_signal_spin.value(),
            "macd_weight": self.macd_weight_spin.value(),
            "bb_enabled": self.bb_check.isChecked(),
            "bb_period": self.bb_period_spin.value(),
            "bb_std_dev": self.bb_std_spin.value(),
            "bb_weight": self.bb_weight_spin.value(),
            "stop_loss_pct": self.stop_loss_spin.value(),
            "take_profit_pct": self.take_profit_spin.value(),
            "max_position_size": self.max_position_spin.value(),
            "market_type": self.market_type_combo.currentText(),
            "leverage": self.leverage_spin.value(),
        }
        
        # 설정 파일 저장
        with open("bot_settings.txt", "w") as f:
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        
        # API 키 가져오기
        api_key = self.api_key_input.text()
        api_secret = self.api_secret_input.text()
        exchange = self.exchange_combo.currentText()
        
        # 환경 변수 저장
        os.environ['BINANCE_API_KEY'] = api_key
        os.environ['BINANCE_API_SECRET'] = api_secret
        
        # 지갑 API 설정 및 테스트
        connection_result = self.wallet_widget.set_api(
            exchange_id=exchange,
            api_key=api_key,
            api_secret=api_secret,
            symbol=self.symbol_combo.currentText()
        )
        
        # 설정 저장 완료 메시지
        msg = QMessageBox()
        if connection_result:
            msg.setIcon(QMessageBox.Information)
            msg.setText("설정이 저장되었으며 API 연결에 성공했습니다.")
        else:
            msg.setIcon(QMessageBox.Warning)
            msg.setText("설정이 저장되었으나 API 연결에 실패했습니다. API 키를 확인하세요.")
        
        msg.setWindowTitle("설정 저장")
        msg.exec_()
    
    def closeEvent(self, event):
        # 프로그램 종료 시 봇 중지
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.wait()
        event.accept()
    
    def update_backtest_params(self, strategy_name):
        """선택한 전략에 따라 파라미터 입력 영역을 업데이트합니다."""
        # 기존 파라미터 위젯 제거
        while self.backtest_params_layout.count():
            item = self.backtest_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 전략별 파라미터 위젯 추가
        if strategy_name == 'moving_average':
            # 이동평균 전략 파라미터
            self.backtest_ma_short = QSpinBox()
            self.backtest_ma_short.setRange(1, 50)
            self.backtest_ma_short.setValue(9)
            self.backtest_ma_long = QSpinBox()
            self.backtest_ma_long.setRange(10, 200)
            self.backtest_ma_long.setValue(26)
            self.backtest_ma_type = QComboBox()
            self.backtest_ma_type.addItems(['sma', 'ema'])
            
            self.backtest_params_layout.addRow("단기 이동평균선:", self.backtest_ma_short)
            self.backtest_params_layout.addRow("장기 이동평균선:", self.backtest_ma_long)
            self.backtest_params_layout.addRow("이동평균 유형:", self.backtest_ma_type)
            
        elif strategy_name == 'rsi':
            # RSI 전략 파라미터
            self.backtest_rsi_period = QSpinBox()
            self.backtest_rsi_period.setRange(1, 50)
            self.backtest_rsi_period.setValue(14)
            self.backtest_rsi_overbought = QSpinBox()
            self.backtest_rsi_overbought.setRange(50, 100)
            self.backtest_rsi_overbought.setValue(70)
            self.backtest_rsi_oversold = QSpinBox()
            self.backtest_rsi_oversold.setRange(0, 50)
            self.backtest_rsi_oversold.setValue(30)
            
            self.backtest_params_layout.addRow("RSI 기간:", self.backtest_rsi_period)
            self.backtest_params_layout.addRow("과매수 기준:", self.backtest_rsi_overbought)
            self.backtest_params_layout.addRow("과매도 기준:", self.backtest_rsi_oversold)
            
        elif strategy_name == 'macd':
            # MACD 전략 파라미터
            self.backtest_macd_fast = QSpinBox()
            self.backtest_macd_fast.setRange(1, 50)
            self.backtest_macd_fast.setValue(12)
            self.backtest_macd_slow = QSpinBox()
            self.backtest_macd_slow.setRange(10, 100)
            self.backtest_macd_slow.setValue(26)
            self.backtest_macd_signal = QSpinBox()
            self.backtest_macd_signal.setRange(1, 50)
            self.backtest_macd_signal.setValue(9)
            
            self.backtest_params_layout.addRow("빠른 EMA 기간:", self.backtest_macd_fast)
            self.backtest_params_layout.addRow("느린 EMA 기간:", self.backtest_macd_slow)
            self.backtest_params_layout.addRow("시그널 기간:", self.backtest_macd_signal)
            
        elif strategy_name == 'bollinger_bands':
            # 볼린저 밴드 전략 파라미터
            self.backtest_bb_period = QSpinBox()
            self.backtest_bb_period.setRange(1, 100)
            self.backtest_bb_period.setValue(20)
            self.backtest_bb_std = QDoubleSpinBox()
            self.backtest_bb_std.setRange(0.1, 5.0)
            self.backtest_bb_std.setValue(2.0)
            self.backtest_bb_std.setSingleStep(0.1)
            
            self.backtest_params_layout.addRow("기간:", self.backtest_bb_period)
            self.backtest_params_layout.addRow("표준편차 배수:", self.backtest_bb_std)
            
        elif strategy_name == 'stochastic':
            # 스토캐스틱 전략 파라미터
            self.backtest_stoch_k = QSpinBox()
            self.backtest_stoch_k.setRange(1, 30)
            self.backtest_stoch_k.setValue(14)
            self.backtest_stoch_d = QSpinBox()
            self.backtest_stoch_d.setRange(1, 30)
            self.backtest_stoch_d.setValue(3)
            self.backtest_stoch_overbought = QSpinBox()
            self.backtest_stoch_overbought.setRange(50, 100)
            self.backtest_stoch_overbought.setValue(80)
            self.backtest_stoch_oversold = QSpinBox()
            self.backtest_stoch_oversold.setRange(0, 50)
            self.backtest_stoch_oversold.setValue(20)
            
            self.backtest_params_layout.addRow("%K 기간:", self.backtest_stoch_k)
            self.backtest_params_layout.addRow("%D 기간:", self.backtest_stoch_d)
            self.backtest_params_layout.addRow("과매수 기준:", self.backtest_stoch_overbought)
            self.backtest_params_layout.addRow("과매도 기준:", self.backtest_stoch_oversold)
            
        elif strategy_name == 'breakout':
            # 브레이크아웃 전략 파라미터
            self.backtest_breakout_period = QSpinBox()
            self.backtest_breakout_period.setRange(5, 100)
            self.backtest_breakout_period.setValue(20)
            
            self.backtest_params_layout.addRow("기간:", self.backtest_breakout_period)
            
        elif strategy_name == 'volatility_breakout':
            # 변동성 돌파 전략 파라미터
            self.backtest_vb_period = QSpinBox()
            self.backtest_vb_period.setRange(1, 20)
            self.backtest_vb_period.setValue(1)
            self.backtest_vb_k = QDoubleSpinBox()
            self.backtest_vb_k.setRange(0.1, 2.0)
            self.backtest_vb_k.setValue(0.5)
            self.backtest_vb_k.setSingleStep(0.1)
            
            self.backtest_params_layout.addRow("기간:", self.backtest_vb_period)
            self.backtest_params_layout.addRow("K 값:", self.backtest_vb_k)
            
        elif strategy_name == 'bollinger_band_futures':
            # 볼린저 밴드 + RSI + MACD + 헤이킨 아시 기반 선물 전략 파라미터
            self.backtest_bbf_bb_period = QSpinBox()
            self.backtest_bbf_bb_period.setRange(5, 100)
            self.backtest_bbf_bb_period.setValue(20)
            self.backtest_bbf_bb_std = QDoubleSpinBox()
            self.backtest_bbf_bb_std.setRange(1.0, 5.0)
            self.backtest_bbf_bb_std.setValue(2.0)
            self.backtest_bbf_bb_std.setSingleStep(0.1)
            self.backtest_bbf_rsi_period = QSpinBox()
            self.backtest_bbf_rsi_period.setRange(5, 50)
            self.backtest_bbf_rsi_period.setValue(14)
            self.backtest_bbf_rsi_overbought = QSpinBox()
            self.backtest_bbf_rsi_overbought.setRange(50, 100)
            self.backtest_bbf_rsi_overbought.setValue(70)
            self.backtest_bbf_rsi_oversold = QSpinBox()
            self.backtest_bbf_rsi_oversold.setRange(0, 50)
            self.backtest_bbf_rsi_oversold.setValue(30)
            self.backtest_bbf_macd_fast = QSpinBox()
            self.backtest_bbf_macd_fast.setRange(1, 50)
            self.backtest_bbf_macd_fast.setValue(12)
            self.backtest_bbf_macd_slow = QSpinBox()
            self.backtest_bbf_macd_slow.setRange(10, 100)
            self.backtest_bbf_macd_slow.setValue(26)
            self.backtest_bbf_macd_signal = QSpinBox()
            self.backtest_bbf_macd_signal.setRange(1, 50)
            self.backtest_bbf_macd_signal.setValue(9)
            self.backtest_bbf_leverage = QSpinBox()
            self.backtest_bbf_leverage.setRange(1, 20)
            self.backtest_bbf_leverage.setValue(3)
            self.backtest_params_layout.addRow("BB 기간:", self.backtest_bbf_bb_period)
            self.backtest_params_layout.addRow("BB 표준편차:", self.backtest_bbf_bb_std)
            self.backtest_params_layout.addRow("RSI 기간:", self.backtest_bbf_rsi_period)
            self.backtest_params_layout.addRow("RSI 과매수:", self.backtest_bbf_rsi_overbought)
            self.backtest_params_layout.addRow("RSI 과매도:", self.backtest_bbf_rsi_oversold)
            self.backtest_params_layout.addRow("MACD Fast:", self.backtest_bbf_macd_fast)
            self.backtest_params_layout.addRow("MACD Slow:", self.backtest_bbf_macd_slow)
            self.backtest_params_layout.addRow("MACD Signal:", self.backtest_bbf_macd_signal)
            self.backtest_params_layout.addRow("레버리지:", self.backtest_bbf_leverage)
        elif strategy_name == 'combined':
            # 복합 전략 파라미터 (각 전략의 사용 여부)
            self.backtest_use_ma = QCheckBox("이동평균 사용")
            self.backtest_use_ma.setChecked(True)
            self.backtest_use_rsi = QCheckBox("RSI 사용")
            self.backtest_use_rsi.setChecked(True)
            self.backtest_use_macd = QCheckBox("MACD 사용")
            self.backtest_use_macd.setChecked(True)
            self.backtest_use_bb = QCheckBox("볼린저 밴드 사용")
            self.backtest_use_bb.setChecked(False)
            
            self.backtest_params_layout.addRow("", self.backtest_use_ma)
            self.backtest_params_layout.addRow("", self.backtest_use_rsi)
            self.backtest_params_layout.addRow("", self.backtest_use_macd)
            self.backtest_params_layout.addRow("", self.backtest_use_bb)
    
    def run_backtest(self):
        """백테스트를 실행하고 결과를 표시합니다."""
        try:
            # 사용자 입력 값 가져오기
            exchange = self.backtest_exchange_combo.currentText()
            symbol = self.backtest_symbol_edit.text()
            timeframe = self.backtest_timeframe_combo.currentText()
            start_date = self.backtest_start_date.date().toString("yyyy-MM-dd")
            end_date = self.backtest_end_date.date().toString("yyyy-MM-dd")
            initial_balance = self.backtest_initial_balance.value()
            commission = self.backtest_commission.value()
            strategy_name = self.backtest_strategy_combo.currentText()
            
            # 시장 타입 및 레버리지 가져오기
            market_type = self.backtest_market_type_combo.currentText()
            leverage = 1  # 기본값
            if market_type == 'futures':
                leverage = self.backtest_leverage_spin.value()
            
            self.log_text.append(f"백테스트 시작: {strategy_name} 전략, {symbol}, {start_date}~{end_date}, 시장 타입: {market_type}{', 레버리지: ' + str(leverage) + '배' if market_type == 'futures' else ''}")
            
            # 백테스터 초기화
            backtester = Backtester(exchange_id=exchange, symbol=symbol, timeframe=timeframe, 
                                market_type=market_type, leverage=leverage)
            
            # 전략 생성
            strategy = None
            if strategy_name == 'moving_average':
                # backtest_ma_type이 존재하는지 확인하고 존재하면 사용, 존재하지 않으면 기본값 'sma' 사용
                ma_type = 'sma'
                try:
                    if hasattr(self, 'backtest_ma_type'):
                        ma_type = self.backtest_ma_type.currentText()
                except Exception as e:
                    logger.warning(f"이동평균 유형 설정 오류, 기본값 'sma' 사용: {e}")
                
                strategy = MovingAverageCrossover(
                    short_period=self.backtest_ma_short.value(),
                    long_period=self.backtest_ma_long.value(),
                    ma_type=ma_type
                )
            elif strategy_name == 'rsi':
                strategy = RSIStrategy(
                    period=self.backtest_rsi_period.value(),
                    overbought=self.backtest_rsi_overbought.value(),
                    oversold=self.backtest_rsi_oversold.value()
                )
            elif strategy_name == 'macd':
                strategy = MACDStrategy(
                    fast_period=self.backtest_macd_fast.value(),
                    slow_period=self.backtest_macd_slow.value(),
                    signal_period=self.backtest_macd_signal.value()
                )
            elif strategy_name == 'bollinger_bands':
                strategy = BollingerBandsStrategy(
                    period=self.backtest_bb_period.value(),
                    std_dev=self.backtest_bb_std.value()
                )
            elif strategy_name == 'stochastic':
                strategy = StochasticStrategy(
                    k_period=self.backtest_stoch_k.value(),
                    d_period=self.backtest_stoch_d.value(),
                    overbought=self.backtest_stoch_overbought.value(),
                    oversold=self.backtest_stoch_oversold.value()
                )
            # elif strategy_name == 'breakout':
            #     strategy = BreakoutStrategy(
            #         period=self.backtest_breakout_period.value()
            #     )
            # elif strategy_name == 'volatility_breakout':
            #     strategy = VolatilityBreakoutStrategy(
            #         period=self.backtest_vb_period.value(),
            #         k=self.backtest_vb_k.value()
            #     )
            elif strategy_name == 'bollinger_band_futures':
                # 볼린저 밴드 + RSI + MACD + 헤이킨 아시 기반 선물 전략 실제 객체 생성
                strategy = BollingerBandFuturesStrategy(
                    bb_period=self.backtest_bbf_bb_period.value(),
                    bb_std=self.backtest_bbf_bb_std.value(),
                    rsi_period=self.backtest_bbf_rsi_period.value(),
                    rsi_overbought=self.backtest_bbf_rsi_overbought.value(),
                    rsi_oversold=self.backtest_bbf_rsi_oversold.value(),
                    macd_fast=self.backtest_bbf_macd_fast.value(),
                    macd_slow=self.backtest_bbf_macd_slow.value(),
                    macd_signal=self.backtest_bbf_macd_signal.value(),
                    leverage=self.backtest_bbf_leverage.value(),
                    timeframe=timeframe
                )
            elif strategy_name == 'combined':
                # 선택한 전략들을 조합
                strategies = []
                if self.backtest_use_ma.isChecked():
                    # 이동평균 전략 추가 - 기본값으로 'ema' 사용 (최신 암호화폐에 더 적합)
                    strategies.append(MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'))
                if self.backtest_use_rsi.isChecked():
                    strategies.append(RSIStrategy(period=14, overbought=70, oversold=30))
                if self.backtest_use_macd.isChecked():
                    strategies.append(MACDStrategy(fast_period=12, slow_period=26, signal_period=9))
                if self.backtest_use_bb.isChecked():
                    strategies.append(BollingerBandsStrategy(period=20, std_dev=2.0))
                
                if not strategies:
                    QMessageBox.warning(self, "경고", "적어도 하나 이상의 전략을 선택해야 합니다.")
                    return
                
                # 동일한 가중치 부여
                weights = [1/len(strategies)] * len(strategies)
                strategy = CombinedStrategy(strategies, weights)
            
            # 백테스트 실행
            result = backtester.run_backtest(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                commission=commission
            )
            
            # 결과가 None인지 확인
            if result is None:
                QMessageBox.warning(self, "경고", "백테스트 데이터를 가져오는 데 실패했습니다. \n다른 기간이나 심볼을 선택해보세요.")
                self.log_text.append("백테스트 실패: 데이터를 가져오는 데 실패했습니다.")
                return
            
            # 결과 표시
            self.update_backtest_results(result)
            
            self.log_text.append(f"백테스트 완료: 총 수익률 {result.total_return:.2f}%")
            
            # 결과 저장을 위한 현재 백테스트 결과 저장
            self.current_backtest_result = result
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"백테스트 실행 중 오류 발생: {str(e)}")
            logger.error(f"백테스트 오류: {str(e)}")
    
    def update_backtest_results(self, result):
        """백테스트 결과를 UI에 표시합니다."""
        # result가 None인지 확인
        if result is None:
            # 결과가 없을 경우 테이블 초기화
            for i in range(10):
                self.backtest_result_table.setItem(i, 0, QTableWidgetItem(""))
                self.backtest_result_table.setItem(i, 1, QTableWidgetItem(""))
            return
            
        # 결과 테이블 업데이트
        metrics = [
            ("총 수익률 (%)", f"{result.total_return:.2f}"),
            ("연간 수익률 (%)", f"{result.annual_return:.2f}"),
            ("최대 낙폭 (%)", f"{result.max_drawdown:.2f}"),
            ("승률 (%)", f"{result.win_rate:.2f}"),
            ("총 거래 횟수", f"{result.total_trades}"),
            ("평균 보유 기간", f"{result.average_holding_period:.1f} 일"),
            ("샤프 비율", f"{result.sharpe_ratio:.2f}"),
            ("손익비", f"{result.profit_factor:.2f}"),
            ("최대 연속 손실", f"{result.max_consecutive_losses}"),
            ("최대 연속 이익", f"{result.max_consecutive_wins}")
        ]
        
        for i, (metric, value) in enumerate(metrics):
            self.backtest_result_table.setItem(i, 0, QTableWidgetItem(metric))
            self.backtest_result_table.setItem(i, 1, QTableWidgetItem(value))
        
        # 차트 업데이트
        self.backtest_figure.clear()
        
        # result가 None인지 확인
        if result is None:
            # 결과가 없을 경우 빈 차트 표시
            ax = self.backtest_figure.add_subplot(111)
            ax.text(0.5, 0.5, '백테스트 결과가 없습니다', 
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, fontsize=12)
            ax.axis('off')
            self.backtest_figure.tight_layout()
            self.backtest_canvas.draw()
            return
        
        # 수익률 곡선 그래프
        ax1 = self.backtest_figure.add_subplot(211)
        ax1.plot(result.equity_curve.index, result.equity_curve['equity_curve'] * 100, label='전략')
        ax1.plot(result.equity_curve.index, result.equity_curve['buy_hold_return'] * 100, 'g--', label='Buy & Hold')
        ax1.set_title('수익률 곡선')
        ax1.set_ylabel('수익률 (%)')
        ax1.legend()
        ax1.grid(True)
        
        # 손익 분포 히스토그램
        ax2 = self.backtest_figure.add_subplot(212)
        ax2.hist(result.trade_records['return'] * 100, bins=20, alpha=0.7)
        ax2.set_title('거래별 손익 분포')
        ax2.set_xlabel('수익률 (%)')
        ax2.set_ylabel('빈도')
        ax2.grid(True)
        
        self.backtest_figure.tight_layout()
        self.backtest_canvas.draw()
    
    def save_backtest_result(self):
        """백테스트 결과를 파일로 저장합니다."""
        if not hasattr(self, 'current_backtest_result') or self.current_backtest_result is None:
            QMessageBox.warning(self, "경고", "저장할 백테스트 결과가 없습니다.")
            return
        
        try:
            # 저장 경로 선택 대화상자
            save_path, _ = QFileDialog.getSaveFileName(
                self, "백테스트 결과 저장", "", "CSV 파일 (*.csv);;JSON 파일 (*.json);;모든 파일 (*.*)"
            )
            
            if not save_path:
                return  # 사용자가 취소함
            
            result = self.current_backtest_result
            
            # 파일 확장자에 따라 저장 형식 선택
            if save_path.endswith('.csv'):
                # CSV 형식으로 저장
                # 기본 결과 정보 저장
                with open(save_path, 'w') as f:
                    f.write("항목,값\n")
                    f.write(f"전략,{result.strategy_name}\n")
                    f.write(f"심볼,{result.symbol}\n")
                    f.write(f"타임프레임,{result.timeframe}\n")
                    f.write(f"시작 날짜,{result.start_date}\n")
                    f.write(f"종료 날짜,{result.end_date}\n")
                    f.write(f"초기 자본,{result.initial_balance}\n")
                    f.write(f"최종 자본,{result.final_balance}\n")
                    f.write(f"총 수익률,{result.total_return:.4f}\n")
                    f.write(f"연간 수익률,{result.annual_return:.4f}\n")
                    f.write(f"최대 낙폭,{result.max_drawdown:.4f}\n")
                    f.write(f"승률,{result.win_rate:.4f}\n")
                    f.write(f"총 거래 횟수,{result.total_trades}\n")
                    f.write(f"평균 보유 기간,{result.average_holding_period:.2f}\n")
                    f.write(f"샤프 비율,{result.sharpe_ratio:.4f}\n")
                    f.write(f"손익비,{result.profit_factor:.4f}\n")
                    f.write(f"최대 연속 손실,{result.max_consecutive_losses}\n")
                    f.write(f"최대 연속 이익,{result.max_consecutive_wins}\n")
                
                # 거래 기록 저장
                trade_csv_path = save_path.replace('.csv', '_trades.csv')
                result.trade_records.to_csv(trade_csv_path, index=False)
                
                # 수익률 곡선 저장
                equity_csv_path = save_path.replace('.csv', '_equity.csv')
                result.equity_curve.to_csv(equity_csv_path)
                
            elif save_path.endswith('.json'):
                # JSON 형식으로 저장
                import json
                
                # 기본 결과 정보
                result_dict = {
                    "strategy_name": result.strategy_name,
                    "symbol": result.symbol,
                    "timeframe": result.timeframe,
                    "start_date": result.start_date,
                    "end_date": result.end_date,
                    "initial_balance": result.initial_balance,
                    "final_balance": result.final_balance,
                    "total_return": result.total_return,
                    "annual_return": result.annual_return,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                    "average_holding_period": result.average_holding_period,
                    "sharpe_ratio": result.sharpe_ratio,
                    "profit_factor": result.profit_factor,
                    "max_consecutive_losses": result.max_consecutive_losses,
                    "max_consecutive_wins": result.max_consecutive_wins,
                    # 거래 기록과 수익률 곡선은 별도 파일로 저장
                }
                
                with open(save_path, 'w') as f:
                    json.dump(result_dict, f, indent=4)
                
                # 거래 기록과 수익률 곡선은 CSV로 별도 저장
                trade_csv_path = save_path.replace('.json', '_trades.csv')
                result.trade_records.to_csv(trade_csv_path, index=False)
                
                equity_csv_path = save_path.replace('.json', '_equity.csv')
                result.equity_curve.to_csv(equity_csv_path)
            
            # 그래프 이미지 저장
            fig_path = save_path.replace('.csv', '.png').replace('.json', '.png')
            self.backtest_figure.savefig(fig_path, dpi=300, bbox_inches='tight')
            
            QMessageBox.information(self, "알림", f"백테스트 결과가 성공적으로 저장되었습니다.\n{save_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"백테스트 결과 저장 중 오류 발생: {str(e)}")
            logger.error(f"백테스트 결과 저장 오류: {str(e)}")
    
    # API 호출을 위한 메서드들
    def get_bot_status(self):
        """
        봇의 현재 상태를 반환하는 메서드
        
        Returns:
            dict: 봇의 상태 정보
        """
        # 헤드리스 모드일 경우 기본 심볼 사용
        default_symbol = "BTC/USDT"  # 기본 심볼 직접 정의
        
        return {
            'running': self.bot_running,
            'exchange': self.exchange_id,
            'symbol': self.symbol_combo.currentText() if not self.headless else default_symbol,
            'strategy': self.strategy_combo.currentText() if not self.headless else self.current_strategy,
            'balance': self.balance_data
        }
    
    def start_bot_api(self, strategy=None, symbol=None, timeframe=None, auto_sl_tp=False, partial_tp=False, strategy_params=None):
        """
        API를 통해 봇을 시작하는 메서드
        
        Args:
            strategy (str, optional): 사용할 전략
            symbol (str, optional): 거래 심볼
            timeframe (str, optional): 타임프레임
            auto_sl_tp (bool, optional): 자동 손절매/이익실현 활성화 여부
            partial_tp (bool, optional): 부분 청산 활성화 여부
            strategy_params (dict, optional): 전략별 세부 파라미터
            
        Returns:
            dict: 성공/실패 상태 및 메시지
        """
        try:
            if self.bot_running:
                return {'success': False, 'message': '봇이 이미 실행 중입니다.'}
            
            # 거래 심볼 설정
            if symbol and not self.headless:
                index = self.symbol_combo.findText(symbol)
                if index >= 0:
                    self.symbol_combo.setCurrentIndex(index)
            
            # 헤드리스 모드에서도 심볼과 타임프레임 설정
            if symbol:
                self.symbol = symbol
            if timeframe:
                self.timeframe = timeframe
            
            # 전략 설정
            if strategy:
                # 헤드리스 모드에서도 전략 이름 저장
                self.current_strategy = strategy
                self.strategy = strategy  # strategy 속성에도 저장
                logger.info(f"전략 설정: {strategy}")
                
                # 전략 파라미터 저장
                if strategy_params:
                    self.strategy_params = strategy_params
                    logger.info(f"전략 파라미터 설정: {strategy_params}")
                
                # UI 업데이트는 헤드리스 모드가 아닐 때만
                if not self.headless:
                    index = self.strategy_combo.findText(strategy)
                    if index >= 0:
                        self.strategy_combo.setCurrentIndex(index)
            
            # 봇 시작
            if not self.headless:
                self.start_bot()
            else:
                # 헤드리스 모드에서 봇 시작 로직
                self.bot_running = True
                # interval 값 가져오기 (헤드리스 모드에서는 기본값 사용)
                interval = self.interval_spin.value() if hasattr(self, 'interval_spin') else 3600  # 기본값 1시간(3600초)
                # 자동 손절매/이익실현 및 부분 청산 옵션, 전략 파라미터를 포함한 BotThread 생성
                self.bot_thread = BotThread(self, interval, auto_sl_tp=auto_sl_tp, partial_tp=partial_tp, strategy_params=strategy_params)
                self.bot_thread.update_signal.connect(self.update_bot_status)
                self.bot_thread.start()
            
            return {'success': True, 'message': '봇 시작 성공'}
        except Exception as e:
            return {'success': False, 'message': f'봇 시작 실패: {str(e)}'}
    
    def stop_bot_api(self):
        """
        API를 통해 봇을 중지하는 메서드
        
        Returns:
            dict: 성공/실패 상태 및 메시지
        """
        try:
            if not self.bot_running:
                return {'success': False, 'message': '봇이 실행 중이 아닙니다.'}
            
            # 봇 중지
            if not self.headless:
                self.stop_bot()
            else:
                # 헤드리스 모드에서 봇 중지 로직
                if self.bot_thread:
                    self.bot_thread.stop()
                    self.bot_thread = None
                self.bot_running = False
            
            return {'success': True, 'message': '봇 중지 성공'}
        except Exception as e:
            return {'success': False, 'message': f'봇 중지 실패: {str(e)}'}
    
    def update_bot_status(self, message):
        """
        봇 상태 업데이트 메서드 (API 용)
        
        Args:
            message (str): 상태 메시지
        """
        if message.startswith('잔액:'):
            # 잔액 정보 추출 및 저장
            try:
                # '잔액: 1000 USD' 같은 형식에서 금액과 통화 추출
                parts = message.split(': ')[1].split(' ')
                amount = float(parts[0])
                currency = parts[1]
                self.balance_data = {'amount': amount, 'currency': currency}
            except Exception as e:
                logger.error(f"잔액 정보 추출 오류: {str(e)}")
        
        # 로그 메시지 출력
        if not self.headless:
            self.log_text.append(message)
        logger.info(message)

    def get_balance_api(self):
        """
        API를 통해 잔액 정보를 반환하는 메서드
        
        Returns:
            dict: 잔액 정보 (현물 및 선물 잔고 모두 포함)
        """
        # 기존에 저장된 잔액 정보가 있는지 확인
        if self.balance_data:
            return {'success': True, 'data': self.balance_data}
            
        # 기존 잔액 정보가 없으면 바이낸스에서 직접 가져오기 시도
        try:
            # 거래소 API가 초기화되어 있는지 확인
            if hasattr(self, 'exchange_api') and self.exchange_api:
                # 현물+선물 모든 잔액 정보 가져오기
                balance_result = self.exchange_api.get_balance('all')
                
                # 설정된 시장 유형에 따라 적절한 잔고 정보 선택
                market_type = 'spot'
                if hasattr(self.exchange_api, 'market_type'):
                    market_type = self.exchange_api.market_type
                
                # 선물 거래인 경우 선물 잔고 사용
                if market_type == 'futures' and balance_result.get('future'):
                    logger.info("선물 잔고 정보를 사용합니다.")
                    future_balance = balance_result['future']
                    if future_balance and 'total' in future_balance:
                        # USDT 선물 잔고 찾기
                        for currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                            if currency in future_balance['total']:
                                total_balance = future_balance['total'][currency]
                                self.balance_data = {
                                    'amount': total_balance, 
                                    'currency': currency,
                                    'type': 'future'
                                }
                                return {'success': True, 'data': self.balance_data}
                
                # 현물 잔고 사용 (바이낸스 일반 잔고 또는 선물 거래 정보가 없는 경우)
                spot_balance = balance_result.get('spot') or balance_result
                if spot_balance and 'total' in spot_balance:
                    # 스테이블코인 잔고 찾기
                    for currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                        if currency in spot_balance['total'] and spot_balance['total'][currency] > 0:
                            total_balance = spot_balance['total'][currency]
                            self.balance_data = {
                                'amount': total_balance, 
                                'currency': currency,
                                'type': 'spot'
                            }
                            return {'success': True, 'data': self.balance_data}
                    
                    # 그 외의 통화 잔고 찾기
                    for currency in ['BTC', 'ETH']:
                        if currency in spot_balance['total'] and spot_balance['total'][currency] > 0:
                            total_balance = spot_balance['total'][currency]
                            self.balance_data = {
                                'amount': total_balance, 
                                'currency': currency,
                                'type': 'spot'
                            }
                            return {'success': True, 'data': self.balance_data}
            
            # 거래소 API가 없거나 가져오기 실패한 경우
            return {'success': False, 'message': '잔액 정보가 없습니다. 봇이 실행 중인지 확인하세요.'}
        except Exception as e:
            logger.error(f"잔액 정보 조회 중 오류: {str(e)}")
            return {'success': False, 'message': f'잔액 정보 조회 중 오류: {str(e)}'}

# 메인 함수
def main(headless=False):
    """암호화폐 거래 봇 GUI 실행 함수
    
    Args:
        headless (bool): GUI를 화면에 표시하지 않는 모드
    
    Returns:
        GUI 경우 None을 반환, 헤드리스 모드의 경우 CryptoTradingBotGUI 인스턴스 반환
    """
    if headless:
        # 헤드리스 모드 - GUI 표시 없이 인스턴스 반환
        # Qt 애플리케이션이 없으면 생성
        if not QApplication.instance():
            app = QApplication(sys.argv)
        window = CryptoTradingBotGUI(headless=True)
        return window
    else:
        # 일반 GUI 모드
        app = QApplication(sys.argv)
        window = CryptoTradingBotGUI(headless=False)
        window.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
