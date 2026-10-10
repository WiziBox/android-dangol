# Pinned upstream source preparation (not a complete ROM build)

`upstream.xml` is generated from the development tree's `repo manifest -r` output. All 709 project revisions are commit hashes. GitHub and AOSP fetch roots are absolute public HTTPS URLs. An unused private SSH remote and upstream pre-upload hooks were removed. This manifest does not contain local device/vendor folders outside the upstream project graph.

It is configuration data, not a redistribution of those projects' source contents. Each fetched project retains its own license and copyright. The exported project commits describe the upstream baseline, not the uncommitted port changes.

## Prepare a new workspace

Use Linux or WSL with the Android `repo` tool, Git, Git LFS and required build packages installed. Do not reuse an unrelated dirty source tree. Full syncing is large and does not yet yield a buildable port; device/vendor sources and boot packaging are still being prepared.

```sh
mkdir android9-source
cd android9-source
repo init -u https://github.com/WiziBox/android-dangol.git -b main -m manifests/upstream.xml
repo sync -j4
```

The source commits are fixed, but the distribution tooling on `main` can change. Record the distribution repository commit for reproducibility; future releases will pin this as well.

WebView prebuilt projects use Git LFS. A successful sync that leaves `webview.apk` as a short LFS pointer is not a valid build input. Exact object materialization and hash checks remain part of the build preparation work.

## Check/apply port changes

From your clone of this distribution repository, with the freshly synced source directory:

```sh
python3 tools/apply_patches.py --source /absolute/path/to/android9-source
# Review the successful dry-run, then explicitly apply:
python3 tools/apply_patches.py --source /absolute/path/to/android9-source --apply
```

The tool checks all eleven project's base commits, patch hashes, clean status and applicability before modifying any project. It does not reset/delete existing changes. An unexpected application failure may leave earlier projects applied; the report lists them and stops without an automatic reset. This is source preparation only, not a full ROM build or flashing command.
