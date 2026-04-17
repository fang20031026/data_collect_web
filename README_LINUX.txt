Camera Collector Linux 使用说明

适用系统：
- Linux x86_64 桌面系统
- 推荐 Ubuntu/Debian/Linux Mint 等常见发行版
- 推荐浏览器：Chrome、Chromium、Firefox 最新版

使用方式：
1. 解压 camera_collector_linux_x86_64.tar.gz。
2. 进入解压后的 camera_collector_linux_x86_64 目录。
3. 双击 run.sh，或在终端运行：

   ./run.sh

4. 程序会自动启动本地服务，并打开浏览器页面。
5. 点击“选择保存目录”。
6. 选择“单摄像头”或“多摄像头”模式。
7. 单摄像头模式：选择设备，点击“打开摄像头”。
8. 多摄像头模式：为 head、left、right 选择摄像头，点击“打开全部摄像头”。
   - 三路可以选择同一个摄像头，也可以选择不同摄像头。
   - head 输出固定为 1280 x 720。
   - left 输出固定为 640 x 360。
   - right 输出固定为 640 x 360。
   - 三路都打开后才能开始录制。
   - 三路打开后，修改某一路的摄像头下拉框会只切换该路，不需要重新打开全部摄像头。
   - 画面左侧 head 宽高都是右侧 left/right 的 2 倍。
9. 浏览器请求权限时选择允许。
10. 点击“开始录制”。
11. 点击“停止录制”。
12. 自动保存开启时，单摄像头 MP4 会保存为 000000.mp4、000001.mp4、000002.mp4。
13. 多摄像头模式会保存为：

   选择目录/head/000000.mp4
   选择目录/left/000000.mp4
   选择目录/right/000000.mp4
   选择目录/metadata/000000.json

14. 切换到新的保存目录后，编号会从 000000.mp4 重新开始。
15. 点击“退出程序”关闭本地服务。

如果双击 run.sh 没有反应：
1. 在目录空白处打开终端。
2. 运行：

   chmod +x run.sh camera_collector
   ./run.sh

说明：
- 发布包内包含 ffmpeg 时，会优先使用包内 ffmpeg。
- 如果包内 ffmpeg 在目标机器不可用，请安装系统 ffmpeg：

  sudo apt install ffmpeg

- Linux 二进制包通常适用于同架构 x86_64 且 glibc 版本兼容的桌面系统。
