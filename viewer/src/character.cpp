#include "character.h"

#include <algorithm>
#include <cmath>
#include <cstring>

using namespace DirectX;

namespace {

XMMATRIX load(const XMFLOAT4X4& m) { return XMLoadFloat4x4(&m); }

XMFLOAT4X4 store(FXMMATRIX m) {
    XMFLOAT4X4 out;
    XMStoreFloat4x4(&out, m);
    return out;
}

XMVECTOR euler_xyz(float x, float y, float z) {
    // rotate about x, then y, then z (v * Rx * Ry * Rz), as the game and export_gltf.py do
    XMVECTOR qx = XMQuaternionRotationAxis(XMVectorSet(1, 0, 0, 0), x);
    XMVECTOR qy = XMQuaternionRotationAxis(XMVectorSet(0, 1, 0, 0), y);
    XMVECTOR qz = XMQuaternionRotationAxis(XMVectorSet(0, 0, 1, 0), z);
    return XMQuaternionMultiply(XMQuaternionMultiply(qx, qy), qz);
}

bool ends_with(const std::string& text, const char* suffix) {
    size_t n = std::strlen(suffix);
    return text.size() >= n && text.compare(text.size() - n, n, suffix) == 0;
}

// model leg length / motion leg length, from frame 0 (export_gltf.py leg_ratio)
float leg_ratio(const GltfModel& model, const MotionBank& bank, const MotionClip& clip) {
    float model_len = 0, motion_len = 0;
    for (size_t i = 0; i < bank.names.size(); ++i) {
        const std::string& name = bank.names[i];
        if (!ends_with(name, "_LeftUpLeg") && !ends_with(name, "_LeftLeg") && !ends_with(name, "_LeftFoot"))
            continue;
        int node = model.find_node(name);
        if (node < 0)
            continue;
        const XMFLOAT4X4& m = model.nodes[node].local;
        model_len += std::sqrt(m._41 * m._41 + m._42 * m._42 + m._43 * m._43);
        float ch[9];
        clip.sample(uint32_t(i), 0, ch);
        motion_len += std::sqrt(ch[0] * ch[0] + ch[1] * ch[1] + ch[2] * ch[2]);
    }
    return motion_len > 0 && model_len > 0 ? model_len / motion_len : 1.0f;
}

// meshes that are not plain color passes: shadow / depth proxies (zdmodel has no normals),
// and those the game switches on by state: sweat overlays, torn clothing
bool hidden_by_default(const std::string& mesh) {
    return mesh.find("SHADOW") != std::string::npos || mesh.find("zdmodel") != std::string::npos ||
           mesh.find("sweat") != std::string::npos ||
           mesh.find("_z_break") != std::string::npos || ends_with(mesh, "_brk");
}

}  // namespace

Part* Character::part(PartRole role) {
    for (auto& p : parts_)
        if (p.role == role)
            return &p;
    return nullptr;
}

bool Character::set_part(PartRole role, const std::string& glb, const std::filesystem::path& out_dir,
                         Renderer& renderer, std::string& error) {
    parts_.erase(std::remove_if(parts_.begin(), parts_.end(), [&](const Part& p) { return p.role == role; }),
                 parts_.end());
    if (glb.empty())
        return true;
    auto path = out_dir / std::filesystem::path(reinterpret_cast<const char8_t*>(glb.c_str()));
    std::shared_ptr<GltfModel> model = model_cache_[path].lock();
    if (!model) {
        model = std::make_shared<GltfModel>();
        if (!model->load(path, renderer, error))
            return false;
        model_cache_[path] = model;
    }
    Part part;
    part.role = role;
    part.glb = glb;
    part.model = model;
    part.hidden.assign(model->primitives.size(), 0);
    for (size_t i = 0; i < model->primitives.size(); ++i)
        part.hidden[i] = hidden_by_default(model->mesh_names[model->primitives[i].mesh]);
    parts_.push_back(std::move(part));
    std::stable_sort(parts_.begin(), parts_.end(), [](const Part& a, const Part& b) { return a.role < b.role; });
    return true;
}

