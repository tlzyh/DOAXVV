// Application state and the ImGui panels.
#pragma once

#include "catalog.h"
#include "character.h"
#include "game_renderer.h"
#include "renderer.h"

#include <renderdoc_app.h>

#include <string>

struct ViewSettings {
    float light_yaw = 0.6f, light_pitch = 0.7f;
    float light_intensity = 2.2f;
    float light_color[3] = {1.0f, 0.97f, 0.92f};
    float ambient = 0.55f;
    float sky[3] = {0.75f, 0.82f, 1.0f};
    float ground[3] = {0.45f, 0.40f, 0.38f};
    float exposure = 1.0f;
    float background[3] = {0.18f, 0.19f, 0.22f};
    bool normal_maps = true;
    bool wireframe = false;
    bool skeleton = false;
    int debug_mode = 0;
    int debug_slot = 0;
    int debug_channel = 0;
    bool vsync = true;
};

enum class RenderMode { Simple, Game };

// game render mode: lights and post-processing of a RenderDoc capture (阶段总结.md 14)
struct GameView {
    int debug_view = GameFinal;
    bool normal_maps = true, tone_curve = true, bloom = true, sss = true;
};

struct CameraState {
    float yaw = 0.0f, pitch = 0.1f, distance = 2.6f;
    float target[3] = {0.0f, 0.95f, 0.0f};
    float fov = 0.6f;
};

struct AppState {
    Renderer* renderer = nullptr;
    Catalog catalog;
    Character character;
    ViewSettings view;
    CameraState camera;
    RenderMode render = RenderMode::Game;
    GameScene scene;
    GameRenderer game;
    GameView game_view;
    std::string scene_error;

    int character_index = -1;
    std::string costume_glb, hair_glb;
    char filter[64] = {};

    int motion_set = -1;
    int clip = 0;
    float frame = 0;
    bool playing = true;
    bool animate = true;
    float speed = 1.0f;
    float fps = 60.0f;

    int inspect_part = 0;
    int inspect_material = -1;
    int preview_slot = -1;
    int preview_channel = 5;

    std::string status;
    std::string shader_log;
    RENDERDOC_API_1_1_2* renderdoc = nullptr;
};

void select_character(AppState& app, int index);
// glb relative to the out folder, empty removes the part
void load_part(AppState& app, PartRole role, const std::string& glb);
// index into the character's motion_sets list, -1 = bind pose
void select_motion(AppState& app, int index);
// fits the costume's bind-pose bounds into view
void frame_camera(AppState& app);
void draw_ui(AppState& app);
// simple + game mode shaders; errors go to app.shader_log
void reload_all_shaders(AppState& app);
