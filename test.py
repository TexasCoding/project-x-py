import time
from project_x_py import ProjectX, setup_logging
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

setup_logging()

try:
    # Initialize ProjectX client
    project_x = ProjectX(username="jeffw102", api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE=")
    
    # Get authentication details
    jwt_token = project_x.get_session_token()
    account = project_x.get_account_info()
    
    if not account:
        raise ValueError("No account found")
    
    print(f"Account ID: {account.id}")
    print(f"JWT Token length: {len(jwt_token) if jwt_token else 'None'}")
    print(f"JWT Token (first 50 chars): {jwt_token[:50] if jwt_token else 'None'}...")
    
    # Initialize real-time data manager
    realtime_client = ProjectXRealtimeDataManager(
        instrument="MNQ", 
        project_x=project_x, 
        account_id=str(account.id)
    )
    
    if realtime_client.initialize(initial_days=1):
        print("✅ Initialized realtime client")
        
        # Check if JWT token is valid before starting real-time feed
        if not jwt_token:
            print("❌ No JWT token available")
            exit(1)
            
        print(f"🔄 Starting real-time feed with JWT token...")
        success = realtime_client.start_realtime_feed(jwt_token)
        
        if success:
            print("✅ Real-time feed started successfully")
            
            # Test with shorter loop and better error handling
            for i in range(30):  # Run for 30 seconds
                try:
                    data = realtime_client.get_data("5min", bars=3)
                    if data is not None and len(data) > 0:
                        latest = data.tail(1)
                        latest_time = latest.select('timestamp').item()
                        latest_close = latest.select('close').item()
                        
                    else:
                        print(f"[{i:2d}] No data available")
                        
                    # Check if still connected
                    if hasattr(realtime_client, 'is_running') and not realtime_client.is_running:
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
        realtime_client.stop_realtime_feed()
        print("✅ Cleanup completed")
    except:
        pass