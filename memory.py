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

def read_node_hugepages() -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Read hugepages information from /sys/devices for each NUMA node.
    
    Returns:
        Dict with node IDs as keys, containing hugepage info for each size.
    """
    result = {}
    node_path = "/sys/devices/system/node"
    
    # Check if the path exists
    if not os.path.exists(node_path):
        print(f"Error: {node_path} not found. NUMA information unavailable.")
        return result
    
    # Find all node directories
    node_dirs = [d for d in os.listdir(node_path) if d.startswith("node")]
    
    for node_dir in node_dirs:
        node_id = node_dir.replace("node", "")
        hugepages_path = os.path.join(node_path, node_dir, "hugepages")
        
        if not os.path.exists(hugepages_path):
            continue
            
        result[node_id] = {}
        
        # Check for different hugepage sizes
        for size_dir in os.listdir(hugepages_path):
            # Extract size in kB from directory name (e.g., "hugepages-2048kB")
            match = re.match(r"hugepages-(\d+)kB", size_dir)
            if not match:
                continue
                
            size_kb = int(match.group(1))
            size_name = "1GB" if size_kb == 1048576 else "2MB" if size_kb == 2048 else f"{size_kb}kB"
            
            full_path = os.path.join(hugepages_path, size_dir)
            hugepage_info = {
                "size_kb": size_kb,
                "total": 0,
                "free": 0,
                "surplus": 0
            }
            
            # Read the values from files
            try:
                with open(os.path.join(full_path, "nr_hugepages"), 'r') as f:
                    hugepage_info["total"] = int(f.read().strip())
                
                with open(os.path.join(full_path, "free_hugepages"), 'r') as f:
                    hugepage_info["free"] = int(f.read().strip())
                    
                with open(os.path.join(full_path, "surplus_hugepages"), 'r') as f:
                    hugepage_info["surplus"] = int(f.read().strip())
            except (FileNotFoundError, ValueError) as e:
                print(f"Error reading hugepage info for node {node_id}, size {size_name}: {e}")
            
            result[node_id][size_name] = hugepage_info
    
    return result
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