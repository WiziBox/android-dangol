# 재빌드 없이 소유자 전용 이미지 만들기

Linux/WSL, Python 3.9 이상, `debugfs`, `e2fsck`가 필요합니다. 호스트 파일만
만드는 단계이며 다운로드·플래싱 도구가 아닙니다. 현재 비공개 후보를 공개
최종 ROM으로 승인한 것은 아닙니다.

검토한 raw system 이미지의 보정 파일 위치가 비어 있어야 합니다.
[원본 입력 추출](VENDOR-INPUTS.ko.md)로 확보한 **이 기기의** 보정 파일만
사용하세요. 오프라인 프로필 검사는 파일 소유자나 기기 식별을 증명하지 않습니다.

```sh
python3 tools/compose_owner_image.py \
  --device dangol \
  --input /path/to/private/reviewed-base.raw.img \
  --base-sha256 YOUR_BASE_RAW_SHA256 \
  --calibration /path/to/private/stock-inputs/vendor/firmware/nvram_ap6212.txt \
  --output /path/to/private/new-owner-system.raw.img
```

기본 실행은 검사만 합니다. 통과 후 같은 명령에 `--apply --confirm-owner-input`
두 옵션을 붙이면 저장소 밖의 **새** 비공개 파일을 생성합니다. 원본이나 기존
출력은 덮어쓰지 않습니다. 실패하면 새 부분 파일을 보존하며 자동 재시도·삭제를
하지 않습니다.

전체 원본 이미지 체크섬, raw ext4 형식·2GiB 크기와 읽기 전용 파일시스템 검사를
확인합니다. 실제 firmware 디렉터리가 있어야 하며 보정 파일이 이미 있으면
중단합니다. ASCII·필수 보드 필드·MAC 형식을 확인하고 네트워크 이름·암호나
인증키가 섞인 입력은 거부합니다. RF·국가·MAC 값을 고치지 않고 보정 바이트를
그대로 `/vendor/firmware/nvram_ap6212.txt`에 넣습니다. root 소유권·0644 권한·
`u:object_r:vendor_file:s0` 레이블을 적용하고 내용·권한·레이블을 다시 읽습니다.

성공 출력에는 비공개 **전체 이미지** 체크섬만 있으며 보정 파일의 내용·MAC·
개별 해시는 없습니다. 보정값이 들어간 결과와 입력 파일·보고서는 GitHub에
올리지 마세요. 나머지 파일의 인증정보·재배포 권한이나 커널/모듈 짝을 이 도구가
검증하지 않습니다. 실기 부팅·플래싱·완전한 복구도 별도 조건입니다.

2026-10-11 두 비공개 후보에서 실제 호스트 조합과 보정값·권한·레이블 읽기 및
파일시스템 검사가 통과했습니다. 합성 테스트 9개도 추가했습니다. 같은 도구의
Acer 프로필은 Dangol에 사용하지 마세요. 이 명령은 기기 기록을 승인하지 않습니다.
