#!/usr/bin/env python3
"""Source-level Aoko Chest ESP upgrade for Minecraft 1.21.x. Patches only modern bridge source."""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
path = root / "McInjector/src/main/cpp/bridge_261.cpp"
s = path.read_text(encoding="utf-8")

def once(before, after, name):
    global s
    n = s.count(before)
    if n != 1: raise RuntimeError(f"{name}: expected one anchor, found {n}")
    s = s.replace(before, after, 1)

once("    bool hasScreenRect;\n};\nstatic std::vector<ChestData121> g_chestList;",
     "    bool hasScreenRect;\n    int kind = 0;\n};\nstatic std::vector<ChestData121> g_chestList;",
     "chest kind member")
once("struct ChestChunkCache121 { std::vector<ChestData121> hits; };",
     "struct ChestChunkCache121 { std::vector<ChestData121> hits; DWORD scannedAtMs = 0; };",
     "cache age member")

once("// Global cached player and its Reach attribute instance",
r"""// 0=normal, 1=ender chest, 2=barrel, 3=shulker
static int GetChestEspKind121(JNIEnv* env, jobject be) {
    if (!env || !be) return 0;
    for (int i = 0; i < 4; i++) {
        if (g_chestBlockEntityClasses[i] &&
            env->IsInstanceOf(be, g_chestBlockEntityClasses[i]) == JNI_TRUE)
            return i;
        if (env->ExceptionCheck()) env->ExceptionClear();
    }
    return 0;
}

// Global cached player and its Reach attribute instance""", "kind classifier")

p = r"(?m)^([ \t]*)chunkChests\.push_back\(\{cx2, cy2, cz2, 0\.0\}\);$"
if len(re.findall(p, s)) != 2: raise RuntimeError("collection site count changed")
s = re.sub(p, lambda m:
    m.group(1)+"ChestData121 record = {cx2, cy2, cz2, 0.0};\n"+
    m.group(1)+"record.kind = GetChestEspKind121(env, be);\n"+
    m.group(1)+"chunkChests.push_back(record);",s)

once("            if (g_chestChunkCache.find(chestKey) != g_chestChunkCache.end()) continue;",
     "            auto cached = g_chestChunkCache.find(chestKey);\n"
     "            if (cached != g_chestChunkCache.end() &&\n"
     "                (now - cached->second.scannedAtMs) < 2500) continue;",
     "cache age check")
once("            g_chestChunkCache[chestKey].hits = std::move(chunkChests);",
     "            auto& item = g_chestChunkCache[chestKey];\n"
     "            item.hits = std::move(chunkChests);\n"
     "            item.scannedAtMs = now;",
     "cache timestamp")

a = "                        // A chest occupies one block: x±0.5"
b = "                        fg->AddRect(ImVec2(minSX, minSY), ImVec2(maxSX, maxSY), boxColor, 0.0f, 0, lineThick);"
if s.count(a) != 1 or s.count(b) != 1:
    raise RuntimeError("ESP renderer anchor changed")
start = s.index(a); end = s.index(b,start)+len(b)
render = r"""                        // Render in world-space with a projected 3D wireframe.
                        // Model inset 1/16 and height 14/16 on ordinary/ender chests.
                        const bool full = ch.kind == 2 || ch.kind == 3;
                        const double inset = full ? 0.0 : 0.0625;
                        const double height = full ? 1.0 : 0.875;
                        const double low = -0.5 + inset, high = 0.5 - inset;
                        const double offsets[8][3] = {
                            {low,0,low},{high,0,low},{low,0,high},{high,0,high},
                            {low,height,low},{high,height,low},{low,height,high},{high,height,high}
                        };
                        static const int edges[12][2] = {
                            {0,1},{1,3},{3,2},{2,0},
                            {4,5},{5,7},{7,6},{6,4},
                            {0,4},{1,5},{2,6},{3,7}
                        };
                        ImVec2 points[8];
                        bool ok[8] = {};
                        for (int c=0; c<8; ++c) {
                            LegoVec3 xyz = {ch.x+offsets[c][0],
                                            ch.y+offsets[c][1],
                                            ch.z+offsets[c][2]};
                            float x=0.f,y=0.f;
                            bool projected = espMatsOk
                                ? WorldToScreen(xyz,espCam,espView,espProj,winW,winH,&x,&y)
                                : WorldToScreen_Angles(xyz,espCam,espYaw,espPitch,fov,winW,winH,&x,&y);
                            ok[c] = projected && std::isfinite(x) && std::isfinite(y) &&
                                    std::fabs(x) < winW*8.f && std::fabs(y) < winH*8.f;
                            points[c] = ImVec2(x,y);
                        }
                        ImU32 outline = overlayTheme.accentPrimary;
                        if (ch.kind == 1) outline=IM_COL32(170,100,255,230);
                        if (ch.kind == 2) outline=IM_COL32(255,170,75,230);
                        if (ch.kind == 3) outline=IM_COL32(220,125,240,230);
                        if (ok[4] && ok[5] && ok[6] && ok[7])
                            fg->AddQuadFilled(points[4],points[5],points[7],points[6],
                                              WithAlpha(outline,22));
                        for (int e=0; e<12; ++e) {
                            int i=edges[e][0],j=edges[e][1];
                            if (!ok[i] || !ok[j]) continue;
                            fg->AddLine(points[i],points[j],IM_COL32(0,0,0,140),lineThick+1.5f);
                            fg->AddLine(points[i],points[j],outline,lineThick);
                        }"""
s=s[:start]+render+s[end:]
path.write_text(s, encoding="utf-8")
print(f"Patched modern Chest ESP: {path}")
