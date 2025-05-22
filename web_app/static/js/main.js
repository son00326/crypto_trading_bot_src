/**
 * 암호화폐 자동 매매 봇 웹 인터페이스 JavaScript
 */

// DOM 요소 참조 변수
const botStatusElem = document.getElementById('bot-status');
const exchangeNameElem = document.getElementById('exchange-name');
const symbolNameElem = document.getElementById('symbol-name');
const strategyNameElem = document.getElementById('strategy-name');
const lastUpdateElem = document.getElementById('last-update');
const startBotBtn = document.getElementById('start-bot-btn');
const stopBotBtn = document.getElementById('stop-bot-btn');
const balanceAmountElem = document.getElementById('balance-amount');
const balanceCurrencyElem = document.getElementById('balance-currency');
const botConfigForm = document.getElementById('bot-config-form');

// API URL 상수
const API_URLS = {
    STATUS: '/api/status',
    START_BOT: '/api/start_bot',
    STOP_BOT: '/api/stop_bot',
    BALANCE: '/api/balance',
    TRADES: '/api/trades',
    POSITIONS: '/api/positions', 
    SUMMARY: '/api/summary',
    SET_STOPLOSS_TAKEPROFIT: '/api/set_stop_loss_take_profit'
};

// 봇 상태 업데이트 함수
function updateBotStatus() {
    fetch(API_URLS.STATUS)
        .then(response => response.json())
        .then(data => {
            // 봇 상태 업데이트
            const running = data.running;
            botStatusElem.textContent = running ? '실행 중' : '중지됨';
            botStatusElem.className = `badge ${running ? 'bg-success' : 'bg-secondary'}`;
            
            // 기타 정보 업데이트
            exchangeNameElem.textContent = data.exchange || '-';
            symbolNameElem.textContent = data.symbol || '-';
            strategyNameElem.textContent = data.strategy || '-';
            lastUpdateElem.textContent = data.last_update || '-';
            
            // 버튼 상태 업데이트
            startBotBtn.disabled = running;
            stopBotBtn.disabled = !running;
            
            // 잔액 정보 업데이트
            if (data.balance) {
                balanceAmountElem.textContent = data.balance.amount || '0';
                balanceCurrencyElem.textContent = data.balance.currency || 'USDT';
            }
        })
        .catch(error => {
            console.error('상태 업데이트 오류:', error);
        });
}

