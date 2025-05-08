#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 API 서버
import os
import sys
import threading
import time
import json
import logging
from datetime import datetime

# 프로젝트 루트 경로 추가 (상위 디렉토리 모듈 가져오기 위함)
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# PyQt5 임포트
from PyQt5.QtWidgets import QApplication
import sys

# GUI 모듈 임포트
from gui.crypto_trading_bot_gui_complete import CryptoTradingBotGUI, logger

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
        
        try:
            # PyQt5 애플리케이션 객체 초기화 (실행 중이 아니면 생성)
            self.qt_app = QApplication.instance()
            if self.qt_app is None:
                self.qt_app = QApplication(sys.argv)
            
            # 헤드리스 모드로 GUI 초기화
            from gui.crypto_trading_bot_gui_complete import main as run_gui
            self.bot_gui = run_gui(headless=headless)
            
            # 서버 설정
            self.host = host
            self.port = port
            
            logger.info(f"API 서버가 초기화되었습니다. 봇 GUI를 헤드리스 모드로 실행 중...")  
        except Exception as e:
            logger.error(f"GUI 초기화 중 오류: {str(e)}")
            raise
        
        # API 엔드포인트 등록
        self.register_endpoints()
        
        logger.info(f"API 서버 초기화 완료. 호스트: {host}, 포트: {port}, 헤드리스 모드: {headless}")
    
    def register_endpoints(self):
        """API 엔드포인트 등록"""
        
        # 메인 페이지
        @self.flask_app.route('/')
        def index():
            return render_template('index.html')
        
        # 상태 확인 API
        @self.flask_app.route('/api/status')
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
        
        # 봇 시작 API
        @self.flask_app.route('/api/start_bot', methods=['POST'])
        def start_bot():
            try:
                data = request.json or {}
                
                # GUI API를 통해 봇 시작
                strategy = data.get('strategy')
                symbol = data.get('symbol')
                timeframe = data.get('timeframe')
                
                result = self.bot_gui.start_bot_api(strategy=strategy, symbol=symbol, timeframe=timeframe)
                
                return jsonify({
                    'status': 'success',
                    'message': '봇이 시작되었습니다.',
                    'result': result
                })
            except Exception as e:
                logger.error(f"봇 시작 중 오류: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'봇 시작 중 오류: {str(e)}'
                }), 500
        
        # 봇 중지 API
        @self.flask_app.route('/api/stop_bot', methods=['POST'])
        def stop_bot():
            try:
                # GUI API를 통해 봇 중지
                result = self.bot_gui.stop_bot_api()
                
                return jsonify(result)
            except Exception as e:
                logger.error(f"봇 중지 중 오류: {str(e)}")
                return jsonify({
                    'status': 'error',
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
    
    def run(self):
        """API 서버 실행"""
        self.flask_app.run(host=self.host, port=self.port, debug=True)


if __name__ == '__main__':
    # 직접 실행 시 서버 시작
    server = TradingBotAPIServer(host='127.0.0.1', port=8080)
    server.run()
