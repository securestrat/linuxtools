# Disk Benchmark Tool Makefile

CC = gcc
CFLAGS = -O2 -Wall -Wextra -D_GNU_SOURCE
TARGET = disk_bench

# Platform-specific settings
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    LDFLAGS = -lrt
else
    LDFLAGS =
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): disk_bench.c
	$(CC) $(CFLAGS) -o $(TARGET) disk_bench.c $(LDFLAGS)

clean:
	rm -f $(TARGET) *.o

install: $(TARGET)
	install -m 755 $(TARGET) /usr/local/bin/
