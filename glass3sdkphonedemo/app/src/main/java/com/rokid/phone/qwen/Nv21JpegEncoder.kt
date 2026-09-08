package com.rokid.phone.qwen

import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import java.io.ByteArrayOutputStream

object Nv21JpegEncoder {
    /**
     * Qwen Realtime 单张图片限制 256 KiB。依次降低 JPEG 质量，仍超限则丢弃该帧。
     */
    fun encode(
        nv21: ByteArray,
        width: Int,
        height: Int,
        maxBytes: Int = QwenRealtimeClient.MAX_IMAGE_BYTES,
    ): ByteArray? {
        if (width <= 0 || height <= 0 || nv21.size < width * height * 3 / 2) return null
        val image = YuvImage(nv21, ImageFormat.NV21, width, height, null)
        for (quality in JPEG_QUALITIES) {
            val output = ByteArrayOutputStream()
            if (!image.compressToJpeg(Rect(0, 0, width, height), quality, output)) continue
            val jpeg = output.toByteArray()
            if (jpeg.size <= maxBytes) return jpeg
        }
        return null
    }

    private val JPEG_QUALITIES = intArrayOf(55, 40, 25)
}
