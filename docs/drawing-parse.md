# Drawing Parse

## 목적

`data/raw`에 내려받은 도면 파일을 `data/parsed` 아래의 표준 JSON으로 변환합니다.

지원 상태:

- SVG: 텍스트 추출
- PDF: 페이지별 텍스트 블록 추출
- DXF: modelspace 텍스트, 엔티티 타입, 레이어, bbox 후보 추출
- DWG: 원본 인식 후 `conversion_required` 상태로 기록

## 실행

```powershell
drawing-mapper parse-drawings --config config/project.json
```

결과:

```text
data/parsed/
data/parsed/parse-manifest.json
```

각 원본 파일별 JSON이 생성되고, 전체 결과는 `parse-manifest.json`에 모입니다.

## DWG 처리

DWG는 폐쇄 포맷이라 Python 파서만으로 안정적으로 읽기 어렵습니다.
따라서 현재 파이프라인은 DWG를 아래처럼 기록합니다.

```json
{
  "source_format": "dwg",
  "status": "conversion_required",
  "message": "DWG must be converted to DXF, PDF, or SVG before geometry parsing."
}
```

추천 변환 흐름:

```text
DWG
-> DXF 변환
-> drawing-mapper parse-drawings
-> ParsedDrawing JSON
```

변환기는 아래 중 하나를 붙이는 방식이 현실적입니다.

- ODA File Converter
- Autodesk Platform Services
- AutoCAD batch export

MVP에서는 변환된 DXF를 `data/raw`의 같은 폴더 구조에 넣고 `parse-drawings`를 다시 실행하면 됩니다.
