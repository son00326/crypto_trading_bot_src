#!/usr/bin/env python3
"""
로컬과 서버의 패키지 버전을 비교하는 스크립트
"""
import subprocess
import sys

def get_local_versions():
    """로컬 환경의 패키지 버전 가져오기"""
    result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], 
                          capture_output=True, text=True)
    return dict(line.split('==') for line in result.stdout.strip().split('\n') 
                if '==' in line)

def get_server_versions():
    """서버 환경의 패키지 버전 가져오기 (SSH 필요)"""
    cmd = 'ssh -i "/Users/yong/Library/Mobile Documents/com~apple~CloudDocs/Personal/crypto-bot-key.pem" ec2-user@52.76.43.91 "cd crypto_trading_bot && source venv/bin/activate && pip freeze"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    # SSH 배너 제거
    packages = [line for line in lines if '==' in line and not line.startswith((' ', '\t', '#'))]
    return dict(line.split('==') for line in packages)

def compare_versions():
    """버전 비교 및 리포트"""
    print("패키지 버전 비교 중...")
    
    local = get_local_versions()
    server = get_server_versions()
    
    # 주요 패키지 목록
    important_packages = ['ccxt', 'pandas', 'flask', 'numpy', 'matplotlib']
    
    print("\n=== 주요 패키지 버전 비교 ===")
    print(f"{'패키지':<15} {'로컬':<15} {'서버':<15} {'상태':<10}")
    print("-" * 55)
    
    for pkg in important_packages:
        local_ver = local.get(pkg, 'Not installed')
        server_ver = server.get(pkg, 'Not installed')
        status = '✅' if local_ver == server_ver else '❌'
        print(f"{pkg:<15} {local_ver:<15} {server_ver:<15} {status:<10}")
    
    # 버전 불일치 패키지 찾기
    print("\n=== 버전 불일치 패키지 ===")
    mismatches = []
    for pkg in set(local.keys()) | set(server.keys()):
        if pkg in local and pkg in server and local[pkg] != server[pkg]:
            mismatches.append((pkg, local[pkg], server[pkg]))
    
    if mismatches:
        for pkg, local_ver, server_ver in mismatches[:10]:  # 최대 10개만 표시
            print(f"{pkg}: 로컬={local_ver}, 서버={server_ver}")
    else:
        print("모든 패키지 버전이 일치합니다! ✅")

if __name__ == "__main__":
    compare_versions()
