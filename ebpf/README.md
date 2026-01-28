# eBPF Network I/O Monitor

A powerful eBPF-based tool for monitoring network I/O of specific processes in real-time.

## Features

- **PID-based filtering**: Monitor network activity for a specific process
- **Real-time monitoring**: See network I/O as it happens
- **Comprehensive syscall coverage**: Hooks `sendto`, `recvfrom`, `sendmsg`, `recvmsg`, `read`, and `write`
- **Detailed statistics**: Track bytes sent/received, operation counts, and per-connection stats
- **Low overhead**: Filtering happens in kernel space using eBPF

## Requirements

- Linux kernel 4.4 or newer with eBPF support
- BCC (BPF Compiler Collection)
- Root/sudo privileges
- Python 3.6+

## Installation

### Install BCC

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install bpfcc-tools linux-headers-$(uname -r)
sudo apt-get install python3-bpfcc
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install bcc-tools kernel-devel
sudo dnf install python3-bcc
```

**From source:**
```bash
# See https://github.com/iovisor/bcc/blob/master/INSTALL.md
```

### Verify Installation

```bash
python3 -c "import bcc; print('BCC installed successfully')"
```

## Usage

### Basic Usage

```bash
# Monitor network I/O for a specific PID
sudo python3 netio_monitor.py <PID>

# Example: Monitor PID 1234
sudo python3 netio_monitor.py 1234
```

### Find PID of a Process

```bash
# Using pgrep
sudo python3 netio_monitor.py $(pgrep nginx)

# Using ps
ps aux | grep <process_name>
sudo python3 netio_monitor.py <PID>

# Using pidof
sudo python3 netio_monitor.py $(pidof sshd)
```

### Command-Line Options

```
positional arguments:
  pid                Process ID to monitor

optional arguments:
  -h, --help         Show help message
  -v, --verbose      Verbose output (show probe attachment details)
```

## Output Format

The tool displays real-time network I/O events in the following format:

```
TIME     DIR  PID    COMM             BYTES     CONNECTION
22:30:45 SEND 1234   curl             512 bytes  192.168.1.100:45678 -> 93.184.216.34:80
22:30:45 RECV 1234   curl             1024 bytes 192.168.1.100:45678 -> 93.184.216.34:80
```

**Columns:**
- **TIME**: Timestamp of the event
- **DIR**: Direction (SEND or RECV)
- **PID**: Process ID
- **COMM**: Process/command name
- **BYTES**: Number of bytes transferred
- **CONNECTION**: Source and destination IP:port (when available)

## Examples

### Monitor a Web Server

```bash
# Start nginx
sudo systemctl start nginx

# Find nginx PID
NGINX_PID=$(pgrep nginx | head -1)

# Monitor nginx network I/O
sudo python3 netio_monitor.py $NGINX_PID

# In another terminal, generate traffic
curl http://localhost
```

### Monitor a Network Client

```bash
# Start the monitor in one terminal
sudo python3 netio_monitor.py $(pgrep curl) &

# Run curl in another terminal
curl https://example.com
```

### Monitor SSH Connections

```bash
# Find SSH daemon PID
sudo python3 netio_monitor.py $(pidof sshd)
```

## Summary Statistics

When you exit the tool (Ctrl+C), it displays summary statistics:

```
================================================================================
SUMMARY STATISTICS
================================================================================
Total Bytes Sent:     15,360 bytes (15.00 KB)
Total Bytes Received: 51,200 bytes (50.00 KB)
Send Operations:      24
Receive Operations:   18

Per-Connection Statistics:
--------------------------------------------------------------------------------
192.168.1.100:45678 -> 93.184.216.34:80
  Sent: 15,360 bytes, Recv: 51,200 bytes
```

## How It Works

The tool uses eBPF (extended Berkeley Packet Filter) to hook into kernel network syscalls:

1. **Kernel Probes**: Attaches kprobes and kretprobes to network syscalls
2. **PID Filtering**: Filters events in kernel space for efficiency (only events from target PID are sent to userspace)
3. **Event Collection**: Uses BPF perf buffers to stream events to userspace
4. **Statistics**: Aggregates data and displays real-time and summary statistics

## Troubleshooting

### "This program must be run as root"

eBPF programs require root privileges. Use `sudo`:
```bash
sudo python3 netio_monitor.py <PID>
```

### "Process with PID X not found"

The process doesn't exist or has terminated. Verify the PID:
```bash
ps aux | grep <PID>
```

### "ModuleNotFoundError: No module named 'bcc'"

BCC is not installed. Follow the installation instructions above.

### No output displayed

- Verify the process is actually doing network I/O
- Try the verbose flag: `sudo python3 netio_monitor.py -v <PID>`
- Check kernel version: `uname -r` (must be 4.4+)
- Verify eBPF support: `ls /sys/kernel/debug/tracing/`

### "Could not attach to X syscall"

Some syscalls might not be available on your kernel. This is usually not critical as the tool hooks multiple syscalls.

## Limitations

- Requires root/sudo privileges
- Only monitors IPv4 connections (IPv6 support can be added)
- Connection information may not be available for all socket types
- Some encrypted traffic (e.g., TLS) will show encrypted byte counts

## Performance

eBPF programs run in the kernel with minimal overhead:
- Filtering happens in kernel space
- No context switches for filtered-out events
- Efficient perf buffer for event streaming
- Negligible impact on monitored process

## License

This tool is part of the linuxtools project.

## See Also

- [BCC Documentation](https://github.com/iovisor/bcc)
- [eBPF Documentation](https://ebpf.io/)
- Similar tools: `tcpdump`, `wireshark`, `ss`, `netstat`
