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
     "    bool hasScreenRect;\n    int kind;\n};\nstatic std::vector<ChestData121> g_chestList;",
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

# Render-frame camera pose. The old background snapshot was intentionally
# asynchronous, which caused chests to drift on the screen during camera turns.
# Keep JNI operations to Get*Field only; no method calls on this render path.
once("static void RenderOverlayPanels(\n",
r"""// Get camera pose during the actual rendered frame so ESP follows blocks.
static bool TryReadFrameChestCamera121(LegoVec3* pos, float* yawOut, float* pitchOut) {
    if (!g_jvm || !g_stateJniReady || !g_mcInstance ||
        !g_gameRendererField_121 || !g_gameRendererCameraField_121 ||
        !g_cameraPosF_121 || !g_cameraYawF_121 || !g_cameraPitchF_121 ||
        !g_vec3dX_121 || !g_vec3dY_121 || !g_vec3dZ_121) return false;
    JNIEnv* env = nullptr;
    if (g_jvm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) != JNI_OK || !env)
        return false;
    if (env->ExceptionCheck()) return false;
    LockGuard lk(g_jniRemapMtx);
    jobject gr = env->GetObjectField(g_mcInstance, g_gameRendererField_121);
    if (env->ExceptionCheck()) { env->ExceptionClear(); gr = nullptr; }
    if (!gr) return false;
    jobject cam = env->GetObjectField(gr, g_gameRendererCameraField_121);
    if (env->ExceptionCheck()) { env->ExceptionClear(); cam = nullptr; }
    env->DeleteLocalRef(gr);
    if (!cam) return false;
    jobject v = env->GetObjectField(cam, g_cameraPosF_121);
    if (env->ExceptionCheck()) { env->ExceptionClear(); v = nullptr; }
    if (!v) { env->DeleteLocalRef(cam); return false; }
    const double x = env->GetDoubleField(v, g_vec3dX_121);
    const double y = env->GetDoubleField(v, g_vec3dY_121);
    const double z = env->GetDoubleField(v, g_vec3dZ_121);
    const float yaw = env->GetFloatField(cam, g_cameraYawF_121);
    const float pitch = env->GetFloatField(cam, g_cameraPitchF_121);
    const bool ok = !env->ExceptionCheck() &&
        std::isfinite(x) && std::isfinite(y) && std::isfinite(z) &&
        std::isfinite(yaw) && std::isfinite(pitch);
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(v);
    env->DeleteLocalRef(cam);
    if (!ok) return false;
    *pos = {x, y, z};
    *yawOut = yaw;
    *pitchOut = pitch;
    return true;
}

static void RenderOverlayPanels(
""", "frame-camera-helper")

once("                // Use shared camera data (same source as nametags – no redundant JNI fetch)\n"
     "                const LegoVec3   espCam   = sharedCam;\n"
     "                const float      espYaw   = sharedYaw;\n"
     "                const float      espPitch = sharedPitch;\n"
     "                const bool       espMatsOk = sharedMatsOk;\n",
     "                // Use the current render frame's camera pose whenever available.\n"
     "                LegoVec3 espCam = sharedCam;\n"
     "                float espYaw = sharedYaw;\n"
     "                float espPitch = sharedPitch;\n"
     "                const bool framePoseOk = TryReadFrameChestCamera121(&espCam, &espYaw, &espPitch);\n"
     "                // Avoid mixing current camera pose with stale background view matrices.\n"
     "                const bool espMatsOk = !framePoseOk && sharedMatsOk;\n",
     "chest-frame-projection")


