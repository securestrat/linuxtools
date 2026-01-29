#!/usr/bin/env python3
"""
Simplified Network I/O Monitor using eBPF - for debugging
Captures network I/O for a specific process ID

Usage: sudo python3 netio_monitor_simple.py <PID>
"""

from bcc import BPF
import argparse
import sys
import signal
import os

# Simplified eBPF program - just track read/write syscalls
bpf_text = """
#include <uapi/linux/ptrace.h>

#define TASK_COMM_LEN 16

struct data_t {
    u32 pid;
    char comm[TASK_COMM_LEN];
    u64 bytes;
    u8 direction; // 0=write, 1=read
};

BPF_PERF_OUTPUT(events);

// Target PID
static inline int filter_pid() {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    if (pid != TARGET_PID)
        return 0;
    return 1;
}

// Track write syscall returns
int trace_write_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret <= 0)
        return 0;
    
    struct data_t data = {};
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.bytes = ret;
    data.direction = 0; // write
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Track read syscall returns
int trace_read_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret <= 0)
        return 0;
    
    struct data_t data = {};
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.bytes = ret;
    data.direction = 1; // read
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}
"""

# Statistics
total_write = 0
total_read = 0
write_count = 0
read_count = 0

def print_event(cpu, data, size):
    """Callback for perf buffer events"""
    global total_write, total_read, write_count, read_count
    
    event = b["events"].event(data)
    direction_str = "WRITE" if event.direction == 0 else "READ"
    comm = event.comm.decode('utf-8', 'replace')
    
    if event.direction == 0:
        total_write += event.bytes
        write_count += 1
    else:
        total_read += event.bytes
        read_count += 1
    
    print(f"{direction_str:5s} {event.pid:6d} {comm:16s} {event.bytes:8d} bytes")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total Bytes Written: {total_write:,} bytes ({total_write/1024:.2f} KB)")
    print(f"Total Bytes Read:    {total_read:,} bytes ({total_read/1024:.2f} KB)")
    print(f"Write Operations:    {write_count:,}")
    print(f"Read Operations:     {read_count:,}")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description="Monitor network I/O for a specific process (simplified version)"
    )
    parser.add_argument("pid", type=int, help="Process ID to monitor")
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() != 0:
        print("Error: This program must be run as root (use sudo)")
        sys.exit(1)
    
    # Check if PID exists
    try:
        with open(f"/proc/{args.pid}/comm", "r") as f:
            process_name = f.read().strip()
        print(f"Monitoring I/O for PID {args.pid} ({process_name})")
    except FileNotFoundError:
        print(f"Error: Process with PID {args.pid} not found")
        sys.exit(1)
    
    # Replace TARGET_PID in BPF program
    bpf_code = bpf_text.replace("TARGET_PID", str(args.pid))
    
    print("Loading BPF program...")
    
    # Load BPF program
    global b
    try:
        b = BPF(text=bpf_code)
        print("BPF program loaded successfully")
    except Exception as e:
        print(f"Error loading BPF program: {e}")
        sys.exit(1)
    
    # Attach probes
    print("Attaching probes...")
    try:
        b.attach_kretprobe(event=b.get_syscall_fnname("write"), fn_name="trace_write_return")
        print("  Attached to write syscall")
        b.attach_kretprobe(event=b.get_syscall_fnname("read"), fn_name="trace_read_return")
        print("  Attached to read syscall")
    except Exception as e:
        print(f"Error attaching probes: {e}")
        sys.exit(1)
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Print header
    print("\n" + "="*60)
    print(f"{'DIR':<5} {'PID':<6} {'COMM':<16} {'BYTES':<8}")
    print("="*60)
    
    # Open perf buffer
    b["events"].open_perf_buffer(print_event)
    
    # Poll for events
    print("Monitoring... Press Ctrl+C to stop\n")
    while True:
        try:
            b.perf_buffer_poll()
        except KeyboardInterrupt:
            signal_handler(None, None)

if __name__ == "__main__":
    main()