// 봇 시작 함수
function startBot() {
    // 폼에서 설정값 가져오기
    const exchange = document.getElementById('exchange').value;
    const symbol = document.getElementById('symbol').value;
    const timeframe = document.getElementById('timeframe').value;
    const strategy = document.getElementById('strategy').value;
    const marketType = document.getElementById('market-type').value;
    
    // 전략별 파라미터 수집
    const strategyParams = collectStrategyParameters(strategy);
    
    // API 요청 데이터
    const requestData = {
        exchange: exchange,
        symbol: symbol,
        timeframe: timeframe,
        strategy: strategy,
        market_type: marketType,
        strategy_params: strategyParams
    };
    
    // API 호출
    fetch(API_URLS.START_BOT, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('봇이 성공적으로 시작되었습니다.', 'success');
            updateBotStatus();
        } else {
            showAlert(`봇 시작 실패: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('봇 시작 오류:', error);
        showAlert('봇 시작 중 오류가 발생했습니다.', 'danger');
    });
}

// 전략별 파라미터 수집 함수
function collectStrategyParameters(strategy) {
    const params = {};
    
    // 전략별로 다른 파라미터 수집
    switch(strategy) {
        case 'MovingAverageCrossover':
            params['MovingAverageCrossover'] = {
                short_period: parseInt(document.getElementById('ma-short-period').value),
                long_period: parseInt(document.getElementById('ma-long-period').value),
                ma_type: document.getElementById('ma-type').value
            };
            break;
            
        case 'RSIStrategy':
            params['RSIStrategy'] = {
                period: parseInt(document.getElementById('rsi-period').value),
                overbought: parseInt(document.getElementById('rsi-overbought').value),
                oversold: parseInt(document.getElementById('rsi-oversold').value)
            };
            break;
            
        case 'MACDStrategy':
            params['MACDStrategy'] = {
                fast_period: parseInt(document.getElementById('macd-fast-period').value),
                slow_period: parseInt(document.getElementById('macd-slow-period').value),
                signal_period: parseInt(document.getElementById('macd-signal-period').value)
            };
            break;
            
        case 'BollingerBandsStrategy':
            params['BollingerBandsStrategy'] = {
                period: parseInt(document.getElementById('bb-period').value),
                std_dev: parseFloat(document.getElementById('bb-std-dev').value)
            };
            break;
            
        case 'CombinedStrategy':
            // 복합 전략은 이동평균 교차와 RSI 전략을 함께 사용
            if(document.getElementById('use-ma-crossover').checked) {
                params['MovingAverageCrossover'] = {
                    short_period: parseInt(document.getElementById('ma-short-period').value),
                    long_period: parseInt(document.getElementById('ma-long-period').value),
                    ma_type: document.getElementById('ma-type').value
                };
            }
            
            if(document.getElementById('use-rsi').checked) {
                params['RSIStrategy'] = {
                    period: parseInt(document.getElementById('rsi-period').value),
                    overbought: parseInt(document.getElementById('rsi-overbought').value),
                    oversold: parseInt(document.getElementById('rsi-oversold').value)
                };
            }
            break;
    }
    
    return params;
}

// 전략 변경 시 파라미터 UI 업데이트
function updateStrategyParameters() {
    const strategy = document.getElementById('strategy').value;
    
    // 모든 전략 파라미터 패널 숨기기
    document.querySelectorAll('.strategy-params').forEach(panel => {
        panel.classList.add('d-none');
    });
    
    // 선택된 전략에 맞는 파라미터 패널 표시
    switch(strategy) {
        case 'MovingAverageCrossover':
            document.getElementById('ma-crossover-params').classList.remove('d-none');
            break;
        case 'RSIStrategy':
            document.getElementById('rsi-params').classList.remove('d-none');
            break;
        case 'MACDStrategy':
            document.getElementById('macd-params').classList.remove('d-none');
            break;
        case 'BollingerBandsStrategy':
            document.getElementById('bb-params').classList.remove('d-none');
            break;
        case 'CombinedStrategy':
            document.getElementById('combined-params').classList.remove('d-none');
            // 복합 전략은 MA와 RSI 파라미터를 모두 표시
            document.getElementById('ma-crossover-params').classList.remove('d-none');
            document.getElementById('rsi-params').classList.remove('d-none');
            break;
    }
}

// 봇 중지 함수
function stopBot() {
    fetch(API_URLS.STOP_BOT, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('봇이 성공적으로 중지되었습니다.', 'success');
            updateBotStatus();
        } else {
            showAlert(`봇 중지 실패: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('봇 중지 오류:', error);
        showAlert('봇 중지 중 오류가 발생했습니다.', 'danger');
    });
}

// 잔액 정보 가져오기
function getBalance() {
    fetch(API_URLS.BALANCE)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                balanceAmountElem.textContent = data.data.amount || '0';
                balanceCurrencyElem.textContent = data.data.currency || 'USDT';
            } else {
                console.warn('잔액 정보 없음:', data.message);
            }
        })
        .catch(error => {
            console.error('잔액 정보 가져오기 오류:', error);
            
            // 오류 발생 시 기본값 표시
            const balances = [
                {
                    amount: '0',
                    currency: 'USDT',
                    type: 'spot'
                },
                {
                    amount: '0',
                    currency: 'USDT',
                    type: 'future'
                }
            ];
            
            // 잔액 표시 업데이트 - 메인 표시용
            const mainBalance = balances[0];
            const formattedBalance = formatCurrency(mainBalance.amount, mainBalance.currency);
            walletBalanceElem.textContent = formattedBalance;
            walletBalanceElem.dataset.amount = mainBalance.amount;
            walletBalanceElem.dataset.currency = mainBalance.currency;
            
            // 잔액 표시 업데이트 - 상세 표시용
            balanceListElem.innerHTML = '';
            balances.forEach(balance => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                const balanceType = balance.type === 'future' ? '선물 잔액' : '현물 잔액';
                const formattedAmount = formatCurrency(balance.amount, balance.currency);
                li.innerHTML = '<span>' + balanceType + '</span><span class="badge bg-primary rounded-pill">' + formattedAmount + '</span>';
                balanceListElem.appendChild(li);
            });
        });
}

