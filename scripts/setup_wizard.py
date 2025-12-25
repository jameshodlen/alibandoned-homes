#!/usr/bin/env python3
"""
Setup Wizard for Abandoned Homes Prediction System
==================================================

This script simplifies the deployment process for non-technical administrators.
It handles:
1. Prerequisite checking (Docker, Git)
2. Secure environment variable generation
3. Configuration of external services
4. Docker Compose build and launch
"""

import sys
import shutil
import secrets
import subprocess
import time
import os
from pathlib import Path

# ANSI colors for pretty output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def print_step(message):
    print(f"\n{GREEN}==> {message}{RESET}")

def print_warn(message):
    print(f"{YELLOW}WARNING: {message}{RESET}")

def print_error(message):
    print(f"{RED}ERROR: {message}{RESET}")

def check_command(command, name):
    try:
        subprocess.check_call([command, '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_prerequisites():
    print_step("Checking prerequisites...")
    
    deps = [
        ('docker', 'Docker'),
        ('git', 'Git'),
    ]
    
    missing = []
    for cmd, name in deps:
        if check_command(cmd, name):
            print(f"  [x] {name} is installed")
        else:
            print(f"  [ ] {name} is MISSING")
            missing.append(name)
            
    # Check for docker-compose (v1 or v2)
    if check_command('docker-compose', 'Docker Compose'):
        print("  [x] Docker Compose is installed")
    elif check_command('docker', 'Docker') and subprocess.run(['docker', 'compose', 'version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
         print("  [x] Docker Compose (plugin) is installed")
    else:
        print("  [ ] Docker Compose is MISSING")
        missing.append("Docker Compose")

    if missing:
        print_error(f"Please install the following tools before proceeding: {', '.join(missing)}")
        sys.exit(1)

def generate_env_file():
    print_step("Configuring Environment...")
    
    root_dir = Path(__file__).resolve().parent.parent
    env_example = root_dir / ".env.example"
    env_target = root_dir / ".env"
    
    if not env_example.exists():
        print_error(".env.example not found! Are you in the right directory?")
        sys.exit(1)

    if env_target.exists():
        response = input(f"{YELLOW}.env already exists. Overwrite? (y/N): {RESET}")
        if response.lower() != 'y':
            print("Skipping .env generation.")
            return

    # Read template
    with open(env_example, 'r') as f:
        content = f.read()

    # Generate Secrets
    api_key = secrets.token_hex(32)
    jwt_secret = secrets.token_hex(32)
    db_password = secrets.token_urlsafe(16)
    
    print("  [x] Generated secure API Key")
    print("  [x] Generated secure JWT Secret")
    print("  [x] Generated secure Database Password")

    # Replace placeholders
    # We assume standard placeholders based on .env.example
    # For a robust replacement, we'll manually reconstruct the file or use replace.
    # Simple replace approach:
    new_content = content.replace("generate_random_key_here", api_key)
    new_content = new_content.replace("another_random_key_here", jwt_secret)
    new_content = new_content.replace("change_this_secure_password", db_password)
    
    # Optional User Inputs
    mapbox_key = input("\nEnter Mapbox Public Token (Press Enter to skip): ").strip()
    if mapbox_key:
        new_content += f"\nREACT_APP_MAPBOX_TOKEN={mapbox_key}\n"
    
    sentinel_client = input("Enter Sentinel Hub Client ID (Press Enter to skip): ").strip()
    if sentinel_client:
        new_content = new_content.replace("SENTINEL_HUB_CLIENT_ID=", f"SENTINEL_HUB_CLIENT_ID={sentinel_client}")
        
    sentinel_secret = input("Enter Sentinel Hub Client Secret (Press Enter to skip): ").strip()
    if sentinel_secret:
        new_content = new_content.replace("SENTINEL_HUB_CLIENT_SECRET=", f"SENTINEL_HUB_CLIENT_SECRET={sentinel_secret}")

    # Write file
    with open(env_target, 'w') as f:
        f.write(new_content)
    
    print(f"  [x] wrote configuration to {env_target}")

def launch_application():
    print_step("Launching Application (this may take a few minutes)...")
    
    root_dir = Path(__file__).resolve().parent.parent
    
    # 1. Build
    print("  Building containers...")
    if subprocess.call(['docker-compose', 'build'], cwd=root_dir) != 0:
        print_error("Build failed.")
        sys.exit(1)
        
    # 2. Up
    print("  Starting services...")
    if subprocess.call(['docker-compose', 'up', '-d'], cwd=root_dir) != 0:
        print_error("Failed to start services.")
        sys.exit(1)
        
    # 3. Health Check Loop
    print("  Waiting for backend to be healthy...")
    retries = 30
    import urllib.request
    import urllib.error
    
    # Using backend URL from docker-compose defaults (localhost:8000)
    health_url = "http://localhost:8000/health"
    
    for i in range(retries):
        try:
            with urllib.request.urlopen(health_url) as response:
                if response.status == 200:
                    print(f"  {GREEN}[x] Backend is online!{RESET}")
                    break
        except Exception:
            time.sleep(2)
            sys.stdout.write(".")
            sys.stdout.flush()
    else:
        print_warn("Backend timed out, but containers are running. Check logs with 'make logs'.")

def main():
    print(f"""
{GREEN}================================================
   Abandoned Homes System - Setup Wizard
================================================{RESET}
""")
    
    check_prerequisites()
    generate_env_file()
    
    launch = input("\nReady to build and launch? (Y/n): ").strip()
    if launch.lower() == 'n':
        print("Setup completed without launching.")
    else:
        launch_application()
        
    print(f"""
{GREEN}================================================
   SUCCESS!
   
   Your application is ready at:
   Frontend: http://localhost:3000
   API Docs: http://localhost:8000/docs
   
   Common commands:
   - Stop app: docker-compose down
   - View logs: docker-compose logs -f
   
================================================{RESET}
""")

if __name__ == "__main__":
    main()
