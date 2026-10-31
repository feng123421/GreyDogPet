# 🐶 灰白立耳小狗桌宠 (GreyDogPet)

一个用 Python + PyQt6 打造的桌面宠物：一只灰白立耳的小狗，会闲逛、开心、睡觉、撒娇、惊讶……安静地趴在你的桌面上。

## ✨ 特性

- **7 种状态动画**：待机(IDLE)、开心(HAPPY)、睡觉(SLEEP)、走路(WALK)、惊讶(SURPRISE)、蹭头(RUB)、坐下(SIT)，状态互斥、自动切换
- **智能闲时行为**：闲置 10 秒自动坐下，20 秒自动入睡
- **鼠标互动**：
  - 左键单击 → 开心蹦跶
  - 拖拽窗口 → 走路动画
  - 睡眠时点一下 → 惊讶惊醒
  - 鼠标移入 → 歪头撒娇（带冷却）
- **无边框 + 置顶 + 透明背景**：真正像「趴在桌面上的宠物」，不抢焦点
- **右键菜单**：重置位置 / 退出
- **零运行时 IO**：启动时一次性预加载全部素材，运行期不读盘
- **素材容错**：素材缺失或图片损坏都不会崩溃，自动回退占位图

## 🛠 技术栈

- Python 3.10+
- PyQt6（窗口 / 定时器 / 绘图）
- Pillow（素材加载与处理）
- PyInstaller（打包成单文件 exe）

> 不使用 tkinter / pygame / electron / vue，严格遵循纯 PyQt6 方案。

## 📁 目录结构

```
desktop_pet/
├── assets/                # 动画素材（透明 PNG，256×256）
│   ├── idle/  happy/  sleep/  walk/
│   ├── surprise/  rub/  sit/
├── config.py              # 全局配置（尺寸/帧率/状态时间/资源路径）
├── pet.py                # 状态机（PetState 枚举 + Pet 对象）
├── utils.py              # 素材加载、预加载、占位图、日志
├── main.py               # 主窗口（无边框/置顶/透明/交互/右键菜单）
└── README.md
```

## 🚀 运行（从源码）

建议使用虚拟环境：

```bash
# 1. 创建并激活虚拟环境（任选其一）
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. 安装依赖
pip install PyQt6 Pillow

# 3. 启动
python main.py
```

## 📦 打包成 exe

使用 PyInstaller 打包为单文件、无控制台、并内嵌 assets：

```bash
pip install pyinstaller
pyinstaller -F -w --add-data "assets;assets" main.py -n GreyDogPet
```

打包完成后，`dist/GreyDogPet.exe` 即为可直接运行的单文件程序（无需 Python 环境）。

## 🎮 交互说明

| 操作 | 反应 |
| --- | --- |
| 左键单击 | 开心 |
| 拖拽移动 | 走路 |
| 睡眠时点击 | 惊讶惊醒 |
| 鼠标移入 | 歪头撒娇 |
| 闲置 10 秒 | 自动坐下 |
| 闲置 20 秒 | 自动入睡 |
| 右键 | 菜单（重置位置 / 退出） |

## 📄 License

MIT（详见 LICENSE 文件）
