"""
데이터 수집 모듈 - 암호화폐 자동매매 봇

이 모듈은 실시간 및 과거 시장 데이터를 수집하는 기능을 제공합니다.
다양한 거래소에서 OHLCV 데이터를 가져오고 저장하는 기능을 담당합니다.
"""

import pandas as pd
import numpy as np
import time
import logging
import os
from datetime import datetime, timedelta
from src.exchange_api import ExchangeAPI
from src.data_manager import DataManager
from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('data_collector')

class DataCollector:
    """시장 데이터 수집을 위한 클래스"""
    
    def __init__(self, exchange_id=DEFAULT_EXCHANGE, symbol=DEFAULT_SYMBOL, timeframe=DEFAULT_TIMEFRAME):
        """
        데이터 수집기 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
            timeframe (str): 타임프레임
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        
        # 거래소 API 및 데이터 관리자 초기화
        self.exchange_api = ExchangeAPI(exchange_id=exchange_id, symbol=symbol, timeframe=timeframe)
        self.data_manager = DataManager(exchange_id=exchange_id, symbol=symbol)
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 데이터 수집기가 초기화되었습니다.")
    
    def fetch_recent_data(self, limit=100):
        """
        최근 OHLCV 데이터 가져오기
        
        Args:
            limit (int): 가져올 데이터 개수
        
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            logger.info(f"{self.symbol}의 최근 {limit}개 OHLCV 데이터를 가져오는 중...")
            df = self.exchange_api.get_ohlcv(limit=limit)
            
            if df is not None and not df.empty:
                logger.info(f"{len(df)}개의 OHLCV 데이터를 성공적으로 가져왔습니다.")
                return df
            else:
                logger.warning("OHLCV 데이터를 가져오지 못했습니다.")
                return None
        
        except Exception as e:
            logger.error(f"최근 데이터 가져오기 중 오류 발생: {e}")
            return None
    
    def fetch_historical_data(self, start_date, end_date=None, save=True):
        """
        과거 OHLCV 데이터 가져오기
        
        Args:
            start_date (str): 시작 날짜 (YYYY-MM-DD 형식)
            end_date (str, optional): 종료 날짜 (YYYY-MM-DD 형식, None인 경우 현재까지)
            save (bool): 데이터 저장 여부
        
        Returns:
            DataFrame: OHLCV 데이터
        """
        try:
            # 종료 날짜가 지정되지 않은 경우 현재 날짜 사용
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"{self.symbol}의 {start_date}부터 {end_date}까지의 과거 데이터를 가져오는 중...")
            
            # 날짜를 datetime 객체로 변환
            try:
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
            except Exception as e:
                logger.error(f"날짜 변환 오류: {e}")
                start_dt = pd.to_datetime(start_date, format='%Y-%m-%d')
                end_dt = pd.to_datetime(end_date, format='%Y-%m-%d')
                
            logger.info(f"변환된 날짜: {start_dt} ~ {end_dt}")
            
            # 가져온 데이터를 저장할 리스트
            all_data = []
            current_start = start_dt
            
            # Binance인 경우 다른 기간 계산 방식 사용
            is_binance = self.exchange_id.lower() == 'binance'
            
            while current_start < end_dt:
                # 타임프레임과 거래소에 따라 적절한 기간 계산
                if is_binance:
                    # Binance는 더 짧은 기간으로 분할하여 개선
                    if self.timeframe == '1m':
                        current_end = min(current_start + timedelta(hours=12), end_dt)  # 12시간만
                    elif self.timeframe in ['5m', '15m', '30m']:
                        current_end = min(current_start + timedelta(days=2), end_dt)   # 2일만
                    elif self.timeframe == '1h':
                        current_end = min(current_start + timedelta(days=7), end_dt)   # 7일만
                    elif self.timeframe == '4h':
                        current_end = min(current_start + timedelta(days=15), end_dt)  # 15일만
                    else:  # 1d 이상
                        current_end = min(current_start + timedelta(days=100), end_dt) # 100일만
                else:
                    # 다른 거래소는 기존 방식 유지
                    if self.timeframe == '1m':
                        current_end = min(current_start + timedelta(days=1), end_dt)
                    elif self.timeframe in ['5m', '15m']:
                        current_end = min(current_start + timedelta(days=5), end_dt)
                    elif self.timeframe == '1h':
                        current_end = min(current_start + timedelta(days=30), end_dt)
                    else:  # 1d 이상
                        current_end = min(current_start + timedelta(days=365), end_dt)
                
                # 시작 시간과 종료 시간을 밀리초로 변환
                since = int(current_start.timestamp() * 1000)
                until = int(current_end.timestamp() * 1000)
                
                # 여러 번 시도
                retry_count = 0
                max_retries = 3
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        # CCXT를 통해 OHLCV 데이터 가져오기
                        ohlcv = self.exchange_api.exchange.fetch_ohlcv(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            since=since,
                            limit=1000  # 대부분의 거래소에서 지원하는 최대 제한
                        )
                        success = True
                    except Exception as e:
                        retry_count += 1
                        logger.warning(f"OHLCV 데이터 가져오기 실패 ({retry_count}/{max_retries}): {e}")
                        time.sleep(2)  # 재시도 전 대기 시간 증가
                
                if success and ohlcv and len(ohlcv) > 0:
                    # 데이터프레임으로 변환
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    # 시간스탬프를 인덱스로 설정
                    df.set_index('timestamp', inplace=True)
                    
                    all_data.append(df)
                    logger.info(f"{current_start.strftime('%Y-%m-%d %H:%M')}부터 {current_end.strftime('%Y-%m-%d %H:%M')}까지 {len(df)}개의 데이터를 가져왔습니다.")
                elif not success:
                    logger.error(f"{current_start.strftime('%Y-%m-%d %H:%M')}부터 {current_end.strftime('%Y-%m-%d %H:%M')}까지 데이터 가져오기 실패")
                
                # 다음 기간으로 이동
                current_start = current_end
                
                # API 호출 제한을 피하기 위한 대기
                time.sleep(1)
            
            if all_data:
                # 모든 데이터 병합
                result_df = pd.concat(all_data)
                
                # 중복 제거 및 정렬
                result_df = result_df[~result_df.index.duplicated(keep='first')].sort_index()
                
                # 데이터 업샘플링 검사 (1분 데이터에서 더 긴 타임프레임으로 분석하는 경우를 위해)
                if self.timeframe != '1m' and len(result_df) > 0:
                    logger.info(f"데이터 업샘플링 여부 확인: {self.timeframe} 타임프레임")
                    # 파입된 시간보다 더 짧은 시간의 데이터가 있는지 확인
                    if result_df.index.to_series().diff().min().total_seconds() < self.timeframe_to_seconds(self.timeframe):
                        logger.info("데이터 업샘플링 필요")
                        # 타임프레임에 맞게 다시 폴링
                        result_df = self.resample_data(result_df, self.timeframe)
                
                logger.info(f"총 {len(result_df)}개의 과거 데이터를 성공적으로 가져왔습니다.")
                
                # 데이터 저장
                if save:
                    filepath = self.data_manager.save_ohlcv_data(result_df, timeframe=self.timeframe)
                    logger.info(f"과거 데이터를 {filepath}에 저장했습니다.")
                
                return result_df
            else:
                logger.warning("과거 데이터를 가져오지 못했습니다.")
                return None
        
        except Exception as e:
            logger.error(f"과거 데이터 가져오기 중 오류 발생: {e}")
            return None
    
    def timeframe_to_seconds(self, timeframe):
        """
        타임프레임 문자열을 초 단위로 변환
        
        Args:
            timeframe (str): 타임프레임 문자열 (1m, 5m, 1h, 1d 등)
            
        Returns:
            int: 초 단위 값
        """
        # 숫자와 단위 분리
        value = int(''.join(filter(str.isdigit, timeframe)))
        unit = ''.join(filter(str.isalpha, timeframe))
        
        if unit == 'm':
            return value * 60  # 분 
        elif unit == 'h':
            return value * 60 * 60  # 시간
        elif unit == 'd':
            return value * 60 * 60 * 24  # 일
        elif unit == 'w':
            return value * 60 * 60 * 24 * 7  # 주
        else:
            raise ValueError(f"알 수 없는 타임프레임 형식: {timeframe}")
    
    def resample_data(self, df, timeframe):
        """
        데이터를 지정된 타임프레임으로 리샘플링
        
        Args:
            df (DataFrame): OHLCV 데이터프레임
            timeframe (str): 변환할 타임프레임 (1m, 5m, 1h, 1d 등)
            
        Returns:
            DataFrame: 리샘플링된 데이터프레임
        """
        # 타임프레임 문자열을 pandas 리샘플링 규칙으로 변환
        if timeframe == '1m':
            rule = '1min'
        elif timeframe == '5m':
            rule = '5min'
        elif timeframe == '15m':
            rule = '15min'
        elif timeframe == '30m':
            rule = '30min'
        elif timeframe == '1h':
            rule = '1H'
        elif timeframe == '4h':
            rule = '4H'
        elif timeframe == '1d':
            rule = '1D'
        else:
            raise ValueError(f"지원되지 않는 타임프레임: {timeframe}")
        
        # OHLCV 리샘플링
        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # NaN 값 제거
        resampled = resampled.dropna()
        
        logger.info(f"데이터 리샘플링 완료: {len(df)} -> {len(resampled)} 레코드")
        return resampled
    
    def fetch_realtime_data(self, interval=60, callback=None):
        """
        실시간 OHLCV 데이터 수집 (주기적으로 데이터 가져오기)
        
        Args:
            interval (int): 데이터 수집 간격 (초)
            callback (function, optional): 데이터 수집 후 호출할 콜백 함수
        """
        try:
            logger.info(f"{self.symbol}의 실시간 데이터 수집을 시작합니다. (간격: {interval}초)")
            
            while True:
                # 최근 데이터 가져오기
                df = self.fetch_recent_data(limit=10)
                
                if df is not None and not df.empty:
                    # 데이터 저장
                    self.data_manager.save_ohlcv_data(df, timeframe=self.timeframe)
                    
                    # 콜백 함수 호출
                    if callback is not None:
                        callback(df)
                
                # 다음 수집까지 대기
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("사용자에 의해 실시간 데이터 수집이 중단되었습니다.")
        
        except Exception as e:
            logger.error(f"실시간 데이터 수집 중 오류 발생: {e}")
    
    def update_data(self, save=True):
        """
        저장된 데이터를 최신 상태로 업데이트
        
        Args:
            save (bool): 데이터 저장 여부
        
        Returns:
            DataFrame: 업데이트된 OHLCV 데이터
        """
        try:
            # 저장된 데이터 로드
            df = self.data_manager.load_ohlcv_data(timeframe=self.timeframe)
            
            if df is None or df.empty:
                logger.warning("저장된 데이터가 없습니다. 최근 데이터를 가져옵니다.")
                return self.fetch_recent_data(limit=100)
            
            # 마지막 데이터 시간 확인
            last_time = df['timestamp'].max()
            
            # 현재 시간
            now = datetime.now()
            
            # 마지막 데이터 이후의 데이터 가져오기
            since = int(last_time.timestamp() * 1000)
            
            logger.info(f"{last_time} 이후의 데이터를 가져오는 중...")
            
            # CCXT를 통해 OHLCV 데이터 가져오기
            ohlcv = self.exchange_api.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                since=since,
                limit=1000
            )
            
            if ohlcv and len(ohlcv) > 0:
                # 데이터프레임으로 변환
                new_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
                
                # 중복 제거를 위해 마지막 데이터 제외
                new_df = new_df[new_df['timestamp'] > last_time]
                
                if not new_df.empty:
                    # 기존 데이터와 새 데이터 병합
                    result_df = pd.concat([df, new_df])
                    
                    # 중복 제거 및 정렬
                    result_df = result_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
                    
                    # 인덱스 재설정
                    result_df = result_df.reset_index(drop=True)
                    
                    logger.info(f"{len(new_df)}개의 새로운 데이터를 추가했습니다. 총 {len(result_df)}개의 데이터가 있습니다.")
                    
                    # 데이터 저장
                    if save:
                        filepath = self.data_manager.save_ohlcv_data(result_df, timeframe=self.timeframe)
                        logger.info(f"업데이트된 데이터를 {filepath}에 저장했습니다.")
                    
                    return result_df
                else:
                    logger.info("새로운 데이터가 없습니다.")
                    return df
            else:
                logger.info("새로운 데이터가 없습니다.")
                return df
        
        except Exception as e:
            logger.error(f"데이터 업데이트 중 오류 발생: {e}")
            return None

# 테스트 코드
if __name__ == "__main__":
    # 데이터 수집기 초기화
    collector = DataCollector(exchange_id='binance', symbol='BTC/USDT', timeframe='1h')
    
    # 최근 데이터 가져오기
    recent_data = collector.fetch_recent_data(limit=10)
    print("\n최근 데이터:")
    print(recent_data.head())
    
    # 과거 데이터 가져오기 (지난 30일)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    historical_data = collector.fetch_historical_data(start_date=start_date, end_date=end_date)
    if historical_data is not None:
        print(f"\n과거 데이터 ({start_date} ~ {end_date}):")
        print(f"총 {len(historical_data)}개의 데이터")
        print(historical_data.head())
    
    # 데이터 업데이트 테스트
    updated_data = collector.update_data()
    if updated_data is not None:
        print("\n업데이트된 데이터:")
        print(f"총 {len(updated_data)}개의 데이터")
        print(updated_data.tail())
