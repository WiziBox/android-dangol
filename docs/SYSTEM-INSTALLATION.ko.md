# recovery ADB의 system 전송 도구 — 실기 미검증

`flash_system.py`는 Dangol의 작은 cache에 이미지를 저장하지 않고 PC의 완전한
2GiB raw system 파일을 recovery ADB stdin으로 직접 전송하는 구현입니다.
**합성 테스트만 완료했고 실제 recovery의 exec-in·기록·복원은 확인하지 않았습니다.**
현재 완성된 일반 사용자 설치 절차로 권장하지 않습니다. 현장 복구 가능 여부와
recovery 호환성을 먼저 확인해야 하며 이 도구만으로 boot·환경·공장 복원을 해결하지
못합니다. 제조사 파일을 포함한 이미지의 공개 권한과도 별개입니다.

## 사전 조건과 dry-run

- 자기 기기에 `backup_device.py`로 만든 6개 호스트 백업, backup-receipt와
  일련번호가 연결된 owner-device-record가 있어야 합니다. 다른 기기의 기록을
  수정해서 사용하지 마세요. receipt는 서명 인증이 아니므로 자기 원본을 신뢰해야
  합니다. 예전 수동 백업만 있으면 기록을 임의로 만들어 우회하지 마세요.
- 지원 대상 기기의 root ADB가 이미 실행되어야 합니다. recovery 속성과
  `/tmp/recovery.log`가 있어야 하고 system은 **모든 마운트 별칭에서도** 미마운트
  상태여야 합니다. 도구는 recovery 진입·root 전환·unmount를 하지 않습니다.
- 기기 속성·fstab·sysfs 경계·system major/minor와 정규 블록 경로를 검사합니다.
  외국 파티션 표·부트로더를 쓰지 않습니다.
- 호스트 입력은 sparse가 아닌 완전한 raw 이미지이며 예상 SHA-256을 지정합니다.
  [raw 변환과 system 검사](SYSTEM-IMAGE-CHECK.ko.md)를 별도로 완료하세요.

```sh
python3 tools/flash_system.py --adb /path/to/adb --serial YOUR_SERIAL --image /private/system.raw.img --sha256 YOUR_RAW_SHA256 --owner-backup-dir /private/your-device-backup
```

이 명령은 dry-run이며 기기에 기록하지 않습니다. 실제 기록을 선택하려면
`--apply`가 필요하고 이때 **기존 system 전체가 덮어써집니다**. 기록 직전 대상과
입력 체크섬을 다시 검사합니다. 고정된 `/dev/block/mmcblk0p3`에만 exec-in dd로
전송하고 sync 후 기기 파티션의 전체 SHA-256을 읽어 호스트 입력과 비교합니다.
boot·recovery·환경·userdata에는 기록하지 않고 erase·format·재부팅을 하지 않습니다.

도구의 오류 응답은 기록 전 거부와 기록 도중 실패를 모두 포함하므로 오류가 나면
system이 부분 기록됐을 수 있습니다. 자동 재시도하거나 재부팅하지 마세요. recovery
연결을 유지하고 현장에서 자기 백업 복원 경로를 확인해야 합니다. 전송과 검사 사이
다른 root 작업을 완전히 차단하는 원자적 동작은 아니며 전원 손실에 안전한 갱신도
아닙니다. 파일·backup receipt는 공개하지 마세요.

복원에도 자기 system 원본을 입력할 수 있지만 그 경로 역시 실기 미검증입니다.
boot와 저장된 U-Boot 읽기 길이의 호환성을 별도로 확인하지 않으면 system만
기록해도 부팅되지 않을 수 있습니다. 정상 부팅·사용자 데이터 호환성·콜드 부팅은
이 도구가 증명하지 않습니다.
