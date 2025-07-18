import time

from project_x_py import ProjectX, create_trading_suite, setup_logging
from project_x_py.orderbook import OrderBook
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

setup_logging()

try:
    # Initialize ProjectX client
    project_x = ProjectX(
        username="jeffw102", api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE="
    )

    # Get authentication details
    jwt_token = project_x.get_session_token()
    account = project_x.get_account_info()

    if not account:
        raise ValueError("No account found")

    print(f"Account ID: {account.id}")
    print(f"JWT Token length: {len(jwt_token) if jwt_token else 'None'}")
    print(f"JWT Token (first 50 chars): {jwt_token[:50] if jwt_token else 'None'}...")

    suite = create_trading_suite(
        instrument="MNQ",
        project_x=project_x,
        jwt_token=jwt_token,
        account_id=str(account.id),
        timeframes=["5sec"],
    )

    realtime_client: ProjectXRealtimeClient = suite["realtime_client"]
    data_manager: ProjectXRealtimeDataManager = suite["data_manager"]
    orderbook: OrderBook = suite["orderbook"]

    if realtime_client.connect():
        print("✅ Initialized realtime client")

        # Check if JWT token is valid before starting real-time feed
        if not jwt_token:
            print("❌ No JWT token available")
            exit(1)

        print("🔄 Starting real-time feed with JWT token...")
        success = data_manager.initialize(initial_days=1)

        if success:
            print("✅ Real-time feed started successfully")

        data_success = data_manager.start_realtime_feed()
        if data_success:
            print("✅ Real-time feed started successfully")
        else:
            print("❌ Failed to start real-time feed")
            exit(1)

        realtime_client.add_callback("market_depth", orderbook.process_market_depth)

        # Test with shorter loop and better error handling
        for i in range(30):  # Run for 30 seconds
            try:
                data = data_manager.get_data("5sec", bars=3)
                if data is not None and len(data) > 0:
                    latest = data.tail(1)
                    latest_time = latest.select("timestamp").item()
                    latest_close = latest.select("close").item()
                    # print(f"[{i:2d}] Latest close: {latest_close}")
                else:
                    print(f"[{i:2d}] No data available")

                print(orderbook.get_orderbook_snapshot())
                # Check if still connected
                if hasattr(data_manager, "is_running") and not data_manager.is_running:
                    print("❌ Real-time feed stopped running")
                    break

            except Exception as e:
                print(f"❌ Error getting data: {e}")

            time.sleep(1)

        else:
            print("❌ Failed to start real-time feed")

    else:
        print("❌ Failed to initialize realtime client")

except KeyboardInterrupt:
    print("\n🛑 Stopping...")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
finally:
    try:
        data_manager.stop_realtime_feed()
        print("✅ Cleanup completed")
    except Exception:
        pass
