#!/bin/bash
# 암호화폐 트레이딩 봇 웹 인터페이스 실행 스크립트

# 스크립트가 위치한 디렉토리로 이동
cd "$(dirname "$0")"

# 환경 변수 출력 (디버그용)
echo "현재 작업 디렉토리: $(pwd)"

# 웹 서버 실행
python3 web_app/app.py
