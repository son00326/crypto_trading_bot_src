"""
설정 파일 - 암호화폐 자동매매 봇 설정

이 파일은 API 키, 거래 설정, 전략 파라미터 등 봇 운영에 필요한 설정을 관리합니다.
실제 API 키는 .env 파일에 저장하고 이 파일에서는 환경 변수로 불러옵니다.
"""

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 거래소 API 설정
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
UPBIT_API_KEY = os.getenv('UPBIT_API_KEY', '')
UPBIT_API_SECRET = os.getenv('UPBIT_API_SECRET', '')
BITHUMB_API_KEY = os.getenv('BITHUMB_API_KEY', '')
BITHUMB_API_SECRET = os.getenv('BITHUMB_API_SECRET', '')

# 거래 설정
DEFAULT_EXCHANGE = 'binance'  # 기본 거래소 (binance, upbit, bithumb)
DEFAULT_SYMBOL = 'BTC/USDT'   # 기본 거래 심볼
DEFAULT_TIMEFRAME = '1h'      # 기본 타임프레임 (1m, 5m, 15m, 1h, 4h, 1d)

# 전략 파라미터
STRATEGY_PARAMS = {
    'moving_average': {
        'short_period': 9,    # 단기 이동평균선 기간
        'long_period': 26,    # 장기 이동평균선 기간
    },
    'rsi': {
        'period': 14,         # RSI 계산 기간
        'overbought': 70,     # 과매수 기준
        'oversold': 30,       # 과매도 기준
    },
    'macd': {
        'fast_period': 12,    # 빠른 EMA 기간
        'slow_period': 26,    # 느린 EMA 기간
        'signal_period': 9,   # 시그널 기간
    },
    'bollinger_bands': {
        'period': 20,         # 볼린저 밴드 기간
        'std_dev': 2,         # 표준편차 배수
    }
}

# 위험 관리 설정
RISK_MANAGEMENT = {
    'max_position_size': 0.1,  # 계좌 자산의 최대 포지션 크기 (10%)
    'stop_loss_pct': 0.02,     # 손절매 비율 (2%)
    'take_profit_pct': 0.05,   # 이익실현 비율 (5%)
    'max_daily_trades': 5,     # 일일 최대 거래 횟수
}

# 백테스팅 설정
BACKTEST = {
    'start_date': '2024-01-01',  # 백테스팅 시작일
    'end_date': '2024-04-01',    # 백테스팅 종료일
    'initial_balance': 10000,    # 초기 자산 (USDT)
    'commission': 0.001,         # 수수료 (0.1%)
}

# 데이터 저장 설정
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# 디렉토리가 없으면 생성
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