// 경고 메시지 표시 함수
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts-container');
    const alertElem = document.createElement('div');
    alertElem.className = `alert alert-${type} alert-dismissible fade show`;
    alertElem.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    alertsContainer.appendChild(alertElem);
    
    // 5초 후 자동 제거
    setTimeout(() => {
        alertElem.classList.remove('show');
        setTimeout(() => alertElem.remove(), 500);
    }, 5000);
}

// 거래 내역 업데이트 함수
function updateTrades() {
    fetch(API_URLS.TRADES)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                // 거래 내역 테이블 참조
                const tradesTableBody = document.getElementById('trades-table-body');
                if (!tradesTableBody) return;
                
                // 거래 내역 테이블 비우기
                tradesTableBody.innerHTML = '';
                
                // 거래 내역이 없는 경우
                if (data.data.length === 0) {
                    const row = document.createElement('tr');
                    row.innerHTML = '<td colspan="7" class="text-center">거래 내역이 없습니다.</td>';
                    tradesTableBody.appendChild(row);
                } else {
                    // 거래 내역 데이터로 테이블 채우기
                    data.data.forEach(trade => {
                        // 테스트 모드 배지 추가
                        const testBadge = trade.test_mode ? 
                            '<span class="badge bg-info me-1">테스트</span>' : '';
                            
                        // null/undefined 처리
                        const date = trade.datetime ? new Date(trade.datetime).toLocaleString() : '';
                        const price = parseFloat(trade.price || 0).toFixed(2);
                        const amount = parseFloat(trade.amount || 0).toFixed(4);
                        const cost = parseFloat(trade.cost || 0).toFixed(2);
                        const profit = parseFloat(trade.profit || 0);
                        const profitPercent = parseFloat(trade.profit_percent || 0).toFixed(2);
                        
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${date}</td>
                            <td>${trade.symbol || ''}</td>
                            <td>${testBadge}<span class="badge ${trade.type === 'buy' ? 'bg-success' : 'bg-danger'}">${trade.type || ''}</span></td>
                            <td>${price}</td>
                            <td>${amount}</td>
                            <td>${cost}</td>
                            <td><span class="${profit >= 0 ? 'text-success' : 'text-danger'}">${profit.toFixed(2)} (${profitPercent}%)</span></td>
                        `;
                        tradesTableBody.appendChild(row);
                    });
                }
                
                // "데이터를 불러오는 중..." 메시지 숨기기
                const loadingMsg = document.getElementById('trades-loading-message');
                if (loadingMsg) loadingMsg.classList.add('d-none');
                
                // 테이블 표시
                const tradesTable = document.getElementById('trades-table');
                if (tradesTable) tradesTable.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('거래 내역 업데이트 오류:', error);
        });
}

// 포지션 정보 업데이트 함수
function updatePositions() {
    fetch(API_URLS.POSITIONS)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                // 포지션 테이블 참조
                const positionsTableBody = document.getElementById('positions-table-body');
                if (!positionsTableBody) return;
                
                // 포지션 테이블 비우기
                positionsTableBody.innerHTML = '';
                
                // 포지션이 없는 경우
                if (data.data.length === 0) {
                    const row = document.createElement('tr');
                    row.innerHTML = '<td colspan="6" class="text-center">포지션이 없습니다.</td>';
                    positionsTableBody.appendChild(row);
                } else {
                    // 포지션 데이터로 테이블 채우기
                    data.data.forEach(position => {
                        // 테스트 모드 배지 추가
                        const testBadge = position.test_mode ? 
                            '<span class="badge bg-info me-1">테스트</span>' : '';
                            
                        // null/undefined 처리
                        const entryPrice = parseFloat(position.entry_price || 0).toFixed(2);
                        const amount = parseFloat(position.amount || 0).toFixed(4);
                        const currentPrice = parseFloat(position.current_price || 0).toFixed(2);
                        const profit = parseFloat(position.profit || 0);
                        const profitPercent = parseFloat(position.profit_percent || 0).toFixed(2);
                        
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${position.symbol || ''}</td>
                            <td>${testBadge}<span class="badge ${position.type === 'long' ? 'bg-success' : 'bg-danger'}">${position.type || ''}</span></td>
                            <td>${entryPrice}</td>
                            <td>${amount}</td>
                            <td>${currentPrice}</td>
                            <td><span class="${profit >= 0 ? 'text-success' : 'text-danger'}">${profit.toFixed(2)} (${profitPercent}%)</span></td>
                            <td>
                                <button class="btn btn-sm btn-primary set-stoploss-takeprofit-btn" 
                                    data-position-id="${position.id}" 
                                    data-symbol="${position.symbol}" 
                                    data-side="${position.type}" 
                                    data-entry-price="${position.entry_price}">
                                    손절/이익실현 설정
                                </button>
                            </td>
                        `;
                        positionsTableBody.appendChild(row);
                    });
                }
                
                // "데이터를 불러오는 중..." 메시지 숨기기
                const positionsLoadingMsg = document.getElementById('positions-loading-message');
                if (positionsLoadingMsg) positionsLoadingMsg.classList.add('d-none');
                
                // 테이블 표시
                const positionsTable = document.getElementById('positions-table');
                if (positionsTable) positionsTable.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('포지션 업데이트 오류:', error);
        });
}

