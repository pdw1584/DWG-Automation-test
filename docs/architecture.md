# Architecture

## Components

### Drive Sync

Google Drive API를 사용해 지정 폴더의 파일을 동기화합니다.

Responsibilities:

- 폴더 내 파일 목록 조회
- 변경된 파일 감지
- 원본 파일 다운로드
- 파일 ID, revision, mime type, checksum 저장

### Drawing Parser

도면 파일을 표준 JSON으로 변환합니다.

Supported inputs:

- PDF
- SVG
- DXF
- image-based PDF or image files, later via OCR

Parser output:

- pages
- text blocks
- vector paths
- symbols
- layers
- bounding boxes
- scale hints
- floor hints

### Geocoding

현장 주소를 위도/경도로 변환합니다.

The first implementation can use a provider adapter interface so Google,
Naver, or Kakao geocoding can be swapped later.

### Coordinate Calibration

도면 좌표를 실제 좌표로 변환하려면 기준점이 필요합니다.
초기에는 사람이 도면 기준점 2~3개를 찍고, 해당 실제 GPS 좌표를 입력하는 방식이 가장 안정적입니다.

Calibration inputs:

- drawing point: `x`, `y`
- geo point: `lat`, `lng`
- floor

Calibration output:

- affine transform or homography
- confidence
- unit scale

### Equipment Extraction

초기에는 규칙 기반으로 시작합니다.

Examples:

- 텍스트 라벨: `AHU`, `FCU`, `PUMP`, `MCC`, `EPS`, `TPS`
- 심볼 주변 텍스트
- 레이어명
- 블록명, if DXF is available

후속 단계에서 ML/OCR 모델을 붙일 수 있도록 후보와 확정 데이터를 분리합니다.

## Data Flow

```text
DriveFile
  -> RawDrawing
  -> ParsedDrawingJson
  -> FloorDrawing
  -> EquipmentCandidate
  -> VerifiedEquipmentLocation
```

## API Draft

```http
POST /buildings
GET /buildings/{building_id}

POST /drive/sync
GET /drawings
GET /drawings/{drawing_id}

POST /drawings/{drawing_id}/parse
GET /drawings/{drawing_id}/parsed-json

POST /buildings/{building_id}/geocode
POST /floors/{floor_id}/calibration-points
GET /floors/{floor_id}/equipment
```

