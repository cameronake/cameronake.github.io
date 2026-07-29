# Native build for the limit order book engine.
#
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build
#   ctest --test-dir build --output-on-failure   # correctness tests
#   ./build/lob_bench                            # regenerate ../data/*.js
#
# WASM is a separate, offline step — see build_wasm.sh (needs emcc).
cmake_minimum_required(VERSION 3.16)
project(lob_engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

find_package(Threads REQUIRED)

add_library(lob_engine STATIC
  src/order_book.cpp
  src/feed_handler.cpp)
target_include_directories(lob_engine PUBLIC include)
target_link_libraries(lob_engine PUBLIC Threads::Threads)

if(MSVC)
  target_compile_options(lob_engine PRIVATE /W4 /O2)
else()
  target_compile_options(lob_engine PRIVATE -Wall -Wextra -O3)
endif()

# Benchmark harness -> writes ../data/lob_bench.js and ../data/lob_replay.js.
add_executable(lob_bench bench/bench.cpp)
target_link_libraries(lob_bench PRIVATE lob_engine)

# Correctness tests.
enable_testing()
add_executable(lob_tests tests/test_order_book.cpp)
target_link_libraries(lob_tests PRIVATE lob_engine)
add_test(NAME lob_tests COMMAND lob_tests)
