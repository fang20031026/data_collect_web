# Camera Collector

本工具用于通过浏览器预览摄像头、录制视频，并由本地 Python 服务保存为 MP4。支持单摄像头模式和 head / left / right 三路多摄像头模式。

## Linux 免安装发布包

已经生成的 Linux x86_64 发布包在：

```text
release/camera_collector_linux_x86_64.tar.gz
```

新电脑解压后运行：

```bash
tar -xzf camera_collector_linux_x86_64.tar.gz
cd camera_collector_linux_x86_64
./run.sh
```

发布包内包含 Linux 版 `ffmpeg`，程序会优先使用包内版本。

## Linux 启动

```bash
chmod +x start_linux.sh
./start_linux.sh
```

## Windows 启动

双击 `start_windows.bat`，或在命令行运行：

```bat
start_windows.bat
```

## 使用流程

1. 程序启动后会自动选择可用端口并打开浏览器。
2. 点击“选择保存目录”。
3. 选择“单摄像头”或“多摄像头”模式。
4. 单摄像头模式：选择设备，点击“打开摄像头”。
5. 多摄像头模式：为 head、left、right 选择摄像头，点击“打开全部摄像头”。
6. 浏览器请求权限时选择允许。
7. 点击“开始录制”。
8. 点击“停止录制”。
9. 自动保存开启时，MP4 会直接保存到当前目录；关闭时需要点击“保存到目录”。
10. 点击“打开保存目录”可以查看输出文件。
11. 点击“退出程序”可以关闭本地服务。

## 多摄像头模式

- head 输出固定为 1280 x 720。
- left 输出固定为 640 x 360。
- right 输出固定为 640 x 360。
- 三路都打开后才能开始录制。
- 三路可以选择同一个摄像头，也可以选择不同摄像头。
- 三路打开后，修改某一路摄像头下拉框会只切换该路。
- 画面左侧 head 宽高都是右侧 left/right 的 2 倍。

多摄像头模式保存结构：

```text
选择目录/
├── head/000000.mp4
├── left/000000.mp4
├── right/000000.mp4
└── metadata/000000.json
```

## 依赖

- Python 3
- ffmpeg
- Chrome、Edge 或 Firefox 最新版

Linux 目录选择优先使用 `zenity` 或 `kdialog`，没有时尝试 `tkinter`。

## 打包方向

安装构建依赖：

```bash
python3 -m pip install -r requirements-build.txt
```

Linux 构建：

```bash
./build_linux.sh
```

构建后可以直接运行：

```bash
./dist/linux/camera_collector
```

Windows 构建：

```bat
build_windows.bat
```

Windows 构建会生成：

```text
release\camera_collector_windows\camera_collector.exe
```


Windows 发布包打包（在 Windows 机器执行）：

```bat
package_windows_release.bat
```

会生成：

```text
release\camera_collector_windows.zip
```

采集人员双击 `camera_collector.exe` 即可自动启动本地服务并打开浏览器。

Windows 可执行文件需要在 Windows 机器上运行 `build_windows.bat` 构建。PyInstaller 不能在 Linux 上直接交叉生成 Windows `.exe`。

为了让 Windows 端不需要手动安装 ffmpeg，请把 Windows 版 `ffmpeg.exe` 放到：

```text
third_party\ffmpeg\windows\ffmpeg.exe
```

如果没有内置 `ffmpeg.exe`，程序仍可构建，但目标机器需要能在 PATH 中找到 `ffmpeg`。
