# INSIGNAL TAB4418 (dangol) — Android 9 port

비공식 Android 9 / LineageOS 16.0 포팅 프로젝트입니다. INSIGNAL, Nexell 또는 LineageOS의 공식 배포가 아닙니다.

## 지원 대상

- 보드 실크: `INSIGNAL TAB4418_MAIN_V1.4`, 날짜 `2020.04.28`
- Android 코드명: `dangol`
- 확인된 플랫폼: Nexell S5P6818
- 32비트 ARM 사용자 공간, 기존 4.4.83+ 커널 기반
- TAB4418은 확인된 보드명이며 완제품 판매 모델명은 미확인입니다. 같은 이름의 다른 보드나 SoC에는 적용하지 마세요.

## 현재 공개 상태

최종 목표는 이 저장소만으로 소스 준비·빌드·다운로드·설치·복구를 할 수 있는 완성된 배포본입니다. 현재 일부 검토된 소스와 실제 실행한 도구가 공개됐지만, 전체 빌드와 설치 가능한 최종 ROM은 아직 완성되지 않았습니다. 문서나 단위 테스트 통과만으로 최종본이라고 표시하지 않습니다.

라이선스를 확인한 공유 작업 트리의 패치 11개 프로젝트, 커밋 고정 upstream manifest 및 일부 HWC 소스를 고지사항과 함께 공개했습니다. 나머지 기기·커널·vendor 입력과 전체 빌드 연결은 진행 중입니다. [라이선스 검토 결과](docs/LICENSE-REVIEW.ko.md), [공개 HWC 소스](source/README.md)와 [소스 준비 절차](manifests/README.md)를 참조하세요.

[WebView 입력 다운로드·검증](docs/WEBVIEW-INPUT.md): 공식 서버에서 정확한 ARM 객체를 다운로드하고 크기·SHA256·APK 구조를 확인하는 도구를 제공합니다. Dangol에서는 `--abi arm`을 사용하며 Acer 검증 트리에 적용하지 마세요.

[다른 PC용 빌드·다운로드·플래싱 작업 현황](docs/PORTABLE-WORKFLOW.ko.md): boot 승인키 검사 도구와 Windows/Linux 단위 테스트를 추가했습니다. GitHub Actions도 이 도구만 검사하며 ROM을 빌드하거나 플래싱하지 않습니다.

개발 기기에서는 Android 9 부팅, 화면·터치 방향, 하단 내비게이션 및 Wi-Fi 관련 수정 작업을 수행했습니다. 이것이 다른 기기의 호환성이나 장시간 안정성을 보장하지는 않습니다.

진단용 boot에는 개발 PC의 ADB 공개키가 들어간 후보가 있어 그대로 공개하지 않습니다. 실기기에 적용한 후속 수정과 기존 system 이미지의 일치 여부도 배포 전에 정리해야 합니다.

## 배포 예정 구성

- 확인된 device tree와 프레임워크 패치
- 빌드 manifest, 원본 커밋 및 빌드 방법
- 커널 대응 소스 또는 정확한 소스 확보 방법과 변경분
- 한국어 설치·복구 안내, 체크섬, 알려진 문제
- 재배포 조건 확인 후 준비한 ROM을 GitHub Releases에 별도 제공

## 주의

현재 문서만으로 플래싱하지 마세요. 원본 복구 경로와 대상 기기의 파티션·부트로더 구성을 먼저 확인해야 합니다. 다른 기기의 전체 eMMC 백업이나 U-Boot 환경을 복사하지 마세요.

Android 9은 오래된 플랫폼입니다. 루트 권한·SELinux permissive 등 개발 설정은 일반 사용자 배포 전에 별도 검토가 필요합니다.

자세한 공개 전 조건은 [배포 체크리스트](docs/RELEASE-CHECKLIST.ko.md)를 참조하세요.
