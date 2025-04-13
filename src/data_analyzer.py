"""
데이터 분석 모듈 - 암호화폐 자동매매 봇

이 모듈은 수집된 시장 데이터를 분석하고 시각화하는 기능을 제공합니다.
기술적 분석 지표를 적용하고 차트를 생성하여 시장 동향을 파악합니다.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import logging
import os
from datetime import datetime, timedelta
from src.indicators import (
    simple_moving_average, exponential_moving_average, 
    moving_average_convergence_divergence, relative_strength_index,
    bollinger_bands, stochastic_oscillator
)
from src.data_manager import DataManager
from src.config import DATA_DIR

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('data_analyzer')

class DataAnalyzer:
    """시장 데이터 분석을 위한 클래스"""
    
    def __init__(self, exchange_id='binance', symbol='BTC/USDT'):
        """
        데이터 분석기 초기화
        
        Args:
            exchange_id (str): 거래소 ID
            symbol (str): 거래 심볼
        """
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.data_manager = DataManager(exchange_id=exchange_id, symbol=symbol)
        
        # 시각화 결과 저장 디렉토리
        self.charts_dir = os.path.join(DATA_DIR, 'charts')
        os.makedirs(self.charts_dir, exist_ok=True)
        
        logger.info(f"{exchange_id} 거래소의 {symbol} 데이터 분석기가 초기화되었습니다.")
    
    def apply_indicators(self, df, indicators=None):
        """
        데이터프레임에 기술적 분석 지표 적용
        
        Args:
            df (DataFrame): OHLCV 데이터
            indicators (dict): 적용할 지표 설정
        
        Returns:
            DataFrame: 지표가 추가된 데이터프레임
        """
        if indicators is None:
            indicators = {
                'sma': [20, 50, 200],
                'ema': [9, 21],
                'macd': True,
                'rsi': True,
                'bollinger': True,
                'stochastic': True
            }
        
        # 데이터프레임 복사
        result_df = df.copy()
        
        try:
            # SMA 적용
            if 'sma' in indicators and indicators['sma']:
                for period in indicators['sma']:
                    result_df[f'sma_{period}'] = simple_moving_average(df, period=period)
            
            # EMA 적용
            if 'ema' in indicators and indicators['ema']:
                for period in indicators['ema']:
                    result_df[f'ema_{period}'] = exponential_moving_average(df, period=period)
            
            # MACD 적용
            if 'macd' in indicators and indicators['macd']:
                macd_line, signal_line, histogram = moving_average_convergence_divergence(df)
                result_df['macd'] = macd_line
                result_df['macd_signal'] = signal_line
                result_df['macd_histogram'] = histogram
            
            # RSI 적용
            if 'rsi' in indicators and indicators['rsi']:
                result_df['rsi'] = relative_strength_index(df)
            
            # 볼린저 밴드 적용
            if 'bollinger' in indicators and indicators['bollinger']:
                middle_band, upper_band, lower_band = bollinger_bands(df)
                result_df['bb_middle'] = middle_band
                result_df['bb_upper'] = upper_band
                result_df['bb_lower'] = lower_band
            
            # 스토캐스틱 오실레이터 적용
            if 'stochastic' in indicators and indicators['stochastic']:
                k, d = stochastic_oscillator(df)
                result_df['stoch_k'] = k
                result_df['stoch_d'] = d
            
            logger.info(f"기술적 분석 지표 적용 완료")
            return result_df
        
        except Exception as e:
            logger.error(f"지표 적용 중 오류 발생: {e}")
            return df
    
    def plot_price_chart(self, df, title=None, save_path=None, show=True):
        """
        가격 차트 생성
        
        Args:
            df (DataFrame): OHLCV 데이터
            title (str, optional): 차트 제목
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            # 차트 크기 설정
            plt.figure(figsize=(14, 10))
            
            # 제목 설정
            if title is None:
                title = f"{self.symbol} 가격 차트"
            
            # 가격 차트 (메인)
            ax1 = plt.subplot2grid((6, 1), (0, 0), rowspan=3, colspan=1)
            ax1.set_title(title, fontsize=14)
            ax1.plot(df.index, df['close'], label='종가', color='black', linewidth=2)
            
            # 이동평균선 추가
            if 'sma_20' in df.columns:
                ax1.plot(df.index, df['sma_20'], label='SMA(20)', color='blue', linewidth=1)
            if 'sma_50' in df.columns:
                ax1.plot(df.index, df['sma_50'], label='SMA(50)', color='green', linewidth=1)
            if 'sma_200' in df.columns:
                ax1.plot(df.index, df['sma_200'], label='SMA(200)', color='red', linewidth=1)
            if 'ema_9' in df.columns:
                ax1.plot(df.index, df['ema_9'], label='EMA(9)', color='purple', linewidth=1, linestyle='--')
            if 'ema_21' in df.columns:
                ax1.plot(df.index, df['ema_21'], label='EMA(21)', color='orange', linewidth=1, linestyle='--')
            
            # 볼린저 밴드 추가
            if 'bb_upper' in df.columns and 'bb_middle' in df.columns and 'bb_lower' in df.columns:
                ax1.plot(df.index, df['bb_upper'], label='BB Upper', color='gray', linewidth=0.5, linestyle='--')
                ax1.plot(df.index, df['bb_middle'], label='BB Middle', color='gray', linewidth=0.5)
                ax1.plot(df.index, df['bb_lower'], label='BB Lower', color='gray', linewidth=0.5, linestyle='--')
                ax1.fill_between(df.index, df['bb_upper'], df['bb_lower'], color='gray', alpha=0.1)
            
            ax1.set_ylabel('가격', fontsize=12)
            ax1.legend(loc='upper left', fontsize=10)
            ax1.grid(True, alpha=0.3)
            
            # 거래량 차트
            ax2 = plt.subplot2grid((6, 1), (3, 0), rowspan=1, colspan=1, sharex=ax1)
            ax2.bar(df.index, df['volume'], label='거래량', color='blue', alpha=0.5)
            ax2.set_ylabel('거래량', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            # MACD 차트
            if 'macd' in df.columns and 'macd_signal' in df.columns and 'macd_histogram' in df.columns:
                ax3 = plt.subplot2grid((6, 1), (4, 0), rowspan=1, colspan=1, sharex=ax1)
                ax3.plot(df.index, df['macd'], label='MACD', color='blue', linewidth=1)
                ax3.plot(df.index, df['macd_signal'], label='Signal', color='red', linewidth=1)
                ax3.bar(df.index, df['macd_histogram'], label='Histogram', color='green', alpha=0.5)
                ax3.set_ylabel('MACD', fontsize=12)
                ax3.legend(loc='upper left', fontsize=10)
                ax3.grid(True, alpha=0.3)
            
            # RSI 차트
            if 'rsi' in df.columns:
                ax4 = plt.subplot2grid((6, 1), (5, 0), rowspan=1, colspan=1, sharex=ax1)
                ax4.plot(df.index, df['rsi'], label='RSI', color='purple', linewidth=1)
                ax4.axhline(70, color='red', linestyle='--', alpha=0.5)
                ax4.axhline(30, color='green', linestyle='--', alpha=0.5)
                ax4.set_ylabel('RSI', fontsize=12)
                ax4.set_ylim(0, 100)
                ax4.legend(loc='upper left', fontsize=10)
                ax4.grid(True, alpha=0.3)
            
            # X축 날짜 포맷 설정
            plt.xlabel('날짜', fontsize=12)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"차트를 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"차트 생성 중 오류 발생: {e}")
            plt.close()
    
    def plot_correlation_matrix(self, symbols, timeframe='1d', period=30, save_path=None, show=True):
        """
        여러 암호화폐 간의 상관관계 매트릭스 생성
        
        Args:
            symbols (list): 암호화폐 심볼 리스트
            timeframe (str): 타임프레임
            period (int): 기간 (일)
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            # 각 심볼의 종가 데이터 수집
            prices = {}
            
            for symbol in symbols:
                # 데이터 관리자 초기화
                data_manager = DataManager(exchange_id=self.exchange_id, symbol=symbol)
                
                # 데이터 로드
                df = data_manager.load_ohlcv_data(timeframe=timeframe)
                
                if df is not None and not df.empty:
                    # 최근 데이터만 사용
                    df = df.tail(period)
                    prices[symbol.replace('/', '')] = df['close'].values
            
            if not prices:
                logger.warning("상관관계 분석을 위한 데이터가 없습니다.")
                return
            
            # 데이터프레임 생성
            price_df = pd.DataFrame(prices)
            
            # 상관관계 계산
            corr = price_df.corr()
            
            # 상관관계 매트릭스 시각화
            plt.figure(figsize=(10, 8))
            sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1, linewidths=0.5)
            plt.title(f"암호화폐 간 상관관계 (최근 {period}일)", fontsize=14)
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"상관관계 매트릭스를 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"상관관계 매트릭스 생성 중 오류 발생: {e}")
            plt.close()
    
    def plot_volatility_comparison(self, symbols, timeframe='1d', period=30, save_path=None, show=True):
        """
        여러 암호화폐의 변동성 비교 차트 생성
        
        Args:
            symbols (list): 암호화폐 심볼 리스트
            timeframe (str): 타임프레임
            period (int): 기간 (일)
            save_path (str, optional): 저장 경로
            show (bool): 차트 표시 여부
        """
        try:
            # 각 심볼의 변동성 계산
            volatilities = {}
            
            for symbol in symbols:
                # 데이터 관리자 초기화
                data_manager = DataManager(exchange_id=self.exchange_id, symbol=symbol)
                
                # 데이터 로드
                df = data_manager.load_ohlcv_data(timeframe=timeframe)
                
                if df is not None and not df.empty:
                    # 최근 데이터만 사용
                    df = df.tail(period)
                    
                    # 일일 변동성 계산 (고가-저가)/저가 * 100
                    daily_volatility = ((df['high'] - df['low']) / df['low'] * 100).mean()
                    volatilities[symbol.replace('/', '')] = daily_volatility
            
            if not volatilities:
                logger.warning("변동성 분석을 위한 데이터가 없습니다.")
                return
            
            # 변동성 시각화
            plt.figure(figsize=(12, 6))
            
            # 내림차순 정렬
            sorted_volatilities = {k: v for k, v in sorted(volatilities.items(), key=lambda item: item[1], reverse=True)}
            
            plt.bar(sorted_volatilities.keys(), sorted_volatilities.values(), color='skyblue')
            plt.title(f"암호화폐 변동성 비교 (최근 {period}일)", fontsize=14)
            plt.xlabel('암호화폐', fontsize=12)
            plt.ylabel('평균 일일 변동성 (%)', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            
            # 차트 저장
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"변동성 비교 차트를 {save_path}에 저장했습니다.")
            
            # 차트 표시
            if show:
                plt.show()
            else:
                plt.close()
        
        except Exception as e:
            logger.error(f"변동성 비교 차트 생성 중 오류 발생: {e}")
            plt.close()
    
    def analyze_market_data(self, timeframe='1d', period=100, save_charts=True):
        """
        시장 데이터 종합 분석
        
        Args:
            timeframe (str): 타임프레임
            period (int): 분석 기간
            save_charts (bool): 차트 저장 여부
        
        Returns:
            dict: 분석 결과
        """
        try:
            logger.info(f"{self.symbol}의 시장 데이터 분석을 시작합니다.")
            
            # 데이터 로드
            df = self.data_manager.load_ohlcv_data(timeframe=timeframe)
            
            if df is None or df.empty:
                logger.warning("분석할 데이터가 없습니다.")
                return None
            
            # 최근 데이터만 사용
            df = df.tail(period).copy()
            
            # 기술적 분석 지표 적용
            df = self.apply_indicators(df)
            
            # 분석 결과
            analysis = {}
            
            # 기본 통계
            analysis['basic_stats'] = {
                'start_date': df.index[0].strftime('%Y-%m-%d'),
                'end_date': df.index[-1].strftime('%Y-%m-%d'),
                'days': len(df),
                'current_price': df['close'].iloc[-1],
                'price_change': (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100,
                'avg_volume': df['volume'].mean(),
                'max_price': df['high'].max(),
                'min_price': df['low'].min(),
                'volatility': ((df['high'] - df['low']) / df['low'] * 100).mean()
            }
            
            # 추세 분석
            if 'sma_50' in df.columns and 'sma_200' in df.columns:
                # 골든 크로스/데드 크로스 확인
                golden_cross = (df['sma_50'].iloc[-1] > df['sma_200'].iloc[-1]) and (df['sma_50'].iloc[-2] <= df['sma_200'].iloc[-2])
                dead_cross = (df['sma_50'].iloc[-1] < df['sma_200'].iloc[-1]) and (df['sma_50'].iloc[-2] >= df['sma_200'].iloc[-2])
                
                # 추세 판단
                if df['sma_50'].iloc[-1] > df['sma_200'].iloc[-1]:
                    trend = "상승 추세"
                else:
                    trend = "하락 추세"
                
                analysis['trend'] = {
                    'trend': trend,
                    'golden_cross': golden_cross,
                    'dead_cross': dead_cross,
                    'above_sma_50': df['close'].iloc[-1] > df['sma_50'].iloc[-1],
                    'above_sma_200': df['close'].iloc[-1] > df['sma_200'].iloc[-1]
                }
            
            # 과매수/과매도 분석
            if 'rsi' in df.columns:
                rsi_value = df['rsi'].iloc[-1]
                if rsi_value > 70:
                    rsi_status = "과매수"
                elif rsi_value < 30:
                    rsi_status = "과매도"
                else:
                    rsi_status = "중립"
                
                analysis['overbought_oversold'] = {
                    'rsi': rsi_value,
                    'status': rsi_status
                }
            
            # 지지/저항 레벨 분석
            analysis['support_resistance'] = {
                'recent_high': df['high'].tail(20).max(),
                'recent_low': df['low'].tail(20).min()
            }
            
            # 차트 생성 및 저장
            if save_charts:
                # 파일명 생성
                symbol_filename = self.symbol.replace('/', '_')
                date_str = datetime.now().strftime('%Y%m%d')
                
                # 가격 차트 저장
                price_chart_path = os.path.join(self.charts_dir, f"{symbol_filename}_{timeframe}_{date_str}.png")
                self.plot_price_chart(df, save_path=price_chart_path, show=False)
                
                analysis['charts'] = {
                    'price_chart': price_chart_path
                }
            
            logger.info(f"{self.symbol}의 시장 데이터 분석이 완료되었습니다.")
            return analysis
        
        except Exception as e:
            logger.error(f"시장 데이터 분석 중 오류 발생: {e}")
            return None

# 테스트 코드
if __name__ == "__main__":
    # 데이터 분석기 초기화
    analyzer = DataAnalyzer(exchange_id='binance', symbol='BTC/USDT')
    
    # 데이터 로드
    data_manager = DataManager(exchange_id='binance', symbol='BTC/USDT')
    df = data_manager.load_ohlcv_data(timeframe='1d')
    
    if df is not None and not df.empty:
        # 최근 100일 데이터만 사용
        df = df.tail(100).copy()
        
        # 기술적 분석 지표 적용
        df_with_indicators = analyzer.apply_indicators(df)
        
        # 가격 차트 생성
        analyzer.plot_price_chart(df_with_indicators)
        
        # 시장 데이터 종합 분석
        analysis_result = analyzer.analyze_market_data(timeframe='1d', period=100)
        
        if analysis_result:
            print("\n시장 데이터 분석 결과:")
            for category, data in analysis_result.items():
                if category != 'charts':
                    print(f"\n{category}:")
                    for key, value in data.items():
                        print(f"  {key}: {value}")
    else:
        print("분석할 데이터가 없습니다.")
