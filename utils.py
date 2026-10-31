"""工具模块。

职责：
  * 用 Pillow 读取素材图片，一次性转换成 QPixmap 列表（启动时预加载，运行期零 IO）
  * 统一处理「目录缺失 / 图片损坏」等异常，保证素材有问题时程序也不崩溃
  * 提供一个纯代码绘制的占位贴图，用于素材全部缺失时兜底显示
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Union

from PIL import Image
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

from config import ASSETS_DIR, SPRITE_ACTIONS, SPRITE_SIZE

PathLike = Union[str, Path]

# 占位贴图配色，与正式素材保持一致的灰白调
_PLACEHOLDER_LINE = QColor(108, 118, 138)
_PLACEHOLDER_FILL = QColor(241, 244, 248)
_PLACEHOLDER_EYE = QColor(56, 64, 82)


def _write(stream, message: str) -> None:
    """把日志写到指定流。

    PyInstaller 用 ``-w``（无控制台）打包后，``sys.stdout`` / ``sys.stderr`` 可能为 None，
    直接 print 会抛异常，因此这里必须做兜底：无控制台时静默丢弃日志。
    """
    if stream is None:
        return
    try:
        print(message, file=stream, flush=True)
    except (AttributeError, OSError, ValueError):
        pass


def log(message: str) -> None:
    """统一日志输出，方便从命令行排查素材问题。"""
    _write(sys.stdout, f"[Pet] {message}")


def warn(message: str) -> None:
    """异常提示（仅打印，不中断程序）。"""
    _write(sys.stderr, f"[Pet] {message}")


# --------------------------------------------------------------------------- #
# 图片转换
# --------------------------------------------------------------------------- #
def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    """把 Pillow 的 RGBA 图像转换为 QPixmap。

    注意：``QImage`` 直接引用 Python bytes 的内存，必须调用 ``copy()``，
    否则 bytes 被回收后可能花屏甚至崩溃。
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    width, height = image.size
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def load_sprite_folder(folder: PathLike) -> List[QPixmap]:
    """读取一个文件夹下的所有 png，按文件名排序后转为 QPixmap 列表。

    容错策略：
        * 文件夹不存在   -> 打印提示，返回空列表
        * 单张图片损坏   -> 打印提示并跳过，不影响其它帧
        * 尺寸不符合规范 -> 用 LANCZOS 缩放到 ``SPRITE_SIZE``
    """
    folder = Path(folder)

    if not folder.is_dir():
        warn(f"素材目录不存在，已跳过：{folder}")
        return []

    frames: List[QPixmap] = []
    for file in sorted(folder.glob("*.png")):
        try:
            with Image.open(file) as raw:
                image = raw.convert("RGBA")
                if image.size != SPRITE_SIZE:
                    image = image.resize(SPRITE_SIZE, Image.LANCZOS)
                frames.append(pil_to_qpixmap(image))
        except (OSError, ValueError) as exc:
            # PIL 对损坏文件抛 UnidentifiedImageError（OSError 的子类）
            warn(f"素材损坏，已跳过：{file.name} -> {exc}")
        except Exception as exc:  # noqa: BLE001 - 兜底，绝不因为一张图崩掉程序
            warn(f"素材加载失败，已跳过：{file.name} -> {exc}")

    if not frames:
        warn(f"目录内没有可用帧：{folder}")
    else:
        log(f"已加载 {len(frames):>2d} 帧：{folder.name}")

    return frames


def load_all_sprites(assets_dir: PathLike = ASSETS_DIR) -> Dict[str, List[QPixmap]]:
    """预加载全部动作素材，返回 ``{动作名: [帧, ...]}``。

    在程序启动时调用一次，之后动画循环只做列表取值，不再访问磁盘。
    """
    assets_dir = Path(assets_dir)
    sprites: Dict[str, List[QPixmap]] = {
        action: load_sprite_folder(assets_dir / action) for action in SPRITE_ACTIONS
    }

    total = sum(len(frames) for frames in sprites.values())
    if total == 0:
        warn(f"未找到任何可用素材（{assets_dir}），将使用占位贴图运行")
    else:
        log(f"素材预加载完成，共 {total} 帧")

    return sprites


# --------------------------------------------------------------------------- #
# 兜底贴图
# --------------------------------------------------------------------------- #
def make_placeholder_pixmap(size: tuple = SPRITE_SIZE) -> QPixmap:
    """用 QPainter 画一只极简小狗，素材缺失时保证界面上仍有东西可交互。"""
    width, height = size
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(_PLACEHOLDER_LINE, 3))
    painter.setBrush(_PLACEHOLDER_FILL)

    # 立耳（两个三角形）
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.28, height * 0.36),
        QPointF(width * 0.36, height * 0.10),
        QPointF(width * 0.48, height * 0.30),
    ]))
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.72, height * 0.36),
        QPointF(width * 0.64, height * 0.10),
        QPointF(width * 0.52, height * 0.30),
    ]))

    # 身体 + 脑袋
    painter.drawEllipse(QRectF(width * 0.24, height * 0.50, width * 0.52, height * 0.36))
    painter.drawEllipse(QRectF(width * 0.26, height * 0.24, width * 0.48, height * 0.40))

    # 眼睛
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_PLACEHOLDER_EYE)
    painter.drawEllipse(QRectF(width * 0.40, height * 0.42, width * 0.07, height * 0.07))
    painter.drawEllipse(QRectF(width * 0.53, height * 0.42, width * 0.07, height * 0.07))
    painter.end()

    return pixmap
