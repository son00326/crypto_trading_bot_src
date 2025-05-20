#!/usr/bin/env python3
"""
메인 실행 파일 - 암호화폐 자동 매매 봇

이 파일은 암호화폐 자동 매매 봇의 메인 실행 파일입니다.
다양한 기능을 통합하여 사용자가 쉽게 봇을 실행할 수 있도록 합니다.
"""

import os
import sys
import argparse
import logging
import json
import time
import signal
import atexit
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# 프로젝트 모듈 임포트
from src.config import (
    DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME,
    DATA_DIR, RISK_MANAGEMENT
)
from src.exchange_api import ExchangeAPI
from src.data_manager import DataManager
from src.data_collector import DataCollector
from src.data_analyzer import DataAnalyzer
from src.indicators import (
    simple_moving_average, exponential_moving_average, moving_average_convergence_divergence,
    relative_strength_index, bollinger_bands, stochastic_oscillator
)
from src.strategies import (
    MovingAverageCrossover, RSIStrategy, MACDStrategy,
    BollingerBandsStrategy, CombinedStrategy
)
from src.trading_algorithm import TradingAlgorithm
from src.backtesting import Backtester
from src.risk_manager import RiskManager

# 오류 처리 및 모니터링 모듈 임포트
from src.error_handlers import ErrorAnalyzer, RateLimitManager, advanced_network_error_handler
from src.system_health import SystemHealthMonitor
from src.network_monitor import NetworkMonitor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('crypto_bot')

# .env 파일 로드
load_dotenv()

# 전역 오류 처리 및 모니터링 인스턴스
error_analyzer = ErrorAnalyzer()
rate_limit_manager = RateLimitManager()
health_monitor = SystemHealthMonitor(check_interval=60)
network_monitor = NetworkMonitor(check_interval=120)

def setup_directories():
    """필요한 디렉토리 생성"""
    directories = [
        os.path.join(DATA_DIR, 'ohlcv'),
        os.path.join(DATA_DIR, 'charts'),
        os.path.join(DATA_DIR, 'backtest_results'),
        os.path.join(DATA_DIR, 'risk_logs')
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"디렉토리 생성: {directory}")

def parse_arguments():
    """명령줄 인수 파싱"""
    parser = argparse.ArgumentParser(description='암호화폐 자동 매매 봇')
    
    # 기본 설정
    parser.add_argument('--exchange', type=str, default=DEFAULT_EXCHANGE,
                        help=f'거래소 ID (기본값: {DEFAULT_EXCHANGE})')
    parser.add_argument('--symbol', type=str, default=DEFAULT_SYMBOL,
                        help=f'거래 심볼 (기본값: {DEFAULT_SYMBOL})')
    parser.add_argument('--timeframe', type=str, default=DEFAULT_TIMEFRAME,
                        help=f'타임프레임 (기본값: {DEFAULT_TIMEFRAME})')
    
    # 모드 선택
    parser.add_argument('--mode', type=str, required=True, 
                        choices=['collect', 'analyze', 'backtest', 'trade', 'optimize', 'gui', 'web', 'both'],
                        help='실행 모드 (collect: 데이터 수집, analyze: 데이터 분석, backtest: 백테스팅, trade: 거래, optimize: 최적화, gui: GUI 인터페이스, web: 웹 인터페이스, both: GUI 및 웹 동시 실행)')
    
    # 데이터 수집 옵션
    parser.add_argument('--start-date', type=str, 
                        help='시작 날짜 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, 
                        help='종료 날짜 (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=1000,
                        help='가져올 데이터 개수 (기본값: 1000)')
    
    # 전략 옵션
    parser.add_argument('--strategy', type=str, 
                        choices=['ma_crossover', 'rsi', 'macd', 'bollinger', 'combined'],
                        help='사용할 거래 전략')
    
    # 백테스팅 옵션
    parser.add_argument('--initial-balance', type=float, default=10000,
                        help='초기 자본금 (기본값: 10000)')
    parser.add_argument('--commission', type=float, default=0.001,
                        help='거래 수수료 (기본값: 0.001)')
    
    # 거래 옵션
    parser.add_argument('--test-mode', action='store_true',
                        help='테스트 모드 (실제 거래 없음)')
    parser.add_argument('--interval', type=int, default=60,
                        help='거래 사이클 간격 (초) (기본값: 60)')
    
    # 위험 관리 옵션
    parser.add_argument('--stop-loss', type=float,
                        help='손절매 비율 (예: 0.05 = 5%)')
    parser.add_argument('--take-profit', type=float,
                        help='이익실현 비율 (예: 0.1 = 10%)')
    parser.add_argument('--trailing-stop', action='store_true',
                        help='트레일링 스탑 사용')
    
    return parser.parse_args()

