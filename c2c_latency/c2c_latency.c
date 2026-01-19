#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <pthread.h>
#include <sched.h>
#include <string.h>
#include <time.h>
#include <getopt.h>
#include <errno.h>

// Cache line size is typically 64 bytes. 
// We align structures to avoid false sharing.
#define CACHE_LINE_SIZE 64
#define ITERATIONS 100000

typedef struct {
    volatile uint64_t flag __attribute__((aligned(CACHE_LINE_SIZE)));
    volatile uint64_t turn __attribute__((aligned(CACHE_LINE_SIZE)));
    // Padding to ensure separate cache lines if the compiler packs aggressively
    char pad[CACHE_LINE_SIZE]; 
} shared_data_t;

typedef struct {
    int thread_id;
    int cpu_id;
    shared_data_t *data;
} thread_args_t;

// Helper to get RDTSC
static inline uint64_t rdtsc(void) {
    unsigned int lo, hi;
    __asm__ __volatile__ ("rdtsc" : "=a" (lo), "=d" (hi));
    return ((uint64_t)hi << 32) | lo;
}

// Function to pin thread to a core
void pin_thread_to_core(int core_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(core_id, &cpuset);

    pthread_t current_thread = pthread_self();
    if (pthread_setaffinity_np(current_thread, sizeof(cpu_set_t), &cpuset) != 0) {
        fprintf(stderr, "Error calling pthread_setaffinity_np: %s\n", strerror(errno));
        // We continue, but results might be noisy
    }
}

// Thread function
void *ping_pong_thread(void *arg) {
    thread_args_t *args = (thread_args_t *)arg;
    pin_thread_to_core(args->cpu_id);
    
    shared_data_t *data = args->data;
    int is_leader = (args->thread_id == 0);

    // Warmup / Synchronization
    // Just a simple barrier to try to start somewhat together
    if (is_leader) {
        data->turn = 0;
    }

    // Prepare for loop
    // We want to measure round trip essentially.
    
    // Logic:
    // Leader writes 1, Follower sees 1, Follower writes 0, Leader sees 0.
    // Latency = (Time Leader sees 0 - Time Leader wrote 1) / 2
    
    // Actually, simpler:
    // Thread 0 waits for turn == 0, then sets turn = 1
    // Thread 1 waits for turn == 1, then sets turn = 0
    
    if (is_leader) {
        for (int i = 0; i < ITERATIONS; i++) {
            while (data->turn != 0) {
                // Busy wait
                // __asm__ __volatile__("pause"); // Optional: nice for hyperthreading, but might affect pure latency?
            }
            data->turn = 1;
        }
    } else {
        for (int i = 0; i < ITERATIONS; i++) {
            while (data->turn != 1) {
                // Busy wait
            }
            data->turn = 0;
        }
    }

    return NULL;
}



// Optimized Thread Functions for Measurement
typedef struct {
    int cpu_to_pin;
    shared_data_t *data;
    uint64_t total_cycles;
} measure_args_t;

void *thread_leader(void *arg) {
    measure_args_t *args = (measure_args_t *)arg;
    pin_thread_to_core(args->cpu_to_pin);
    shared_data_t *data = args->data;
    
    // Sync start
    data->turn = 0;
    
    // Wait for follower to be ready? 
    // We can rely on a separate flag or sleep.
    // A simple nanosleep to let the other thread spin up is often sufficient for a benchmark tool.
    struct timespec ts = {0, 1000000}; // 1ms
    nanosleep(&ts, NULL);

    uint64_t start = rdtsc();
    for (int i = 0; i < ITERATIONS; i++) {
        data->turn = 1;         // Signal other
        while (data->turn == 1); // Wait for return
    }
    uint64_t end = rdtsc();
    
    args->total_cycles = end - start;
    return NULL;
}

void *thread_follower(void *arg) {
    measure_args_t *args = (measure_args_t *)arg;
    pin_thread_to_core(args->cpu_to_pin);
    shared_data_t *data = args->data;
    
    for (int i = 0; i < ITERATIONS; i++) {
        while (data->turn == 0); // Wait for signal
        data->turn = 0;          // Signal back
    }
    return NULL;
}

double run_benchmark(int cpu1, int cpu2) {
    pthread_t t1, t2;
    shared_data_t *data = aligned_alloc(CACHE_LINE_SIZE, sizeof(shared_data_t));
    if (!data) { perror("malloc"); return -1; }
    memset(data, 0, sizeof(shared_data_t));
    
    measure_args_t args1 = {cpu1, data, 0};
    measure_args_t args2 = {cpu2, data, 0};
    
    pthread_create(&t2, NULL, thread_follower, &args2); // Start follower first
    pthread_create(&t1, NULL, thread_leader, &args1);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    free(data);
    
    // total_cycles is for ITERATIONS round-trips.
    // One round trip is (CPU1->CPU2 + CPU2->CPU1).
    // We usually report one-way latency.
    return (double)args1.total_cycles / (2.0 * ITERATIONS);
}

void print_help(char *prog) {
    printf("Usage: %s [-c cpu1,cpu2] [-m] [-h]\n", prog);
    printf("  -c: Measure latency between two specific cores.\n");
    printf("  -m: Output a matrix of latencies for all core pairs.\n");
    printf("  -h: Show this help.\n");
}

int main(int argc, char *argv[]) {
    int opt;
    int mode_matrix = 0;
    int cpu1 = -1, cpu2 = -1;
    
    while ((opt = getopt(argc, argv, "mc:h")) != -1) {
        switch (opt) {
            case 'm':
                mode_matrix = 1;
                break;
            case 'c':
                sscanf(optarg, "%d,%d", &cpu1, &cpu2);
                break;
            case 'h':
                print_help(argv[0]);
                return 0;
            default:
                print_help(argv[0]);
                return 1;
        }
    }
    
    if (!mode_matrix && (cpu1 == -1 || cpu2 == -1)) {
        // Default to Matrix if no args? Or just show help? 
        // Let's default to matrix if nothing specified is usually nice, but let's strictly follow flags.
        // If nothing, print help.
        print_help(argv[0]);
        return 1;
    }

    if (mode_matrix) {
        long num_cores = sysconf(_SC_NPROCESSORS_ONLN);
        printf("Measuring core-to-core latency for %ld cores...\n", num_cores);
        
        // Print Header
        printf("      ");
        for (int j = 0; j < num_cores; j++) {
            printf(" %5d", j);
        }
        printf("\n");
        
        for (int i = 0; i < num_cores; i++) {
            printf("%5d ", i);
            for (int j = 0; j < num_cores; j++) {
                if (i == j) {
                    printf("     -");
                    continue;
                }
                double latency = run_benchmark(i, j);
                printf(" %5.0f", latency);
                fflush(stdout);
            }
            printf("\n");
        }
    } else {
        printf("Measuring latency between core %d and %d...\n", cpu1, cpu2);
        double latency = run_benchmark(cpu1, cpu2);
        printf("Latency: %.2f cycles\n", latency);
    }

    return 0;
}
