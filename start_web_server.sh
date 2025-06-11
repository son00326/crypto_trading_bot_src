#!/bin/bash
# 웹 서버 실행 스크립트
cd "$(dirname "$0")/web_app"

# 현재 작업 디렉토리 출력
echo "현재 작업 디렉토리: $(pwd)"

# Python 실행 경로 확인
which python

# 서버 시작
python bot_api_server.py
