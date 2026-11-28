#include "motion.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>

namespace {

struct Reader {
    const std::vector<uint8_t>& data;
    size_t pos = 0;
    bool ok = true;

    template <typename T>
    T get() {
        T value{};
        if (pos + sizeof(T) > data.size()) {
            ok = false;
            return value;
        }
        std::memcpy(&value, data.data() + pos, sizeof(T));
        pos += sizeof(T);
        return value;
    }
    std::string text() {
        uint16_t length = get<uint16_t>();
        if (pos + length > data.size()) {
            ok = false;
            return {};
        }
        std::string out(reinterpret_cast<const char*>(data.data() + pos), length);
        pos += length;
        return out;
    }
};

}  // namespace

void MotionClip::sample(uint32_t node, float frame, float out[9]) const {
    float last = float(samples > 0 ? samples - 1 : 0);
    frame = std::clamp(frame, 0.0f, last);
    uint32_t a = uint32_t(frame);
    uint32_t b = std::min(a + 1, samples - 1);
    float t = frame - float(a);
    for (int c = 0; c < 9; ++c) {
        size_t k = size_t(node) * 9 + c;
        const float* v = values.data() + offset[k];
        out[c] = animated[k] ? v[a] + (v[b] - v[a]) * t : v[0];
    }
}

bool MotionFile::load(const std::filesystem::path& path, std::string& error) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        error = "cannot open " + path.string();
        return false;
    }
    data_.assign(std::istreambuf_iterator<char>(in), {});
    Reader r{data_};
    char magic[4];
    for (char& c : magic)
        c = char(r.get<uint8_t>());
    uint32_t version = r.get<uint32_t>(), count = r.get<uint32_t>();
    if (std::memcmp(magic, "VMOT", 4) != 0 || version != 1) {
        error = "not a VMOT v1 file: " + path.string();
        return false;
    }
    for (uint32_t i = 0; i < count && r.ok; ++i) {
        MotionBank bank;
        bank.root = r.text();
        bank.kind = BankKind(r.get<uint8_t>());
        uint32_t nodes = r.get<uint32_t>();
        for (uint32_t n = 0; n < nodes; ++n)
            bank.names.push_back(r.text());
        for (uint32_t n = 0; n < nodes; ++n)
            bank.parents.push_back(r.get<int32_t>());
        uint32_t clips = r.get<uint32_t>();
        for (uint32_t c = 0; c < clips; ++c)
            bank.clip_offsets.push_back(r.get<uint64_t>());
        banks.push_back(std::move(bank));
    }
    if (!r.ok) {
        error = "truncated VMOT header: " + path.string();
        return false;
    }
    clips_.resize(banks.size());
    for (size_t i = 0; i < banks.size(); ++i)
        clips_[i].resize(banks[i].clip_offsets.size());
    return true;
}

const MotionClip* MotionFile::clip(size_t bank, size_t index) {
    if (bank >= banks.size() || index >= banks[bank].clip_offsets.size())
        return nullptr;
    MotionClip& clip = clips_[bank][index];
    if (clip.samples)
        return &clip;
    size_t nodes = banks[bank].names.size();
    Reader r{data_, size_t(banks[bank].clip_offsets[index])};
    clip.samples = r.get<uint32_t>();
    clip.animated.resize(nodes * 9);
    for (auto& flag : clip.animated)
        flag = r.get<uint8_t>();
    clip.offset.resize(nodes * 9);
    for (size_t k = 0; k < nodes * 9 && r.ok; ++k) {
        clip.offset[k] = uint32_t(clip.values.size());
        size_t n = clip.animated[k] ? clip.samples : 1;
        for (size_t s = 0; s < n; ++s)
            clip.values.push_back(r.get<float>());
    }
    if (!r.ok || !clip.samples) {
        clip = {};
        return nullptr;
    }
    return &clip;
}
