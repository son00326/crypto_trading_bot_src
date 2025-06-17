#!/usr/bin/env python3
"""
바이낸스 선물 API 엔드포인트 문제 수정 스크립트
"""

import os
import sys

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_api_endpoints():
    """utils/api.py의 바이낸스 API 엔드포인트 수정"""
    
    # utils/api.py 파일 경로
    api_file = os.path.join(os.path.dirname(__file__), 'utils', 'api.py')
    
    # 파일 읽기
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 수정 전 백업
    backup_file = api_file + '.backup'
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 백업 파일 생성: {backup_file}")
    
    # v1 엔드포인트를 v2로 수정
    original_line = 'exchange.fapiPrivateGetPositionrisk.__func__.__name__ = "fapiPrivateGetV2Positionrisk"'
    
    if original_line in content:
        print("❌ 기존 패치 방식이 발견되었습니다. 새로운 방식으로 수정합니다.")
        
        # 새로운 패치 방식으로 변경
        new_patch = '''
        # 바이낸스 선물 positionRisk 엔드포인트 v2로 패치
        # v1이 404를 반환하므로 v2 사용
        if hasattr(exchange, 'fapiPrivateGetPositionrisk'):
            # 원본 메서드 백업
            original_method = exchange.fapiPrivateGetPositionrisk
            
            # v2 엔드포인트를 사용하는 새 메서드 정의
            def patched_position_risk(params=None):
                if params is None:
                    params = {}
                # URL을 v2로 변경
                request = exchange.sign('fapi/v2/positionRisk', 'private', 'GET', params)
                return exchange.fetch(request['url'], request['method'], request['headers'], request['body'])
            
            # 메서드 교체
            exchange.fapiPrivateGetPositionrisk = patched_position_risk
            print("✅ 바이낸스 선물 positionRisk 엔드포인트가 v2로 패치되었습니다.")
        '''
        
        # 기존 패치 코드를 새로운 것으로 교체
        content = content.replace(
            '# positionRisk 엔드포인트를 v2로 패치\n        if hasattr(exchange, \'fapiPrivateGetPositionrisk\'):\n            exchange.fapiPrivateGetPositionrisk.__func__.__name__ = "fapiPrivateGetV2Positionrisk"',
            new_patch.strip()
        )
        
        # 파일 저장
        with open(api_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ utils/api.py가 수정되었습니다.")
        return True
    else:
        print("⚠️ 기존 패치 코드를 찾을 수 없습니다.")
        return False

if __name__ == "__main__":
    if fix_api_endpoints():
        print("\n✅ API 엔드포인트 수정 완료!")
        print("💡 이제 다시 테스트를 실행해보세요: python test_binance_futures.py")
    else:
        print("\n❌ API 엔드포인트 수정 실패!")
        print("💡 utils/api.py 파일을 직접 확인해보세요.")
