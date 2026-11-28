// DOAXVV model viewer: costume + hair + face from out\models, official motion sets from out\motions.
#include "ui.h"

#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <imgui.h>
#include <imgui_impl_dx11.h>
#include <imgui_impl_sdl3.h>
#include <windows.h>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <string>

using namespace DirectX;
namespace fs = std::filesystem;

namespace {

RENDERDOC_API_1_1_2* load_renderdoc(bool force) {
    HMODULE module = GetModuleHandleA("renderdoc.dll");
    if (!module && force)
        module = LoadLibraryA("C:\\Program Files\\RenderDoc\\renderdoc.dll");
    if (!module)
        return nullptr;
    auto get_api = reinterpret_cast<pRENDERDOC_GetAPI>(GetProcAddress(module, "RENDERDOC_GetAPI"));
    RENDERDOC_API_1_1_2* api = nullptr;
    if (!get_api || !get_api(eRENDERDOC_API_Version_1_1_2, reinterpret_cast<void**>(&api)))
        return nullptr;
    return api;
}

XMVECTOR camera_eye(const CameraState& c) {
    XMVECTOR target = XMVectorSet(c.target[0], c.target[1], c.target[2], 1);
    XMVECTOR dir = XMVectorSet(std::cos(c.pitch) * std::sin(c.yaw), std::sin(c.pitch),
                               std::cos(c.pitch) * std::cos(c.yaw), 0);
    return XMVectorAdd(target, XMVectorScale(dir, c.distance));
}

void handle_camera(AppState& app, const SDL_Event& e) {
    CameraState& c = app.camera;
    if (e.type == SDL_EVENT_MOUSE_MOTION) {
        if (e.motion.state & SDL_BUTTON_LMASK) {
            c.yaw -= e.motion.xrel * 0.008f;
            c.pitch = std::clamp(c.pitch + e.motion.yrel * 0.008f, -1.5f, 1.5f);
        } else if (e.motion.state & (SDL_BUTTON_RMASK | SDL_BUTTON_MMASK)) {
            float scale = c.distance * 0.0015f;
            XMVECTOR eye = camera_eye(c);
            XMVECTOR target = XMVectorSet(c.target[0], c.target[1], c.target[2], 1);
            XMVECTOR forward = XMVector3Normalize(XMVectorSubtract(target, eye));
            XMVECTOR right = XMVector3Normalize(XMVector3Cross(forward, XMVectorSet(0, 1, 0, 0)));
            XMVECTOR up = XMVector3Cross(right, forward);
            target = XMVectorAdd(target, XMVectorScale(right, -e.motion.xrel * scale));
            target = XMVectorAdd(target, XMVectorScale(up, e.motion.yrel * scale));
            XMFLOAT3 t;
            XMStoreFloat3(&t, target);
            c.target[0] = t.x, c.target[1] = t.y, c.target[2] = t.z;
        }
    } else if (e.type == SDL_EVENT_MOUSE_WHEEL) {
        c.distance = std::clamp(c.distance * std::pow(0.9f, e.wheel.y), 0.05f, 50.0f);
    }
}

void draw_skeleton(const AppState& app, const XMMATRIX& view_proj, float width, float height) {
    ImDrawList* draw = ImGui::GetBackgroundDrawList();
    auto project = [&](const float p[3], ImVec2& out) {
        XMVECTOR v = XMVector4Transform(XMVectorSet(p[0], p[1], p[2], 1), view_proj);
        float w = XMVectorGetW(v);
        if (w <= 0.001f)
            return false;
        out = ImVec2((XMVectorGetX(v) / w * 0.5f + 0.5f) * width, (0.5f - XMVectorGetY(v) / w * 0.5f) * height);
        return true;
    };
    for (auto& s : app.character.skeleton()) {
        ImVec2 a, b;
        if (project(s.from, a) && project(s.to, b)) {
            draw->AddLine(a, b, IM_COL32(80, 255, 120, 220), 1.5f);
            draw->AddCircleFilled(b, 2.0f, IM_COL32(255, 255, 255, 220));
        }
    }
}

void write_report(const AppState& app, const std::vector<DrawItem>& items, const fs::path& path) {
    FILE* f = _wfopen(path.wstring().c_str(), L"w");
    if (!f)
        return;
    std::fprintf(f, "status: %s\nshader: %s\n", app.status.c_str(), app.shader_log.c_str());
    std::fprintf(f, "characters %d, motion files %d\n", int(app.catalog.characters.size()),
                 int(app.catalog.motion_files.size()));
    const Character& character = app.character;
    for (auto& part : character.parts()) {
        int textured = 0;
        for (auto& img : part.model->images)
            textured += img.texture ? 1 : 0;
        const GltfModel& m = *part.model;
        std::fprintf(f, "part %s: nodes %d primitives %d materials %d images %d (loaded %d) bounds %.3f %.3f %.3f .. %.3f %.3f %.3f\n",
                     part.glb.c_str(), int(m.nodes.size()), int(m.primitives.size()), int(m.materials.size()),
                     int(m.images.size()), textured, m.bounds_min[0], m.bounds_min[1], m.bounds_min[2],
                     m.bounds_max[0], m.bounds_max[1], m.bounds_max[2]);
    }
    std::fprintf(f, "motion set %d, banks %d, clips %d, clip %d frames %d, frame %.1f\n", app.motion_set,
                 int(character.banks().size()), int(character.clip_count()), app.clip,
                 character.clip_count() ? character.clip_frames(size_t(app.clip)) : 0, app.frame);
    std::fprintf(f, "draw items %d\n", int(items.size()));
    float top[3] = {0, -1e9f, 0};
    for (auto& s : character.skeleton())
        if (s.to[1] > top[1])
            std::copy(s.to, s.to + 3, top);
    std::fprintf(f, "highest bone tip %.3f %.3f %.3f\n", top[0], top[1], top[2]);
    std::fclose(f);
}

}  // namespace

