cmake_minimum_required(VERSION 3.24)
project(doaxvv_viewer LANGUAGES C CXX)

# Third-party sources live in third_party/ (SDL 3.4.20, Dear ImGui 1.93.1, cgltf 1.15,
# stb_image, renderdoc_app.h 1.7); nothing is fetched at configure time.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

if(NOT WIN32)
  message(FATAL_ERROR "the viewer renders with Direct3D 11 and only builds on Windows")
endif()

set(SDL_SHARED OFF CACHE BOOL "" FORCE)
set(SDL_STATIC ON CACHE BOOL "" FORCE)
set(SDL_TEST_LIBRARY OFF CACHE BOOL "" FORCE)
set(SDL_TESTS OFF CACHE BOOL "" FORCE)
set(SDL_EXAMPLES OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/SDL3 EXCLUDE_FROM_ALL)

set(IMGUI_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party/imgui)
add_library(imgui STATIC
  ${IMGUI_DIR}/imgui.cpp
  ${IMGUI_DIR}/imgui_demo.cpp
  ${IMGUI_DIR}/imgui_draw.cpp
  ${IMGUI_DIR}/imgui_tables.cpp
  ${IMGUI_DIR}/imgui_widgets.cpp
  ${IMGUI_DIR}/backends/imgui_impl_sdl3.cpp
  ${IMGUI_DIR}/backends/imgui_impl_dx11.cpp)
target_include_directories(imgui PUBLIC ${IMGUI_DIR} ${IMGUI_DIR}/backends)
target_link_libraries(imgui PUBLIC SDL3::SDL3-static)

add_executable(doaxvv_viewer WIN32
  src/main.cpp
  src/catalog.cpp
  src/gltf_model.cpp
  src/motion.cpp
  src/character.cpp
  src/game_renderer.cpp
  src/game_scene.cpp
  src/renderer.cpp
  src/ui.cpp
  src/third_party_impl.cpp)
target_include_directories(doaxvv_viewer PRIVATE
  src
  third_party/cgltf
  third_party/stb
  third_party/renderdoc)
target_compile_definitions(doaxvv_viewer PRIVATE
  NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS
  VIEWER_REPO_DIR="${CMAKE_CURRENT_SOURCE_DIR}/.."
  VIEWER_SHADER_DIR="${CMAKE_CURRENT_SOURCE_DIR}/shaders")
if(MSVC)
  target_compile_options(doaxvv_viewer PRIVATE /W4 /utf-8 /permissive-)
endif()
target_link_libraries(doaxvv_viewer PRIVATE imgui SDL3::SDL3-static d3d11 dxgi d3dcompiler)