bool Character::set_motion(const std::vector<std::pair<std::string, std::string>>& banks,
                           const std::map<std::string, std::string>& motion_files,
                           const std::filesystem::path& out_dir, std::string& error) {
    banks_.clear();
    for (auto& [hash, kind] : banks) {
        auto it = motion_files.find(hash);
        if (it == motion_files.end()) {
            // "?" banks are not motion data survey_motion.py could parse; export_motion.py skips them too
            if (kind != "?")
                error = "motion " + hash.substr(0, 12) + " is not exported (run tools\\export_motion.py)";
            continue;
        }
        std::shared_ptr<MotionFile> file = motion_cache_[hash].lock();
        if (!file) {
            file = std::make_shared<MotionFile>();
            if (!file->load(out_dir / it->second, error))
                continue;
            motion_cache_[hash] = file;
        }
        for (size_t b = 0; b < file->banks.size(); ++b) {
            BankKind k = file->banks[b].kind;
            if (k == BankKind::Body || k == BankKind::Hand || k == BankKind::Face || k == BankKind::Breast)
                banks_.push_back({hash, file, b, k});
        }
    }
    return !banks_.empty();
}

size_t Character::clip_count() const {
    size_t n = 0;
    for (auto& b : banks_)
        n = std::max(n, b.file->banks[b.bank].clip_offsets.size());
    return n;
}

int Character::clip_frames(size_t clip) const {
    int frames = 0;
    for (auto& b : banks_)
        if (const MotionClip* c = b.file->clip(b.bank, clip))
            frames = std::max(frames, int(c->samples) - 1);
    return frames;
}

void Character::apply_bank(Part& part, const LoadedBank& loaded, size_t clip_index, float frame) {
    const MotionBank& bank = loaded.file->banks[loaded.bank];
    const MotionClip* clip = loaded.file->clip(loaded.bank, clip_index);
    if (!clip)
        return;
    const GltfModel& model = *part.model;
    float ratio = loaded.kind == BankKind::Body ? leg_ratio(model, bank, *clip) : 1.0f;
    for (size_t i = 0; i < bank.names.size(); ++i) {
        int node = bank.names[i].empty() ? -1 : model.find_node(bank.names[i]);
        if (node < 0)
            continue;
        float ch[9];
        clip->sample(uint32_t(i), frame, ch);
        const XMFLOAT4X4& bind = model.nodes[node].local;
        XMVECTOR t;
        if (model.nodes[node].parent < 0)
            t = XMVectorSet(ch[0] * ratio, ch[1] * ratio, ch[2] * ratio, 1);
        else if (loaded.kind == BankKind::Face)
            t = XMVectorSet(ch[0], ch[1], ch[2], 1);  // expressions move face bones by translation
        else
            t = XMVectorSet(bind._41, bind._42, bind._43, 1);  // keep the model's own bone lengths
        XMMATRIX m = XMMatrixScaling(ch[6], ch[7], ch[8]) * XMMatrixRotationQuaternion(euler_xyz(ch[3], ch[4], ch[5])) *
                     XMMatrixTranslationFromVector(t);
        part.local[node] = store(m);
    }
}

void Character::forward(Part& part, const std::vector<int>& root_override, const Part* source) {
    const auto& nodes = part.model->nodes;
    part.world.resize(nodes.size());
    std::vector<int> stack;
    for (size_t i = 0; i < nodes.size(); ++i)
        if (nodes[i].parent < 0)
            stack.push_back(int(i));
    while (!stack.empty()) {
        int i = stack.back();
        stack.pop_back();
        const ModelNode& n = nodes[i];
        if (n.parent < 0)
            part.world[i] = source && root_override[i] >= 0 ? source->world[root_override[i]] : part.local[i];
        else
            part.world[i] = store(load(part.local[i]) * load(part.world[n.parent]));
        for (int c : n.children)
            stack.push_back(c);
    }
}

