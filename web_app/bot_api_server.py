#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Binance API를 통한 암호화폐 트레이딩 봇 구현
# Author: Yong Son

# 프로젝트 루트 디렉토리를 시스템 경로에 추가하여 어디서든 동일한 임포트 구조 사용 가능
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 암호화폐 자동 매매 봇 API 서버
import time
import json
import random
import string
import secrets
import requests
import ssl
import urllib
import uuid
import urllib.parse
import urllib.request
import webbrowser
import threading
import configparser
import traceback
import datetime
import logging
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse

# 유틸리티 모듈 가져오기
from utils.config import get_api_credentials, validate_api_key, get_validated_api_credentials
import utils.api as api
from utils.api import get_formatted_balances, get_spot_balance, get_future_balance
from PyQt5.QtWidgets import QApplication
from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, flash, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 프로젝트 루트 디렉토리 설정 및 환경 구성
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 시스템 경로에 프로젝트 루트 추가 (모듈 임포트를 위해)
sys.path.append(project_root)

# 작업 디렉토리 변경 (상대 경로 문제 해결을 위해)
os.chdir(project_root)

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

# API 기능 임포트
from utils.config import load_env_variable, get_api_credentials, validate_api_key
from utils.api import create_binance_client, get_formatted_balances

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crypto_bot_web')

