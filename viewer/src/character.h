// A character = costume (body + swimsuit, owns the skeleton) + hair + face (+ extras),
// posed by the banks of one official motion set (阶段总结.md 4.1, 10.4, 10.6).
#pragma once

#include "gltf_model.h"
#include "motion.h"

#include <filesystem>
#include <map>
#include <memory>
#include <string>
#include <vector>

enum class PartRole { Costume, Hair, Face, Extra };

struct Part {
    PartRole role = PartRole::Extra;
    std::string glb;  // relative to the out folder
    std::shared_ptr<GltfModel> model;
    std::vector<XMFLOAT4X4> local, world;
    std::vector<char> hidden;  // per primitive
};

struct LoadedBank {
    std::string hash;
    std::shared_ptr<MotionFile> file;
    size_t bank = 0;
    BankKind kind = BankKind::Other;
};

struct BoneSegment {
    float from[3], to[3];
};

class Character {
public:
    // empty glb removes the part
    bool set_part(PartRole role, const std::string& glb, const std::filesystem::path& out_dir, Renderer& renderer,
                  std::string& error);
    Part* part(PartRole role);
    std::vector<Part>& parts() { return parts_; }
    const std::vector<Part>& parts() const { return parts_; }

    // hashes + kinds of one motion_sets.csv row; banks whose kind the viewer cannot place are skipped
    bool set_motion(const std::vector<std::pair<std::string, std::string>>& banks,
                    const std::map<std::string, std::string>& motion_files, const std::filesystem::path& out_dir,
                    std::string& error);
    void clear_motion() { banks_.clear(); }
    const std::vector<LoadedBank>& banks() const { return banks_; }
    size_t clip_count() const;
    int clip_frames(size_t clip) const;  // longest bank of that clip

    void pose(size_t clip, float frame, bool animate);
    // fills joint matrices and draw items for the current pose
    void gather(Renderer& renderer, const DirectX::XMMATRIX& view, std::vector<XMFLOAT4X4>& joints,
                std::vector<DrawItem>& items, int debug_slot, const ModelMaterial* highlight);
    std::vector<BoneSegment> skeleton() const;

private:
    void apply_bank(Part& part, const LoadedBank& bank, size_t clip, float frame);
    void forward(Part& part, const std::vector<int>& root_override, const Part* source);

    std::vector<Part> parts_;
    std::vector<LoadedBank> banks_;
    std::map<std::filesystem::path, std::weak_ptr<GltfModel>> model_cache_;
    std::map<std::string, std::weak_ptr<MotionFile>> motion_cache_;
};
