#!/usr/bin/env python3
"""
Visualize disk benchmark results from CSV output

Usage: python3 visualize.py results.csv
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

def plot_results(csv_file):
    """Generate visualization plots from benchmark CSV"""
    
    # Read CSV
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    
    if df.empty:
        print("No data in CSV file")
        sys.exit(1)
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Disk Benchmark Results', fontsize=16, fontweight='bold')
    
    # Plot 1: Throughput by mode
    ax1 = axes[0, 0]
    modes = df['mode'].unique()
    throughputs = [df[df['mode'] == mode]['throughput_mbps'].values for mode in modes]
    ax1.bar(modes, [tp[0] if len(tp) > 0 else 0 for tp in throughputs], color='steelblue')
    ax1.set_xlabel('Test Mode')
    ax1.set_ylabel('Throughput (MB/s)')
    ax1.set_title('Throughput by Test Mode')
    ax1.grid(axis='y', alpha=0.3)
    
    # Plot 2: IOPS by mode
    ax2 = axes[0, 1]
    iops_data = [df[df['mode'] == mode]['iops'].values for mode in modes]
    ax2.bar(modes, [iops[0] if len(iops) > 0 else 0 for iops in iops_data], color='coral')
    ax2.set_xlabel('Test Mode')
    ax2.set_ylabel('IOPS')
    ax2.set_title('IOPS by Test Mode')
    ax2.grid(axis='y', alpha=0.3)
    
    # Plot 3: Latency percentiles
    ax3 = axes[1, 0]
    percentiles = ['lat_p50_us', 'lat_p95_us', 'lat_p99_us', 'lat_p999_us']
    percentile_labels = ['p50', 'p95', 'p99', 'p99.9']
    
    x = range(len(modes))
    width = 0.2
    for i, (percentile, label) in enumerate(zip(percentiles, percentile_labels)):
        values = [df[df['mode'] == mode][percentile].values[0] if len(df[df['mode'] == mode]) > 0 else 0 
                  for mode in modes]
        ax3.bar([xi + i * width for xi in x], values, width, label=label)
    
    ax3.set_xlabel('Test Mode')
    ax3.set_ylabel('Latency (microseconds)')
    ax3.set_title('Latency Percentiles by Test Mode')
    ax3.set_xticks([xi + width * 1.5 for xi in x])
    ax3.set_xticklabels(modes)
    ax3.legend()
    ax3.grid(axis='y', alpha=0.3)
    
    # Plot 4: Summary table
    ax4 = axes[1, 1]
    ax4.axis('tight')
    ax4.axis('off')
    
    # Create summary table
    summary_data = []
    for mode in modes:
        mode_df = df[df['mode'] == mode]
        if not mode_df.empty:
            row = mode_df.iloc[0]
            summary_data.append([
                mode,
                f"{row['throughput_mbps']:.2f}",
                f"{row['iops']:.0f}",
                f"{row['lat_avg_us']:.2f}",
                f"{row['lat_p99_us']:.2f}"
            ])
    
    table = ax4.table(cellText=summary_data,
                     colLabels=['Mode', 'Throughput\n(MB/s)', 'IOPS', 'Avg Latency\n(μs)', 'p99 Latency\n(μs)'],
                     cellLoc='center',
                     loc='center',
                     colWidths=[0.2, 0.2, 0.2, 0.2, 0.2])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header
    for i in range(5):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    plt.tight_layout()
    
    # Save plot
    output_file = csv_file.replace('.csv', '_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
    # Also create individual latency distribution if we have detailed data
    create_latency_histogram(df, csv_file)

def create_latency_histogram(df, csv_file):
    """Create latency distribution histogram"""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    modes = df['mode'].unique()
    colors = ['steelblue', 'coral', 'lightgreen', 'gold']
    
    for i, mode in enumerate(modes):
        mode_df = df[df['mode'] == mode]
        if not mode_df.empty:
            row = mode_df.iloc[0]
            # Create histogram data from percentiles
            latencies = [
                row['lat_min_us'],
                row['lat_p50_us'],
                row['lat_p95_us'],
                row['lat_p99_us'],
                row['lat_p999_us'],
                row['lat_max_us']
            ]
            percentiles = [0, 50, 95, 99, 99.9, 100]
            
            ax.plot(percentiles, latencies, marker='o', label=mode, 
                   color=colors[i % len(colors)], linewidth=2, markersize=8)
    
    ax.set_xlabel('Percentile', fontsize=12)
    ax.set_ylabel('Latency (microseconds)', fontsize=12)
    ax.set_title('Latency Distribution by Percentile', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    
    plt.tight_layout()
    
    output_file = csv_file.replace('.csv', '_latency.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Latency plot saved to: {output_file}")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <results.csv>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    plot_results(csv_file)

if __name__ == "__main__":
    main()
