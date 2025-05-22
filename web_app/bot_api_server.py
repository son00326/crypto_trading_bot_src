#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 API 서버
import os
import sys
import time
import json
import random
import string
import traceback
import threading
import secrets
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse
from PyQt5.QtWidgets import QApplication
from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, flash
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 프로젝트 루트 디렉토리로 작업 디렉토리 변경
# 이것은 상대 경로를 사용하는 부분에서 문제를 해결하기 위함
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# .env 파일 로드
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)
print(f"Working directory set to: {os.getcwd()}")
print(f"Loading environment variables from: {env_path}")

from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, flash
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# 표준 라이브러리를 사용하여 URL 파싱
from urllib.parse import urlparse
from PyQt5.QtWidgets import QApplication

# 사용자 모델 임포트
from web_app.models import User

# 필요한 모듈 추가
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from src.db_manager import DatabaseManager
from src.exchange_api import ExchangeAPI
from src.config import DEFAULT_EXCHANGE, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME

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
                config_file = os.path.join(home_dir, ".crypto_trading_bot", "config.env")
                
                if os.path.exists(config_file):
                    # 저장된 API 키 파일이 있으면 환경 변수에 로드
                    with open(config_file, 'r') as f:
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                os.environ[key] = value
                    logger.info(f"GUI에서 저장한 API 키 설정을 로드했습니다.")
                
                # 환경 변수에서 API 키 확인
                api_key = os.getenv('BINANCE_API_KEY')
                api_secret = os.getenv('BINANCE_API_SECRET')
                
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
                # 현재 포지션 데이터 가져오기
                positions = self.db.load_positions()
                
                # 공통 변환 메서드를 사용하여 데이터 가공
                positions_data = [self._format_position_data(pos) for pos in positions]
                    
                return jsonify({
                    'success': True,
                    'data': positions_data
                })
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='get_positions')
        
        # 손절/이익실현 설정 API
        @app.route('/api/set_stop_loss_take_profit', methods=['POST'])
        @login_required
        def set_stop_loss_take_profit():
            try:
                data = request.json
                symbol = data.get('symbol')
                position_id = data.get('position_id')
                side = data.get('side', 'long')  # 'long' 또는 'short'
                entry_price = float(data.get('entry_price', 0))
                stop_loss_pct = float(data.get('stop_loss_pct', 0.05))
                take_profit_pct = float(data.get('take_profit_pct', 0.1))
                
                # RiskManager 인스턴스 생성
                from src.risk_manager import RiskManager
                risk_manager = RiskManager(
                    exchange_id=DEFAULT_EXCHANGE, 
                    symbol=symbol
                )
                
                # 손절가, 이익실현가 계산
                stop_loss_price = risk_manager.calculate_stop_loss_price(
                    entry_price=entry_price,
                    side=side,
                    custom_pct=stop_loss_pct
                )
                
                take_profit_price = risk_manager.calculate_take_profit_price(
                    entry_price=entry_price,
                    side=side,
                    custom_pct=take_profit_pct
                )
                
                # 위험 대비 보상 비율 계산
                risk_reward_ratio = risk_manager.calculate_risk_reward_ratio(
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price
                )
                
                # 기존 포지션이 있다면 업데이트
                if position_id:
                    positions = self.db.load_positions()
                    updated = False
                    
                    for pos in positions:
                        if str(pos.get('id')) == str(position_id):
                            pos['stop_loss_price'] = stop_loss_price
                            pos['take_profit_price'] = take_profit_price
                            pos['stop_loss_pct'] = stop_loss_pct
                            pos['take_profit_pct'] = take_profit_pct
                            pos['risk_reward_ratio'] = risk_reward_ratio
                            updated = True
                            break
                            
                    if updated:
                        self.db.save_positions(positions)
                        logger.info(f"포지션 {position_id}의 손절/이익실현 설정이 업데이트되었습니다.")
                
                return jsonify({
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'position_id': position_id,
                        'side': side,
                        'entry_price': entry_price,
                        'stop_loss_price': stop_loss_price,
                        'take_profit_price': take_profit_price,
                        'risk_reward_ratio': risk_reward_ratio
                    }
                })
                
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='set_stop_loss_take_profit')

        # 지갑 잔액 및 요약 정보 API
        @app.route('/api/summary', methods=['GET'])
        @login_required
        def get_summary():
            try:
                # 지갑 요약 정보 가져오기
                # 현물과 선물 지갑 정보를 모두 가져오기
                spot_balance = None
                future_balance = None
                
                if hasattr(self.bot_gui, 'exchange_api') and self.bot_gui.exchange_api:
                    # 현물+선물 잔고 모두 가져오기
                    try:
                        all_balances = self.bot_gui.exchange_api.get_balance('all')
                        
                        # 현물 잔고 처리
                        if 'spot' in all_balances and all_balances['spot']:
                            spot_data = all_balances['spot']
                            for currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                                if currency in spot_data.get('total', {}) and spot_data['total'][currency] > 0:
                                    spot_balance = {
                                        'amount': spot_data['total'][currency],
                                        'currency': currency,
                                        'type': 'spot'
                                    }
                                    break
                            
                            # 스테이블코인이 없는 경우 다른 통화 검색
                            if not spot_balance:
                                for currency in ['BTC', 'ETH']:
                                    if currency in spot_data.get('total', {}) and spot_data['total'][currency] > 0:
                                        spot_balance = {
                                            'amount': spot_data['total'][currency],
                                            'currency': currency,
                                            'type': 'spot'
                                        }
                                        break
                        
                        # 선물 잔고 처리
                        if 'future' in all_balances and all_balances['future']:
                            future_data = all_balances['future']
                            for currency in ['USDT', 'USD', 'BUSD', 'USDC']:
                                if currency in future_data.get('total', {}) and future_data['total'][currency] > 0:
                                    future_balance = {
                                        'amount': future_data['total'][currency],
                                        'currency': currency,
                                        'type': 'future'
                                    }
                                    break
                    except Exception as e:
                        logger.error(f"잔고 정보 가져오기 오류: {str(e)}")
                
                # 이전 방식으로도 시도 (이전 코드와의 호환성 유지)
                if not spot_balance and not future_balance and hasattr(self.bot_gui, 'get_balance_api'):
                    balance_result = self.bot_gui.get_balance_api()
                    if balance_result.get('success', False):
                        balance_data = balance_result.get('data')
                        if balance_data.get('type') == 'future':
                            future_balance = balance_data
                        else:
                            spot_balance = balance_data
                
                # 종합 밸런스 정보
                balance = {
                    'spot': spot_balance,
                    'future': future_balance
                }
                
                # 수익 요약 정보
                performance = self.db.load_performance_stats() if hasattr(self.db, 'load_performance_stats') else None
                
                return jsonify({
                    'success': True,
                    'data': {
                        'balance': balance,
                        'performance': performance
                    }
                })
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='get_summary')
        
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
                
                # BotThread 에 자동 손절매/이익실현 설정 전달
                result = self.bot_gui.start_bot_api(strategy=strategy, symbol=symbol, timeframe=timeframe, 
                                                   auto_sl_tp=auto_sl_tp, partial_tp=partial_tp)
                
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
                # GUI API를 통해 잔액 정보 가져오기
                result = self.bot_gui.get_balance_api()
                return jsonify(result)
            except Exception as e:
                return self._create_error_response(e, status_code=500, endpoint='get_balance')

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
                positions = self.exchange_api.get_positions()
                
                if positions:
                    # 가져온 포지션을 DB에 저장
                    for pos in positions:
                        self.db.save_position(pos)
                    logger.info(f"포지션 정보 동기화 완료: {len(positions)}개 포지션")
                else:
                    logger.info("활성화된 실제 포지션이 없습니다.")
                    
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
        """
        try:
            if not self.exchange_api:
                return
                
            # 현재 심볼 가격 가져오기
            try:
                symbol = self.exchange_api.symbol
                current_price = 0
                
                # 거래소 API에서 현재 가격 조회
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
                    logger.debug(f"가격 데이터 동기화 완료: {symbol} = {current_price}")
                else:
                    logger.debug("가격 데이터를 가져올 수 없습니다.")
            except Exception as e:
                logger.error(f"가격 조회 중 오류: {str(e)}")
        except Exception as e:
            logger.error(f"가격 데이터 동기화 중 오류: {str(e)}")
    
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
            
        self.db.save_bot_state(bot_state)
        return True
        
    # API 서버 실행
    def run(self):
        """
        API 서버 시작
        """
        # 보안 헤더 설정
        @self.flask_app.after_request
        def apply_security_headers(response):
            # XSS 방지
            response.headers["X-XSS-Protection"] = "1; mode=block"
            # 클릭재킹 방지
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            # MIME 스니핑 방지
            response.headers["X-Content-Type-Options"] = "nosniff"
            # 콘텐츠 보안 정책
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data:;"
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
    # 직접 실행 시 서버 시작
    server = TradingBotAPIServer(host='127.0.0.1', port=8080)
    # 데이터 동기화는 이미 TradingBotAPIServer 초기화 시 시작됨
    server.run()