def create_strategy(strategy_name, **kwargs):
    """전략 객체 생성"""
    if strategy_name == 'ma_crossover':
        short_period = kwargs.get('short_period', 9)
        long_period = kwargs.get('long_period', 26)
        ma_type = kwargs.get('ma_type', 'ema')
        return MovingAverageCrossover(short_period=short_period, long_period=long_period, ma_type=ma_type)
    
    elif strategy_name == 'rsi':
        period = kwargs.get('period', 14)
        overbought = kwargs.get('overbought', 70)
        oversold = kwargs.get('oversold', 30)
        return RSIStrategy(period=period, overbought=overbought, oversold=oversold)
    
    elif strategy_name == 'macd':
        fast_period = kwargs.get('fast_period', 12)
        slow_period = kwargs.get('slow_period', 26)
        signal_period = kwargs.get('signal_period', 9)
        return MACDStrategy(fast_period=fast_period, slow_period=slow_period, signal_period=signal_period)
    
    elif strategy_name == 'bollinger':
        period = kwargs.get('period', 20)
        std_dev = kwargs.get('std_dev', 2)
        return BollingerBandsStrategy(period=period, std_dev=std_dev)
    
    elif strategy_name == 'combined':
        return CombinedStrategy([
            MovingAverageCrossover(short_period=9, long_period=26, ma_type='ema'),
            RSIStrategy(period=14, overbought=70, oversold=30)
        ])
    
    else:
        logger.error(f"알 수 없는 전략: {strategy_name}")
        return None

def collect_data(args):
    """데이터 수집 모드"""
    logger.info(f"데이터 수집 모드 시작: {args.exchange} {args.symbol} {args.timeframe}")
    
    collector = DataCollector(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe
    )
    
    if args.start_date and args.end_date:
        # 과거 데이터 수집
        df = collector.fetch_historical_data(
            start_date=args.start_date,
            end_date=args.end_date
        )
        logger.info(f"과거 데이터 수집 완료: {len(df)} 개의 데이터")
    else:
        # 최근 데이터 수집
        df = collector.fetch_recent_data(limit=args.limit)
        logger.info(f"최근 데이터 수집 완료: {len(df)} 개의 데이터")
    
    # 데이터 저장
    file_path = collector.save_data(df)
    logger.info(f"데이터 저장 완료: {file_path}")
    
    return df

def analyze_data(args):
    """데이터 분석 모드"""
    logger.info(f"데이터 분석 모드 시작: {args.exchange} {args.symbol} {args.timeframe}")
    
    # 데이터 수집기 초기화
    collector = DataCollector(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe
    )
    
    # 데이터 로드
    if args.start_date and args.end_date:
        df = collector.load_data(start_date=args.start_date, end_date=args.end_date)
    else:
        df = collector.load_data(limit=args.limit)
    
    if df is None or len(df) == 0:
        logger.error("분석할 데이터가 없습니다. 먼저 데이터를 수집하세요.")
        return
    
    logger.info(f"데이터 로드 완료: {len(df)} 개의 데이터")
    
    # 데이터 분석기 초기화
    analyzer = DataAnalyzer(
        exchange_id=args.exchange,
        symbol=args.symbol
    )
    
    # 기술적 분석 지표 적용
    df_with_indicators = analyzer.apply_indicators(df)
    
    # 가격 차트 생성
    chart_path = analyzer.plot_price_chart(df_with_indicators)
    logger.info(f"가격 차트 생성 완료: {chart_path}")
    
    # 시장 데이터 종합 분석
    analysis_result = analyzer.analyze_market_data(df=df_with_indicators)
    logger.info(f"시장 분석 결과: {analysis_result}")
    
    # 분석 결과 저장
    result_path = os.path.join(DATA_DIR, 'analysis_result.json')
    with open(result_path, 'w') as f:
        json.dump(analysis_result, f, indent=4)
    
    logger.info(f"분석 결과 저장 완료: {result_path}")
    
    return df_with_indicators, analysis_result

