#!/usr/bin/env python3
"""
AMD Solarflare system report tool

SPDX-License-Identifier: GPL-2.0-only
Copyright (C) 2022-2023, Advanced Micro Devices, Inc.
Copyright (C) 2019-2022, Xilinx, Inc.
Copyright (C) 2007-2019, Solarflare Communications.
"""

import os
import sys
import struct
import socket
import fcntl
import time
import re
import subprocess
import glob
import hashlib
import argparse
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, Union

# Constants
VERSION = "4.16.1"
DATE = time.strftime("%c")

# Driver/device identifiers
DRIVER_NAME_RE = r'sfc\w*|onload|xilinx_efct'
RPM_NAME_PREFIXES = [
    'kernel-module-sfc-', 'kmod-solarflare-sfc-', 'sfc-dkms', 'sfutils',
    'onload', 'openonload', 'enterpriseonload', 'solar_capture', 'sfptp',
    'kernel-module-xilinx-efct', 'tcpdirect'
]
DEB_NAME_PREFIXES = [
    'sfc-modules-', 'xilinx-efct', 'onload', 'enterpriseonload',
    'tcpdirect', 'sfptp'
]

EFX_VENDID_SFC = 0x1924
EFX_VENDID_XILINX = 0x10ee

# Format constants
FORMAT_TEXT = 0
FORMAT_HTML = 1
FORMAT_MINIMAL = 2
FORMAT_JSON = 3

# Table formatting
GUTTER_WIDTH = 2
ORIENT_HORIZ = 0
ORIENT_VERT = 1
VALUES_FORMAT_DEFAULT = 0
VALUES_FORMAT_PRE = 1

# Interest types
INTEREST_ERROR = 0
INTEREST_WARN = 1
INTEREST_PERF = 2
INTEREST_BADPKT = 3

INTEREST_CSS_CLASSES = ["error", "warn", "perf", "badpkt"]
INTEREST_LABELS = ["Error", "Warning", "Performance Warning", "Bad Packet Warning"]

# ioctl constants
SIOCETHTOOL = 0x8946
ETHTOOL_GDRVINFO = 0x00000003
SIOCEFX = 0x89f3
EFX_GET_TS_CONFIG = 0xef25
SIOCGHWTSTAMP = 0x89b1

