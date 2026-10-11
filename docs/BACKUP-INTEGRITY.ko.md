# 비공개 원본 백업 이동·무결성 확인

기기에서 새 백업을 읽는 별도 도구는 [읽기 전용 ADB 백업](DEVICE-BACKUP.ko.md)을 참조하세요. 이 문서의 `verify_backup.py`는 기존 호스트 파일 검사만 합니다.

Python 3 표준 라이브러리만 필요합니다. 기기를 연결하거나 기록하지 않습니다.
원본 백업을 보존하고 다른 PC로 복사할 때 사용하는 도구이며, 백업 생성·실기
복구·대상 기기 식별을 수행하지 않습니다.

검사 대상은 개발 기기에서 확인한 파티션 크기에 한정합니다.

| 파일 | 원본 파티션 | 바이트 |
| --- | --- | ---: |
| dangol-boot.img | mmcblk0p1 | 62914560 |
| dangol-p2.img | mmcblk0p2 | 3145728 |
| dangol-system.img | mmcblk0p3 | 2147483648 |
| dangol-p5.img | mmcblk0p5 | 67108864 |
| dangol-recovery.img | mmcblk0p7 | 67108864 |
| dangol-misc.img | mmcblk0p8 | 1048576 |

기존 5개 백업만 있다면 system 백업이 빠져 있어 검사에 실패합니다. 빈 파일로
대체하지 마세요. p2와 p5의 역할은 확정되지 않았으며 파일명에 역할을 추측해서
붙이지 않습니다. userdata·cache·전체 디스크 파티션 테이블·eMMC boot 영역 및
U-Boot 환경이 포함된 완전한 복구 세트라고 주장하지 않습니다.

원본 PC에서 이미 확보한 백업으로 최초 기록을 만듭니다. 저장소 밖의 비공개
폴더를 사용하세요. Windows에서는 `python3` 대신 `python`을 사용할 수 있습니다.

```sh
python3 tools/verify_backup.py --backup-dir /private/dangol-backup --create-private-receipt /private/dangol-backup-receipt.json
```

백업과 receipt를 다른 PC에 복사한 뒤 검사합니다.

```sh
python3 tools/verify_backup.py --backup-dir /private/dangol-backup --verify-private-receipt /private/dangol-backup-receipt.json
```

출력은 파일 개수와 성공 여부만 표시합니다. receipt에는 전체 파티션 SHA-256이
포함되어 있으므로 백업과 함께 **공개 업로드하지 마세요**. 기존 receipt를
덮어쓰지 않습니다. Linux에서는 새 receipt 권한을 0600으로 설정하지만 Windows
ACL을 대신하지 않으므로 Windows에서도 비공개 폴더 권한을 유지해야 합니다.

최초 기록은 현재 파일을 기준으로 만들 뿐 정상 원본인지 증명하지 않습니다.
이후 비교는 이동 중 손상을 찾는 검사이지 서명 인증이나 복구 가능성 검증이
아닙니다. 같은 이름·크기여도 다른 기기의 백업을 복원해서는 안 됩니다.
