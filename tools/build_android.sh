#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build on the host only. No flashing or automatic download occurs here.
set -euo pipefail
if [[ $# -lt 2 ]]; then
    echo 'Usage: bash tools/build_android.sh SOURCE NEW_OUT_DIR [make targets...]' >&2
    exit 2
fi
source_tree=$(realpath "$1")
build_output=$(realpath -m "$2")
tool_directory=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
shift 2
if [[ -e "$build_output" || -L "$build_output" ]]; then
    echo 'Refusing to reuse an existing output directory.' >&2
    exit 2
fi
case "$build_output/" in
    "$source_tree/"*) echo 'Output must be outside the source tree.' >&2; exit 2;;
esac
test -f "$source_tree/build/envsetup.sh"
test -f "$source_tree/device/nexell/dangol/device.mk"
test -f "$source_tree/vendor/nexell/dangol/dangol-vendor.mk"
export JAVA_HOME="$source_tree/prebuilts/jdk/jdk8/linux-x86"
test -x "$JAVA_HOME/bin/java"
python_prebuilt="$source_tree/prebuilts/python/linux-x86/2.7.5"
test -x "$python_prebuilt/bin/python2.7"
test -f "$source_tree/external/python/cpython2/Modules/zlibmodule.c"
command -v gcc >/dev/null
# Refuse an unresolved LFS pointer or wrong ABI before creating output.
python3 - "$source_tree/external/chromium-webview/prebuilt/arm/webview.apk" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as apk:
    if not any(name.startswith('lib/armeabi-v7a/') and name.endswith('.so') for name in apk.namelist()):
        raise SystemExit('ARM WebView native libraries missing')
PY
# Keep this host extension under the new output; never reuse a developer's
# copied zlib.so or change the system Python. Host 32-bit zlib headers/libs
# and GCC multilib are required. Upstream CPython source stays untouched.
mkdir -p "$build_output/host/python2-modules"
gcc -m32 -shared -fPIC -O2 \
    -I "$python_prebuilt/include/python2.7" \
    -include "$tool_directory/python27-zlib-compat.h" \
    "$source_tree/external/python/cpython2/Modules/zlibmodule.c" -lz \
    -o "$build_output/host/python2-modules/zlib.so"
export PYTHONPATH="$build_output/host/python2-modules"
export PYTHONDONTWRITEBYTECODE=1
export PATH="$python_prebuilt/bin:$JAVA_HOME/bin:$PATH"
python2.7 -c 'import sys, zlib; assert sys.version_info[:2] == (2, 7); assert zlib.decompress(zlib.compress("probe")) == "probe"'
export OUT_DIR="$build_output"
cd "$source_tree"
# The historical envsetup script assumes variables may be unset.
set +u
source build/envsetup.sh
lunch lineage_dangol-userdebug
# Keep nounset disabled while calling old envsetup functions (TOP may be unset).
if [[ $# -eq 0 ]]; then
    set -- systemimage ramdisk
fi
if ! m -j"${BUILD_JOBS:-4}" "$@" > "$build_output/build.log" 2>&1; then
    tail -n 80 "$build_output/build.log" >&2
    echo 'Build failed; preserve the output and inspect build.log.' >&2
    exit 1
fi
echo 'Host build completed. Stock kernel/DTB boot packaging remains separate; no release approval or device installation.'
