#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 API 서버
import os
import sys
import threading
import logging
import json
import time
from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from PyQt5.QtWidgets import QApplication

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
        CORS(self.flask_app)
        
        # 데이터베이스 관리자 초기화
        self.db = DatabaseManager()
        
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
        self.start_data_sync(interval=60)  # 60초마다 동기화
        
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
    
    def register_endpoints(self):
        """API 엔드포인트 등록"""
        app = self.flask_app
        
        # 메인 페이지
        @app.route('/')
        def index():
            return render_template('index.html')
        
        # 상태 확인 API
        @app.route('/api/status', methods=['GET'])
        def get_status():
            try:
                # GUI에서 상태 정보 가져오기
                status = self.bot_gui.get_bot_status()
                status['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return jsonify(status)
            except Exception as e:
                logger.error(f"상태 조회 중 오류: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'상태 조회 중 오류: {str(e)}'
                }), 500
        
        # 거래 내역 조회 API
        @app.route('/api/trades', methods=['GET'])
        def get_trades():
            try:
                # 거래 내역 데이터 가져오기
                trades = self.db.load_trades(limit=20)  # 최근 20개 거래 내역
                
                # 클라이언트에 반환할 형식으로 데이터 가공
                trades_data = []
                for trade in trades:
                    trades_data.append({
                        'id': trade.get('id'),
                        'symbol': trade.get('symbol'),
                        'type': trade.get('type'),  # buy 또는 sell
                        'price': trade.get('price'),
                        'amount': trade.get('amount'),
                        'cost': trade.get('cost'),
                        'datetime': trade.get('datetime'),
                        'profit': trade.get('profit', 0),
                        'profit_percent': trade.get('profit_percent', 0)
                    })
                    
                return jsonify({
                    'success': True,
                    'data': trades_data
                })
            except Exception as e:
                logger.error(f"거래 내역 조회 중 오류: {str(e)}")
                return jsonify({
                    'success': False, 
                    'message': f'거래 내역 조회 중 오류: {str(e)}'
                }), 500

        # 포지션 정보 조회 API
        @app.route('/api/positions', methods=['GET'])
        def get_positions():
            try:
                # 현재 포지션 데이터 가져오기
                positions = self.db.load_positions()
                
                # 클라이언트에 반환할 형식으로 데이터 가공
                positions_data = []
                for pos in positions:
                    positions_data.append({
                        'id': pos.get('id'),
                        'symbol': pos.get('symbol'),
                        'type': pos.get('type'),  # long 또는 short
                        'entry_price': pos.get('entry_price'),
                        'amount': pos.get('amount'),
                        'current_price': pos.get('current_price', 0),
                        'profit': pos.get('profit', 0),
                        'profit_percent': pos.get('profit_percent', 0),
                        'open_time': pos.get('open_time')
                    })
                    
                return jsonify({
                    'success': True,
                    'data': positions_data
                })
            except Exception as e:
                logger.error(f"포지션 정보 조회 중 오류: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'포지션 정보 조회 중 오류: {str(e)}'
                }), 500
        
        # 손절/이익실현 설정 API
        @app.route('/api/set_stop_loss_take_profit', methods=['POST'])
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
                logger.error(f"손절매/이익실현 설정 중 오류: {str(e)}")
                return jsonify({
                    'success': False, 
                    'message': f'손절매/이익실현 설정 중 오류: {str(e)}'
                }), 500

        # 지갑 잔액 및 요약 정보 API
        @app.route('/api/summary', methods=['GET'])
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
                logger.error(f"요약 정보 조회 중 오류: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'요약 정보 조회 중 오류: {str(e)}'
                }), 500
        
        # 봇 시작 API
        @app.route('/api/start_bot', methods=['POST'])
        def start_bot():
            try:
                data = request.json or {}
                
                # GUI API를 통해 봇 시작
                strategy = data.get('strategy')
                symbol = data.get('symbol')
                timeframe = data.get('timeframe')
                
                result = self.bot_gui.start_bot_api(strategy=strategy, symbol=symbol, timeframe=timeframe)
                
                # 성공적으로 시작되면 상태 저장
                if result.get('success', False):
                    # 반환값에서 비밀번호 필드 제거 (JSON 직렬화 문제 방지)
                    if 'api_key' in result:
                        del result['api_key']
                    if 'api_secret' in result:
                        del result['api_secret']
                    
                    # 봇 상태 저장
                    try:
                        bot_state = {
                            'exchange_id': self.bot_gui.exchange_id if hasattr(self.bot_gui, 'exchange_id') else 'unknown',
                            'symbol': symbol or (self.bot_gui.symbol if hasattr(self.bot_gui, 'symbol') else 'unknown'),
                            'timeframe': timeframe or (self.bot_gui.timeframe if hasattr(self.bot_gui, 'timeframe') else '1h'),
                            'strategy': strategy or 'unknown',
                            'market_type': getattr(self.bot_gui, 'market_type', 'spot'),
                            'leverage': getattr(self.bot_gui, 'leverage', 1),
                            'is_running': True,
                            'test_mode': getattr(self.bot_gui, 'test_mode', True),
                            'updated_at': datetime.now().isoformat(),
                            'additional_info': {
                                'via': 'web_api',
                                'client_ip': request.remote_addr
                            }
                        }
                        
                        self.db.save_bot_state(bot_state)
                        logger.info(f"봇 상태 저장 성공: {symbol}, {strategy}")
                    except Exception as e:
                        logger.warning(f"봇 상태 저장 중 오류: {e}")
                
                # 성공/실패에 따른 응답
                if result.get('success', False):
                    return jsonify(result)
                else:
                    return jsonify(result), 400
            except Exception as e:
                logger.error(f"봇 시작 중 오류: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'봇 시작 중 오류: {str(e)}'
                }), 500
        
        # 봇 중지 API
        @self.flask_app.route('/api/stop_bot', methods=['POST'])
        def stop_bot():
            try:
                # GUI API를 통해 봇 중지
                result = self.bot_gui.stop_bot_api()
                
                # 봇을 중지할 때 상태 저장 (실행 중지 상태로 갱신)
                try:
                    # 이전 상태 정보 가져오기
                    saved_state = self.db.load_bot_state()
                    
                    if saved_state:
                        # 이전 상태에서 is_running만 업데이트
                        saved_state['is_running'] = False
                        saved_state['updated_at'] = datetime.now().isoformat()
                        
                        if 'additional_info' not in saved_state:
                            saved_state['additional_info'] = {}
                        
                        saved_state['additional_info']['stopped_via'] = 'web_api'
                        saved_state['additional_info']['stopped_at'] = datetime.now().isoformat()
                        saved_state['additional_info']['client_ip'] = request.remote_addr
                        
                        # 상태 저장
                        self.db.save_bot_state(saved_state)
                        logger.info("봇 중지 상태 저장 완료")
                    else:
                        # 이전 상태가 없는 경우 새로 생성
                        bot_state = {
                            'exchange_id': self.bot_gui.exchange_id if hasattr(self.bot_gui, 'exchange_id') else 'unknown',
                            'symbol': self.bot_gui.symbol if hasattr(self.bot_gui, 'symbol') else 'unknown',
                            'timeframe': self.bot_gui.timeframe if hasattr(self.bot_gui, 'timeframe') else '1h',
                            'strategy': 'unknown',
                            'is_running': False,
                            'test_mode': getattr(self.bot_gui, 'test_mode', True),
                            'updated_at': datetime.now().isoformat(),
                            'additional_info': {
                                'stopped_via': 'web_api',
                                'stopped_at': datetime.now().isoformat(),
                                'client_ip': request.remote_addr
                            }
                        }
                        self.db.save_bot_state(bot_state)
                        logger.info("개체를 생성하여 봇 중지 상태 저장 완료")
                except Exception as e:
                    logger.warning(f"봇 중지 상태 저장 중 오류: {e}")
                
                return jsonify(result)
            except Exception as e:
                logger.error(f"봇 중지 중 오류: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'봇 중지 중 오류: {str(e)}'
                }), 500
    
        # 잔액 정보 API
        @self.flask_app.route('/api/balance')
        def get_balance():
            try:
                # GUI API를 통해 잔액 정보 가져오기
                result = self.bot_gui.get_balance_api()
                return jsonify(result)
            except Exception as e:
                logger.error(f"잔액 정보 조회 중 오류: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'잔액 정보 조회 중 오류: {str(e)}'
                }), 500

        # 데이터 동기화 스레드 시작
    def start_data_sync(self, interval=60):
        """
        바이낸스에서 주기적으로 데이터를 가져와 DB에 동기화하는 스레드 시작
        
        Args:
            interval (int): 동기화 주기(초)
        """
        if self.sync_thread is not None and self.sync_thread.is_alive():
            logger.warning("데이터 동기화 스레드가 이미 실행 중입니다.")
            return
        
        self.sync_running = True
        self.sync_thread = threading.Thread(
            target=self._data_sync_worker, 
            args=(interval,),
            daemon=True
        )
        self.sync_thread.start()
        logger.info(f"데이터 동기화 스레드 시작됨 (주기: {interval}초)")
    
    # 데이터 동기화 워커 함수
    def _data_sync_worker(self, interval):
        """
        주기적으로 바이낸스 데이터를 가져와 DB에 저장하는 워커 함수
        
        Args:
            interval (int): 동기화 주기(초)
        """
        while self.sync_running:
            try:
                if self.exchange_api is not None:
                    self._sync_positions()
                    self._sync_trades()
                    logger.debug("데이터 동기화 완료")
            except Exception as e:
                logger.error(f"데이터 동기화 중 오류 발생: {str(e)}")
            
            # 지정된 간격만큼 대기
            time.sleep(interval)
    
    # 포지션 정보 동기화
    def _sync_positions(self):
        """
        바이낸스에서 현재 포지션 정보를 가져와 DB에 저장
        """
        try:
            # 거래소에서 현재 포지션 정보 가져오기
            positions = self.exchange_api.get_positions()
            
            if positions:
                # 가져온 포지션을 DB에 저장
                for pos in positions:
                    self.db.save_position(pos)
                logger.info(f"포지션 정보 동기화 완료: {len(positions)}개 포지션")
            else:
                logger.info("활성화된 포지션이 없습니다.")
                
        except Exception as e:
            logger.error(f"포지션 정보 동기화 중 오류: {str(e)}")
    
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
    
    # API 서버 실행
    def run(self):
        """
        API 서버 시작
        """
        logger.info(f"API 서버 실행 준비 완료. 호스트: {self.host}, 포트: {self.port}")
        try:
            self.flask_app.run(host=self.host, port=self.port, debug=True)
        finally:
            # 서버 종료 시 데이터 동기화 스레드 중지
            self.stop_data_sync()


if __name__ == '__main__':
    # 직접 실행 시 서버 시작
    server = TradingBotAPIServer(host='127.0.0.1', port=8080)
    server.start_data_sync(interval=60)  # 데이터 동기화 스레드 시작
    server.run()
