# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **phone-control skill package** for the OpenClaw framework - an Android remote control skill that supports screen mirroring, touch control, and automated operations.

The project enables controlling Android devices via ADB (Android Debug Bridge) with features like:
- Device connection management (USB/WiFi ADB)
- Touch, swipe, input, and key press operations
- Screenshot and OCR-based text recognition
- Script-based automation sequences

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│ OpenClaw Skill  │────▶│  API Interface   │────▶│ Device Control│
└─────────────────┘     └──────────────────┘     └───────────────┘
      ▲                        ▲                        ▲
      │                        │                        │
  Skill Config            Business Logic          ADB/Scrcpy
```

### Core Modules

| Module | File | Purpose |
|--------|------|---------|
| Device Manager | `src/device_manager.py` | USB/LAN device scanning, connection management |
| ADB Client | `src/adb_client.py` | ADB command wrappers (tap, swipe, input, key) |
| Screen | `src/screen.py` | Screenshots, OCR, coordinate matching |
| Script Runner | `src/script_runner.py` | JSON script parsing and execution |
| Main API | `main.py` | FastAPI endpoints |

## Project Structure

```
phone-control-skill/
├── SKILL.md              # OpenClaw skill specification
├── manifest.json         # Skill metadata
├── main.py               # FastAPI entry point
├── src/
│   ├── adb_client.py     # ADB operations
│   ├── scrcpy_client.py  # Scrcpy screen mirroring
│   ├── device_manager.py # Device connection
│   ├── screen.py         # OCR and screen interaction
│   └── script_runner.py  # Script execution engine
├── requirements.txt      # Python dependencies
├── install.sh          # Setup script
└── docs/               # Development documents
```

## Dependencies

### System Dependencies
- `adb` - Android Debug Bridge
- `scrcpy` - Screen mirroring and control
- `tesseract-ocr` - OCR engine
- `ffmpeg` - Media processing

### Python Dependencies
- `fastapi` + `uvicorn` - Web framework
- `pure-python-adb` - ADB client library
- `opencv-python` - Image processing
- `pytesseract` - OCR Python bindings
- `pillow` - Image manipulation

## API Interface

Base prefix: `/api/phone-control/v1`

### Device Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/device/list` | List connected devices |
| POST | `/device/connect` | Connect to device |
| POST | `/device/disconnect` | Disconnect device |

### Control Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/control/click` | Tap at coordinates or text |
| POST | `/control/swipe` | Swipe gesture |
| POST | `/control/input` | Input text |
| POST | `/control/key` | Press system key |
| POST | `/control/app` | Start/stop app |

### Screen Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/screen/screenshot` | Capture screen |
| POST | `/script/run` | Execute script |

## Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1001 | Device not found |
| 1002 | Device connection failed |
| 1003 | Operation failed |
| 1004 | Target not found |
| 1005 | Permission denied |
| 2001 | Invalid parameters |
| 5000 | Internal error |

## Performance Requirements

- Command response latency: ≤500ms
- Screenshot capture time: ≤2s
- OCR accuracy: ≥90%
- Continuous operation stability: ≥24 hours

## Development References

Key documents in the repository:
- `可行性分析报告.md` - Feasibility analysis
- `技术方案.md` - Technical architecture
- `接口规范.md` - API specification
- `开发计划.md` - Development plan
- `测试用例.md` - Test cases

## Technology Stack

- **Language**: Python 3.10+
- **Web Framework**: FastAPI + Uvicorn
- **Android Control**: ADB + pure-python-adb
- **Screen Mirroring**: Scrcpy v2.0+
- **OCR**: Tesseract OCR 5.x
- **Image Processing**: OpenCV-Python