// 요약 정보 업데이트 함수
function updateSummary() {
    console.log('잔액 정보 업데이트 시작...');
    fetch(API_URLS.SUMMARY)
        .then(response => {
            console.log('응답 상태 코드:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('받은 잔액 데이터 (JSON):', JSON.stringify(data));
            if (data.success && data.data) {
                // 잔액 정보 업데이트
                if (data.data.balance) {
                    console.log('발견된 잔액 데이터:', data.data.balance);
                    // 새로운 잔액 구조 처리 (현물 + 선물)
                    const balances = [];
                    
                    // 현물 잔액 처리
                    if (data.data.balance.spot) {
                        console.log('현물 잔액 발견:', data.data.balance.spot);
                        balances.push({
                            amount: data.data.balance.spot.amount,
                            currency: data.data.balance.spot.currency,
                            type: 'spot'
                        });
                    }
                    
                    // 선물 잔액 처리
                    if (data.data.balance.future) {
                        console.log('선물 잔액 발견:', data.data.balance.future);
                        balances.push({
                            amount: data.data.balance.future.amount,
                            currency: data.data.balance.future.currency,
                            type: 'future'
                        });
                    }
                    
                    // 잔액 정보가 없을 경우 기본값 설정
                    if (balances.length === 0) {
                        console.log('잔액 정보 없음, 기본값 사용');
                        balances.push({
                            amount: '0',
                            currency: 'USDT',
                            type: 'spot'
                        });
                        
                        // 선물 잔액도 기본값 추가
                        balances.push({
                            amount: '0',
                            currency: 'USDT',
                            type: 'future'
                        });
                    }
                    
                    console.log('처리된 잔액 데이터:', balances);
                    
                    // 잔액 표시 업데이트 - 메인 표시용
                    if (balances.length > 0) {
                        // 메인 표시 영역에는 모든 잔액 표시
                        if (balanceAmountElem && balanceCurrencyElem) {
                            const mainBalance = balances[0];
                            balanceAmountElem.textContent = Number(mainBalance.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 8});
                            balanceCurrencyElem.textContent = mainBalance.currency;
                            console.log('메인 잔액 업데이트 완료');
                        } else {
                            console.error('메인 잔액 표시 요소를 찾을 수 없음');
                        }
                    }
                    
                    // 요약 표시용
                    const summaryBalanceAmount = document.getElementById('summary-balance-amount');
                    const summaryBalanceCurrency = document.getElementById('summary-balance-currency');
                    if (summaryBalanceAmount && summaryBalanceCurrency && balances.length > 0) {
                        const mainBalance = balances[0];
                        summaryBalanceAmount.textContent = Number(mainBalance.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 8});
                        summaryBalanceCurrency.textContent = mainBalance.currency;
                        console.log('요약 잔액 업데이트 완료');
                    }
                    
                    // 현물/선물 잔액 모두 표시
                    const balanceContainer = document.getElementById('balance-container');
                    if (balanceContainer) {
                        // 기존 내용 삭제
                        balanceContainer.innerHTML = '';
                        console.log('balance-container 발견, 내용 초기화');
                        
                        // 각 잔액 정보 표시
                        balances.forEach(balance => {
                            const balanceItem = document.createElement('div');
                            balanceItem.className = 'mb-2';
                            balanceItem.innerHTML = `
                                <div class="fw-bold">${balance.type === 'spot' ? '현물' : '선물'} 잔액:</div>
                                <div class="h5 mb-0">
                                    <span>${Number(balance.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 8})}</span>
                                    <span>${balance.currency}</span>
                                </div>
                            `;
                            balanceContainer.appendChild(balanceItem);
                            console.log(`${balance.type} 잔액 업데이트 완료: ${balance.amount} ${balance.currency}`);
                        });
                    } else {
                        console.error('balance-container 요소를 찾을 수 없음');
                    }
                }
                
                // 수익 성과 정보 업데이트
                if (data.data.performance) {
                    const perf = data.data.performance;
                    const totalProfitElem = document.getElementById('total-profit');
                    if (totalProfitElem) totalProfitElem.textContent = perf.total_profit || '0.00';
                    
                    const winRateElem = document.getElementById('win-rate');
                    if (winRateElem) winRateElem.textContent = perf.win_rate || '0%';
                    
                    const avgProfitElem = document.getElementById('avg-profit');
                    if (avgProfitElem) avgProfitElem.textContent = perf.avg_profit || '0.00';
                }
                
                // "데이터를 불러오는 중..." 메시지 숨기기
                const summaryLoadingMsg = document.getElementById('summary-loading-message');
                if (summaryLoadingMsg) summaryLoadingMsg.classList.add('d-none');
                
                // 요약 데이터 표시
                const summaryContent = document.getElementById('summary-content');
                if (summaryContent) summaryContent.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('요약 정보 업데이트 오류:', error);
        });
}

