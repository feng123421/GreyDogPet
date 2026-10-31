"""宠物核心类：状态机 + 动画推进 + 闲置计时。

设计要点
--------
1. **状态互斥**：所有动画都由唯一的 ``_state`` 字段驱动，
   同一时刻只可能存在一种状态，不存在多段动画叠加。
2. **动画推进**：外部 60ms 定时器调用 :meth:`Pet.update`，
   内部按「单帧停留时长」累计时间，逐帧推进。
3. **自动收尾**：一次性动作（happy / surprise / rub / sit）播放完一轮后
   自动回到 ``IDLE``；``WALK`` 与 ``SLEEP`` 属于循环动作。
4. **闲置计时**：任何鼠标交互都会把计时清零；超时先坐下、再睡觉。

交互与状态对照
--------------
====================  ==========================================
鼠标操作              触发状态
====================  ==========================================
左键单击              HAPPY（若正在睡觉则先 SURPRISE 惊醒）
左键按住拖拽          WALK（松手回 IDLE）
鼠标移入              RUB（撒娇歪头，带冷却）
闲置 10 秒            SIT（每轮闲置只触发一次）
闲置 20 秒            SLEEP
====================  ==========================================
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap

from config import (
    FRAME_DURATION_MS,
    FRAME_INTERVAL_MS,
    IDLE_SIT_TIME,
    IDLE_SLEEP_TIME,
    LOOP_ACTIONS,
    RUB_COOLDOWN_TIME,
    WALK_WHILE_DRAGGING,
)
from utils import load_all_sprites, make_placeholder_pixmap, warn


class PetState(Enum):
    """宠物状态；``value`` 同时就是 assets 下的素材目录名。"""

    IDLE = "idle"          # 待机
    HAPPY = "happy"        # 开心挥手
    SLEEP = "sleep"        # 睡觉
    WALK = "walk"          # 走路（拖拽时循环播放）
    SURPRISE = "surprise"  # 惊讶
    RUB = "rub"            # 歪头撒娇
    SIT = "sit"            # 坐下


class Pet(QObject):
    """桌宠核心状态机（与界面解耦，方便单测与复用）。"""

    #: 状态变化时发出，参数为新的 :class:`PetState`
    state_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        #: 预加载的全部素材：{动作名: [帧, ...]}
        self._sprites: Dict[str, List[QPixmap]] = load_all_sprites()
        self._placeholder: QPixmap = make_placeholder_pixmap()

        # ---- 状态机 ----
        self._state: PetState = PetState.IDLE
        self._frame_index: int = 0
        self._frame_elapsed: float = 0.0     # 当前帧已停留的毫秒数

        # ---- 计时 ----
        self._clock: float = 0.0             # 程序内部累计时间（毫秒）
        self._idle_elapsed: float = 0.0      # 距离上次交互的闲置时间（毫秒）
        self._last_rub_at: float = -1e9      # 上次撒娇的时间点
        self._has_sat: bool = False          # 本轮闲置是否已经坐过

        if not any(self._sprites.values()):
            warn("素材全部缺失，宠物将以占位贴图运行")

    # ------------------------------------------------------------------ #
    # 只读属性
    # ------------------------------------------------------------------ #
    @property
    def state(self) -> PetState:
        """当前状态。"""
        return self._state

    @property
    def is_sleeping(self) -> bool:
        return self._state is PetState.SLEEP

    @property
    def pixmap(self) -> QPixmap:
        """当前应显示的帧；素材缺失时返回占位贴图。"""
        frames = self._sprites.get(self._state.value) or []
        if not frames:
            return self._placeholder
        return frames[self._frame_index % len(frames)]

    # ------------------------------------------------------------------ #
    # 主循环
    # ------------------------------------------------------------------ #
    def update(self, elapsed_ms: float = FRAME_INTERVAL_MS) -> None:
        """由主窗口的定时器驱动，推进动画与闲置计时。"""
        self._clock += elapsed_ms
        self._tick_idle(elapsed_ms)
        self._tick_animation(elapsed_ms)

    def _tick_idle(self, elapsed_ms: float) -> None:
        """闲置计时：超时先坐下，再睡觉。"""
        if self._state is PetState.WALK:
            # 拖拽过程中不算闲置，避免拖着拖着睡着
            self._idle_elapsed = 0.0
            return

        if self._state is not PetState.IDLE:
            return

        self._idle_elapsed += elapsed_ms
        if self._idle_elapsed >= IDLE_SLEEP_TIME * 1000:
            self.set_state(PetState.SLEEP)
        elif not self._has_sat and self._idle_elapsed >= IDLE_SIT_TIME * 1000:
            self._has_sat = True          # 每轮闲置只坐一次，避免反复坐下
            self.set_state(PetState.SIT)

    def _tick_animation(self, elapsed_ms: float) -> None:
        """按「单帧停留时长」累加时间，逐帧推进动画。"""
        duration = FRAME_DURATION_MS.get(self._state.value, FRAME_INTERVAL_MS)
        self._frame_elapsed += elapsed_ms
        if self._frame_elapsed < duration:
            return
        self._frame_elapsed = 0.0

        frames = self._sprites.get(self._state.value) or []
        if not frames:
            # 该动作没有素材：不要卡在这一帧上，一次性动作直接判定结束
            if self._state.value not in LOOP_ACTIONS:
                self.set_state(PetState.IDLE)
            return

        self._frame_index += 1
        if self._frame_index < len(frames):
            return

        # 播放到最后一帧之后
        if self._state.value in LOOP_ACTIONS:
            self._frame_index = 0                       # 循环播放
        else:
            self.set_state(PetState.IDLE)               # 动作结束，回到待机

    # ------------------------------------------------------------------ #
    # 状态切换
    # ------------------------------------------------------------------ #
    def set_state(self, state: PetState) -> None:
        """切换状态并从第一帧开始播放。

        这是唯一的入口，保证「同一时间只有一种动画」。
        """
        if state is self._state:
            return

        self._state = state
        self._frame_index = 0
        self._frame_elapsed = 0.0
        self.state_changed.emit(state)

    def _reset_idle(self) -> bool:
        """重置闲置计时，返回重置前是否正在睡觉。"""
        self._idle_elapsed = 0.0
        self._has_sat = False
        return self._state is PetState.SLEEP

    # ------------------------------------------------------------------ #
    # 鼠标交互（由主窗口调用）
    # ------------------------------------------------------------------ #
    def handle_click(self) -> None:
        """左键单击：开心挥手；正在睡觉时先被惊醒（惊讶）。"""
        if self._reset_idle():
            self.set_state(PetState.SURPRISE)
        else:
            self.set_state(PetState.HAPPY)

    def handle_drag_start(self) -> None:
        """开始拖拽：重置闲置计时，可配置为播放走路动画。"""
        self._reset_idle()
        if WALK_WHILE_DRAGGING:
            self.set_state(PetState.WALK)

    def handle_drag_end(self) -> None:
        """松手：从走路回到待机。"""
        self._reset_idle()
        if self._state is PetState.WALK:
            self.set_state(PetState.IDLE)

    def handle_hover(self) -> None:
        """鼠标移入：撒娇歪头（带冷却，睡眠 / 拖拽时不打扰）。"""
        if self._state in (PetState.SLEEP, PetState.WALK):
            return
        if self._clock - self._last_rub_at < RUB_COOLDOWN_TIME * 1000:
            return

        self._last_rub_at = self._clock
        self._reset_idle()
        self.set_state(PetState.RUB)

    # ------------------------------------------------------------------ #
    # 扩展点位（当前版本未启用）
    # ------------------------------------------------------------------ #
    # TODO: 接入系统托盘后，可在此增加「喂食 / 投喂好感度」等逻辑
    # TODO: 需要读档存档时，可在此持久化状态与闲置计时
