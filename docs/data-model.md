# Data Model

## Building

```json
{
  "id": "building_001",
  "name": "Sample Site",
  "address": "서울특별시 ...",
  "latitude": 37.0,
  "longitude": 127.0
}
```

## DrawingFile

```json
{
  "id": "drawing_file_001",
  "building_id": "building_001",
  "drive_file_id": "google_drive_file_id",
  "name": "mechanical_floor_1_6.pdf",
  "mime_type": "application/pdf",
  "source_path": "raw/mechanical_floor_1_6.pdf",
  "status": "downloaded"
}
```

## ParsedDrawingJson

```json
{
  "drawing_file_id": "drawing_file_001",
  "pages": [
    {
      "page_number": 1,
      "width": 841.89,
      "height": 595.28,
      "unit": "pt",
      "floor_hint": "1F",
      "texts": [],
      "paths": [],
      "symbols": []
    }
  ]
}
```

## Floor

```json
{
  "id": "floor_001",
  "building_id": "building_001",
  "label": "1F",
  "level": 1,
  "drawing_page_id": "drawing_page_001"
}
```

## Equipment

```json
{
  "id": "equipment_001",
  "building_id": "building_001",
  "type": "pump",
  "name": "PUMP-01",
  "description": "Basement water pump"
}
```

## EquipmentLocation

```json
{
  "id": "equipment_location_001",
  "equipment_id": "equipment_001",
  "floor_id": "floor_001",
  "drawing_x": 324.5,
  "drawing_y": 128.2,
  "latitude": 37.0,
  "longitude": 127.0,
  "confidence": 0.82,
  "source": "parser_candidate"
}
```

## CoordinateCalibration

```json
{
  "id": "calibration_001",
  "floor_id": "floor_001",
  "method": "affine",
  "points": [
    {
      "drawing_x": 100.0,
      "drawing_y": 200.0,
      "latitude": 37.0,
      "longitude": 127.0
    }
  ],
  "transform": {
    "matrix": [1, 0, 0, 0, 1, 0]
  }
}
```

