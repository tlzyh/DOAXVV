// Reads out\motions\<hash>.vmot written by tools\export_motion.py.
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

enum class BankKind : uint8_t { Other = 0, Body = 1, Hand = 2, Face = 3, Breast = 4, Root = 5 };

struct MotionClip {
    uint32_t samples = 0;  // frames + 1
    // per node and channel: offset into values and whether it varies per sample
    std::vector<uint32_t> offset;
    std::vector<uint8_t> animated;
    std::vector<float> values;

    // 9 channels of a node at a fractional frame (clamped): translate xyz, rotate xyz, scale xyz
    void sample(uint32_t node, float frame, float out[9]) const;
};

struct MotionBank {
    std::string root;
    BankKind kind = BankKind::Other;
    std::vector<std::string> names;
    std::vector<int32_t> parents;
    std::vector<uint64_t> clip_offsets;
};

class MotionFile {
public:
    bool load(const std::filesystem::path& path, std::string& error);
    // decoded on first use; the bank's clip list keeps file offsets only
    const MotionClip* clip(size_t bank, size_t index);

    std::vector<MotionBank> banks;

private:
    std::vector<uint8_t> data_;
    std::vector<std::vector<MotionClip>> clips_;
};
