// API 엔드포인트 URL 정의
const API_URLS = {
    BALANCE: '/api/balance',
    STATUS: '/api/status',
    START_BOT: '/api/start_bot',
    STOP_BOT: '/api/stop_bot',
    POSITIONS: '/api/positions',
    TRADES: '/api/trades',
    SET_SL_TP: '/api/set_stop_loss_take_profit'
};

// 모든 UI 요소 참조 저장
const balanceAmountElem = document.getElementById('summary-balance-amount');
const balanceCurrencyElem = document.getElementById('summary-balance-currency');
const balanceDetailsElem = document.getElementById('summary-balance-details');
const summaryLoadingMsg = document.getElementById('summary-loading-message');
const summaryContent = document.getElementById('summary-content');
const statusContainer = document.getElementById('status-container');
const positionsContainer = document.getElementById('positions-container');
const tradesTableBody = document.getElementById('trades-table-body');
const botStartBtn = document.getElementById('bot-start-btn');
const botStopBtn = document.getElementById('bot-stop-btn');

// 금액 포맷팅 함수
function formatCurrency(amount, minimumFractionDigits = 2, maximumFractionDigits = 8) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: minimumFractionDigits,
        maximumFractionDigits: maximumFractionDigits
    }).format(amount);
}

// 날짜 포맷팅 함수 
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 상태 업데이트 함수
function updateStatus() {
    fetch(API_URLS.STATUS)
        .then(response => response.json())
        .then(data => {
            if (data.status && statusContainer) {
                const statusBadge = data.status.is_running ? 
                    '<span class="badge bg-success">실행 중</span>' :
                    '<span class="badge bg-danger">중지됨</span>';
                    
                statusContainer.innerHTML = `
                    <p>봇 상태: ${statusBadge}</p>
                    <p>거래소: ${data.status.exchange || 'N/A'}</p>
                    <p>거래 쌍: ${data.status.symbol || 'N/A'}</p>
                    <p>레버리지: ${data.status.leverage || 'N/A'}x</p>
                `;
                
                // 버튼 상태 업데이트
                if (botStartBtn && botStopBtn) {
                    botStartBtn.disabled = data.status.is_running;
                    botStopBtn.disabled = !data.status.is_running;
                }
            }
        })
        .catch(error => console.error('상태 정보 업데이트 오류:', error));
}

// 포지션 정보 업데이트 함수
function updatePositions() {
    fetch(API_URLS.POSITIONS)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.positions && positionsContainer) {
                if (data.positions.length === 0) {
                    positionsContainer.innerHTML = '<p class="text-muted">열린 포지션이 없습니다.</p>';
                } else {
                    let html = '<div class="list-group">';
                    data.positions.forEach(position => {
                        const profitClass = position.unrealized_pnl >= 0 ? 'text-success' : 'text-danger';
                        html += `
                            <div class="list-group-item">
                                <div class="d-flex justify-content-between">
                                    <h6>${position.symbol}</h6>
                                    <span class="badge ${position.side === 'long' ? 'bg-success' : 'bg-danger'}">${position.side.toUpperCase()}</span>
                                </div>
                                <p class="mb-1">수량: ${position.contracts}</p>
                                <p class="mb-1">평균가: $${formatCurrency(position.entry_price)}</p>
                                <p class="mb-0 ${profitClass}">미실현 손익: $${formatCurrency(position.unrealized_pnl)}</p>
                            </div>
                        `;
                    });
                    html += '</div>';
                    positionsContainer.innerHTML = html;
                }
            }
        })
        .catch(error => console.error('포지션 정보 업데이트 오류:', error));
}

// 거래 내역 업데이트 함수
function updateTrades() {
    fetch(API_URLS.TRADES)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.trades && tradesTableBody) {
                if (data.trades.length === 0) {
                    tradesTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">거래 내역이 없습니다.</td></tr>';
                } else {
                    let html = '';
                    data.trades.forEach(trade => {
                        const profitClass = trade.profit >= 0 ? 'text-success' : 'text-danger';
                        html += `
                            <tr>
                                <td>${formatDate(trade.timestamp)}</td>
                                <td>${trade.symbol}</td>
                                <td><span class="badge ${trade.side === 'buy' ? 'bg-success' : 'bg-danger'}">${trade.side.toUpperCase()}</span></td>
                                <td>${trade.amount}</td>
                                <td>$${formatCurrency(trade.price)}</td>
                                <td>$${formatCurrency(trade.cost)}</td>
                                <td class="${profitClass}">${trade.profit ? '$' + formatCurrency(trade.profit) : '-'}</td>
                            </tr>
                        `;
                    });
                    tradesTableBody.innerHTML = html;
                }
            }
        })
        .catch(error => console.error('거래 내역 업데이트 오류:', error));
}

// 봇 시작 함수
function startBot() {
    if (confirm('봇을 시작하시겠습니까?')) {
        fetch(API_URLS.START_BOT, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('봇이 시작되었습니다.');
                    updateStatus();
                } else {
                    alert('봇 시작 실패: ' + (data.error || '알 수 없는 오류'));
                }
            })
            .catch(error => {
                console.error('봇 시작 오류:', error);
                alert('봇 시작 중 오류가 발생했습니다.');
            });
    }
}