def run_backtest(args):
    """백테스팅 모드"""
    logger.info(f"백테스팅 모드 시작: {args.exchange} {args.symbol} {args.timeframe}")
    
    if not args.strategy:
        logger.error("백테스팅을 위한 전략을 지정해야 합니다.")
        return
    
    if not args.start_date or not args.end_date:
        logger.error("백테스팅을 위한 시작 날짜와 종료 날짜를 지정해야 합니다.")
        return
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe
    )
    
    # 전략 생성
    strategy = create_strategy(args.strategy)
    if not strategy:
        return
    
    # 위험 관리 설정
    risk_config = RISK_MANAGEMENT.copy()
    if args.stop_loss:
        risk_config['stop_loss_pct'] = args.stop_loss
    if args.take_profit:
        risk_config['take_profit_pct'] = args.take_profit
    
    # 백테스트 실행
    result = backtester.run_backtest(
        strategy=strategy,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_balance=args.initial_balance,
        commission=args.commission,
        risk_config=risk_config,
        use_trailing_stop=args.trailing_stop
    )
    
    # 결과 시각화
    result.plot_equity_curve()
    result.plot_drawdown_chart()
    result.plot_monthly_returns()
    
    # 결과 저장
    result_path = result.save_results()
    logger.info(f"백테스트 결과 저장 완료: {result_path}")
    
    # 결과 요약 출력
    summary = result.get_summary()
    logger.info("백테스트 결과 요약:")
    for key, value in summary.items():
        logger.info(f"  {key}: {value}")
    
    return result

def optimize_strategy(args):
    """전략 최적화 모드"""
    logger.info(f"전략 최적화 모드 시작: {args.exchange} {args.symbol} {args.timeframe}")
    
    if not args.strategy:
        logger.error("최적화할 전략을 지정해야 합니다.")
        return
    
    if not args.start_date or not args.end_date:
        logger.error("최적화를 위한 시작 날짜와 종료 날짜를 지정해야 합니다.")
        return
    
    # 백테스터 초기화
    backtester = Backtester(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe
    )
    
    # 전략별 파라미터 그리드 정의
    param_grids = {
        'ma_crossover': {
            'short_period': [5, 8, 9, 12, 15],
            'long_period': [20, 26, 30, 40, 50],
            'ma_type': ['sma', 'ema']
        },
        'rsi': {
            'period': [7, 10, 14, 21],
            'overbought': [65, 70, 75, 80],
            'oversold': [20, 25, 30, 35]
        },
        'macd': {
            'fast_period': [8, 10, 12, 15],
            'slow_period': [20, 26, 30, 35],
            'signal_period': [7, 9, 12]
        },
        'bollinger': {
            'period': [10, 15, 20, 25],
            'std_dev': [1.5, 2.0, 2.5, 3.0]
        }
    }
    
    # 전략 클래스 매핑
    strategy_classes = {
        'ma_crossover': MovingAverageCrossover,
        'rsi': RSIStrategy,
        'macd': MACDStrategy,
        'bollinger': BollingerBandsStrategy
    }
    
    # 최적화 실행
    if args.strategy in param_grids and args.strategy in strategy_classes:
        param_grid = param_grids[args.strategy]
        strategy_class = strategy_classes[args.strategy]
        
        best_params, best_result = backtester.optimize_strategy(
            strategy_class=strategy_class,
            param_grid=param_grid,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission
        )
        
        logger.info(f"최적화 완료. 최적 파라미터: {best_params}")
        
        # 최적 파라미터로 백테스트 실행
        strategy = create_strategy(args.strategy, **best_params)
        result = backtester.run_backtest(
            strategy=strategy,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.initial_balance,
            commission=args.commission
        )
        
        # 결과 시각화
        result.plot_equity_curve()
        result.plot_drawdown_chart()
        result.plot_monthly_returns()
        
        # 결과 저장
        result_path = result.save_results(suffix='_optimized')
        logger.info(f"최적화된 백테스트 결과 저장 완료: {result_path}")
        
        # 최적 파라미터 저장
        params_path = os.path.join(DATA_DIR, f'optimal_params_{args.strategy}.json')
        with open(params_path, 'w') as f:
            json.dump(best_params, f, indent=4)
        
        logger.info(f"최적 파라미터 저장 완료: {params_path}")
        
        return best_params, result
    else:
        logger.error(f"최적화를 지원하지 않는 전략: {args.strategy}")
        return None, None

