# Google Drive Sync

## 인증 방식

초기 구현은 서비스 계정 JSON을 사용합니다.
현장 자동 수집에는 사람이 매번 로그인하는 OAuth보다 서비스 계정이 더 단순합니다.

## 준비

1. Google Cloud Console에서 프로젝트를 만듭니다.
2. Google Drive API를 활성화합니다.
3. 서비스 계정을 만들고 JSON key를 내려받습니다.
4. JSON key를 `secrets/google-service-account.json`에 둡니다.
5. Google Drive의 도면 폴더를 서비스 계정 이메일에 공유합니다.
6. `config/project.example.json`을 `config/project.json`으로 복사한 뒤 값을 채웁니다.

## 설정 예시

```json
{
  "google_drive": {
    "folder_id": "google-drive-folder-id",
    "service_account_file": "secrets/google-service-account.json",
    "include_shared_drives": true,
    "recursive": true,
    "preserve_drive_paths": true,
    "allowed_mime_types": [
      "application/pdf",
      "image/svg+xml",
      "application/acad",
      "application/autocad",
      "application/dwg",
      "application/x-dwg",
      "image/vnd.dwg"
    ],
    "allowed_extensions": [
      ".pdf",
      ".svg",
      ".dwg",
      ".dxf"
    ]
  },
  "building": {
    "name": "현장명",
    "address": "현주소",
    "floors": [1, 2, 3, 4, 5, 6]
  },
  "storage": {
    "raw_dir": "data/raw",
    "parsed_dir": "data/parsed",
    "metadata_dir": "data/metadata"
  }
}
```

## 실행

의존성 설치:

```powershell
pip install -e ".[google]"
```

Drive 동기화:

```powershell
drawing-mapper sync-drive --config config/project.json
```

복잡한 Drive 구조에서는 먼저 작은 범위로 테스트합니다.

```powershell
drawing-mapper sync-drive --config config/project.json --max-files 10 --list-only
drawing-mapper sync-drive --config config/project.json --max-files 10
```

Drive 루트에 계약서, 견적서, 안전문서 PDF가 섞여 있으면 `config/project.json`의
`allowed_extensions`를 `.dwg`만 두는 편이 좋습니다.

결과:

- 원본 도면: `data/raw`
- Drive 파일 메타데이터: `data/metadata/drive-files.json`

원본 도면은 같은 파일명이 있어도 덮어쓰지 않도록
`{drive_file_id}_{original_name}` 형식으로 저장됩니다.
`preserve_drive_paths`가 `true`이면 Drive의 하위 폴더 구조도 `data/raw` 아래에 같이 보존됩니다.

예:

```text
Drive/기계/1F/A-001.dwg
-> data/raw/기계/1F/{drive_file_id}_A-001.dwg
```

## 로컬 테스트

Google 인증을 붙이기 전에도 로컬 폴더를 Drive처럼 사용해 동기화 흐름을 테스트할 수 있습니다.

```powershell
drawing-mapper sync-drive --config config/project.example.json --local-fixture-dir samples/drive
```

## 주의

- 서비스 계정 이메일이 Drive 폴더에 공유되어 있어야 파일 목록이 보입니다.
- Shared Drive를 쓰는 경우 `include_shared_drives`를 `true`로 둡니다.
- `secrets/`와 `data/raw/`는 `.gitignore`에 포함되어 있습니다.
- DWG 파일은 Drive MIME 타입이 일정하지 않을 수 있어 `allowed_extensions` 필터를 함께 씁니다.
- 폴더 구조가 복잡하면 `recursive`를 `true`로 둡니다. 기본 추천값입니다.

## DWG 처리 방향

Drive 동기화 단계에서는 DWG 원본을 그대로 내려받습니다.
파싱 단계에서는 아래 중 하나로 진행하는 것이 좋습니다.

1. DWG를 DXF로 변환한 뒤 `ezdxf`로 파싱
2. DWG를 PDF/SVG로 export한 뒤 현재 PDF/SVG 파서로 처리
3. AutoCAD, ODA File Converter, Autodesk Platform Services 같은 외부 변환기를 별도 worker로 연결

초기 MVP에서는 원본 DWG를 보관하고, 변환 산출물인 DXF/PDF/SVG를 `data/parsed`에 연결하는 방식이 가장 현실적입니다.
