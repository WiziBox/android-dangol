# 다른 PC에서 빌드·다운로드·플래싱하기 위한 작업 계획

목표는 소스 확보 → 빌드 → 이미지 다운로드·검증 → 대상 기기 확인 → 백업·플래싱·복구를 저장소에서 수행할 수 있게 하는 것입니다. 전체 경로는 아직 미완성입니다. 소스와 커널/DTB의 대응 관계, 라이선스, 누락된 프레임워크 변경 및 U-Boot 읽기 길이 처리를 정리해야 합니다.

## boot 승인키 검사

Python 3 표준 라이브러리만 사용합니다. 기기를 연결하거나 이미지를 수정하지 않습니다.

```sh
python3 -m unittest discover -s tests -v
python3 tools/audit_boot.py --device dangol /path/to/boot.img
```

Windows에서는 설치한 `python` 명령을 사용할 수 있습니다. 종료 코드 0은 지원하는 boot ramdisk 검사만 통과한 것이며 ROM 전체의 안전성·라이선스·부팅 성공이나 공개 승인을 뜻하지 않습니다. 종료 코드 1은 키/설정 문제, 2는 파일/파싱 오류입니다. 도구는 키 내용이나 호스트 식별자를 출력하지 않습니다.

## 기존 후보 검사 결과 — 2026-10-11

- `dangol-lineage16-root-adb-boot.img`: `/adb_keys`와 기본 권한 설정 문제 검출. 미공개.
- `dangol-lineage16-trusted-adb-boot.img`: `/adb_keys` 검출. 미공개.
- `dangol-lineage16-adb-boot.img`: 지원하는 boot/ramdisk 키 검사 통과. system/vendor·커널·라이선스·최종 기능과의 일치 확인이 남아 있어 아직 배포용 ROM으로 제공하지 않음.

## 원본을 보존하는 boot 승인키 제거 도구

지원하는 unsigned Android v0 형식에 한해 새 후보를 별도 파일로 생성합니다.

```sh
python3 tools/sanitize_boot.py --device dangol --input /path/to/private-boot.img --output /path/to/new-candidate.img
```

기존 출력 파일을 덮어쓰지 않으며, ADB 공개 승인 파일을 제거하고 기존 `default.prop`의 `ro.adb.secure`와 `ro.secure`를 1로 설정합니다. 커널과 second payload(DTB)를 보존하고 알 수 없는 서명·트레일러, 남은 키 검사 문제는 거부합니다. 네트워크 ADB 자동 활성화나 system/vendor는 수정하지 않습니다. 플래싱 또는 부팅 가능 여부 검증도 하지 않습니다.

2026-10-11에 원본을 보존한 로컬 새 후보(21,864,448 bytes, SHA256 `d6b84eee294fa9d434c5e0647a5217662062e49212c8243798b20cad52a32763`)를 생성했고, 제한된 boot 키 검사와 커널·DTB 보존 검사를 통과했습니다. 도구 테스트는 36개로 늘었고 로컬에서 통과했습니다. 이 파일은 전체 ROM 검토 및 실기 부팅 검증을 완료한 공개 Release가 아닙니다.

## 남은 작업

2026-10-11: [커밋 고정 소스 manifest와 패치 준비 절차](../manifests/README.md)를 추가했습니다. 709개 upstream 프로젝트와 11개 프로젝트의 tracked 텍스트 패치는 확보했지만 device/vendor·커널/DTB·WebView LFS 입력·boot 패키징은 미완성입니다. `tools/apply_patches.py`는 기존 수정본을 덮어쓰지 않고 커밋·해시·깨끗한 상태를 먼저 검사합니다.

1. 커밋 고정 upstream manifest, 기기 소스와 최종 후속 수정 정리
2. 원본 kernel/DTB·독점 파일의 소스 및 재배포 조건 또는 사용자 추출 방법 확인
3. 개인 인증키 없는 배포용 ramdisk·boot 패키징
4. system 이미지 포함물과 키 검사, 전체 라이선스 검토
5. 기존 PC 경로와 out에 의존하지 않는 클린 빌드
6. 최종 boot 크기에 맞는 U-Boot 절차와 기기별 백업·복구 안내
7. 검증 가능한 Release manifest·체크섬·다운로드·플래싱 스크립트
8. 실기기 회귀 결과 기록 및 시험판 공개

다른 기기의 전체 eMMC 백업이나 U-Boot 환경을 복사하는 방식은 제공하지 않습니다. 플래싱 자동화와 지금 연결된 기기에 실제 기록하는 작업은 구분합니다.