int main(int argc, char** argv) {
    fs::path out_dir = fs::path(VIEWER_REPO_DIR) / "out";
    fs::path shader_dir = VIEWER_SHADER_DIR;
    bool force_renderdoc = false;
    // --screenshot renders a few frames, writes the BMP plus a .txt report and exits (for scripted checks)
    fs::path screenshot;
    int start_row = 10, start_motion = -1, start_clip = 0, start_debug = 0, shot_frames = 20;
    float start_frame = 0;
    bool show_ui = true, show_skeleton = false, camera_override = false;
    CameraState camera;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        bool has_value = i + 1 < argc;
        if (arg == "--out" && has_value)
            out_dir = fs::path(reinterpret_cast<const char8_t*>(argv[++i]));
        else if (arg == "--shaders" && has_value)
            shader_dir = fs::path(reinterpret_cast<const char8_t*>(argv[++i]));
        else if (arg == "--renderdoc")
            force_renderdoc = true;
        else if (arg == "--screenshot" && has_value)
            screenshot = fs::path(reinterpret_cast<const char8_t*>(argv[++i]));
        else if (arg == "--char" && has_value)
            start_row = std::atoi(argv[++i]);
        else if (arg == "--motion" && has_value)
            start_motion = std::atoi(argv[++i]);
        else if (arg == "--clip" && has_value)
            start_clip = std::atoi(argv[++i]);
        else if (arg == "--frame" && has_value)
            start_frame = float(std::atof(argv[++i]));
        else if (arg == "--debug" && has_value)
            start_debug = std::atoi(argv[++i]);
        else if (arg == "--camera" && i + 6 < argc) {
            camera_override = true;
            for (int k = 0; k < 3; ++k)
                camera.target[k] = float(std::atof(argv[++i]));
            camera.distance = float(std::atof(argv[++i]));
            camera.yaw = float(std::atof(argv[++i]));
            camera.pitch = float(std::atof(argv[++i]));
        } else if (arg == "--no-ui")
            show_ui = false;
        else if (arg == "--skeleton")
            show_skeleton = true;
    }

    AppState app;
    // RenderDoc has to hook D3D11 before the device is created
    app.renderdoc = load_renderdoc(force_renderdoc);
    if (app.renderdoc) {
        std::string capture = (fs::path(VIEWER_REPO_DIR) / "out" / "captures" / "viewer").string();
        fs::create_directories(fs::path(capture).parent_path());
        app.renderdoc->SetCaptureFilePathTemplate(capture.c_str());
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "doaxvv_viewer", SDL_GetError(), nullptr);
        return 1;
    }
    SDL_Window* window = SDL_CreateWindow("DOAXVV Viewer", 1680, 1000, SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY);
    if (!window) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "doaxvv_viewer", SDL_GetError(), nullptr);
        return 1;
    }
    HWND hwnd = static_cast<HWND>(
        SDL_GetPointerProperty(SDL_GetWindowProperties(window), SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr));
    int width = 0, height = 0;
    SDL_GetWindowSizeInPixels(window, &width, &height);

    Renderer renderer;
    renderer.shader_dir = shader_dir;
    std::string error;
    if (!renderer.init(hwnd, width, height, error)) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "doaxvv_viewer", error.c_str(), window);
        return 1;
    }
    app.renderer = &renderer;
    if (!renderer.reload_shaders(app.shader_log) && app.shader_log.empty())
        app.shader_log = "着色器编译失败";

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = "doaxvv_viewer.ini";
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    float dpi = SDL_GetWindowDisplayScale(window);
    if (dpi <= 0)
        dpi = 1;
    ImGui::StyleColorsDark();
    ImGui::GetStyle().ScaleAllSizes(dpi);
    ImGui::GetStyle().FontScaleDpi = dpi;
    if (fs::exists("C:\\Windows\\Fonts\\msyh.ttc"))
        io.Fonts->AddFontFromFileTTF("C:\\Windows\\Fonts\\msyh.ttc", 16.0f);
    ImGui_ImplSDL3_InitForD3D(window);
    ImGui_ImplDX11_Init(renderer.device(), renderer.context());

    if (!app.catalog.load(out_dir, error))
        app.status = error;
    else if (!app.catalog.characters.empty()) {
        int start = 0;
        for (int i = 0; i < int(app.catalog.characters.size()); ++i)
            if (app.catalog.characters[i].row == start_row)
                start = i;
        select_character(app, start);
        if (start_motion >= 0)
            select_motion(app, start_motion);
    }
    app.clip = start_clip;
    app.frame = start_frame;
    if (start_motion >= 0)
        frame_camera(app);
    app.view.debug_mode = start_debug;
    app.view.skeleton = show_skeleton;
    if (camera_override)
        app.camera = camera;
    if (!screenshot.empty())
        app.playing = false;
    int frame_number = 0;

    std::vector<XMFLOAT4X4> joints;
    std::vector<DrawItem> items;
    uint64_t last = SDL_GetTicksNS();
    uint64_t last_poll = last;
    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            ImGui_ImplSDL3_ProcessEvent(&e);
            if (e.type == SDL_EVENT_QUIT ||
                (e.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED && e.window.windowID == SDL_GetWindowID(window)))
                running = false;
            else if (e.type == SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED) {
                width = e.window.data1, height = e.window.data2;
                renderer.resize(width, height);
            } else if (e.type == SDL_EVENT_KEY_DOWN && !io.WantCaptureKeyboard) {
                if (e.key.key == SDLK_F5)
                    renderer.reload_shaders(app.shader_log);
                else if (e.key.key == SDLK_F11 && app.renderdoc)
                    app.renderdoc->TriggerCapture();
                else if (e.key.key == SDLK_SPACE)
                    app.playing = !app.playing;
                else if (e.key.key == SDLK_F)
                    frame_camera(app);
                else if (e.key.key == SDLK_TAB)
                    show_ui = !show_ui;
            }
            if ((e.type == SDL_EVENT_MOUSE_MOTION || e.type == SDL_EVENT_MOUSE_WHEEL) && !io.WantCaptureMouse)
                handle_camera(app, e);
        }
        if (SDL_GetWindowFlags(window) & SDL_WINDOW_MINIMIZED) {
            SDL_Delay(50);
            continue;
        }

        uint64_t now = SDL_GetTicksNS();
        float dt = float(double(now - last) * 1e-9);
        last = now;
        if (now - last_poll > 500'000'000ull) {
            last_poll = now;
            renderer.poll_shaders(app.shader_log);
        }

        int clips = int(app.character.clip_count());
        if (clips > 0) {
            app.clip = std::clamp(app.clip, 0, clips - 1);
            int frames = app.character.clip_frames(size_t(app.clip));
            if (app.playing && frames > 1) {
                app.frame += dt * app.fps * app.speed;
                app.frame = std::fmod(app.frame, float(frames - 1));
            }
        }
        app.character.pose(size_t(std::max(app.clip, 0)), app.frame, app.animate && clips > 0);

        const CameraState& cam = app.camera;
        XMVECTOR eye = camera_eye(cam);
        XMMATRIX view = XMMatrixLookAtRH(eye, XMVectorSet(cam.target[0], cam.target[1], cam.target[2], 1),
                                         XMVectorSet(0, 1, 0, 0));
        XMMATRIX proj = XMMatrixPerspectiveFovRH(cam.fov, float(width) / float(std::max(height, 1)),
                                                 std::max(0.005f, cam.distance * 0.01f), 200.0f);
        XMMATRIX view_proj = XMMatrixMultiply(view, proj);

        const ViewSettings& v = app.view;
        FrameConstants frame;
        XMStoreFloat4x4(&frame.view_proj, view_proj);
        XMFLOAT3 eye3;
        XMStoreFloat3(&eye3, eye);
        frame.camera_pos = XMFLOAT4(eye3.x, eye3.y, eye3.z, 1);
        // light direction is relative to the camera yaw so the lit side follows the orbit
        float yaw = cam.yaw + v.light_yaw;
        frame.light_dir = XMFLOAT4(std::cos(v.light_pitch) * std::sin(yaw), std::sin(v.light_pitch),
                                   std::cos(v.light_pitch) * std::cos(yaw), v.light_intensity);
        frame.light_color = XMFLOAT4(v.light_color[0], v.light_color[1], v.light_color[2], v.ambient);
        frame.sky_color = XMFLOAT4(v.sky[0], v.sky[1], v.sky[2], v.normal_maps ? 1.0f : 0.0f);
        frame.ground_color = XMFLOAT4(v.ground[0], v.ground[1], v.ground[2], v.exposure);
        frame.debug_mode = v.debug_mode;
        frame.debug_slot = v.debug_slot;
        frame.debug_channel = v.debug_channel;

        const ModelMaterial* highlight = nullptr;
        auto& parts = app.character.parts();
        if (app.inspect_part >= 0 && app.inspect_part < int(parts.size()) && app.inspect_material >= 0 &&
            app.inspect_material < int(parts[app.inspect_part].model->materials.size()))
            highlight = &parts[app.inspect_part].model->materials[app.inspect_material];

        joints.clear();
        items.clear();
        app.character.gather(renderer, view, joints, items, v.debug_slot, highlight);
        renderer.upload_joints(joints);
        float clear[4] = {v.background[0], v.background[1], v.background[2], 1};
        renderer.begin_frame(clear);
        renderer.draw_scene(items, frame, v.wireframe);

        ImGui_ImplDX11_NewFrame();
        ImGui_ImplSDL3_NewFrame();
        ImGui::NewFrame();
        if (show_ui)
            draw_ui(app);
        if (app.view.skeleton)
            draw_skeleton(app, view_proj, io.DisplaySize.x, io.DisplaySize.y);
        ImGui::Render();
        renderer.begin_ui();
        ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
        if (!screenshot.empty() && ++frame_number == shot_frames) {
            renderer.save_backbuffer(screenshot);
            write_report(app, items, fs::path(screenshot).replace_extension(".txt"));
            running = false;
        }
        renderer.present(app.view.vsync);
    }

    ImGui_ImplDX11_Shutdown();
    ImGui_ImplSDL3_Shutdown();
    ImGui::DestroyContext();
    app.character = Character();
    renderer.shutdown();
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