// 봇 중지 함수
function stopBot() {
    if (confirm('봇을 중지하시겠습니까?')) {
        fetch(API_URLS.STOP_BOT, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('봇이 중지되었습니다.');
                    updateStatus();
                } else {
                    alert('봇 중지 실패: ' + (data.error || '알 수 없는 오류'));
                }
            })
            .catch(error => {
                console.error('봇 중지 오류:', error);
                alert('봇 중지 중 오류가 발생했습니다.');
            });
    }
}

// 손절/익절 설정 함수
function setStopLossTakeProfit(symbol, stopLoss, takeProfit) {
    const data = {
        symbol: symbol,
        stop_loss: stopLoss,
        take_profit: takeProfit
    };
    
    fetch(API_URLS.SET_SL_TP, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('손절/익절이 설정되었습니다.');
            updatePositions();
        } else {
            alert('손절/익절 설정 실패: ' + (data.error || '알 수 없는 오류'));
        }
    })
    .catch(error => {
        console.error('손절/익절 설정 오류:', error);
        alert('손절/익절 설정 중 오류가 발생했습니다.');
    });
}

// 모든 데이터 업데이트 함수
function updateAllData() {
    updateStatus();
    updateSummary();
    updatePositions();
    updateTrades();
}

// 봇 로그 업데이트 함수
function updateBotLogs() {
    // WebSocket 또는 별도 API를 통해 구현
    console.log('봇 로그 업데이트 (미구현)');
}

// 차트 업데이트 함수
function updateChart() {
    // Chart.js 또는 다른 차트 라이브러리를 사용하여 구현
    console.log('차트 업데이트 (미구현)');
}

// 로그아웃 함수
function logout() {
    if (confirm('로그아웃하시겠습니까?')) {
        window.location.href = '/logout';
    }
}

// 잔액 정보 업데이트 함수 (수정됨)
function updateBalance() {
    console.log('잔액 정보 업데이트 시작...');
    fetch(API_URLS.BALANCE)
        .then(response => {
            console.log('응답 상태:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('받은 데이터:', data);
            
            if (data && data.success && data.balance) {
                // 현물과 선물 잔액 가져오기
                const spotBalance = (data.balance.spot && data.balance.spot.balance) || 0;
                const futureBalance = (data.balance.future && data.balance.future.balance) || 0;
                const totalBalance = spotBalance + futureBalance;
                
                console.log('현물 잔액:', spotBalance);
                console.log('선물 잔액:', futureBalance);
                console.log('총 잔액:', totalBalance);
                
                // 메인 잔액 표시
                if (balanceAmountElem) {
                    balanceAmountElem.textContent = formatCurrency(totalBalance, 2, 8);
                    console.log('잔액 요소 업데이트 완료');
                } else {
                    console.error('잔액 표시 요소를 찾을 수 없습니다');
                }
                
                if (balanceCurrencyElem) {
                    balanceCurrencyElem.textContent = 'USDT';
                }
                
                // 상세 잔액 표시
                if (balanceDetailsElem) {
                    let detailsHtml = '';
                    if (spotBalance > 0) {
                        detailsHtml += `
                            <div class="d-flex justify-content-between">
                                <span class="text-muted">현물:</span>
                                <span>${formatCurrency(spotBalance, 2, 8)} USDT</span>
                            </div>
                        `;
                    }
                    if (futureBalance > 0) {
                        detailsHtml += `
                            <div class="d-flex justify-content-between">
                                <span class="text-muted">선물:</span>
                                <span>${formatCurrency(futureBalance, 2, 8)} USDT</span>
                            </div>
                        `;
                    }
                    balanceDetailsElem.innerHTML = detailsHtml;
                }
                
                // 로딩 메시지 숨기고 콘텐츠 표시
                if (summaryLoadingMsg) {
                    summaryLoadingMsg.classList.add('d-none');
                }
                if (summaryContent) {
                    summaryContent.classList.remove('d-none');
                }
            } else {
                console.error('잔액 데이터 형식이 올바르지 않습니다:', data);
            }
        })
        .catch(error => {
            console.error('잔액 정보 업데이트 오류:', error);
            if (balanceAmountElem) {
                balanceAmountElem.textContent = '오류';
            }
        });
}

// 요약 정보 업데이트 함수 (updateBalance 호출)
function updateSummary() {
    updateBalance();
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('페이지 로드 완료, 초기화 시작...');
    
    // 버튼 이벤트 리스너 등록
    if (botStartBtn) {
        botStartBtn.addEventListener('click', startBot);
    }
    if (botStopBtn) {
        botStopBtn.addEventListener('click', stopBot);
    }
    
    // 초기 데이터 로드
    updateAllData();
    
    // 주기적 업데이트 설정 (30초마다)
    setInterval(updateAllData, 30000);
});

// 디버깅을 위한 전역 함수 노출
window.updateBalance = updateBalance;
window.updateSummary = updateSummary;
