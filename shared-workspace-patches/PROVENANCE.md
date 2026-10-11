# Provenance, licensing and modification notice

These are **modified** upstream sources distributed as textual patches, not unmodified upstream releases. Changes were made during the WiziBox Android 9 development project. Apache-file patch changes are distributed under Apache-2.0; the Skia patch retains BSD-3-Clause. Original copyrights and applicable notices remain in force. See `../LICENSES/` and `../third-party-notices/`.

| Patch | Upstream repository | Base commit |
|---|---|---|
| frameworks-native.patch | https://github.com/LineageOS/android_frameworks_native | 38be48f36da1acd812670fbecb75bffca9b4cd98 |
| frameworks-base.patch | https://github.com/LineageOS/android_frameworks_base | ea0de66d71ac88db42f26d9b63c9c1941aa097fc |
| frameworks-av.patch | https://github.com/LineageOS/android_frameworks_av | 541d785e2b89cfbc60df0ecae0edff7977283351 |
| system-core.patch | https://github.com/LineageOS/android_system_core | 976019d07ad1c007043b78450857f428a1440f06 |
| system-netd.patch | https://github.com/LineageOS/android_system_netd | 02458b0a19ce2d3214a00f9779bd36868541b7ca |

## Modified files and purposes

- frameworks/native: `libs/ui/Gralloc2.cpp` (allocation diagnostics), `services/inputflinger/InputReader.cpp` (legacy touch rotation), `services/surfaceflinger/SurfaceFlinger.cpp` (legacy display compatibility and client composition)
- frameworks/base: `core/jni/fd_utils.cpp` (isolated-process optional trace access), `libs/hwui/Properties.cpp` (SystemUI renderer selection), `services/core/java/com/android/server/display/ColorFade.java` (legacy display capture guard), `services/core/java/com/android/server/net/NetworkPolicyManagerService.java` (legacy network compatibility)
- frameworks/av: `media/libstagefright/ACodec.cpp` (legacy codec extension/crop handling), `media/libstagefright/colorconversion/SoftwareRenderer.cpp` (software rendering compatibility)
- system/core: `libsuspend/autosuspend_wakeup_count.cpp` (legacy resume handling)
- system/netd: `server/TetherController.cpp` (legacy counter-chain initialization)

The eleven files listed above belong to the first five projects and carry Apache-2.0 headers. Six more projects (twelve files) are recorded in additional-provenance.json, bringing the total to eleven projects and twenty-three files. Skia uses its original BSD-3-Clause license, not Apache-2.0. Original file headers and available upstream NOTICE/LICENSE files are preserved. All eleven patches were checked against their actual base commits using disposable Git indexes, with no live source or index changes. This is not a complete build or functional validation.

No proprietary library implementation, firmware, Google APK, kernel binary or device backup is included. This subset must not be mistaken for a complete corresponding kernel source distribution or a complete ROM source tree.
