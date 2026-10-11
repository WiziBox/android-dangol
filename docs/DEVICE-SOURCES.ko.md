# Dangol 기기 트리 배치

대상은 INSIGNAL TAB4418_MAIN_V1.4 보드의 `dangol` 제품입니다. 다른
S5P6818 기기에 이 설정을 그대로 사용하지 마세요.

저장소의 `source/device/nexell/dangol`은 프로젝트 설정 16개와 기존에
출처·수정 내역을 검토한 Nexell HWC/그라록 파일 32개를 포함합니다.
`source/dangol-device-provenance.json`은 설정 파일의 크기와 SHA-256을,
`source/dangol-hwc-provenance.json`은 상류 코드의 출처와 해시를 기록합니다.
제조사 드라이버 바이너리, 원본 오디오 설정, Wi-Fi 보정 데이터는 포함하지 않습니다.

새 Android 소스 작업 공간에서만 실행하세요. 기본 실행은 검사만 합니다.

```sh
python3 tools/stage_device.py --source /path/to/new-android-source
python3 tools/stage_device.py --source /path/to/new-android-source --apply
```

`build/envsetup.sh`가 있어야 하며 `device/nexell/dangol`이 이미 존재하면
덮어쓰지 않고 중단합니다. 실패 시 새로 생긴 부분 디렉터리를 자동 삭제하지 않습니다.
이 단계만으로 ROM을 빌드하거나 기기에 접속하지 않습니다.

## 원본 개발 환경과 구분해야 할 정책

- ARM 32비트 사용자 공간과 소유자 원본 ARM64 커널/DTB를 사용합니다.
  원본 `bcmdhd.ko`는 그 커널과 짝지어야 합니다. 새 커널을 빌드했다고
  주장하거나 다른 커널에 이 모듈을 재사용하지 않습니다.
- 기본 디스플레이 HAL은 기존 `dangol`입니다. `dangol_next`는 빌드 대상에만
  포함되며 활성화하지 않습니다. 패널 회전 270도와 기존 표시 보정값을 유지합니다.
- USB ADB 인증을 켭니다. 개인 승인키를 포함하거나 네트워크 ADB를 자동으로
  활성화하지 않습니다. 다른 PC에서는 기기 화면에서 새 연결을 승인해야 합니다.
- Wi-Fi 기본 설정은 자격 증명 없는 새 템플릿입니다. 소유자의 AP 이름·암호·
  MAC 주소·보정 파일을 공개 소스에 복사하지 않습니다.
- `/system` 기본 마운트는 읽기 전용입니다. 개발용 읽기·쓰기 설정과 다르므로
  완성 이미지의 실제 부팅 및 유지보수 동작 검증이 필요합니다.
- Wi-Fi 모듈과 원본 오디오 설정 두 개의 복사는 별도 소유자 vendor 목록에서만
  수행합니다. 제품 설정에서 중복 복사하지 않습니다. vendor 목록이 없으면
  빌드가 실패하도록 필수 입력으로 지정했습니다.
- GPU/ION 노드의 넓은 접근 권한과 기존 커널 보안 한계는 그대로 남습니다.
  보안 강화된 정식 제조사 ROM과 동등하다고 보장하지 않습니다.

이 기기 트리 배치 테스트는 실제 부팅·플래싱·복구 시험이나 제조사 파일의
재배포 허가를 대신하지 않습니다. 특히 recovery 설정 파일의 존재는 TWRP 또는
작동하는 recovery 이미지가 완성됐다는 의미가 아닙니다.
