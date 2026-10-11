# 자기 기기의 읽기 전용 ADB 백업

`backup_device.py`는 새 PC의 비공개 폴더로 6개 파티션과 파티션 앞 영역을 직접 읽는 도구입니다.
Python 3와 ADB가 필요하고 기기에는 기존 root ADB·지원되는 sysfs/fstab 및
`sha256sum`, `dd` 명령이 있어야 합니다. root 활성화·재부팅·마운트 변경·기기
기록은 하지 않습니다. system 등 대상 파티션이 rw로 마운트되어 있으면 거부합니다.

```sh
python3 tools/backup_device.py --adb /path/to/adb --serial YOUR_SERIAL --output /private/new-dangol-backup
```

기본값은 읽기 전용 사전 검사이며 새 파일을 만들지 않습니다. 검사 통과 후
`--apply`를 추가하면 각 파티션을 `adb exec-out dd if=...`로 읽어 PC에 저장합니다.
PowerShell의 바이너리 `>` 리다이렉션을 사용하지 않습니다. 출력 폴더는 존재하면
안 되고 부모 비공개 폴더는 미리 준비해야 합니다. 저장소 밖에 저장하세요.
Linux 폴더 0700·파일 0600 설정은 Windows ACL을 대신하지 않습니다.

지원 기기 속성·파티션 경계·크기를 검사하고 major/minor도 확인합니다. 각 파티션의
기기 SHA-256을 읽기 전후에 비교하고 PC 파일의 전체 크기·SHA-256과 대조합니다.
마지막으로 모든 PC 파일을 다시 검사합니다. 실패하면 자동 재시도·재부팅·부분
출력 삭제를 하지 않습니다. 완료 receipt가 없거나 오류 출력이면 복구 세트로
사용하지 마세요. 성공해도 동시 root 변경을 완전히 차단하는 원자적 스냅샷은
아닙니다. 원본 기기의 앱을 종료하고 파일시스템 상태를 안정시켜 사용해야 합니다.

성공 시 `backup-receipt.json`과 자기 일련번호가 포함된 `owner-device-record.json`을
새 폴더에 저장합니다. 파일·receipt·일련번호 기록은 모두 **업로드 금지**입니다.
화면 출력은 성공 분류만 표시하며 백업 내용·키·일련번호·체크섬을 표시하지 않습니다.

```sh
python3 tools/verify_backup.py --backup-dir /private/new-dangol-backup --verify-private-receipt /private/new-dangol-backup/backup-receipt.json
```

백업 범위는 boot/p2/system/p5/recovery/misc 및 사용자 eMMC 앞 4,915,200바이트입니다.
사전 점검의 실제 p1 시작 섹터가 9,600인지 확인한 뒤 해당 앞 영역만 읽습니다.
새 비공개 `dangol-preboot.bin`에 저장하고 전후 기기 해시·호스트 크기/해시 및
전체 파티션 백업 이후 해시를 확인합니다. `owner-device-record.json`의 preboot
항목에 지문을 저장하지만 기존 6개 파일용 receipt의 형식은 바꾸지 않습니다.
`verify_backup.py`는 여전히 6개 파티션만 검사하고 preboot는 별도입니다.

이 앞 영역에는 부트로더·파티션 표·U-Boot 환경·고유 정보가 포함될 수 있으므로
절대 공개하거나 다른 기기에 복사하지 마세요. 환경 위치·CRC·명령과 복원 방법을
검증한 것은 아니며 whole-disk raw 기록 명령은 제공하지 않습니다. userdata·cache·
별도 mmcblk0boot0/boot1·RPMB는 포함하지 않습니다. 현재 기기에 수정 ROM이 설치되어
있으면 그 상태의 백업이며 공장 원본이 아닙니다. 기존 순정 백업은 별도로 보존하세요.
이 백업은 완전한 공장 복원 세트나 검증된 실기 복구 성공을 뜻하지 않습니다.

구현은 합성 ADB 응답과 작은 호스트 파일로 테스트했습니다. 실제 연결 기기의
전체 백업·ADB exec-out 호환성은 아직 확인하지 않았습니다. 실제 환경에서 거부되면
검사를 끄지 말고 지원 여부를 먼저 확인해야 합니다.
