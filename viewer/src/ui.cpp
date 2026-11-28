#include "ui.h"

#include <imgui.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>

namespace {

const char* role_name(PartRole role) {
    switch (role) {
        case PartRole::Costume: return "服装";
        case PartRole::Hair: return "发型";
        case PartRole::Face: return "脸";
        default: return "其他";
    }
}

const CharacterEntry* current_character(const AppState& app) {
    return app.character_index >= 0 && app.character_index < int(app.catalog.characters.size())
               ? &app.catalog.characters[app.character_index]
               : nullptr;
}

void load_part(AppState& app, PartRole role, const std::string& glb) {
    std::string error;
    if (!app.character.set_part(role, glb, app.catalog.out_dir, *app.renderer, error))
        app.status = error;
    app.inspect_material = -1;
    app.preview_slot = -1;
}

}  // namespace

void select_motion(AppState& app, int index) {
    bool had_motion = app.character.clip_count() > 0;
    app.motion_set = index;
    app.clip = 0;
    app.frame = 0;
    const CharacterEntry* ch = current_character(app);
    if (!ch || index < 0) {
        app.character.clear_motion();
        if (had_motion)
            frame_camera(app);
        return;
    }
    const MotionSet& set = app.catalog.motion_sets[ch->row][index];
    std::vector<std::pair<std::string, std::string>> banks;
    for (auto& b : set.banks)
        banks.push_back({b.hash, b.kind});
    std::string error;
    if (!app.character.set_motion(banks, app.catalog.motion_files, app.catalog.out_dir, error))
        app.status = error.empty() ? "这个动作组里没有身体、手、表情或胸部动作" : error;
    else
        app.status = error;
    if (had_motion != (app.character.clip_count() > 0))
        frame_camera(app);
}

