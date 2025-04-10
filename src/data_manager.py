"""
데이터 관리 모듈 - 암호화폐 자동매매 봇

이 모듈은 거래 데이터의 저장, 로드, 관리 기능을 제공합니다.
OHLCV 데이터, 거래 기록, 백테스팅 결과 등을 파일로 저장하고 불러오는 기능을 담당합니다.
"""

import os
import pandas as pd
import json
import pickle
from datetime import datetime
import logging
from config import DATA_DIR, LOG_DIR

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('data_manager')

class DataManager:
    """데이터 저장 및 관리를 위한 클래스"""
    
    def __init__(self, exchange_id='binance', symbol='BTC/USDT'):
        """
        데이터 관리자 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.symbol_filename = symbol.replace('/', '_')
        
        # 거래소별 데이터 디렉토리 생성
        self.exchange_data_dir = os.path.join(DATA_DIR, exchange_id)
        os.makedirs(self.exchange_data_dir, exist_ok=True)
        
        # 로그 디렉토리 생성
        self.log_dir = LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
    
    def save_ohlcv_data(self, df, timeframe='1h'):
        """
        OHLCV 데이터를 CSV 파일로 저장
        
        Args:
            df (DataFrame): OHLCV 데이터
            timeframe (str): 타임프레임 (예: '1m', '1h', '1d')
        
        Returns:
            str: 저장된 파일 경로
        """
        try:
            filename = f"{self.symbol_filename}_{timeframe}.csv"
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            df.to_csv(filepath, index=False)
            logger.info(f"OHLCV 데이터 저장 완료: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"OHLCV 데이터 저장 중 오류 발생: {e}")
            return None
    
    def load_ohlcv_data(self, timeframe='1h'):
        """
        저장된 OHLCV 데이터를 로드
        
        Args:
            timeframe (str): 타임프레임 (예: '1m', '1h', '1d')
        
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            filename = f"{self.symbol_filename}_{timeframe}.csv"
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"OHLCV 데이터 파일이 존재하지 않습니다: {filepath}")
                return None
            
            df = pd.read_csv(filepath)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"OHLCV 데이터 로드 완료: {filepath}")
            return df
        
        except Exception as e:
            logger.error(f"OHLCV 데이터 로드 중 오류 발생: {e}")
            return None
    
    def save_trade_history(self, trades, strategy_name='default'):
        """
        거래 기록을 JSON 파일로 저장
        
        Args:
            trades (list): 거래 기록 리스트
            strategy_name (str): 전략 이름
        
        Returns:
            str: 저장된 파일 경로
        """
        try:
            date_str = datetime.now().strftime('%Y%m%d')
            filename = f"{self.symbol_filename}_{strategy_name}_trades_{date_str}.json"
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(trades, f, indent=4, default=str)
            
            logger.info(f"거래 기록 저장 완료: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"거래 기록 저장 중 오류 발생: {e}")
            return None
    
    def load_trade_history(self, strategy_name='default', date_str=None):
        """
        저장된 거래 기록을 로드
        
        Args:
            strategy_name (str): 전략 이름
            date_str (str): 날짜 문자열 (YYYYMMDD 형식, None인 경우 최신 파일)
        
        Returns:
            list: 거래 기록 리스트
        """
        try:
            if date_str is None:
                # 날짜가 지정되지 않은 경우 최신 파일 찾기
                pattern = f"{self.symbol_filename}_{strategy_name}_trades_*.json"
                files = [f for f in os.listdir(self.exchange_data_dir) if f.startswith(f"{self.symbol_filename}_{strategy_name}_trades_")]
                
                if not files:
                    logger.warning(f"거래 기록 파일이 존재하지 않습니다.")
                    return []
                
                # 파일명 기준 정렬하여 최신 파일 선택
                files.sort(reverse=True)
                filename = files[0]
            else:
                filename = f"{self.symbol_filename}_{strategy_name}_trades_{date_str}.json"
            
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"거래 기록 파일이 존재하지 않습니다: {filepath}")
                return []
            
            with open(filepath, 'r') as f:
                trades = json.load(f)
            
            logger.info(f"거래 기록 로드 완료: {filepath}")
            return trades
        
        except Exception as e:
            logger.error(f"거래 기록 로드 중 오류 발생: {e}")
            return []
    
    def save_backtest_result(self, result, strategy_name='default'):
        """
        백테스팅 결과를 저장
        
        Args:
            result (dict): 백테스팅 결과
            strategy_name (str): 전략 이름
        
        Returns:
            str: 저장된 파일 경로
        """
        try:
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.symbol_filename}_{strategy_name}_backtest_{date_str}.pkl"
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            with open(filepath, 'wb') as f:
                pickle.dump(result, f)
            
            # 요약 정보는 JSON으로도 저장
            summary = {k: str(v) if isinstance(v, (pd.DataFrame, pd.Series)) else v 
                      for k, v in result.items() if k != 'trades_df'}
            
            summary_filename = f"{self.symbol_filename}_{strategy_name}_backtest_{date_str}_summary.json"
            summary_filepath = os.path.join(self.exchange_data_dir, summary_filename)
            
            with open(summary_filepath, 'w') as f:
                json.dump(summary, f, indent=4, default=str)
            
            logger.info(f"백테스팅 결과 저장 완료: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"백테스팅 결과 저장 중 오류 발생: {e}")
            return None
    
    def load_backtest_result(self, strategy_name='default', date_str=None):
        """
        저장된 백테스팅 결과를 로드
        
        Args:
            strategy_name (str): 전략 이름
            date_str (str): 날짜 문자열 (YYYYMMDD_HHMMSS 형식, None인 경우 최신 파일)
        
        Returns:
            dict: 백테스팅 결과
        """
        try:
            if date_str is None:
                # 날짜가 지정되지 않은 경우 최신 파일 찾기
                files = [f for f in os.listdir(self.exchange_data_dir) 
                        if f.startswith(f"{self.symbol_filename}_{strategy_name}_backtest_") and f.endswith('.pkl')]
                
                if not files:
                    logger.warning(f"백테스팅 결과 파일이 존재하지 않습니다.")
                    return None
                
                # 파일명 기준 정렬하여 최신 파일 선택
                files.sort(reverse=True)
                filename = files[0]
            else:
                filename = f"{self.symbol_filename}_{strategy_name}_backtest_{date_str}.pkl"
            
            filepath = os.path.join(self.exchange_data_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"백테스팅 결과 파일이 존재하지 않습니다: {filepath}")
                return None
            
            with open(filepath, 'rb') as f:
                result = pickle.load(f)
            
            logger.info(f"백테스팅 결과 로드 완료: {filepath}")
            return result
        
        except Exception as e:
            logger.error(f"백테스팅 결과 로드 중 오류 발생: {e}")
            return None

# 테스트 코드
if __name__ == "__main__":
    # 테스트용 데이터 생성
    data_manager = DataManager(exchange_id='binance', symbol='BTC/USDT')
    
    # 테스트용 OHLCV 데이터 생성
    test_data = {
        'timestamp': [datetime.now() for _ in range(5)],
        'open': [10000, 10100, 10200, 10300, 10400],
        'high': [10100, 10200, 10300, 10400, 10500],
        'low': [9900, 10000, 10100, 10200, 10300],
        'close': [10050, 10150, 10250, 10350, 10450],
        'volume': [100, 150, 200, 250, 300]
    }
    df = pd.DataFrame(test_data)
    
    # OHLCV 데이터 저장 테스트
    filepath = data_manager.save_ohlcv_data(df, timeframe='1h')
    print(f"OHLCV 데이터 저장 경로: {filepath}")
    
    # OHLCV 데이터 로드 테스트
    loaded_df = data_manager.load_ohlcv_data(timeframe='1h')
    print("\n로드된 OHLCV 데이터:")
    print(loaded_df.head())
