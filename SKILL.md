# 手机控制技能 (Phone Control Skill)

通过ADB远程控制安卓手机，支持设备管理、触控操作、屏幕截图、OCR识别和自动化脚本执行。

## 功能特性

- **设备管理**: 自动发现USB/网络ADB设备，支持多设备并发管理
- **基础控制**: 点击、滑动、输入文字、系统按键(返回/主页/电源等)
- **应用管理**: 启动/停止应用，获取已安装应用列表
- **屏幕交互**: 截图、OCR文字识别、按文字点击
- **自动化脚本**: JSON格式操作脚本，支持延时和条件判断

## 安装要求

### 系统依赖

- **ADB**: Android Debug Bridge (`adb`)
- **Scrcpy**: 屏幕镜像和控制工具 (`scrcpy`)
- **Tesseract OCR**: 光学字符识别引擎 (`tesseract`)
- **FFmpeg**: 多媒体处理工具 (`ffmpeg`)

#### macOS
```bash
brew install android-platform-tools scrcpy tesseract ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y adb scrcpy tesseract-ocr ffmpeg
```

#### Windows
1. 下载 [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools) 并解压到PATH
2. 下载 [Scrcpy](https://github.com/Genymobile/scrcpy/releases) 并解压到PATH
3. 安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) 并添加到PATH
4. 下载 [FFmpeg](https://ffmpeg.org/download.html) 并添加到PATH

### Python依赖

```bash
pip install -r requirements.txt
```

或自动安装:
```bash
bash install.sh
```

## 使用方法

### 1. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 2. 连接设备

确保手机开启开发者模式和ADB调试:

```bash
# 查看已连接设备
adb devices

# 连接网络设备
adb connect 192.168.1.100:5555
```

### 3. API调用示例

#### 获取设备列表
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/device/list
```

#### 点击操作
```bash
# 坐标点击
curl -X POST http://localhost:8080/api/phone-control/v1/control/click \
  -H "Content-Type: application/json" \
  -d '{"device_id": "192.168.1.100:5555", "target": "500,1000"}'

# 文字点击(通过OCR)
curl -X POST http://localhost:8080/api/phone-control/v1/control/click \
  -H "Content-Type: application/json" \
  -d '{"device_id": "192.168.1.100:5555", "target": "设置"}'
```

#### 滑动操作
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/control/swipe \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "192.168.1.100:5555",
    "start": "100,2000",
    "end": "100,500",
    "duration": 500
  }'
```

#### 输入文字
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/control/input \
  -H "Content-Type: application/json" \
  -d '{"device_id": "192.168.1.100:5555", "text": "Hello World"}'
```

#### 系统按键
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/control/key \
  -H "Content-Type: application/json" \
  -d '{"device_id": "192.168.1.100:5555", "key": "home"}'
```
支持按键: `back`, `home`, `power`, `volume_up`, `volume_down`, `menu`

#### 应用管理
```bash
# 启动应用
curl -X POST http://localhost:8080/api/phone-control/v1/control/app \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "192.168.1.100:5555",
    "action": "start",
    "package": "com.tencent.mm"
  }'

# 停止应用
curl -X POST http://localhost:8080/api/phone-control/v1/control/app \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "192.168.1.100:5555",
    "action": "stop",
    "package": "com.tencent.mm"
  }'
```

#### 屏幕截图
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/screen/screenshot \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "192.168.1.100:5555",
    "save_path": "/tmp/screenshot.png"
  }'
```

#### 执行脚本
```bash
curl -X POST http://localhost:8080/api/phone-control/v1/script/run \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "192.168.1.100:5555",
    "script": [
      {"action": "key", "params": {"key": "home"}},
      {"action": "click", "params": {"target": "500,1000"}},
      {"action": "sleep", "params": {"seconds": 2}},
      {"action": "swipe", "params": {"start": "100,2000", "end": "100,500"}}
    ]
  }'
```

## 错误码说明

| 错误码 | 含义 | 说明 |
|--------|------|------|
| 0 | 成功 | 操作正常完成 |
| 1001 | 设备未找到 | 指定设备不存在或未连接 |
| 1002 | 设备连接失败 | 检查ADB权限、网络连接 |
| 1003 | 操作执行失败 | 指令执行失败，检查参数或设备状态 |
| 1004 | 目标未找到 | 点击的文字未在屏幕识别到 |
| 1005 | 权限不足 | 缺少设备调试授权 |
| 2001 | 参数错误 | 请求参数缺失或格式错误 |
| 5000 | 系统内部错误 | 服务异常，查看日志 |

## 性能指标

- **指令响应延迟**: ≤500ms
- **截屏耗时**: ≤2s
- **OCR识别准确率**: ≥90%
- **连续运行稳定性**: ≥24小时无崩溃

## 常见问题

### Q: 设备连接失败怎么办？
A: 检查以下几点:
1. 手机是否开启开发者模式和USB调试
2. 使用`adb devices`确认设备被识别
3. 网络设备需要先用`adb connect IP:5555`连接
4. 检查防火墙设置

### Q: OCR识别准确率低怎么办？
A: 可以尝试:
1. 调整截图质量参数
2. 安装Tesseract中文语言包
3. 确保屏幕亮度适中，文字清晰可见
4. 在配置中设置合适的OCR识别语言

### Q: 如何查看详细日志？
A: 启动服务时添加日志级别参数:
```bash
uvicorn main:app --log-level debug --reload
```

## License

Apache 2.0 License

## 相关文档

- [可行性分析报告](docs/可行性分析报告.md)
- [技术方案](docs/技术方案.md)
- [接口规范](docs/接口规范.md)
- [开发计划](docs/开发计划.md)
- [测试用例](docs/测试用例.md)
