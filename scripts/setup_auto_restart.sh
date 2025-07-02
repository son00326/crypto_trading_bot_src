#!/bin/bash
# 봇 자동 재시작 설정 스크립트

echo "Crypto Trading Bot 자동 재시작 설정"
echo "=================================="

# 스크립트 경로 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
AUTO_RESTART_SCRIPT="$PROJECT_DIR/web_app/auto_restart.py"

# Python 경로 확인
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo "❌ Python3가 설치되어 있지 않습니다."
    exit 1
fi

# 현재 사용자 확인
CURRENT_USER=$(whoami)

# systemd 서비스 파일 생성
SERVICE_FILE="/etc/systemd/system/crypto-bot-auto-restart.service"
SERVICE_CONTENT="[Unit]
Description=Crypto Trading Bot Auto Restart Service
After=network.target mysql.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment=\"PATH=/usr/bin:/usr/local/bin\"
ExecStart=$PYTHON_PATH $AUTO_RESTART_SCRIPT
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"

# 서비스 파일 생성 (sudo 필요)
echo "서비스 파일을 생성합니다..."
echo "$SERVICE_CONTENT" | sudo tee $SERVICE_FILE > /dev/null

# 권한 설정
sudo chmod 644 $SERVICE_FILE

# systemd 리로드
echo "systemd를 리로드합니다..."
sudo systemctl daemon-reload

# 서비스 활성화
echo "자동 시작을 활성화합니다..."
sudo systemctl enable crypto-bot-auto-restart

echo ""
echo "✅ 설정 완료!"
echo ""
echo "사용 가능한 명령어:"
echo "  - 서비스 시작: sudo systemctl start crypto-bot-auto-restart"
echo "  - 서비스 중지: sudo systemctl stop crypto-bot-auto-restart"
echo "  - 서비스 상태: sudo systemctl status crypto-bot-auto-restart"
echo "  - 로그 확인: sudo journalctl -u crypto-bot-auto-restart -f"
echo ""
echo "테스트:"
echo "  python3 $AUTO_RESTART_SCRIPT --check"
