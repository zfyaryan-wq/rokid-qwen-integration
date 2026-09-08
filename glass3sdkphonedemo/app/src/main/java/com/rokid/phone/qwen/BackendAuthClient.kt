package com.rokid.phone.qwen

import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class BackendAuthClient(
    private val baseUrl: String,
    private val enrollmentToken: String,
) {
    data class Session(
        val accessToken: String,
        val realtimeWsUrl: String,
        val expiresInSeconds: Long,
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun login(
        deviceId: String,
        onSuccess: (Session) -> Unit,
        onError: (String) -> Unit,
    ) {
        if (baseUrl.isBlank() || enrollmentToken.isBlank()) {
            onError("缺少华为云后端地址或设备注册口令")
            return
        }
        val body = JSONObject()
            .put("device_id", deviceId)
            .put("enrollment_token", enrollmentToken)
            .toString()
            .toRequestBody(JSON)
        val request = Request.Builder()
            .url("${baseUrl.trimEnd('/')}/api/v1/devices/login")
            .post(body)
            .build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, error: IOException) {
                onError("后端登录失败：${error.message.orEmpty()}")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    val responseBody = it.body?.string().orEmpty()
                    if (!it.isSuccessful) {
                        val detail = runCatching {
                            JSONObject(responseBody).optString("detail")
                        }.getOrDefault("")
                        onError("后端登录失败（HTTP ${it.code}）${detail.takeIf(String::isNotBlank)?.let { value -> "：$value" }.orEmpty()}")
                        return
                    }
                    try {
                        val payload = JSONObject(responseBody)
                        val session = Session(
                            accessToken = payload.getString("access_token"),
                            realtimeWsUrl = payload.getString("realtime_ws_url"),
                            expiresInSeconds = payload.optLong("expires_in"),
                        )
                        if (
                            session.accessToken.isBlank() ||
                            !(session.realtimeWsUrl.startsWith("ws://") ||
                                session.realtimeWsUrl.startsWith("wss://"))
                        ) {
                            onError("后端返回了无效的实时会话")
                            return
                        }
                        onSuccess(session)
                    } catch (error: Exception) {
                        onError("后端登录响应解析失败：${error.message.orEmpty()}")
                    }
                }
            }
        })
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}
