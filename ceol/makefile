# Makefile for ceol
CXX = clang++
CXXFLAGS = -O2 -std=c++17

TARGET = ceol.exe
SRC = main.cpp tinyxml2.cpp

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

clean:
	del /Q ceol.exe 2>nul || rm -f ceol.exe
