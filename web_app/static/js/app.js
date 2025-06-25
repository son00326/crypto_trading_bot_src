// 암호화폐 자동 매매 봇 웹 애플리케이션 JavaScript

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 봇 상태 로드
    updateBotStatus();
    
    // 5초마다 상태 업데이트
    setInterval(updateBotStatus, 5000);
    
    // 이벤트 리스너 등록
    document.getElementById('start-bot-btn').addEventListener('click', startBot);
    document.getElementById('stop-bot-btn').addEventListener('click', stopBot);
    
    // 마켓 타입 변경 이벤트 리스너
    document.getElementById('market-type').addEventListener('change', updateMarketTypeUI);
    
    // 레인지 슬라이더 값 표시 업데이트
    document.getElementById('leverage').addEventListener('input', updateLeverageValue);
    document.getElementById('stop-loss').addEventListener('input', updateStopLossValue);
    document.getElementById('take-profit').addEventListener('input', updateTakeProfitValue);
    document.getElementById('max-position').addEventListener('input', updateMaxPositionValue);
    
    // 자동 손절매/이익실현 체크박스 상태 변경 이벤트
    document.getElementById('auto-sl-tp').addEventListener('change', function() {
        // 부분 청산 체크박스 활성화/비활성화
        document.getElementById('partial-tp').disabled = !this.checked;
        
        // 체크 해제되면 부분 청산 해제
        if (!this.checked) {
            document.getElementById('partial-tp').checked = false;
        }
    });
    
    // 초기 UI 설정
    updateMarketTypeUI();
});

// 폼 초기화 여부 추적
let formInitialized = false;

// 봇 상태 업데이트
function updateBotStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            // 봇 상태 업데이트
            const statusElement = document.getElementById('bot-status');
            if (data.status === 'running') {
                statusElement.textContent = '실행 중';
                statusElement.className = 'badge bg-success';
                document.getElementById('start-bot-btn').disabled = true;
                document.getElementById('stop-bot-btn').disabled = false;
            } else {
                statusElement.textContent = '중지됨';
                statusElement.className = 'badge bg-secondary';
                document.getElementById('start-bot-btn').disabled = false;
                document.getElementById('stop-bot-btn').disabled = true;
            }
            
            // 기본 정보 업데이트
            document.getElementById('exchange-name').textContent = data.exchange || '-';
            document.getElementById('symbol-name').textContent = data.symbol || '-';
            document.getElementById('strategy-name').textContent = data.strategy || '-';
            document.getElementById('last-update').textContent = data.last_update || '-';
            
            // 폼 값 설정 (최초 로드 시)
            if (!formInitialized) {
                document.getElementById('exchange').value = data.exchange || 'binance';
                document.getElementById('symbol').value = data.symbol || 'BTC/USDT';
                document.getElementById('timeframe').value = data.timeframe || '1h';
                document.getElementById('strategy').value = data.strategy || 'ma_crossover';
                document.getElementById('test-mode').checked = data.test_mode !== false;
                
                // 마켓 타입 및 레버리지 설정
                if (data.market_type) {
                    document.getElementById('market-type').value = data.market_type;
                    
                    if (data.market_type === 'futures' && data.leverage) {
                        document.getElementById('leverage').value = data.leverage;
                        updateLeverageValue();
                    }
                    
                    updateMarketTypeUI();
                }
                
                // 위험 관리 설정
                if (data.risk_management) {
                    if (data.risk_management.stop_loss_pct) {
                        document.getElementById('stop-loss').value = Math.round(data.risk_management.stop_loss_pct * 100);
                        updateStopLossValue();
                    }
                    
                    if (data.risk_management.take_profit_pct) {
                        document.getElementById('take-profit').value = Math.round(data.risk_management.take_profit_pct * 100);
                        updateTakeProfitValue();
                    }
                    
                    if (data.risk_management.max_position_size) {
                        document.getElementById('max-position').value = Math.round(data.risk_management.max_position_size * 100);
                        updateMaxPositionValue();
                    }
                }
                
                formInitialized = true;
            }
            
            // 지갑 잔액 업데이트
            if (data.balance) {
                updateWalletBalance(data.balance);
            }
            
            // 포지션 정보 업데이트
            if (data.position) {
                updatePositionInfo(data.position);
            }
            
            // 거래 내역 업데이트
            if (data.trades && data.trades.length > 0) {
                updateRecentTrades(data.trades);
            }
        })
        .catch(error => console.error('상태 업데이트 실패:', error));
}