# Fabric world-render hook provides actual projection and modelview matrices.
# This is fundamentally different from predicting screen coordinates from yaw/FOV.
once("static void RenderOverlayPanels(\n",
r"""#include "aoko_world_matrix_class.h"

// Fabric 1.21.x exact world-frame projection captured from WorldRenderEvents.LAST.
struct AokoWorldMatrixFrame121 {
    Matrix4x4 view, proj;
    LegoVec3 camera;
    DWORD seenAt = 0;
    bool valid = false;
};
static AokoWorldMatrixFrame121 g_aokoWorldMatrixFrame121;
static Mutex g_aokoWorldMatrixMutex121;
static bool g_aokoWorldMatrixHookInstalled121 = false;

static void JNICALL AokoOnWorldMatrices121(JNIEnv* env, jclass,
        jfloatArray viewArr, jfloatArray projArr, jobject camera) {
    if (!env || !viewArr || !projArr || !camera || !g_cameraPosF_121 ||
        !g_vec3dX_121 || !g_vec3dY_121 || !g_vec3dZ_121) return;
    if (env->GetArrayLength(viewArr) != 16 || env->GetArrayLength(projArr) != 16)
        return;
    jobject pos = env->GetObjectField(camera, g_cameraPosF_121);
    if (env->ExceptionCheck()) { env->ExceptionClear(); pos = nullptr; }
    if (!pos) return;
    const double x = env->GetDoubleField(pos, g_vec3dX_121);
    const double y = env->GetDoubleField(pos, g_vec3dY_121);
    const double z = env->GetDoubleField(pos, g_vec3dZ_121);
    if (env->ExceptionCheck()) { env->ExceptionClear(); env->DeleteLocalRef(pos); return; }
    env->DeleteLocalRef(pos);
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return;
    AokoWorldMatrixFrame121 next;
    env->GetFloatArrayRegion(viewArr, 0, 16, next.view.m);
    env->GetFloatArrayRegion(projArr, 0, 16, next.proj.m);
    if (env->ExceptionCheck()) { env->ExceptionClear(); return; }
    next.camera = {x,y,z};
    next.seenAt = GetTickCount();
    next.valid = true;
    LockGuard lk(g_aokoWorldMatrixMutex121);
    g_aokoWorldMatrixFrame121 = next;
}

static void AokoInstallWorldMatrixHook121(JNIEnv* env) {
    if (!env || !g_gameClassLoader || g_aokoWorldMatrixHookInstalled121)
        return;
    jclass helper = env->DefineClass("aoko/render/WorldMatrixTap",
        g_gameClassLoader,
        reinterpret_cast<const jbyte*>(kAokoWorldMatrixTapClass),
        (jsize)sizeof(kAokoWorldMatrixTapClass));
    if (env->ExceptionCheck()) { env->ExceptionClear(); return; }
    if (!helper) return;
    JNINativeMethod natives[] = {
        {const_cast<char*>("onMatrices"),
         const_cast<char*>("([F[FLjava/lang/Object;)V"),
         reinterpret_cast<void*>(AokoOnWorldMatrices121)}
    };
    if (env->RegisterNatives(helper, natives, 1) != JNI_OK) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        env->DeleteLocalRef(helper); return;
    }
    jmethodID install = env->GetStaticMethodID(helper, "install", "(Ljava/lang/ClassLoader;)Z");
    if (env->ExceptionCheck()) { env->ExceptionClear(); install = nullptr; }
    if (install) {
        jboolean installed = env->CallStaticBooleanMethod(helper, install, g_gameClassLoader);
        if (env->ExceptionCheck()) { env->ExceptionClear(); installed = JNI_FALSE; }
        if (installed == JNI_TRUE) {
            g_aokoWorldMatrixHookInstalled121 = true;
            Log("ChestESP: Fabric WorldRenderEvents.LAST exact matrices ACTIVE");
        }
    }
    env->DeleteLocalRef(helper);
}

static void RenderOverlayPanels(
""", "World-frame hook")

# Run registration on the JNI worker, never in OpenGL/Vulkan present callback.
once("static DWORD WINAPI FastPollThreadProc(LPVOID) {",
     "static void AokoInstallWorldMatrixHook121(JNIEnv* env);\n"
     "static DWORD WINAPI FastPollThreadProc(LPVOID) {",
     "hook forward declaration")

once("                ReadCameraState(env);\n",
     "                ReadCameraState(env);\n"
     "                AokoInstallWorldMatrixHook121(env);\n",
     "world matrix hook registration")

# Use actual frame matrices rather than reconstructed angle math for Chest ESP.
once("                // Avoid mixing current camera pose with stale background view matrices.\n"
     "                const bool espMatsOk = !framePoseOk && sharedMatsOk;\n"
     "                const Matrix4x4  espProj  = sharedProj;\n"
     "                const Matrix4x4  espView  = sharedView;\n",
     "                // Exact world-frame matrices, including interpolation, FOV effects,\n"
     "                // bobbing, and renderer-specific projection transforms.\n"
     "                AokoWorldMatrixFrame121 frame;\n"
     "                { LockGuard lk(g_aokoWorldMatrixMutex121); frame = g_aokoWorldMatrixFrame121; }\n"
     "                const bool frameValid = frame.valid &&\n"
     "                    (GetTickCount() - frame.seenAt) < 120;\n"
     "                if (frameValid) espCam = frame.camera;\n"
     "                const bool espMatsOk = frameValid;\n"
     "                const Matrix4x4 espProj = frameValid ? frame.proj : sharedProj;\n"
     "                const Matrix4x4 espView = frameValid ? frame.view : sharedView;\n",
     "world-frame render selection")

path.write_text(s, encoding="utf-8")
print(f"Patched modern Chest ESP: {path}")
