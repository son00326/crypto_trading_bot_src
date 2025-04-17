# GUI에 지갑 잔액 표시 기능 추가 방법

아래는 `crypto_trading_bot_gui_complete.py` 파일을 수정하여 지갑 잔액 표시 기능을 추가하는 단계별 가이드입니다.

## 1. 임포트 섹션 수정

파일 상단의 임포트 섹션에 다음 추가:
```python
from gui.wallet_balance_widget import WalletBalanceWidget
```

## 2. GUI 클래스 수정

1. `__init__` 메서드에 지갑 위젯 인스턴스 추가:
```python
self.wallet_widget = WalletBalanceWidget()
```

2. API 설정 그룹 바로 아래에 지갑 위젯 추가:
```python
# API 설정 그룹을 설정한 후
api_group.setLayout(api_layout)

# 그 바로 다음에 지갑 위젯 추가 
# (settings_content_layout.addWidget(api_group) 바로 앞에 추가)
settings_content_layout.addWidget(api_group)
settings_content_layout.addWidget(self.wallet_widget)  # 이 줄 추가
```

3. 설정 저장 버튼 핸들러 수정:
```python
def save_settings(self):
    # 기존 코드...
    
    # API 설정 적용
    api_key = self.api_key_input.text()
    api_secret = self.api_secret_input.text()
    exchange = self.exchange_combo.currentText()
    
    # 환경 변수 저장
    os.environ['BINANCE_API_KEY'] = api_key
    os.environ['BINANCE_API_SECRET'] = api_secret
    
    # 지갑 API 설정 및 테스트
    connection_result = self.wallet_widget.set_api(
        exchange_id=exchange,
        api_key=api_key,
        api_secret=api_secret,
        symbol=self.symbol_input.text()
    )
    
    # 설정 저장 완료 메시지
    msg = QMessageBox()
    if connection_result:
        msg.setIcon(QMessageBox.Information)
        msg.setText("설정이 저장되었으며 API 연결에 성공했습니다.")
    else:
        msg.setIcon(QMessageBox.Warning)
        msg.setText("설정이 저장되었으나 API 연결에 실패했습니다. API 키를 확인하세요.")
    
    msg.setWindowTitle("설정 저장")
    msg.exec_()
```

## 3. 새로운 API 연결 테스트 함수 추가

```python
def check_api_connection(self):
    # API 키 가져오기
    api_key = self.api_key_input.text()
    api_secret = self.api_secret_input.text()
    exchange = self.exchange_combo.currentText()
    
    # 지갑 API 설정 및 테스트
    connection_result = self.wallet_widget.set_api(
        exchange_id=exchange,
        api_key=api_key,
        api_secret=api_secret,
        symbol=self.symbol_input.text()
    )
    
    # 연결 결과 메시지
    msg = QMessageBox()
    if connection_result:
        msg.setIcon(QMessageBox.Information)
        msg.setText("API 연결에 성공했습니다.")
    else:
        msg.setIcon(QMessageBox.Warning)
        msg.setText("API 연결에 실패했습니다. API 키를 확인하세요.")
    
    msg.setWindowTitle("API 연결 테스트")
    msg.exec_()
```

## 4. 기존 API 키가 있을 경우 자동 연결 코드 추가

`setup_ui` 메서드 끝부분에 다음 코드 추가:
```python
# API 키 설정 후 지갑 위젯 초기화
api_key = self.api_key_input.text()
api_secret = self.api_secret_input.text()
if api_key and api_secret:
    self.wallet_widget.set_api(
        exchange_id=self.exchange_combo.currentText(),
        api_key=api_key,
        api_secret=api_secret,
        symbol=self.symbol_input.text()
    )
```

## 수정 후 실행 방법

1. 위의 변경사항을 적용한 후에 GUI를 실행합니다.
2. API 키와 시크릿을 입력하고 "API 연결 확인" 버튼을 클릭합니다.
3. 연결이 성공하면 지갑 잔액이 표시됩니다.
4. "새로고침" 버튼을 클릭하여 언제든지 최신 잔액을 조회할 수 있습니다.
