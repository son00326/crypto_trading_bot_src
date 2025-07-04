#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crypto Trading Bot API Server
Binance API를 통한 암호화폐 트레이딩 봇 구현
Author: Yong Son
"""

# 프로젝트 루트 디렉토리를 시스템 경로에 추가하여 어디서든 동일한 임포트 구조 사용
import os
import sys
import threading

# 프로젝트 루트 디렉토리 설정 및 환경 구성
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 시스템 경로에 프로젝트 루트 추가 (모듈 임포트를 위해)
sys.path.append(project_root)

# 작업 디렉토리 변경 (상대 경로 문제 해결을 위해)
os.chdir(project_root)

import json
import time
import logging
import asyncio
from threading import Thread
from flask import Flask
from flask_socketio import SocketIO, emit
import random
import signal
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import configparser
import traceback
import datetime
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse

# 유틸리티 모듈 가져오기
from utils.config import validate_api_key, get_validated_api_credentials
import utils.api as api
from utils.api import get_positions, get_positions_with_objects, get_formatted_balances, get_spot_balance, get_future_balance, get_ticker, get_orderbook, set_stop_loss_take_profit
from PyQt5.QtWidgets import QApplication
from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, flash, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# .env 파일 로드
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# 콘솔에 정보 출력
logging.info(f"Working directory set to: {os.getcwd()}")
logging.info(f"Loading environment variables from: {env_path}")

# 사용자 모델 임포트
from web_app.models import User
from src.db_manager import DatabaseManager
from src.exchange_api import ExchangeAPI
from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crypto_bot_web')

class BotAPIServer:
    """GUI 코드를 웹 API로 노출하는 서버 클래스"""
    
    def __init__(self, host='0.0.0.0', port=8080, headless=True):
        """API 서버 초기화
        
        Args:
            host (str): 서버 호스트 주소
            port (int): 서버 포트
            headless (bool): GUI를 화면에 표시하지 않는 모드
        """
        # Flask 앱 초기화
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        
        self.flask_app = Flask(__name__,
                         template_folder=template_dir,
                         static_folder=static_dir)
        
        # 안전한 SECRET_KEY 설정
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            # 랜덤 SECRET_KEY 생성
            import secrets
            secret_key = secrets.token_hex(32)  # 256비트 랜덤 값
            logger.warning('SECRET_KEY 환경변수가 설정되지 않았습니다. 임시 랜덤 키를 생성했습니다.')
            logger.warning('서버 재시작 시 세션이 모두 초기화됩니다. 프로덕션 환경에서는 환경변수로 SECRET_KEY를 설정하세요.')
            
        self.flask_app.secret_key = secret_key
        
        # CORS 설정
        CORS(self.flask_app)
        
        # 로그인 관리자 초기화
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.flask_app)
        self.login_manager.login_view = 'login'
        self.login_manager.login_message = '이 페이지에 액세스하려면 로그인이 필요합니다.'
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
        # 사용자 테이블 생성 확인
        self.db.create_users_table()
        
        # 기본 관리자 계정 생성 (없는 경우)
        admin_user = self.db.get_user_by_username('admin')
        if not admin_user:
            # 환경변수에서 관리자 암호 가져오기, 없으면 강력한 무작위 비밀번호 생성
            admin_password = os.getenv('ADMIN_PASSWORD')
            if not admin_password:
                # 강력한 무작위 비밀번호 생성 (16자리)
                import random
                import string
                chars = string.ascii_letters + string.digits + '!@#$%^&*()'
                admin_password = ''.join(random.choice(chars) for _ in range(16))
                logger.warning(f'ADMIN_PASSWORD 환경변수가 설정되지 않았습니다. 생성된 관리자 비밀번호: {admin_password}')
                logger.warning('이 비밀번호를 안전한 곳에 저장하고 환경변수를 설정하세요!')
            
            self.db.create_user(
                username='admin',
                password_hash=generate_password_hash(admin_password),
                is_admin=True
            )
            logger.info('기본 관리자 계정이 생성되었습니다.')
        
        try:
            # PyQt5 애플리케이션 객체 초기화 (실행 중이 아니면 생성)
            self.qt_app = QApplication.instance()
            if self.qt_app is None:
                self.qt_app = QApplication(sys.argv)
            
            # 이전 봇 상태 정보를 데이터베이스에서 로드
            saved_state = self.db.load_bot_state()
            
            # 헤드리스 모드로 GUI 초기화
            from gui.crypto_trading_bot_gui_complete import main as run_gui
            self.bot_gui = run_gui(headless=headless)
            
            # 봇 관련 변수 초기화
            self.bot = None
            self.trading_thread = None
            self.bot_status = {
                'is_running': False,
                'strategy': None,
                'symbol': None,
                'timeframe': None,
                'market_type': 'spot',
                'leverage': 1,
                'test_mode': False,
                'started_at': None,
                'last_update': None
            }
            
            # 서버 설정  
            self.host = host
            self.port = port
            
            # 이전 봇 상태가 있으면 복원
            if saved_state and hasattr(self.bot_gui, 'exchange_id'):
                # 테스트를 위해 로그에만 출력
                logger.info(f"이전 봇 상태 값 발견: {saved_state['exchange_id']}, {saved_state['symbol']}")
                
                # 이미 상태가 이기번에 복원되었을 가능성이 높지만, 추가 복원 작업을 진행할 수 있음
                if 'is_running' in saved_state and saved_state['is_running'] and not self.bot_gui.bot_running:
                    logger.info("이전에 실행 중이었던 봇 상태를 복원합니다.")
                    # 특정 조건에서 봇 자동 재시작을 원하는 경우 사용
                    # self.start_bot_with_saved_settings(saved_state)
            
            logger.info(f"API 서버가 초기화되었습니다. 봇 GUI를 헤드리스 모드로 실행 중...")
        except Exception as e:
            logger.error(f"GUI 초기화 중 오류: {str(e)}")
            raise
        
        # 거래소 API 인스턴스 초기화 (데이터 동기화용)
        self.exchange_api = None
        
        try:
            # saved_state가 있으면 그 값을 사용, 없으면 기본값 사용
            if saved_state:
                exchange_id = saved_state.get('exchange_id', DEFAULT_EXCHANGE)
                symbol = saved_state.get('symbol', DEFAULT_SYMBOL)
                timeframe = saved_state.get('timeframe', DEFAULT_TIMEFRAME)
                market_type = saved_state.get('market_type', 'futures')  # 기본값을 futures로 설정
                leverage = saved_state.get('leverage', 1)
                strategy_params = saved_state.get('strategy_params', saved_state.get('parameters', {}))  # parameters 필드에서 strategy_params 로드하도록 수정
            else:
                # saved_state가 없으면 기본값 사용
                exchange_id = DEFAULT_EXCHANGE
                symbol = DEFAULT_SYMBOL
                timeframe = DEFAULT_TIMEFRAME
                market_type = 'futures'
                leverage = 1
                strategy_params = {}  # 빈 dict로 초기화
                logger.info("저장된 봇 상태가 없습니다. 기본값으로 초기화합니다.")
            
            # GUI에서 저장한 API 키 불러오기
            home_dir = os.path.expanduser("~")
            config_file = os.path.join(home_dir, ".crypto_trading_bot_src", "config.env")
            
            if os.path.exists(config_file):
                # 저장된 API 키 파일이 있으면 환경 변수에 로드
                with open(config_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value
                logger.info(f"GUI에서 저장한 API 키 설정을 로드했습니다.")
            
            # 환경 변수에서 API 키 확인 - 새로운 유틸리티 함수 사용
            api_result = get_validated_api_credentials()
            
            if api_result['success']:
                api_key = api_result['api_key']
                api_secret = api_result['api_secret']
                logger.info(f"API 키가 설정되어 있습니다: {api_key[:5]}...")
            else:
                logger.warning(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}")
            
            # 심볼 형식 확인 및 수정 (BTCUSDT:USDT -> BTCUSDT)
            symbol_to_use = symbol
            if ':' in symbol_to_use:
                clean_symbol = symbol_to_use.split(':')[0]
                logger.info(f"심볼 형식 수정: {symbol_to_use} → {clean_symbol}")
                symbol_to_use = clean_symbol
                
            self.exchange_api = ExchangeAPI(
                exchange_id=exchange_id,
                symbol=symbol_to_use,  # 수정된 심볼 사용
                timeframe=timeframe,  # timeframe 매개변수 추가
                market_type=market_type,
                leverage=leverage
            )
            logger.info(f"거래소 API 초기화 완료: {exchange_id}, {symbol}, {market_type}")
            
            # 생성된 exchange_api 객체를 GUI 인스턴스에도 전달
            if hasattr(self.bot_gui, '__dict__'):
                self.bot_gui.exchange_api = self.exchange_api
                self.bot_gui.exchange_id = exchange_id  # exchange_id도 설정
                logger.info("GUI 인스턴스에 거래소 API 객체 전달 완료")
        except Exception as e:
            logger.error(f"거래소 API 초기화 오류: {str(e)}")
            logger.exception("상세 오류 정보:")
        
        # 데이터 동기화 스레드 시작
        self.sync_thread = None
        self.sync_running = False
        
        # 차등화된 동기화 주기 설정 (AWS 환경 최적화)
        self.price_sync_interval = 3     # 가격 데이터 (초)
        self.order_sync_interval = 5     # 주문 상태 (초)
        self.position_sync_interval = 15  # 포지션 정보 (초)
        self.balance_sync_interval = 30   # 계좌 잔액 (초)
        
        self.start_data_sync()  # 차등화된 주기로 동기화
        
        # API 엔드포인트 등록
        self.register_endpoints()
        
        logger.info(f"API 서버 초기화 완료. 호스트: {host}, 포트: {port}, 헤드리스 모드: {headless}")
    
    def start_bot_with_saved_settings(self, saved_state):
        """저장된 설정으로 봇 자동 재시작"""
        try:
            # 저장된 설정으로 봇 시작
            strategy = saved_state.get('strategy')
            symbol = saved_state.get('symbol')
            timeframe = saved_state.get('timeframe')
            
            # 저장된 전략 파라미터 가져오기
            strategy_params = saved_state.get('strategy_params', saved_state.get('parameters', {}))  # parameters 필드에서 strategy_params 로드하도록 수정
            if isinstance(strategy_params, str):
                # JSON 문자열인 경우 파싱
                import json
                try:
                    strategy_params = json.loads(strategy_params)
                except:
                    strategy_params = {}
            
            # 실제 봇 시작 API 호출 - 전략 파라미터 포함
            result = self.bot_gui.start_bot_api(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                strategy_params=strategy_params  # 전략 파라미터 전달
            )
            
            # 저장된 포지션 정보와 거래 정보 복원
            if result.get('success') and self.bot_gui.algo:
                # 포지션 정보 복원
                if 'positions' in saved_state and saved_state['positions']:
                    logger.info(f"저장된 포지션 정보 복원: {len(saved_state['positions'])}개")
                    # 포지션 정보는 참조용으로만 사용 (실제 포지션은 거래소에서 조회)
                
                # 거래 정보 복원 (진입가, 목표가, 손절가 등)
                if 'current_trade_info' in saved_state and saved_state['current_trade_info']:
                    logger.info(f"저장된 거래 정보 복원: {saved_state['current_trade_info']}")
                    if hasattr(self.bot_gui.algo, 'current_trade_info'):
                        self.bot_gui.algo.current_trade_info = saved_state['current_trade_info']
                        logger.info("거래 정보 복원 완료")
            
            logger.info(f"저장된 설정으로 봇 재시작 결과: {result}")
            return result
        except Exception as e:
            logger.error(f"저장된 설정으로 봇 재시작 중 오류: {e}")
            return {
                'success': False,
                'message': f"저장된 설정으로 봇 재시작 중 오류: {str(e)}"
            }
    
    def start_bot_with_settings(self, settings):
        """저장된 설정으로 봇 시작 (자동 재시작용)"""
        try:
            logger.info("저장된 설정으로 봇을 시작합니다...")
            
            # GUI 설정 업데이트
            self.bot_gui.exchange_id = settings.get('exchange_id', 'binance')
            self.bot_gui.symbol = settings.get('symbol', 'BTC/USDT')
            self.bot_gui.timeframe = settings.get('timeframe', '1h')
            self.bot_gui.strategy = settings.get('strategy', 'ma_crossover')
            self.bot_gui.market_type = settings.get('market_type', 'futures')
            self.bot_gui.leverage = settings.get('leverage', 1)
            
            # 테스트 모드 설정 명시적 복원 - 기본값은 False로 설정
            self.bot_gui.test_mode = settings.get('test_mode', False)
            logger.info(f"테스트 모드 설정 복원: {self.bot_gui.test_mode}")
            
            # 전략 파라미터 설정
            strategy_params = {}
            if 'strategy_params' in settings:
                strategy_params = settings['strategy_params']
                self.bot_gui.strategy_params = strategy_params
                logger.info(f"전략 파라미터 복원: {strategy_params}")
            
            # 위험 관리 설정 복원 - parameters에서도 확인
            parameters = settings.get('parameters', {})
            
            # 위험 관리 설정을 명시적으로 복원
            risk_management = {}
            
            # strategy_params에서 위험 관리 설정 추출
            if 'stop_loss_pct' in strategy_params:
                risk_management['stop_loss_pct'] = strategy_params.get('stop_loss_pct')
            if 'take_profit_pct' in strategy_params:
                risk_management['take_profit_pct'] = strategy_params.get('take_profit_pct')
            if 'max_position_size' in strategy_params:
                risk_management['max_position_size'] = strategy_params.get('max_position_size')
                
            # parameters에서도 확인 (legacy 지원)
            if not risk_management and isinstance(parameters, dict):
                if 'stop_loss_pct' in parameters:
                    risk_management['stop_loss_pct'] = parameters.get('stop_loss_pct')
                if 'take_profit_pct' in parameters:
                    risk_management['take_profit_pct'] = parameters.get('take_profit_pct')
                if 'max_position_size' in parameters:
                    risk_management['max_position_size'] = parameters.get('max_position_size')
            
            if risk_management:
                logger.info(f"위험 관리 설정 복원: {risk_management}")
                
                # GUI에 위험 관리 설정 적용
                if hasattr(self.bot_gui, 'stop_loss_spin') and 'stop_loss_pct' in risk_management:
                    self.bot_gui.stop_loss_spin.setValue(float(risk_management['stop_loss_pct']))
                
                if hasattr(self.bot_gui, 'take_profit_spin') and 'take_profit_pct' in risk_management:
                    self.bot_gui.take_profit_spin.setValue(float(risk_management['take_profit_pct']))
                
                if hasattr(self.bot_gui, 'max_position_spin') and 'max_position_size' in risk_management:
                    self.bot_gui.max_position_spin.setValue(float(risk_management['max_position_size']))
                    
                # 전략 파라미터에 위험 관리 설정 병합
                if not 'strategy_params' in settings:
                    self.bot_gui.strategy_params = {}
                self.bot_gui.strategy_params.update(risk_management)
            
            # 추가 설정
            if hasattr(self.bot_gui, 'stop_loss'):
                self.bot_gui.stop_loss = settings.get('stop_loss', 2.0)
                self.bot_gui.take_profit = settings.get('take_profit', 5.0)
                self.bot_gui.max_position = settings.get('max_position', 1000)
                self.bot_gui.auto_sl_tp = settings.get('auto_sl_tp', True)
                self.bot_gui.partial_tp = settings.get('partial_tp', False)
            
            # 봇 시작
            self.bot_gui.start_bot()
            
            # 상태 업데이트
            self.update_bot_status()
            
            logger.info("봇이 자동으로 시작되었습니다!")
            return True
            
        except Exception as e:
            logger.error(f"봇 자동 시작 실패: {e}", exc_info=True)
            return False

    # 사용자 로드 콜백 함수
    def load_user(self, user_id):
        """사용자 ID로 사용자 객체 로드"""
        user_data = self.db.get_user_by_id(user_id)
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                email=user_data['email'],
                is_admin=user_data['is_admin']
            )
        return None

    def register_endpoints(self):
        """API 엔드포인트 등록"""
        app = self.flask_app
        
        # 사용자 로드 콜백 등록 - 클래스 메서드를 직접 참조
        self.login_manager.user_loader(self.load_user)
        
        # 로그인 페이지
        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if current_user.is_authenticated:
                return redirect(url_for('index'))
                
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                remember = 'remember' in request.form
                
                # 디버깅을 위한 출력 추가
                logger.info(f"로그인 시도: {username}")
                
                # 사용자 확인
                user_data = self.db.get_user_by_username(username)
                if user_data:
                    # 비밀번호 해시 확인
                    logger.info(f"사용자 찾음: {username}, 비밀번호 검증 시도")
                    
                    # 해시 타입 확인 및 변환
                    stored_hash = str(user_data['password_hash'])
                    
                    if check_password_hash(stored_hash, password):
                        user = User(
                            id=user_data['id'],
                            username=user_data['username'],
                            password_hash=user_data['password_hash'],
                            email=user_data['email'],
                            is_admin=user_data['is_admin']
                        )
                        login_user(user, remember=remember)
                        
                        logger.info(f"로그인 성공: {username}")
                        
                        # 원래 요청했던 페이지로 리다이렉트
                        next_page = request.args.get('next')
                        if not next_page or urlparse(next_page).netloc != '':
                            next_page = '/'
                            
                        return redirect(next_page)
                    else:
                        logger.warning(f"비밀번호 불일치: {username}")
                else:
                    logger.warning(f"사용자 없음: {username}")
                    
                # 로그인 실패
                flash('사용자명 또는 비밀번호가 잘못되었습니다.')
            
            return render_template('login.html')

        # 회원가입 페이지 - 비활성화(고정 관리자 계정만 사용)
        @app.route('/register', methods=['GET', 'POST'])
        def register():
            # 관리자 계정만 사용하도록 회원가입 기능 비활성화
            flash('회원가입이 필요하지 않습니다. 기본 관리자 계정을 사용하세요.')
            return redirect(url_for('login'))

        # 로그아웃
        @app.route('/logout')
        @login_required
        def logout():
            logout_user()
            return redirect(url_for('index'))
        
        # 메인 페이지
        @app.route('/')
        @login_required
        def index():
            return render_template('index.html')
        
        # 잔액 조회 통합 API
        @app.route('/api/balance', methods=['GET'])
        @login_required
        def get_balance():
            """통합 잔액 조회 API - 현물/선물 잔액과 추가 정보 제공"""
            try:
                # utils/config.py의 검증된 API 키 가져오기
                from utils.config import get_validated_api_credentials
                from utils.api import get_formatted_balances
                
                # API 키 검증 및 가져오기
                api_result = get_validated_api_credentials()
                
                if not api_result['success']:
                    logger.error(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}")
                    return jsonify({
                        'success': False,
                        'message': api_result.get('message', ''),
                        'error_code': 'API_VALIDATION_FAILED'
                    }), 401
                
                # 표준화된 잔액 정보 가져오기
                balance_result = get_formatted_balances(
                    api_result['api_key'], 
                    api_result['api_secret']
                )
                
                # success가 false더라도 데이터가 있으면 정상 응답으로 처리
                if balance_result.get('balance'):
                    # GUI 객체가 있으면 balance_data 업데이트
                    if hasattr(self, 'bot_gui') and self.bot_gui:
                        self.bot_gui.balance_data = {
                            'spot': balance_result['balance']['spot'],
                            'future': balance_result['balance']['future']
                        }
                    
                    # 데이터 수정: success 필드 업데이트
                    balance_data = balance_result.get('balance', {})
                    spot_success = balance_data.get('spot', {}).get('success', False)
                    future_success = balance_data.get('future', {}).get('success', False)
                    
                    # 하나라도 성공했으면 전체를 성공으로 처리
                    if spot_success or future_success:
                        balance_result['success'] = True
                    
                    return jsonify(balance_result)
                else:
                    # 데이터가 없는 경우만 에러 처리
                    return jsonify(balance_result), 400
                
            except Exception as e:
                logger.error(f"잔액 조회 중 오류: {e}")
                logger.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'message': f'서버 오류가 발생했습니다: {str(e)}',
                    'error_code': 'SERVER_ERROR'
                }), 500
        
        # 상태 확인 API (봇 상태 중심)
        @app.route('/api/status', methods=['GET'])
        @login_required
        def get_status():
            """봇 상태 조회"""
            try:
                # 현재 봇 상태 로깅
                logger.info(f"봇 상태 조회 - is_running: {self.bot_status.get('is_running', False)}")
                logger.info(f"봇 상태 상세: {self.bot_status}")
                
                # symbol 형식을 UI에 맞게 변환
                status_copy = self.bot_status.copy()
                
                # ui_symbol 추가: 마켓 타입에 따라 심볼 형식 변환
                if status_copy.get('symbol') and status_copy.get('market_type'):
                    market_type = status_copy.get('market_type', 'spot')
                    original_symbol = status_copy.get('symbol', '')
                    
                    if market_type == 'futures':
                        # 선물: 슬래시 제거 (BTC/USDT → BTCUSDT)
                        ui_symbol = original_symbol.replace('/', '')
                    else:
                        # 현물: 슬래시 추가 (BTCUSDT → BTC/USDT)
                        if '/' not in original_symbol and len(original_symbol) > 4:
                            # USDT로 끝나는 경우
                            if original_symbol.endswith('USDT'):
                                ui_symbol = original_symbol[:-4] + '/' + original_symbol[-4:]
                            else:
                                ui_symbol = original_symbol
                    
                    status_copy['ui_symbol'] = ui_symbol
                
                return jsonify({
                    'success': True,
                    'data': status_copy
                })
            except Exception as e:
                logger.error(f"봇 상태 조회 오류: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # 시장 데이터 조회 API 수정 - utils/api.py 활용
        @app.route('/api/market/<symbol>')
        @login_required
        def get_market_data(symbol):
            """시장 데이터 조회 API"""
            try:
                from utils.config import get_validated_api_credentials
                from utils.api import get_ticker, get_orderbook
                
                # API 키 검증
                api_result = get_validated_api_credentials()
                
                if not api_result['success']:
                    return jsonify({
                        'success': False,
                        'message': api_result.get('message', ''),
                        'error_code': 'API_VALIDATION_FAILED'
                    }), 401
                
                # 티커 정보 가져오기
                ticker_result = get_ticker(
                    api_result['api_key'],
                    api_result['api_secret'],
                    symbol
                )
                
                if not ticker_result['success']:
                    return jsonify(ticker_result), 400
                
                # 추가 시장 정보 (필요시 orderbook 등)
                # orderbook_result = get_orderbook(...)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'ticker': ticker_result['data'],
                        'timestamp': datetime.now().isoformat()
                    }
                })
                
            except Exception as e:
                logger.error(f"시장 데이터 조회 중 오류: {e}")
                return jsonify({
                    'success': False,
                    'message': f'시장 데이터 조회 중 오류가 발생했습니다: {str(e)}',
                    'error_code': 'SERVER_ERROR'
                }), 500
        
        # 거래 내역 조회 API
        @app.route('/api/trades', methods=['GET'])
        @login_required
        def get_trades():
            try:
                # 거래 내역 데이터 가져오기
                trades = self.db.load_trades(limit=20)  # 최근 20개 거래 내역
                
                # 공통 변환 메서드를 사용하여 데이터 가공
                trades_data = [self._format_trade_data(trade) for trade in trades]
                    
                return jsonify({
                    'success': True,
                    'data': trades_data
                })
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='get_trades')

        # 포지션 정보 조회 API
        @app.route('/api/positions', methods=['GET'])
        @login_required
        def api_get_positions():
            """현재 열린 포지션 정보 가져오기"""
            try:
                logger.info("포지션 정보 조회 시작")
                
                # API 키 가져오기
                api_result = get_validated_api_credentials()
                if not api_result['success']:
                    logger.warning(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}")
                    return jsonify({
                        'success': False,
                        'error': api_result['error']
                    }), 401 if 'API credentials' in api_result['error'] else 400
                
                api_key = api_result['api_key']
                api_secret = api_result['api_secret']
                    
                # 새롭게 구현한 함수로 포지션 정보 가져오기
                positions_data = get_positions(api_key, api_secret)

                # 포지션 정보 기록 (DB 저장)
                if positions_data and isinstance(positions_data, list) and len(positions_data) > 0:
                    self.save_positions(positions_list=positions_data)
                    logger.info(f"포지션 정보 저장 완료: {len(positions_data)}개 포지션")
                else:
                    logger.info("저장할 포지션이 없습니다.")
                
                return jsonify({
                    'success': True,
                    'data': positions_data
                })
            except Exception as e:
                logger.error(f"포지션 조회 중 오류 발생: {str(e)}")
                logger.error(traceback.format_exc())
                return self._create_error_response(e, status_code=500, endpoint='get_positions')
        
        # Position 객체로 포지션 조회 API
        @app.route('/api/positions_objects', methods=['GET'])
        @login_required
        def get_positions_objects():
            """
            Position 객체를 사용하여 포지션 조회
            """
            try:
                logger.info("[시작] Position 객체 기반 포지션 조회")
                
                # API 자격 증명 가져오기
                api_result = get_validated_api_credentials()
                if not api_result.get('success'):
                    logger.warning(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}")
                    return jsonify({
                        'success': False,
                        'error': api_result['error']
                    }), 401 if 'API credentials' in api_result['error'] else 400
                
                api_key = api_result['api_key']
                api_secret = api_result['api_secret']
                    
                # Position 객체로 포지션 정보 가져오기
                position_objects = get_positions_with_objects(api_key, api_secret)
                
                # Position 객체를 딕셔너리로 변환하여 JSON 직렬화 가능하게 만듦
                positions_data = []
                for pos in position_objects:
                    try:
                        pos_dict = pos.to_dict_compatible()
                        # 추가 정보 포함
                        pos_dict['type'] = 'Position Object'
                        pos_dict['class_name'] = pos.__class__.__name__
                        positions_data.append(pos_dict)
                    except Exception as e:
                        logger.error(f"Position 객체 변환 실패: {e}")
                        continue
                
                # DB에도 저장 (Position 객체로)
                if position_objects:
                    for pos_obj in position_objects:
                        self.db.save_position(pos_obj)
                    logger.info(f"Position 객체 DB 저장 완료: {len(position_objects)}개")
                
                logger.info(f"Position 객체 조회 완료: {len(positions_data)}개")
                
                return jsonify({
                    'success': True,
                    'data': positions_data,
                    'count': len(positions_data),
                    'message': f"{len(positions_data)}개의 포지션이 조회되었습니다."
                })
                
            except Exception as e:
                logger.error(f"Position 객체 조회 중 오류 발생: {str(e)}")
                logger.error(traceback.format_exc())
                return self._create_error_response(e, status_code=500, endpoint='get_positions_objects')
        
        # 손절/이익실현 설정 API
        @app.route('/api/set_stop_loss_take_profit', methods=['POST'])
        @login_required
        def set_stop_loss_take_profit():
            try:
                # 최상위 로깅
                logger.info("[시작] 손절/이익실현 설정 API 호출")
                
                # 요청 데이터 파싱
                data = request.json
                if not data:
                    return self._create_error_response(
                        Exception("요청 데이터가 없습니다"), 
                        status_code=400, 
                        endpoint='set_stop_loss_take_profit'
                    )
                
                # 필수 파라미터 검증
                symbol = data.get('symbol')
                if not symbol:
                    return self._create_error_response(
                        Exception("심볼이 지정되지 않았습니다"), 
                        status_code=400, 
                        endpoint='set_stop_loss_take_profit'
                    )
                
                # API 키 및 시크릿 가져오기
                api_result = get_validated_api_credentials()
                
                if not api_result['success']:
                    return self._create_error_response(
                        Exception(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}"), 
                        status_code=500, 
                        endpoint='set_stop_loss_take_profit'
                    )
                
                api_key = api_result['api_key']
                api_secret = api_result['api_secret']
                
                # 새로운 유틸리티 함수를 사용하여 손절/이익실현 설정
                from utils.api import set_stop_loss_take_profit
                
                # 입력값 처리
                side = data.get('side', 'BOTH')  # 기본값은 'BOTH'
                stop_loss = None
                take_profit = None
                
                # 비율 대신 직접 가격을 지정한 경우 처리
                if 'stop_loss_price' in data:
                    stop_loss = float(data.get('stop_loss_price'))
                elif 'stop_loss_pct' in data and 'entry_price' in data:
                    # 상대적 비율에서 가격 계산
                    entry_price = float(data.get('entry_price', 0))
                    stop_loss_pct = float(data.get('stop_loss_pct', 0.05))
                    
                    # 거래 방향에 따라 손절가 계산
                    direction = 1 if side.lower() == 'short' else -1
                    stop_loss = entry_price * (1 + direction * stop_loss_pct)
                
                # 비율 대신 직접 가격을 지정한 경우 처리
                if 'take_profit_price' in data:
                    take_profit = float(data.get('take_profit_price'))
                elif 'take_profit_pct' in data and 'entry_price' in data:
                    # 상대적 비율에서 가격 계산
                    entry_price = float(data.get('entry_price', 0))
                    take_profit_pct = float(data.get('take_profit_pct', 0.1))
                    
                    # 거래 방향에 따라 이익실현가 계산
                    direction = -1 if side.lower() == 'short' else 1
                    take_profit = entry_price * (1 + direction * take_profit_pct)
                
                # 손절/이익실현 설정 함수 호출
                result = set_stop_loss_take_profit(
                    api_key=api_key,
                    api_secret=api_secret,
                    symbol=symbol,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_side=side
                )
                
                # 포지션 ID가 있는 경우 DB에 업데이트
                position_id = data.get('position_id')
                if position_id and result.get('success', False):
                    logger.info(f"DB에 포지션 {position_id} 업데이트")
                    # DB에 포지션 정보 갱신 로직 추가 가능
                
                return jsonify({
                    'success': result.get('success', False),
                    'message': result.get('message', ''),
                    'data': result
                })
                
            except Exception as e:
                logger.error(f"손절/이익실현 설정 중 오류 발생: {str(e)}")
                logger.error(traceback.format_exc())
                return self._create_error_response(e, status_code=500, endpoint='set_stop_loss_take_profit')

        # 봇 시작 API
        @app.route('/api/start_bot', methods=['POST'])
        @login_required
        def start_bot():
            """봇 시작"""
            logger.info("봇 시작 요청 받음")
            
            if self.bot_status.get('is_running', False):
                logger.warning("봇이 이미 실행 중입니다")
                return jsonify({
                    'success': False,
                    'error': '봇이 이미 실행 중입니다'
                }), 400
            
            try:
                data = request.get_json()
                logger.info(f"봇 시작 요청 데이터: {data}")
                
                # 필수 매개변수 검증
                required_fields = ['strategy', 'symbol', 'timeframe']
                for field in required_fields:
                    if field not in data:
                        logger.error(f"필수 필드 누락: {field}")
                        return jsonify({
                            'success': False,
                            'error': f'{field}는 필수 항목입니다'
                        }), 400
                
                # 위험 관리 설정 추출 - 웹 인터페이스에서 전송하는 형식에 맞춤
                risk_management = data.get('risk_management', {})
                strategy_params = data.get('strategy_params', {})
                strategy_params.update(risk_management)
                
                # 마켓 타입에 따라 심볼 형식 변환
                symbol = data.get('symbol')
                if symbol:
                    market_type = data.get('market_type', 'spot')
                    if market_type == 'futures':
                        # 선물: 슬래시 제거 (BTC/USDT → BTCUSDT)
                        if '/' in symbol:
                            symbol = symbol.replace('/', '')
                            logger.info(f"선물 거래용 심볼 형식으로 변환: {data.get('symbol')} → {symbol}")
                    else:
                        # 현물: 슬래시 추가 (BTCUSDT → BTC/USDT)
                        if '/' not in symbol and (symbol.endswith('USDT') or symbol.endswith('BUSD')):
                            for quote in ['USDT', 'BUSD']:
                                if symbol.endswith(quote):
                                    base = symbol[:-len(quote)]
                                    symbol = f"{base}/{quote}"
                                    logger.info(f"현물 거래용 심볼 형식으로 변환: {data.get('symbol')} → {symbol}")
                                    break
                
                # GUI API를 통해 봇 시작
                strategy = data.get('strategy')
                timeframe = data.get('timeframe')
                market_type = data.get('market_type', 'spot')
                leverage = data.get('leverage', 1)
                test_mode = data.get('test_mode', False)
                
                # 전략 파라미터 추출
                strategy_params = data.get('strategy_params', {})
                
                # 마켓 타입 설정 저장
                if hasattr(self.bot_gui, 'exchange_id') and self.exchange_api:
                    # 기존 exchange_api 인스턴스 업데이트
                    self.exchange_api.market_type = market_type
                    if market_type == 'futures':
                        self.exchange_api.leverage = leverage
                    logger.info(f"시장 타입을 {market_type}로 설정했습니다. 레버리지: {leverage}")
                
                # bot_gui 객체에도 market_type과 leverage 설정
                if hasattr(self.bot_gui, 'exchange_id'):
                    self.bot_gui.market_type = market_type
                    self.bot_gui.leverage = leverage
                    logger.info(f"bot_gui에 시장 타입 {market_type}, 레버리지 {leverage} 설정 완료")
                
                # 테스트 모드 설정
                if hasattr(self.bot_gui, 'test_mode'):
                    self.bot_gui.test_mode = test_mode
                    logger.info(f"테스트 모드: {test_mode}")
                
                # 자동 손절매/이익실현 설정 처리
                auto_sl_tp = data.get('auto_sl_tp', False)
                partial_tp = data.get('partial_tp', False)
                
                if hasattr(self.bot_gui, 'auto_sl_tp'):
                    self.bot_gui.auto_sl_tp = auto_sl_tp
                    self.bot_gui.partial_tp = partial_tp
                    logger.info(f"자동 손절매/이익실현: {auto_sl_tp}, 부분 청산: {partial_tp}")
                
                # BotThread 에 자동 손절매/이익실현 설정 및 전략 파라미터 전달
                result = self.bot_gui.start_bot_api(strategy=strategy, symbol=symbol, timeframe=timeframe,
                                                   auto_sl_tp=auto_sl_tp, partial_tp=partial_tp,
                                                   strategy_params=strategy_params)
                
                # 성공적으로 시작되면 상태 저장
                if result.get('success', False):
                    # 봇 상태 업데이트
                    self.bot_status.update({
                        'is_running': True,
                        'strategy': strategy,
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'market_type': market_type,
                        'leverage': leverage,
                        'test_mode': test_mode,
                        'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                    # 반환값에서 비밀번호 필드 제거 (JSON 직렬화 문제 방지)
                    if 'api_key' in result:
                        del result['api_key']
                    if 'api_secret' in result:
                        del result['api_secret']
                    
                    # 봇 상태 저장
                    try:
                        # 봇 시작 상태 저장
                        additional_info = {
                            'via': 'web_api',
                            'client_ip': request.remote_addr
                        }
                        
                        self._save_bot_state(
                            is_running=True,
                            symbol=symbol,
                            timeframe=timeframe,
                            strategy=strategy,
                            strategy_params=strategy_params,  # strategy_params로 변경
                            market_type=market_type,
                            leverage=leverage,
                            test_mode=test_mode,
                            auto_sl_tp=auto_sl_tp,
                            partial_tp=partial_tp,
                            additional_info=additional_info
                        )
                        
                        logger.info(f"봇 상태 저장 성공: {symbol}, {strategy}")
                    except Exception as e:
                        logger.warning(f"봇 상태 저장 중 오류: {e}")
                
                # 성공/실패에 따른 응답
                if result.get('success', False):
                    return jsonify(result)
                else:
                    return jsonify(result), 400
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='start_bot')
        
        # 봇 중지 API
        @self.flask_app.route('/api/stop_bot', methods=['POST'])
        @login_required
        def stop_bot():
            try:
                # GUI API를 통해 봇 중지
                result = self.bot_gui.stop_bot_api()
                
                # 봇 상태 업데이트
                if result.get('success', False):
                    self.bot_status.update({
                        'is_running': False,
                        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # 봇을 중지할 때 상태 저장 (실행 중지 상태로 갱신)
                try:
                    # 중지 관련 추가 정보
                    additional_info = {
                        'stopped_via': 'web_api',
                        'stopped_at': datetime.now().isoformat(),
                        'client_ip': request.remote_addr
                    }
                    
                    # 봇 중지 상태 저장
                    self._save_bot_state(
                        is_running=False,
                        additional_info=additional_info,
                        update_existing=True  # 기존 상태 업데이트
                    )
                    
                    logger.info("봇 중지 상태 저장 완료")
                except Exception as e:
                    logger.warning(f"봇 중지 상태 저장 중 오류: {e}")
                
                return jsonify(result)
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='stop_bot')
        
        # 데이터 동기화 스레드 시작
    def start_data_sync(self):
        """
        바이낸스에서 주기적으로 데이터를 가져와 DB에 동기화하는 스레드 시작
        차등화된 주기로 각 데이터 유형별 동기화 수행
        """
        if self.sync_thread is not None and self.sync_thread.is_alive():
            logger.info("데이터 동기화 스레드가 이미 실행 중입니다.")
            return
        
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._data_sync_worker, daemon=True)
        self.sync_thread.start()
        logger.info(f"차등화된 주기(가격:{self.price_sync_interval}초, 주문:{self.order_sync_interval}초, 포지션:{self.position_sync_interval}초, 잔액:{self.balance_sync_interval}초)로 데이터 동기화 스레드 시작")
    
    # 데이터 동기화 워커 함수
    def _data_sync_worker(self):
        """
        차등화된 주기로 바이낸스 데이터를 가져와 DB에 저장하는 워커 함수
        데이터 유형별로 다른 동기화 주기 적용
        """
        last_price_sync = 0
        last_order_sync = 0
        last_position_sync = 0
        last_balance_sync = 0
        
        while self.sync_running:
            try:
                # 거래소 API가 없는 경우 초기화 시도
                if self.exchange_api is None:
                    logger.warning("거래소 API가 초기화되지 않았습니다. 초기화를 시도합니다.")
                    time.sleep(5)  # 5초 후 다시 시도
                    continue
                
                current_time = time.time()
                
                # 가격 정보 동기화 (높은 빈도)
                if current_time - last_price_sync >= self.price_sync_interval:
                    self._sync_price_data()
                    last_price_sync = current_time
                
                # 주문 상태 동기화
                if current_time - last_order_sync >= self.order_sync_interval:
                    self._sync_orders()
                    last_order_sync = current_time
                
                # 포지션 정보 동기화
                if current_time - last_position_sync >= self.position_sync_interval:
                    self._sync_positions()
                    last_position_sync = current_time
                
                # 잔액 정보 동기화 (낮은 빈도)
                if current_time - last_balance_sync >= self.balance_sync_interval:
                    self._sync_balance()
                    last_balance_sync = current_time
                
                # 거래 내역 동기화 (포지션 동기화와 같은 주기)
                if current_time - last_position_sync >= self.position_sync_interval:
                    self._sync_trades()
                
            except requests.exceptions.RequestException as e:
                # 네트워크 관련 오류 - 재시도 가능
                logger.warning(f"데이터 동기화 중 네트워크 오류(재시도 예정): {str(e)}")
                # 재시도 로직을 위해 짧은 대기 시간 설정
                time.sleep(2)
            except json.JSONDecodeError as e:
                # JSON 파싱 오류 - 일시적인 API 응답 문제일 수 있음
                logger.warning(f"데이터 동기화 중 JSON 파싱 오류(재시도 예정): {str(e)}")
                time.sleep(2)
            except Exception as e:
                # 기타 모든 예외 처리
                logger.error(f"데이터 동기화 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                # 심각한 오류 후 좀 더 긴 대기 시간 설정
                time.sleep(5)
            
            # 최소 동기화 주기(가격 데이터)만큼 대기
            time.sleep(1)  # 1초마다 체크하여 각 데이터 유형별 동기화 타이밍 확인
        
        # 시장 타입이 'futures'가 아닐 경우 실제 포지션 조회 스킵
        if not self.exchange_api or self.exchange_api.market_type != 'futures':
            logger.debug(f"현재 시장 타입이 {self.exchange_api.market_type if self.exchange_api else 'unknown'}이미로 실제 포지션 정보를 조회하지 않습니다.")
        else:
            try:
                # 거래소에서 현재 포지션 정보 가져오기
                try:
                    # 함수인지 확인하고 호출 방식 변경
                    if callable(self.exchange_api.get_positions):
                        positions = self.exchange_api.get_positions()  # 함수 호출
                        
                        # 반환값이 리스트인지 확인
                        if not isinstance(positions, list):
                            positions = []  # 리스트가 아니면 빈 리스트로 초기화
                            logger.warning("get_positions() 함수가 리스트를 반환하지 않았습니다.")
                    else:
                        positions = []  # get_positions가 함수가 아니면 빈 리스트 사용
                        logger.warning("get_positions가 함수가 아닙니다.")
                    
                    if positions:
                        # 가져온 포지션을 DB에 저장
                        for pos in positions:
                            self.db.save_position(pos)
                        logger.info(f"포지션 정보 동기화 완료: {len(positions)}개 포지션")
                    else:
                        logger.info("활성화된 실제 포지션이 없습니다.")
                except TypeError as type_error:
                    logger.error(f"포지션 정보 형식 오류: {str(type_error)}")
                    positions = []  # 오류 발생 시 빈 리스트로 초기화
                    
            except requests.exceptions.RequestException as e:
                # 네트워크 관련 오류 - 재시도 가능
                logger.warning(f"포지션 정보 조회 중 네트워크 오류(재시도 예정): {str(e)}")
                time.sleep(2)
            except json.JSONDecodeError as e:
                # JSON 파싱 오류 - 일시적인 API 응답 문제일 수 있음
                logger.warning(f"포지션 정보 조회 중 JSON 파싱 오류(재시도 예정): {str(e)}")
                time.sleep(2)
            except Exception as e:
                # 현물 계좌에서 포지션 조회 오류이면 무시
                if "MarketTypeError" in str(e.__class__) or "현물 계좌에서는 포지션 조회가 불가능합니다" in str(e):
                    logger.debug(f"현물 계좌에서는 포지션 조회가 불가능합니다: {self.exchange_api.exchange_id if self.exchange_api else 'unknown'}")
                else:
                    logger.error(f"포지션 정보 동기화 중 오류: {str(e)}")
                    logger.error(traceback.format_exc())
        
        # 테스트 포지션 정의 및 보존
        # 테스트 포지션 샘플 데이터 (실제 거래소 연결 실패 시 사용)
        test_positions = [
            {
                'id': 'test_pos_1',
                'symbol': 'BTC/USDT',
                'side': 'long',
                'amount': 0.01,
                'entry_price': 60000.0,
                'status': 'open',
                'pnl': 50.0,
                'leverage': 10,
                'created_at': datetime.now().timestamp()
            }
        ]
        
        # 테스트 포지션 보존
        for test_pos in test_positions:
            # 중복 저장 방지
            existing_ids = [p.get('id') for p in self.db.load_positions()]
            if test_pos.get('id') not in existing_ids and test_pos.get('status') == 'open':
                logger.info(f"테스트 포지션 보존: {test_pos.get('symbol')}, {test_pos.get('side')}")
                self.db.save_position(test_pos)
    
    # 가격 데이터 동기화
    def _sync_price_data(self):
        """
        거래소에서 최신 가격 데이터를 가져와 DB에 저장
        리팩토링: 표준화된 api.get_ticker() 함수를 사용하도록 변경
        """
        try:
            if not self.exchange_api:
                return
                
            # 현재 심볼 가격 가져오기
            try:
                # 원래 심볼에서 콜론(:) 이후 부분 제거 (BTCUSDT:USDT → BTCUSDT)
                symbol = self.exchange_api.symbol
                if ':' in symbol:
                    symbol = symbol.split(':')[0]
                    logger.info(f"심볼 형식 변환: {self.exchange_api.symbol} → {symbol}")
                
                # API 키 가져오기 (utils/config.py 사용)
                api_result = get_validated_api_credentials()
                
                if not api_result['success']:
                    logger.warning(f"API 키 검증 실패: {api_result.get('message', '알 수 없는 오류')}")
                    return
                
                api_key = api_result['api_key']
                api_secret = api_result['api_secret']
                
                # 새로 추가된 표준 API 호출 함수 사용
                ticker_result = api.get_ticker(
                    api_key=api_key,
                    api_secret=api_secret,
                    symbol=symbol
                )
                
                if ticker_result.get('success', False) and 'last' in ticker_result:
                    current_price = ticker_result['last']
                    
                    # 가격 데이터 DB에 저장
                    self.db.update_price_data({
                        'symbol': symbol,
                        'price': current_price,
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.debug(f"가격 데이터 동기화 완료: {symbol} = {current_price}")
                else:
                    # API 호출은 성공했지만 가격 정보가 없는 경우
                    error_msg = ticker_result.get('message', '알 수 없는 오류')
                    logger.debug(f"API 응답에서 가격 데이터를 찾을 수 없습니다: {error_msg}")
                    
                    # 기존 방식으로 폴백 시도
                    current_price = 0
                    if hasattr(self.exchange_api, 'get_current_price') and callable(self.exchange_api.get_current_price):
                        current_price = self.exchange_api.get_current_price()
                    elif hasattr(self.bot_gui, 'get_current_price') and callable(self.bot_gui.get_current_price):
                        current_price = self.bot_gui.get_current_price()
                    
                    if current_price > 0:
                        # 가격 데이터 DB에 저장
                        self.db.update_price_data({
                            'symbol': symbol,
                            'price': current_price,
                            'timestamp': datetime.now().isoformat()
                        })
                        logger.debug(f"폴백 방식으로 가격 데이터 동기화 완료: {symbol} = {current_price}")
                    else:
                        logger.debug("가격 데이터를 가져올 수 없습니다.")
            except Exception as e:
                logger.error(f"가격 조회 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"가격 데이터 동기화 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
    
    # 주문 상태 동기화
    def _sync_orders(self):
        """
        거래소에서 주문 상태를 가져와 DB에 저장
        """
        try:
            if not self.exchange_api:
                return
                
            # 현재 열린 주문 가져오기
            try:
                # 거래소 API에서 열린 주문 조회
                orders = None
                if hasattr(self.exchange_api, 'get_open_orders') and callable(self.exchange_api.get_open_orders):
                    orders = self.exchange_api.get_open_orders()
                elif hasattr(self.bot_gui, 'get_open_orders') and callable(self.bot_gui.get_open_orders):
                    orders = self.bot_gui.get_open_orders()
                
                if orders and isinstance(orders, list):
                    # 주문 데이터 DB에 저장
                    self.db.save_orders(orders)
                    logger.debug(f"주문 상태 동기화 완료: {len(orders)}개의 열린 주문")
                else:
                    logger.debug("열린 주문 없음")
            except Exception as e:
                logger.error(f"주문 조회 중 오류: {str(e)}")
        except Exception as e:
            logger.error(f"주문 상태 동기화 중 오류: {str(e)}")
    
    # 계좌 잔액 동기화
    def _sync_balance(self):
        """
        거래소에서 계정 잔고 정보를 가져와 DB에 저장
        """
        try:
            if not self.exchange_api:
                return
                
            # 현재 잔고 정보 가져오기
            try:
                # 거래소 API에서 계정 잔고 조회
                balance = None
                if hasattr(self.exchange_api, 'get_balance') and callable(self.exchange_api.get_balance):
                    balance = self.exchange_api.get_balance()
                elif hasattr(self.bot_gui, 'get_balance') and callable(self.bot_gui.get_balance):
                    balance = self.bot_gui.get_balance()
                
                if balance and isinstance(balance, dict):
                    # 잔고 데이터 DB에 저장
                    self.db.save_balances(balance)
                    logger.debug("계정 잔고 동기화 완료")
                else:
                    logger.debug("잔고 정보 없음")
            except Exception as e:
                logger.error(f"잔고 조회 중 오류: {str(e)}")
        except Exception as e:
            logger.error(f"계정 잔고 동기화 중 오류: {str(e)}")
    
    # 포지션 정보 동기화
    def _sync_positions(self):
        """
        거래소에서 현재 포지션 정보를 가져와 DB에 저장
        """
        try:
            # 시장 타입이 'futures'가 아닐 경우 실제 포지션 조회 스킵
            if not self.exchange_api or self.exchange_api.market_type != 'futures':
                logger.info("선물 포지션 정보를 조회할 수 없습니다.")
                return
            
            # 현재 포지션 조회
            try:
                positions = self.exchange_api.get_positions()
                if positions and isinstance(positions, list):
                    logger.debug(f"현재 포지션 조회 결과: {len(positions)}")
                    
                    # 새로운 포지션 정보로 DB 업데이트
                    self.db.save_positions(positions)
                else:
                    logger.debug("포지션 정보 없음")
                
                logger.debug("포지션 동기화 완료")
            except Exception as e:
                logger.error(f"포지션 조회 중 오류: {str(e)}")
                logger.debug("포지션 정보 업데이트 실패")
        except Exception as e:
            logger.error(f"포지션 동기화 중 오류: {str(e)}")
    
    # 거래 내역 동기화
    def _sync_trades(self):
        """
        바이낸스에서 최근 거래 내역을 가져와 DB에 저장
        """
        try:
            # 가장 최근 거래 ID 확인 (중복 방지)
            recent_trades = self.db.load_trades(limit=1)
            last_trade_id = recent_trades[0]['id'] if recent_trades else None
            
            # 거래소에서 최근 거래 내역 가져오기
            trades = self.exchange_api.get_my_trades(since=None, limit=20)
            
            if trades:
                new_trades = 0
                for trade in trades:
                    # 이미 DB에 있는 거래는 건너뛰기
                    if last_trade_id and str(trade.get('id')) == str(last_trade_id):
                        continue
                    
                    self.db.save_trade(trade)
                    new_trades += 1
                
                if new_trades > 0:
                    logger.info(f"거래 내역 동기화 완료: {new_trades}개 새 거래")
            else:
                logger.info("새로운 거래 내역이 없습니다.")
                
        except Exception as e:
            logger.error(f"거래 내역 동기화 중 오류: {str(e)}")
    
    # 동기화 중지
    def stop_data_sync(self):
        """
        데이터 동기화 스레드 중지
        """
        self.sync_running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5.0)
            logger.info("데이터 동기화 스레드 중지됨")
    
    # 데이터 변환 유틸리티 메서드
    def _format_trade_data(self, trade):
        """
        거래 데이터를 API 응답 형식으로 변환
        
        Args:
            trade (dict): DB에서 가져온 거래 데이터
            
        Returns:
            dict: API 응답용 형식으로 변환된 거래 데이터
        """
        return {
            'id': trade.get('id'),
            'symbol': trade.get('symbol'),
            'type': trade.get('type'),  # buy 또는 sell
            'price': trade.get('price'),
            'amount': trade.get('amount'),
            'cost': trade.get('cost'),
            'datetime': trade.get('datetime'),
            'profit': trade.get('profit', 0),
            'profit_percent': trade.get('profit_percent', 0),
            'test_mode': trade.get('additional_info', {}).get('test_mode', False)
        }
    
    def _format_position_data(self, position):
        """
        포지션 데이터를 API 응답 형식으로 변환
        
        Args:
            position (dict): DB에서 가져온 포지션 데이터
            
        Returns:
            dict: API 응답용 형식으로 변환된 포지션 데이터
        """
        return {
            'id': position.get('id'),
            'symbol': position.get('symbol'),
            'type': position.get('type'),  # long 또는 short
            'entry_price': position.get('entry_price'),
            'amount': position.get('amount'),
            'current_price': position.get('current_price', 0),
            'profit': position.get('profit', 0),
            'profit_percent': position.get('profit_percent', 0),
            'open_time': position.get('open_time'),
            'test_mode': position.get('additional_info', {}).get('test_mode', False),
            'stop_loss_price': position.get('stop_loss_price'),
            'take_profit_price': position.get('take_profit_price')
        }
    
    def save_positions(self, positions_list):
        """
        여러 포지션을 DB에 저장하는 메서드
        
        Args:
            positions_list (list): 포지션 데이터 리스트
        """
        try:
            if not isinstance(positions_list, list):
                logger.error("save_positions: positions_list가 리스트가 아닙니다.")
                return
            
            saved_count = 0
            for position in positions_list:
                try:
                    # DatabaseManager의 save_position 메서드 호출
                    # 별도 변환 없이 API 데이터를 그대로 사용
                    self.db.save_position(position)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"포지션 저장 중 오류: {str(e)}, 포지션 데이터: {position}")
                    continue
            
            logger.info(f"save_positions: {saved_count}/{len(positions_list)}개 포지션 저장 완료")
        except Exception as e:
            logger.error(f"save_positions 메서드 실행 중 오류: {str(e)}")
    
    # API 오류 응답 유틸리티 메서드
    def _create_error_response(self, error, status_code=500, endpoint=None):
        """
        표준화된 API 오류 응답을 생성하는 유틸리티 메서드
        
        Args:
            error (Exception 또는 str): 오류 내용
            status_code (int): HTTP 상태 코드
            endpoint (str, optional): 오류가 발생한 엔드포인트 이름
        
        Returns:
            tuple: (jsonify된 응답, 상태 코드)
        """
        # 오류 로깅
        error_str = str(error)
        endpoint_info = f" [{endpoint}]" if endpoint else ""
        logger.error(f"API 오류{endpoint_info}: {error_str}")
        
        # 오류 응답 구성
        response = {
            'success': False,
            'message': error_str,
            'error_type': error.__class__.__name__ if isinstance(error, Exception) else 'Error',
            'timestamp': datetime.now().isoformat()
        }
        
        # 엔드포인트 정보 추가
        if endpoint:
            response['endpoint'] = endpoint
            
        return jsonify(response), status_code
    
    def _save_bot_state(self, is_running, additional_info=None, update_existing=False, **kwargs):
        """
        봇 상태를 데이터베이스에 저장하는 유틸리티 메서드
        
        Args:
            is_running (bool): 봇 실행 상태
            additional_info (dict, optional): 추가 정보
            update_existing (bool, optional): 기존 상태 업데이트 여부
            **kwargs: 추가 상태 데이터 (예: symbol, timeframe, strategy 등)
        """
        if update_existing:
            # 기존 상태 정보 가져오기
            saved_state = self.db.load_bot_state()
            
            if saved_state:
                # 이전 상태 업데이트
                saved_state['is_running'] = is_running
                saved_state['updated_at'] = datetime.now().isoformat()
                
                # 추가 파라미터 적용
                for key, value in kwargs.items():
                    if value is not None:  # None이 아닌 값만 업데이트
                        saved_state[key] = value
                
                # 추가 정보 업데이트
                if additional_info:
                    if 'additional_info' not in saved_state:
                        saved_state['additional_info'] = {}
                    saved_state['additional_info'].update(additional_info)
                
                # 현재 포지션 정보 저장
                if is_running and hasattr(self.bot_gui, 'algo') and self.bot_gui.algo:
                    try:
                        # 현재 포지션 정보 가져오기
                        positions = self.bot_gui.algo.get_positions()
                        if positions:
                            saved_state['positions'] = positions
                            logger.info(f"현재 포지션 정보 저장: {len(positions)}개")
                        
                        # 현재 전략 상태 저장 (진입가, 목표가, 손절가 등)
                        if hasattr(self.bot_gui.algo, 'current_trade_info'):
                            saved_state['current_trade_info'] = self.bot_gui.algo.current_trade_info
                            logger.info("거래 정보 복원 완료")
                    except Exception as e:
                        logger.error(f"포지션 정보 저장 중 오류: {e}")
                
                # 업데이트된 상태 저장
                self.db.save_bot_state(saved_state)
                return True
            elif is_running is False:  # 이전 상태가 없는데 중지 요청인 경우
                # 최소한의 정보로 새 상태 생성
                bot_state = {
                    'exchange_id': self.bot_gui.exchange_id if hasattr(self.bot_gui, 'exchange_id') else 'unknown',
                    'symbol': getattr(self.bot_gui, 'symbol', kwargs.get('symbol', 'unknown')),
                    'timeframe': getattr(self.bot_gui, 'timeframe', kwargs.get('timeframe', '1h')),
                    'strategy': kwargs.get('strategy', 'unknown'),
                    'is_running': is_running,
                    'test_mode': getattr(self.bot_gui, 'test_mode', kwargs.get('test_mode', True)),
                    'updated_at': datetime.now().isoformat(),
                }
                
                # 추가 파라미터 적용
                for key, value in kwargs.items():
                    if value is not None and key not in bot_state:
                        bot_state[key] = value
                
                # 추가 정보 적용
                if additional_info:
                    bot_state['additional_info'] = additional_info
                
                self.db.save_bot_state(bot_state)
                return True
            else:
                # 이전 상태가 없는데 시작 요청이면 새로 생성해야 함
                pass
                
        # 새 상태 생성
        bot_state = {
            'exchange_id': self.bot_gui.exchange_id if hasattr(self.bot_gui, 'exchange_id') else 'unknown',
            'symbol': kwargs.get('symbol', getattr(self.bot_gui, 'symbol', 'unknown')),
            'timeframe': kwargs.get('timeframe', getattr(self.bot_gui, 'timeframe', '1h')),
            'strategy': kwargs.get('strategy', 'unknown'),
            'market_type': kwargs.get('market_type', 'spot'),
            'leverage': kwargs.get('leverage', 1),
            'is_running': is_running,
            'test_mode': kwargs.get('test_mode', getattr(self.bot_gui, 'test_mode', True)),
            'auto_sl_tp': kwargs.get('auto_sl_tp', False),
            'partial_tp': kwargs.get('partial_tp', False),
            'strategy_params': kwargs.get('strategy_params', {}),
            'updated_at': datetime.now().isoformat()
        }
        
        # 현재 포지션 정보 저장 (새 상태 생성 시에도)
        if is_running and hasattr(self.bot_gui, 'algo') and self.bot_gui.algo:
            try:
                # 현재 포지션 정보 가져오기
                positions = self.bot_gui.algo.get_positions()
                if positions:
                    bot_state['positions'] = positions
                    logger.info(f"새 상태에 포지션 정보 저장: {len(positions)}개")
                
                # 현재 전략 상태 저장 (진입가, 목표가, 손절가 등)
                if hasattr(self.bot_gui.algo, 'current_trade_info'):
                    bot_state['current_trade_info'] = self.bot_gui.algo.current_trade_info
                    logger.info(f"새 상태에 거래 정보 저장: {bot_state['current_trade_info']}")
            except Exception as e:
                logger.error(f"포지션 정보 저장 중 오류: {e}")
        
        # 추가 정보 적용
        if additional_info:
            bot_state['additional_info'] = additional_info
            
        # 상태 저장
        self.db.save_bot_state(bot_state)
        return True
    
    def _create_error_response(self, error, status_code=500, endpoint=None):
        """
        표준화된 API 오류 응답을 생성하는 유틸리티 메서드
        
        Args:
            error (Exception 또는 str): 오류 내용
            status_code (int): HTTP 상태 코드
            endpoint (str, optional): 오류가 발생한 엔드포인트 이름
        
        Returns:
            tuple: (jsonify된 응답, 상태 코드)
        """
        # 오류 로깅
        error_str = str(error)
        endpoint_info = f" [{endpoint}]" if endpoint else ""
        logger.error(f"API 오류{endpoint_info}: {error_str}")
        
        # 오류 응답 구성
        response = {
            'success': False,
            'message': error_str,
            'error_type': error.__class__.__name__ if isinstance(error, Exception) else 'Error',
            'timestamp': datetime.now().isoformat()
        }
        
        # 엔드포인트 정보 추가
        if endpoint:
            response['endpoint'] = endpoint
            
        return jsonify(response), status_code
    
    def run(self):
        """API 서버 시작"""
        # CSP 헤더 추가
        @self.flask_app.after_request
        def apply_security_headers(response):
            # 콘텐츠 보안 정책 - 웹앱 기능 완벽 작동을 위해 허용 정책 확장
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com https://stackpath.bootstrapcdn.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://stackpath.bootstrapcdn.com; img-src 'self' data: https: blob:; connect-src 'self' https://* ws://* wss://*; font-src 'self' data: https://cdn.jsdelivr.net; worker-src 'self' blob:; frame-src 'self'"
            # HSTS 설정 (프로덕션에서만 활성화)
            if os.getenv('PRODUCTION', 'false').lower() == 'true':
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response
        
        # SSL 인증서 경로 확인
        ssl_context = None
        cert_file = os.getenv('SSL_CERT_FILE')
        key_file = os.getenv('SSL_KEY_FILE')
        
        # SSL 인증서가 있으면 HTTPS 사용
        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            ssl_context = (cert_file, key_file)
            logger.info(f"HTTPS 모드로 서버를 실행합니다.")
        else:
            logger.warning("SSL 인증서가 없어 HTTP 모드로 서버를 실행합니다. 프로덕션 환경에서는 HTTPS 사용을 권장합니다.")
        
        logger.info(f"API 서버 실행 준비 완료. 호스트: {self.host}, 포트: {self.port}")
        try:
            # SSL 인증서 설정 (있는 경우)
            cert_path = os.getenv('SSL_CERT_PATH', None)
            key_path = os.getenv('SSL_KEY_PATH', None)
            
            ssl_context = None
            if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
                ssl_context = (cert_path, key_path)
                logger.info(f"SSL 인증서를 사용하여 HTTPS 모드로 서버를 실행합니다.")
            else:
                logger.warning("SSL 인증서가 없어 HTTP 모드로 서버를 실행합니다. 프로덕션 환경에서는 HTTPS 사용을 권장합니다.")
            
            # debug=True는 개발 환경에서만 사용
            # 재시작 경로 문제를 해결하기 위해 디버그 모드를 비활성화
            debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
            if debug_mode:
                logger.warning("디버그 모드가 활성화되어 있습니다. 프로덕션 환경에서는 비활성화하세요.")
            
            self.flask_app.run(
                host=self.host,
                port=self.port,
                debug=debug_mode,
                ssl_context=ssl_context,
                use_reloader=False  # 파일 변경 감지에 의한 자동 재시작 비활성화
            )
        finally:
            # 서버 종료 시 데이터 동기화 스레드 중지
            self.stop_data_sync()


if __name__ == '__main__':
    # 직접 실행 시 서버 시작 - 외부 접속 허용
    server = BotAPIServer(host='0.0.0.0', port=8080)
    # 데이터 동기화는 이미 BotAPIServer 초기화 시 시작됨
    server.run()
