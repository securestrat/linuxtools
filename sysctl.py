import subprocess
import json
import os
import socket
import datetime
import logging
from typing import Dict, List, Any, Optional

#!/usr/bin/env python3
"""
Module to query sysctl and network settings on Linux systems and save to JSON.
"""


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command: str) -> Optional[str]:
    """
    Run a shell command and return its output.
    
    Args:
        command: The command to execute
        
    Returns:
        The command output or None if error
    """
    try:
        result = subprocess.run(command, shell=True, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        return result.stdout
    except subprocess.SubprocessError as e:
        logger.error(f"Error running command '{command}': {e}")
        return None

def get_sysctl_params() -> Dict[str, str]:
    """
    Query and return all sysctl parameters.
    
    Returns:
        Dictionary of sysctl parameters
    """
    output = run_command("sysctl -a")
    if not output:
        return {}
    
    params = {}
    for line in output.splitlines():
        try:
            key, value = line.split("=", 1)
            params[key.strip()] = value.strip()
        except ValueError:
            continue
    
    return params

def get_network_interfaces() -> Dict[str, Dict[str, Any]]:
    """
    Get information about network interfaces.
    
    Returns:
        Dictionary with interface information
    """
    interfaces = {}
    
    # Get list of interfaces
    output = run_command("ls /sys/class/net/")
    if not output:
        return interfaces
    
    for interface in output.splitlines():
        interface = interface.strip()
        interfaces[interface] = {}
        
        # Get interface details
        ip_output = run_command(f"ip addr show {interface}")
        if ip_output:
            interfaces[interface]["ip_info"] = ip_output
        
        # Get interface stats
        if os.path.exists(f"/sys/class/net/{interface}/statistics"):
            rx_bytes = run_command(f"cat /sys/class/net/{interface}/statistics/rx_bytes")
            tx_bytes = run_command(f"cat /sys/class/net/{interface}/statistics/tx_bytes")
            
            if rx_bytes:
                interfaces[interface]["rx_bytes"] = rx_bytes.strip()
            if tx_bytes:
                interfaces[interface]["tx_bytes"] = tx_bytes.strip()
    
    return interfaces

def get_routing_table() -> List[Dict[str, str]]:
    """
    Get the routing table information.
    
    Returns:
        List of routing table entries
    """
    output = run_command("ip route")
    if not output:
        return []
    
    routes = []
    for line in output.splitlines():
        routes.append({"route": line.strip()})
    
    return routes

def get_dns_settings() -> Dict[str, Any]:
    """
    Get DNS configuration.
    
    Returns:
        Dictionary with DNS information
    """
    dns_info = {}
    
    # Get DNS servers from resolv.conf
    if os.path.exists("/etc/resolv.conf"):
        output = run_command("cat /etc/resolv.conf")
        if output:
            nameservers = []
            for line in output.splitlines():
                if line.startswith("nameserver"):
                    nameservers.append(line.split()[1])
            dns_info["nameservers"] = nameservers
    
    # Try to get hostname information
    try:
        dns_info["hostname"] = socket.gethostname()
        dns_info["fqdn"] = socket.getfqdn()
    except Exception as e:
        logger.error(f"Error getting hostname information: {e}")
    
    return dns_info

def collect_system_info() -> Dict[str, Any]:
    """
    Collect all system information.
    
    Returns:
        Dictionary with all collected system information
    """
    system_info = {
        "timestamp": datetime.datetime.now().isoformat(),
        "sysctl": get_sysctl_params(),
        "network": {
            "interfaces": get_network_interfaces(),
            "routing": get_routing_table(),
            "dns": get_dns_settings()
        }
    }
    
    return system_info

def save_to_json(data: Dict[str, Any], filename: str) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        data: The data to save
        filename: The filename to save to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Data successfully written to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error writing to {filename}: {e}")
        return False

def main():
    """Main function to run the script."""
    # Generate a filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"system_info_{timestamp}.json"
    
    # Collect system information
    logger.info("Collecting system information...")
    system_info = collect_system_info()
    
    # Save to JSON file
    save_to_json(system_info, filename)

if __name__ == "__main__":
    main()