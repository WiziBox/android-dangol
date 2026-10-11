# Dangol 소유자 입력으로 빌드하기

이 문서는 다른 PC에서 소스 빌드를 원할 때 사용할 절차입니다. 기존에 만든
최종 이미지가 없다는 뜻이 아니며, 배포 준비를 위해 전체 빌드를 반드시 다시
실행할 필요도 없습니다. 현재 작업에서는 기존 이미지를 우선 보존·검토하고,
누락된 코드 변경이 확인될 때만 해당 변경의 컴파일 필요성을 판단합니다.

아래 명령은 Linux/WSL에서 실행합니다. 각 경로를 자신의 새 작업 공간으로
바꾸세요. 저장소는 도구·프로젝트 소스만 제공하며 제조사 바이너리나 개인
보정 데이터는 소유자가 원본 기기의 백업에서 준비해야 합니다.

필요한 호스트 패키지는 Git, Git LFS, Android repo, Python 3, GCC multilib,
32비트 zlib 개발 헤더·라이브러리, debugfs입니다. 기존 개발 출력이나 시스템
Python 2를 가져다 쓰지 않습니다. JDK 8과 Python 2.7 실행 파일은 고정된
Android 소스의 prebuilt를 사용합니다.

## 1. 소스와 WebView

[고정 매니페스트](../manifests/README.md)로 새 소스를 동기화하고,
저장소 루트에서 프레임워크 패치를 검사·적용합니다.

```sh
python3 tools/apply_patches.py --source /path/to/android9-source
python3 tools/apply_patches.py --source /path/to/android9-source --apply
python3 tools/fetch_webview.py --abi arm --output /path/to/new-arm-webview
python3 tools/materialize_webview.py --source /path/to/android9-source --abi arm --input /path/to/new-arm-webview/webview.apk
python3 tools/materialize_webview.py --source /path/to/android9-source --abi arm --input /path/to/new-arm-webview/webview.apk --apply
```

## 2. 기기 트리와 비공개 소유자 입력

`dangol-stock-system.img`는 해당 기기의 원본 2GiB raw ext4 system 백업입니다.
다른 제품의 이미지나 사용자 데이터 파티션을 입력하지 마세요. 추출 도구는
원본을 마운트하거나 수정하지 않고 허용 목록의 파일만 읽습니다. 추출 결과는
GitHub 저장소 밖에 두세요. 상세 조건은 [소유자 입력](VENDOR-INPUTS.ko.md)과
[기기 트리](DEVICE-SOURCES.ko.md)를 확인하세요.

```sh
python3 tools/stage_device.py --source /path/to/android9-source
python3 tools/stage_device.py --source /path/to/android9-source --apply
python3 tools/extract_stock.py --system-image /path/to/private/dangol-stock-system.img --output /path/to/new-private-stock-inputs
mkdir -p /path/to/android9-source/vendor/nexell
python3 tools/import_vendor.py --input-root /path/to/new-private-stock-inputs --output /path/to/android9-source/vendor/nexell/dangol
python3 tools/import_vendor.py --input-root /path/to/new-private-stock-inputs --output /path/to/android9-source/vendor/nexell/dangol --apply
```

기존 출력은 덮어쓰지 않습니다. 소유자 파일 해시가 다르면 임의로 해시 검사를
끄지 말고 원본 버전 차이를 먼저 확인해야 합니다. 이 vendor 트리에는 개인
Wi-Fi 보정값이 있을 수 있으므로 생성 후에도 공개 업로드 대상이 아닙니다.

## 3. 새 출력 디렉터리에서 빌드

```sh
BUILD_JOBS=4 bash tools/build_android.sh /path/to/android9-source /path/to/new-android-out
```

기본 목표는 `systemimage ramdisk`입니다. 출력은 소스 밖의 새 디렉터리여야
합니다. 실패 시 출력과 `build.log`를 보존해 원인을 확인하세요. 이 명령은
커널을 빌드하거나 태블릿을 재부팅·플래싱하지 않습니다. 원본 커널과 그에
대응하는 원본 Wi-Fi 모듈을 사용하는 제품입니다.

## 4. 새 boot 패키징

원본 `/boot` 파티션 백업을 비공개 템플릿으로 사용합니다. 새 ramdisk는 방금
빌드한 출력의 `target/product/dangol/ramdisk.img`입니다.

```sh
python3 tools/pack_boot.py --template /path/to/private/dangol-stock-boot.img --ramdisk /path/to/new-android-out/target/product/dangol/ramdisk.img --output /path/to/private/new-dangol-boot.img
python3 tools/pack_boot.py --template /path/to/private/dangol-stock-boot.img --ramdisk /path/to/new-android-out/target/product/dangol/ramdisk.img --output /path/to/private/new-dangol-boot.img --apply
python3 tools/audit_boot.py --device dangol /path/to/private/new-dangol-boot.img
sha256sum /path/to/private/new-dangol-boot.img /path/to/new-android-out/target/product/dangol/system.img
```

패키징은 원본 kernel/DTB만 유지하고 원본 ramdisk·기기명·명령줄·미사용
헤더 값을 복사하지 않습니다. 새 명령줄은 `buildvariant=userdebug`입니다.
지원 형식은 이 보드에서 확인된 2048바이트 페이지의 unsigned Android v0와
ARM64 Image, FDT v17입니다. 알 수 없는 비제로 후행 데이터는 거부합니다.
newc/gzip ramdisk 승인키 검사에 실패하면 새 boot를 만들지 않습니다.

결과의 `uboot_read_sectors`는 새 이미지 크기에 필요한 512바이트 섹터 수입니다.
기기의 기존 U-Boot 읽기 길이가 부족하면 boot 기록만으로는 부팅하지 못할 수
있습니다. 이 숫자는 시작 섹터나 U-Boot 환경 변경 명령이 아니며 도구는
부트로더 설정을 바꾸지 않습니다. 기기별 원본 환경·복구 경로 검토 없이
임의의 환경 값을 기록하지 마세요.

## 검증 상태와 남은 배포 조건

새 패키징의 합성 테스트 6개와 실제 원본 boot의 kernel/DTB 읽기가 통과했습니다.
원본 kernel은 20,102,208바이트, DTB는 63,488바이트입니다. 이는 새 ROM의 실제
부팅 성공을 증명하지 않습니다. 새 작업 공간 전체 빌드, 전체 system 검사,
U-Boot 읽기 경로 및 실기 설치·복구 확인이 남습니다. 제조사 파일과 보정 데이터의
재배포 권한이 확인되기 전에는 이 결과를 공개 ROM으로 업로드하지 않습니다.
