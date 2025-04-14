"""
바이낸스 계정 잔액 조회 스크립트
"""

from src.exchange_api import ExchangeAPI

def check_balance():
    # 바이낸스 API 연결
    exchange = ExchangeAPI(exchange_id="binance", symbol="BTC/USDT")
    
    # 잔액 조회
    balance = exchange.get_balance()
    
    if balance:
        print("\n===== 바이낸스 계정 잔액 =====")
        
        # 사용 가능한 잔액 출력
        print("\n사용 가능한 잔액:")
        for currency, amount in balance['free'].items():
            if float(amount) > 0:
                print(f"{currency}: {amount}")
        
        # 사용 중인 잔액 출력
        print("\n사용 중인 잔액:")
        for currency, amount in balance['used'].items():
            if float(amount) > 0:
                print(f"{currency}: {amount}")
                
        # 총 잔액 출력
        print("\n총 잔액:")
        for currency, amount in balance['total'].items():
            if float(amount) > 0:
                print(f"{currency}: {amount}")
                
        print("\n=============================")
    else:
        print("잔액 조회에 실패했습니다. API 키를 확인하세요.")

if __name__ == "__main__":
    check_balance()
