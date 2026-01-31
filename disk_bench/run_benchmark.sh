#!/bin/bash
#
# Example benchmark script - runs multiple disk tests and generates visualizations
#

set -e

# Configuration
TEST_FILE="/tmp/disk_bench_test.dat"
OUTPUT_CSV="disk_bench_results.csv"
DURATION=10  # seconds per test

echo "==================================================================="
echo "Disk Benchmark Suite"
echo "==================================================================="
echo ""
echo "Test file: $TEST_FILE"
echo "Duration per test: ${DURATION}s"
echo "Output CSV: $OUTPUT_CSV"
echo ""

# Clean up old results
rm -f "$OUTPUT_CSV"
rm -f "$TEST_FILE"

# Create a test file for read tests
echo "Creating test file (1GB)..."
dd if=/dev/zero of="$TEST_FILE" bs=1M count=1024 2>/dev/null
sync

echo ""
echo "-------------------------------------------------------------------"
echo "Test 1: Sequential Read (with cache)"
echo "-------------------------------------------------------------------"
./disk_bench -f "$TEST_FILE" -m seq-read -d "$DURATION" -o "$OUTPUT_CSV"

echo ""
echo "-------------------------------------------------------------------"
echo "Test 2: Sequential Read (Direct I/O, bypass cache)"
echo "-------------------------------------------------------------------"
./disk_bench -f "$TEST_FILE" -m seq-read -d "$DURATION" -D -o "$OUTPUT_CSV"

echo ""
echo "-------------------------------------------------------------------"
echo "Test 3: Sequential Write"
echo "-------------------------------------------------------------------"
rm -f "$TEST_FILE"
./disk_bench -f "$TEST_FILE" -m seq-write -d "$DURATION" -o "$OUTPUT_CSV"

echo ""
echo "-------------------------------------------------------------------"
echo "Test 4: Random Read (4K blocks)"
echo "-------------------------------------------------------------------"
./disk_bench -f "$TEST_FILE" -m rand-read -b 4096 -d "$DURATION" -o "$OUTPUT_CSV"

echo ""
echo "-------------------------------------------------------------------"
echo "Test 5: Random Write (4K blocks)"
echo "-------------------------------------------------------------------"
./disk_bench -f "$TEST_FILE" -m rand-write -b 4096 -d "$DURATION" -s 1024 -o "$OUTPUT_CSV"

echo ""
echo "-------------------------------------------------------------------"
echo "Test 6: Random Read with Direct I/O (4K blocks)"
echo "-------------------------------------------------------------------"
./disk_bench -f "$TEST_FILE" -m rand-read -b 4096 -d "$DURATION" -D -o "$OUTPUT_CSV"

echo ""
echo "==================================================================="
echo "All tests completed!"
echo "==================================================================="
echo ""

# Generate visualizations if Python is available
if command -v python3 &> /dev/null; then
    echo "Generating visualizations..."
    if python3 visualize.py "$OUTPUT_CSV" 2>/dev/null; then
        echo "Visualizations created successfully"
    else
        echo "Note: Install matplotlib and pandas for visualizations:"
        echo "  pip3 install matplotlib pandas"
    fi
else
    echo "Python3 not found - skipping visualization"
fi

echo ""
echo "Results saved to: $OUTPUT_CSV"
echo ""

# Clean up test file
rm -f "$TEST_FILE"
echo "Cleanup complete"
