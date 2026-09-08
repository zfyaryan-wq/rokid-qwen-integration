# glass3sdkdemo

#### 介绍
Glass3 眼镜端和手机端 Demo 示例项目。

#### 文档地址
https://x-docs.rokid.com/docs/

## Qwen Omni × Glass3 POC

本分支在官方 `2.2.0-E` Demo 上增加了端到端实时对话：

1. Glass3 将 16 kHz 单声道 PCM 和 NV21 视频流传到手机。
2. 手机每秒把一张 NV21 帧压成 JPEG，并与 PCM 一起发送到
   `qwen3.5-omni-flash-realtime`。
3. Qwen 返回 16 kHz PCM，手机通过 Rokid 经典蓝牙音频流回传眼镜播放。

### 配置

API Key 仅供本地设备 POC 使用，不要提交到仓库。PowerShell 中执行：

```powershell
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
$env:DASHSCOPE_WORKSPACE_ID="你的百炼业务空间 ID"
cd .\glass3sdkphonedemo
.\gradlew.bat assembleDebug
```

也可以在用户级 `~/.gradle/gradle.properties` 中配置：

```properties
qwen.apiKey=你的百炼APIKey
qwen.workspaceId=你的业务空间ID
qwen.endpointHost=cn-beijing.maas.aliyuncs.com
qwen.model=qwen3.5-omni-flash-realtime
```

### 运行

1. 分别安装并启动 `glassdemo` 和 `glass3sdkphonedemo`。
2. 手机连接 Glass3 的蓝牙和 Wi-Fi P2P。
3. 眼镜端进入“消息接收”页面，使其接收并播放手机发送的 PCM。
4. 手机端进入“获取音视频流”，打开“Qwen Omni 实时对话”。
5. 保持自动选择的 `NV21 / 640 × 480`，点击“开始预览”后直接说话。

预览页左上角会显示连接状态、用户转写和 Qwen 回复文本。

### 当前边界

- 首版为半双工：AI 回复期间暂停上传眼镜麦克风，防止扬声器回声再次触发模型。
- 生产版不能把长期 API Key 放进 APK；需要业务后端签发短期连接凭证。
- 真正的全双工打断、AEC/NS 和弱网优化建议改用 AOQ Client SDK 后实机验收。
- 图片按 1 fps 上传且限制在 256 KiB 内；完整 15–30 fps 视频应走独立数据采集链路。
