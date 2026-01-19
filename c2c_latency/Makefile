CC = gcc
CFLAGS = -O3 -pthread -Wall
TARGET = c2c_latency
SRC = c2c_latency.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)
