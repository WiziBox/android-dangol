# system 이미지의 제한된 개인정보 검사

`tools/inspect_system.py`와 `tools/audit_system.py`는 같은 프로젝트의 Acer 공개
도구를 Apache-2.0 고지와 함께 재사용했습니다. 이미지 검사에는 `--device dangol`을
지정합니다. 이미지 크기·형식 검사는 Python 표준 라이브러리로 Windows/Linux에서
가능하지만 전체 파일 검사는 Linux의 e2fsprogs `debugfs`, `e2fsck`가 필요합니다.

```sh
python3 tools/inspect_system.py --device dangol /private/system.raw.img
python3 tools/audit_system.py --device dangol --image /private/system.raw.img --work-dir /private/work --report /private/system-audit.json --check-filesystem
```

work 폴더는 미리 만들어 두고 결과 JSON은 아직 없는 새 경로를 사용합니다.
보고서는 공개 저장소 밖에 저장하며 Linux에서 새 보고서 권한은 0600입니다.
보고서도 검토 없이 업로드하지 마세요. 개인 키·MAC·SSID 값 자체는 출력하지
않지만 의심 파일 경로와 원인 분류는 표시합니다.

Android sparse 이미지도 검사하며 변환이 필요하면 고정 소스에서 만든
`--simg2img /private/host/bin/simg2img`를 지정합니다. 별도 임시 raw 파일 공간이
필요합니다. 원본을 마운트·수정하지 않으며 기기와 통신하지 않습니다.
`e2fsck -f -n`은 읽기 전용이고 자동 복구하지 않습니다.

검사 범위: 전체 일반 파일, APK/JAR/ZIP의 바로 아래 압축 멤버, 알려진 개인키·ADB
승인키 패턴, 저장된 네트워크 설정, 비보안 ADB 기본값, 주요 Google 앱 후보 등.
심볼릭 링크 대상은 따라가지 않으며 중첩 압축파일을 재귀 검사하지 않습니다.
모든 비밀·인증서·토큰·라이선스·펌웨어 권리를 판별하는 도구는 아닙니다.
`google.jks` 같은 신뢰 인증서 모음도 키 파일명 규칙에 걸릴 수 있으므로 결과를
자동 삭제 명령으로 바꾸지 말고 별도 분석하세요.

종료 코드 0은 제한된 검사를 완료하고 발견 항목이 없음, 1은 발견 항목이 있음,
2는 검사 미완료·형식·파일시스템 오류입니다. 모든 결과에서 공개 승인은 false입니다.

2026-10-11 기존 보정값 제거 비공개 Dangol 후보에서 일반 파일 1,908개,
디렉터리 205개, 786,208,863바이트를 검사했습니다. 발견 항목 없음과 읽기 전용
파일시스템 검사 통과를 확인했습니다. 이것은 재빌드·새 후보 실기 부팅 성공·ROM
재배포 허가가 아닙니다. 이미지·비공개 보고서는 업로드하지 않았습니다.
