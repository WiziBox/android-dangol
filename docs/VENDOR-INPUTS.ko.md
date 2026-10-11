# Dangol 소유자 입력 추출

대상은 INSIGNAL TAB4418_MAIN_V1.4 보드의 `dangol`, S5P6818, 원본 Android 7.1.2입니다. 보드 이름만 보고 S5P4418용 파일을 사용하면 안 됩니다.

이 저장소에는 제조사 바이너리, 공장 백업, 개인 Wi-Fi 보정 파일을 배포하지 않습니다. 아래 도구는 사용자가 합법적으로 확보한 **원본 system 백업**에서 필요한 파일만 추출합니다. 이미 수정한 LineageOS system 이미지가 아니라 원본을 사용하세요. 추출 성공은 재배포 허가를 뜻하지 않습니다.

## Linux / WSL 준비

Python 3.9 이상과 `debugfs`(`e2fsprogs`)가 필요합니다. 이미지와 출력 폴더를 개인 디렉터리에 두세요. 출력 부모 폴더는 미리 만들되 `stock-inputs`와 `vendor/nexell/dangol`은 존재하지 않아야 합니다.

```bash
python3 tools/extract_stock.py \
  --system-image /path/to/private/dangol-system.img \
  --output /path/to/private/stock-inputs

python3 tools/import_vendor.py \
  --input-root /path/to/private/stock-inputs \
  --output /path/to/android-source/vendor/nexell/dangol

# 위 사전 점검이 통과한 다음에만 실제 입력 트리를 생성합니다.
python3 tools/import_vendor.py \
  --input-root /path/to/private/stock-inputs \
  --output /path/to/android-source/vendor/nexell/dangol --apply
```

`extract_stock.py`는 raw ext4 백업만 받습니다. Android sparse 이미지라면 고정된 Android 소스의 `simg2img`로 **별도 새 파일**에 변환한 뒤 사용하세요. 도구는 `debugfs -w`, 마운트, ADB, fastboot를 사용하지 않습니다. 원본 이미지를 수정하지 않으며 지원 기준과 다른 파일은 거부합니다. 원본 펌웨어 심볼릭 링크는 백업 안에서 읽기 전용으로 해석합니다.

## 파일 범위와 주의점

25개 고정 입력은 그래픽·오디오·영상 라이브러리, Bluetooth/Wi-Fi 펌웨어, 오디오 설정과 원본 `bcmdhd.ko`입니다. `vendor-inputs/stock.json`에 크기와 SHA-256이 있습니다. 기존 포트의 제조사 입력 23개 및 Wi-Fi 모듈을 원본 백업과 비교하여 동일함을 확인했습니다. 제조사 구현 소스나 바이너리를 공개한 것은 아닙니다.

별도의 `nvram_ap6212.txt`에는 **기기 MAC 주소와 RF 보정값**이 있습니다. 도구는 소유자 파일을 그대로 보존하고 ASCII·중복 필드·MAC 형식·자격 증명 포함 여부만 검사합니다. 이 파일의 내용과 해시는 공개 색인이나 추출 영수증에 넣지 않습니다. Linux 출력 권한은 개인용으로 제한합니다. Windows에서는 계정별 ACL도 관리하세요. 생성된 vendor 폴더, system 이미지 및 원본 백업은 공개 Git/Release에 올리지 마세요.

현재 입력의 Wi-Fi 모듈은 **같은 원본 커널**과 함께 사용할 때만 유효합니다. 새 커널을 빌드한다면 모듈도 그 커널 설정/ABI에 맞게 다시 빌드해야 합니다. 이 도구는 해당 커널 소스 대응 관계나 모듈 호환성을 자동으로 증명하지 않습니다.

기기 트리의 오디오 파일 복사 항목은 생성된 `dangol-vendor.mk`와 중복되지 않아야 합니다. 전체 기기 트리 설치·빌드·부트 패키징이 아직 통합 중이므로, 이 문서만으로 완성 ROM을 빌드할 수 있다고 주장하지 않습니다. 플래싱은 하지 않습니다.
