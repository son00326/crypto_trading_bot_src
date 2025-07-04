# Logging Standardization Guidelines

## 1. Log Level Usage

### INFO Level
- **Purpose**: Normal operational messages and state changes
- **When to use**:
  - Module initialization/shutdown
  - Major operations start/completion
  - Configuration changes
  - Successful transactions
  - System state changes
  
### WARNING Level
- **Purpose**: Recoverable issues and degraded functionality
- **When to use**:
  - Missing optional configuration
  - Retryable failures
  - Performance degradation
  - Non-critical API errors
  - Deprecated feature usage

### ERROR Level
- **Purpose**: Critical failures requiring attention
- **When to use**:
  - Failed operations that cannot recover
  - Missing required configuration
  - API authentication failures
  - Data corruption/loss
  - Unhandled exceptions

### DEBUG Level
- **Purpose**: Detailed diagnostic information
- **When to use**:
  - Function entry/exit
  - Variable values and state
  - Detailed API responses
  - Performance metrics
  - Stack traces (with ERROR level)

## 2. Message Format Standards

### Module Prefix
All log messages should be prefixed with the module name for easy filtering:
```python
logger.info(f"[{self.__class__.__name__}] Operation completed successfully")
```

### Structured Messages
Use consistent formatting for similar operations:

#### Initialization
```python
logger.info(f"{self.__class__.__name__} 초기화 시작:")
logger.info(f"- parameter1: {value1}")
logger.info(f"- parameter2: {value2}")
logger.info(f"{self.__class__.__name__} 초기화 완료")
```

#### Operation Start/End
```python
logger.info("=" * 60)
logger.info("작업 설명")
logger.info(f"  - 매개변수1: {value1}")
logger.info(f"  - 매개변수2: {value2}")
logger.info("=" * 60)
# ... operation ...
logger.info("작업 완료")
```

#### Error Handling
```python
try:
    # operation
except Exception as e:
    logger.error(f"작업 실패: {str(e)}")
    logger.debug(traceback.format_exc())
```

## 3. Structured Logging (Future Implementation)

### JSON Format
For production environments, implement structured logging:
```python
logger.info({
    "event": "position_opened",
    "symbol": symbol,
    "side": side,
    "amount": amount,
    "price": price,
    "timestamp": datetime.utcnow().isoformat()
})
```

### Benefits
- Easy parsing and filtering
- Better integration with log aggregation systems
- Consistent field names across logs
- Machine-readable format

## 4. Context Information

Always include relevant context in log messages:
- User/Session ID
- Transaction/Order ID
- Symbol/Market
- Timestamp
- Error codes
- Performance metrics

## 5. Best Practices

### DO:
- Log at appropriate levels
- Include context and identifiers
- Use consistent message formats
- Log both success and failure
- Include timing for long operations

### DON'T:
- Log sensitive information (API keys, passwords)
- Use print() statements
- Log excessively in loops
- Mix languages in log messages
- Log at INFO level in performance-critical paths

## 6. Examples

### Good Examples:
```python
# Module initialization
logger.info(f"TradingAlgorithm 초기화: symbol={symbol}, strategy={strategy}, leverage={leverage}")

# Operation success
logger.info(f"포지션 개설 성공: {symbol} {side} {amount}@{price}, order_id={order_id}")

# Warning
logger.warning(f"API 요청 재시도 ({retry_count}/{max_retries}): {error_message}")

# Error with context
logger.error(f"포지션 청산 실패: position_id={position_id}, reason={error}")
logger.debug(f"상세 오류: {traceback.format_exc()}")
```

### Bad Examples:
```python
# Too generic
logger.info("Operation completed")

# Missing context
logger.error("Failed")

# Sensitive information
logger.info(f"API Key: {api_key}")

# Wrong level
logger.info(f"CRITICAL ERROR: System crashed!")  # Should be ERROR
logger.error("Starting application")  # Should be INFO
```

## 7. Implementation Checklist

- [ ] Review all logger.* calls for appropriate level
- [ ] Add module prefix to all log messages
- [ ] Remove print() statements
- [ ] Add context to error messages
- [ ] Implement consistent formatting
- [ ] Add performance logging for slow operations
- [ ] Document any module-specific logging patterns
- [ ] Configure log rotation and retention policies
- [ ] Set up log aggregation for production
