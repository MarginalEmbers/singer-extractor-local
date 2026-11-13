"""Generate the project's vector-style waveform icon; no external image assets."""

import math
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

target = Path(__file__).resolve().parents[1] / "singer_extractor/web/app.ico"
images = []
for size in (32, 64, 128, 256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#201b39"))
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.23, size * 0.23)
    for row, color in enumerate(("#b7a0ff", "#8edbc9", "#b7a0ff")):
        path = QPainterPath()
        for step in range(101):
            x = size * (0.2 + 0.6 * step / 100)
            y = size * (0.32 + row * 0.18 + 0.06 * math.sin(step / 100 * math.pi * 2))
            if step == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.setPen(
            QPen(QColor(color), size * 0.045, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawPath(path)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    images.append((size, bytes(buffer.data())))
offset = 6 + 16 * len(images)
result = struct.pack("<HHH", 0, 1, len(images))
for size, png in images:
    result += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
    offset += len(png)
target.write_bytes(result + b"".join(png for size, png in images))
print(target)
