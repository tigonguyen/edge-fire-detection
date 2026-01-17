cmake_minimum_required(VERSION 3.14)
project(FireDetectionApp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find packages
find_package(OpenCV REQUIRED)
find_package(Torch REQUIRED)

# Include directories
include_directories(
    ${OpenCV_INCLUDE_DIRS}
    ${TORCH_INCLUDE_DIRS}
    ${CMAKE_SOURCE_DIR}/include
)

# Source files
set(SOURCES
    src/main.cpp
    src/fire_detector.cpp
)

# Create executable
add_executable(fire_detector ${SOURCES})

# Link libraries
target_link_libraries(fire_detector
    ${OpenCV_LIBS}
    ${TORCH_LIBRARIES}
)

# Set C++ flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")

# Copy resources
file(COPY ${CMAKE_SOURCE_DIR}/../README.md DESTINATION ${CMAKE_BINARY_DIR})

# Installation
install(TARGETS fire_detector DESTINATION bin)

# Print configuration
message(STATUS "===== Fire Detection App Configuration =====")
message(STATUS "OpenCV version: ${OpenCV_VERSION}")
message(STATUS "OpenCV include dirs: ${OpenCV_INCLUDE_DIRS}")
message(STATUS "Torch found: ${TORCH_FOUND}")
message(STATUS "Torch include dirs: ${TORCH_INCLUDE_DIRS}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "============================================")

