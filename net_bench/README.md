# Network Bandwidth & Latency Benchmark

`net_bench` is a tool designed to measure network performance by systematically ramping up bandwidth and concurrently measuring throughput, latency, and packet drops.

## Features
- **Ramp-Up Test**: Automatically increments bandwidth (1 MB/s steps) to find the saturation point.
- **Metrics**: Captures Throughput (Mbps), Latency (us), and Packet Drops.
- **Visualization**: Includes a Python script to verify results graphically.
- **Low-Overhead**: Uses UDP for traffic generation to avoid TCP congestion control affecting measurement.

## Usage

### 1. Compile
```bash
make
```

### 2. Start Receiver (Server)
On the machine that will receive traffic:
```bash
./net_bench -s
```
This will bind to port 10001 (UDP) and listen for incoming traffic.

### 3. Start Sender (Client)
On the machine generating traffic:
```bash
./net_bench -c <SERVER_IP> -b <MAX_BW_MBPS> -t <DURATION_PER_STEP>
```
- `-c`: IP address of the receiver.
- `-b`: Maximum bandwidth to ramp up to (in MB/s).
- `-t`: Duration to run each step (in seconds).

**Example:**
Test up to 100 MB/s, running each step for 5 seconds against 192.168.1.10:
```bash
./net_bench -c 192.168.1.10 -b 100 -t 5
```

### 4. Visualize Results
The receiver outputs CSV-like data to stdout. Capture it to a file:
```bash
./net_bench -s > results.csv
```

Then generate a graph:
```bash
python3 plot_results.py results.csv
```
This will produce `benchmark_results.png`.
