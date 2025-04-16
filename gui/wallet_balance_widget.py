"""
지갑 잔액 표시 위젯
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QComboBox
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
        
        # 마켓 타입 선택 (Spot/Futures)
        self.market_type_layout = QHBoxLayout()
        self.market_type_label = QLabel("마켓 타입:")
        self.market_type_combo = QComboBox()
        self.market_type_combo.addItems(["Spot", "Futures"])
        self.market_type_combo.currentIndexChanged.connect(self.on_market_type_changed)
        
        self.market_type_layout.addWidget(self.market_type_label)
        self.market_type_layout.addWidget(self.market_type_combo)
        self.market_type_layout.addStretch()
        
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
        self.balance_table = QTableWidget(0, 4)  # 행, 열 (4열로 변경)
        self.balance_table.setHorizontalHeaderLabels(["코인", "사용 가능", "총 잔액", "레버리지/유형"])
        self.balance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 테이블 높이 설정 - 코인 리스트를 더 많이 표시하기 위해 높이 증가
        self.balance_table.setMinimumHeight(300)  # 최소 높이 300픽셀로 설정
        
        # 수직 확장 정책 설정
        from PyQt5.QtWidgets import QSizePolicy
        self.balance_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 레이아웃 배치
        group_layout.addLayout(self.market_type_layout)  # 마켓 타입 선택 UI 추가
        group_layout.addLayout(self.status_layout)
        group_layout.addWidget(self.balance_table)
        
        self.group_box.setLayout(group_layout)
        layout.addWidget(self.group_box)
        
        self.setLayout(layout)
    
    def set_api(self, exchange_id, api_key, api_secret, symbol="BTC/USDT", market_type=None):
        """API 설정"""
        try:
            # 마켓 타입이 설정되었으면 사용, 아니면 현재 선택된 값 사용
            if market_type is None:
                market_type = 'futures' if self.market_type_combo.currentIndex() == 1 else 'spot'
            
            self.api = ExchangeAPI(
                exchange_id=exchange_id, 
                symbol=symbol,
                market_type=market_type
            )
            
            # API 키 유효성 확인
            if not (api_key and api_secret):
                self.connection_status.setText("연결 상태: API 키 누락")
                self.connection_status.setStyleSheet("color: red;")
                return False
            
            # 여기서 직접 API 객체 설정
            self.api.exchange.apiKey = api_key
            self.api.exchange.secret = api_secret
            
            # 마켓 타입 콤보박스 업데이트
            index = 1 if market_type == 'futures' else 0
            self.market_type_combo.setCurrentIndex(index)
            
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
                    
                    # 레버리지/마켓 유형 정보
                    market_type = self.api.market_type
                    leverage = self.api.leverage if market_type == 'futures' else 1
                    
                    if market_type == 'futures':
                        info_item = QTableWidgetItem(f"{leverage}x (Futures)")
                    else:
                        info_item = QTableWidgetItem("Spot")
                    info_item.setTextAlignment(Qt.AlignCenter)
                    self.balance_table.setItem(row, 3, info_item)
                    
                    row += 1
            
            self.balance_table.sortItems(0, Qt.AscendingOrder)
            
            # 마켓 유형 표시 업데이트
            market_type = self.api.market_type
            leverage = self.api.leverage if market_type == 'futures' else 1
            market_text = "Spot" if market_type == 'spot' else f"Futures (레버리지: {leverage}x)"
            self.group_box.setTitle(f"지갑 잔액 ({market_text})")
        except Exception as e:
            self.connection_status.setText(f"잔액 조회 중 오류: {str(e)}")
            self.connection_status.setStyleSheet("color: red;")
    
    def on_market_type_changed(self):
        """마켓 타입 변경 핸들러"""
        market_type = self.market_type_combo.currentText().lower()
        self.api.market_type = market_type
        self.refresh_balance()
