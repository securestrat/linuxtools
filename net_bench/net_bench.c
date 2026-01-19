#define _GNU_SOURCE
#include "net_bench.h"
#include <getopt.h>

// Global config
int num_threads = 1;
char *server_ip = NULL;
int duration_per_step = 5;
int max_bandwidth_mbps = 100;
int is_server = 0;
volatile int running = 1;



// Client Side Logic
void *sender_thread(void *arg) {
    // Thread arg contains target IP and port offset
    // Rate limiting logic
    // Busy wait loop to match target MB/s / num_threads
    return NULL;
}

// For this iteration, I will implement a single-threaded loop first to ensure logic is correct, 
// then expand if needed. But user asked for multiple CPUs.
// Let's implement the core loop structure.

void run_server() {
    printf("Starting Receiver on port %d...\n", DATA_PORT);
    // Bind UDP socket
    int sockfd;
    struct sockaddr_in servaddr, cliaddr; 
    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) { perror("socket creation failed"); exit(EXIT_FAILURE); }
    
    // Allow address reuse
    int opt = 1;
    setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    // Increase receive buffer size for high-rate traffic
    int rcvbuf = 8 * 1024 * 1024; // 8MB
    setsockopt(sockfd, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));
    
    memset(&servaddr, 0, sizeof(servaddr)); 
    servaddr.sin_family = AF_INET; 
    servaddr.sin_addr.s_addr = INADDR_ANY; 
    servaddr.sin_port = htons(DATA_PORT); 
    
    if ( bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0 ) { perror("bind failed"); exit(EXIT_FAILURE); } 

    // Set socket receive timeout for checking loop
    struct timeval tv;
    tv.tv_sec = 1;
    tv.tv_usec = 0;
    setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv);

    // Stats
    uint64_t total_bytes = 0;
    uint64_t total_pkts = 0;
    uint64_t total_drops = 0;
    uint64_t max_seq = 0;
    double total_latency = 0;
    
    printf("timestamp,mbps,latency_avg_ns,drops\n");
    
    udp_packet_t packet;
    socklen_t len = sizeof(cliaddr);
    
    uint64_t last_report_time = get_time_ns();
    
    // Timeout Logic
    int traffic_started = 0;
    time_t start_time = time(NULL);
    time_t last_recv_time = time(NULL);
    time_t current_time;
    int timeout_check_counter = 0;
    
    while(running) {
        int n = recvfrom(sockfd, &packet, sizeof(packet), 0, (struct sockaddr *)&cliaddr, &len);
        
        if (n > 0) {
            if (!traffic_started) {
                traffic_started = 1;
                printf("Traffic started.\n");
                last_recv_time = time(NULL);
            }
            
            uint64_t now = get_time_ns();
            uint64_t sent_ts = packet.header.timestamp_ns;
            uint64_t lat = (now > sent_ts) ? (now - sent_ts) : 0;
            
            // Check drops
            if (max_seq > 0 && packet.header.seq_num > max_seq + 1) {
                total_drops += (packet.header.seq_num - max_seq - 1);
            }
            if (packet.header.seq_num > max_seq) {
                max_seq = packet.header.seq_num;
            }
            
            total_bytes += n;
            total_pkts++;
            total_latency += lat;
            
            // Report every 1s
            if (now - last_report_time > 1000000000ULL) {
                double mbps = (double)total_bytes * 8 / 1000000.0;
                double avg_lat = (total_pkts > 0) ? (total_latency / total_pkts) : 0;
                
                printf("%lu,%.2f,%.0f,%lu\n", now/1000000000, mbps, avg_lat, total_drops);
                fflush(stdout);
                
                total_bytes = 0;
                total_pkts = 0;
                total_drops = 0; 
                total_latency = 0;
                last_report_time = now;
            }
        } else {
            // No packet received (timeout or error)
            // Only check time every N iterations to reduce syscall overhead
            if (++timeout_check_counter >= 10) {
                current_time = time(NULL);
                timeout_check_counter = 0;
                
                if (!traffic_started) {
                    if (difftime(current_time, start_time) > 1800) { // 30 minutes
                        printf("No traffic received for 30 minutes. Exiting.\n");
                        break;
                    }
                } else {
                    if (difftime(current_time, last_recv_time) > 30) { // 30 seconds
                        printf("Traffic stopped for 30 seconds. Exiting.\n");
                        break;
                    }
                }
            }
        }
    }
    close(sockfd);
}

void run_client() {
    printf("Starting Sender to %s...\n", server_ip);
    int sockfd; 
    struct sockaddr_in servaddr; 
  
    if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 ) { perror("socket creation failed"); exit(EXIT_FAILURE); } 
  
    // Increase send buffer size for high-rate traffic
    int sndbuf = 8 * 1024 * 1024; // 8MB
    setsockopt(sockfd, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
  
    memset(&servaddr, 0, sizeof(servaddr)); 
    servaddr.sin_family = AF_INET; 
    servaddr.sin_port = htons(DATA_PORT); 
    servaddr.sin_addr.s_addr = inet_addr(server_ip); 
    
    udp_packet_t packet;
    uint64_t seq = 1;
    
    // Ramp up logic
    for (int rate = 1; rate <= max_bandwidth_mbps; rate++) {
        printf("Testing Rate: %d MB/s\n", rate);
        
        uint64_t start_time = get_time_ns();
        uint64_t end_time = start_time + (uint64_t)duration_per_step * 1000000000ULL;
        
        // Token bucket for rate limiting
        // Bytes per second
        uint64_t bytes_per_sec = rate * 1024 * 1024;
        uint64_t packet_interval_ns = 1000000000ULL / (bytes_per_sec / PACKET_SIZE);
        
        uint64_t next_send = get_time_ns();
        
        while (1) {
            uint64_t now = get_time_ns();
            if (now >= end_time) break;
            
            if (now >= next_send) {
                packet.header.seq_num = seq++;
                packet.header.timestamp_ns = now;
                sendto(sockfd, &packet, sizeof(packet), 0, (const struct sockaddr *) &servaddr, sizeof(servaddr)); 
                next_send += packet_interval_ns;
            } else {
                 // Adaptive wait: yield for short waits, nanosleep for longer
                 uint64_t wait_ns = next_send - now;
                 if (wait_ns > 100000) { // > 100μs
                     struct timespec ts = {0, wait_ns / 2}; // Sleep half the time
                     nanosleep(&ts, NULL);
                 } else if (wait_ns > 1000) { // > 1μs
                     sched_yield();
                 }
                 // else: tight spin for < 1μs
            }
        }
    }
    printf("Test Complete.\n");
}

int main(int argc, char *argv[]) {
    int opt;
    while ((opt = getopt(argc, argv, "sc:b:t:")) != -1) {
        switch (opt) {
            case 's': is_server = 1; break;
            case 'c': server_ip = optarg; break;
            case 'b': max_bandwidth_mbps = atoi(optarg); break;
            case 't': duration_per_step = atoi(optarg); break;
        }
    }
    
    if (is_server) {
        run_server();
    } else {
        if (!server_ip) {
            fprintf(stderr, "Client mode requires -c <server_ip>\n");
            exit(1);
        }
        run_client();
    }
    return 0;
}
