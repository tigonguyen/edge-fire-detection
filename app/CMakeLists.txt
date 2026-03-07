cmake_minimum_required(VERSION 3.14)
project(fire_detection_backend CXX)

set(CMAKE_CXX_STANDARD 17)

# ONNX Runtime: use env ONNXRUNTIME_ROOT or system install
set(ONNXRUNTIME_ROOT "$ENV{ONNXRUNTIME_ROOT}" CACHE PATH "ONNX Runtime root")
if(NOT ONNXRUNTIME_ROOT)
  set(ONNXRUNTIME_ROOT "/usr/local")
endif()

find_path(ONNXRUNTIME_INCLUDE onnxruntime_cxx_api.h HINTS ${ONNXRUNTIME_ROOT}/include)
find_library(ONNXRUNTIME_LIB onnxruntime HINTS ${ONNXRUNTIME_ROOT}/lib ${ONNXRUNTIME_ROOT}/lib64)

if(NOT ONNXRUNTIME_INCLUDE OR NOT ONNXRUNTIME_LIB)
  message(FATAL_ERROR "ONNX Runtime not found. Set ONNXRUNTIME_ROOT or install libonnxruntime-dev")
endif()

add_executable(fire_backend
  src/main.cpp
)

target_include_directories(fire_backend PRIVATE
  ${ONNXRUNTIME_INCLUDE}
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(fire_backend PRIVATE
  ${ONNXRUNTIME_LIB}
  pthread
)

# Optional: static linking for smaller container
# target_link_libraries(fire_backend PRIVATE ${ONNXRUNTIME_LIB} -static-libgcc -static-libstdc++)

install(TARGETS fire_backend RUNTIME DESTINATION bin)
