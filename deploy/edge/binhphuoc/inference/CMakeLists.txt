cmake_minimum_required(VERSION 3.14)
project(fire_inference CXX)

set(CMAKE_CXX_STANDARD 17)

# ── ONNX Runtime ──────────────────────────────────────────────────────
set(ONNXRUNTIME_ROOT "$ENV{ONNXRUNTIME_ROOT}" CACHE PATH "ONNX Runtime root")
if(NOT ONNXRUNTIME_ROOT)
  set(ONNXRUNTIME_ROOT "/usr/local")
endif()

find_path(ORT_INCLUDE onnxruntime_cxx_api.h HINTS ${ONNXRUNTIME_ROOT}/include)
find_library(ORT_LIB onnxruntime HINTS ${ONNXRUNTIME_ROOT}/lib ${ONNXRUNTIME_ROOT}/lib64)

if(NOT ORT_INCLUDE OR NOT ORT_LIB)
  message(FATAL_ERROR "ONNX Runtime not found. Set ONNXRUNTIME_ROOT.")
endif()

# ── Mosquitto ─────────────────────────────────────────────────────────
find_path(MOSQ_INCLUDE mosquitto.h)
find_library(MOSQ_LIB mosquitto)

if(NOT MOSQ_INCLUDE OR NOT MOSQ_LIB)
  message(FATAL_ERROR "libmosquitto not found. Install libmosquitto-dev.")
endif()

# ── Target ────────────────────────────────────────────────────────────
add_executable(fire_inference inference.cpp)

target_include_directories(fire_inference PRIVATE ${ORT_INCLUDE} ${MOSQ_INCLUDE})
target_link_libraries(fire_inference PRIVATE ${ORT_LIB} ${MOSQ_LIB} pthread)

install(TARGETS fire_inference RUNTIME DESTINATION bin)
