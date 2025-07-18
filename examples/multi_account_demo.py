#!/usr/bin/env python3
"""
Multi-Account Support Demo

This example demonstrates the enhanced multi-account functionality in ProjectX:
1. List all available accounts
2. Select specific accounts by name
3. Work with multiple accounts simultaneously
4. Handle account selection errors gracefully

Author: TexasCoding
Date: June 2025
"""

from project_x_py import ProjectX, create_client


def demonstrate_account_listing():
    """Demonstrate listing all available accounts."""
    print("=" * 60)
    print("📋 ACCOUNT LISTING DEMONSTRATION")
    print("=" * 60)

    try:
        # Create client without specifying account (will use first account)
        client = ProjectX.from_env()

        # List all available accounts
        print("\n🔍 Listing all available accounts:")
        accounts = client.list_accounts()

        if not accounts:
            print("   ❌ No accounts found")
            return

        print(f"   ✅ Found {len(accounts)} account(s):")
        for i, account in enumerate(accounts, 1):
            print(f"\n   {i}. Account: {account.get('name', 'Unnamed')}")
            print(f"      ID: {account.get('id')}")
            print(f"      Balance: ${account.get('balance', 0):,.2f}")
            print(f"      Can Trade: {account.get('canTrade', False)}")
            print(f"      Status: {account.get('status', 'Unknown')}")

        # Show currently selected account
        current_account = client.get_account_info()
        if current_account:
            print(f"\n💡 Currently selected account: {current_account.name}")

        return accounts

    except Exception as e:
        print(f"❌ Error listing accounts: {e}")
        return []


def demonstrate_account_selection(available_accounts):
    """Demonstrate selecting specific accounts by name."""
    print("\n" + "=" * 60)
    print("🎯 ACCOUNT SELECTION DEMONSTRATION")
    print("=" * 60)

    if not available_accounts:
        print("❌ No accounts available for selection demo")
        return

    # Try to select each available account by name
    for account in available_accounts:
        account_name = account.get("name")
        if not account_name:
            continue

        print(f"\n🔄 Selecting account: '{account_name}'")

        try:
            # Create client with specific account name
            client = ProjectX.from_env(account_name=account_name)

            # Verify the correct account was selected
            selected_account = client.get_account_info()
            if selected_account:
                print(f"   ✅ Successfully selected: {selected_account.name}")
                print(f"   Account ID: {selected_account.id}")
                print(f"   Balance: ${selected_account.balance:,.2f}")

                # Get some account-specific data
                positions = client.search_open_positions()
                print(f"   Open positions: {len(positions)}")

            else:
                print(f"   ❌ Failed to select account: {account_name}")

        except Exception as e:
            print(f"   ❌ Error selecting account '{account_name}': {e}")


def demonstrate_invalid_account_selection():
    """Demonstrate handling of invalid account names."""
    print("\n" + "=" * 60)
    print("⚠️ INVALID ACCOUNT HANDLING")
    print("=" * 60)

    invalid_account_name = "NonExistent Account"
    print(f"\n🚫 Attempting to select invalid account: '{invalid_account_name}'")

    try:
        # Try to create client with invalid account name
        client = ProjectX.from_env(account_name=invalid_account_name)

        # Try to get account info
        account = client.get_account_info()
        if account:
            print(f"   ❌ Unexpected: Got account {account.name}")
        else:
            print(f"   ✅ Correctly handled: No account returned")

    except Exception as e:
        print(f"   ✅ Correctly handled error: {e}")


def demonstrate_environment_variable_setup():
    """Show how to set up environment variables for account selection."""
    print("\n" + "=" * 60)
    print("🔧 ENVIRONMENT VARIABLE SETUP")
    print("=" * 60)

    print("\n💡 To use account selection with environment variables:")
    print("   export PROJECT_X_API_KEY='your_api_key'")
    print("   export PROJECT_X_USERNAME='your_username'")
    print("   export PROJECT_X_ACCOUNT_NAME='Your Account Name'  # Optional")

    print("\n💡 Then create client:")
    print("   from project_x_py import ProjectX")
    print("   client = ProjectX.from_env()  # Uses PROJECT_X_ACCOUNT_NAME if set")

    print("\n💡 Or override the environment variable:")
    print("   client = ProjectX.from_env(account_name='Different Account')")

    print("\n💡 Using the convenience function:")
    print("   from project_x_py import create_client")
    print("   client = create_client(account_name='Specific Account')")


def demonstrate_multiple_account_operations():
    """Demonstrate working with multiple accounts simultaneously."""
    print("\n" + "=" * 60)
    print("🔄 MULTIPLE ACCOUNT OPERATIONS")
    print("=" * 60)

    try:
        # Get list of accounts first
        temp_client = ProjectX.from_env()
        accounts = temp_client.list_accounts()

        if len(accounts) < 2:
            print("   ⚠️ Need at least 2 accounts for multi-account demo")
            print(f"   Only {len(accounts)} account(s) available")
            return

        print(f"\n🔄 Working with {len(accounts)} accounts simultaneously:")

        account_clients = {}

        # Create separate clients for each account
        for account in accounts[:3]:  # Limit to first 3 accounts
            account_name = account.get("name")
            if account_name:
                try:
                    client = ProjectX.from_env(account_name=account_name)
                    account_info = client.get_account_info()
                    if account_info:
                        account_clients[account_name] = client
                        print(f"   ✅ Connected to: {account_name}")
                except Exception as e:
                    print(f"   ❌ Failed to connect to {account_name}: {e}")

        # Perform operations on each account
        print(f"\n📊 Summary across {len(account_clients)} accounts:")
        total_balance = 0
        total_positions = 0

        for account_name, client in account_clients.items():
            try:
                account = client.get_account_info()
                positions = client.search_open_positions()

                print(f"   {account_name}:")
                print(f"     Balance: ${account.balance:,.2f}")
                print(f"     Positions: {len(positions)}")

                total_balance += account.balance
                total_positions += len(positions)

            except Exception as e:
                print(f"     ❌ Error: {e}")

        print(f"\n💰 Total Balance Across Accounts: ${total_balance:,.2f}")
        print(f"📈 Total Open Positions: {total_positions}")

    except Exception as e:
        print(f"❌ Multi-account operations error: {e}")


def main():
    """Main demonstration function."""
    print("🚀 ProjectX Multi-Account Support Demo")
    print("=" * 60)
    print("Demonstrating enhanced account selection and management")

    try:
        # 1. List all available accounts
        accounts = demonstrate_account_listing()

        # 2. Demonstrate account selection by name
        demonstrate_account_selection(accounts)

        # 3. Show invalid account handling
        demonstrate_invalid_account_selection()

        # 4. Show environment variable setup
        demonstrate_environment_variable_setup()

        # 5. Demonstrate multiple account operations
        demonstrate_multiple_account_operations()

        print("\n" + "=" * 60)
        print("✅ MULTI-ACCOUNT DEMO COMPLETED")
        print("=" * 60)
        print("\n🎯 Key Features:")
        print("• List all available accounts with details")
        print("• Select specific accounts by name")
        print("• Environment variable support for account selection")
        print("• Graceful handling of invalid account names")
        print("• Support for working with multiple accounts simultaneously")
        print("• Backward compatibility - uses first account if none specified")

        print("\n💡 This enables professional multi-account trading workflows!")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("\n💡 Make sure your ProjectX API credentials are configured:")
        print("   export PROJECT_X_API_KEY='your_api_key'")
        print("   export PROJECT_X_USERNAME='your_username'")


if __name__ == "__main__":
    main()
