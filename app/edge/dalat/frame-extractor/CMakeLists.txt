cmake_minimum_required(VERSION 3.14)
project(fire_frame_extractor CXX)

set(CMAKE_CXX_STANDARD 17)

# Find Packages
find_package(OpenCV REQUIRED core imgproc videoio)
find_package(CURL REQUIRED)

# Header boundaries
find_path(NLOHMANN_JSON_INCLUDE nlohmann/json.hpp)
find_path(MOSQ_INCLUDE mosquitto.h)
find_library(MOSQ_LIB mosquitto)

if(NOT MOSQ_LIB)
  message(FATAL_ERROR "libmosquitto not found.")
endif()

if(NOT NLOHMANN_JSON_INCLUDE)
  message(FATAL_ERROR "nlohmann-json not found.")
endif()

# Target
add_executable(fire_frame_extractor extractor.cpp)

target_include_directories(fire_frame_extractor PRIVATE 
    ${OpenCV_INCLUDE_DIRS} 
    ${MOSQ_INCLUDE} 
    ${NLOHMANN_JSON_INCLUDE}
    ${CURL_INCLUDE_DIRS}
)

target_link_libraries(fire_frame_extractor PRIVATE 
    ${OpenCV_LIBS} 
    ${MOSQ_LIB}
    ${CURL_LIBRARIES}
    pthread
)

install(TARGETS fire_frame_extractor RUNTIME DESTINATION bin)
