#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -lt 1 ]; then
    echo "usage: $0 <output-dir> (e.g. /license-output)" >&2
    exit 2
fi
OUT="$1"
BUILD_DIR="${BUILD_DIR:-/tmp/wings-license-build}"

# 第三方源码不入 git(AdaptiveLM 厂商源码约 7.5 万行 + Huawei Secure C),构建期
# 按需从内部制品仓库下载:解压目录已存在时直接复用;归档已存在时跳过下载(可把
# 归档预先拷入本目录实现离线构建)。libboundscheck 的 zip 解压出 libboundscheck-v1.1.16/
# 目录,需改名为构建期望的 libboundscheck/,以兼容既有解压缓存。
ADAPTIVELM_URL="http://artifactrepo.wux-g.tools.xfusion.com/artifactory/generic-operator/xfusion-operator/AdaptiveLMV100R005C10_S.tar"
LIBBOUNDSCHECK_URL="http://artifactrepo.wux-g.tools.xfusion.com/artifactory/opensource_general/libboundscheck/1.1.16/package/libboundscheck-v1.1.16.zip"

fetch_archive() {
    local url="$1"
    local archive="$2"
    if [ -f "$archive" ]; then
        return 0
    fi
    echo "Fetching $(basename "$archive") from artifact repository ..."
    if ! wget -q -O "$archive.part" "$url"; then
        rm -f "$archive.part"
        echo "ERROR: failed to download $url" >&2
        exit 1
    fi
    mv "$archive.part" "$archive"
}

prepare_adaptivelm() {
    if [ -d "$ROOT/adaptivelm" ]; then
        return 0
    fi
    fetch_archive "$ADAPTIVELM_URL" "$ROOT/AdaptiveLMV100R005C10_S.tar"
    echo "Extracting adaptivelm ..."
    tar -xf "$ROOT/AdaptiveLMV100R005C10_S.tar" -C "$ROOT" adaptivelm
    if [ ! -d "$ROOT/adaptivelm" ]; then
        echo "ERROR: adaptivelm/ not found after extraction" >&2
        exit 1
    fi
}

prepare_libboundscheck() {
    if [ -d "$ROOT/libboundscheck" ]; then
        return 0
    fi
    fetch_archive "$LIBBOUNDSCHECK_URL" "$ROOT/libboundscheck-v1.1.16.zip"
    echo "Extracting libboundscheck ..."
    rm -rf "$ROOT/libboundscheck-v1.1.16"
    unzip -q "$ROOT/libboundscheck-v1.1.16.zip" -d "$ROOT"
    mv "$ROOT/libboundscheck-v1.1.16" "$ROOT/libboundscheck"
    if [ ! -f "$ROOT/libboundscheck/Makefile" ]; then
        echo "ERROR: libboundscheck/Makefile not found after extraction" >&2
        exit 1
    fi
}

prepare_adaptivelm
prepare_libboundscheck

rm -rf "$BUILD_DIR" "$OUT"
mkdir -p "$BUILD_DIR/adaptivelm" "$BUILD_DIR/libboundscheck" "$OUT/bin" "$OUT/lib" "$OUT/key"

cp -a "$ROOT/libboundscheck/." "$BUILD_DIR/libboundscheck/"
make -C "$BUILD_DIR/libboundscheck" -j"$(nproc)"

cmake -S "$ROOT/adaptivelm" -B "$BUILD_DIR/adaptivelm" \
    -DTARGET_PLATFORM=linux_native \
    -DBYTE_ORDER_FLAG=le \
    -DTARGET_VERSION=release \
    -DTARGET=static \
    -DTARGET_OUTPUT="$BUILD_DIR" \
    -DSECUREC=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-D__LINUX__ -I$BUILD_DIR/libboundscheck/include"
cmake --build "$BUILD_DIR/adaptivelm" -j"$(nproc)"

# Key File 构建期加密:交付件只携带 license.key.enc(XTEA-CTR),对称密钥
# (每次构建随机生成)编进 checker 二进制(key_material.h),运行期内存解密,
# 明文不落盘、不进交付件。
python3 "$ROOT/encrypt_key.py" \
    "$ROOT/key/keyFile_KunLunAIPerfSDK_26_RSA3072.txt" \
    "$OUT/key/license.key.enc" \
    "$BUILD_DIR/key_material.h"

# Hardened build flags: -O2 enables _FORTIFY_SOURCE; stack protector and
# full RELRO harden the checker binary; -s strips symbols. PIE is kept
# separate: the prebuilt AdaptiveLM static lib may not be PIC-compatible.
CFLAGS="-O2 -D_FORTIFY_SOURCE=2 -fstack-protector-strong"
LDFLAGS="-Wl,-z,relro -Wl,-z,now -s"
PIE_FLAGS="-fPIE -pie"

if ! gcc $PIE_FLAGS -D__LINUX__ \
    -I"$ROOT/adaptivelm/include" \
    -I"$BUILD_DIR" \
    "$ROOT/checker.c" \
    "$BUILD_DIR/output/linux_native/lic_linux_native_le_release.a" \
    -L"$BUILD_DIR/libboundscheck/lib" \
    -lboundscheck -lpthread \
    $CFLAGS $LDFLAGS \
    -Wl,-rpath,'$ORIGIN/../lib' \
    -o "$OUT/bin/wings-license-check" 2>/dev/null; then
    PIE_FLAGS=""
    gcc -D__LINUX__ \
        -I"$ROOT/adaptivelm/include" \
        -I"$BUILD_DIR" \
        "$ROOT/checker.c" \
        "$BUILD_DIR/output/linux_native/lic_linux_native_le_release.a" \
        -L"$BUILD_DIR/libboundscheck/lib" \
        -lboundscheck -lpthread \
        $CFLAGS $LDFLAGS \
        -Wl,-rpath,'$ORIGIN/../lib' \
        -o "$OUT/bin/wings-license-check"
fi

cp "$BUILD_DIR/libboundscheck/lib/libboundscheck.so" "$OUT/lib/"
chmod 0555 "$OUT/bin/wings-license-check"
chmod 0444 "$OUT/lib/libboundscheck.so" "$OUT/key/license.key.enc"
