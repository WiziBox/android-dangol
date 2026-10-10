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

## 남은 작업

1. 커밋 고정 upstream manifest, 기기 소스와 최종 후속 수정 정리
2. 원본 kernel/DTB·독점 파일의 소스 및 재배포 조건 또는 사용자 추출 방법 확인
3. 개인 인증키 없는 배포용 ramdisk·boot 패키징
4. system 이미지 포함물과 키 검사, 전체 라이선스 검토
5. 기존 PC 경로와 out에 의존하지 않는 클린 빌드
6. 최종 boot 크기에 맞는 U-Boot 절차와 기기별 백업·복구 안내
7. 검증 가능한 Release manifest·체크섬·다운로드·플래싱 스크립트
8. 실기기 회귀 결과 기록 및 시험판 공개

다른 기기의 전체 eMMC 백업이나 U-Boot 환경을 복사하는 방식은 제공하지 않습니다. 플래싱 자동화와 지금 연결된 기기에 실제 기록하는 작업은 구분합니다.
