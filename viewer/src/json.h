// Minimal JSON reader for glTF "extras" (objects, arrays, numbers, strings, literals).
#pragma once

#include <cstdlib>
#include <map>
#include <memory>
#include <string>
#include <vector>

struct Json {
    enum Type { Null, Bool, Number, String, Array, Object } type = Null;
    double number = 0;
    std::string text;
    std::vector<Json> items;
    std::map<std::string, Json> fields;

    const Json& operator[](const std::string& key) const {
        static const Json none;
        auto it = fields.find(key);
        return it == fields.end() ? none : it->second;
    }
    const Json& operator[](size_t i) const {
        static const Json none;
        return i < items.size() ? items[i] : none;
    }
    int as_int(int fallback = 0) const { return type == Number ? int(number) : fallback; }
    float as_float(float fallback = 0) const { return type == Number ? float(number) : fallback; }

    static Json parse(const char* text) {
        if (!text)
            return {};
        const char* p = text;
        return parse_value(p);
    }

private:
    static void skip(const char*& p) {
        while (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t')
            ++p;
    }
    static std::string parse_string(const char*& p) {
        std::string out;
        ++p;
        while (*p && *p != '"') {
            if (*p == '\\' && p[1]) {
                ++p;
                switch (*p) {
                    case 'n': out += '\n'; break;
                    case 't': out += '\t'; break;
                    case 'u': out += '?'; p += 4; break;
                    default: out += *p;
                }
            } else {
                out += *p;
            }
            ++p;
        }
        if (*p == '"')
            ++p;
        return out;
    }
    static Json parse_value(const char*& p) {
        Json v;
        skip(p);
        if (*p == '{') {
            v.type = Object;
            ++p;
            for (skip(p); *p && *p != '}'; skip(p)) {
                if (*p != '"')
                    break;
                std::string key = parse_string(p);
                skip(p);
                if (*p == ':')
                    ++p;
                v.fields[key] = parse_value(p);
                skip(p);
                if (*p == ',')
                    ++p;
            }
            if (*p == '}')
                ++p;
        } else if (*p == '[') {
            v.type = Array;
            ++p;
            for (skip(p); *p && *p != ']'; skip(p)) {
                v.items.push_back(parse_value(p));
                skip(p);
                if (*p == ',')
                    ++p;
            }
            if (*p == ']')
                ++p;
        } else if (*p == '"') {
            v.type = String;
            v.text = parse_string(p);
        } else if (*p == 't' || *p == 'f') {
            v.type = Bool;
            v.number = *p == 't';
            p += *p == 't' ? 4 : 5;
        } else if (*p == 'n') {
            p += 4;
        } else if (*p) {
            char* end = nullptr;
            v.type = Number;
            v.number = std::strtod(p, &end);
            p = end > p ? end : p + 1;
        }
        return v;
    }
};
