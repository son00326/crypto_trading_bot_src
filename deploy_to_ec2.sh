#!/bin/bash

# EC2 서버 정보
EC2_HOST="52.76.43.91"
EC2_USER="ec2-user"
EC2_KEY="/Users/yong/Library/Mobile Documents/com~apple~CloudDocs/Personal/crypto-bot-key.pem"

echo "=== 크립토 트레이딩 봇 EC2 배포 스크립트 ==="
echo ""

# 1. 변경된 파일 업로드
echo "1. 변경된 파일 업로드 중..."

# SSH 키 권한 설정
chmod 400 "$EC2_KEY"

# 변경된 파일들 업로드
FILES_TO_UPLOAD=(
    "src/trading_algorithm.py"
    "src/db_manager.py" 
    "crypto_trading_bot_gui_complete.py"
)

for FILE in "${FILES_TO_UPLOAD[@]}"; do
    echo "   - $FILE 업로드 중..."
    scp -i "$EC2_KEY" "$FILE" "$EC2_USER@$EC2_HOST:~/crypto_trading_bot/$FILE"
done

echo ""
echo "2. EC2 서버에서 봇 재시작..."

# EC2 서버에서 명령 실행
ssh -i "$EC2_KEY" "$EC2_USER@$EC2_HOST" << 'EOF'
    echo "   - 현재 봇 상태 확인..."
    sudo systemctl status crypto-bot.service --no-pager
    
    echo ""
    echo "   - 봇 서비스 재시작..."
    sudo systemctl restart crypto-bot.service
    
    echo ""
    echo "   - 재시작 후 상태 확인..."
    sleep 5
    sudo systemctl status crypto-bot.service --no-pager
    
    echo ""
    echo "   - 최근 로그 확인..."
    sudo journalctl -u crypto-bot.service --no-pager -n 50
EOF

echo ""
echo "=== 배포 완료 ==="
echo ""
echo "웹 인터페이스 접속: http://$EC2_HOST:8080"
echo ""
