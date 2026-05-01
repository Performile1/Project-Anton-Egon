#!/usr/bin/env python3
"""
Project Anton Egon - Calendar Integration Setup Script
Guides you through setting up Microsoft Graph and Google Calendar API credentials
"""

import os
import sys
from pathlib import Path


def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_step(step, description):
    """Print a step with numbering"""
    print(f"\n[STEP {step}] {description}")
    print("-" * 80)


def setup_microsoft_graph():
    """Setup Microsoft Graph API credentials"""
    print_section("MICROSOFT GRAPH API SETUP")
    
    print_step(1, "Create Azure AD Application")
    print("""
    1. Go to: https://portal.azure.com/
    2. Navigate to: Azure Active Directory > App registrations
    3. Click: New registration
    4. Name: "Anton Egon Calendar"
    5. Supported account types: "Accounts in this organizational directory only"
    6. Click: Register
    """)
    
    input("\nPress Enter after creating the Azure AD app...")
    
    print_step(2, "Get Application Details")
    print("""
    1. Copy the Application (client) ID
    2. Copy the Directory (tenant) ID
    3. Navigate to: Certificates & secrets > New client secret
    4. Name: "Anton Egon Secret"
    5. Expires: Select your preference
    6. Click: Add
    7. Copy the client secret (you won't see it again!)
    """)
    
    client_id = input("\nEnter Application (client) ID: ").strip()
    tenant_id = input("Enter Directory (tenant) ID: ").strip()
    client_secret = input("Enter Client secret: ").strip()
    
    print_step(3, "Configure API Permissions")
    print("""
    1. Navigate to: API permissions > Add a permission
    2. Select: Microsoft Graph
    3. Select: Application permissions (not delegated)
    4. Search for: "Calendar.Read"
    5. Select: Calendar.Read
    6. Click: Add permissions
    7. Click: Grant admin consent for [your organization]
    """)
    
    input("\nPress Enter after configuring permissions...")
    
    return {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "client_secret": client_secret
    }


def setup_google_calendar():
    """Setup Google Calendar API credentials"""
    print_section("GOOGLE CALENDAR API SETUP")
    
    print_step(1, "Create Google Cloud Project")
    print("""
    1. Go to: https://console.cloud.google.com/
    2. Click: Select a project > New project
    3. Name: "Anton Egon Calendar"
    4. Click: Create
    """)
    
    input("\nPress Enter after creating the project...")
    
    print_step(2, "Enable Calendar API")
    print("""
    1. Navigate to: APIs & Services > Library
    2. Search for: "Google Calendar API"
    3. Click: Enable
    """)
    
    input("\nPress Enter after enabling the API...")
    
    print_step(3, "Create OAuth 2.0 Credentials")
    print("""
    1. Navigate to: APIs & Services > Credentials
    2. Click: Create Credentials > OAuth client ID
    3. Application type: Desktop application
    4. Name: "Anton Egon Desktop"
    5. Click: Create
    6. Download the JSON file
    7. Save it as: credentials/google_calendar.json
    """)
    
    input("\nPress Enter after downloading credentials...")
    
    print_step(4, "Configure OAuth Consent Screen")
    print("""
    1. Navigate to: APIs & Services > OAuth consent screen
    2. Select: External (if not already configured)
    3. Fill in required fields (App name, User support email)
    4. Click: Save and Continue
    5. Skip Scopes (add later if needed)
    6. Add test users (your email)
    7. Click: Save and Continue
    """)
    
    input("\nPress Enter after configuring consent screen...")
    
    credentials_path = input("\nEnter path to credentials JSON (default: credentials/google_calendar.json): ").strip()
    if not credentials_path:
        credentials_path = "credentials/google_calendar.json"
    
    return {
        "credentials_path": credentials_path
    }


def update_env_file(microsoft_config, google_config):
    """Update .env file with credentials"""
    print_section("UPDATE .ENV FILE")
    
    env_path = Path(".env")
    env_example_path = Path(".env.example")
    
    # Create .env from .env.example if it doesn't exist
    if not env_path.exists() and env_example_path.exists():
        import shutil
        shutil.copy(env_example_path, env_path)
        print(f"Created .env from .env.example")
    
    # Read existing .env
    env_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()
    
    # Update or add Microsoft Graph credentials
    microsoft_keys = {
        "MICROSOFT_GRAPH_CLIENT_ID": microsoft_config["client_id"],
        "MICROSOFT_GRAPH_CLIENT_SECRET": microsoft_config["client_secret"],
        "MICROSOFT_GRAPH_TENANT_ID": microsoft_config["tenant_id"]
    }
    
    # Update or add Google Calendar credentials
    google_keys = {
        "GOOGLE_CALENDAR_CREDENTIALS_PATH": google_config["credentials_path"]
    }
    
    # Merge all keys
    all_keys = {**microsoft_keys, **google_keys}
    
    # Update env_lines
    updated_lines = []
    for line in env_lines:
        key = line.split("=")[0] if "=" in line else None
        if key in all_keys:
            updated_lines.append(f"{key}={all_keys[key]}\n")
            del all_keys[key]
        else:
            updated_lines.append(line)
    
    # Add new keys
    for key, value in all_keys.items():
        updated_lines.append(f"{key}={value}\n")
    
    # Write back
    with open(env_path, "w") as f:
        f.writelines(updated_lines)
    
    print(f"\n✅ Updated .env file with calendar credentials")


def update_config_file():
    """Update config/settings.json to enable calendar sync"""
    print_section("UPDATE CONFIG FILE")
    
    import json
    
    config_path = Path("config/settings.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Enable calendar sync
    config["calendar"]["enable_microsoft_graph"] = True
    config["calendar"]["enable_google_calendar"] = True
    
    # Enable calendar sync in orchestrator
    config["orchestrator"]["enable_calendar_sync"] = True
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Updated config/settings.json to enable calendar sync")


def create_credentials_directory():
    """Create credentials directory if it doesn't exist"""
    credentials_dir = Path("credentials")
    if not credentials_dir.exists():
        credentials_dir.mkdir(parents=True)
        print(f"✅ Created credentials directory")
    else:
        print(f"✅ Credentials directory already exists")


def main():
    """Main setup function"""
    print("\n" + "="*80)
    print("  ANTON EGON - CALENDAR INTEGRATION SETUP")
    print("="*80)
    print("\nThis script will guide you through setting up calendar integration")
    print("for Microsoft Graph (Outlook/Teams) and Google Calendar API.\n")
    
    input("Press Enter to continue...")
    
    # Create credentials directory
    create_credentials_directory()
    
    # Setup Microsoft Graph
    microsoft_config = setup_microsoft_graph()
    
    # Setup Google Calendar
    google_config = setup_google_calendar()
    
    # Update .env file
    update_env_file(microsoft_config, google_config)
    
    # Update config file
    update_config_file()
    
    print_section("SETUP COMPLETE")
    print("""
    ✅ Calendar integration setup complete!
    
    Next steps:
    1. Verify .env file has correct credentials
    2. Test calendar sync: python core/calendar_sync.py
    3. Start orchestrator with calendar enabled
    4. Check dashboard for daily agenda
    
    Troubleshooting:
    - Microsoft Graph: Ensure admin consent is granted
    - Google Calendar: Ensure credentials file is in correct path
    - Check logs/ for error messages
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during setup: {e}")
        sys.exit(1)