void Character::pose(size_t clip, float frame, bool animate) {
    Part* costume = part(PartRole::Costume);
    for (auto& p : parts_) {
        p.local.resize(p.model->nodes.size());
        for (size_t i = 0; i < p.model->nodes.size(); ++i)
            p.local[i] = p.model->nodes[i].local;
    }
    if (costume) {
        if (animate)
            for (auto& b : banks_)
                if (b.kind != BankKind::Face)
                    apply_bank(*costume, b, clip, frame);
        forward(*costume, {}, nullptr);
    }
    for (auto& p : parts_) {
        if (&p == costume)
            continue;
        // hair is rooted at MOT01_Head and faces at MOT15_Neck: roots take the costume's world
        // transform of the same bone, other body bones copy its local rotation
        std::vector<int> override_of(p.model->nodes.size(), -1);
        if (costume) {
            for (size_t i = 0; i < p.model->nodes.size(); ++i) {
                int src = costume->model->find_node(p.model->nodes[i].name);
                if (src < 0)
                    continue;
                if (p.model->nodes[i].parent < 0) {
                    override_of[i] = src;
                } else {
                    XMVECTOR s, r, t, s2, r2, t2;
                    XMMatrixDecompose(&s, &r, &t, load(p.local[i]));
                    XMMatrixDecompose(&s2, &r2, &t2, load(costume->local[src]));
                    p.local[i] = store(XMMatrixScalingFromVector(s) * XMMatrixRotationQuaternion(r2) *
                                       XMMatrixTranslationFromVector(t));
                }
            }
        }
        if (animate)
            for (auto& b : banks_)
                if (b.kind == BankKind::Face)
                    apply_bank(p, b, clip, frame);
        forward(p, override_of, costume);
    }
}

void Character::gather(Renderer& renderer, const XMMATRIX& view, std::vector<XMFLOAT4X4>& joints,
                       std::vector<DrawItem>& items, int debug_slot, const ModelMaterial* highlight) {
    for (auto& p : parts_) {
        GltfModel& model = *p.model;
        std::vector<int> skin_offset(model.skins.size(), -1);
        for (size_t pi = 0; pi < model.primitives.size(); ++pi) {
            if (p.hidden[pi])
                continue;
            const ModelPrimitive& prim = model.primitives[pi];
            uint32_t offset;
            if (prim.skin >= 0) {
                if (skin_offset[prim.skin] < 0) {
                    skin_offset[prim.skin] = int(joints.size());
                    const ModelSkin& skin = model.skins[prim.skin];
                    for (size_t j = 0; j < skin.joints.size(); ++j)
                        joints.push_back(store(load(skin.inverse_bind[j]) * load(p.world[skin.joints[j]])));
                }
                offset = uint32_t(skin_offset[prim.skin]);
            } else {
                offset = uint32_t(joints.size());
                joints.push_back(p.world[prim.node]);
            }
            DrawItem item;
            item.vertices = prim.vertices.Get();
            item.indices = prim.indices.Get();
            item.index_format = prim.index_format;
            item.index_count = prim.index_count;
            item.constants.joint_offset = offset;
            const ModelMaterial* mat = prim.material >= 0 ? &model.materials[prim.material] : nullptr;
            if (mat) {
                item.constants.alpha_mode = uint32_t(mat->alpha_mode);
                item.constants.alpha_cutoff = mat->alpha_cutoff;
                if (const TextureRef* t = mat->slot(0)) {
                    item.color = model.texture(t->image, renderer);
                    item.constants.color_uv = uint32_t(t->uv);
                }
                if (const TextureRef* t = mat->slot(2)) {
                    item.normal = model.texture(t->image, renderer);
                    item.constants.normal_uv = uint32_t(t->uv);
                }
                if (const TextureRef* t = mat->slot(debug_slot)) {
                    item.slot = model.texture(t->image, renderer);
                    item.constants.slot_uv = uint32_t(t->uv);
                }
                if (mat == highlight)
                    item.constants.flags |= Highlight;
            }
            if (item.color)
                item.constants.flags |= HasColor;
            if (item.normal)
                item.constants.flags |= HasNormal;
            if (item.slot)
                item.constants.flags |= HasSlot;
            XMVECTOR c = XMVector3Transform(XMVectorSet(prim.center[0], prim.center[1], prim.center[2], 1),
                                            load(joints[offset]));
            item.depth = -XMVectorGetZ(XMVector3Transform(c, view));
            items.push_back(item);
        }
    }
}

std::vector<BoneSegment> Character::skeleton() const {
    std::vector<BoneSegment> out;
    for (auto& p : parts_) {
        if (p.role != PartRole::Costume)
            continue;
        for (size_t i = 0; i < p.model->nodes.size(); ++i) {
            int parent = p.model->nodes[i].parent;
            if (parent < 0 || p.model->nodes[i].name.rfind("mesh_", 0) == 0)
                continue;
            const XMFLOAT4X4 &a = p.world[parent], &b = p.world[i];
            out.push_back({{a._41, a._42, a._43}, {b._41, b._42, b._43}});
        }
    }
    return out;
}
