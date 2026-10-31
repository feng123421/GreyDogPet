"""程序入口：透明置顶窗口 + 鼠标交互 + 60ms 主循环。

运行方式
--------
    python main.py

打包（单文件、无控制台黑窗口、内嵌 assets 素材）
----------------------------------------------
    pyinstaller -F -w --add-data "assets;assets" main.py -n GreyDogPet
"""

from __future__ import annotations

import sys
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QGuiApplication, QPainter
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from config import (
    DRAG_THRESHOLD,
    FRAME_INTERVAL_MS,
    SPRITE_SIZE,
    WINDOW_MARGIN,
    WINDOW_TITLE,
)
from pet import Pet
from utils import warn

# 右键菜单样式：配合灰白小狗的清爽配色
_MENU_STYLE = """
QMenu {
    background-color: #F7F9FC;
    border: 1px solid #D7DEE9;
    border-radius: 8px;
    padding: 6px;
    color: #3A4252;
    font-size: 13px;
}
QMenu::item {
    padding: 6px 28px 6px 18px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #E7EEF8;
}
QMenu::separator {
    height: 1px;
    background: #E1E7F0;
    margin: 4px 8px;
}
"""


class PetWindow(QWidget):
    """桌宠主窗口：无边框、置顶、背景透明，只负责绘制与鼠标交互。"""

    def __init__(self) -> None:
        super().__init__()

        # ---- 交互状态 ----
        self._press_global: QPoint = QPoint()      # 按下时的全局坐标
        self._drag_offset: Optional[QPoint] = None  # 窗口左上角相对鼠标的偏移
        self._dragging: bool = False                # 本次按下是否已判定位拖拽

        # ---- 核心状态机 ----
        self._pet = Pet(self)

        self._init_window()
        self._init_timer()
        self._move_to_corner()

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #
    def _init_window(self) -> None:
        """无边框 + 置顶 + 子窗口（不进任务栏切换列表）+ 透明背景。"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(*SPRITE_SIZE)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint      # 去掉标题栏与边框
            | Qt.WindowType.WindowStaysOnTopHint   # 始终置顶
            | Qt.WindowType.SubWindow              # 作为子窗口，不抢任务栏
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        # TODO: 需要显示在托盘时，可在此创建 QSystemTrayIcon 并绑定同一份右键菜单

    def _init_timer(self) -> None:
        """60ms 主循环：驱动动画帧推进并触发重绘。"""
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_INTERVAL_MS)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _move_to_corner(self) -> None:
        """把宠物放到主屏幕右下角（右键菜单「重置位置」也复用这里）。"""
        screen = QGuiApplication.primaryScreen()
        if screen is None:                      # 理论上不会发生，做防御性判断
            return

        area = screen.availableGeometry()
        x = area.right() - self.width() - WINDOW_MARGIN
        y = area.bottom() - self.height() - WINDOW_MARGIN
        self.move(int(x), int(y))

    # ------------------------------------------------------------------ #
    # 主循环
    # ------------------------------------------------------------------ #
    def _on_tick(self) -> None:
        """每一个定时器周期：推进状态机 -> 请求重绘。"""
        self._pet.update(FRAME_INTERVAL_MS)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        """绘制当前帧；透明背景由窗口属性保证。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, self._pet.pixmap)

    # ------------------------------------------------------------------ #
    # 鼠标交互
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event) -> None:  # noqa: N802
        """左键按下：记录起点，等待后续判断是「拖拽」还是「单击」。"""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        self._press_global = event.globalPosition().toPoint()
        self._drag_offset = self._press_global - self.frameGeometry().topLeft()
        self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """按住移动：超过阈值判定为拖拽，窗口跟随鼠标。"""
        if self._drag_offset is None:
            return

        current = event.globalPosition().toPoint()
        if not self._dragging:
            moved = (current - self._press_global).manhattanLength()
            if moved < DRAG_THRESHOLD:      # 轻微抖动不算拖拽
                return
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._pet.handle_drag_start()

        self.move(current - self._drag_offset)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """左键松开：拖拽结束，或判定为一次单击（触发开心动画）。"""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if self._dragging:
            self._pet.handle_drag_end()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._drag_offset is not None:
            self._pet.handle_click()

        self._drag_offset = None
        self._dragging = False
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802
        """鼠标移入：撒娇歪头（冷却由状态机内部管理）。"""
        self._pet.handle_hover()
        super().enterEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """右键菜单：重置位置 / 退出程序。"""
        menu = QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)

        reset_action = QAction("重置位置", menu)
        quit_action = QAction("退出", menu)
        menu.addAction(reset_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        chosen = menu.exec(event.globalPos())
        if chosen is reset_action:
            self._move_to_corner()
        elif chosen is quit_action:
            QApplication.quit()

        # TODO: 后续可在此追加「设置面板」「开机自启」等菜单项

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:  # noqa: N802
        """关闭窗口时停掉定时器，避免退出过程中继续回调。"""
        self._timer.stop()
        super().closeEvent(event)


def main() -> int:
    """创建应用与窗口，进入事件循环。"""
    app = QApplication(sys.argv)
    app.setApplicationName("GreyDogPet")
    app.setQuitOnLastWindowClosed(True)

    window = PetWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - 入口兜底，避免闪退无提示
        warn(f"程序异常退出：{exc}")
        raise
