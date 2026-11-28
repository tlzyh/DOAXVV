#include "gltf_model.h"

#include "json.h"

#include <cgltf.h>
#include <stb_image.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstring>

namespace {

XMFLOAT4X4 from_gltf(const float m[16]) {
    // glTF stores column-major column-vector matrices; the same 16 floats read row by row
    // are the row-vector matrix used everywhere in the viewer.
    XMFLOAT4X4 out;
    std::memcpy(&out, m, sizeof(out));
    return out;
}

template <typename T>
int index_of(const T* item, const T* first) {
    return item ? int(item - first) : -1;
}

// area-weighted vertex normals, for primitives exported without NORMAL
void compute_normals(std::vector<Vertex>& vertices, const std::vector<uint32_t>& indices) {
    using namespace DirectX;
    std::vector<XMFLOAT3> sum(vertices.size(), XMFLOAT3(0, 0, 0));
    for (size_t i = 0; i + 2 < indices.size(); i += 3) {
        uint32_t a = indices[i], b = indices[i + 1], c = indices[i + 2];
        if (a >= vertices.size() || b >= vertices.size() || c >= vertices.size())
            continue;
        XMVECTOR pa = XMLoadFloat3(reinterpret_cast<const XMFLOAT3*>(vertices[a].position));
        XMVECTOR pb = XMLoadFloat3(reinterpret_cast<const XMFLOAT3*>(vertices[b].position));
        XMVECTOR pc = XMLoadFloat3(reinterpret_cast<const XMFLOAT3*>(vertices[c].position));
        XMVECTOR n = XMVector3Cross(XMVectorSubtract(pb, pa), XMVectorSubtract(pc, pa));
        for (uint32_t k : {a, b, c})
            XMStoreFloat3(&sum[k], XMVectorAdd(XMLoadFloat3(&sum[k]), n));
    }
    for (size_t k = 0; k < vertices.size(); ++k) {
        XMVECTOR n = XMLoadFloat3(&sum[k]);
        n = XMVectorGetX(XMVector3LengthSq(n)) > 0 ? XMVector3Normalize(n) : XMVectorSet(0, 1, 0, 0);
        XMStoreFloat3(reinterpret_cast<XMFLOAT3*>(vertices[k].normal), n);
    }
}

}  // namespace

const TextureRef* ModelMaterial::slot(int number) const {
    for (auto& t : textures)
        if (t.slot == number && t.image >= 0)
            return &t;
    return nullptr;
}

int GltfModel::find_node(const std::string& name) const {
    auto it = node_by_name_.find(name);
    return it == node_by_name_.end() ? -1 : it->second;
}

