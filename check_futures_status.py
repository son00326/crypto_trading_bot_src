#!/usr/bin/env python3
"""
선물거래 봇 현재 상태 점검 스크립트
"""

import os
import sys
import importlib.util

# 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_module_exists(module_path):
    """모듈 존재 여부 확인"""
    return os.path.exists(module_path)

def check_method_exists(module_path, class_name, method_name):
    """특정 클래스의 메서드 존재 여부 확인"""
    try:
        spec = importlib.util.spec_from_file_location("module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, class_name):
            cls = getattr(module, class_name)
            return hasattr(cls, method_name)
        return False
    except:
        return False

def main():
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}선물거래 봇 상태 점검{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    checks = []
    
    # 1. 핵심 파일 존재 확인
    print(f"\n{YELLOW}[1] 핵심 파일 확인{RESET}")
    core_files = [
        'src/trading_algorithm.py',
        'src/exchange_api.py',
        'src/auto_position_manager.py',
        'gui/crypto_trading_bot_gui_complete.py',
        'utils/api.py'
    ]
    
    for file in core_files:
        exists = check_module_exists(file)
        status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
        print(f"  {status} {file}")
        checks.append(('file', file, exists))
    
    # 2. TradingAlgorithm 메서드 확인
    print(f"\n{YELLOW}[2] TradingAlgorithm 필수 메서드{RESET}")
    ta_methods = [
        ('__init__', 'market_type 파라미터'),
        ('get_current_price', '현재가 조회'),
        ('get_open_positions', '포지션 조회'),
        ('close_position', '포지션 청산')
    ]
    
    for method, desc in ta_methods:
        exists = check_method_exists('src/trading_algorithm.py', 'TradingAlgorithm', method)
        status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
        print(f"  {status} {method}: {desc}")
        checks.append(('method', f'TradingAlgorithm.{method}', exists))
    
    # 3. ExchangeAPI 메서드 확인
    print(f"\n{YELLOW}[3] ExchangeAPI 선물거래 메서드{RESET}")
    ea_methods = [
        ('get_positions', '포지션 조회'),
        ('set_leverage', '레버리지 설정'),
        ('set_margin_mode', '마진 모드 설정')
    ]
    
    for method, desc in ea_methods:
        exists = check_method_exists('src/exchange_api.py', 'ExchangeAPI', method)
        status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
        print(f"  {status} {method}: {desc}")
        checks.append(('method', f'ExchangeAPI.{method}', exists))
    
    # 4. GUI 통합 확인
    print(f"\n{YELLOW}[4] GUI 통합 상태{RESET}")
    gui_checks = [
        ('BotThread.init_trading_algorithm에서 market_type 전달', 
         check_method_exists('gui/crypto_trading_bot_gui_complete.py', 'BotThread', 'init_trading_algorithm'))
    ]
    
    for desc, exists in gui_checks:
        status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
        print(f"  {status} {desc}")
        checks.append(('gui', desc, exists))
    
    # 5. 환경 설정 확인
    print(f"\n{YELLOW}[5] 환경 설정{RESET}")
    env_vars = [
        ('BINANCE_API_KEY', os.getenv('BINANCE_API_KEY') is not None),
        ('BINANCE_API_SECRET', os.getenv('BINANCE_API_SECRET') is not None)
    ]
    
    for var, exists in env_vars:
        status = f"{GREEN}✅{RESET}" if exists else f"{RED}❌{RESET}"
        masked = '***' if exists else 'Not Set'
        print(f"  {status} {var}: {masked}")
        checks.append(('env', var, exists))
    
    # 6. 데이터베이스 확인
    print(f"\n{YELLOW}[6] 데이터베이스{RESET}")
    db_path = 'trading_bot.db'
    db_exists = os.path.exists(db_path)
    status = f"{GREEN}✅{RESET}" if db_exists else f"{RED}❌{RESET}"
    print(f"  {status} {db_path}")
    checks.append(('db', db_path, db_exists))
    
    # 결과 요약
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}점검 결과 요약{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    total = len(checks)
    passed = sum(1 for _, _, result in checks if result)
    failed = total - passed
    
    print(f"\n전체: {passed}/{total} 통과")
    
    if failed > 0:
        print(f"\n{RED}실패 항목:{RESET}")
        for category, name, result in checks:
            if not result:
                print(f"  - [{category}] {name}")
    
    # EC2 배포 가능 여부
    critical_checks = [
        ('file', 'src/trading_algorithm.py', True),
        ('file', 'src/exchange_api.py', True),
        ('method', 'TradingAlgorithm.market_type 파라미터', True),
        ('method', 'ExchangeAPI.get_positions', True)
    ]
    
    critical_passed = all(
        check[2] for check in checks 
        if (check[0], check[1]) in [(c[0], c[1]) for c in critical_checks]
    )
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if critical_passed and passed >= total * 0.8:
        print(f"{GREEN}✅ EC2 배포 가능 상태입니다!{RESET}")
        print("\n배포 전 체크리스트:")
        print("1. .env 파일에 실제 API 키 설정")
        print("2. requirements.txt 확인")
        print("3. 선물거래 계정 활성화 및 API 권한 확인")
        print("4. 초기 레버리지 설정 확인")
    else:
        print(f"{RED}❌ 아직 EC2 배포 준비가 안되었습니다.{RESET}")
        print("위의 실패 항목들을 먼저 수정해주세요.")
    
    return passed == total

if __name__ == "__main__":
    main()
