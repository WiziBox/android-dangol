# 업로드 입력 검사

공개 저장소 루트에서 `python tools/check_publication_inputs.py`를 실행합니다.
Git 추적 파일의 알려진 바이너리·백업 경로, 개인키 PEM 헤더, Dangol 원본 백업
receipt 형식을 검사합니다. 의심 파일의 내용·경로를 출력하지 않습니다.
GitHub Actions에서도 실행하지만 push 이후 검사이므로 이미 업로드된 비밀을
막거나 삭제하지는 못합니다. 업로드 **전** 명시적인 파일 검토와 함께 실행하세요.

암호화·압축·인코딩된 임의 비밀, 모든 인증 토큰·개인 MAC, Git 과거 커밋 및 Release
첨부파일을 완전히 검사하지 않습니다. 검사 통과는 개인정보·라이선스 안전성의
보증이 아닙니다. ROM 공개 정책을 바꾸는 기능도 아닙니다.

`git add` 후 커밋 전에 `python tools/check_publication_inputs.py --staged`를 실행하세요.
이 옵션은 작업 폴더가 아닌 실제 Git index의 추가·수정된 blob을 읽습니다. 작업
폴더만 깨끗하게 바꿔도 index에 남은 개인키는 검출합니다. 삭제 파일은 제외하며
symlink·submodule·충돌 항목은 거부합니다. 검사 이후 index가 바뀌면 다시 검사해야
합니다. 기본 모드는 전체 현재 추적 파일 검사이므로 두 검사를 함께 사용하세요.