bool GltfModel::load(const std::filesystem::path& file, Renderer& renderer, std::string& error) {
    path = file;
    cgltf_options options{};
    cgltf_data* data = nullptr;
    std::string utf8 = file.string();
    if (cgltf_parse_file(&options, utf8.c_str(), &data) != cgltf_result_success) {
        error = "cannot parse " + utf8;
        return false;
    }
    std::unique_ptr<cgltf_data, decltype(&cgltf_free)> guard(data, cgltf_free);
    if (cgltf_load_buffers(&options, data, utf8.c_str()) != cgltf_result_success) {
        error = "cannot load buffers of " + utf8;
        return false;
    }

    nodes.resize(data->nodes_count);
    for (size_t i = 0; i < data->nodes_count; ++i) {
        const cgltf_node& n = data->nodes[i];
        ModelNode& node = nodes[i];
        node.name = n.name ? n.name : "";
        node.parent = index_of(n.parent, data->nodes);
        for (size_t c = 0; c < n.children_count; ++c)
            node.children.push_back(index_of(n.children[c], data->nodes));
        float m[16];
        cgltf_node_transform_local(&n, m);
        node.local = from_gltf(m);
        if (!node.name.empty())
            node_by_name_.emplace(node.name, int(i));
    }

    for (size_t i = 0; i < data->skins_count; ++i) {
        const cgltf_skin& s = data->skins[i];
        ModelSkin skin;
        for (size_t j = 0; j < s.joints_count; ++j) {
            skin.joints.push_back(index_of(s.joints[j], data->nodes));
            float m[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
            if (s.inverse_bind_matrices)
                cgltf_accessor_read_float(s.inverse_bind_matrices, j, m, 16);
            skin.inverse_bind.push_back(from_gltf(m));
        }
        skins.push_back(std::move(skin));
    }

    auto base = file.parent_path();
    for (size_t i = 0; i < data->images_count; ++i) {
        const cgltf_image& img = data->images[i];
        ModelImage image;
        if (img.uri)
            image.path = base / std::filesystem::path(reinterpret_cast<const char8_t*>(img.uri));
        image.tmcl_texture = Json::parse(img.extras.data)["tmcl_texture"].as_int(-1);
        images.push_back(std::move(image));
    }
    std::map<int, int> image_of_tmcl;
    for (size_t i = 0; i < images.size(); ++i)
        if (images[i].tmcl_texture >= 0)
            image_of_tmcl[images[i].tmcl_texture] = int(i);

    for (size_t i = 0; i < data->materials_count; ++i) {
        const cgltf_material& m = data->materials[i];
        ModelMaterial material;
        material.name = m.name ? m.name : "";
        material.alpha_mode = m.alpha_mode == cgltf_alpha_mode_mask ? 1 : m.alpha_mode == cgltf_alpha_mode_blend ? 2 : 0;
        material.alpha_cutoff = m.alpha_cutoff;
        Json extras = Json::parse(m.extras.data);
        material.tmc_material = extras["tmc_material"].as_int(-1);
        for (auto& t : extras["textures"].items) {
            TextureRef ref{t["slot"].as_int(), t["uv"].as_int(), t["texture"].as_int()};
            auto it = image_of_tmcl.find(ref.tmcl_texture);
            ref.image = it == image_of_tmcl.end() ? -1 : it->second;
            material.textures.push_back(ref);
        }
        for (auto& row : extras["mtrcol"].items) {
            std::vector<float> values;
            for (auto& v : row.items)
                values.push_back(v.as_float());
            material.mtrcol.push_back(std::move(values));
        }
        materials.push_back(std::move(material));
    }

    for (size_t i = 0; i < data->meshes_count; ++i)
        mesh_names.push_back(data->meshes[i].name ? data->meshes[i].name : "");

    std::fill(bounds_min, bounds_min + 3, FLT_MAX);
    std::fill(bounds_max, bounds_max + 3, -FLT_MAX);
    for (size_t ni = 0; ni < data->nodes_count; ++ni) {
        const cgltf_node& n = data->nodes[ni];
        if (!n.mesh)
            continue;
        int mesh = index_of(n.mesh, data->meshes);
        for (size_t pi = 0; pi < n.mesh->primitives_count; ++pi) {
            const cgltf_primitive& p = n.mesh->primitives[pi];
            const cgltf_accessor* pos = cgltf_find_accessor(&p, cgltf_attribute_type_position, 0);
            if (!pos || !p.indices || p.type != cgltf_primitive_type_triangles)
                continue;
            std::vector<Vertex> vertices(pos->count);
            for (auto& v : vertices) {
                std::memset(&v, 0, sizeof(v));
                v.tangent[0] = 1;
                v.tangent[3] = 1;
                v.weights[0] = 1;
            }
            int joint_sets = 0;
            for (size_t a = 0; a < p.attributes_count; ++a) {
                const cgltf_attribute& attr = p.attributes[a];
                const cgltf_accessor* acc = attr.data;
                for (size_t k = 0; k < acc->count && k < vertices.size(); ++k) {
                    Vertex& v = vertices[k];
                    switch (attr.type) {
                        case cgltf_attribute_type_position: cgltf_accessor_read_float(acc, k, v.position, 3); break;
                        case cgltf_attribute_type_normal: cgltf_accessor_read_float(acc, k, v.normal, 3); break;
                        case cgltf_attribute_type_tangent: cgltf_accessor_read_float(acc, k, v.tangent, 4); break;
                        case cgltf_attribute_type_texcoord:
                            if (attr.index == 0)
                                cgltf_accessor_read_float(acc, k, v.uv0, 2);
                            else if (attr.index == 1)
                                cgltf_accessor_read_float(acc, k, v.uv1, 2);
                            else if (attr.index == 2)
                                cgltf_accessor_read_float(acc, k, v.uv2, 2);
                            break;
                        case cgltf_attribute_type_joints:
                            if (attr.index < 3) {
                                cgltf_uint j[4] = {};
                                cgltf_accessor_read_uint(acc, k, j, 4);
                                for (int c = 0; c < 4; ++c)
                                    v.joints[attr.index * 4 + c] = uint8_t(j[c]);
                            }
                            break;
                        case cgltf_attribute_type_weights:
                            if (attr.index < 3)
                                cgltf_accessor_read_float(acc, k, v.weights + attr.index * 4, 4);
                            break;
                        default: break;
                    }
                }
                if (attr.type == cgltf_attribute_type_joints)
                    joint_sets = std::max(joint_sets, int(attr.index) + 1);
            }
            ModelPrimitive prim;
            prim.mesh = mesh;
            prim.material = index_of(p.material, data->materials);
            prim.skin = n.skin && joint_sets ? index_of(n.skin, data->skins) : -1;
            prim.node = int(ni);
            Json extras = Json::parse(p.extras.data);
            prim.submesh = extras["submesh"].as_int(-1);
            for (auto& v : extras["submesh_raw"].items)
                prim.submesh_raw.push_back(uint32_t(v.number));
            if (prim.skin < 0)
                for (auto& v : vertices) {
                    std::memset(v.joints, 0, sizeof(v.joints));
                    std::memset(v.weights, 0, sizeof(v.weights));
                    v.weights[0] = 1;
                }

            std::vector<uint32_t> indices(p.indices->count);
            cgltf_accessor_unpack_indices(p.indices, indices.data(), sizeof(uint32_t), indices.size());
            if (!cgltf_find_accessor(&p, cgltf_attribute_type_normal, 0))
                compute_normals(vertices, indices);
            float lo[3] = {FLT_MAX, FLT_MAX, FLT_MAX}, hi[3] = {-FLT_MAX, -FLT_MAX, -FLT_MAX};
            for (auto& v : vertices)
                for (int c = 0; c < 3; ++c) {
                    lo[c] = std::min(lo[c], v.position[c]);
                    hi[c] = std::max(hi[c], v.position[c]);
                }
            for (int c = 0; c < 3; ++c) {
                prim.center[c] = (lo[c] + hi[c]) * 0.5f;
                bounds_min[c] = std::min(bounds_min[c], lo[c]);
                bounds_max[c] = std::max(bounds_max[c], hi[c]);
            }
            prim.vertex_count = uint32_t(vertices.size());
            prim.index_count = uint32_t(indices.size());
            prim.vertices = renderer.create_buffer(vertices.data(), vertices.size() * sizeof(Vertex),
                                                   D3D11_BIND_VERTEX_BUFFER);
            if (vertices.size() <= 0xFFFF) {
                std::vector<uint16_t> narrow(indices.size());
                for (size_t k = 0; k < indices.size(); ++k)
                    narrow[k] = uint16_t(indices[k]);
                prim.indices = renderer.create_buffer(narrow.data(), narrow.size() * 2, D3D11_BIND_INDEX_BUFFER);
                prim.index_format = DXGI_FORMAT_R16_UINT;
            } else {
                prim.indices = renderer.create_buffer(indices.data(), indices.size() * 4, D3D11_BIND_INDEX_BUFFER);
            }
            primitives.push_back(std::move(prim));
        }
    }
    return true;
}

const Texture* GltfModel::texture(int image, Renderer& renderer) {
    if (image < 0 || image >= int(images.size()))
        return nullptr;
    ModelImage& img = images[image];
    if (img.texture || img.failed)
        return img.texture.get();
    int w = 0, h = 0, n = 0;
    std::u8string utf8 = img.path.u8string();
    unsigned char* pixels = stbi_load(reinterpret_cast<const char*>(utf8.c_str()), &w, &h, &n, 4);
    if (!pixels) {
        img.failed = true;
        return nullptr;
    }
    // TMC slots differ per shader, so tangent-space normal maps are told apart by their content
    double sum[3] = {};
    size_t count = size_t(w) * size_t(h), step = std::max<size_t>(1, count / 4096), samples = 0;
    for (size_t k = 0; k < count; k += step, ++samples)
        for (int c = 0; c < 3; ++c)
            sum[c] += pixels[k * 4 + c] / 255.0;
    double r = sum[0] / samples, g = sum[1] / samples, b = sum[2] / samples;
    img.normal_map = b > 0.75 && std::abs(r - 0.5) < 0.12 && std::abs(g - 0.5) < 0.12;
    img.texture = renderer.create_texture(pixels, w, h);
    stbi_image_free(pixels);
    img.failed = !img.texture;
    return img.texture.get();
}
