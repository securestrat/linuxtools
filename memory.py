#!/usr/bin/env python3
"""
Hugepages and Memory Information Collector

This module queries system information about 1GB and 2MB hugepages as well as
total memory and outputs the results in a JSON format to a timestamped file.
"""

import json
import os
import datetime
import re
from typing import Dict, Any


def read_meminfo() -> Dict[str, str]:
    """Read the /proc/meminfo file and return its contents as a dictionary."""
    result = {}
    
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                # Split the line into key and value
                parts = line.split(':')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    # Remove trailing "kB" and strip whitespace
                    value = parts[1].strip().split()[0]
                    result[key] = value
    except FileNotFoundError:
        print("Error: /proc/meminfo not found. This script requires a Linux system.")
    
    return result


def get_memory_info() -> Dict[str, Any]:
    """Gather information about hugepages and total memory."""
    meminfo = read_meminfo()
    
    # Initialize the result structure
    result = {
        "timestamp": datetime.datetime.now().isoformat(),
        "memory": {
            "total_kb": int(meminfo.get("MemTotal", 0)),
            "hugepages": {
                "1GB": {
                    "total": int(meminfo.get("HugePages_Total", 0)),
                    "free": int(meminfo.get("HugePages_Free", 0)),
                    "reserved": int(meminfo.get("HugePages_Rsvd", 0)),
                    "size_kb": int(meminfo.get("Hugepagesize", 0))
                },
                "2MB": {
                    "total": 0,
                    "free": 0,
                    "reserved": 0,
                    "size_kb": 2048
                }
            }
        }
    }
    
    # Check for 2MB hugepages - they might be listed as "Hugepage2MB" or similar
    for key in meminfo:
        if re.match(r"Hugepage(s_)?(2MB|2048kB).*", key):
            if key.endswith("Total"):
                result["memory"]["hugepages"]["2MB"]["total"] = int(meminfo[key])
            elif key.endswith("Free"):
                result["memory"]["hugepages"]["2MB"]["free"] = int(meminfo[key])
            elif key.endswith("Rsvd"):
                result["memory"]["hugepages"]["2MB"]["reserved"] = int(meminfo[key])
    
    return result


def save_to_file(data: Dict[str, Any]) -> str:
    """Save the memory information to a JSON file with timestamp in filename."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"memory_info_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filename


def main():
    """Main function to collect and save memory information."""
    memory_info = get_memory_info()
    filename = save_to_file(memory_info)
    print(f"Memory information saved to {filename}")


if __name__ == "__main__":
    main()