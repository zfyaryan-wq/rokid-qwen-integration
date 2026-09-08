# glass3sdkdemo

#### 介绍
Glass3 眼镜端和手机端 Demo 示例项目。

#### 文档地址
https://x-docs.rokid.com/docs/

## Qwen Omni × Glass3 POC

本分支在官方 `2.2.0-E` Demo 上增加了端到端实时对话：

1. Glass3 将 16 kHz 单声道 PCM 和 NV21 视频流传到手机。
2. 手机使用低权限设备注册口令登录华为云后端，获得短期 JWT。
3. 手机通过后端 WebSocket 代理发送 PCM 和每秒一张 JPEG；百炼长期 API Key
   只保存在 ECS。
4. Qwen 返回 16 kHz PCM，手机通过 Rokid 经典蓝牙音频流回传眼镜播放。

### 配置

先按 [`deploy/README.md`](deploy/README.md) 部署 FastAPI、PostgreSQL、
Nginx 和 WireGuard。Android debug 包通过 VPN 访问后端：

```powershell
$env:OMNI_BACKEND_BASE_URL="http://10.8.0.1"
$env:OMNI_DEVICE_ENROLLMENT_TOKEN="与后端相同的设备注册口令"
cd .\glass3sdkphonedemo
.\gradlew.bat assembleDebug
```

也可以在用户级 `~/.gradle/gradle.properties` 中配置：

```properties
omni.backendBaseUrl=http://10.8.0.1
omni.deviceEnrollmentToken=与后端相同的设备注册口令
```

仓库结构：

- `backend/`：设备鉴权、Qwen Realtime WebSocket 代理、OBS 预签名上传。
- `deploy/`：Docker Compose、Nginx、WireGuard 和 systemd。
- `glass3sdkphonedemo/`：Android 手机端。
- `glassdemo/`：Glass3 眼镜端。

### 运行

1. 分别安装并启动 `glassdemo` 和 `glass3sdkphonedemo`。
2. 手机连接 Glass3 的蓝牙和 Wi-Fi P2P。
3. 眼镜端进入“消息接收”页面，使其接收并播放手机发送的 PCM。
4. 手机端进入“获取音视频流”，打开“Qwen Omni 实时对话”。
5. 保持自动选择的 `NV21 / 640 × 480`，点击“开始预览”后直接说话。

预览页左上角会显示连接状态、用户转写和 Qwen 回复文本。

### 当前边界

- 首版为半双工：AI 回复期间暂停上传眼镜麦克风，防止扬声器回声再次触发模型。
- 当前设备注册口令适用于受控 POC；正式运营应改为每台设备独立凭证和吊销机制。
- 真正的全双工打断、AEC/NS 和弱网优化建议改用 AOQ Client SDK 后实机验收。
- 图片按 1 fps 上传且限制在 256 KiB 内；完整 15–30 fps 视频应走独立数据采集链路。