class TradingBotAPIServer:
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
        if saved_state:
            try:
                exchange_id = saved_state.get('exchange_id', DEFAULT_EXCHANGE)
                symbol = saved_state.get('symbol', DEFAULT_SYMBOL)
                timeframe = saved_state.get('timeframe', DEFAULT_TIMEFRAME)
                market_type = saved_state.get('market_type', 'futures')  # 기본값을 futures로 설정
                leverage = saved_state.get('leverage', 1)
                
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
                api_key, api_secret = get_api_credentials()
                
                if api_key and api_secret:
                    logger.info(f"API 키가 설정되어 있습니다: {api_key[:5]}...")
                else:
                    logger.warning("API 키가 설정되어 있지 않습니다. 지갑 정보를 가져올 수 없습니다.")
                
                self.exchange_api = ExchangeAPI(
                    exchange_id=exchange_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    market_type=market_type,
                    leverage=leverage
                )
                logger.info(f"거래소 API 초기화 완료: {exchange_id}, {symbol}, {market_type}")
                
                # 생성된 exchange_api 객체를 GUI 인스턴스에도 전달
                if hasattr(self.bot_gui, '__dict__'):
                    self.bot_gui.exchange_api = self.exchange_api
                    logger.info("GUI 인스턴스에 거래소 API 객체 전달 완료")
            except Exception as e:
                logger.error(f"거래소 API 초기화 오류: {str(e)}")
        
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
            
            # 실제 봇 시작 API 호출
            result = self.bot_gui.start_bot_api(strategy=strategy, symbol=symbol, timeframe=timeframe)
            logger.info(f"저장된 설정으로 봇 재시작 결과: {result}")
            return result
        except Exception as e:
            logger.error(f"저장된 설정으로 봇 재시작 중 오류: {e}")
            return {
                'success': False,
                'message': f"저장된 설정으로 봇 재시작 중 오류: {str(e)}"
            }
    
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
        
        # 상태 확인 API
        @app.route('/api/status', methods=['GET'])
        @login_required
        def get_status():
            try:
                # GUI에서 상태 정보 가져오기
                status = self.bot_gui.get_bot_status()
                status['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 수정: 매번 최신 잔액 정보를 직접 가져옴
                try:
                    logger.info("[STATUS API] 최신 잔액 정보 직접 요청 중")
                    # exchange_api에서 최신 잔액 가져오기
                    if hasattr(self.bot_gui, 'exchange_api') and self.bot_gui.exchange_api:
                        # API 키가 있는지 확인 - 새로운 유틸리티 함수 사용
                        api_key, api_secret = get_api_credentials()
                        
                        if api_key and api_secret:
                            # 바이낸스에서 직접 잔액 정보 가져오기
                            import ccxt
                            binance = ccxt.binance({
                                'apiKey': api_key,
                                'secret': api_secret,
                                'enableRateLimit': True,
                                'options': {'recvWindow': 5000}
                            })
                            
                            # 현물 잔액
                            spot_balance = binance.fetch_balance()
                            usdt_balance = 0
                            if 'USDT' in spot_balance['total']:
                                usdt_balance = spot_balance['total']['USDT']
                            
                            # 선물 잔액 (필요한 경우)
                            future_balance = 0
                            try:
                                binance_futures = ccxt.binance({
                                    'apiKey': api_key,
                                    'secret': api_secret,
                                    'enableRateLimit': True,
                                    'options': {'defaultType': 'future'}
                                })
                                futures = binance_futures.fetch_balance()
                                if 'USDT' in futures['total']:
                                    future_balance = futures['total']['USDT']
                            except Exception as e:
                                logger.error(f"[STATUS API] 선물 잔액 조회 오류: {e}")
                            
                            # 잔액 정보 업데이트
                            balance_data = {
                                'spot': {
                                    'amount': usdt_balance,
                                    'currency': 'USDT',
                                    'type': 'spot'
                                },
                                'future': {
                                    'amount': future_balance,
                                    'currency': 'USDT',
                                    'type': 'future'
                                }
                            }
                            
                            # GUI 객체의 balance_data 업데이트 (중요!)
                            try:
                                # 현물/선물 중 하나라도 잔액이 있는 경우 GUI 객체에 업데이트
                                if usdt_balance > 0:
                                    self.bot_gui.balance_data = {
                                        'amount': usdt_balance,
                                        'currency': 'USDT',
                                        'type': 'spot'
                                    }
                                elif future_balance > 0:
                                    self.bot_gui.balance_data = {
                                        'amount': future_balance,
                                        'currency': 'USDT',
                                        'type': 'future'
                                    }
                                
                                logger.info(f"[STATUS API] GUI 객체의 balance_data 업데이트 성공: {self.bot_gui.balance_data}")
                            except Exception as update_err:
                                logger.error(f"[STATUS API] GUI 객체의 balance_data 업데이트 중 오류: {update_err}")
                            
                            # 상태 업데이트
                            status['balance'] = balance_data
                            logger.info(f"[STATUS API] 잔액 정보 업데이트 성공: {status['balance']}")
                except Exception as balance_err:
                    logger.error(f"[STATUS API] 잔액 업데이트 중 오류: {balance_err}")
                    # 오류가 발생해도 API 응답은 계속 반환
                
                status['success'] = True
                return jsonify(status)
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='get_status')
        
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
        def get_positions():
            try:
                # API 키 및 시크릿 가져오기
                from utils.config import get_api_credentials
                api_key, api_secret = get_api_credentials()
                
                if not api_key or not api_secret:
                    return self._create_error_response(
                        Exception("API 키 정보가 없습니다"), 
                        status_code=500, 
                        endpoint='get_positions'
                    )
                    
                # 새롭게 구현한 함수로 포지션 정보 가져오기
                from utils.api import get_positions
                positions_data = get_positions(api_key, api_secret)
                
                # 포지션 정보 기록 (DB 저장)
                if positions_data and isinstance(positions_data, list):
                    self.db.save_positions(positions_data)
                    logger.info(f"포지션 정보 저장 완료: {len(positions_data)}개 포지션")
                    
                return jsonify({
                    'success': True,
                    'data': positions_data
                })
            except Exception as e:
                logger.error(f"포지션 조회 중 오류 발생: {str(e)}")
                logger.error(traceback.format_exc())
                return self._create_error_response(e, status_code=500, endpoint='get_positions')
        
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
                from utils.config import get_api_credentials
                api_key, api_secret = get_api_credentials()
                
                if not api_key or not api_secret:
                    return self._create_error_response(
                        Exception("API 키 정보가 없습니다"), 
                        status_code=500, 
                        endpoint='set_stop_loss_take_profit'
                    )
                
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

        # 시장 데이터 API
        @app.route('/api/market_data', methods=['GET'])
        @login_required
        def get_market_data():
            """
            시장 데이터 조회 엔드포인트 (티커, 호가창, 봉 데이터 등)
            """
            try:
                # 필수 파라미터 검증
                symbol = request.args.get('symbol')
                if not symbol:
                    return jsonify({
                        'success': False,
                        'message': '심볼 정보가 필요합니다',
                        'error_code': 'MISSING_SYMBOL'
                    }), 400
                
                # 데이터 타입 파라미터 검증
                data_type = request.args.get('type', 'ticker').lower()
                valid_types = ['ticker', 'orderbook', 'ohlcv']
                
                if data_type not in valid_types:
                    return jsonify({
                        'success': False,
                        'message': f'유효하지 않은 데이터 타입입니다. 가능한 값: {", ".join(valid_types)}',
                        'error_code': 'INVALID_DATA_TYPE'
                    }), 400
                
                # API 키 가져오기
                api_key, api_secret = self._get_api_keys_from_session()
                if not api_key or not api_secret:
                    return jsonify({
                        'success': False, 
                        'message': 'API 키가 설정되지 않았습니다',
                        'error_code': 'NO_API_KEYS'
                    }), 401
                
                # 데이터 타입에 따라 적절한 함수 호출
                if data_type == 'ticker':
                    result = api.get_ticker(
                        api_key=api_key, 
                        api_secret=api_secret, 
                        symbol=symbol
                    )
                    
                elif data_type == 'orderbook':
                    # 추가 파라미터 처리
                    try:
                        limit = int(request.args.get('limit', 20))
                        if limit < 1 or limit > 1000:
                            limit = 20  # 기본값으로 재설정
                    except ValueError:
                        limit = 20  # 숫자가 아닌 경우 기본값 사용
                    
                    result = api.get_orderbook(
                        api_key=api_key, 
                        api_secret=api_secret, 
                        symbol=symbol, 
                        limit=limit
                    )
                    
                elif data_type == 'ohlcv':
                    # 추가 파라미터 처리
                    timeframe = request.args.get('timeframe', '1h')
                    
                    try:
                        limit = int(request.args.get('limit', 100))
                        if limit < 1 or limit > 1000:
                            limit = 100  # 기본값으로 재설정
                    except ValueError:
                        limit = 100  # 숫자가 아닌 경우 기본값 사용
                    
                    result = api.get_ohlcv(
                        api_key=api_key, 
                        api_secret=api_secret, 
                        symbol=symbol, 
                        timeframe=timeframe, 
                        limit=limit
                    )
                
                # 결과 반환
                if result.get('success', False):
                    # DB에 최신 가격 데이터 저장 (티커 정보인 경우)
                    if data_type == 'ticker' and 'last' in result:
                        try:
                            self.db.update_price_data({
                                'symbol': symbol,
                                'price': result['last'],
                                'timestamp': datetime.now().isoformat()
                            })
                        except Exception as db_err:
                            logger.warning(f"가격 데이터 DB 저장 실패: {str(db_err)}")
                    
                    return jsonify(result), 200
                else:
                    return jsonify(result), 400
                
            except Exception as e:
                logger.error(f"시장 데이터 조회 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'message': f'시장 데이터 조회 중 오류가 발생했습니다: {str(e)}',
                    'error': str(e),
                    'error_code': 'SERVER_ERROR'
                }), 500
        
        # 지갑 잔액 및 요약 정보 API
        @app.route('/api/summary', methods=['GET'])
        @login_required
        def get_summary():
            # 클래스 인스턴스를 직접 참조
            bot_api_server = self
            try:
                # 지갑 요약 정보 가져오기
                # 현물과 선물 지갑 정보를 모두 가져오기
                spot_balance = None
                future_balance = None
                
                # 디버깅 로그 추가 - 단계별 검증
                logger.info("[STEP 1] get_summary 함수 시작")
                logger.info(f"bot_gui 객체 존재 확인: {hasattr(bot_api_server, 'bot_gui')}")

                if hasattr(bot_api_server, 'bot_gui'):
                    logger.info(f"[STEP 2] bot_gui 속성 목록: {dir(bot_api_server.bot_gui)}")
                    
                    if hasattr(bot_api_server.bot_gui, 'exchange_api'):
                        logger.info(f"[STEP 3] exchange_api 객체 존재 확인: {bot_api_server.bot_gui.exchange_api is not None}")
                        
                        if bot_api_server.bot_gui.exchange_api:
                            exchange_api = bot_api_server.bot_gui.exchange_api
                            # 디버깅 로그 추가
                            logger.info(f"[STEP 4] exchange_api 객체: {exchange_api}")
                            logger.info(f"[STEP 5] exchange_api 클래스: {exchange_api.__class__.__name__}")
                            logger.info(f"[STEP 6] exchange_api 속성 목록: {dir(exchange_api)}")
                            
                            # get_balance 메서드 존재 확인
                            has_get_balance = hasattr(exchange_api, 'get_balance')
                            logger.info(f"[STEP 7] get_balance 메서드 존재: {has_get_balance}")
                            
                            # exchange_id 속성 확인
                            exchange_id = exchange_api.exchange_id if hasattr(exchange_api, 'exchange_id') else 'unknown'
                            logger.info(f"[STEP 8] 거래소 ID: {exchange_id}")
                            
                            # 거래소 연결 상태 확인
                            logger.info(f"[STEP 9] 거래소 연결 상태: {exchange_api.is_connected() if hasattr(exchange_api, 'is_connected') else 'unknown'}")

                            # 현물+선물 잔고 모두 가져오기
                            try:
                                logger.info("[STEP 10] get_balance('all') 호출 시작")
                                
                                # get_balance 메서드가 있는지 다시 확인
                                if not hasattr(exchange_api, 'get_balance'):
                                    logger.error("[ERROR] exchange_api에 get_balance 메서드가 없습니다")
                                    raise AttributeError("exchange_api에 get_balance 메서드가 없습니다")
                                
                                # get_balance 메서드 시그니처 확인 시도
                                import inspect
                                try:
                                    sig = inspect.signature(exchange_api.get_balance)
                                    logger.info(f"[STEP 11] get_balance 메서드 시그니처: {sig}")
                                except Exception as e:
                                    logger.warning(f"[WARNING] 시그니처 검사 실패: {str(e)}")
                                    
                                # API 키 확인 - 새로운 유틸리티 모듈 사용
                                api_result = get_validated_api_credentials()
                                
                                if not api_result['success']:
                                    logger.error(f"[ERROR] 바이낸스 API 키 검증 실패: {api_result['message']}")
                                    # 에러를 발생시키지 않고 오류 응답 반환
                                    return jsonify({
                                        "error": f"API 키 오류: {api_result['message']}",
                                        "balance": {
                                            "spot": {"amount": 0, "currency": "USDT", "type": "spot"},
                                            "future": {"amount": 0, "currency": "USDT", "type": "future"}
                                        }
                                    }), 401
                                    
                                # API 키 정보 가져오기
                                api_key = api_result['api_key']
                                api_secret = api_result['api_secret']
                                logger.info(f"[INFO] API 키 검증 성공: {api_key[:5]}... ({api_result['message']})")
                                
                                logger.info("[INFO] 새 유틸리티 함수를 사용하여 잔액 조회 시도")
                                
                                # 새로운 유틸리티 함수를 사용하여 잔액 조회
                                balance_result = get_formatted_balances(api_key, api_secret, retries=2)
                                logger.info(f"[INFO] 잔액 조회 결과: {balance_result}")
                                
                                # 기존 데이터 형식에 부합
                                all_balances = {'spot': {'total': {}}, 'future': {'total': {}}}
                                
                                # 현물 잔액 처리
                                spot_amount = balance_result['balance']['spot'].get('amount', 0)
                                all_balances['spot']['total']['USDT'] = spot_amount
                                
                                # 선물 잔액 처리
                                future_amount = balance_result['balance']['future'].get('amount', 0)
                                all_balances['future']['total']['USDT'] = future_amount
                                
                                logger.info(f"[INFO] 변환된 잔액 정보: {all_balances}")
                                
                                # 오류가 있는지 확인
                                if not balance_result['success']:
                                    logger.warning(f"[WARNING] 잔액 조회 중 오류 발생: {balance_result['error']}")
                                    # 오류가 있어도 계속 진행 (잔액이 0으로 표시됨)
                                
                                # 중요: API 키는 환경변수를 통해 안전하게 관리합니다.
                                
                                logger.info(f"[INFO] 최종 잔액 정보: {all_balances}")
                                
                                # 이제 새로운 유틸리티 함수를 사용하여 잔액 조회가 완료되었으므로
                                # 기존의 복잡한 코드 대신 간소화된 코드로 대체했습니다.
                                
                                # 밸런스가 정상적으로 가져왔는지 확인
                                logger.info(f"[STEP 13] get_balance('all') 결과: {all_balances}")
                            except Exception as e1:
                                logger.error(f"[ERROR] 잔액 조회 중 오류 발생: {str(e1)}")
                                
                                # 실패 시 빈 잔액 정보로 초기화
                                all_balances = {'spot': {'total': {'USDT': 0}}, 'future': {'total': {'USDT': 0}}}
                                
                                # 표준화된 오류 응답 생성
                                error_response = {
                                    "error": f"잔액 조회에 실패했습니다: {str(e1)}",
                                    "balance": {
                                        "spot": {"amount": 0, "currency": "USDT", "type": "spot"},
                                        "future": {"amount": 0, "currency": "USDT", "type": "future"}
                                    }
                                }
                                
                                # 개발 환경에서는 오류 상세 정보 로깅
                                logger.error(traceback.format_exc())
                                
                                # utils.api 기능이 실패한 경우 기본 값 사용
                                all_balances = {
                                    'spot': {'total': {'USDT': 0.0}},
                                    'future': {'total': {'USDT': 0.0}}
                                }
                                logger.info(f"[INFO] 잔액 값을 가져오지 못했습니다. 기본값을 사용합니다: {all_balances}")

                                # 표준화된 응답 형식 사용
                                # utils.api의 get_formatted_balances() 함수가 이미 프론트엔드 형식과 호환되는 구조로 반환
                                
                                # 현물 밸런스 처리 - 기본 구조 유지
                                spot_balance = {
                                    'amount': all_balances['spot']['total'].get('USDT', 0.0),
                                    'currency': 'USDT',
                                    'type': 'spot'
                                }
                                
                                # 지원 통화가 없으면 다른 주요 통화 확인
                                if spot_balance['amount'] == 0:
                                    for currency in ['USDC', 'BUSD', 'BTC', 'ETH']:
                                        amount = all_balances['spot']['total'].get(currency, 0.0)
                                        if amount > 0:
                                            spot_balance = {
                                                'amount': amount,
                                                'currency': currency,
                                                'type': 'spot'
                                            }
                                            break
                                
                                # 선물 밸런스 처리 - 단순화
                                future_balance = {
                                    'amount': all_balances['future']['total'].get('USDT', 0.0),
                                    'currency': 'USDT',
                                    'type': 'future'
                                }
                            except Exception as outer_e:
                                logger.error(f"[ERROR] 외부 try 블록 예외 발생: {str(outer_e)}")
                                logger.error(traceback.format_exc())
                                
                                # 기본값 설정 - 오류 발생 시 0으로 초기화
                                spot_balance = {
                                    'amount': 0.0,
                                    'currency': 'USDT',
                                    'type': 'spot'
                                }
                                future_balance = {
                                    'amount': 0.0,
                                    'currency': 'USDT',
                                    'type': 'future'
                                }
                        
                        # 종합 밸런스 정보 초기화 - 기본값은 0 USDT로 설정
                        balance = {
                            'spot': {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'spot'
                            },
                            'future': {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'future'
                            }
                        }
                        
                        # 대체 값 설정 - spot_balance가 None이거나 필수 필드가 없는 경우
                        if spot_balance:
                            # 디버깅 로그
                            logger.info(f"현물 잔고 정보 검증: {spot_balance}")
                            # 데이터 필드 검증
                            if 'amount' in spot_balance and 'currency' in spot_balance:
                                balance['spot'] = spot_balance
                            else:
                                logger.warning("현물 잔고 정보에 필수 필드가 없습니다")
                                # 기본값 설정
                                balance['spot'] = {
                                    'amount': 0,
                                    'currency': 'USDT',
                                    'type': 'spot'
                                }
                        else:
                            # 기본값 설정
                            balance['spot'] = {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'spot'
                            }
                            
                        # 대체 값 설정 - future_balance가 None이거나 필수 필드가 없는 경우
                        if future_balance:
                            # 디버깅 로그
                            logger.info(f"선물 잔고 정보 검증: {future_balance}")
                            # 데이터 필드 검증
                            if 'amount' in future_balance and 'currency' in future_balance:
                                balance['future'] = future_balance
                            else:
                                logger.warning("선물 잔고 정보에 필수 필드가 없습니다")
                                # 기본값 설정
                                balance['future'] = {
                                    'amount': 0,
                                    'currency': 'USDT',
                                    'type': 'future'
                                }
                        else:
                            # 기본값 설정
                            balance['future'] = {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'future'
                            }
                            
                        # 디버깅 로그 추가
                        logger.info(f"최종 밸런스 정보: {balance}")
                        
                        # 수익 요약 정보
                        try:
                            if hasattr(bot_api_server.db, 'load_performance_stats'):
                                performance = bot_api_server.db.load_performance_stats()
                                logger.info(f"데이터베이스에서 가져온 성과 정보: {performance}")
                            else:
                                logger.warning("load_performance_stats 메서드가 없습니다")
                                performance = None
                        except Exception as e:
                            logger.error(f"성과 정보 불러오기 오류: {str(e)}")
                            performance = None
                        
                        # 응답 데이터 로깅
                        response_data = {
                            'success': True,
                            'data': {
                                'balance': balance,
                                'performance': performance
                            }
                        }
                        
                        # 최종 응답 전 추가 검증 - 출력 전 null 값을 기본값으로 치환
                        if balance['spot'] is None:
                            balance['spot'] = {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'spot'
                            }
                        if balance['future'] is None:
                            balance['future'] = {
                                'amount': 0,
                                'currency': 'USDT',
                                'type': 'future'
                            }
                        
                        logger.info(f"최종 응답 데이터: {response_data}")
                        return jsonify(response_data)
            except Exception as e:
                logger.error(f"요약 정보 조회 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                return bot_api_server._create_error_response(e, status_code=500, endpoint='get_summary')
        
        # 봇 시작 API
        @app.route('/api/start_bot', methods=['POST'])
        @login_required
        def start_bot():
            try:
                data = request.json or {}
                
                # GUI API를 통해 봇 시작
                strategy = data.get('strategy')
                symbol = data.get('symbol')
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
        # 잔액 정보 API
        @self.flask_app.route('/api/balance')
        @login_required
        def get_balance():
            try:
                # utils/api.py의 표준 함수 사용
                import utils.api as api
                import os
                
                # API 키/시크릿 가져오기
                api_key = os.environ.get('BINANCE_API_KEY')
                api_secret = os.environ.get('BINANCE_API_SECRET')
                
                if not api_key or not api_secret:
                    # API 키가 환경 변수에 없으면 세션에서 가져오기
                    api_result = get_validated_api_credentials()
                    if not api_result['success']:
                        logger.error(f"API 키 오류: {api_result['message']}")
                        return jsonify({
                            'success': False,
                            'message': f'오류: {api_result["message"]}',
                            'error_code': 'API_KEYS_MISSING',
                        })
                    api_key = api_result['api_key']
                    api_secret = api_result['api_secret']
                
                logger.info(f"API 키 확인됨: {api_key[:5]}...")
                
                # utils/api.py의 표준화된 함수 호출
                balanced_result = api.get_formatted_balances(api_key, api_secret)
                
                # utils/api.py의 원래 형식 그대로 사용
                if balanced_result.get('success', False):
                    logger.info(f"잔액 조회 성공: {balanced_result}")
                    
                    # GUI 업데이트용 데이터 준비
                    spot_balance = balanced_result.get('balance', {}).get('spot', {}).get('balance', 0)
                    future_balance = balanced_result.get('balance', {}).get('future', {}).get('balance', 0)
                    
                    # GUI 업데이트 - 선물 계정 기준으로 업데이트
                    balance_to_use = {
                        'balance': future_balance if future_balance > 0 else spot_balance,
                        'currency': 'USDT',
                        'type': 'future' if future_balance > 0 else 'spot'
                    }
                    
                    try:
                        if hasattr(self.bot_gui, 'balance_data'):
                            self.bot_gui.balance_data = balance_to_use
                            logger.info(f"[get_balance] GUI 객체의 balance_data 업데이트 성공: {balance_to_use}")
                    except Exception as update_err:
                        logger.error(f"[get_balance] GUI 객체의 balance_data 업데이트 중 오류: {update_err}")
                    
                    # API 응답 생성 - 원본 형식 그대로 반환
                    return jsonify({
                        'success': True,
                        'data': {
                            'balance': balanced_result.get('balance', {}),
                            'performance': {
                                'total_trades': 0,
                                'win_trades': 0,
                                'loss_trades': 0,
                                'win_rate': '0.0%',
                                'avg_profit': '0.00',
                                'total_profit': '0.00'
                            }
                        }
                    })
                else:
                    logger.error(f"잔액 조회 실패: {balanced_result}")
                    error_msg = balanced_result.get('error', {})
                    return jsonify({
                        'success': True,
                        'data': {
                            'balance': {
                                'spot': {'amount': 0, 'currency': 'USDT', 'type': 'spot'},
                                'future': {'amount': 0, 'currency': 'USDT', 'type': 'future'}
                            },
                            'performance': {
                                'total_trades': 0,
                                'win_trades': 0,
                                'loss_trades': 0,
                                'win_rate': '0.0%',
                                'avg_profit': '0.00',
                                'total_profit': '0.00'
                            }
                        }
                    })
                    
            except ValueError as e:
                logger.error(f"API 키 인증 오류: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({
                    'success': False,
                    'message': str(e),
                    'error_code': 'API_AUTH_ERROR',
                    'status_code': 401
                }), 401
            except Exception as e:
                logger.error(f"잔액 정보 조회 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                
                # 오류 유형에 따라 다른 오류 코드와 메시지 제공
                if 'connection' in str(e).lower():
                    error_code = 'CONNECTION_ERROR'
                    message = '바이낸스 API에 연결할 수 없습니다. 인터넷 연결을 확인하세요.'
                    status_code = 503
                elif 'timeout' in str(e).lower():
                    error_code = 'TIMEOUT_ERROR'
                    message = '바이낸스 API 요청 시간이 초과되었습니다. 나중에 다시 시도하세요.'
                    status_code = 504
                else:
                    error_code = 'GENERIC_ERROR'
                    message = f'잔액 정보 조회 중 오류 발생: {str(e)}'
                    status_code = 500
                    
                return jsonify({
                    'success': False,
                    'message': message,
                    'error_code': error_code,
                    'error_details': str(e),
                    'status_code': status_code
                }), status_code

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
                # 원래 심볼에서 콜론(:) 이후 부분 제거 (BTCUSDT:USDT -> BTCUSDT)
                symbol = self.exchange_api.symbol
                if ':' in symbol:
                    symbol = symbol.split(':')[0]
                    logger.info(f"심볼 형식 변환: {self.exchange_api.symbol} -> {symbol}")
                
                # API 키 가져오기 (세션에서)
                api_key, api_secret = self._get_api_keys_from_session()
                if not api_key or not api_secret:
                    logger.warning("API 키가 설정되지 않아 가격 동기화를 수행할 수 없습니다.")
                    return
                
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
    
    # API 키 가져오기
    def _get_api_keys_from_session(self):
        """
        세션에서 API 키와 시크릿을 가져오는 헬퍼 함수
        반환값:
            tuple: (api_key, api_secret) 형태로 반환, 없으면 (None, None) 반환
        """
        try:
            # 현재 로그인된 사용자 확인 - current_user가 None일 수 있음
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                # 로그인하지 않은 경우에도 환경 변수에서 API 키를 가져올 수 있음
                api_key = os.environ.get('BINANCE_API_KEY')
                api_secret = os.environ.get('BINANCE_API_SECRET')
                
                if api_key and api_secret:
                    return api_key, api_secret
                    
                logger.warning("인증된 사용자가 아닙니다. API 키를 가져올 수 없습니다.")
                return None, None
            
            # 환경변수에서 우선 시도
            api_key = os.environ.get('BINANCE_API_KEY')
            api_secret = os.environ.get('BINANCE_API_SECRET')
            
            # 업데이트 된 환경변수가 있는지 확인
            if not api_key or not api_secret:
                # 세션에서 찾기
                api_key = session.get('api_key')
                api_secret = session.get('api_secret')
            
            # 여전히 없는 경우, 사용자 데이터베이스에서 시도
            if not api_key or not api_secret:
                # 데이터베이스에서 사용자의 API 키 정보 가져오기
                if hasattr(self, 'db') and self.db:
                    user_id = current_user.get_id()
                    user_data = self.db.get_user_data(user_id)
                    
                    if user_data and 'api_key' in user_data and 'api_secret' in user_data:
                        api_key = user_data.get('api_key')
                        api_secret = user_data.get('api_secret')
            
            # 불필요한 로깅 방지를 위해 API 키가 없는 경우에만 로그 출력
            if not api_key or not api_secret:
                logger.warning("세션 또는 DB에서 API 키를 찾을 수 없습니다.")
                return None, None
            
            return api_key, api_secret
            
        except Exception as e:
            logger.error(f"API 키 가져오기 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
            return None, None
    
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
            # 시장 타입이 'futures'가 아닀 경우 실제 포지션 조회 스킵
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
    
    # 봇 상태 저장 유틸리티 메서드
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
            'updated_at': datetime.now().isoformat()
        }
        
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
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com https://stackpath.bootstrapcdn.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://stackpath.bootstrapcdn.com; img-src 'self' data: https: blob:; connect-src 'self' https://* ws://* wss://*; font-src 'self' data: https://cdn.jsdelivr.net; worker-src 'self' blob:; frame-src 'self'"
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
            # debug=True는 개발 환경에서만 사용
            debug_mode = os.getenv('DEBUG', 'true').lower() == 'true'
            self.flask_app.run(
                host=self.host,
                port=self.port,
                debug=debug_mode,
                ssl_context=ssl_context
            )
        finally:
            # 서버 종료 시 데이터 동기화 스레드 중지
            self.stop_data_sync()


if __name__ == '__main__':
    # 직접 실행 시 서버 시작 - 외부 접속 허용
    server = TradingBotAPIServer(host='0.0.0.0', port=8080)
    # 데이터 동기화는 이미 TradingBotAPIServer 초기화 시 시작됨
    server.run()
