# Disk Benchmark Tool

A high-performance disk throughput and latency benchmark utility for Linux systems.

## Features

- **Multiple Test Modes**: Sequential read/write, random read/write
- **Accurate Latency Measurement**: Nanosecond-precision timing with percentiles (p50, p95, p99, p99.9)
- **Direct I/O Support**: Bypass OS cache for accurate disk performance measurement
- **Configurable Parameters**: Block size, test duration, file size
- **CSV Output**: Export results for analysis and visualization
- **Visualization**: Generate graphs from benchmark results

## Building

```bash
make
```

This creates the `disk_bench` executable.

## Usage

### Basic Usage

```bash
# Sequential read test
./disk_bench -f /tmp/testfile -m seq-read -d 30

# Random write test with 4K blocks
./disk_bench -f /tmp/testfile -m rand-write -b 4096 -d 30

# Direct I/O test (bypass cache)
./disk_bench -f /tmp/testfile -m seq-read -D -d 30
```

### Command-Line Options

```
-f FILE       Test file path (required)
-m MODE       Test mode: seq-read, seq-write, rand-read, rand-write
-s SIZE       File size in MB (default: 1024)
-b SIZE       Block size in bytes (default: 4096)
-d DURATION   Test duration in seconds (default: 30)
-D            Use Direct I/O (bypass cache)
-S            Use synchronous I/O (O_SYNC)
-o FILE       Output CSV file
-h            Show help
```

### Test Modes

- **seq-read**: Sequential read - measures maximum sequential read throughput
- **seq-write**: Sequential write - measures maximum sequential write throughput
- **rand-read**: Random read - measures random read IOPS and latency (typically 4K blocks)
- **rand-write**: Random write - measures random write IOPS and latency (typically 4K blocks)

## Output

The tool displays comprehensive statistics:

```
================================================================================
BENCHMARK RESULTS
================================================================================
Test Mode:        seq-read
Block Size:       4096 bytes
Duration:         30.00 seconds
Total Operations: 2456789
Total Data:       9565.19 MB

Throughput:       318.84 MB/s
IOPS:             81892.97

Latency (microseconds):
  Min:            2.15
  Average:        12.21
  p50:            10.45
  p95:            18.32
  p99:            25.67
  p99.9:          156.23
  Max:            1234.56
================================================================================
```

## CSV Output

Use the `-o` option to save results to CSV:

```bash
./disk_bench -f /tmp/testfile -m seq-read -d 30 -o results.csv
```

CSV format includes:
- Timestamp
- Test mode and parameters
- Throughput (MB/s) and IOPS
- Latency statistics (min, avg, percentiles, max)

## Visualization

Generate graphs from CSV results:

```bash
# Install dependencies
pip3 install matplotlib pandas

# Generate plots
python3 visualize.py results.csv
```

This creates:
- `results_plot.png`: Throughput, IOPS, and latency comparison
- `results_latency.png`: Latency distribution by percentile

## Running the Full Benchmark Suite

Use the provided script to run multiple tests:

```bash
chmod +x run_benchmark.sh
./run_benchmark.sh
```

This runs:
1. Sequential read (cached)
2. Sequential read (Direct I/O)
3. Sequential write
4. Random read (4K)
5. Random write (4K)
6. Random read with Direct I/O (4K)

## Best Practices

### For Accurate Results

1. **Use Direct I/O** (`-D` flag) to bypass OS cache:
   ```bash
   ./disk_bench -f /tmp/testfile -m seq-read -D -d 30
   ```

2. **Drop caches before testing** (requires root):
   ```bash
   sync
   echo 3 | sudo tee /proc/sys/vm/drop_caches
   ./disk_bench -f /tmp/testfile -m seq-read -d 30
   ```

3. **Use a test file larger than RAM** to avoid caching effects

4. **Run tests multiple times** and average results

5. **Avoid other I/O activity** during testing

### Block Size Selection

- **Sequential tests**: Use larger blocks (64K, 1M) for maximum throughput
- **Random tests**: Use 4K blocks (typical database/filesystem block size)

### Test Duration

- Minimum 10 seconds for stable results
- 30-60 seconds recommended for production benchmarks

## Examples

### Test SSD Performance

```bash
# Sequential throughput
./disk_bench -f /mnt/ssd/testfile -m seq-read -b 1048576 -D -d 30

# Random IOPS
./disk_bench -f /mnt/ssd/testfile -m rand-read -b 4096 -D -d 30
```

### Compare Cached vs Uncached

```bash
# With cache
./disk_bench -f /tmp/testfile -m seq-read -d 10 -o results.csv

# Without cache (Direct I/O)
./disk_bench -f /tmp/testfile -m seq-read -D -d 10 -o results.csv
```

### Benchmark Different Block Sizes

```bash
for bs in 4096 8192 16384 65536 1048576; do
    ./disk_bench -f /tmp/testfile -m seq-read -b $bs -d 10 -o results.csv
done
```

## Understanding Results

### Throughput (MB/s)
- **Sequential Read/Write**: Typically 100-500 MB/s for HDDs, 500-3500 MB/s for SSDs
- Higher is better

### IOPS (I/O Operations Per Second)
- **Random 4K**: Typically 100-200 for HDDs, 10,000-100,000+ for SSDs
- Higher is better

### Latency
- **p50 (median)**: Typical latency for most operations
- **p95/p99**: Latency for slower operations
- **p99.9**: Worst-case latency (important for tail latency)
- Lower is better

## Troubleshooting

### "Invalid argument" error with Direct I/O

Direct I/O requires aligned buffers and block sizes. Ensure:
- Block size is a multiple of 512 bytes (preferably 4096)
- File system supports Direct I/O

### Low throughput results

- Check if other processes are using the disk
- Verify Direct I/O is enabled (`-D` flag)
- Drop caches before testing
- Ensure test file is on the target disk

### Permission denied

- Ensure you have write permissions for the test file location
- Some operations may require root privileges

## Performance Notes

- The tool uses `clock_gettime(CLOCK_MONOTONIC)` for nanosecond-precision timing
- Direct I/O bypasses the page cache for accurate disk measurements
- Latency measurements include syscall overhead (typically <1μs)
- Results may vary based on disk type, filesystem, and system load

## Requirements

- Linux kernel 2.6+
- GCC compiler
- For visualization: Python 3 with matplotlib and pandas

## License

Part of the linuxtools project.
