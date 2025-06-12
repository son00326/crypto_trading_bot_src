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
// 포지션 관련 요소
const positionsLoadingMessage = document.getElementById('positions-loading-message');
const positionsTable = document.getElementById('positions-table');
const positionsTableBody = document.getElementById('positions-table-body');

// 거래 관련 요소
const tradesLoadingMessage = document.getElementById('trades-loading-message');
const tradesTable = document.getElementById('trades-table');
const tradesTableBody = document.getElementById('trades-table-body');
const botStartBtn = document.getElementById('start-bot-btn');
const botStopBtn = document.getElementById('stop-bot-btn');

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
// 설정 비활성화 함수 추가
function toggleSettingsAvailability(isRunning) {
    // 모든 설정 입력 요소를 비활성화
    const settingsForm = document.getElementById('bot-config-form');
    if (settingsForm) {
        const formElements = settingsForm.querySelectorAll('input, select, button');
        formElements.forEach(element => {
            element.disabled = isRunning;
        });
    }
}

function updateStatus() {
    fetch(API_URLS.STATUS, {
        method: 'GET',
        credentials: 'same-origin'  // 쿠키 포함
    })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.data) {
                const status = data.data;
                const isRunning = status.is_running;
                
                // 버튼 상태 업데이트
                if (botStartBtn && botStopBtn) {
                    botStartBtn.disabled = isRunning;
                    botStopBtn.disabled = !isRunning;
                    
                    // 버튼 스타일 업데이트
                    if (isRunning) {
                        botStartBtn.classList.add('disabled');
                        botStopBtn.classList.remove('disabled');
                    } else {
                        botStartBtn.classList.remove('disabled');
                        botStopBtn.classList.add('disabled');
                    }
                }
                
                // 설정 양식 비활성화
                toggleSettingsAvailability(isRunning);
                
                // 봇 상태 배지 업데이트
                const botStatusElem = document.getElementById('bot-status');
                if (botStatusElem) {
                    botStatusElem.className = isRunning ? 'badge bg-success' : 'badge bg-danger';
                    botStatusElem.textContent = isRunning ? '실행 중' : '중지됨';
                }
                
                // 거래소, 심볼, 전략 정보 업데이트
                const exchangeElem = document.getElementById('exchange-name');
                const symbolElem = document.getElementById('symbol-name');
                const strategyElem = document.getElementById('strategy-name');
                
                if (exchangeElem) exchangeElem.textContent = status.exchange || '-';
                if (symbolElem) symbolElem.textContent = status.ui_symbol || status.symbol || '-';
                if (strategyElem) strategyElem.textContent = status.strategy || '-';
                
                // 상태 컨테이너 업데이트
                if (statusContainer) {
                    let marketTypeText = status.market_type === 'futures' ? '선물' : '현물';
                    let modeText = status.test_mode ? '테스트 모드' : '실거래 모드';
                    
                    statusContainer.innerHTML = `
                        <small class="text-muted ms-2">${marketTypeText} | ${modeText}</small>
                        ${status.timeframe ? `<p class="mb-1">시간프레임: ${status.timeframe}</p>` : ''}
                        ${status.leverage && status.leverage > 1 ? `<p>레버리지: ${status.leverage}x</p>` : ''}
                        ${status.started_at ? `<p class="text-muted small">시작 시간: ${formatDate(status.started_at)}</p>` : ''}
                    `;
                }
            }
        })
        .catch(error => {
            console.error('상태 업데이트 오류:', error);
            if (statusContainer) {
                statusContainer.innerHTML = '<span class="badge bg-warning">상태 확인 불가</span>';
            }
        });
}

