CC = gcc
CFLAGS = -O3 -pthread -Wall
TARGET = net_bench
SRC = net_bench.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)