namespace {

bool matches(const std::string& text, const char* filter) {
    if (!*filter)
        return true;
    auto lower = [](std::string s) {
        for (char& c : s)
            c = char(std::tolower(static_cast<unsigned char>(c)));
        return s;
    };
    return lower(text).find(lower(filter)) != std::string::npos;
}

void character_panel(AppState& app) {
    ImGui::SetNextWindowPos(ImVec2(10, 10), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(330, 640), ImGuiCond_FirstUseEver);
    ImGui::Begin("角色");
    const auto& chars = app.catalog.characters;
    const CharacterEntry* ch = current_character(app);
    if (ImGui::BeginCombo("角色", ch ? ch->code.c_str() : "-")) {
        for (int i = 0; i < int(chars.size()); ++i)
            if (ImGui::Selectable(chars[i].code.c_str(), i == app.character_index))
                select_character(app, i);
        ImGui::EndCombo();
    }
    ch = current_character(app);
    if (!ch) {
        ImGui::End();
        return;
    }
    ImGui::TextDisabled("脸 %s", ch->face_glb.c_str());
    ImGui::InputTextWithHint("##filter", "按名字过滤", app.filter, sizeof(app.filter));
    auto& list = app.catalog.costumes[ch->row];
    for (const char* kind : {"cos", "hair"}) {
        bool is_hair = std::string(kind) == "hair";
        std::string& current = is_hair ? app.hair_glb : app.costume_glb;
        int count = int(std::count_if(list.begin(), list.end(), [&](const CostumeEntry& e) { return e.kind == kind; }));
        char label[64];
        std::snprintf(label, sizeof(label), "%s (%d)###%s", is_hair ? "发型" : "服装", count, kind);
        if (!ImGui::CollapsingHeader(label, is_hair ? 0 : ImGuiTreeNodeFlags_DefaultOpen))
            continue;
        ImGui::BeginChild(kind, ImVec2(0, is_hair ? 140.0f : 300.0f), ImGuiChildFlags_Borders);
        for (auto& e : list) {
            if (e.kind != kind || !matches(e.tmc_name, app.filter))
                continue;
            char item[160];
            std::snprintf(item, sizeof(item), "%s  #%d", e.tmc_name.c_str(), e.number);
            if (ImGui::Selectable(item, current == e.glb)) {
                current = e.glb;
                load_part(app, is_hair ? PartRole::Hair : PartRole::Costume, e.glb);
            }
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("%s", e.glb.c_str());
        }
        ImGui::EndChild();
    }
    if (ImGui::Button("去掉发型")) {
        app.hair_glb.clear();
        load_part(app, PartRole::Hair, "");
    }
    ImGui::SameLine();
    if (ImGui::Button("去掉脸"))
        load_part(app, PartRole::Face, "");
    ImGui::SameLine();
    if (ImGui::Button("加回脸"))
        load_part(app, PartRole::Face, ch->face_glb);
    ImGui::End();
}

void motion_panel(AppState& app) {
    ImGui::SetNextWindowPos(ImVec2(10, 660), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(330, 330), ImGuiCond_FirstUseEver);
    ImGui::Begin("动作");
    const CharacterEntry* ch = current_character(app);
    if (!ch) {
        ImGui::End();
        return;
    }
    auto& sets = app.catalog.motion_sets[ch->row];
    if (app.catalog.motion_files.empty())
        ImGui::TextColored(ImVec4(1, 0.6f, 0.3f, 1), "没有 catalog\\motions.csv，先运行 tools\\export_motion.py");
    ImGui::Checkbox("播放动作", &app.animate);
    ImGui::SameLine();
    if (ImGui::Button("绑定姿势"))
        select_motion(app, -1);
    ImGui::BeginChild("sets", ImVec2(0, 130), ImGuiChildFlags_Borders);
    ImGuiListClipper clipper;
    clipper.Begin(int(sets.size()));
    while (clipper.Step())
        for (int i = clipper.DisplayStart; i < clipper.DisplayEnd; ++i) {
            std::string kinds;
            for (auto& b : sets[i].banks)
                kinds += b.kind + " ";
            char label[160];
            std::snprintf(label, sizeof(label), "%3d  %s  %s", sets[i].row, sets[i].id.c_str(), kinds.c_str());
            if (ImGui::Selectable(label, i == app.motion_set))
                select_motion(app, i);
        }
    ImGui::EndChild();
    int clips = int(app.character.clip_count());
    if (clips > 0) {
        if (ImGui::SliderInt("剪辑", &app.clip, 0, clips - 1))
            app.frame = 0;
        int frames = app.character.clip_frames(size_t(app.clip));
        ImGui::SliderFloat("帧", &app.frame, 0, float(std::max(frames, 1)), "%.1f");
        ImGui::Text("%d 帧, %.2f 秒 @ %.0f fps", frames, frames / app.fps, app.fps);
        if (ImGui::Button(app.playing ? "暂停 (空格)" : "播放 (空格)"))
            app.playing = !app.playing;
        ImGui::SameLine();
        ImGui::SetNextItemWidth(120);
        ImGui::SliderFloat("速度", &app.speed, 0.05f, 2.0f, "%.2f");
        ImGui::SliderFloat("fps", &app.fps, 10, 120, "%.0f");
        for (auto& b : app.character.banks())
            ImGui::TextDisabled("%s  %s", b.file->banks[b.bank].root.c_str(), b.hash.substr(0, 12).c_str());
    }
    ImGui::End();
}

void view_panel(AppState& app) {
    ImGui::SetNextWindowPos(ImVec2(350, 10), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(300, 420), ImGuiCond_FirstUseEver);
    ImGui::Begin("显示");
    ViewSettings& v = app.view;
    const char* modes[] = {"光照", "底色（槽位 0）", "法线（含法线图）", "UV0", "贴图槽位", "顶点法线"};
    ImGui::Combo("视图", &v.debug_mode, modes, IM_ARRAYSIZE(modes));
    if (v.debug_mode == 4) {
        ImGui::SliderInt("槽位", &v.debug_slot, 0, 3);
        const char* channels[] = {"RGB", "R", "G", "B", "A"};
        ImGui::Combo("通道", &v.debug_channel, channels, IM_ARRAYSIZE(channels));
    }
    ImGui::Checkbox("线框", &v.wireframe);
    ImGui::SameLine();
    ImGui::Checkbox("骨骼", &v.skeleton);
    ImGui::SameLine();
    ImGui::Checkbox("法线图", &v.normal_maps);
    ImGui::SeparatorText("灯光");
    ImGui::SliderAngle("方位", &v.light_yaw, -180, 180);
    ImGui::SliderAngle("仰角", &v.light_pitch, -89, 89);
    ImGui::SliderFloat("强度", &v.light_intensity, 0, 6);
    ImGui::ColorEdit3("光色", v.light_color);
    ImGui::SliderFloat("环境光", &v.ambient, 0, 2);
    ImGui::ColorEdit3("天空", v.sky);
    ImGui::ColorEdit3("地面", v.ground);
    ImGui::SliderFloat("曝光", &v.exposure, 0.1f, 3);
    ImGui::ColorEdit3("背景", v.background);
    ImGui::Checkbox("垂直同步", &v.vsync);
    ImGui::SameLine();
    if (ImGui::Button("重置视角 (F)"))
        frame_camera(app);
    ImGui::TextDisabled("左键旋转  右键/中键平移  滚轮缩放");
    ImGui::SeparatorText("着色器");
    ImGui::TextDisabled("%s", app.renderer->shader_dir.string().c_str());
    if (ImGui::Button("重新编译 (F5)")) {
        app.renderer->reload_shaders(app.shader_log);
    }
    if (!app.shader_log.empty())
        ImGui::TextColored(ImVec4(1, 0.5f, 0.4f, 1), "%s", app.shader_log.c_str());
    ImGui::SeparatorText("RenderDoc");
    if (app.renderdoc) {
        if (ImGui::Button("抓取一帧 (F11)"))
            app.renderdoc->TriggerCapture();
        ImGui::SameLine();
        ImGui::Text("已抓 %u 帧", app.renderdoc->GetNumCaptures());
    } else {
        ImGui::TextDisabled("未加载：用 RenderDoc 启动，或加 --renderdoc");
    }
    ImGui::End();
}

void model_panel(AppState& app) {
    ImGui::SetNextWindowPos(ImVec2(1250, 10), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(420, 900), ImGuiCond_FirstUseEver);
    ImGui::Begin("模型");
    auto& parts = app.character.parts();
    if (parts.empty()) {
        ImGui::TextDisabled("先选角色和服装");
        ImGui::End();
        return;
    }
    app.inspect_part = std::clamp(app.inspect_part, 0, int(parts.size()) - 1);
    if (ImGui::BeginTabBar("parts")) {
        for (int i = 0; i < int(parts.size()); ++i)
            if (ImGui::BeginTabItem(role_name(parts[i].role))) {
                if (app.inspect_part != i) {
                    app.inspect_material = -1;
                    app.preview_slot = -1;
                }
                app.inspect_part = i;
                ImGui::EndTabItem();
            }
        ImGui::EndTabBar();
    }
    Part& part = parts[app.inspect_part];
    GltfModel& model = *part.model;
    ImGui::TextWrapped("%s", part.glb.c_str());
    ImGui::Text("节点 %d  蒙皮 %d  图元 %d  材质 %d  贴图 %d", int(model.nodes.size()), int(model.skins.size()),
                int(model.primitives.size()), int(model.materials.size()), int(model.images.size()));

    if (ImGui::CollapsingHeader("网格", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (int m = 0; m < int(model.mesh_names.size()); ++m) {
            bool visible = false, any = false;
            for (size_t p = 0; p < model.primitives.size(); ++p)
                if (model.primitives[p].mesh == m) {
                    any = true;
                    visible |= !part.hidden[p];
                }
            if (!any)
                continue;
            ImGui::PushID(m);
            if (ImGui::Checkbox(model.mesh_names[m].c_str(), &visible))
                for (size_t p = 0; p < model.primitives.size(); ++p)
                    if (model.primitives[p].mesh == m)
                        part.hidden[p] = !visible;
            ImGui::PopID();
        }
    }

    if (ImGui::CollapsingHeader("材质", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::BeginChild("materials", ImVec2(0, 150), ImGuiChildFlags_Borders);
        for (int i = 0; i < int(model.materials.size()); ++i) {
            const ModelMaterial& mat = model.materials[i];
            std::string meshes;
            for (auto& p : model.primitives)
                if (p.material == i && meshes.find(model.mesh_names[p.mesh]) == std::string::npos)
                    meshes += model.mesh_names[p.mesh] + " ";
            char label[200];
            static const char* alpha[] = {"", " [mask]", " [blend]"};
            std::snprintf(label, sizeof(label), "%s  MtrCol %d%s  %s", mat.name.c_str(), mat.tmc_material,
                          alpha[mat.alpha_mode], meshes.c_str());
            if (ImGui::Selectable(label, i == app.inspect_material)) {
                app.inspect_material = i == app.inspect_material ? -1 : i;
                app.preview_slot = -1;
            }
        }
        ImGui::EndChild();
        ImGui::TextDisabled("选中的材质在画面里以橙色高亮");
    }

    if (app.inspect_material >= 0 && app.inspect_material < int(model.materials.size())) {
        const ModelMaterial& mat = model.materials[app.inspect_material];
        ImGui::SeparatorText("贴图");
        for (int t = 0; t < int(mat.textures.size()); ++t) {
            const TextureRef& ref = mat.textures[t];
            char label[200];
            std::string file = ref.image >= 0 ? model.images[ref.image].path.filename().string() : "(未导出)";
            bool normal = ref.image >= 0 && model.images[ref.image].normal_map;
            std::snprintf(label, sizeof(label), "槽位 %d  uv %d  TMCL #%d  %s%s", ref.slot, ref.uv, ref.tmcl_texture,
                          file.c_str(), normal ? "  [法线]" : "");
            if (ImGui::Selectable(label, app.preview_slot == t))
                app.preview_slot = t;
        }
        if (app.preview_slot >= 0 && app.preview_slot < int(mat.textures.size())) {
            const TextureRef& ref = mat.textures[app.preview_slot];
            const Texture* tex = model.texture(ref.image, *app.renderer);
            if (tex) {
                const char* channels[] = {"RGB", "R", "G", "B", "A", "RGBA"};
                for (int c = 0; c < 6; ++c) {
                    if (c)
                        ImGui::SameLine();
                    ImGui::RadioButton(channels[c], &app.preview_channel, c);
                }
                ImGui::Text("%d x %d", tex->width, tex->height);
                if (ID3D11ShaderResourceView* srv = app.renderer->preview(tex, app.preview_channel, false))
                    ImGui::Image(ImTextureID(reinterpret_cast<intptr_t>(srv)), ImVec2(380, 380));
            }
        }
        if (ImGui::TreeNode("MtrCol 原始数值")) {
            for (size_t r = 0; r < mat.mtrcol.size(); ++r) {
                std::string line;
                char num[32];
                for (float v : mat.mtrcol[r]) {
                    std::snprintf(num, sizeof(num), "%.4g ", v);
                    line += num;
                }
                ImGui::Text("%2d: %s", int(r), line.c_str());
            }
            ImGui::TreePop();
        }
        if (ImGui::TreeNode("子网格头 submesh_raw")) {
            for (auto& p : model.primitives) {
                if (p.material != app.inspect_material)
                    continue;
                std::string line;
                char num[16];
                for (size_t k = 0; k < p.submesh_raw.size(); ++k) {
                    std::snprintf(num, sizeof(num), "%x%s", p.submesh_raw[k], k % 9 == 8 ? "\n" : " ");
                    line += num;
                }
                ImGui::Text("%s #%d", model.mesh_names[p.mesh].c_str(), p.submesh);
                ImGui::TextWrapped("%s", line.c_str());
            }
            ImGui::TreePop();
        }
    }
    ImGui::End();
}

}  // namespace

void select_character(AppState& app, int index) {
    if (index < 0 || index >= int(app.catalog.characters.size()))
        return;
    app.character_index = index;
    const CharacterEntry& ch = app.catalog.characters[index];
    auto& list = app.catalog.costumes[ch.row];
    auto first = [&](const char* kind) {
        // a costume with the character's own code reads better as the default than an OWN one
        std::string own = "_" + ch.code + "_";
        for (char& c : own)
            c = char(std::toupper(static_cast<unsigned char>(c)));
        const CostumeEntry* pick = nullptr;
        for (auto& e : list)
            if (e.kind == kind && (!pick || (e.tmc_name.find(own) != std::string::npos &&
                                             pick->tmc_name.find(own) == std::string::npos)))
                pick = &e;
        return pick ? pick->glb : std::string();
    };
    app.costume_glb = first("cos");
    app.hair_glb = first("hair");
    app.status.clear();
    load_part(app, PartRole::Costume, app.costume_glb);
    load_part(app, PartRole::Hair, app.hair_glb);
    load_part(app, PartRole::Face, ch.face_glb);
    select_motion(app, -1);
    frame_camera(app);
}

void frame_camera(AppState& app) {
    // bone positions of all parts: vertex bounds of the face and hair are in their own space.
    // The bind pose has the hips at the origin; motions stand the character on y = 0.
    app.character.pose(size_t(std::max(app.clip, 0)), app.frame, app.animate && app.character.clip_count() > 0);
    float lo[3] = {1e9f, 1e9f, 1e9f}, hi[3] = {-1e9f, -1e9f, -1e9f};
    for (auto& s : app.character.skeleton())
        for (int c = 0; c < 3; ++c) {
            lo[c] = std::min({lo[c], s.from[c], s.to[c]});
            hi[c] = std::max({hi[c], s.from[c], s.to[c]});
        }
    float height = hi[1] - lo[1];
    if (height <= 0)
        return;
    hi[1] += height * 0.08f;  // top of the head is past the last head bone
    for (int c = 0; c < 3; ++c)
        app.camera.target[c] = (lo[c] + hi[c]) * 0.5f;
    app.camera.distance = (hi[1] - lo[1]) * 0.58f / std::tan(app.camera.fov * 0.5f);
    app.camera.yaw = 0;
    app.camera.pitch = 0.05f;
}

void draw_ui(AppState& app) {
    character_panel(app);
    motion_panel(app);
    view_panel(app);
    model_panel(app);
    if (!app.status.empty()) {
        ImGuiViewport* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(ImVec2(vp->Size.x * 0.5f, vp->Size.y - 10), ImGuiCond_Always, ImVec2(0.5f, 1));
        ImGui::Begin("状态", nullptr, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoTitleBar);
        ImGui::TextUnformatted(app.status.c_str());
        ImGui::SameLine();
        if (ImGui::SmallButton("x"))
            app.status.clear();
        ImGui::End();
    }
}
