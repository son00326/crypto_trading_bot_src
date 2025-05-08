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
        
        # 서버 실행
        server.run()
    except Exception as e:
        logger.error(f"API 서버 실행 중 오류: {str(e)}")
        raise

# 직접 실행 시 서버 시작
if __name__ == '__main__':
    run_api_server()
