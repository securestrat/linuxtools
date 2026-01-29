#!/usr/bin/env python3
"""
Network I/O Monitor using eBPF
Captures network I/O for a specific process ID

Usage: sudo python3 netio_monitor.py <PID>
"""

from bcc import BPF
import argparse
import socket
import struct
import sys
import signal
from time import sleep, strftime
from collections import defaultdict

# eBPF program
bpf_text = """
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <bcc/proto.h>
#include <linux/socket.h>
#include <linux/net.h>

#define TASK_COMM_LEN 16

// Data structure for events
struct data_t {
    u32 pid;
    u32 tid;
    char comm[TASK_COMM_LEN];
    u64 ts;
    u32 saddr;
    u32 daddr;
    u16 sport;
    u16 dport;
    u64 bytes;
    u8 protocol;
    u8 direction; // 0=send, 1=recv
};

BPF_PERF_OUTPUT(events);
BPF_HASH(currsock, u64, struct sock *);

// Target PID (will be replaced by Python)
static inline int filter_pid() {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    if (pid != TARGET_PID)
        return 0;
    return 1;
}

// Extract socket information
static void extract_sock_info(struct pt_regs *ctx, struct sock *sk, struct data_t *data, u8 direction, u64 bytes) {
    u16 family = sk->__sk_common.skc_family;
    
    if (family == AF_INET) {
        data->saddr = sk->__sk_common.skc_rcv_saddr;
        data->daddr = sk->__sk_common.skc_daddr;
        data->sport = sk->__sk_common.skc_num;
        data->dport = sk->__sk_common.skc_dport;
        data->dport = ntohs(data->dport);
        data->protocol = sk->sk_protocol;
    }
    
    data->pid = bpf_get_current_pid_tgid() >> 32;
    data->tid = bpf_get_current_pid_tgid();
    data->ts = bpf_ktime_get_ns();
    data->bytes = bytes;
    data->direction = direction;
    bpf_get_current_comm(&data->comm, sizeof(data->comm));
}

// Hook sendto
int trace_sendto_entry(struct pt_regs *ctx, int fd, void *buf, size_t len) {
    if (!filter_pid())
        return 0;
    
    u64 pid_tgid = bpf_get_current_pid_tgid();
    struct task_struct *task = (struct task_struct *)bpf_get_current_task();
    struct files_struct *files = task->files;
    
    // Store fd for return probe
    u64 id = pid_tgid;
    bpf_trace_printk("sendto: fd=%d, len=%d\\n", fd, len);
    
    return 0;
}

int trace_sendto_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    struct data_t data = {};
    struct task_struct *task = (struct task_struct *)bpf_get_current_task();
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 0; // send
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Hook recvfrom
int trace_recvfrom_entry(struct pt_regs *ctx, int fd, void *buf, size_t len) {
    if (!filter_pid())
        return 0;
    
    bpf_trace_printk("recvfrom: fd=%d, len=%d\\n", fd, len);
    return 0;
}

int trace_recvfrom_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    struct data_t data = {};
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 1; // recv
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Hook sendmsg
int trace_sendmsg_entry(struct pt_regs *ctx, int fd) {
    if (!filter_pid())
        return 0;
    
    bpf_trace_printk("sendmsg: fd=%d\\n", fd);
    return 0;
}

int trace_sendmsg_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    struct data_t data = {};
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 0; // send
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Hook recvmsg
int trace_recvmsg_entry(struct pt_regs *ctx, int fd) {
    if (!filter_pid())
        return 0;
    
    bpf_trace_printk("recvmsg: fd=%d\\n", fd);
    return 0;
}

int trace_recvmsg_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    struct data_t data = {};
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 1; // recv
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Hook write (for socket writes)
int trace_write_entry(struct pt_regs *ctx, unsigned int fd, const char __user *buf, size_t count) {
    if (!filter_pid())
        return 0;
    
    return 0;
}

int trace_write_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    // We'll filter for socket fds in userspace if needed
    struct data_t data = {};
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 0; // send
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}

// Hook read (for socket reads)
int trace_read_entry(struct pt_regs *ctx, unsigned int fd, char __user *buf, size_t count) {
    if (!filter_pid())
        return 0;
    
    return 0;
}

int trace_read_return(struct pt_regs *ctx) {
    if (!filter_pid())
        return 0;
    
    int ret = PT_REGS_RC(ctx);
    if (ret < 0)
        return 0;
    
    struct data_t data = {};
    
    data.pid = bpf_get_current_pid_tgid() >> 32;
    data.tid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    data.bytes = ret;
    data.direction = 1; // recv
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}
"""

