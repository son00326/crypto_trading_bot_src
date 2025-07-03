#!/usr/bin/env python3
"""
Comprehensive test script to verify end-to-end risk management integration
from strategy generation through order execution.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import required classes
from strategies import MovingAverageCrossover, RSIStrategy
from risk_manager import RiskManager
from trading_algorithm import TradingAlgorithm
from order_executor import OrderExecutor
from portfolio_manager import PortfolioManager
from data_collector import DataCollector
from db_manager import DatabaseManager

def create_sample_data(num_points=100):
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=num_points, freq='1H')
    np.random.seed(42)
    
    # Generate realistic price data
    base_price = 45000
    prices = []
    for i in range(num_points):
        change = np.random.normal(0, 0.01) * base_price
        if i > 0:
            base_price = prices[i-1] + change
        else:
            base_price = base_price + change
        prices.append(base_price)
    
    data = pd.DataFrame({
        'open': prices,
        'high': [p * 1.002 for p in prices],
        'low': [p * 0.998 for p in prices],
        'close': [p * (1 + np.random.uniform(-0.001, 0.001)) for p in prices],
        'volume': np.random.uniform(100, 1000, num_points)
    }, index=dates)
    
    return data

def test_strategy_position_sizing():
    """Test that strategies properly calculate suggested position sizes."""
    logger.info("=" * 60)
    logger.info("Testing Strategy Position Sizing")
    logger.info("=" * 60)
    
    # Create sample data
    data = create_sample_data()
    current_price = data['close'].iloc[-1]
    
    # Create strategy with risk parameters
    risk_params = {
        'stop_loss_pct': 0.02,      # 2% stop loss
        'take_profit_pct': 0.05,    # 5% take profit  
        'max_position_size': 0.3    # 30% max position
    }
    
    strategy = MovingAverageCrossover(
        short_period=10,
        long_period=20,
        stop_loss_pct=risk_params['stop_loss_pct'],
        take_profit_pct=risk_params['take_profit_pct'],
        max_position_size=risk_params['max_position_size']
    )
    
    # Generate signal
    portfolio = {
        'quote_balance': 10000,
        'base_balance': 0,
        'open_positions': []
    }
    
    signals_df = strategy.generate_signals(data)
    logger.info(f"Generated signals shape: {signals_df.shape}")
    
    # Check for suggested_position_size column
    if 'suggested_position_size' in signals_df.columns:
        last_suggested_size = signals_df['suggested_position_size'].iloc[-1]
        logger.info(f"✓ Strategy generated suggested_position_size: {last_suggested_size:.4f}")
    else:
        logger.error("✗ Strategy did not generate suggested_position_size column")
        return False
    
    # Generate trade signal
    signal = strategy.generate_signal(data, current_price, portfolio)
    
    if signal:
        logger.info(f"Trade signal generated:")
        logger.info(f"  Direction: {signal.direction}")
        logger.info(f"  Confidence: {signal.confidence}")
        logger.info(f"  Suggested quantity: {getattr(signal, 'suggested_quantity', 'Not set')}")
        
        if hasattr(signal, 'suggested_quantity'):
            logger.info("✓ TradeSignal includes suggested_quantity")
        else:
            logger.error("✗ TradeSignal missing suggested_quantity")
            return False
    else:
        logger.info("No trade signal generated (may be normal)")
    
    return True

def test_risk_manager_integration():
    """Test that RiskManager properly uses suggested quantities."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Risk Manager Integration")
    logger.info("=" * 60)
    
    # Create sample data and strategy
    data = create_sample_data()
    current_price = data['close'].iloc[-1]
    
    risk_params = {
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_position_size': 0.3
    }
    
    strategy = RSIStrategy(
        period=14,
        overbought=70,
        oversold=30,
        stop_loss_pct=risk_params['stop_loss_pct'],
        take_profit_pct=risk_params['take_profit_pct'],
        max_position_size=risk_params['max_position_size']
    )
    
    # Create risk manager
    risk_config = {
        'max_position_size_pct': risk_params['max_position_size'],
        'stop_loss_pct': risk_params['stop_loss_pct'],
        'take_profit_pct': risk_params['take_profit_pct'],
        'max_positions': 3,
        'max_drawdown': 0.15
    }
    
    risk_manager = RiskManager(risk_config)
    
    # Generate signal
    portfolio_status = {
        'quote_balance': 10000,
        'base_balance': 0,
        'open_positions': [],
        'positions': []
    }
    
    signals_df = strategy.generate_signals(data)
    signal = strategy.generate_signal(data, current_price, portfolio_status)
    
    if signal and hasattr(signal, 'suggested_quantity'):
        logger.info(f"Signal suggested quantity: {signal.suggested_quantity:.4f}")
        
        # Test risk assessment
        risk_assessment = risk_manager.assess_risk(
            signal=signal,
            portfolio_status=portfolio_status,
            current_price=current_price,
            leverage=1,
            market_type='spot'
        )
        
        logger.info(f"Risk assessment result:")
        logger.info(f"  Should execute: {risk_assessment['should_execute']}")
        logger.info(f"  Position size: {risk_assessment['position_size']}")
        logger.info(f"  Reason: {risk_assessment.get('reason', 'N/A')}")
        
        # Verify position size respects suggested quantity and limits
        if risk_assessment['should_execute']:
            if risk_assessment['position_size'] <= signal.suggested_quantity:
                logger.info("✓ Risk manager properly limited position size")
            else:
                logger.error("✗ Risk manager exceeded suggested quantity")
                return False
        
        return True
    else:
        logger.info("No signal with suggested quantity generated")
        return True

