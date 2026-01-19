#ifndef NET_BENCH_H
#define NET_BENCH_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <time.h>
#include <sys/time.h>
#include <errno.h>

#define CTRL_PORT 10000
#define DATA_PORT 10001
#define PACKET_SIZE 1400 // Safe UDP payload size

typedef struct {
    uint64_t seq_num;
    uint64_t timestamp_ns;
} packet_header_t;

typedef struct {
    packet_header_t header;
    char payload[PACKET_SIZE - sizeof(packet_header_t)];
} udp_packet_t;

// Statistics for a time window
typedef struct {
    uint64_t packets_received;
    uint64_t bytes_received;
    uint64_t packets_lost;
    double latency_sum_ns;
    uint64_t latency_count;
    uint32_t target_bw_mbps;
} interval_stats_t;

// Global control flags
extern volatile int running;

// Utils
static inline uint64_t get_time_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

#endif
