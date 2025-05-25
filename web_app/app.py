#!/usr/bin/env python3
# 암호화폐 자동 매매 봇 웹 애플리케이션
import os
import sys
import logging
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가 (상위 디렉토리 모듈 가져오기 위함)
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 환경 변수 로드
load_dotenv()

# 로깅 설정
from src.config import DATA_DIR
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, 'web_bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('crypto_bot_web')

# API 서버 임포트
from web_app.bot_api_server import TradingBotAPIServer

# CSP 헤더 추가 함수
def add_csp_headers(app):
    """
    Flask 앱에 Content Security Policy 헤더를 추가하는 함수
    
    Args:
        app: Flask 애플리케이션 인스턴스
    Returns:
        Flask 애플리케이션 인스턴스
    """
    @app.after_request
    def apply_security_headers(response):
        # unsafe-eval 허용하여 JavaScript eval() 함수 사용 가능하게 함
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self' https://*; font-src 'self' data:; worker-src 'self' blob:"
        return response
    return app

def run_api_server(host='0.0.0.0', port=8080, headless=True, debug=True):
    """
    API 서버 실행 함수
    
    Args:
        host (str): 서버 호스트 주소
        port (int): 서버 포트
        headless (bool): GUI를 화면에 표시하지 않는 모드
        debug (bool): 디버그 모드 활성화 여부
    """
    try:
        # API 서버 생성
        server = TradingBotAPIServer(host=host, port=port, headless=headless)
        logger.info(f"API 서버 실행 준비 완료. 호스트: {host}, 포트: {port}")
        
        # CSP 헤더 추가
        server.flask_app = add_csp_headers(server.flask_app)
        logger.info("CSP 헤더 추가: JavaScript eval() 함수 사용 허용")
        
        # 서버 실행
        server.run()
    except Exception as e:
        logger.error(f"API 서버 실행 중 오류: {str(e)}")
        raise

# CSP 헤더 추가 함수 (Content Security Policy)
def add_csp_headers(server):
    """Flask 서버에 CSP 헤더를 추가하는 함수"""
    @server.after_request
    def add_security_headers(response):
        # unsafe-eval 허용하여 JavaScript eval() 함수 사용 가능하게 함
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self' https://*; font-src 'self' data:; worker-src 'self' blob:"
        return response
    return server

# 직접 실행 시 서버 시작
if __name__ == '__main__':
    run_api_server()
