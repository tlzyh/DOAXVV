// One exported model: out\models\<category>\<group>\<name>.glb plus <name>_tex\NN.png.
#pragma once

#include "renderer.h"

#include <filesystem>
#include <map>
#include <memory>
#include <string>
#include <vector>

struct ModelNode {
    std::string name;
    int parent = -1;
    std::vector<int> children;
    XMFLOAT4X4 local;  // bind pose, row-vector convention (translation in row 3)
};

struct ModelSkin {
    std::vector<int> joints;
    std::vector<XMFLOAT4X4> inverse_bind;
};

struct TextureRef {
    int slot = 0, uv = 0, tmcl_texture = 0;
    int image = -1;  // index into GltfModel::images, -1 if the texture was not exported
};

struct ModelMaterial {
    std::string name;
    int tmc_material = -1;
    int alpha_mode = 0;  // 0 opaque, 1 mask, 2 blend
    float alpha_cutoff = 0.5f;
    std::vector<TextureRef> textures;
    std::vector<std::vector<float>> mtrcol;  // raw MtrCol rows

    const TextureRef* slot(int number) const;
};

struct ModelImage {
    std::filesystem::path path;
    int tmcl_texture = -1;
    std::shared_ptr<Texture> texture;  // loaded on first use
    bool failed = false;
    bool normal_map = false;  // set on load from the average color
};

struct ModelPrimitive {
    int mesh = 0;
    int material = -1;
    int skin = -1;  // -1: drawn with the world matrix of `node`
    int node = -1;
    int submesh = -1;
    std::vector<uint32_t> submesh_raw;
    ComPtr<ID3D11Buffer> vertices, indices;
    DXGI_FORMAT index_format = DXGI_FORMAT_R32_UINT;
    uint32_t index_count = 0, vertex_count = 0;
    float center[3] = {};
};

class GltfModel {
public:
    bool load(const std::filesystem::path& path, Renderer& renderer, std::string& error);
    const Texture* texture(int image, Renderer& renderer);
    int find_node(const std::string& name) const;

    std::filesystem::path path;
    std::vector<ModelNode> nodes;
    std::vector<ModelSkin> skins;
    std::vector<ModelMaterial> materials;
    std::vector<ModelImage> images;
    std::vector<std::string> mesh_names;
    std::vector<ModelPrimitive> primitives;
    float bounds_min[3] = {}, bounds_max[3] = {};

private:
    std::map<std::string, int> node_by_name_;
};
