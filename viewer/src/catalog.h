// Reads the relation tables under out\catalog\ (see 阶段总结.md 4.2).
#pragma once

#include <filesystem>
#include <map>
#include <string>
#include <vector>

struct CsvTable {
    std::vector<std::string> header;
    std::vector<std::vector<std::string>> rows;
    int column(const std::string& name) const;
};

bool read_csv(const std::filesystem::path& path, CsvTable& table, std::string& error);

struct CharacterEntry {
    int row = 0;
    std::string code;
    std::string face_glb;
    std::string effect_glb;
};

struct CostumeEntry {
    std::string kind;  // "cos" or "hair"
    int number = 0;
    std::string tmc_name;
    std::string glb;  // relative to out\, empty if not exported
};

struct MotionBankRef {
    std::string hash;
    std::string kind;  // body, face, hand, breast, ? (from motion_sets.csv)
};

struct MotionSet {
    int row = 0;
    std::string id;
    std::vector<MotionBankRef> banks;
};

class Catalog {
public:
    bool load(const std::filesystem::path& out_dir, std::string& error);

    std::filesystem::path out_dir;
    std::vector<CharacterEntry> characters;
    std::map<int, std::vector<CostumeEntry>> costumes;  // by character row
    std::map<int, std::vector<MotionSet>> motion_sets;  // by character row
    std::map<std::string, std::string> motion_files;    // char_dat hash -> path relative to the out folder

    std::filesystem::path resolve(const std::string& relative) const { return out_dir / relative; }
};