// 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', function() {
    // 초기 데이터 로드
    updateBotStatus();
    
    // 지연 후 잔액 정보 불러오기 - 세션 초기화 시간 확보
    setTimeout(() => {
        console.log('지연 후 잔액 정보 가져오기 시도...');
        updateSummary();
    }, 2000);
    
    updateTrades();
    updatePositions();
    
    // 자동 업데이트 타이머 설정
    setInterval(updateBotStatus, 5000);     // 5초마다
    setInterval(updateTrades, 15000);       // 15초마다
    setInterval(updatePositions, 10000);    // 10초마다
    setInterval(updateSummary, 15000);      // 15초마다 (더 자주 확인)
    
    // 봇 시작 버튼 클릭 이벤트
    startBotBtn.addEventListener('click', startBot);
    
    // 봇 중지 버튼 클릭 이벤트
    stopBotBtn.addEventListener('click', stopBot);
    
    // 전략 변경 시 파라미터 UI 업데이트
    const strategySelect = document.getElementById('strategy');
    strategySelect.addEventListener('change', updateStrategyParameters);
    
    // 초기 전략 파라미터 UI 설정
    updateStrategyParameters();
    
    // 마켓 타입과 거래소 변경 관련 요소
    const marketTypeSelect = document.getElementById('market-type');
    const futuresSettings = document.getElementById('futures-settings');
    const symbolInput = document.getElementById('symbol');
    const exchangeSelect = document.getElementById('exchange');
    
    // 마켓 타입에 따른 거래 쌍 포맷 설정
    function updateSymbolFormat() {
        const marketType = marketTypeSelect.value;
        const currentSymbol = symbolInput.value;
        
        if (marketType === 'futures') {
            // 선물일 경우 포맷 변경 (BTC/USDT -> BTCUSDT:USDT)
            if (currentSymbol.includes('/')) {
                const parts = currentSymbol.split('/');
                symbolInput.value = parts[0] + parts[1] + ':' + parts[1];
            } else if (!currentSymbol.includes(':')) {
                // 포맷이 아직 올바르지 않다면 기본값으로 설정
                symbolInput.value = 'BTCUSDT:USDT';
            }
            // 선물 설정 표시
            futuresSettings.classList.remove('d-none');
        } else {
            // 현물일 경우 포맷 변경 (BTCUSDT:USDT -> BTC/USDT)
            if (currentSymbol.includes(':')) {
                const base = currentSymbol.split(':')[0].replace(/USDT$|USD$/, '');
                const quote = currentSymbol.includes('USDT') ? 'USDT' : 'USD';
                symbolInput.value = base + '/' + quote;
            } else if (!currentSymbol.includes('/')) {
                // 포맷이 아직 올바르지 않다면 기본값으로 설정
                symbolInput.value = 'BTC/USDT';
            }
            // 선물 설정 숨김
            futuresSettings.classList.add('d-none');
        }
    }
    
    // 마켓 타입 변경 시 거래 쌍 포맷 업데이트
    marketTypeSelect.addEventListener('change', updateSymbolFormat);
    
    // 거래소 변경 시에도 해당 거래소에 맞는 포맷으로 업데이트
    exchangeSelect.addEventListener('change', function() {
        updateSymbolFormat();
    });
    
    // 슬라이더 값 표시 기능 추가
    function setupSlider(sliderId, bubbleId, valueSuffixFn) {
        const slider = document.getElementById(sliderId);
        const bubble = document.getElementById(bubbleId);
        const valueSpan = document.getElementById(sliderId + '-value');
        
        if (!slider || !bubble) return;
        
        function updateBubble(slider, bubble, valueSuffixFn) {
            // 슬라이더 값
            const val = slider.value;
            
            // 버블에 표시할 텍스트 설정
            const displayValue = valueSuffixFn ? valueSuffixFn(val) : val;
            bubble.textContent = displayValue;
            
            // 슬라이더 가운데 값 업데이트
            if (valueSpan) {
                valueSpan.textContent = displayValue;
            }
            
            // 버블 위치 조정
            const min = slider.min ? parseFloat(slider.min) : 0;
            const max = slider.max ? parseFloat(slider.max) : 100;
            const newVal = Number((val - min) * 100 / (max - min));
            bubble.style.left = `calc(${newVal}% + (${8 - newVal * 0.15}px))`;
        }
        
        // 초기 값 설정
        updateBubble(slider, bubble, valueSuffixFn);
        
        // 슬라이더 이동 시 업데이트
        slider.addEventListener('input', function() {
            updateBubble(this, bubble, valueSuffixFn);
        });
    }
    
    // 슬라이더 초기화
    setupSlider('leverage', 'leverage-bubble', val => val + 'x');
    setupSlider('stop-loss', 'stop-loss-bubble', val => val + '%');
    setupSlider('take-profit', 'take-profit-bubble', val => val + '%'); 
    setupSlider('max-position', 'max-position-bubble', val => val + '%');
});
