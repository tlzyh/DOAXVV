#include "catalog.h"

#include <algorithm>
#include <fstream>
#include <set>
#include <sstream>

int CsvTable::column(const std::string& name) const {
    auto it = std::find(header.begin(), header.end(), name);
    return it == header.end() ? -1 : int(it - header.begin());
}

static std::vector<std::string> split_line(const std::string& line) {
    std::vector<std::string> out;
    std::string field;
    bool quoted = false;
    for (size_t i = 0; i < line.size(); ++i) {
        char c = line[i];
        if (quoted) {
            if (c == '"' && i + 1 < line.size() && line[i + 1] == '"') {
                field += '"';
                ++i;
            } else if (c == '"') {
                quoted = false;
            } else {
                field += c;
            }
        } else if (c == '"') {
            quoted = true;
        } else if (c == ',') {
            out.push_back(field);
            field.clear();
        } else if (c != '\r') {
            field += c;
        }
    }
    out.push_back(field);
    return out;
}

bool read_csv(const std::filesystem::path& path, CsvTable& table, std::string& error) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        error = "cannot open " + path.string();
        return false;
    }
    std::string line;
    bool first = true;
    while (std::getline(in, line)) {
        if (first && line.size() >= 3 && line.compare(0, 3, "\xEF\xBB\xBF") == 0)
            line.erase(0, 3);
        auto fields = split_line(line);
        if (first) {
            table.header = fields;
            first = false;
        } else if (!line.empty()) {
            fields.resize(table.header.size());
            table.rows.push_back(std::move(fields));
        }
    }
    return true;
}

static int to_int(const std::string& text) {
    try {
        return std::stoi(text);
    } catch (...) {
        return 0;
    }
}

bool Catalog::load(const std::filesystem::path& dir, std::string& error) {
    out_dir = dir;
    auto catalog = dir / "catalog";
    CsvTable chars, cos, sets, mots;
    if (!read_csv(catalog / "characters.csv", chars, error) || !read_csv(catalog / "char_costumes.csv", cos, error) ||
        !read_csv(catalog / "motion_sets.csv", sets, error))
        return false;
    if (!read_csv(catalog / "motions.csv", mots, error))
        mots = {};  // optional: run tools\export_motion.py

    int c_row = chars.column("row"), c_code = chars.column("code"), c_face = chars.column("face_glb"),
        c_effect = chars.column("effect_glb");
    for (auto& r : chars.rows) {
        if (r[c_face].empty())
            continue;  // the default chrall row has no face
        characters.push_back({to_int(r[c_row]), r[c_code], r[c_face], c_effect >= 0 ? r[c_effect] : ""});
    }

    int k_char = cos.column("char"), k_kind = cos.column("kind"), k_number = cos.column("number"),
        k_name = cos.column("tmc_name"), k_glb = cos.column("glb");
    std::map<int, std::set<std::string>> seen;
    for (auto& r : cos.rows) {
        int ch = to_int(r[k_char]);
        if (r[k_glb].empty() || !seen[ch].insert(r[k_kind] + r[k_glb]).second)
            continue;  // one entry per model; several cos rows can point at the same costume
        costumes[ch].push_back({r[k_kind], to_int(r[k_number]), r[k_name], r[k_glb]});
    }
    for (auto& [ch, list] : costumes)
        std::stable_sort(list.begin(), list.end(),
                         [](const CostumeEntry& a, const CostumeEntry& b) { return a.tmc_name < b.tmc_name; });

    int m_hash = mots.column("hash"), m_file = mots.column("file");
    for (auto& r : mots.rows)
        motion_files[r[m_hash]] = r[m_file];

    int s_char = sets.column("char"), s_row = sets.column("row"), s_id = sets.column("id"),
        s_banks = sets.column("banks"), s_kinds = sets.column("kinds");
    for (auto& r : sets.rows) {
        MotionSet set;
        set.row = to_int(r[s_row]);
        set.id = r[s_id];
        std::istringstream hashes(r[s_banks]), kinds(r[s_kinds]);
        std::string hash, kind;
        while (hashes >> hash) {
            if (!(kinds >> kind))
                kind = "?";
            set.banks.push_back({hash, kind});
        }
        motion_sets[to_int(r[s_char])].push_back(std::move(set));
    }
    return true;
}
