import json
import subprocess
import os
import re
import socket
from datetime import datetime

#!/usr/bin/env python3
"""
Network Configuration Module

This module queries the network configuration of a Linux server and
creates a JSON file with detailed information about network interfaces,
IP addresses, VLANs, ethernet parameters, and routing information.
"""


def run_command(command):
    """Run shell command and return output"""
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Error executing command '{command}': {e}")
        return ""

def get_interfaces():
    """Get list of network interfaces"""
    output = run_command("ip -o link show")
    interfaces = []
    for line in output.split('\n'):
        if line:
            match = re.search(r'^[0-9]+: ([^:@]+)', line)
            if match:
                interfaces.append(match.group(1).strip())
    return interfaces

def get_ip_info(interface):
    """Get IP address information for an interface"""
    ip_info = {"ipv4": [], "ipv6": []}
    
    # Get IPv4 addresses
    output = run_command(f"ip -4 addr show {interface}")
    for line in output.split('\n'):
        match = re.search(r'inet\s+([0-9.]+)/(\d+)', line)
        if match:
            addr = match.group(1)
            prefix = match.group(2)
            broadcast = re.search(r'brd\s+([0-9.]+)', line)
            brd = broadcast.group(1) if broadcast else ""
            ip_info["ipv4"].append({
                "address": addr,
                "prefix": prefix,
                "broadcast": brd
            })
    
    # Get IPv6 addresses
    output = run_command(f"ip -6 addr show {interface}")
    for line in output.split('\n'):
        match = re.search(r'inet6\s+([0-9a-f:]+)/(\d+)', line)
        if match:
            ip_info["ipv6"].append({
                "address": match.group(1),
                "prefix": match.group(2)
            })
    
    return ip_info

def get_vlan_info(interface):
    """Get VLAN information for an interface"""
    vlan_info = {"is_vlan": False, "vlan_id": None, "parent": None}
    
    # Check if interface is a VLAN
    if "." in interface:
        parts = interface.split(".")
        if len(parts) == 2 and parts[1].isdigit():
            vlan_info["is_vlan"] = True
            vlan_info["vlan_id"] = parts[1]
            vlan_info["parent"] = parts[0]
    
    # Check using ip command
    output = run_command(f"ip -d link show {interface}")
    vlan_match = re.search(r'vlan\s+id\s+(\d+)', output)
    if vlan_match:
        vlan_info["is_vlan"] = True
        vlan_info["vlan_id"] = vlan_match.group(1)
    
    return vlan_info

def get_ethernet_params(interface):
    """Get ethernet parameters using ethtool"""
    eth_params = {}
    
    # Get link information
    output = run_command(f"ethtool {interface} 2>/dev/null")
    if output:
        speed_match = re.search(r'Speed:\s+([\d]+[A-Za-z]+)', output)
        if speed_match:
            eth_params["speed"] = speed_match.group(1)
        
        duplex_match = re.search(r'Duplex:\s+(\w+)', output)
        if duplex_match:
            eth_params["duplex"] = duplex_match.group(1)
        
        link_match = re.search(r'Link detected:\s+(\w+)', output)
        if link_match:
            eth_params["link_detected"] = link_match.group(1) == "yes"
    
    # Get driver information
    output = run_command(f"ethtool -i {interface} 2>/dev/null")
    if output:
        driver_match = re.search(r'driver:\s+(\S+)', output)
        if driver_match:
            eth_params["driver"] = driver_match.group(1)
        
        version_match = re.search(r'version:\s+(\S+)', output)
        if version_match:
            eth_params["driver_version"] = version_match.group(1)
    
    # Get MAC address
    output = run_command(f"ip link show {interface}")
    mac_match = re.search(r'link/\S+\s+([0-9a-f:]{17})', output)
    if mac_match:
        eth_params["mac_address"] = mac_match.group(1)
    
    return eth_params

def get_routes():
    """Get routing information"""
    routes = []
    output = run_command("ip route")
    for line in output.split('\n'):
        if line.strip():
            routes.append(line.strip())
    return routes

def get_network_config():
    """Get complete network configuration"""
    config = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "hostname": socket.gethostname()
        },
        "interfaces": {},
        "routes": get_routes()
    }
    
    for interface in get_interfaces():
        config["interfaces"][interface] = {
            "ip": get_ip_info(interface),
            "vlan": get_vlan_info(interface),
            "ethernet_params": get_ethernet_params(interface)
        }
    
    return config

def main():
    """Main function to collect network config and write to file"""
    config = get_network_config()
    
    output_file = "network_config.json"
    with open(output_file, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"Network configuration saved to {output_file}")

if __name__ == "__main__":
    main()