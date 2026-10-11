# Exact WebView build input

The pinned Android 9 manifest uses Git LFS for WebView. A short `webview.apk` pointer is not a usable APK. This workflow downloads the exact manifest input from the official LineageOS LFS service and validates it; it does not bundle an APK in this repository or approve redistribution of the resulting ROM.

Use **arm for Dangol**. This is a 32-bit userspace input; do not choose a 64-bit input based only on the processor's capabilities.

## Download into a new directory

From this distribution repository clone, using Python 3:

```sh
python3 tools/fetch_webview.py --abi arm --output /private/webview-input
```

Choose one command for the target device. The output must not exist. The tool uses the official LineageOS LFS batch API, checks the returned object identity, accepts only HTTPS downloads, bounds the byte count, checks SHA256 and APK CRCs, and requires the expected native library. It creates `webview.apk` and a credential-free receipt in the new directory. It does not read local Git credentials or ADB keys, modify a source tree, contact a tablet, or install an application.

On failure inspect any new partial directory; do not merge it into an existing download. Official-server availability is external to this project. Do not substitute a random APK or bypass the hash check. You may use an already downloaded exact input instead of downloading again.

## Validate and materialize in the correct source tree

Use this device's Android source workspace:

```sh
python3 tools/materialize_webview.py --source /path/to/android9-source --abi arm --input /path/to/new-webview-download/webview.apk
# After successful read-only validation:
python3 tools/materialize_webview.py --source /path/to/android9-source --abi arm --input /path/to/new-webview-download/webview.apk --apply
```

The tool checks the pinned project revision and the exact input. It only replaces the expected LFS pointer atomically; unknown contents and symlinks are refused. An already materialized matching APK is left unchanged. This does not add or update any application on the tablet.

| ABI | Project revision | Bytes | SHA256 |
| --- | --- | ---: | --- |
| arm | `b2639126d02b401ae8a8a7f3ca302633713a12e6` | 90257078 | `b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11` |

## Evidence and limits

On 2026-10-11 the public downloader fetched and verified the arm object from the official service. The materializer was exercised in this device's verification workspace. This is not a claim of a complete source build or device installation. Synthetic tests cover dry-run, idempotence, unknown-file preservation, wrong hash/revision, existing-output refusal and avoiding temporary authorization headers in receipts.

This verifies a build input only, not a full Android build or release installation. Applicable upstream licenses and notices must still be preserved in the complete ROM. The tools report `redistribution_approved=false`.

Protocol reference: [Git LFS Batch API](https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md).
