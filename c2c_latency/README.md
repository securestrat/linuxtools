# CPU Core-to-Core Latency Benchmark

This tool measures the cache coherence latency between CPU cores on a Linux system. It uses `pthread` affinity to pin threads to specific cores and `rdtsc` to measure the round-trip time for a cache line transfer.

## Prerequisites
- Linux system
- `gcc`
- `make`

## Compilation
1. Navigate to the `c2c_latency` directory.
2. Run `make`.
   ```bash
   make
   ```

## Usage

### 1. Matrix Mode (Recommended)
To measure and display a matrix of latencies between all available online cores:

```bash
./c2c_latency -m
```

**Output Example:**
```text
Measuring core-to-core latency for 4 cores...
          0     1     2     3
    0     -   120   124   118
    1   120     -   118   122
    2   125   119     -   120
    3   119   123   121     -
```
Values are in CPU cycles.

### 2. Specific Pair Mode
To measure latency between two specific cores (e.g., core 0 and core 4):

```bash
./c2c_latency -c 0,4
```

## Interpreting Results
- **Lower values** indicate faster communication, typically meaning the cores share a closer cache level (e.g., L2 or L3) or are on the same socket.
- **Higher values** usually indicate communication across sockets (NUMA) or cores that do not share last-level cache.

## Tested On
- Linux server `172.16.205.129` (Latencies ~250 cycles).
