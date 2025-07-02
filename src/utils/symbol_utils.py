"""
심볼 형식 변환 유틸리티 모듈
암호화폐 거래에서 사용되는 다양한 심볼 형식 간 변환을 담당합니다.
"""

import logging

logger = logging.getLogger('symbol_utils')

def normalize_symbol(symbol, exchange_id='binance', market_type='spot'):
    """
    심볼을 표준 형식으로 정규화
    
    Args:
        symbol (str): 원본 심볼 (예: 'BTC/USDT', 'BTCUSDT', 'BTC-USDT')
        exchange_id (str): 거래소 ID
        market_type (str): 시장 타입 ('spot' 또는 'futures')
        
    Returns:
        str: 표준화된 심볼 형식
    """
    if not symbol:
        return symbol
        
    # 바이낸스 선물의 경우
    if exchange_id == 'binance' and market_type == 'futures':
        # 모든 구분자 제거
        normalized = symbol.replace('/', '').replace('-', '').replace('_', '')
        
        # ':USDT' 같은 suffix 제거
        if ':' in normalized:
            normalized = normalized.split(':')[0]
            
        # 대문자로 변환
        normalized = normalized.upper()
        
        return normalized
    
    # 바이낸스 현물의 경우
    elif exchange_id == 'binance' and market_type == 'spot':
        # '/' 포함 형식으로 통일
        if '/' not in symbol:
            # BTCUSDT -> BTC/USDT
            if 'USDT' in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT"
            elif 'BTC' in symbol and symbol.endswith('BTC'):
                base = symbol.replace('BTC', '')
                return f"{base}/BTC"
            elif 'ETH' in symbol and symbol.endswith('ETH'):
                base = symbol.replace('ETH', '')
                return f"{base}/ETH"
        return symbol
    
    # 기타 거래소는 원본 그대로
    return symbol

def convert_symbol_format(symbol, from_format='standard', to_format='exchange', 
                         exchange_id='binance', market_type='spot'):
    """
    심볼 형식을 변환
    
    Args:
        symbol (str): 변환할 심볼
        from_format (str): 원본 형식 ('standard' 또는 'exchange')
        to_format (str): 대상 형식 ('standard' 또는 'exchange')
        exchange_id (str): 거래소 ID
        market_type (str): 시장 타입
        
    Returns:
        str: 변환된 심볼
    """
    if from_format == to_format:
        return symbol
        
    # standard (BTC/USDT) -> exchange 형식
    if from_format == 'standard' and to_format == 'exchange':
        if exchange_id == 'binance' and market_type == 'futures':
            # BTC/USDT -> BTCUSDT
            return symbol.replace('/', '')
        elif exchange_id == 'binance' and market_type == 'spot':
            # 바이낸스 현물도 '/' 제거
            return symbol.replace('/', '')
            
    # exchange 형식 -> standard (BTC/USDT)
    elif from_format == 'exchange' and to_format == 'standard':
        if exchange_id == 'binance':
            # BTCUSDT -> BTC/USDT
            if 'USDT' in symbol and '/' not in symbol:
                base = symbol.replace('USDT', '')
                return f"{base}/USDT"
            elif 'BTC' in symbol and symbol.endswith('BTC'):
                base = symbol.replace('BTC', '')
                return f"{base}/BTC"
                
    return symbol

def get_base_quote_assets(symbol):
    """
    심볼에서 기본 자산과 견적 자산 추출
    
    Args:
        symbol (str): 심볼 (예: 'BTC/USDT', 'BTCUSDT')
        
    Returns:
        tuple: (base_asset, quote_asset)
    """
    # '/' 구분자가 있는 경우
    if '/' in symbol:
        parts = symbol.split('/')
        if len(parts) == 2:
            return parts[0], parts[1]
    
    # 구분자가 없는 경우 일반적인 quote 자산들로 파싱 시도
    common_quotes = ['USDT', 'USDC', 'BUSD', 'BTC', 'ETH', 'BNB']
    
    for quote in common_quotes:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            if base:  # 빈 문자열이 아닌 경우만
                return base, quote
                
    # 파싱 실패
    logger.warning(f"심볼 파싱 실패: {symbol}")
    return None, None

def validate_symbol_format(symbol, exchange_id='binance', market_type='spot'):
    """
    심볼 형식이 올바른지 검증
    
    Args:
        symbol (str): 검증할 심볼
        exchange_id (str): 거래소 ID
        market_type (str): 시장 타입
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not symbol:
        return False, "심볼이 비어있습니다"
        
    # 바이낸스 선물
    if exchange_id == 'binance' and market_type == 'futures':
        # '/' 가 없어야 함
        if '/' in symbol:
            return False, "바이낸스 선물 심볼에는 '/'가 포함되면 안됩니다"
        # 대문자여야 함
        if symbol != symbol.upper():
            return False, "심볼은 대문자여야 합니다"
        # 기본/견적 자산 파싱 가능해야 함
        base, quote = get_base_quote_assets(symbol)
        if not base or not quote:
            return False, "유효하지 않은 심볼 형식입니다"
            
    # 바이낸스 현물
    elif exchange_id == 'binance' and market_type == 'spot':
        # 대문자여야 함
        if '/' in symbol:
            parts = symbol.split('/')
            for part in parts:
                if part != part.upper():
                    return False, "심볼은 대문자여야 합니다"
        else:
            if symbol != symbol.upper():
                return False, "심볼은 대문자여야 합니다"
                
    return True, ""
