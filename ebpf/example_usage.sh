#!/bin/bash
#
# Example script showing how to monitor a process's network I/O
# This demonstrates the typical workflow for using netio_monitor.py
#

set -e

echo "==================================================================="
echo "Network I/O Monitor - Example Usage"
echo "==================================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if BCC is installed
if ! python3 -c "import bcc" 2>/dev/null; then
    echo "Error: BCC is not installed"
    echo "Install with: sudo apt-get install python3-bpfcc"
    exit 1
fi

echo "Step 1: Starting test traffic generator..."
python3 test_traffic.py &
TEST_PID=$!
echo "  Started with PID: $TEST_PID"
sleep 2

echo ""
echo "Step 2: Starting network I/O monitor..."
echo "  Monitoring PID: $TEST_PID"
echo "  Press Ctrl+C to stop monitoring"
echo ""
echo "-------------------------------------------------------------------"

# Trap to clean up on exit
cleanup() {
    echo ""
    echo "-------------------------------------------------------------------"
    echo "Cleaning up..."
    kill $TEST_PID 2>/dev/null || true
    echo "Done!"
}
trap cleanup EXIT

# Run the monitor
python3 netio_monitor.py $TEST_PID
