#!/usr/bin/env python3
"""심볼 유틸리티 테스트"""

from src.utils.symbol_utils import (
    normalize_symbol, convert_symbol_format, 
    get_base_quote_assets, validate_symbol_format
)

print("=== 심볼 유틸리티 테스트 ===\n")

# 1. normalize_symbol 테스트
print("1. normalize_symbol 테스트:")
test_symbols = ['BTC/USDT', 'BTCUSDT', 'BTC-USDT', 'btcusdt', 'BTC:USDT']
for symbol in test_symbols:
    normalized = normalize_symbol(symbol, 'binance', 'futures')
    print(f"  {symbol} -> {normalized}")

print("\n2. convert_symbol_format 테스트:")
# 2. convert_symbol_format 테스트
test_cases = [
    ('BTC/USDT', 'standard', 'exchange', 'binance', 'futures'),
    ('BTCUSDT', 'exchange', 'standard', 'binance', 'futures'),
    ('BTC/USDT', 'standard', 'exchange', 'binance', 'spot'),
    ('ETHUSDT', 'exchange', 'standard', 'binance', 'spot'),
]

for symbol, from_fmt, to_fmt, exchange, market in test_cases:
    converted = convert_symbol_format(symbol, from_fmt, to_fmt, exchange, market)
    print(f"  {symbol} ({from_fmt} -> {to_fmt}, {exchange} {market}): {converted}")

print("\n3. get_base_quote_assets 테스트:")
# 3. get_base_quote_assets 테스트
test_symbols = ['BTC/USDT', 'BTCUSDT', 'ETHBTC', 'ETH/BTC']
for symbol in test_symbols:
    base, quote = get_base_quote_assets(symbol)
    print(f"  {symbol} -> base: {base}, quote: {quote}")

print("\n4. validate_symbol_format 테스트:")
# 4. validate_symbol_format 테스트
test_cases = [
    ('BTCUSDT', 'binance', 'futures'),
    ('BTC/USDT', 'binance', 'futures'),
    ('btcusdt', 'binance', 'futures'),
    ('BTCUSDT', 'binance', 'spot'),
    ('BTC/USDT', 'binance', 'spot'),
]

for symbol, exchange, market in test_cases:
    is_valid, error = validate_symbol_format(symbol, exchange, market)
    status = "✓" if is_valid else "✗"
    print(f"  {status} {symbol} ({exchange} {market}): {error if error else 'Valid'}")

print("\n=== 테스트 완료 ===")
