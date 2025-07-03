#!/usr/bin/env python3
"""
Simplified test to verify risk management flow through strategies and risk manager.
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
from strategies import MovingAverageCrossover, RSIStrategy, BollingerBandsStrategy
from risk_manager import RiskManager
from models.trade_signal import TradeSignal

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

def test_strategy_suggested_position():
    """Test that strategies generate suggested position sizes."""
    logger.info("=" * 60)
    logger.info("Testing Strategy Suggested Position Sizes")
    logger.info("=" * 60)
    
    # Test parameters
    risk_params = {
        'stop_loss_pct': 0.02,      # 2% stop loss
        'take_profit_pct': 0.05,    # 5% take profit  
        'max_position_size': 0.3    # 30% max position
    }
    
    strategies_to_test = [
        MovingAverageCrossover(
            short_period=10,
            long_period=20,
            stop_loss_pct=risk_params['stop_loss_pct'],
            take_profit_pct=risk_params['take_profit_pct'],
            max_position_size=risk_params['max_position_size']
        ),
        RSIStrategy(
            period=14,
            overbought=70,
            oversold=30,
            stop_loss_pct=risk_params['stop_loss_pct'],
            take_profit_pct=risk_params['take_profit_pct'],
            max_position_size=risk_params['max_position_size']
        ),
        BollingerBandsStrategy(
            period=20,
            std_dev=2,
            stop_loss_pct=risk_params['stop_loss_pct'],
            take_profit_pct=risk_params['take_profit_pct'],
            max_position_size=risk_params['max_position_size']
        )
    ]
    
    # Create sample data
    data = create_sample_data()
    current_price = data['close'].iloc[-1]
    
    portfolio = {
        'quote_balance': 10000,
        'base_balance': 0,
        'open_positions': []
    }
    
    results = []
    
    for strategy in strategies_to_test:
        logger.info(f"\nTesting {strategy.__class__.__name__}...")
        
        try:
            # Generate signals dataframe
            signals_df = strategy.generate_signals(data)
            
            # Check if suggested_position_size column exists
            if 'suggested_position_size' in signals_df.columns:
                last_suggested = signals_df['suggested_position_size'].iloc[-1]
                logger.info(f"✓ {strategy.__class__.__name__}: suggested_position_size = {last_suggested:.4f}")
                
                # Generate trade signal
                signal = strategy.generate_signal(data, current_price, portfolio)
                
                if signal:
                    if hasattr(signal, 'suggested_quantity') and signal.suggested_quantity is not None:
                        logger.info(f"  Trade signal: {signal.direction}, suggested_quantity = {signal.suggested_quantity:.4f}")
                        results.append((strategy.__class__.__name__, True, signal.suggested_quantity))
                    else:
                        logger.error(f"  ✗ TradeSignal missing or None suggested_quantity")
                        results.append((strategy.__class__.__name__, False, None))
                else:
                    logger.info(f"  No trade signal generated (position = 0)")
                    results.append((strategy.__class__.__name__, True, 0))
            else:
                logger.error(f"✗ {strategy.__class__.__name__}: missing suggested_position_size column")
                results.append((strategy.__class__.__name__, False, None))
                
        except Exception as e:
            logger.error(f"✗ {strategy.__class__.__name__} error: {e}")
            results.append((strategy.__class__.__name__, False, None))
    
    return results

def test_risk_manager_uses_suggested():
    """Test that RiskManager properly uses suggested quantities."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Risk Manager Uses Suggested Quantities")
    logger.info("=" * 60)
    
    # Create risk manager
    risk_config = {
        'max_position_size_pct': 0.3,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_positions': 3,
        'max_drawdown': 0.15
    }
    
    risk_manager = RiskManager(risk_config)
    
    # Test different scenarios
    test_cases = [
        {
            'name': 'Normal case - suggested within limits',
            'signal': TradeSignal(
                symbol='BTC/USDT',
                direction='buy',
                price=45000,
                strategy_name='test',
                confidence=0.8,
                strength=0.8,
                suggested_quantity=0.1
            ),
            'portfolio': {'quote_balance': 10000, 'open_positions': []},
            'current_price': 45000,
            'expected_size': 0.1
        },
        {
            'name': 'Suggested exceeds max position',
            'signal': TradeSignal(
                symbol='BTC/USDT',
                direction='buy',
                price=45000,
                strategy_name='test',
                confidence=0.9,
                strength=0.9,
                suggested_quantity=0.5  # Exceeds 30% max
            ),
            'portfolio': {'quote_balance': 10000, 'open_positions': []},
            'current_price': 45000,
            'expected_size': 0.3  # Should be capped at max
        },
        {
            'name': 'No suggested quantity',
            'signal': TradeSignal(
                symbol='BTC/USDT',
                direction='buy',
                price=45000,
                strategy_name='test',
                confidence=0.7,
                strength=0.7
                # No suggested_quantity
            ),
            'portfolio': {'quote_balance': 10000, 'open_positions': []},
            'current_price': 45000,
            'expected_size': None  # Will use internal calculation
        }
    ]
    
    results = []
    
    for case in test_cases:
        logger.info(f"\nTest case: {case['name']}")
        
        risk_assessment = risk_manager.assess_risk(
            signal=case['signal'],
            portfolio_status=case['portfolio'],
            current_price=case['current_price'],
            leverage=1,
            market_type='spot'
        )
        
        logger.info(f"  Should execute: {risk_assessment['should_execute']}")
        logger.info(f"  Position size: {risk_assessment['position_size']}")
        
        if case['expected_size'] is not None:
            if risk_assessment['should_execute'] and abs(risk_assessment['position_size'] - case['expected_size']) < 0.0001:
                logger.info(f"  ✓ Position size matches expected: {case['expected_size']}")
                results.append((case['name'], True))
            else:
                logger.error(f"  ✗ Position size mismatch: expected {case['expected_size']}, got {risk_assessment['position_size']}")
                results.append((case['name'], False))
        else:
            # Just check that it executed
            logger.info(f"  Internal calculation used (no suggested quantity)")
            results.append((case['name'], risk_assessment['should_execute']))
    
    return results

def main():
    """Run all tests."""
    logger.info("Starting Simplified Risk Management Flow Tests")
    logger.info("=" * 80)
    
    all_results = []
    
    # Test 1: Strategy suggested positions
    logger.info("\n=== TEST 1: Strategy Suggested Positions ===")
    strategy_results = test_strategy_suggested_position()
    all_results.extend([(f"Strategy-{name}", success) for name, success, _ in strategy_results])
    
    # Test 2: Risk manager usage
    logger.info("\n=== TEST 2: Risk Manager Usage ===")
    risk_results = test_risk_manager_uses_suggested()
    all_results.extend(risk_results)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary:")
    logger.info("=" * 80)
    
    for test_name, success in all_results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, success in all_results if success)
    total_tests = len(all_results)
    logger.info(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    # Show position size flow
    logger.info("\n" + "=" * 80)
    logger.info("Position Size Flow Summary:")
    logger.info("=" * 80)
    logger.info("1. Strategy calculates suggested_position_size based on:")
    logger.info("   - Signal strength/confidence")
    logger.info("   - Market volatility")
    logger.info("   - max_position_size parameter")
    logger.info("2. Strategy includes suggested_quantity in TradeSignal")
    logger.info("3. RiskManager uses suggested_quantity if available")
    logger.info("4. RiskManager applies additional limits:")
    logger.info("   - Global max position size")
    logger.info("   - Account balance constraints")
    logger.info("   - Number of open positions")
    logger.info("5. Final position_size passed to OrderExecutor")
    
    return all(success for _, success in all_results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