// 봇 시작
function startBot() {
    // 폼 데이터 수집
    const config = {
        exchange: document.getElementById('exchange').value,
        symbol: document.getElementById('symbol').value,
        timeframe: document.getElementById('timeframe').value,
        strategy: document.getElementById('strategy').value,
        test_mode: document.getElementById('test-mode').checked,
        
        // 마켓 타입 및 레버리지 설정
        market_type: document.getElementById('market-type').value,
        leverage: document.getElementById('market-type').value === 'futures' ? 
                parseInt(document.getElementById('leverage').value) : 1,
        
        // 위험 관리 설정
        risk_management: {
            stop_loss_pct: parseInt(document.getElementById('stop-loss').value) / 100,
            take_profit_pct: parseInt(document.getElementById('take-profit').value) / 100,
            max_position_size: parseInt(document.getElementById('max-position').value) / 100
        },
        
        // 자동 손절매/이익실현 설정
        auto_sl_tp: document.getElementById('auto-sl-tp').checked,
        partial_tp: document.getElementById('partial-tp').checked
    };
    
    // API 호출
    fetch('/api/start_bot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || '봇이 성공적으로 시작되었습니다.');
            // 상태 즉시 업데이트
            updateBotStatus();
        } else {
            alert('오류: ' + (data.message || data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        console.error('봇 시작 실패:', error);
        alert('봇 시작 중 오류가 발생했습니다.');
    });
}

// 봇 중지
function stopBot() {
    fetch('/api/stop_bot', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message || '봇이 성공적으로 중지되었습니다.');
            // 상태 즉시 업데이트
            updateBotStatus();
        } else {
            alert('오류: ' + (data.message || data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        console.error('봇 중지 실패:', error);
        alert('봇 중지 중 오류가 발생했습니다.');
    });
}

// 지갑 잔액 업데이트
function updateWalletBalance(balance) {
    const balanceContainer = document.getElementById('wallet-balance');
    
    // 기존 내용 지우기
    balanceContainer.innerHTML = '';
    
    // 각 자산별 잔액 추가
    for (const [asset, amount] of Object.entries(balance)) {
        const row = document.createElement('div');
        row.className = 'row mb-1';
        row.innerHTML = `
            <div class="col-6">${asset}</div>
            <div class="col-6 text-end">${parseFloat(amount).toFixed(6)}</div>
        `;
        balanceContainer.appendChild(row);
    }
}

// 포지션 정보 업데이트
function updatePositionInfo(position) {
    const positionElement = document.getElementById('position-info');
    
    if (!position || !position.type || position.size === 0) {
        positionElement.innerHTML = '<p>포지션 없음</p>';
        return;
    }
    
    const typeText = position.type === 'long' ? '롱 (매수)' : '숏 (매도)';
    const typeClass = position.type === 'long' ? 'text-success' : 'text-danger';
    
    let html = `
        <div class="mb-2">
            <strong>유형:</strong> <span class="${typeClass}">${typeText}</span>
        </div>
        <div class="mb-2">
            <strong>크기:</strong> ${formatNumber(position.size)}
        </div>
        <div class="mb-2">
            <strong>진입가:</strong> ${formatNumber(position.entry_price)}
        </div>`;
    
    if (position.stop_loss > 0) {
        html += `<div class="mb-2">
            <strong>손절가:</strong> ${formatNumber(position.stop_loss)}
        </div>`;
    }
    
    if (position.take_profit > 0) {
        html += `<div class="mb-2">
            <strong>이익실현가:</strong> ${formatNumber(position.take_profit)}
        </div>`;
    }
    
    positionElement.innerHTML = html;
}

// 최근 거래 내역 업데이트
function updateRecentTrades(trades) {
    const tableBody = document.getElementById('recent-trades');
    
    if (trades.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center">거래 내역이 없습니다</td></tr>';
        return;
    }
    
    let html = '';
    
    // 최근 거래부터 표시 (최대 10개)
    const recentTrades = trades.slice(-10).reverse();
    
    for (const trade of recentTrades) {
        const typeClass = trade.side === 'buy' ? 'text-success' : 'text-danger';
        const typeText = trade.side === 'buy' ? '매수' : '매도';
        
        html += `<tr>
            <td>${trade.datetime}</td>
            <td class="${typeClass}">${typeText}</td>
            <td>${formatNumber(trade.price)}</td>
            <td>${formatNumber(trade.amount)}</td>
            <td>${formatNumber(trade.cost)}</td>
        </tr>`;
    }
    
    tableBody.innerHTML = html;
}

// 숫자 포맷팅 헬퍼 함수
function formatNumber(value) {
    if (value === undefined || value === null) return '-';
    
    // 정수인지 확인
    const isInteger = Number.isInteger(parseFloat(value));
    
    // 큰 숫자인 경우 간결하게 표시
    if (value >= 1000) {
        return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: isInteger ? 0 : 2 });
    }
    // 작은 숫자인 경우 더 많은 소수점 표시
    else {
        return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 8 });
    }
}
