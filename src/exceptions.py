"""
Custom exceptions for the crypto trading bot
"""

class TradingBotException(Exception):
    """Base exception class for trading bot"""
    pass

class APIKeyError(TradingBotException):
    """Raised when API key is invalid or missing"""
    pass

class InsufficientBalanceError(TradingBotException):
    """Raised when account balance is insufficient for the operation"""
    pass

class InvalidOrderError(TradingBotException):
    """Raised when order parameters are invalid"""
    pass

class ExchangeConnectionError(TradingBotException):
    """Raised when unable to connect to the exchange"""
    pass

class OrderExecutionError(TradingBotException):
    """Raised when order execution fails"""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

class SymbolNotFoundError(TradingBotException):
    """Raised when trading symbol is not found"""
    pass

class APIError(TradingBotException):
    """General API error"""
    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

class RateLimitExceeded(TradingBotException):
    """Raised when rate limit is exceeded"""
    pass

class AuthenticationError(TradingBotException):
    """Raised when authentication fails"""
    pass

class NetworkError(TradingBotException):
    """Raised when network operation fails"""
    pass

class OrderNotFound(TradingBotException):
    """Raised when order is not found"""
    pass

class PositionNotFound(TradingBotException):
    """Raised when position is not found"""
    pass

class ConfigurationError(TradingBotException):
    """Raised when configuration is invalid"""
    pass
