"""
심볼 형식 변환 유틸리티
여러 파일에서 중복되는 심볼 변환 로직을 통합
"""

def format_symbol_for_exchange(symbol: str, exchange_id: str = 'binance', market_type: str = 'spot') -> str:
    """
    거래소별 심볼 형식으로 변환
    
    Args:
        symbol: 원본 심볼 (예: 'BTC/USDT' 또는 'BTCUSDT')
        exchange_id: 거래소 ID
        market_type: 시장 타입 ('spot' 또는 'futures')
    
    Returns:
        str: 변환된 심볼
    """
    # 먼저 통일된 형식으로 변환 (슬래시 포함)
    if '/' not in symbol:
        # BTCUSDT -> BTC/USDT 형식으로 변환
        if symbol.endswith('USDT'):
            symbol = symbol[:-4] + '/USDT'
        elif symbol.endswith('BTC'):
            symbol = symbol[:-3] + '/BTC'
        elif symbol.endswith('ETH'):
            symbol = symbol[:-3] + '/ETH'
        elif symbol.endswith('BNB'):
            symbol = symbol[:-3] + '/BNB'
    
    # 거래소별 형식으로 변환
    if exchange_id == 'binance':
        if market_type == 'futures':
            # Binance Futures는 슬래시 없는 형식 사용
            return symbol.replace('/', '')
        else:
            # Binance Spot은 슬래시 포함 형식 사용
            return symbol
    
    elif exchange_id == 'bithumb':
        # Bithumb은 언더스코어 사용
        return symbol.replace('/', '_')
    
    elif exchange_id == 'upbit':
        # Upbit은 대시 사용
        base, quote = symbol.split('/')
        return f"{quote}-{base}"
    
    else:
        # 기본값은 슬래시 포함 형식
        return symbol


def normalize_symbol(symbol: str) -> str:
    """
    심볼을 표준 형식(BTC/USDT)으로 정규화
    
    Args:
        symbol: 원본 심볼
    
    Returns:
        str: 정규화된 심볼
    """
    # 이미 슬래시가 있으면 그대로 반환
    if '/' in symbol:
        return symbol
    
    # 다양한 형식 처리
    if '_' in symbol:
        # BITHUMB 형식: BTC_KRW -> BTC/KRW
        return symbol.replace('_', '/')
    elif '-' in symbol:
        # UPBIT 형식: KRW-BTC -> BTC/KRW
        parts = symbol.split('-')
        if len(parts) == 2:
            return f"{parts[1]}/{parts[0]}"
    else:
        # BINANCE 형식: BTCUSDT -> BTC/USDT
        common_quotes = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB', 'KRW', 'USD']
        for quote in common_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
    
    # 변환할 수 없으면 원본 반환
    return symbol


def get_base_quote_currency(symbol: str) -> tuple:
    """
    심볼에서 기준 통화와 결제 통화 추출
    
    Args:
        symbol: 심볼 (다양한 형식 지원)
    
    Returns:
        tuple: (base_currency, quote_currency)
    """
    # 먼저 정규화
    normalized = normalize_symbol(symbol)
    
    if '/' in normalized:
        parts = normalized.split('/')
        if len(parts) == 2:
            return parts[0], parts[1]
    
    return symbol, 'USDT'  # 기본값
