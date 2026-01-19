import matplotlib.pyplot as plt
import pandas as pd
import sys

def plot_results(csv_file):
    try:
        data = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Assuming CSV columns: timestamp, mbps, latency_avg_ns, drops
    # We want to plot:
    # 1. Throughput vs Time (or Step?)
    # 2. Latency vs Throughput (scatter or line if sorted)
    
    # Create a figure with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    
    # Plot Throughput
    ax1.plot(data['timestamp'], data['mbps'], label='Throughput (Mbps)', color='blue')
    ax1.set_ylabel('Throughput (Mbps)')
    ax1.set_title('Network Benchmark Results')
    ax1.grid(True)
    
    # Plot Latency
    ax2.plot(data['timestamp'], data['latency_avg_ns'], label='Latency (ns)', color='orange')
    ax2.set_ylabel('Latency (ns)')
    ax2.grid(True)
    
    # Plot Drops
    ax3.plot(data['timestamp'], data['drops'], label='Drops', color='red')
    ax3.set_ylabel('Packet Drops')
    ax3.set_xlabel('Time (s)')
    ax3.grid(True)
    
    plt.tight_layout()
    plt.savefig('benchmark_results.png')
    print("Graph saved to benchmark_results.png")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 plot_results.py <csv_file>")
    else:
        plot_results(sys.argv[1])
