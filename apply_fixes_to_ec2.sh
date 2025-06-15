#!/bin/bash

# EC2 서버 정보
EC2_HOST="52.76.43.91"
EC2_USER="ec2-user"
EC2_KEY="/Users/yong/Library/Mobile Documents/com~apple~CloudDocs/Personal/crypto-bot-key.pem"

echo "=== 크립토 트레이딩 봇 긴급 수정사항 EC2 적용 ==="
echo ""

# SSH 키 권한 설정
chmod 400 "$EC2_KEY"

# 1. 변경된 파일 업로드
echo "1. 수정된 파일 업로드 중..."

# 중요 수정 파일들 업로드
echo "   - TradeSignal 모델 수정 (signal_type → direction)..."
scp -i "$EC2_KEY" src/models/trade_signal.py "$EC2_USER@$EC2_HOST:~/crypto_trading_bot/src/models/"

echo "   - API URL v2 업데이트..."
scp -i "$EC2_KEY" utils/api.py "$EC2_USER@$EC2_HOST:~/crypto_trading_bot/utils/"

echo "   - requirements.txt CCXT 버전 업데이트..."
scp -i "$EC2_KEY" requirements.txt "$EC2_USER@$EC2_HOST:~/crypto_trading_bot/"

echo ""
echo "2. EC2 서버에서 패키지 업데이트 및 봇 재시작..."

# EC2 서버에서 명령 실행
ssh -i "$EC2_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
cd ~/crypto_trading_bot

echo "패키지 업데이트 중..."
source venv/bin/activate
pip install --upgrade ccxt

echo ""
echo "서비스 재시작 중..."
sudo systemctl restart crypto-bot.service

echo ""
echo "서비스 상태 확인..."
sudo systemctl status crypto-bot.service --no-pager

echo ""
echo "최근 로그 확인..."
sudo journalctl -u crypto-bot.service --no-pager -n 20
ENDSSH

echo ""
echo "=== 완료! ==="
echo "브라우저에서 http://$EC2_HOST:8080 으로 접속하여 확인하세요."
