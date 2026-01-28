#!/usr/bin/env python3
"""
Simple test script to generate network traffic for testing netio_monitor.py

This script makes HTTP requests to generate observable network I/O.
Run this script, note its PID, then monitor it with netio_monitor.py
"""

import time
import urllib.request
import sys

def main():
    print(f"Test script PID: {os.getpid()}")
    print("This script will make HTTP requests every 5 seconds")
    print(f"Monitor with: sudo python3 netio_monitor.py {os.getpid()}")
    print("\nPress Ctrl+C to stop\n")
    
    urls = [
        "http://example.com",
        "http://httpbin.org/get",
        "http://www.google.com",
    ]
    
    count = 0
    while True:
        try:
            url = urls[count % len(urls)]
            print(f"[{count+1}] Fetching {url}...", end=" ", flush=True)
            
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read()
                print(f"OK ({len(data)} bytes)")
            
            count += 1
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n\nStopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    import os
    main()