// 포지션 정보 업데이트 함수
function updatePositions() {
    // 로딩 메시지 표시, 테이블 숨기기
    if (positionsLoadingMessage) positionsLoadingMessage.classList.remove('d-none');
    if (positionsTable) positionsTable.classList.add('d-none');

    fetch(API_URLS.POSITIONS, {
        method: 'GET',
        credentials: 'same-origin'  // 쿠키 포함
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // 로딩 메시지 숨기고, 테이블 표시
            if (positionsLoadingMessage) positionsLoadingMessage.classList.add('d-none');
            if (positionsTable) positionsTable.classList.remove('d-none');
            
            if (data.success && data.data && positionsTableBody) {
                if (data.data.length === 0) {
                    positionsTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">열린 포지션이 없습니다.</td></tr>';
                } else {
                    let html = '';
                    
                    data.data.forEach(position => {
                        const profitClass = position.unrealized_pnl >= 0 ? 'text-success' : 'text-danger';
                        html += `
                            <tr>
                                <td>${position.symbol}</td>
                                <td><span class="badge ${position.side === 'long' ? 'bg-success' : 'bg-danger'}">${position.side.toUpperCase()}</span></td>
                                <td>${position.contracts}</td>
                                <td>$${formatCurrency(position.entry_price)}</td>
                                <td>$${formatCurrency(position.mark_price)}</td>
                                <td class="${profitClass}">$${formatCurrency(position.unrealized_pnl)}</td>
                                <td><button class="btn btn-sm btn-danger" onclick="closePosition('${position.symbol}')">종료</button></td>
                            </tr>
                        `;
                    });
                    
                    positionsTableBody.innerHTML = html;
                }
            } else if (!data.success && positionsTableBody) {
                positionsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">오류: ${data.error || '포지션 데이터를 불러올 수 없습니다.'}</td></tr>`;
                if (positionsTable) positionsTable.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('포지션 정보 업데이트 오류:', error);
            if (positionsLoadingMessage) positionsLoadingMessage.classList.add('d-none');
            if (positionsTable) positionsTable.classList.remove('d-none');
            if (positionsTableBody) {
                positionsTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">포지션 데이터 로드 실패: ${error.message}</td></tr>`;
            }
        });
}

// 거래 내역 업데이트 함수
function updateTrades() {
    // 로딩 메시지 표시, 테이블 숨기기
    if (tradesLoadingMessage) tradesLoadingMessage.classList.remove('d-none');
    if (tradesTable) tradesTable.classList.add('d-none');

    fetch(API_URLS.TRADES + '?limit=10', {
        method: 'GET',
        credentials: 'same-origin'  // 쿠키 포함
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // 로딩 메시지 숨기고, 테이블 표시
            if (tradesLoadingMessage) tradesLoadingMessage.classList.add('d-none');
            if (tradesTable) tradesTable.classList.remove('d-none');

            if (data.success && data.data && tradesTableBody) {
                if (data.data.length === 0) {
                    tradesTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">거래 내역이 없습니다.</td></tr>';
                } else {
                    let html = '';
                    data.data.forEach(trade => {
                        const profitClass = trade.profit >= 0 ? 'text-success' : 'text-danger';
                        html += `
                            <tr>
                                <td>${formatDate(trade.datetime)}</td>
                                <td>${trade.symbol}</td>
                                <td><span class="badge ${trade.type === 'buy' ? 'bg-success' : 'bg-danger'}">${trade.type.toUpperCase()}</span></td>
                                <td>${trade.amount}</td>
                                <td>$${formatCurrency(trade.price)}</td>
                                <td>$${formatCurrency(trade.cost)}</td>
                                <td class="${profitClass}">${trade.profit ? '$' + formatCurrency(trade.profit) : '-'}</td>
                            </tr>
                        `;
                    });
                    tradesTableBody.innerHTML = html;
                }
            } else if (!data.success && tradesTableBody) {
                tradesTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">오류: ${data.error || '거래 데이터를 불러올 수 없습니다.'}</td></tr>`;
                if (tradesTable) tradesTable.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('거래 내역 업데이트 오류:', error);
            if (tradesLoadingMessage) tradesLoadingMessage.classList.add('d-none');
            if (tradesTable) tradesTable.classList.remove('d-none');
            if (tradesTableBody) {
                tradesTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">거래 데이터 로드 실패: ${error.message}</td></tr>`;
            }
        });
}

// 봇 시작 함수
function startBot() {
    console.log('startBot 함수 호출됨');
    
    if (confirm('봇을 시작하시겠습니까?')) {
        console.log('사용자가 확인 눌렀음');
        
        // 설정 값들 가져오기
        const strategy = document.getElementById('strategy')?.value;
        const symbol = document.getElementById('symbol')?.value;
        const timeframe = document.getElementById('timeframe')?.value;
        const marketType = document.getElementById('market-type')?.value;
        const leverage = document.getElementById('leverage')?.value;
        
        console.log('입력 값들:', {
            strategy,
            symbol,
            timeframe,
            marketType,
            leverage
        });
        
        // 필수 값 검증
        if (!strategy || !symbol || !timeframe) {
            alert('전략, 심볼, 시간프레임을 모두 선택해주세요.');
            return;
        }
        
        // 위험 관리 설정 값들 가져오기
        const stopLoss = document.getElementById('stop-loss')?.value;
        const takeProfit = document.getElementById('take-profit')?.value;
        const maxPosition = document.getElementById('max-position')?.value;
        const autoSlTp = document.getElementById('auto-sl-tp')?.checked;
        const partialTp = document.getElementById('partial-tp')?.checked;
        const testMode = document.getElementById('test-mode')?.checked;
        
        // 전략별 파라미터 가져오기
        const strategyParams = {};
        if (strategy === 'MovingAverageCrossover') {
            strategyParams.short_period = parseInt(document.getElementById('ma-short-period')?.value || 9);
            strategyParams.long_period = parseInt(document.getElementById('ma-long-period')?.value || 26);
            strategyParams.ma_type = document.getElementById('ma-type')?.value || 'sma';
        } else if (strategy === 'RSIStrategy') {
            strategyParams.period = parseInt(document.getElementById('rsi-period')?.value || 14);
            strategyParams.overbought = parseInt(document.getElementById('rsi-overbought')?.value || 70);
            strategyParams.oversold = parseInt(document.getElementById('rsi-oversold')?.value || 30);
        } else if (strategy === 'BollingerBandsStrategy') {
            strategyParams.period = parseInt(document.getElementById('bb-period')?.value || 20);
            strategyParams.std_dev = parseFloat(document.getElementById('bb-std-dev')?.value || 2.0);
        } else if (strategy === 'MACDStrategy') {
            strategyParams.fast_period = parseInt(document.getElementById('macd-fast-period')?.value || 12);
            strategyParams.slow_period = parseInt(document.getElementById('macd-slow-period')?.value || 26);
            strategyParams.signal_period = parseInt(document.getElementById('macd-signal-period')?.value || 9);
        } else if (strategy === 'CombinedStrategy') {
            strategyParams.ma_short_period = parseInt(document.getElementById('combo-ma-short-period')?.value || 9);
            strategyParams.ma_long_period = parseInt(document.getElementById('combo-ma-long-period')?.value || 26);
            strategyParams.rsi_period = parseInt(document.getElementById('combo-rsi-period')?.value || 14);
            strategyParams.rsi_threshold = parseInt(document.getElementById('combo-rsi-threshold')?.value || 50);
        }
        
        const requestData = {
            strategy: strategy,
            symbol: symbol,
            timeframe: timeframe,
            market_type: marketType,
            leverage: parseInt(leverage),
            stop_loss: parseFloat(stopLoss),
            take_profit: parseFloat(takeProfit),
            max_position: parseFloat(maxPosition),
            auto_sl_tp: autoSlTp,
            partial_tp: partialTp,
            test_mode: testMode,
            strategy_params: strategyParams
        };
        
        console.log('전송할 데이터:', requestData);
        console.log('API URL:', API_URLS.START_BOT);
        
        fetch(API_URLS.START_BOT, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',  // 쿠키 포함
            body: JSON.stringify(requestData)
        })
            .then(response => {
                console.log('응답 상태:', response.status);
                console.log('응답 헤더:', response.headers);
                return response.json();
            })
            .then(data => {
                console.log('응답 데이터:', data);
                if (data.success) {
                    alert('봇이 시작되었습니다.');
                    updateStatus();  // 즉시 상태 업데이트
                    updateAllData(); // 전체 데이터 업데이트
                } else {
                    alert('봇 시작 실패: ' + (data.error || '알 수 없는 오류'));
                }
            })
            .catch(error => {
                console.error('봇 시작 오류:', error);
                alert('봇 시작 중 오류가 발생했습니다.');
            });
    } else {
        console.log('사용자가 취소 눌렀음');
    }
}

// 봇 중지 함수
function stopBot() {
    if (confirm('봇을 중지하시겠습니까?')) {
        fetch(API_URLS.STOP_BOT, {
            method: 'POST',
            credentials: 'same-origin'  // 쿠키 포함
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('봇이 중지되었습니다.');
                    updateStatus();  // 즉시 상태 업데이트
                    updateAllData(); // 전체 데이터 업데이트
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
        credentials: 'same-origin',  // 쿠키 포함
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
    fetch(API_URLS.BALANCE, {
        method: 'GET', 
        credentials: 'same-origin'  // 쿠키 포함
    })
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
    
    // 마켓 타입 변경 이벤트 리스너 추가
    const marketTypeSelect = document.getElementById('market-type');
    const symbolInput = document.getElementById('symbol');
    const futuresSettings = document.getElementById('futures-settings');
    
    if (marketTypeSelect && symbolInput) {
        // 심볼 입력란을 읽기 전용으로 설정
        symbolInput.readOnly = true;
        
        // 마켓 타입 변경 시 심볼 형식 업데이트
        marketTypeSelect.addEventListener('change', function() {
            const selectedMarket = this.value;
            const currentSymbol = symbolInput.value;
            
            // 심볼에서 기본 코인 쌍 추출 (BTC/USDT → BTC, USDT)
            let baseCoin = '';
            let quoteCoin = '';
            
            if (currentSymbol.includes('/')) {
                [baseCoin, quoteCoin] = currentSymbol.split('/');
            } else {
                // 슬래시가 없는 경우 (예: BTCUSDT)
                if (currentSymbol.endsWith('USDT')) {
                    baseCoin = currentSymbol.replace('USDT', '');
                    quoteCoin = 'USDT';
                } else if (currentSymbol.endsWith('BUSD')) {
                    baseCoin = currentSymbol.replace('BUSD', '');
                    quoteCoin = 'BUSD';
                }
            }
            
            // 마켓 타입에 따라 심볼 형식 변경
            if (selectedMarket === 'futures') {
                // 선물: 슬래시 없이 (예: BTCUSDT)
                symbolInput.value = baseCoin + quoteCoin;
                // 선물 설정 표시
                if (futuresSettings) {
                    futuresSettings.classList.remove('d-none');
                }
            } else {
                // 현물: 슬래시 있게 (예: BTC/USDT)
                symbolInput.value = baseCoin + '/' + quoteCoin;
                // 선물 설정 숨기기
                if (futuresSettings) {
                    futuresSettings.classList.add('d-none');
                }
            }
            
            console.log(`마켓 타입 변경: ${selectedMarket}, 심볼: ${symbolInput.value}`);
        });
        
        // 초기 심볼 형식 설정
        marketTypeSelect.dispatchEvent(new Event('change'));
    }
    
    // 전략 선택 시 파라미터 섹션 표시 이벤트 리스너
    const strategySelect = document.getElementById('strategy');
    if (strategySelect) {
        // 전략 값과 HTML ID 매핑
        const strategyToParamsMap = {
            'MovingAverageCrossover': 'ma-crossover-params',
            'RSIStrategy': 'rsi-params',
            'MACDStrategy': 'macd-params',
            'BollingerBandsStrategy': 'bb-params',
            'CombinedStrategy': 'combined-params'
        };
        
        strategySelect.addEventListener('change', function() {
            // 모든 전략 파라미터 섹션 숨기기
            document.querySelectorAll('.strategy-params').forEach(section => {
                section.style.display = 'none';
            });
            
            // 선택된 전략의 파라미터 섹션만 표시
            const selectedStrategy = strategySelect.value;
            const paramSectionId = strategyToParamsMap[selectedStrategy];
            const selectedParamSection = document.getElementById(paramSectionId);
            
            if (selectedParamSection) {
                selectedParamSection.style.display = 'block';
            }
        });
        
        // 페이지 로드 시 현재 선택된 전략의 파라미터 섹션 표시
        const initialStrategy = strategySelect.value;
        document.querySelectorAll('.strategy-params').forEach(section => {
            section.style.display = 'none';
        });
        
        const initialParamSectionId = strategyToParamsMap[initialStrategy];
        const initialParamSection = document.getElementById(initialParamSectionId);
        if (initialParamSection) {
            initialParamSection.style.display = 'block';
        }
    }
    
    // 슬라이더 이벤트 핸들러 추가
    const leverageSlider = document.getElementById('leverage');
    const leverageBubble = document.getElementById('leverage-bubble');
    const leverageValue = document.getElementById('leverage-value');
    
    if (leverageSlider && leverageBubble && leverageValue) {
        leverageSlider.addEventListener('input', function() {
            const value = this.value;
            leverageBubble.textContent = value + 'x';
            leverageValue.textContent = value + 'x';
            
            // 버블 위치 조정
            const percent = (value - this.min) / (this.max - this.min);
            const offset = percent * (this.offsetWidth - 20);
            leverageBubble.style.left = offset + 'px';
        });
        
        // 초기 위치 설정
        leverageSlider.dispatchEvent(new Event('input'));
    }
    
    // 손절매 슬라이더
    const stopLossSlider = document.getElementById('stop-loss');
    const stopLossBubble = document.getElementById('stop-loss-bubble');
    const stopLossValue = document.getElementById('stop-loss-value');
    
    if (stopLossSlider && stopLossBubble && stopLossValue) {
        stopLossSlider.addEventListener('input', function() {
            const value = this.value;
            stopLossBubble.textContent = value + '%';
            stopLossValue.textContent = value + '%';
            
            // 버블 위치 조정
            const percent = (value - this.min) / (this.max - this.min);
            const offset = percent * (this.offsetWidth - 20);
            stopLossBubble.style.left = offset + 'px';
        });
        
        // 초기 위치 설정
        stopLossSlider.dispatchEvent(new Event('input'));
    }
    
    // 이익실현 슬라이더
    const takeProfitSlider = document.getElementById('take-profit');
    const takeProfitBubble = document.getElementById('take-profit-bubble');
    const takeProfitValue = document.getElementById('take-profit-value');
    
    if (takeProfitSlider && takeProfitBubble && takeProfitValue) {
        takeProfitSlider.addEventListener('input', function() {
            const value = this.value;
            takeProfitBubble.textContent = value + '%';
            takeProfitValue.textContent = value + '%';
            
            // 버블 위치 조정
            const percent = (value - this.min) / (this.max - this.min);
            const offset = percent * (this.offsetWidth - 20);
            takeProfitBubble.style.left = offset + 'px';
        });
        
        // 초기 위치 설정
        takeProfitSlider.dispatchEvent(new Event('input'));
    }
    
    // 최대 포지션 크기 슬라이더
    const maxPositionSlider = document.getElementById('max-position');
    const maxPositionBubble = document.getElementById('max-position-bubble');
    const maxPositionValue = document.getElementById('max-position-value');
    
    if (maxPositionSlider && maxPositionBubble && maxPositionValue) {
        maxPositionSlider.addEventListener('input', function() {
            const value = this.value;
            maxPositionBubble.textContent = value + '%';
            maxPositionValue.textContent = value + '%';
            
            // 버블 위치 조정
            const percent = (value - this.min) / (this.max - this.min);
            const offset = percent * (this.offsetWidth - 20);
            maxPositionBubble.style.left = offset + 'px';
        });
        
        // 초기 위치 설정
        maxPositionSlider.dispatchEvent(new Event('input'));
    }
    
    // 초기 데이터 로드
    updateAllData();
    
    // 주기적 업데이트 설정 (30초마다)
    setInterval(updateAllData, 30000);
});

// 디버깅을 위한 전역 함수 노출
window.updateBalance = updateBalance;
window.updateSummary = updateSummary;