def test_trading_algorithm_flow():
    """Test the complete flow through TradingAlgorithm."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Trading Algorithm Flow")
    logger.info("=" * 60)
    
    # Mock objects for testing
    class MockExchangeAPI:
        def __init__(self):
            self.symbol = 'BTC/USDT'
        
        def fetch_ticker(self, symbol):
            return {'bid': 45000, 'ask': 45100, 'last': 45050}
    
    class MockDataCollector:
        def fetch_recent_data(self, limit):
            return create_sample_data(limit)
    
    class MockOrderExecutor:
        def __init__(self, *args, **kwargs):
            self.orders = []
            
        def execute_buy(self, price, quantity, portfolio, additional_info=None):
            logger.info(f"MockOrderExecutor.execute_buy called:")
            logger.info(f"  Price: {price}")
            logger.info(f"  Quantity: {quantity}")
            logger.info(f"  Additional info: {additional_info}")
            
            self.orders.append({
                'type': 'buy',
                'price': price,
                'quantity': quantity,
                'additional_info': additional_info
            })
            
            return {'success': True, 'order_id': 'test_order_123'}
        
        def execute_sell(self, price, quantity, portfolio, additional_info=None, close_position=False, position_id=None):
            logger.info(f"MockOrderExecutor.execute_sell called:")
            logger.info(f"  Price: {price}")
            logger.info(f"  Quantity: {quantity}")
            logger.info(f"  Additional info: {additional_info}")
            
            self.orders.append({
                'type': 'sell',
                'price': price,
                'quantity': quantity,
                'additional_info': additional_info
            })
            
            return {'success': True, 'order_id': 'test_order_124'}
    
    class MockPortfolioManager:
        def get_portfolio_status(self):
            return {
                'quote_balance': 10000,
                'base_balance': 0,
                'open_positions': [],
                'positions': []
            }
    
    class MockDatabaseManager:
        def __init__(self):
            pass
            
        def save_trade(self, *args, **kwargs):
            pass
            
        def get_bot_status(self):
            return None
            
        def save_bot_status(self, *args, **kwargs):
            pass
    
    # Create trading algorithm with risk parameters
    strategy_params = {
        'strategy': 'moving_average',
        'short_period': 10,
        'long_period': 20,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_position_size': 0.3
    }
    
    # Create trading algorithm
    algo = TradingAlgorithm(
        exchange_id='binance',
        symbol='BTC/USDT',
        timeframe='1h',
        strategy='MovingAverageCrossover',
        test_mode=True,
        strategy_params=strategy_params
    )
    
    # Replace components with mocks
    algo.data_collector = MockDataCollector()
    algo.order_executor = MockOrderExecutor(exchange_api, db_manager, 'BTC/USDT', True)
    algo.portfolio_manager = MockPortfolioManager()
    
    # Run one trading cycle
    logger.info("Running trading cycle...")
    algo.run()
    
    # Check if order was executed with proper parameters
    if algo.order_executor.orders:
        order = algo.order_executor.orders[0]
        logger.info(f"\n✓ Order executed:")
        logger.info(f"  Type: {order['type']}")
        logger.info(f"  Quantity: {order['quantity']}")
        
        # Check if risk assessment was included
        if order['additional_info'] and 'risk_assessment' in order['additional_info']:
            logger.info("✓ Risk assessment included in order info")
            risk_info = order['additional_info']['risk_assessment']
            logger.info(f"  Position size from risk: {risk_info.get('position_size', 'N/A')}")
        else:
            logger.error("✗ Risk assessment not included in order info")
            return False
            
        return True
    else:
        logger.info("No orders executed (may be normal if no signals)")
        return True

def main():
    """Run all integration tests."""
    logger.info("Starting Risk Management Integration Tests")
    logger.info("=" * 80)
    
    tests = [
        ("Strategy Position Sizing", test_strategy_position_sizing),
        ("Risk Manager Integration", test_risk_manager_integration),
        ("Trading Algorithm Flow", test_trading_algorithm_flow)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary:")
    logger.info("=" * 80)
    
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, success in results if success)
    total_tests = len(results)
    logger.info(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    return all(success for _, success in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