class ReportGenerator:
    def __init__(self, output_path: str = '-', output_format: int = FORMAT_TEXT, minimal: bool = False):
        self.output_path = output_path
        self.output_format = output_format
        self.minimal = minimal
        self.interesting_stuff = []
        self.out_file = None
        self.hostname = socket.gethostname()
        self.user = "ROOT USER" if os.getuid() == 0 else "NON-ROOT USER"
        
        # JSON data structure
        self.json_data = {
            "report_info": {
                "version": VERSION,
                "date": DATE,
                "hostname": self.hostname,
                "user": self.user
            }
        }
        
        # Get system info
        self.uname = os.uname()
        self.os_type = self.uname.sysname
        self.os_release = self.uname.release
        self.os_version = self.uname.version
        self.arch = self.uname.machine
        
        self.arch_is_x86 = bool(re.match(r'^(?:i[x3456]86|(?:x86[-_]|amd)64)$', self.arch))
        self.arch_is_powerpc = bool(re.match(r'^p(?:ower)?pc(?:64)?$', self.arch))
        
        self._setup_output()

    def _setup_output(self):
        """Setup output file and format"""
        if self.minimal:
            self.output_format = FORMAT_MINIMAL

        if self.output_path == '-':
            self.out_file = sys.stdout
            if not self.minimal and self.output_format != FORMAT_JSON:
                self.output_format = FORMAT_TEXT
        else:
            if self.output_format != FORMAT_MINIMAL and self.output_format != FORMAT_JSON:
                if self.output_path.endswith(('.html', '.htm')):
                    self.output_format = FORMAT_HTML
                elif self.output_path.endswith('.json'):
                    self.output_format = FORMAT_JSON
                else:
                    self.output_format = FORMAT_TEXT
            elif self.output_format == FORMAT_MINIMAL:
                self.output_path = f'sfreport-{self.hostname}-{time.strftime("%Y-%m-%d-%H-%M-%S.txt")}'
            elif self.output_format == FORMAT_JSON and self.output_path == '-':
                self.output_path = f'sfreport-{self.hostname}-{time.strftime("%Y-%m-%d-%H-%M-%S.json")}'
            
            try:
                self.out_file = open(self.output_path, 'w')
            except IOError as e:
                print(f"No write permissions on output directory.\nopen: {e}", file=sys.stderr)
                sys.exit(1)

    def read_file(self, path: str, offset: int = 0) -> Optional[str]:
        """Read entire contents of a file as string"""
        try:
            with open(path, 'rb') as f:
                if offset:
                    f.seek(offset)
                return f.read().decode('utf-8', errors='ignore')
        except (IOError, OSError):
            return None

    def list_dir(self, path: str) -> Optional[List[str]]:
        """Return list of directory entries"""
        try:
            entries = os.listdir(path)
            return [e for e in entries if not e.startswith('.')]
        except (IOError, OSError):
            return None

    def run_command(self, command: str) -> str:
        """Run shell command and return output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, 
                                  text=True, timeout=30)
            return result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return ""

    def html_encode(self, text: str) -> str:
        """HTML encode text"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))

    def print_text(self, text: str):
        """Print text with proper encoding"""
        if self.output_format == FORMAT_JSON:
            return  # JSON output is handled differently
        elif self.output_format == FORMAT_HTML:
            self.out_file.write(self.html_encode(text))
        else:
            self.out_file.write(text)

    def print_heading(self, text: str, heading_id: str = "", hide: bool = False):
        """Print section heading"""
        if self.output_format == FORMAT_JSON:
            return  # JSON output is handled differently
            
        display = 'none' if hide else 'block'
        link = ' ...Show' if hide else ' Hide...'
        
        if self.output_format == FORMAT_HTML:
            if heading_id:
                self.out_file.write(f"""<table rows=1 cols=2 style='border:none;'>
<tr style='border:none;'>
<td style='border:none;'>
<a name='{heading_id}'><h2>{self.html_encode(text)}</h2></a></td>
<td style='border:none;'>
<a id='{heading_id}_l' href='#{heading_id}' onclick='toggle("{heading_id}"); return false;'>{link}</a>
</td></tr></table>
<div style='display:{display}' id='{heading_id}_c'>
""")
            else:
                self.out_file.write(f"    <h2>{self.html_encode(text)}</h2>\n")
        else:
            self.out_file.write(f"{text}\n\n")

    def print_footer(self, heading_id: str = ""):
        """Print section footer"""
        if self.output_format == FORMAT_JSON:
            return
        if self.output_format == FORMAT_HTML and heading_id:
            self.out_file.write(f"<a href='#{heading_id}' onclick='toggle(\"{heading_id}\");'>Hide {heading_id}</a><br>\n")
            self.out_file.write("</div>\n")

    def print_preformatted(self, text: str, use_delimiters: bool = False):
        """Print preformatted text"""
        if self.output_format == FORMAT_JSON:
            return
        if self.output_format == FORMAT_HTML:
            self.out_file.write("    <pre>")
            self.print_text(text)
            self.out_file.write("</pre>\n")
        else:
            if use_delimiters:
                self.out_file.write("--- BEGIN ---\n")
            self.out_file.write(text)
            if use_delimiters:
                self.out_file.write("--- END ---\n\n")
            else:
                self.out_file.write("\n")

    def tabulate(self, title: str, type_name: str, attributes: List[str], 
                values: List[Any], orientation: int = ORIENT_HORIZ,
                values_fmt: int = VALUES_FORMAT_DEFAULT, table_id: str = ""):
        """Print a table of values"""
        if not values:
            values = []
        
        # For JSON format, store data in json_data structure
        if self.output_format == FORMAT_JSON:
            section_key = table_id or title.lower().replace(' ', '_')
            if section_key not in self.json_data:
                self.json_data[section_key] = {}
            
            if title:
                self.json_data[section_key]['title'] = title
            
            table_data = []
            for value in values:
                row_data = {}
                for j, attr in enumerate(attributes):
                    if isinstance(value, dict):
                        attr_value = value.get(attr, None)
                    elif isinstance(value, (list, tuple)):
                        attr_value = value[j] if j < len(value) else None
                    else:
                        attr_value = None
                    row_data[attr] = attr_value
                table_data.append(row_data)
            
            self.json_data[section_key]['data'] = table_data
            return
        
        col_widths = []
        cell_texts = []
        cell_interest = []
        
        # Calculate column widths and prepare cell data
        for j, attr in enumerate(attributes):
            if orientation == ORIENT_HORIZ:
                x, y = j, 0
            else:
                x, y = 0, j
            
            if len(cell_texts) <= y:
                cell_texts.extend([[] for _ in range(y - len(cell_texts) + 1)])
            if len(cell_texts[y]) <= x:
                cell_texts[y].extend([None for _ in range(x - len(cell_texts[y]) + 1)])
            
            cell_texts[y][x] = attr
            if len(col_widths) <= x:
                col_widths.extend([0 for _ in range(x - len(col_widths) + 1)])
            col_widths[x] = max(col_widths[x], len(attr))

        # Process data values
        for i, value in enumerate(values):
            for j, attr in enumerate(attributes):
                if orientation == ORIENT_HORIZ:
                    x, y = j, 1 + i
                else:
                    x, y = 1 + i, j
                
                # Ensure cell_texts is big enough
                while len(cell_texts) <= y:
                    cell_texts.append([])
                while len(cell_texts[y]) <= x:
                    cell_texts[y].append(None)
                
                # Get attribute value
                if isinstance(value, dict):
                    attr_value = value.get(attr, "<N/A>")
                elif isinstance(value, (list, tuple)):
                    attr_value = value[j] if j < len(value) else "<N/A>"
                else:
                    attr_value = "<N/A>"
                
                cell_text = str(attr_value) if attr_value is not None else "<N/A>"
                cell_texts[y][x] = cell_text
                
                # Ensure col_widths is big enough
                while len(col_widths) <= x:
                    col_widths.append(0)
                col_widths[x] = max(col_widths[x], len(cell_text))

        self.print_heading(title, table_id)

        if self.output_format == FORMAT_HTML:
            orient_class = 'horiz' if orientation == ORIENT_HORIZ else 'vert'
            self.out_file.write(f"    <table class=\"{orient_class}\">\n")
            
            for y, row in enumerate(cell_texts):
                self.out_file.write("      <tr>\n")
                for x, cell_text in enumerate(row):
                    if cell_text is None:
                        continue
                    head_cell = (y == 0 if orientation == ORIENT_HORIZ else x == 0)
                    elem_name = 'th' if head_cell else 'td'
                    self.out_file.write(f"        <{elem_name}>")
                    if not head_cell and values_fmt == VALUES_FORMAT_PRE:
                        self.print_preformatted(cell_text)
                    else:
                        self.out_file.write(self.html_encode(cell_text))
                    self.out_file.write(f"</{elem_name}>\n")
                
                if orientation == ORIENT_VERT and not values and y == 0:
                    self.out_file.write(f"        <td rowspan=\"{len(attributes)}\"><em>none found</em></td>\n")
                self.out_file.write("      </tr>\n")
            
            if orientation == ORIENT_HORIZ and not values and attributes:
                self.out_file.write(f"      <tr>\n       <td colspan=\"{len(attributes)}\"><em>none found</em></td>\n     </tr>\n")
            elif not values and not attributes:
                self.out_file.write("      <tr><td><em>none found</em></td></tr>\n")
            
            self.out_file.write("    </table>\n")
        else:
            # Text format table
            for y, row in enumerate(cell_texts):
                line = ''
                for x, cell_text in enumerate(row):
                    if cell_text is None:
                        continue
                    pad = col_widths[x] - len(cell_text)
                    line += cell_text + (' ' * (pad + GUTTER_WIDTH))
                    if orientation == ORIENT_VERT and x == 0:
                        line = line[:-1] + '| '
                
                if orientation == ORIENT_VERT and not values and y == 0:
                    line += ' ' * GUTTER_WIDTH + 'none found'
                
                self.out_file.write(f"{line}\n")
                
                if orientation == ORIENT_HORIZ and y == 0 and attributes:
                    table_width = sum(col_widths) + GUTTER_WIDTH * (len(col_widths) - 1)
                    self.out_file.write('=' * table_width + "\n")
            
            if (orientation == ORIENT_HORIZ or not attributes) and not values:
                self.out_file.write("none found\n")
            self.out_file.write("\n")

        if table_id:
            self.print_footer(table_id)

    def get_pci_devices(self) -> Dict[str, Any]:
        """Get PCI devices information"""
        devices = {}
        pci_devices_path = "/sys/bus/pci/devices"
        
        if not os.path.exists(pci_devices_path):
            return devices
            
        for address in os.listdir(pci_devices_path):
            if not re.match(r'^[0-9a-f]{4}:', address):
                continue
            
            config_path = os.path.join(pci_devices_path, address, "config")
            config_data = self.read_file(config_path)
            if config_data:
                devices[address] = PciFunction(address, config_data)
        
        return devices

    def get_sfc_drvinfo(self) -> Dict[str, Any]:
        """Get SFC driver information for network interfaces"""
        sfc_drvinfo = {}
        net_class_path = "/sys/class/net"
        
        if not os.path.exists(net_class_path):
            return sfc_drvinfo
            
        for iface_name in os.listdir(net_class_path):
            # Try to get driver info using ethtool-like functionality
            driver_name = self._get_interface_driver(iface_name)
            if driver_name in ['sfc', 'sfc_ef100', 'xilinx_efct']:
                # Create a mock drvinfo object
                drvinfo = MockDrvinfo(driver_name, iface_name)
                sfc_drvinfo[iface_name] = drvinfo
        
        return sfc_drvinfo

    def _get_interface_driver(self, iface_name: str) -> str:
        """Get driver name for network interface"""
        driver_path = f"/sys/class/net/{iface_name}/device/driver"
        try:
            driver_link = os.readlink(driver_path)
            return os.path.basename(driver_link)
        except (OSError, IOError):
            return ""

    def print_system_summary(self):
        """Print system summary information"""
        if self.output_format == FORMAT_JSON:
            # Store system info in JSON structure
            self.json_data['system_summary'] = {
                'os_name': self.os_type,
                'version': f"{self.os_release} {self.os_version}",
                'architecture': self.arch,
                'system_name': self.hostname
            }
            
            if self.os_type == 'Linux':
                cmdline = self.read_file('/proc/cmdline')
                if cmdline:
                    self.json_data['system_summary']['kernel_command_line'] = cmdline.strip()
                
                distribution = self._get_distribution_info()
                if distribution:
                    self.json_data['system_summary']['distribution'] = distribution
                
                meminfo = self._get_memory_info()
                if meminfo:
                    self.json_data['system_summary']['memory'] = {
                        'total_physical_mb': meminfo['MemTotal'] // 1024,
                        'free_physical_mb': meminfo['MemFree'] // 1024
                    }
            return
        
        attributes = ['OS Name', 'Version', 'Architecture']
        values = [self.os_type, f"{self.os_release} {self.os_version}", self.arch]
        
        if self.os_type == 'Linux':
            cmdline = self.read_file('/proc/cmdline')
            if cmdline:
                cmdline = cmdline.strip()
                attributes.append('Kernel Command Line')
                values.append(cmdline)
            
            # Try to get distribution info
            distribution = self._get_distribution_info()
            if distribution:
                attributes.append('Distribution')
                values.append(distribution)
        
        attributes.append('System Name')
        values.append(self.hostname)
        
        # Add memory information
        if self.os_type == 'Linux':
            meminfo = self._get_memory_info()
            if meminfo:
                attributes.extend(['Total Physical Memory', 'Free Physical Memory'])
                values.extend([f"{meminfo['MemTotal'] // 1024} MB", 
                              f"{meminfo['MemFree'] // 1024} MB"])
        
        self.tabulate('System Summary', None, attributes, [values], ORIENT_VERT)

    def _get_distribution_info(self) -> Optional[str]:
        """Get Linux distribution information"""
        # Try lsb_release first
        lsb_output = self.run_command('lsb_release -d 2>/dev/null')
        if lsb_output:
            match = re.search(r'^Description:\s*(.*)', lsb_output)
            if match:
                return match.group(1)
        
        # Try release files
        release_files = glob.glob('/etc/*-release')
        if release_files:
            content = self.read_file(release_files[0])
            if content:
                return content.split('\n')[0]
        
        # Try debian version
        debian_version = self.read_file('/etc/debian_version')
        if debian_version:
            return f"Debian {debian_version.strip()}"
        
        return None

    def _get_memory_info(self) -> Optional[Dict[str, int]]:
        """Get memory information from /proc/meminfo"""
        meminfo_content = self.read_file('/proc/meminfo')
        if not meminfo_content:
            return None
        
        meminfo = {}
        for line in meminfo_content.split('\n'):
            match = re.match(r'^([^:]+):\s*(\d+)\s*kB', line)
            if match:
                meminfo[match.group(1)] = int(match.group(2))
        
        return meminfo

    def generate_report(self):
        """Generate the complete system report"""
        devices = self.get_pci_devices()
        sfc_drvinfo = self.get_sfc_drvinfo()

        if self.output_format == FORMAT_JSON:
            self.print_system_summary()
            self.print_device_status(devices, sfc_drvinfo)
            self.print_net_status(sfc_drvinfo)
            # Write JSON output
            json.dump(self.json_data, self.out_file, indent=2)
        elif self.output_format == FORMAT_HTML:
            self._write_html_header()
            self.print_system_summary()
            self.print_device_status(devices, sfc_drvinfo)
            self.print_net_status(sfc_drvinfo)
            self._write_html_footer()
        elif self.output_format == FORMAT_MINIMAL:
            self.print_short_device_status(devices, sfc_drvinfo)
        else:
            self.out_file.write(f"AMD Solarflare system report (version {VERSION})\n\n")
            self.print_system_summary()
            self.print_device_status(devices, sfc_drvinfo)
            self.print_net_status(sfc_drvinfo)

        if self.out_file != sys.stdout:
            self.out_file.close()
            print(f"Finished writing report to {self.output_path}", file=sys.stderr)

    def print_device_status(self, devices: Dict[str, Any], sfc_drvinfo: Dict[str, Any]):
        """Print device status information"""
        # Identify SFC devices
        sfc_devices = {}
        for address, device in devices.items():
            vendor_id = device.get_vendor_id()
            device_class = device.get_device_class()
            if (vendor_id == EFX_VENDID_SFC or 
                (vendor_id == EFX_VENDID_XILINX and device_class == 0x200)):
                sfc_devices[address] = device

        # Create table data for SFC devices
        device_data = []
        for address, device in sfc_devices.items():
            device_data.append({
                'address': address,
                'device_id': f"{device.get_vendor_id():04x}:{device.get_device_id():04x}",
                'revision': f"{device.get_revision():02x}",
                'subsystem_id': f"{device.get_subsystem_vendor_id():04x}:{device.get_subsystem_id():04x}"
            })

        self.tabulate('AMD Solarflare PCI devices', 'pci_device_sfc',
                     ['address', 'device_id', 'revision', 'subsystem_id'],
                     device_data, ORIENT_VERT)

    def print_net_status(self, sfc_drvinfo: Dict[str, Any]):
        """Print network status information"""
        if self.output_format != FORMAT_JSON:
            self.print_heading('Network interfaces for AMD Solarflare adapters', 'controller')
        
        interface_data = []
        for name, drvinfo in sfc_drvinfo.items():
            interface_data.append({
                'name': name,
                'address': drvinfo.bus_info,
                'driver_version': drvinfo.version,
                'controller_version': drvinfo.fw_version
            })

        self.tabulate('Network interfaces for AMD Solarflare adapters', 'network_interfaces',
                     ['name', 'address', 'driver_version', 'controller_version'],
                     interface_data)

    def print_short_device_status(self, devices: Dict[str, Any], sfc_drvinfo: Dict[str, Any]):
        """Print minimal CSV format device status"""
        headings = ['name', 'device_id', 'revision', 'subsys_id', 'driver', 
                   'pci_address', 'driver_version', 'controller_version', 'mac_address']
        
        self.out_file.write("CSV:AMD Solarflare inventory report\n")
        self.out_file.write(",".join(headings) + "\n")
        
        for name, drvinfo in sfc_drvinfo.items():
            # Get corresponding PCI device info
            mac_addr = self._get_mac_address(name)
            row = [
                name,
                "unknown",  # device_id - would need PCI lookup
                "unknown",  # revision
                "unknown",  # subsys_id
                drvinfo.driver,
                drvinfo.bus_info,
                drvinfo.version,
                drvinfo.fw_version,
                mac_addr or ""
            ]
            self.out_file.write(",".join(row) + "\n")
        
        self.out_file.write("\n")

    def _get_mac_address(self, iface_name: str) -> Optional[str]:
        """Get MAC address for network interface"""
        addr_content = self.read_file(f"/sys/class/net/{iface_name}/address")
        return addr_content.strip() if addr_content else None

    def _write_html_header(self):
        """Write HTML document header"""
        uptime = self.run_command("uptime 2>&1")
        
        self.out_file.write(f"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
  <head>
    <title>AMD Solarflare system report</title>
    <meta name="generator" value="sfreport.py">
    <style type="text/css">
      table {{ border-collapse: collapse; }}
      th, td {{ text-align: left; border: 1px solid black; }}
      table.vert th {{ text-align: right; }}
      .error {{ background-color: #ff5555 }}
      .warn {{ background-color: #ccaa55 }}
      .perf {{ background-color: #cc8080 }}
      .badpkt {{ background-color: #cc55aa }}
      td > pre {{ margin: 0; }}
    </style>
    <script>
    function toggle(id) {{
      var obj = document.getElementById(id+'_c');
      var lnk = document.getElementById(id+'_l');
      if ( obj ) {{
        if ( obj.style.display == 'block' ) {{
          obj.style.display = 'none';
          lnk.innerHTML = ' ...Show';
        }} else {{
          obj.style.display = 'block';
          lnk.innerHTML = ' Hide...';
        }}
      }}
    }}
    </script>
    </head>
  <body>
    <h1>AMD Solarflare system report (version {VERSION})</h1>
    {DATE} ({self.user})
    
    <hr>
    <h2> System Uptime </h2> {uptime}
""")

    def _write_html_footer(self):
        """Write HTML document footer"""
        self.out_file.write("  </body>\n</html>\n")


class PciFunction:
    """Represents a PCI function with config space reading"""
    
    def __init__(self, address: str, config_data: str):
        self.address = address
        self.config_data = config_data.encode('latin1') if isinstance(config_data, str) else config_data

    def read_config(self, offset: int, length: int) -> Optional[bytes]:
        """Read from PCI config space"""
        if offset + length <= len(self.config_data):
            return self.config_data[offset:offset + length]
        return None

    def get_vendor_id(self) -> int:
        """Get vendor ID"""
        data = self.read_config(0x00, 2)
        return struct.unpack('<H', data)[0] if data else 0

    def get_device_id(self) -> int:
        """Get device ID"""
        data = self.read_config(0x02, 2)
        return struct.unpack('<H', data)[0] if data else 0

    def get_revision(self) -> int:
        """Get revision"""
        data = self.read_config(0x08, 1)
        return struct.unpack('<B', data)[0] if data else 0

    def get_device_class(self) -> int:
        """Get device class"""
        data = self.read_config(0x0a, 2)
        return struct.unpack('<H', data)[0] if data else 0

    def get_subsystem_vendor_id(self) -> int:
        """Get subsystem vendor ID"""
        data = self.read_config(0x2c, 2)
        return struct.unpack('<H', data)[0] if data else 0

    def get_subsystem_id(self) -> int:
        """Get subsystem ID"""
        data = self.read_config(0x2e, 2)
        return struct.unpack('<H', data)[0] if data else 0


class MockDrvinfo:
    """Mock driver info class"""
    
    def __init__(self, driver: str, interface: str):
        self.driver = driver
        self.version = self._get_driver_version()
        self.fw_version = self._get_fw_version(interface)
        self.bus_info = self._get_bus_info(interface)

    def _get_driver_version(self) -> str:
        """Get driver version"""
        # Try to get from module info
        result = subprocess.run(['modinfo', '-F', 'version', self.driver], 
                              capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    def _get_fw_version(self, interface: str) -> str:
        """Get firmware version"""
        # This would normally come from ethtool, simplified here
        return "unknown"

    def _get_bus_info(self, interface: str) -> str:
        """Get bus info for interface"""
        try:
            device_path = f"/sys/class/net/{interface}/device"
            if os.path.exists(device_path):
                return os.path.basename(os.readlink(device_path))
        except (OSError, IOError):
            pass
        return "unknown"


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='AMD Solarflare system report tool')
    parser.add_argument('-m', '--minimal', action='store_true',
                       help='Generate minimal CSV output')
    parser.add_argument('-j', '--json', action='store_true',
                       help='Generate JSON output')
    parser.add_argument('-v', '--version', action='store_true',
                       help='Show version information')
    parser.add_argument('output_file', nargs='?', default='-',
                       help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    if args.version:
        print(f"AMD Solarflare system report (version {VERSION})", file=sys.stderr)
        return 0
    
    if os.getuid() != 0:
        print("WARNING: This script will not provide a full report", file=sys.stderr)
        print("unless you run it as root.", file=sys.stderr)

    # Determine output path and format
    output_path = args.output_file
    if args.json:
        output_format = FORMAT_JSON
        if output_path == '-':
            hostname = socket.gethostname()
            output_path = f'sfreport-{hostname}-{time.strftime("%Y-%m-%d-%H-%M-%S.json")}'
    elif args.minimal:
        output_format = FORMAT_MINIMAL
        if output_path == '-':
            hostname = socket.gethostname()
            output_path = f'sfreport-{hostname}-{time.strftime("%Y-%m-%d-%H-%M-%S.txt")}'
    elif output_path == '-':
        output_format = FORMAT_TEXT
    elif output_path.endswith('.json'):
        output_format = FORMAT_JSON
    elif output_path.endswith(('.html', '.htm')):
        output_format = FORMAT_HTML
    else:
        output_format = FORMAT_TEXT
    
    if output_path != '-':
        print(f"AMD Solarflare system report (version {VERSION})", file=sys.stderr)

    # Generate report
    generator = ReportGenerator(output_path, output_format, args.minimal)
    generator.generate_report()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
