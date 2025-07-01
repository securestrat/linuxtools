#!/usr/bin/env python3
"""
Hugepages and Memory Information Collector

This module queries system information about hugepages from /sys/devices/system
and outputs the results in a JSON format to a timestamped file.
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

def read_system_memory() -> int:
    """Read the total memory from /sys/devices/system/memory"""
    total_kb = 0
    memory_path = "/sys/devices/system/memory"
    
    if not os.path.exists(memory_path):
        print(f"Error: {memory_path} not found. System memory information unavailable.")
        return total_kb
    
    # Count memory blocks and multiply by block size
    try:
        memory_blocks = [d for d in os.listdir(memory_path) if d.startswith("memory")]
        block_size_path = os.path.join(memory_path, "block_size_bytes")
        
        if os.path.exists(block_size_path):
            with open(block_size_path, 'r') as f:
                # Convert hex string to int and convert to KB
                block_size = int(f.read().strip(), 16) // 1024
                total_kb = len(memory_blocks) * block_size
    except (FileNotFoundError, ValueError) as e:
        print(f"Error reading system memory information: {e}")
    
    return total_kb

def get_memory_info() -> Dict[str, Any]:
    """Gather information about hugepages and total memory from /sys/devices/system."""
    hugepages_info = read_node_hugepages()
    total_memory = read_system_memory()
    
    result = {
        "timestamp": datetime.datetime.now().isoformat(),
        "memory": {
            "total_kb": total_memory,
            "numa_nodes": hugepages_info
        }
    }
    
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
