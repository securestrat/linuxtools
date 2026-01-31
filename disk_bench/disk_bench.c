/*
 * disk_bench.c - Disk throughput and latency benchmark tool
 * 
 * Measures disk performance with various I/O patterns:
 * - Sequential read/write
 * - Random read/write
 * - Latency percentiles (p50, p95, p99, p99.9)
 * - CSV output for analysis
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>

// O_DIRECT is Linux-specific
#ifndef O_DIRECT
#define O_DIRECT 0
#warning "O_DIRECT not available on this platform - Direct I/O will be disabled"
#endif

#define DEFAULT_FILE_SIZE_MB 1024
#define DEFAULT_BLOCK_SIZE 4096
#define DEFAULT_DURATION_SEC 30
#define MAX_LATENCIES 1000000

typedef enum {
    MODE_SEQ_READ,
    MODE_SEQ_WRITE,
    MODE_RAND_READ,
    MODE_RAND_WRITE,
    MODE_MIXED
} test_mode_t;

typedef struct {
    char *filename;
    test_mode_t mode;
    size_t file_size;
    size_t block_size;
    int duration_sec;
    int use_direct_io;
    int use_sync;
    char *output_csv;
} config_t;

typedef struct {
    unsigned long *latencies;
    size_t count;
    size_t capacity;
    unsigned long total_bytes;
    unsigned long total_ops;
    double duration_sec;
} stats_t;

// Get current time in nanoseconds
static inline unsigned long get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000UL + ts.tv_nsec;
}

// Compare function for qsort
static int compare_ulong(const void *a, const void *b) {
    unsigned long ua = *(const unsigned long *)a;
    unsigned long ub = *(const unsigned long *)b;
    if (ua < ub) return -1;
    if (ua > ub) return 1;
    return 0;
}

// Calculate percentile from sorted array
static unsigned long get_percentile(unsigned long *sorted, size_t count, double percentile) {
    if (count == 0) return 0;
    size_t index = (size_t)((percentile / 100.0) * count);
    if (index >= count) index = count - 1;
    return sorted[index];
}

// Add latency measurement
static void add_latency(stats_t *stats, unsigned long latency_ns) {
    if (stats->count >= stats->capacity) {
        stats->capacity *= 2;
        stats->latencies = realloc(stats->latencies, stats->capacity * sizeof(unsigned long));
        if (!stats->latencies) {
            perror("realloc");
            exit(1);
        }
    }
    stats->latencies[stats->count++] = latency_ns;
}

// Print statistics
static void print_stats(config_t *config, stats_t *stats) {
    // Sort latencies for percentile calculation
    qsort(stats->latencies, stats->count, sizeof(unsigned long), compare_ulong);
    
    double throughput_mbps = (stats->total_bytes / (1024.0 * 1024.0)) / stats->duration_sec;
    double iops = stats->total_ops / stats->duration_sec;
    
    unsigned long lat_min = stats->latencies[0];
    unsigned long lat_max = stats->latencies[stats->count - 1];
    unsigned long lat_p50 = get_percentile(stats->latencies, stats->count, 50.0);
    unsigned long lat_p95 = get_percentile(stats->latencies, stats->count, 95.0);
    unsigned long lat_p99 = get_percentile(stats->latencies, stats->count, 99.0);
    unsigned long lat_p999 = get_percentile(stats->latencies, stats->count, 99.9);
    
    // Calculate average
    unsigned long lat_sum = 0;
    for (size_t i = 0; i < stats->count; i++) {
        lat_sum += stats->latencies[i];
    }
    unsigned long lat_avg = lat_sum / stats->count;
    
    const char *mode_str;
    switch (config->mode) {
        case MODE_SEQ_READ: mode_str = "seq-read"; break;
        case MODE_SEQ_WRITE: mode_str = "seq-write"; break;
        case MODE_RAND_READ: mode_str = "rand-read"; break;
        case MODE_RAND_WRITE: mode_str = "rand-write"; break;
        case MODE_MIXED: mode_str = "mixed"; break;
        default: mode_str = "unknown"; break;
    }
    
    printf("\n");
    printf("================================================================================\n");
    printf("BENCHMARK RESULTS\n");
    printf("================================================================================\n");
    printf("Test Mode:        %s\n", mode_str);
    printf("Block Size:       %zu bytes\n", config->block_size);
    printf("Duration:         %.2f seconds\n", stats->duration_sec);
    printf("Total Operations: %lu\n", stats->total_ops);
    printf("Total Data:       %.2f MB\n", stats->total_bytes / (1024.0 * 1024.0));
    printf("\n");
    printf("Throughput:       %.2f MB/s\n", throughput_mbps);
    printf("IOPS:             %.2f\n", iops);
    printf("\n");
    printf("Latency (microseconds):\n");
    printf("  Min:            %.2f\n", lat_min / 1000.0);
    printf("  Average:        %.2f\n", lat_avg / 1000.0);
    printf("  p50:            %.2f\n", lat_p50 / 1000.0);
    printf("  p95:            %.2f\n", lat_p95 / 1000.0);
    printf("  p99:            %.2f\n", lat_p99 / 1000.0);
    printf("  p99.9:          %.2f\n", lat_p999 / 1000.0);
    printf("  Max:            %.2f\n", lat_max / 1000.0);
    printf("================================================================================\n");
    
    // Write CSV if requested
    if (config->output_csv) {
        FILE *csv = fopen(config->output_csv, "a");
        if (csv) {
            // Check if file is empty (write header)
            fseek(csv, 0, SEEK_END);
            if (ftell(csv) == 0) {
                fprintf(csv, "timestamp,mode,block_size,duration_sec,total_ops,total_mb,throughput_mbps,iops,");
                fprintf(csv, "lat_min_us,lat_avg_us,lat_p50_us,lat_p95_us,lat_p99_us,lat_p999_us,lat_max_us\n");
            }
            
            fprintf(csv, "%ld,%s,%zu,%.2f,%lu,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                    time(NULL), mode_str, config->block_size, stats->duration_sec,
                    stats->total_ops, stats->total_bytes / (1024.0 * 1024.0),
                    throughput_mbps, iops,
                    lat_min / 1000.0, lat_avg / 1000.0, lat_p50 / 1000.0,
                    lat_p95 / 1000.0, lat_p99 / 1000.0, lat_p999 / 1000.0,
                    lat_max / 1000.0);
            fclose(csv);
            printf("\nResults appended to: %s\n", config->output_csv);
        }
    }
}

// Sequential read test
static void test_seq_read(config_t *config, stats_t *stats) {
    int flags = O_RDONLY;
    if (config->use_direct_io) flags |= O_DIRECT;
    
    int fd = open(config->filename, flags);
    if (fd < 0) {
        perror("open");
        exit(1);
    }
    
    void *buffer;
    if (posix_memalign(&buffer, 4096, config->block_size) != 0) {
        perror("posix_memalign");
        exit(1);
    }
    
    unsigned long start_time = get_time_ns();
    unsigned long end_time = start_time + (config->duration_sec * 1000000000UL);
    
    while (get_time_ns() < end_time) {
        lseek(fd, 0, SEEK_SET);
        
        while (1) {
            unsigned long op_start = get_time_ns();
            ssize_t bytes_read = read(fd, buffer, config->block_size);
            unsigned long op_end = get_time_ns();
            
            if (bytes_read <= 0) break;
            
            add_latency(stats, op_end - op_start);
            stats->total_bytes += bytes_read;
            stats->total_ops++;
            
            if (get_time_ns() >= end_time) break;
        }
    }
    
    stats->duration_sec = (get_time_ns() - start_time) / 1000000000.0;
    
    free(buffer);
    close(fd);
}

// Sequential write test
static void test_seq_write(config_t *config, stats_t *stats) {
    int flags = O_WRONLY | O_CREAT | O_TRUNC;
    if (config->use_direct_io) flags |= O_DIRECT;
    if (config->use_sync) flags |= O_SYNC;
    
    int fd = open(config->filename, flags, 0644);
    if (fd < 0) {
        perror("open");
        exit(1);
    }
    
    void *buffer;
    if (posix_memalign(&buffer, 4096, config->block_size) != 0) {
        perror("posix_memalign");
        exit(1);
    }
    memset(buffer, 0xAB, config->block_size);
    
    unsigned long start_time = get_time_ns();
    unsigned long end_time = start_time + (config->duration_sec * 1000000000UL);
    
    while (get_time_ns() < end_time) {
        unsigned long op_start = get_time_ns();
        ssize_t bytes_written = write(fd, buffer, config->block_size);
        unsigned long op_end = get_time_ns();
        
        if (bytes_written < 0) {
            perror("write");
            break;
        }
        
        add_latency(stats, op_end - op_start);
        stats->total_bytes += bytes_written;
        stats->total_ops++;
    }
    
    stats->duration_sec = (get_time_ns() - start_time) / 1000000000.0;
    
    free(buffer);
    close(fd);
}

// Random read test
static void test_rand_read(config_t *config, stats_t *stats) {
    int flags = O_RDONLY;
    if (config->use_direct_io) flags |= O_DIRECT;
    
    int fd = open(config->filename, flags);
    if (fd < 0) {
        perror("open");
        exit(1);
    }
    
    // Get file size
    struct stat st;
    fstat(fd, &st);
    off_t file_size = st.st_size;
    size_t num_blocks = file_size / config->block_size;
    
    void *buffer;
    if (posix_memalign(&buffer, 4096, config->block_size) != 0) {
        perror("posix_memalign");
        exit(1);
    }
    
    srand(time(NULL));
    
    unsigned long start_time = get_time_ns();
    unsigned long end_time = start_time + (config->duration_sec * 1000000000UL);
    
    while (get_time_ns() < end_time) {
        off_t offset = (rand() % num_blocks) * config->block_size;
        
        unsigned long op_start = get_time_ns();
        ssize_t bytes_read = pread(fd, buffer, config->block_size, offset);
        unsigned long op_end = get_time_ns();
        
        if (bytes_read < 0) {
            perror("pread");
            break;
        }
        
        add_latency(stats, op_end - op_start);
        stats->total_bytes += bytes_read;
        stats->total_ops++;
    }
    
    stats->duration_sec = (get_time_ns() - start_time) / 1000000000.0;
    
    free(buffer);
    close(fd);
}

// Random write test
static void test_rand_write(config_t *config, stats_t *stats) {
    int flags = O_WRONLY | O_CREAT;
    if (config->use_direct_io) flags |= O_DIRECT;
    if (config->use_sync) flags |= O_SYNC;
    
    int fd = open(config->filename, flags, 0644);
    if (fd < 0) {
        perror("open");
        exit(1);
    }
    
    // Ensure file is large enough
    if (ftruncate(fd, config->file_size) < 0) {
        perror("ftruncate");
        exit(1);
    }
    
    size_t num_blocks = config->file_size / config->block_size;
    
    void *buffer;
    if (posix_memalign(&buffer, 4096, config->block_size) != 0) {
        perror("posix_memalign");
        exit(1);
    }
    memset(buffer, 0xCD, config->block_size);
    
    srand(time(NULL));
    
    unsigned long start_time = get_time_ns();
    unsigned long end_time = start_time + (config->duration_sec * 1000000000UL);
    
    while (get_time_ns() < end_time) {
        off_t offset = (rand() % num_blocks) * config->block_size;
        
        unsigned long op_start = get_time_ns();
        ssize_t bytes_written = pwrite(fd, buffer, config->block_size, offset);
        unsigned long op_end = get_time_ns();
        
        if (bytes_written < 0) {
            perror("pwrite");
            break;
        }
        
        add_latency(stats, op_end - op_start);
        stats->total_bytes += bytes_written;
        stats->total_ops++;
    }
    
    stats->duration_sec = (get_time_ns() - start_time) / 1000000000.0;
    
    free(buffer);
    close(fd);
}

// Print usage
static void print_usage(const char *prog) {
    printf("Usage: %s [OPTIONS]\n", prog);
    printf("\nOptions:\n");
    printf("  -f FILE       Test file path (required)\n");
    printf("  -m MODE       Test mode: seq-read, seq-write, rand-read, rand-write (default: seq-read)\n");
    printf("  -s SIZE       File size in MB (default: %d)\n", DEFAULT_FILE_SIZE_MB);
    printf("  -b SIZE       Block size in bytes (default: %d)\n", DEFAULT_BLOCK_SIZE);
    printf("  -d DURATION   Test duration in seconds (default: %d)\n", DEFAULT_DURATION_SEC);
    printf("  -D            Use Direct I/O (bypass cache)\n");
    printf("  -S            Use synchronous I/O (O_SYNC)\n");
    printf("  -o FILE       Output CSV file\n");
    printf("  -h            Show this help\n");
    printf("\nExamples:\n");
    printf("  %s -f /tmp/testfile -m seq-read -d 10\n", prog);
    printf("  %s -f /tmp/testfile -m rand-write -b 4096 -D -o results.csv\n", prog);
}

int main(int argc, char *argv[]) {
    config_t config = {
        .filename = NULL,
        .mode = MODE_SEQ_READ,
        .file_size = DEFAULT_FILE_SIZE_MB * 1024 * 1024,
        .block_size = DEFAULT_BLOCK_SIZE,
        .duration_sec = DEFAULT_DURATION_SEC,
        .use_direct_io = 0,
        .use_sync = 0,
        .output_csv = NULL
    };
    
    int opt;
    while ((opt = getopt(argc, argv, "f:m:s:b:d:DSo:h")) != -1) {
        switch (opt) {
            case 'f':
                config.filename = optarg;
                break;
            case 'm':
                if (strcmp(optarg, "seq-read") == 0) config.mode = MODE_SEQ_READ;
                else if (strcmp(optarg, "seq-write") == 0) config.mode = MODE_SEQ_WRITE;
                else if (strcmp(optarg, "rand-read") == 0) config.mode = MODE_RAND_READ;
                else if (strcmp(optarg, "rand-write") == 0) config.mode = MODE_RAND_WRITE;
                else {
                    fprintf(stderr, "Invalid mode: %s\n", optarg);
                    exit(1);
                }
                break;
            case 's':
                config.file_size = atol(optarg) * 1024 * 1024;
                break;
            case 'b':
                config.block_size = atol(optarg);
                break;
            case 'd':
                config.duration_sec = atoi(optarg);
                break;
            case 'D':
                config.use_direct_io = 1;
                break;
            case 'S':
                config.use_sync = 1;
                break;
            case 'o':
                config.output_csv = optarg;
                break;
            case 'h':
                print_usage(argv[0]);
                exit(0);
            default:
                print_usage(argv[0]);
                exit(1);
        }
    }
    
    if (!config.filename) {
        fprintf(stderr, "Error: Test file (-f) is required\n\n");
        print_usage(argv[0]);
        exit(1);
    }
    
    // Initialize stats
    stats_t stats = {
        .latencies = malloc(MAX_LATENCIES * sizeof(unsigned long)),
        .count = 0,
        .capacity = MAX_LATENCIES,
        .total_bytes = 0,
        .total_ops = 0,
        .duration_sec = 0
    };
    
    if (!stats.latencies) {
        perror("malloc");
        exit(1);
    }
    
    printf("Starting disk benchmark...\n");
    printf("File: %s\n", config.filename);
    printf("Mode: ");
    switch (config.mode) {
        case MODE_SEQ_READ: printf("Sequential Read\n"); break;
        case MODE_SEQ_WRITE: printf("Sequential Write\n"); break;
        case MODE_RAND_READ: printf("Random Read\n"); break;
        case MODE_RAND_WRITE: printf("Random Write\n"); break;
        default: printf("Unknown\n"); break;
    }
    printf("Block Size: %zu bytes\n", config.block_size);
    printf("Duration: %d seconds\n", config.duration_sec);
    printf("Direct I/O: %s\n", config.use_direct_io ? "Yes" : "No");
    printf("Sync I/O: %s\n", config.use_sync ? "Yes" : "No");
    printf("\nRunning test...\n");
    
    // Run test
    switch (config.mode) {
        case MODE_SEQ_READ:
            test_seq_read(&config, &stats);
            break;
        case MODE_SEQ_WRITE:
            test_seq_write(&config, &stats);
            break;
        case MODE_RAND_READ:
            test_rand_read(&config, &stats);
            break;
        case MODE_RAND_WRITE:
            test_rand_write(&config, &stats);
            break;
        default:
            fprintf(stderr, "Mode not implemented\n");
            exit(1);
    }
    
    // Print results
    print_stats(&config, &stats);
    
    free(stats.latencies);
    return 0;
}
