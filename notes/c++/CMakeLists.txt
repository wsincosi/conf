cmake_minimum_required(VERSION 3.10)

project(LearnC++ VERSION 1.0 LANGUAGES CXX)

# Set the C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Set source and include directories
set(INCLUDE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/include)
set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Collect source files (explicitly listing is better than GLOB)
set(SOURCE_FILES
    ${SRC_DIR}/site.cpp
    # Add more files explicitly
)

# Define the executable
add_executable(app ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp ${SOURCE_FILES})

# Add include directories (target-specific)
target_include_directories(app PRIVATE ${INCLUDE_DIR})

# Find and link MPI
find_package(MPI REQUIRED)
target_include_directories(app PRIVATE ${MPI_INCLUDE_PATH})
target_link_libraries(app PRIVATE MPI::MPI_CXX)

# Optionally enable warnings (good practice in CMake projects)
target_compile_options(app PRIVATE -Wall -Wextra -Wpedantic)
