# Network Benchmark Runbook

This runbook guides you through setting up, running, and visualizing the results of the `net_bench` tool.

## 1. Environment Setup

### Prerequisites
*   **Two Linux Servers**: One to act as the Sender (Client) and one as the Receiver (Server).
*   **Network Connectivity**: Ensure open UDP ports (default `10001`) between the servers.
*   **Build Tools**: `gcc`, `make` installed on both servers.
*   **Python**: `python3` with `pandas` and `matplotlib` installed (for visualization).

### Installation
1.  **Clone the Repository** (on both servers):
    ```bash
    git clone https://github.com/securestrat/linuxtools.git
    cd linuxtools/net_bench
    ```

2.  **Compile the Tool**:
    ```bash
    make
    ```
    This creates the `net_bench` executable.

## 2. Running a Benchmark

The test involves a **Receiver** (Server) that collects metrics and a **Sender** (Client) that generates traffic.

### Step A: Start the Receiver
On the machine designated to receive traffic:

```bash
./net_bench -s > results.csv
```
*   The tool listens on UDP port `10001`.
*   Output is redirected to `results.csv` for later analysis.
*   **Timeouts**: 
    *   Waits **10 minutes** for traffic to start.
    *   Stops automatically if traffic ceases for **30 seconds**.

### Step B: Start the Sender
On the machine designated to send traffic:

```bash
./net_bench -c <RECEIVER_IP> -b <MAX_BANDWIDTH> -t <DURATION>
```

*   `-c <RECEIVER_IP>`: IP address of the Receiver.
*   `-b <MAX_BANDWIDTH>`: Target bandwidth to ramp up to (in MB/s).
*   `-t <DURATION>`: Duration to run each bandwidth step (in seconds).

**Example**:
To test up to **100 MB/s**, running each step for **5 seconds**:
```bash
./net_bench -c 172.16.205.130 -b 100 -t 5
```

## 3. Visualizing Results

Once the test completes, use the Python script to create graphs from the `results.csv` file generated on the Receiver.

1.  **Install Python Dependencies** (if not already present):
    ```bash
    pip3 install pandas matplotlib
    ```

2.  **Generate Graph**:
    ```bash
    python3 plot_results.py results.csv
    ```

3.  **View Output**:
    *   The script generates an image file named `benchmark_results.png`.
    *   This image contains charts for **Throughput**, **Latency (ns)**, and **Packet Drops**.

## 4. Troubleshooting
*   **"bind failed: Address already in use"**: The receiver process is still running. Kill it with `pkill net_bench`.
*   **Latency is 0**: This usually indicates the server clocks are not synchronized. The tool measures one-way delay (`Receive Time - Send Time`). If the Sender's clock is ahead, this value is clamped to 0. Use NTP or PTP to synchronize clocks.