def run_trading(args):
    """거래 모드"""
    logger.info(f"거래 모드 시작: {args.exchange} {args.symbol} {args.timeframe}")
    
    if not args.strategy:
        logger.error("거래를 위한 전략을 지정해야 합니다.")
        return
    
    # 전략 생성
    strategy = create_strategy(args.strategy)
    if not strategy:
        return
    
    # 위험 관리 설정
    risk_config = RISK_MANAGEMENT.copy()
    if args.stop_loss:
        risk_config['stop_loss_pct'] = args.stop_loss
    if args.take_profit:
        risk_config['take_profit_pct'] = args.take_profit
    
    # 거래 알고리즘 초기화
    algorithm = TradingAlgorithm(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe,
        strategy=strategy,
        initial_balance=args.initial_balance,
        test_mode=args.test_mode,
        risk_config=risk_config,
        use_trailing_stop=args.trailing_stop
    )
    
    # 거래 시작
    try:
        logger.info(f"자동 거래 시작: 간격={args.interval}초, 테스트 모드={args.test_mode}")
        
        # 별도 스레드에서 자동 거래 시작
        trading_thread = algorithm.start_trading_thread(interval=args.interval)
        
        # 메인 스레드에서는 주기적으로 상태 출력
        while True:
            time.sleep(60)  # 1분마다 상태 확인
            
            # 포트폴리오 요약 정보 확인
            summary = algorithm.get_portfolio_summary()
            logger.info("포트폴리오 상태:")
            for key, value in summary.items():
                logger.info(f"  {key}: {value}")
    
    except KeyboardInterrupt:
        logger.info("사용자에 의해 거래가 중지되었습니다.")
        algorithm.stop_trading()
    
    except Exception as e:
        logger.error(f"거래 중 오류 발생: {e}")
        algorithm.stop_trading()
    
    finally:
        # 최종 포트폴리오 상태 저장
        summary = algorithm.get_portfolio_summary()
        summary_path = os.path.join(DATA_DIR, f'trading_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=4)
        
        logger.info(f"거래 요약 정보 저장 완료: {summary_path}")

def initialize_monitoring():
    """모니터링 및 오류 처리 시스템 초기화"""
    global health_monitor, network_monitor
    
    logger.info("시스템 모니터링 서비스 초기화 중..")
    
    # 시스템 상태 모니터링 시작
    health_monitor.register_component(
        "database", check_database_connection,
        max_consecutive_failures=3
    )
    
    # 거래소 연결 상태 확인 및 복구 등록
    for exchange_id in ['binance', 'bybit', 'ftx']:
        health_monitor.register_component(
            f"exchange_{exchange_id}",
            lambda ex_id=exchange_id: check_exchange_api_connection(ex_id),
            lambda ex_id=exchange_id: recover_exchange_api_connection(ex_id),
            max_consecutive_failures=2
        )
    
    # 데이터 수집기 확인
    health_monitor.register_component(
        "data_collector", check_data_collector,
        max_consecutive_failures=3
    )
    
    # 모니터링 시작
    health_monitor.start_monitoring()
    network_monitor.start_monitoring()
    
    logger.info("시스템 모니터링 서비스 시작됨")


def shutdown_monitoring():
    """모니터링 및 오류 처리 시스템 정리"""
    logger.info("시스템 모니터링 서비스 종료 중..")
    
    # 모니터링 서비스 중지
    if health_monitor.running:
        health_monitor.stop_monitoring()
    
    if network_monitor.running:
        network_monitor.stop_monitoring()
    
    # 오류 정보 저장
    error_analyzer.save_error_logs()
    
    logger.info("시스템 모니터링 서비스 종료됨")


def setup_signal_handlers():
    """시스템 종료 신호 핸들러 설정"""
    def signal_handler(sig, frame):
        logger.info(f"시스템 종료 신호 수신: {sig}")
        shutdown_monitoring()
        sys.exit(0)
    
    # 종료 시 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 터미널 종료
    
    # 프로그램 종료 시 실행될 함수 등록
    atexit.register(shutdown_monitoring)


# 시스템 상태 확인 함수들
def check_database_connection():
    """데이터베이스 연결 상태 확인"""
    try:
        # 간단한 테스트 쿼리 수행
        # 실제 DB 사용 시 이 부분을 DB 연결 확인 코드로 대체
        return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 확인 실패: {e}")
        return False


def check_exchange_api_connection(exchange_id):
    """거래소 API 연결 확인"""
    try:
        api = ExchangeAPI(exchange_id=exchange_id)
        # 간단한 API 요청으로 연결 확인
        api.fetch_ticker()
        return True
    except Exception as e:
        logger.error(f"{exchange_id} 연결 확인 실패: {e}")
        return False


def recover_exchange_api_connection(exchange_id):
    """거래소 API 연결 복구 시도"""
    try:
        logger.info(f"{exchange_id} 연결 복구 시도 중..")
        api = ExchangeAPI(exchange_id=exchange_id, refresh=True)
        return api.fetch_ticker() is not None
    except Exception as e:
        logger.error(f"{exchange_id} 연결 복구 실패: {e}")
        return False


def check_data_collector():
    """데이터 수집기 상태 확인"""
    try:
        collector = DataCollector()
        # 간단한 데이터 요청으로 상태 확인
        data = collector.fetch_recent_data(limit=1)
        return data is not None and len(data) > 0
    except Exception as e:
        logger.error(f"데이터 수집기 확인 실패: {e}")
        return False


def main():
    """메인 함수"""
    # 디렉토리 설정
    setup_directories()
    
    # 모니터링 및 종료 핸들러 설정
    setup_signal_handlers()
    initialize_monitoring()
    
    # 명령줄 인수 파싱
    args = parse_arguments()
    
    # 모드에 따라 실행
    if args.mode == 'collect':
        collect_data(args)
    
    elif args.mode == 'analyze':
        analyze_data(args)
    
    elif args.mode == 'backtest':
        run_backtest(args)
    
    elif args.mode == 'optimize':
        optimize_strategy(args)
    
    elif args.mode == 'trade':
        run_trading(args)
    
    elif args.mode == 'gui':
        try:
            logger.info("GUI 모드 시작")
            from gui.crypto_trading_bot_gui_complete import main as run_gui
            run_gui()
        except ImportError as e:
            logger.error(f"GUI 모듈 로드 실패: {e}")
            logger.error("PyQt5 설치 여부를 확인하세요: pip install PyQt5")
    
    elif args.mode == 'web':
        try:
            logger.info("웹 모드 시작")
            # 웹 API 서버 로드 및 실행
            from web_app.bot_api_server import TradingBotAPIServer
            # 헤드리스 모드로 웹 API 서버 실행
            server = TradingBotAPIServer(host='0.0.0.0', port=8080, headless=True)
            server.run()
        except ImportError as e:
            logger.error(f"웹 모듈 로드 실패: {e}")
            logger.error("Flask 설치 여부를 확인하세요: pip install flask flask-cors")
    
    elif args.mode == 'both':
        try:
            logger.info("GUI 및 웹 동시 실행 모드 시작")
            import threading
            from web_app.bot_api_server import TradingBotAPIServer
            from gui.crypto_trading_bot_gui_complete import main as run_gui
            
            # 웹 서버를 별도 스레드로 실행
            server = TradingBotAPIServer(host='0.0.0.0', port=8080, headless=False)
            web_thread = threading.Thread(target=server.run)
            web_thread.daemon = True
            web_thread.start()
            logger.info("웹 서버가 배경에서 실행 중...") 
            
            # 메인 스레드에서 GUI 실행
            logger.info("GUI 로드 중...")
            run_gui()
        except ImportError as e:
            logger.error(f"GUI 혹은 웹 모듈 로드 실패: {e}")
            logger.error("PyQt5 및 Flask 설치 여부를 확인하세요.")
    
    else:
        logger.error(f"알 수 없는 모드: {args.mode}")

if __name__ == "__main__":
    main()
