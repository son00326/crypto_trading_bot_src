"""
지갑 잔액 표시 위젯
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from src.exchange_api import ExchangeAPI


class WalletBalanceWidget(QWidget):
    """바이낸스 지갑 잔액을 표시하는 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = None
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout()
        
        # 그룹박스
        self.group_box = QGroupBox("지갑 잔액")
        group_layout = QVBoxLayout()
        
        # 연결 상태 표시
        self.status_layout = QHBoxLayout()
        self.connection_status = QLabel("연결 상태: 연결되지 않음")
        self.connection_status.setStyleSheet("color: red;")
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.refresh_balance)
        
        self.status_layout.addWidget(self.connection_status)
        self.status_layout.addStretch()
        self.status_layout.addWidget(self.refresh_button)
        
        # 잔액 테이블
        self.balance_table = QTableWidget(0, 3)  # 행, 열
        self.balance_table.setHorizontalHeaderLabels(["코인", "사용 가능", "총 잔액"])
        self.balance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 레이아웃 배치
        group_layout.addLayout(self.status_layout)
        group_layout.addWidget(self.balance_table)
        
        self.group_box.setLayout(group_layout)
        layout.addWidget(self.group_box)
        
        self.setLayout(layout)
    
    def set_api(self, exchange_id, api_key, api_secret, symbol="BTC/USDT"):
        """API 설정"""
        try:
            self.api = ExchangeAPI(
                exchange_id=exchange_id, 
                symbol=symbol
            )
            
            # API 키 유효성 확인
            if not (api_key and api_secret):
                self.connection_status.setText("연결 상태: API 키 누락")
                self.connection_status.setStyleSheet("color: red;")
                return False
            
            # 여기서 직접 API 객체 설정
            self.api.exchange.apiKey = api_key
            self.api.exchange.secret = api_secret
            
            # 연결 테스트
            result = self.test_connection()
            return result
            
        except Exception as e:
            self.connection_status.setText(f"연결 상태: 오류 - {str(e)}")
            self.connection_status.setStyleSheet("color: red;")
            return False
    
    def test_connection(self):
        """API 연결 테스트"""
        try:
            if not self.api:
                self.connection_status.setText("연결 상태: API 설정 필요")
                self.connection_status.setStyleSheet("color: red;")
                return False
            
            # 간단한 API 호출로 테스트
            balance = self.api.get_balance()
            
            if balance:
                self.connection_status.setText("연결 상태: 연결됨")
                self.connection_status.setStyleSheet("color: green;")
                self.refresh_balance()
                return True
            else:
                self.connection_status.setText("연결 상태: 연결 실패")
                self.connection_status.setStyleSheet("color: red;")
                return False
                
        except Exception as e:
            self.connection_status.setText(f"연결 상태: 오류 - {str(e)}")
            self.connection_status.setStyleSheet("color: red;")
            return False
    
    def refresh_balance(self):
        """잔액 새로고침"""
        try:
            if not self.api:
                self.connection_status.setText("연결 상태: API 설정 필요")
                self.connection_status.setStyleSheet("color: red;")
                return
            
            balance = self.api.get_balance()
            if not balance:
                self.connection_status.setText("연결 상태: 잔액 조회 실패")
                self.connection_status.setStyleSheet("color: red;")
                return
            
            # 테이블 초기화
            self.balance_table.setRowCount(0)
            
            # 잔액이 0보다 큰 항목만 표시
            row = 0
            for currency in balance['total']:
                total_amount = float(balance['total'][currency])
                free_amount = float(balance['free'][currency])
                
                if total_amount > 0:
                    self.balance_table.insertRow(row)
                    
                    # 코인명
                    coin_item = QTableWidgetItem(currency)
                    self.balance_table.setItem(row, 0, coin_item)
                    
                    # 사용 가능 잔액
                    free_item = QTableWidgetItem(f"{free_amount:.8f}")
                    free_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.balance_table.setItem(row, 1, free_item)
                    
                    # 총 잔액
                    total_item = QTableWidgetItem(f"{total_amount:.8f}")
                    total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.balance_table.setItem(row, 2, total_item)
                    
                    row += 1
            
            self.balance_table.sortItems(0, Qt.AscendingOrder)
            
        except Exception as e:
            self.connection_status.setText(f"새로고침 오류: {str(e)}")
            self.connection_status.setStyleSheet("color: red;")
