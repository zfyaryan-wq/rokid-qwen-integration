package com.rokid.phone.qwen

import android.util.Base64
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Qwen3.5 Omni Realtime 的轻量 WebSocket 客户端。
 *
 * Glass3 输入和模型输出都配置为 16 kHz / mono / PCM16，避免在手机端重采样，
 * 并可将模型音频直接交给 Rokid 的经典蓝牙音频流。
 */
class QwenRealtimeClient(
    private val config: Config,
    private val listener: Listener,
) {
    data class Config(
        val accessToken: String,
        val realtimeWsUrl: String,
        val voice: String = "Tina",
        val instructions: String =
            "你是佩戴在第一视角智能眼镜上的中文助手。结合用户语音和最新画面，简短、准确地回答；" +
                "看不清或不确定时直接说明，不要编造。",
    ) {
        val isComplete: Boolean
            get() = accessToken.isNotBlank() &&
                (realtimeWsUrl.startsWith("ws://") || realtimeWsUrl.startsWith("wss://"))
    }

    enum class State {
        DISCONNECTED,
        CONNECTING,
        READY,
        RESPONDING,
    }

    interface Listener {
        fun onStateChanged(state: State)
        fun onInputTranscript(text: String)
        fun onOutputTranscriptDelta(text: String)
        fun onAudioDelta(pcm16: ByteArray)
        fun onError(message: String)
    }

    private val httpClient = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()
    private val ready = AtomicBoolean(false)
    private val assistantSpeaking = AtomicBoolean(false)
    private val hasSentAudio = AtomicBoolean(false)

    @Volatile
    private var socket: WebSocket? = null

    fun connect() {
        if (!config.isComplete) {
            listener.onError("缺少有效的后端设备令牌或 Realtime 地址")
            return
        }
        if (socket != null) return

        listener.onStateChanged(State.CONNECTING)
        val request = Request.Builder()
            .url(config.realtimeWsUrl)
            .header("Authorization", "Bearer ${config.accessToken}")
            .header("User-Agent", "rokid-glass3-qwen-poc/1.0")
            .build()
        socket = httpClient.newWebSocket(request, webSocketListener)
    }

    /**
     * 首版采用半双工防回声：模型播放期间暂停上传眼镜麦克风，避免扬声器声音再次触发 VAD。
     * 后续接 AOQ/AEC 时可以移除该门控以支持真正的随时打断。
     */
    fun sendAudio(pcm16: ByteArray) {
        if (!ready.get() || assistantSpeaking.get() || pcm16.isEmpty()) return
        val event = JSONObject()
            .put("event_id", eventId())
            .put("type", "input_audio_buffer.append")
            .put("audio", Base64.encodeToString(pcm16, Base64.NO_WRAP))
        if (socket?.send(event.toString()) == true) {
            hasSentAudio.set(true)
        }
    }

    fun sendImage(jpeg: ByteArray) {
        if (
            !ready.get() ||
            assistantSpeaking.get() ||
            !hasSentAudio.get() ||
            jpeg.isEmpty() ||
            jpeg.size > MAX_IMAGE_BYTES
        ) {
            return
        }
        val event = JSONObject()
            .put("event_id", eventId())
            .put("type", "input_image_buffer.append")
            .put("image", Base64.encodeToString(jpeg, Base64.NO_WRAP))
        socket?.send(event.toString())
    }

    fun close() {
        ready.set(false)
        assistantSpeaking.set(false)
        hasSentAudio.set(false)
        socket?.close(1000, "activity stopped")
        socket = null
        listener.onStateChanged(State.DISCONNECTED)
    }

    private val webSocketListener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            webSocket.send(sessionUpdateEvent().toString())
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                handleEvent(JSONObject(text))
            } catch (error: Exception) {
                Log.w(TAG, "忽略无法解析的 Qwen 事件", error)
            }
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            webSocket.close(code, reason)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            clearSocket(webSocket)
        }

        override fun onFailure(webSocket: WebSocket, error: Throwable, response: Response?) {
            clearSocket(webSocket)
            listener.onError(
                "Qwen 连接失败${response?.code?.let { "（HTTP $it）" }.orEmpty()}：" +
                    error.message.orEmpty()
            )
        }
    }

    private fun handleEvent(event: JSONObject) {
        when (event.optString("type")) {
            "session.updated" -> {
                ready.set(true)
                listener.onStateChanged(State.READY)
            }

            "input_audio_buffer.speech_started" -> listener.onStateChanged(State.READY)

            "conversation.item.input_audio_transcription.completed" ->
                listener.onInputTranscript(event.optString("transcript"))

            "response.created" -> {
                assistantSpeaking.set(true)
                listener.onStateChanged(State.RESPONDING)
            }

            "response.audio_transcript.delta" ->
                listener.onOutputTranscriptDelta(event.optString("delta"))

            "response.audio.delta" -> {
                assistantSpeaking.set(true)
                val encoded = event.optString("delta")
                if (encoded.isNotEmpty()) {
                    listener.onAudioDelta(Base64.decode(encoded, Base64.DEFAULT))
                }
            }

            "response.done", "response.audio.done" -> {
                assistantSpeaking.set(false)
                listener.onStateChanged(State.READY)
            }

            "error" -> {
                val error = event.optJSONObject("error")
                listener.onError(error?.optString("message").orEmpty().ifBlank { event.toString() })
            }
        }
    }

    private fun sessionUpdateEvent(): JSONObject {
        val format = JSONObject()
            .put("type", "pcm")
            .put("sample_rate", SAMPLE_RATE)
        val audio = JSONObject()
            .put("input", JSONObject().put("format", JSONObject(format.toString())))
            .put("output", JSONObject().put("format", JSONObject(format.toString())))
        val session = JSONObject()
            .put("modalities", org.json.JSONArray().put("text").put("audio"))
            .put("voice", config.voice)
            .put("instructions", config.instructions)
            .put("audio", audio)
            .put(
                "input_audio_transcription",
                JSONObject().put("model", "qwen3-asr-flash-realtime")
            )
            .put(
                "turn_detection",
                JSONObject()
                    .put("type", "semantic_vad")
                    .put("threshold", 0.5)
                    .put("prefix_padding_ms", 300)
                    .put("silence_duration_ms", 800)
            )
        return JSONObject()
            .put("event_id", eventId())
            .put("type", "session.update")
            .put("session", session)
    }

    private fun clearSocket(webSocket: WebSocket) {
        if (socket === webSocket) socket = null
        ready.set(false)
        assistantSpeaking.set(false)
        hasSentAudio.set(false)
        listener.onStateChanged(State.DISCONNECTED)
    }

    private fun eventId(): String = "event_${UUID.randomUUID()}"

    companion object {
        private const val TAG = "QwenRealtimeClient"
        private const val SAMPLE_RATE = 16_000
        const val MAX_IMAGE_BYTES = 256 * 1024
    }
}
