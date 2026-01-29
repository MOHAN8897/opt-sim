"""
Real-time Log Monitoring Script
Watches backend logs and highlights important events

Usage:
    python monitor_logs.py

Or to watch from a specific point:
    python monitor_logs.py --tail 100
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# ANSI Colors
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    MAGENTA = '\033[35m'
    BLUE = '\033[34m'
    
    # Background
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'


def colorize_log_line(line: str) -> str:
    """Add colors to log lines based on content"""
    
    # Entry point
    if '📥' in line and 'ENTRY' in line:
        return f"{Colors.CYAN}{Colors.BOLD}{line}{Colors.RESET}"
    
    # Exit point
    if '📤' in line and 'EXIT' in line:
        return f"{Colors.GREEN}{Colors.BOLD}{line}{Colors.RESET}"
    
    # API calls
    if '✅' in line and ('GET' in line or 'POST' in line):
        return f"{Colors.GREEN}{line}{Colors.RESET}"
    
    if '❌' in line:
        return f"{Colors.RED}{Colors.BOLD}{line}{Colors.RESET}"
    
    if '⚠️' in line or '⚠' in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    # Market status
    if 'MARKET OPEN' in line:
        return f"{Colors.GREEN}{line}{Colors.RESET}"
    
    if 'MARKET CLOSED' in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    # Errors
    if 'ERROR' in line or 'error' in line:
        return f"{Colors.RED}{line}{Colors.RESET}"
    
    # Warnings
    if 'WARNING' in line or 'warning' in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    # Data flow
    if '━━━' in line:
        return f"{Colors.MAGENTA}{line}{Colors.RESET}"
    
    if '════' in line:
        return f"{Colors.MAGENTA}{Colors.BOLD}{line}{Colors.RESET}"
    
    return line


def watch_logs(log_file: str, tail: int = 0):
    """Watch log file and display with colors"""
    
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"{Colors.RED}❌ Log file not found: {log_file}{Colors.RESET}")
        return
    
    print(f"{Colors.CYAN}{Colors.BOLD}📊 BACKEND LOG MONITOR{Colors.RESET}")
    print(f"   Watching: {log_file}")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.MAGENTA}{'='*100}{Colors.RESET}\n")
    
    # Get initial line count
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Show last N lines if requested
    if tail > 0:
        print(f"{Colors.DIM}[Showing last {tail} lines]{Colors.RESET}\n")
        for line in lines[-tail:]:
            print(colorize_log_line(line), end='')
    
    last_line_count = len(lines)
    
    print(f"\n{Colors.YELLOW}[Monitoring... Press Ctrl+C to stop]{Colors.RESET}\n")
    
    try:
        while True:
            time.sleep(0.5)  # Check every 500ms
            
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    current_lines = f.readlines()
                
                # If new lines were added
                if len(current_lines) > last_line_count:
                    new_lines = current_lines[last_line_count:]
                    
                    for line in new_lines:
                        print(colorize_log_line(line), end='')
                    
                    last_line_count = len(current_lines)
            
            except Exception as e:
                print(f"{Colors.RED}Error reading log: {e}{Colors.RESET}")
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}[Monitor stopped]{Colors.RESET}")
        sys.exit(0)


def tail_logs(log_file: str, lines: int = 100):
    """Show last N lines of log file"""
    
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"{Colors.RED}❌ Log file not found: {log_file}{Colors.RESET}")
        return
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        print(f"{Colors.CYAN}{Colors.BOLD}📝 Last {lines} Log Lines{Colors.RESET}\n")
        
        for line in all_lines[-lines:]:
            print(colorize_log_line(line), end='')
    
    except Exception as e:
        print(f"{Colors.RED}Error reading log: {e}{Colors.RESET}")


def grep_logs(log_file: str, pattern: str):
    """Search logs for pattern"""
    
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"{Colors.RED}❌ Log file not found: {log_file}{Colors.RESET}")
        return
    
    print(f"{Colors.CYAN}{Colors.BOLD}🔍 Search Results for: {pattern}{Colors.RESET}\n")
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        matches = [line for line in lines if pattern.lower() in line.lower()]
        
        print(f"Found: {len(matches)} matches\n")
        
        for line in matches:
            print(colorize_log_line(line), end='')
    
    except Exception as e:
        print(f"{Colors.RED}Error reading log: {e}{Colors.RESET}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor backend logs with colors")
    parser.add_argument('--log', default='backend/backend.log', help='Log file path')
    parser.add_argument('--tail', type=int, default=0, help='Show last N lines')
    parser.add_argument('--search', help='Search for pattern')
    parser.add_argument('--watch', action='store_true', default=True, help='Watch continuously')
    
    args = parser.parse_args()
    
    if args.search:
        grep_logs(args.log, args.search)
    elif args.tail > 0:
        tail_logs(args.log, args.tail)
    else:
        watch_logs(args.log, tail=20)  # Show last 20 lines initially
