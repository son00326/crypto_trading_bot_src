"""
환경 변수 관리 및 API 키 유효성 검증을 위한 유틸리티 모듈
"""

import os
import logging
import traceback
from typing import Tuple, Optional, Dict, Any

# 로거 설정
logger = logging.getLogger(__name__)

def load_env_variable(name: str, default: Any = None, required: bool = False) -> Any:
    """
    환경 변수를 안전하게 로드하는 함수
    
    Args:
        name: 환경 변수 이름
        default: 환경 변수가 없을 때 사용할 기본값
        required: 필수 환경 변수 여부
        
    Returns:
        환경 변수 값 또는 기본값, 필수 변수가 없으면 None
    """
    value = os.getenv(name)
    if value is None:
        if required:
            logger.error(f"필수 환경 변수 {name}이(가) 설정되지 않았습니다.")
            return None
        return default
    return value

def get_api_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    바이낸스 API 키 정보를 가져오는 함수
    
    Returns:
        (api_key, api_secret) 튜플, 없으면 (None, None)
    """
    api_key = load_env_variable('BINANCE_API_KEY', required=True)
    api_secret = load_env_variable('BINANCE_API_SECRET', required=True)
    
    if not api_key or not api_secret:
        logger.error("바이낸스 API 키 정보가 없습니다. 환경 변수를 확인해주세요.")
        return None, None
        
    return api_key, api_secret

def validate_api_key(api_key: str, api_secret: str) -> Tuple[bool, str]:
    """
    API 키의 유효성을 검증하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        
    Returns:
        (성공 여부, 메시지) 튜플
    """
    if not api_key or not api_secret:
        return False, "API 키 정보가 없습니다"
        
    try:
        import ccxt
        binance = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'timeout': 10000,  # 10초 타임아웃
            'options': {
                'recvWindow': 5000,
                'adjustForTimeDifference': True
            }
        })
        
        # 간단한 API 호출로 키 유효성 확인 - fetch_balance는 API 키 권한이 필요한 호출
        # 단순히 API 키 형식만 확인하려면 load_markets()를 사용할 수 있음
        try:
            binance.load_markets()  # 공개 API 엔드포인트, 키 형식만 확인
            logger.info("API 키 형식이 올바릅니다.")
            
            # 실제 권한 확인
            binance.fetch_balance({'recvWindow': 5000})
            return True, "API 키가 유효하며 필요한 권한이 있습니다"
        except Exception as e:
            error_msg = str(e)
            if "Invalid API-key" in error_msg or "API-key format invalid" in error_msg:
                return False, "API 키 형식이 잘못되었습니다"
            elif "Signature for this request is not valid" in error_msg:
                return False, "API 시크릿이 잘못되었습니다"
            elif "API-key has no permission" in error_msg:
                return False, "API 키에 필요한 권한이 없습니다 (읽기 권한 필요)"
            elif "Timestamp for this request" in error_msg:
                return False, "서버 시간 동기화 문제가 있습니다"
            else:
                logger.error(f"API 키 권한 검증 중 오류: {error_msg}")
                return False, f"API 키 검증 중 오류 발생: {error_msg}"
    except ImportError:
        logger.error("CCXT 라이브러리가 설치되지 않았습니다")
        return False, "CCXT 라이브러리가 설치되지 않았습니다"
    except Exception as e:
        logger.error(f"API 키 검증 중 예외 발생: {str(e)}")
        logger.error(traceback.format_exc())
        return False, f"API 키 검증 중 예기치 않은 오류: {str(e)}"

def get_validated_api_credentials() -> Dict[str, Any]:
    """
    API 키를 가져오고 유효성을 검증하여 결과를 반환하는 함수
    
    Returns:
        {
            'success': 성공 여부(bool),
            'api_key': API 키(str 또는 None),
            'api_secret': API 시크릿(str 또는 None),
            'message': 상세 메시지(str)
        }
    """
    api_key, api_secret = get_api_credentials()
    
    if not api_key or not api_secret:
        return {
            'success': False,
            'api_key': None,
            'api_secret': None,
            'message': '바이낸스 API 키 정보가 설정되지 않았습니다. 환경 변수를 확인하세요.'
        }
    
    is_valid, message = validate_api_key(api_key, api_secret)
    
    return {
        'success': is_valid,
        'api_key': api_key if is_valid else None,
        'api_secret': api_secret if is_valid else None,
        'message': message
    }