# Statistics
class Stats:
    def __init__(self):
        self.total_sent = 0
        self.total_recv = 0
        self.send_count = 0
        self.recv_count = 0
        self.start_time = None
        self.connections = defaultdict(lambda: {'sent': 0, 'recv': 0})
    
    def update(self, direction, bytes_count, addr_info=None):
        if direction == 0:  # send
            self.total_sent += bytes_count
            self.send_count += 1
        else:  # recv
            self.total_recv += bytes_count
            self.recv_count += 1
        
        if addr_info:
            key = f"{addr_info['saddr']}:{addr_info['sport']} -> {addr_info['daddr']}:{addr_info['dport']}"
            if direction == 0:
                self.connections[key]['sent'] += bytes_count
            else:
                self.connections[key]['recv'] += bytes_count
    
    def print_summary(self):
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        print(f"Total Bytes Sent:     {self.total_sent:,} bytes ({self.total_sent/1024:.2f} KB)")
        print(f"Total Bytes Received: {self.total_recv:,} bytes ({self.total_recv/1024:.2f} KB)")
        print(f"Send Operations:      {self.send_count:,}")
        print(f"Receive Operations:   {self.recv_count:,}")
        print(f"\nPer-Connection Statistics:")
        print("-"*80)
        for conn, stats in self.connections.items():
            if stats['sent'] > 0 or stats['recv'] > 0:
                print(f"{conn}")
                print(f"  Sent: {stats['sent']:,} bytes, Recv: {stats['recv']:,} bytes")

stats = Stats()

def inet_ntoa(addr):
    """Convert network byte order IP to string"""
    return socket.inet_ntoa(struct.pack("I", addr))

def print_event(cpu, data, size):
    """Callback for perf buffer events"""
    event = b["events"].event(data)
    
    direction_str = "SEND" if event.direction == 0 else "RECV"
    comm = event.comm.decode('utf-8', 'replace')
    
    # Format address info if available
    addr_info = None
    if event.saddr != 0 or event.daddr != 0:
        saddr = inet_ntoa(event.saddr)
        daddr = inet_ntoa(event.daddr)
        addr_str = f"{saddr}:{event.sport} -> {daddr}:{event.dport}"
        addr_info = {
            'saddr': saddr,
            'sport': event.sport,
            'daddr': daddr,
            'dport': event.dport
        }
    else:
        addr_str = "N/A"
    
    # Update statistics
    stats.update(event.direction, event.bytes, addr_info)
    
    # Print event
    print(f"{strftime('%H:%M:%S')} {direction_str:4s} {event.pid:6d} {comm:16s} "
          f"{event.bytes:8d} bytes  {addr_str}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nInterrupted by user")
    stats.print_summary()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description="Monitor network I/O for a specific process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    sudo python3 netio_monitor.py 1234        # Monitor PID 1234
    sudo python3 netio_monitor.py $(pgrep nginx)  # Monitor nginx process
        """
    )
    parser.add_argument("pid", type=int, help="Process ID to monitor")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Verbose output (show all syscalls)")
    
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() != 0:
        print("Error: This program must be run as root (use sudo)")
        sys.exit(1)
    
    # Check if PID exists
    try:
        with open(f"/proc/{args.pid}/comm", "r") as f:
            process_name = f.read().strip()
        print(f"Monitoring network I/O for PID {args.pid} ({process_name})")
    except FileNotFoundError:
        print(f"Error: Process with PID {args.pid} not found")
        sys.exit(1)
    
    # Replace TARGET_PID in BPF program
    bpf_code = bpf_text.replace("TARGET_PID", str(args.pid))
    
    # Load BPF program
    global b
    b = BPF(text=bpf_code)
    
    # Attach probes
    syscalls = [
        ("sendto", "trace_sendto_entry", "trace_sendto_return"),
        ("recvfrom", "trace_recvfrom_entry", "trace_recvfrom_return"),
        ("sendmsg", "trace_sendmsg_entry", "trace_sendmsg_return"),
        ("recvmsg", "trace_recvmsg_entry", "trace_recvmsg_return"),
        ("write", "trace_write_entry", "trace_write_return"),
        ("read", "trace_read_entry", "trace_read_return"),
    ]
    
    for syscall, entry_fn, return_fn in syscalls:
        try:
            b.attach_kprobe(event=b.get_syscall_fnname(syscall), fn_name=entry_fn)
            b.attach_kretprobe(event=b.get_syscall_fnname(syscall), fn_name=return_fn)
            if args.verbose:
                print(f"Attached probes to {syscall}")
        except Exception as e:
            print(f"Warning: Could not attach to {syscall}: {e}")
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Print header
    print("\n" + "="*80)
    print(f"{'TIME':<8} {'DIR':<4} {'PID':<6} {'COMM':<16} {'BYTES':<8}  {'CONNECTION'}")
    print("="*80)
    
    # Open perf buffer
    b["events"].open_perf_buffer(print_event)
    
    # Poll for events
    while True:
        try:
            b.perf_buffer_poll()
        except KeyboardInterrupt:
            signal_handler(None, None)

if __name__ == "__main__":
    import os
    main()
