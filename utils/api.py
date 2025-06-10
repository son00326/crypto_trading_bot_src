"""
바이낸스 API 호출을 위한 유틸리티 함수들

이 모듈은 CCXT 라이브러리를 사용하여 바이낸스 API 호출을 단순화하고 표준화합니다.
주요 기능:
- 현물/선물 잔액 조회
- API 응답 파싱 및 표준화
- 오류 처리 및 재시도 로직
"""

import time
import logging
import traceback
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

def create_binance_client(api_key: str, api_secret: str, is_future: bool = False) -> Any:
    """
    CCXT 바이낸스 클라이언트 생성 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        is_future: 선물 거래용 클라이언트 생성 여부
        
    Returns:
        ccxt.binance 인스턴스
    """
    try:
        import ccxt
        
        options = {
            'adjustForTimeDifference': True,
            'recvWindow': 5000
        }
        
        if is_future:
            options['defaultType'] = 'future'
        else:
            options['defaultType'] = 'spot'
            
        binance = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'timeout': 10000,  # 10초 타임아웃
            'options': options
        })
        
        return binance
    except ImportError:
        logger.error("CCXT 라이브러리가 설치되지 않았습니다. 'pip install ccxt'로 설치하세요.")
        raise
    except Exception as e:
        logger.error(f"바이낸스 클라이언트 생성 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def handle_api_error(e: Exception) -> Dict[str, Any]:
    """
    바이낸스 API 오류 처리 함수
    
    Args:
        e: 발생한 예외
        
    Returns:
        표준화된 오류 응답 딕셔너리
    """
    error_msg = str(e)
    error_code = 'UNKNOWN_ERROR'
    
    if 'Invalid API-key' in error_msg or 'API-key format invalid' in error_msg:
        error_code = 'INVALID_API_KEY'
        message = 'API 키 형식이 잘못되었습니다'
    elif 'Signature for this request is not valid' in error_msg:
        error_code = 'INVALID_SIGNATURE'
        message = 'API 시크릿이 잘못되었습니다'
    elif 'API-key has no permission' in error_msg:
        error_code = 'INSUFFICIENT_PERMISSION'
        message = 'API 키에 필요한 권한이 없습니다 (읽기 권한 필요)'
    elif 'Timestamp for this request' in error_msg:
        error_code = 'TIMESTAMP_ERROR'
        message = '서버 시간 동기화 문제가 있습니다'
    elif 'Too many requests' in error_msg or 'too much request weight used' in error_msg:
        error_code = 'RATE_LIMIT'
        message = 'API 호출 제한에 도달했습니다. 잠시 후 다시 시도하세요.'
    elif 'Network request failed' in error_msg or 'Connection refused' in error_msg:
        error_code = 'NETWORK_ERROR'
        message = '네트워크 연결 오류가 발생했습니다'
    else:
        message = f'API 호출 중 오류 발생: {error_msg}'
    
    logger.error(f"바이낸스 API 오류 [{error_code}]: {message}")
    
    return {
        'success': False,
        'error_code': error_code,
        'message': message,
        'detail': error_msg
    }

def is_tradable(balance: Dict[str, Any], min_amount: float = 10.0) -> bool:
    """
    거래 가능한 잔액인지 확인하는 함수
    
    Args:
        balance: 잔액 정보 딕셔너리
        min_amount: 최소 거래 가능 금액 (기본값: 10.0 USDT)
        
    Returns:
        거래 가능 여부
    """
    if not isinstance(balance, dict):
        return False
        
    # USDT 잔액 확인
    usdt_total = balance.get('total', {}).get('USDT', 0)
    
    return usdt_total >= min_amount


def get_spot_balance(api_key: str, api_secret: str, retries: int = 1) -> Dict[str, Any]:
    """
    현물 계정 잔액 조회 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        retries: 재시도 횟수
        
    Returns:
        현물 계정 잔액 정보를 포함한 딕셔너리
    """
    if not api_key or not api_secret:
        return {
            'success': False,
            'error_code': 'MISSING_API_KEYS',
            'message': 'API 키와 시크릿이 필요합니다',
            'usdt_balance': 0
        }
    
    for attempt in range(retries + 1):
        try:
            # 바이낸스 클라이언트 생성
            binance = create_binance_client(api_key, api_secret, is_future=False)
            
            # 현물 계정 잔액 조회
            balance = binance.fetch_balance()
            
            # USDT 잔액 추출
            usdt_balance = balance.get('total', {}).get('USDT', 0)
            
            return {
                'success': True,
                'balance': balance,
                'usdt_balance': usdt_balance
            }
            
        except Exception as e:
            if attempt < retries:
                logger.warning(f"현물 잔액 조회 실패 {attempt+1}/{retries+1}, 재시도 중...: {str(e)}")
                time.sleep(1)  # 재시도 전 1초 대기
                continue
            else:
                return handle_api_error(e)
    
    # 이 코드는 실행되지 않지만, 타입 체크를 위해 필요
    return {
        'success': False,
        'error_code': 'UNKNOWN_ERROR',
        'message': '알 수 없는 오류',
        'usdt_balance': 0
    }


def get_future_balance(api_key: str, api_secret: str, retries: int = 1) -> Dict[str, Any]:
    """
    선물 계정 잔액 조회 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        retries: 재시도 횟수
        
    Returns:
        선물 계정 잔액 정보를 포함한 딕셔너리
    """
    if not api_key or not api_secret:
        return {
            'success': False,
            'error_code': 'MISSING_API_KEYS',
            'message': 'API 키와 시크릿이 필요합니다',
            'usdt_balance': 0
        }
    
    for attempt in range(retries + 1):
        try:
            # 바이낸스 선물 클라이언트 생성
            binance_future = create_binance_client(api_key, api_secret, is_future=True)
            
            # 선물 계정 잔액 조회
            balance = binance_future.fetch_balance()
            
            # USDT 잔액 추출
            usdt_balance = balance.get('total', {}).get('USDT', 0)
            
            return {
                'success': True,
                'balance': balance,
                'usdt_balance': usdt_balance
            }
            
        except Exception as e:
            if attempt < retries:
                logger.warning(f"선물 잔액 조회 실패 {attempt+1}/{retries+1}, 재시도 중...: {str(e)}")
                time.sleep(1)  # 재시도 전 1초 대기
                continue
            else:
                return handle_api_error(e)
    
    # 이 코드는 실행되지 않지만, 타입 체크를 위해 필요
    return {
        'success': False,
        'error_code': 'UNKNOWN_ERROR',
        'message': '알 수 없는 오류',
        'usdt_balance': 0
    }


def get_all_balances(api_key: str, api_secret: str, retries: int = 1) -> Dict[str, Any]:
    """
    현물 및 선물 계정 잔액 통합 조회 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        retries: 재시도 횟수
        
    Returns:
        현물 및 선물 계정 잔액 정보를 포함한 딕셔너리
    """
    # 현물 잔액 조회
    spot_result = get_spot_balance(api_key, api_secret, retries)
    
    # 선물 잔액 조회
    future_result = get_future_balance(api_key, api_secret, retries)
    
    # 결과 통합
    return {
        'success': spot_result.get('success', False) or future_result.get('success', False),
        'spot': {
            'success': spot_result.get('success', False),
            'balance': spot_result.get('usdt_balance', 0),
            'error': spot_result.get('message', None) if not spot_result.get('success', False) else None
        },
        'future': {
            'success': future_result.get('success', False),
            'balance': future_result.get('usdt_balance', 0),
            'error': future_result.get('message', None) if not future_result.get('success', False) else None
        },
        'total_balance': spot_result.get('usdt_balance', 0) + future_result.get('usdt_balance', 0)
    }


# ==========================================================================
# API 응답 파싱 및 표준화 함수
# ==========================================================================

def parse_spot_balance(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    현물 API 응답을 표준 형식으로 변환
    
    Args:
        response: API 응답 데이터
        
    Returns:
        표준화된 현물 잔액 정보
    """
    if not response.get('success', False):
        return {
            'amount': 0,
            'currency': 'USDT',
            'type': 'spot',
            'error': response.get('message', '알 수 없는 오류')
        }
    
    usdt_balance = response.get('usdt_balance', 0)
    return {
        'amount': usdt_balance,
        'currency': 'USDT',
        'type': 'spot'
    }


def parse_future_balance(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    선물 API 응답을 표준 형식으로 변환
    
    Args:
        response: API 응답 데이터
        
    Returns:
        표준화된 선물 잔액 정보
    """
    if not response.get('success', False):
        return {
            'amount': 0,
            'currency': 'USDT',
            'type': 'future',
            'error': response.get('message', '알 수 없는 오류')
        }
    
    usdt_balance = response.get('usdt_balance', 0)
    return {
        'amount': usdt_balance,
        'currency': 'USDT',
        'type': 'future'
    }


def create_standardized_balance_response(spot_data: Dict[str, Any], future_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    표준화된 잔액 응답 생성
    
    Args:
        spot_data: 현물 계정 정보
        future_data: 선물 계정 정보
        
    Returns:
        표준화된 응답 데이터
    """
    has_error = 'error' in spot_data or 'error' in future_data
    
    return {
        'success': not has_error,
        'balance': {
            'spot': spot_data,
            'future': future_data,
            'total_usdt': spot_data.get('amount', 0) + future_data.get('amount', 0)
        },
        'error': {
            'spot': spot_data.get('error') if 'error' in spot_data else None,
            'future': future_data.get('error') if 'error' in future_data else None
        } if has_error else None,
        'timestamp': int(time.time())
    }


def get_formatted_balances(api_key: str, api_secret: str, retries: int = 1) -> Dict[str, Any]:
    """
    표준화된 형식의 잔액 정보를 조회하는 통합 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        retries: 재시도 횟수
        
    Returns:
        표준화된 형식의 잔액 정보
    """
    try:
        # 현물 및 선물 데이터 조회
        all_balances = get_all_balances(api_key, api_secret, retries)
        
        # 표준화된 응답 생성
        return create_standardized_balance_response(
            all_balances.get('spot', {}),
            all_balances.get('future', {})
        )
    except Exception as e:
        logger.error(f"잔액 정보 조회 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        # 오류 발생시 빈 응답 반환
        return create_standardized_balance_response({}, {})


# ==========================================================================
# 주문 관리 함수
# ==========================================================================

def create_order(api_key: str, api_secret: str, symbol: str, order_type: str, 
                 side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
    """
    바이낸스에 주문을 생성하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (예: 'BTC/USDT')
        order_type: 주문 유형 ('limit', 'market')
        side: 매수/매도 방향 ('buy', 'sell')
        amount: 주문 수량
        price: 주문 가격 (limit 주문일 경우에만 필요)
        
    Returns:
        주문 생성 결과를 포함한 딕셔너리
    """
    try:
        # 선물 거래 클라이언트 생성
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 주문 파라미터 설정
        params = {}
        
        # 주문 생성
        response = client.create_order(symbol, order_type, side, amount, price, params)
        
        # 응답 검증
        if not response or 'id' not in response:
            raise ValueError("주문 생성 실패: 응답에 주문 ID가 없습니다")
            
        logger.info(f"주문 생성 성공: {symbol}, {side}, {amount}, {price}")
        return {
            'success': True,
            'order_id': response.get('id'),
            'client_order_id': response.get('clientOrderId'),
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'price': price,
            'amount': amount,
            'status': response.get('status', 'unknown'),
            'raw_response': response
        }
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"주문 생성 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'price': price,
            'amount': amount
        }


def get_open_orders(api_key: str, api_secret: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    미체결 주문 목록을 조회하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (선택적, None일 경우 모든 심볼 조회)
        
    Returns:
        미체결 주문 목록
    """
    try:
        # 선물 거래 클라이언트 생성
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 미체결 주문 조회
        orders = client.fetch_open_orders(symbol)
        
        # 응답 검증 및 표준화
        standardized_orders = []
        for order in orders:
            if not order or 'id' not in order:
                logger.warning(f"유효하지 않은 주문 데이터 발견: {order}")
                continue
                
            standardized_orders.append({
                'order_id': order.get('id'),
                'client_order_id': order.get('clientOrderId'),
                'symbol': order.get('symbol'),
                'type': order.get('type'),
                'side': order.get('side'),
                'price': order.get('price'),
                'amount': order.get('amount'),
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'status': order.get('status', 'unknown'),
                'timestamp': order.get('timestamp'),
                'datetime': order.get('datetime'),
                'raw_data': order
            })
        
        logger.info(f"미체결 주문 조회 성공: {len(standardized_orders)}개 주문 발견")
        return standardized_orders
    except Exception as e:
        logger.error(f"미체결 주문 조회 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return []


def cancel_order(api_key: str, api_secret: str, order_id: str, symbol: str) -> Dict[str, Any]:
    """
    특정 주문을 취소하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        order_id: 취소할 주문 ID
        symbol: 주문 심볼
        
    Returns:
        주문 취소 결과를 포함한 딕셔너리
    """
    try:
        # 선물 거래 클라이언트 생성
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 주문 취소
        response = client.cancel_order(id=order_id, symbol=symbol)
        
        # 응답 검증
        if not response or 'id' not in response:
            raise ValueError("주문 취소 실패: 응답에 주문 ID가 없습니다")
            
        logger.info(f"주문 취소 성공: {symbol}, {order_id}")
        return {
            'success': True,
            'order_id': response.get('id'),
            'client_order_id': response.get('clientOrderId'),
            'symbol': symbol,
            'status': response.get('status', 'canceled'),
            'raw_response': response
        }
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"주문 취소 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'order_id': order_id,
            'symbol': symbol
        }


# ==========================================================================
# 포지션 관리 함수
# ==========================================================================

def get_positions(api_key: str, api_secret: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    현재 열린 포지션 정보를 조회하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 특정 심볼에 대한 포지션만 조회할 경우 지정 (옵션)
        
    Returns:
        포지션 목록 (표준화된 형식)
    """
    try:
        # 선물 거래 클라이언트 생성
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 포지션 조회
        positions = client.fetch_positions(symbol)
        
        # 실제 열린 포지션만 필터링 (포지션 크기가 0이 아닌 것들)
        active_positions = []
        for position in positions:
            # 필수 필드 검증
            if not position or 'info' not in position:
                logger.warning(f"유효하지 않은 포지션 데이터: {position}")
                continue
            
            # 포지션 크기가 0이 아닌 것만 추가
            if abs(float(position.get('contracts', 0))) > 0:
                # 표준화된 형식으로 변환
                standardized_position = {
                    'symbol': position.get('symbol'),
                    'side': position.get('side'),
                    'notional': float(position.get('notional', 0)),
                    'contracts': float(position.get('contracts', 0)),
                    'entry_price': float(position.get('entryPrice', 0)),
                    'mark_price': float(position.get('markPrice', 0)),
                    'liquidation_price': float(position.get('liquidationPrice', 0)),
                    'unrealized_pnl': float(position.get('unrealizedPnl', 0)),
                    'margin_mode': position.get('marginMode', 'cross'),
                    'leverage': int(position.get('leverage', 1)),
                    'raw_data': position
                }
                active_positions.append(standardized_position)
        
        logger.info(f"포지션 조회 성공: {len(active_positions)}개 활성 포지션 발견")
        return active_positions
    except Exception as e:
        logger.error(f"포지션 조회 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return []


def set_stop_loss_take_profit(api_key: str, api_secret: str, symbol: str, 
                             stop_loss: Optional[float] = None,
                             take_profit: Optional[float] = None,
                             position_side: str = 'BOTH') -> Dict[str, Any]:
    """
    특정 포지션에 손절 및 이익실현 가격 설정
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (예: 'BTC/USDT')
        stop_loss: 손절 가격 (옵션)
        take_profit: 이익실현 가격 (옵션)
        position_side: 포지션 방향 ('LONG', 'SHORT', 'BOTH')
        
    Returns:
        설정 결과를 포함한 딕셔너리
    """
    try:
        # 선물 거래 클라이언트 생성
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 현재 포지션 정보 조회
        position = None
        positions = get_positions(api_key, api_secret, symbol)
        
        for pos in positions:
            if pos['symbol'] == symbol:
                position = pos
                break
                
        if not position or abs(float(position.get('contracts', 0))) <= 0:
            return {
                'success': False,
                'message': f"{symbol}에 대한 활성 포지션이 없습니다",
                'error_code': 'NO_ACTIVE_POSITION'
            }
        
        # 주문 설정
        result = {'success': True, 'message': [], 'orders': []}
        
        # 손절 주문 설정
        if stop_loss:
            try:
                side = "sell" if position['side'] == "long" else "buy"
                stop_params = {'stopPrice': stop_loss, 'type': 'STOP_MARKET'}
                
                stop_order = client.create_order(
                    symbol=symbol,
                    type='stop',
                    side=side,
                    amount=abs(position['contracts']),
                    price=None,
                    params=stop_params
                )
                
                result['orders'].append({
                    'type': 'stop_loss',
                    'order_id': stop_order.get('id'),
                    'price': stop_loss
                })
                result['message'].append(f"손절가 {stop_loss}로 설정됨")
                
            except Exception as stop_err:
                logger.error(f"손절 주문 설정 실패: {str(stop_err)}")
                result['stop_loss_error'] = str(stop_err)
        
        # 이익실현 주문 설정
        if take_profit:
            try:
                side = "sell" if position['side'] == "long" else "buy"
                take_profit_params = {'stopPrice': take_profit, 'type': 'TAKE_PROFIT_MARKET'}
                
                tp_order = client.create_order(
                    symbol=symbol,
                    type='take_profit',
                    side=side,
                    amount=abs(position['contracts']),
                    price=None,
                    params=take_profit_params
                )
                
                result['orders'].append({
                    'type': 'take_profit',
                    'order_id': tp_order.get('id'),
                    'price': take_profit
                })
                result['message'].append(f"이익실현가 {take_profit}로 설정됨")
                
            except Exception as tp_err:
                logger.error(f"이익실현 주문 설정 실패: {str(tp_err)}")
                result['take_profit_error'] = str(tp_err)
        
        # 결과 반환
        if result['message']:
            result['message'] = ', '.join(result['message'])
        else:
            result['message'] = "변경된 설정이 없습니다"
            result['success'] = False
            
        logger.info(f"{symbol} 포지션 손절/이익실현 설정 완료: {result['message']}")
        return result
        
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"손절/이익실현 설정 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'symbol': symbol
        }


# ==========================================================================
# 시장 데이터 관리 함수
# ==========================================================================

def get_ticker(api_key: str, api_secret: str, symbol: str) -> Dict[str, Any]:
    """
    특정 심볼의 현재 시세 정보를 조회하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (예: 'BTC/USDT')
        
    Returns:
        표준화된 티커 정보
    """
    try:
        # 거래 클라이언트 생성 - 기본적으로 선물 클라이언트 사용
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 시세 정보 조회
        ticker = client.fetch_ticker(symbol)
        
        # 필수 필드 검증
        if not ticker or 'last' not in ticker:
            raise ValueError(f"{symbol} 심볼의 티커 정보를 가져올 수 없습니다")
        
        # 표준화된 티커 정보 구성
        standardized_ticker = {
            'symbol': symbol,
            'last': ticker.get('last', 0),
            'bid': ticker.get('bid', 0),
            'ask': ticker.get('ask', 0),
            'high': ticker.get('high', 0),
            'low': ticker.get('low', 0),
            'volume': ticker.get('volume', 0),
            'change': ticker.get('change', 0),
            'percentage': ticker.get('percentage', 0),
            'timestamp': ticker.get('timestamp', 0),
            'datetime': ticker.get('datetime', ''),
            'success': True
        }
        
        logger.info(f"{symbol} 티커 정보 조회 성공: 현재가 {standardized_ticker['last']}")
        return standardized_ticker
        
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"{symbol} 티커 조회 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'symbol': symbol
        }


def get_orderbook(api_key: str, api_secret: str, symbol: str, limit: int = 20) -> Dict[str, Any]:
    """
    특정 심볼의 호가창(주문창) 정보를 조회하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (예: 'BTC/USDT')
        limit: 주문창 깊이 (최대 회수)
        
    Returns:
        표준화된 주문창 정보
    """
    try:
        # 거래 클라이언트 생성 - 기본적으로 선물 클라이언트 사용
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 주문창 정보 조회
        orderbook = client.fetch_order_book(symbol, limit)
        
        # 필수 필드 검증
        if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
            raise ValueError(f"{symbol} 심볼의 호가창 정보를 가져올 수 없습니다")
        
        # 표준화된 호가창 정보 구성
        standardized_orderbook = {
            'symbol': symbol,
            'timestamp': orderbook.get('timestamp', 0),
            'datetime': orderbook.get('datetime', ''),
            'bids': orderbook.get('bids', []),  # [[price, amount], ...]
            'asks': orderbook.get('asks', []),  # [[price, amount], ...]
            'bid': orderbook.get('bids', [[0, 0]])[0][0] if len(orderbook.get('bids', [])) > 0 else 0,
            'ask': orderbook.get('asks', [[0, 0]])[0][0] if len(orderbook.get('asks', [])) > 0 else 0,
            'bid_volume': sum(amount for _, amount in orderbook.get('bids', [])),
            'ask_volume': sum(amount for _, amount in orderbook.get('asks', [])),
            'spread': orderbook.get('asks', [[0, 0]])[0][0] - orderbook.get('bids', [[0, 0]])[0][0] if \
                     len(orderbook.get('asks', [])) > 0 and len(orderbook.get('bids', [])) > 0 else 0,
            'spread_percentage': ((orderbook.get('asks', [[0, 0]])[0][0] / orderbook.get('bids', [[0, 0]])[0][0]) - 1.0) * 100 \
                                 if len(orderbook.get('asks', [])) > 0 and len(orderbook.get('bids', [])) > 0 and \
                                    orderbook.get('bids', [[0, 0]])[0][0] > 0 else 0,
            'nonce': orderbook.get('nonce', None),
            'success': True
        }
        
        logger.info(f"{symbol} 호가창 정보 조회 성공: 최상단 매수({standardized_orderbook['bid']}), 최상단 매도({standardized_orderbook['ask']})")
        return standardized_orderbook
        
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"{symbol} 호가창 조회 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'symbol': symbol
        }


def get_ohlcv(api_key: str, api_secret: str, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict[str, Any]:
    """
    특정 심볼의 OHLCV(봉 데이터) 정보를 조회하는 함수
    
    Args:
        api_key: 바이낸스 API 키
        api_secret: 바이낸스 API 시크릿
        symbol: 거래 심볼 (예: 'BTC/USDT')
        timeframe: 시간 프레임 ('1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M' 등)
        limit: 최대 가져올 개수
        
    Returns:
        표준화된 OHLCV 데이터
    """
    try:
        # 거래 클라이언트 생성 - 기본적으로 선물 클라이언트 사용
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # 유효한 시간 프레임 확인
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        if timeframe not in valid_timeframes:
            raise ValueError(f"유효하지 않은 시간 프레임: {timeframe}. 유효한 값: {', '.join(valid_timeframes)}")
        
        # OHLCV 데이터 조회
        ohlcv = client.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        # 필수 필드 검증
        if not ohlcv or len(ohlcv) == 0:
            raise ValueError(f"{symbol} 심볼의 OHLCV 데이터를 가져올 수 없습니다")
        
        # 데이터 변환 - Binance API는 [timestamp, open, high, low, close, volume] 형태로 반환
        formatted_ohlcv = []
        for candle in ohlcv:
            formatted_ohlcv.append({
                'timestamp': candle[0],
                'datetime': datetime.fromtimestamp(candle[0]/1000.0).isoformat(),
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5]
            })
        
        # 표준화된 OHLCV 정보 구성
        standardized_ohlcv = {
            'symbol': symbol,
            'timeframe': timeframe,
            'data': formatted_ohlcv,
            'length': len(formatted_ohlcv),
            'success': True,
            'last_update': int(time.time() * 1000)  # 현재 시간(ms)
        }
        
        logger.info(f"{symbol} OHLCV 데이터 조회 성공: {timeframe} 시간프레임, {len(formatted_ohlcv)} 개 가져옴")
        return standardized_ohlcv
        
    except Exception as e:
        error_response = handle_api_error(e)
        logger.error(f"{symbol} OHLCV 데이터 조회 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e),
            'error_code': error_response.get('error_code'),
            'message': error_response.get('message'),
            'symbol': symbol,
            'timeframe': timeframe
        }
