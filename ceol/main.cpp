#include <iostream>
#include <string>
#include <algorithm>
#include <windows.h>
#include <filesystem>
#include "tinyxml2.h"

namespace fs = std::filesystem;

std::string toLower(const std::string& str) {
    std::string out = str;
    std::transform(out.begin(), out.end(), out.begin(), ::tolower);
    return out;
}

std::string getHotlistPath() {
    char buffer[MAX_PATH];
    DWORD length = GetModuleFileNameA(NULL, buffer, MAX_PATH);
    if (length == 0 || length == MAX_PATH) {
        return "col_paths.hotlist";
    }

    fs::path exePath(buffer);
    fs::path exeDir = exePath.parent_path();
    return (exeDir / "col_paths.hotlist").string();
}

int main(int argc, char* argv[]) {
    std::string hotlistPath = getHotlistPath();

    tinyxml2::XMLDocument doc;
    if (doc.LoadFile(hotlistPath.c_str()) != tinyxml2::XML_SUCCESS) {
        std::cerr << "Error: Could not open " << hotlistPath << "\n";
        return 1;
    }

    tinyxml2::XMLElement* root = doc.FirstChildElement("doublecmd");
    if (!root) return 1;
    tinyxml2::XMLElement* hotlist = root->FirstChildElement("DirectoryHotList");
    if (!hotlist) return 1;

    if (argc < 2) {
        for (tinyxml2::XMLElement* hotDir = hotlist->FirstChildElement("HotDir");
             hotDir != nullptr;
             hotDir = hotDir->NextSiblingElement("HotDir")) {

            const char* name = hotDir->Attribute("Name");
            const char* path = hotDir->Attribute("Path");
            if (name && path) {
                std::cout << name << "\t\t" << path << "\n";
            }
        }
        return 0;
    }

    std::string search = toLower(argv[1]);
    for (tinyxml2::XMLElement* hotDir = hotlist->FirstChildElement("HotDir");
         hotDir != nullptr;
         hotDir = hotDir->NextSiblingElement("HotDir")) {

        const char* name = hotDir->Attribute("Name");
        const char* path = hotDir->Attribute("Path");
        if (name && path) {
            std::string lname = toLower(name);
            if (lname.rfind(search, 0) == 0) { // starts with "search"
                std::cout << path;
                return 0;
            }
        }
    }

    return 0;
}
