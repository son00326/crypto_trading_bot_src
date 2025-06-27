#!/usr/bin/env python3
"""
Comprehensive bot status check script
Tests all major components without executing trades
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment():
    """Check environment variables"""
    print("\n=== Environment Check ===")
    required_vars = ['BINANCE_API_KEY', 'BINANCE_API_SECRET']
    
    all_present = True
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Missing")
            all_present = False
    
    return all_present

def check_imports():
    """Check if all major modules can be imported"""
    print("\n=== Module Import Check ===")
    modules_to_check = [
        ('src.trading_algorithm', 'TradingAlgorithm'),
        ('src.auto_position_manager', 'AutoPositionManager'),
        ('src.event_manager', 'EventManager'),
        ('src.portfolio_manager', 'PortfolioManager'),
        ('src.order_executor', 'OrderExecutor'),
        ('src.risk_manager', 'RiskManager'),
        ('utils.api', 'create_binance_client'),
        ('web_app.bot_api_server', 'BotAPIServer'),
    ]
    
    all_imported = True
    for module_name, class_name in modules_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✅ {module_name}.{class_name}")
        except Exception as e:
            print(f"❌ {module_name}.{class_name}: {str(e)}")
            all_imported = False
    
    return all_imported

def check_api_connection():
    """Check Binance API connection"""
    print("\n=== API Connection Check ===")
    try:
        from utils.api import create_binance_client
        
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            print("❌ API keys not found")
            return False
        
        # Test futures client
        client = create_binance_client(api_key, api_secret, is_future=True)
        
        # Check balance
        balance = client.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('total', 0)
        print(f"✅ Futures API connected")
        print(f"   Balance: {usdt_balance:.2f} USDT")
        
        # Check server time sync
        server_time = client.fetch_time()
        print(f"✅ Server time: {datetime.fromtimestamp(server_time/1000)}")
        
        # Check trading pair
        ticker = client.fetch_ticker('BTC/USDT')
        print(f"✅ BTC/USDT price: ${ticker['last']:,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ API connection failed: {str(e)}")
        return False

def check_database():
    """Check database connection"""
    print("\n=== Database Check ===")
    try:
        from src.db_manager import DatabaseManager
        
        db = DatabaseManager()
        
        # Check if database file exists
        import os
        if os.path.exists(db.db_path):
            print(f"✅ Database file exists: {db.db_path}")
        else:
            print(f"❌ Database file not found: {db.db_path}")
            return False
        
        # Try to get a connection
        try:
            from src.db_connection_manager import get_db_connection
            with get_db_connection(db.db_path) as (conn, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    print("✅ Database connected and queryable")
        except Exception as e:
            print(f"❌ Database connection error: {str(e)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def check_event_system():
    """Check event manager system"""
    print("\n=== Event System Check ===")
    try:
        from src.event_manager import EventManager, EventType
        
        em = EventManager()
        
        # Check all event types
        event_types_to_check = [
            'SYSTEM_RECOVERY',
            'TRADING_ERROR',
            'POSITION_OPENED',
            'STOP_LOSS_TRIGGERED',
            'TAKE_PROFIT_TRIGGERED'
        ]
        
        all_present = True
        for event_name in event_types_to_check:
            if hasattr(EventType, event_name):
                print(f"✅ EventType.{event_name}")
            else:
                print(f"❌ EventType.{event_name} missing")
                all_present = False
        
        return all_present
        
    except Exception as e:
        print(f"❌ Event system error: {str(e)}")
        return False

def check_sl_tp_functionality():
    """Check stop-loss/take-profit functionality"""
    print("\n=== Stop-Loss/Take-Profit Check ===")
    try:
        from utils.api import get_positions
        
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            print("❌ API keys not found")
            return False
        
        # Check current positions
        positions = get_positions(api_key, api_secret, 'BTCUSDT')
        
        if positions:
            print(f"✅ Found {len(positions)} open position(s)")
            for pos in positions:
                print(f"   Symbol: {pos['symbol']}, Size: {pos['contracts']}")
        else:
            print("✅ No open positions (SL/TP will activate on new positions)")
        
        # Verify SL/TP function exists
        from utils.api import set_stop_loss_take_profit
        print("✅ set_stop_loss_take_profit function available")
        
        return True
        
    except Exception as e:
        print(f"❌ SL/TP check failed: {str(e)}")
        return False

def main():
    """Run all checks"""
    print("=== Crypto Trading Bot Status Check ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'environment': check_environment(),
        'imports': check_imports(),
        'api': check_api_connection(),
        'database': check_database(),
        'events': check_event_system(),
        'sl_tp': check_sl_tp_functionality()
    }
    
    print("\n=== Summary ===")
    all_passed = all(results.values())
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check.capitalize()}: {status}")
    
    print("\n=== Overall Status ===")
    if all_passed:
        print("✅ All systems operational - Bot is ready to run!")
        print("\nTo start the bot:")
        print("1. For GUI mode: python main_gui.py")
        print("2. For CLI mode: python main.py")
        print("3. For API server: python -m web_app.bot_api_server")
    else:
        print("❌ Some checks failed - Please fix the issues above")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
