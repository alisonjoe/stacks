#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

# ANSI color codes (Dracula theme)
INFO = "\033[38;2;139;233;253m"       # cyan
WARN = "\033[38;2;255;184;108m"       # orange
GOOD = "\033[38;2;80;250;123m"        # green
PINK = "\033[38;2;255;102;217m"       # pink
PURPLE = "\033[38;2;178;102;255m"     # purple
BG = "\033[48;2;40;42;54m"            # black background
PINKBG = "\033[48;2;255;102;217m"     # pink background
RESET = "\033[0m"                     # reset

def print_logo(version: str):
    """Display the super cool STACKS logo"""
    dashes = '─' * (52 - len(version))
    
    print(f"{BG}{PURPLE} ┌───────────────────────────────────────────────────────────┐ {RESET}")
    print(f"{BG}{PURPLE} │                                                           {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▄████▄ ████████  ▄█▄     ▄████▄  ██    ▄██ ▄████▄     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▀  ▀██   ██    ▄{PINKBG}{PURPLE}▄{BG}▀{PINKBG}▄{BG}{PINK}▄   ██▀  ▀██ ██  ▄██▀ ██▀  ▀██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▄        ██    █{PURPLE}█ █{PINK}█  ██        ██▄██▀   ██▄         {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▀████▄    ██   █{PURPLE}█   █{PINK}█ ██        ████      ▀████▄     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}         ▀██   ██   █{PURPLE}█   █{PINK}█ ██        ██▀██▄        ▀██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▄  ▄██   ██  █{PURPLE}█     █{PINK}█ ██▄  ▄██ ██  ▀██▄ ██▄  ▄██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▀████▀    ██  █{PURPLE}▀     ▀{PINK}█  ▀████▀  ██    ▀██ ▀████▀     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │                                                           {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} └{dashes}╢v{version}╟────┘ {RESET}")
    sys.stdout.flush()  # Force flush before exec

def ensure_directories():
    """Ensure essential directories exist"""
    dirs = [
        Path("/opt/stacks/config"),
        Path("/opt/stacks/logs"),
        Path("/opt/stacks/download")
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)

def setup_config():
    """Check and setup configuration file"""
    config_file = Path("/opt/stacks/config/config.yaml")
    default_config = Path("/opt/stacks/files/config.yaml")
    
    print(f"◼ {INFO}Checking configuration...{RESET}")
    sys.stdout.flush()
    
    if not config_file.exists():
        print(f"  {WARN}No config.yaml found - seeding default.{RESET}")
        sys.stdout.flush()
        shutil.copy2(default_config, config_file)
        config_file.chmod(0o600)
    else:
        print(f"  {GOOD}Found config.yaml at {config_file}.{RESET}")
        sys.stdout.flush()
    
    return str(config_file)

def main():
    """Main startup routine"""
    # Set UTF-8 encoding
    os.environ.setdefault('LANG', 'C.UTF-8')
    
    # Read version
    version_file = Path("/opt/stacks/VERSION")
    try:
        version = version_file.read_text().strip()
    except FileNotFoundError:
        version = "unknown"
    
    # Display logo
    print_logo(version)
    
    # Ensure directories exist
    ensure_directories()
    
    # Setup configuration
    config_path = setup_config()
    
    # Check for admin reset
    reset_admin = os.environ.get('RESET_ADMIN', 'false').lower() == 'true'
    if reset_admin:
        print(f"{WARN}! RESET_ADMIN=true detected - password will be reset!{RESET}")
        print()
        sys.stdout.flush()
    
    # Change to application directory
    os.chdir("/opt/stacks")
    
    # Start the server
    print(f"◼ {INFO}Starting Stacks...{RESET}")
    sys.stdout.flush()
    
    # Replace current process with stacks_server.py
    # This is the Python equivalent of `exec python3 stacks_server.py -c "$CONFIG_FILE"`
    os.execvp(sys.executable, [sys.executable, "stacks_server.py", "-c", config_path])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{WARN}Error during startup: {e}{RESET}", file=sys.stderr)
        sys.exit(1)