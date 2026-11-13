哦，金金的音道分离 · v0.5.0 Windows 在线安装版

这个小包没有内置 Python、PyTorch 和 CUDA 运行库。
第一次需要下载约 3–4 GB 环境，再准备约 919 MB 双阶段模型；并不是几 MB 就能离线运行。
安装和缓存请预留至少 12 GiB 空间，处理歌曲还需要额外空间。

1. 完整解压到可写文件夹，不要只取 EXE 或直接在压缩包内运行。
2. 双击“哦，金金的音道分离.exe”。缺少环境时会显示中文提示。
3. 点击“安装运行环境”，保持联网，等候安装完成。
4. GPU 检查通过后点击“启动软件（GPU）”，首次自动准备模型。
5. 以后双击主 EXE，检查通过会直接打开独立桌面窗口，可以离线处理。

安装位置：%LOCALAPPDATA%\JinjinAudio\runtime-cu128-py311-v1
软件使用自己的 Python，不修改系统 Python、PATH，不要求管理员权限。
完整保留 PyTorch 2.7.1+cu128，仍支持 CUDA GPU 推理，不需要安装 CUDA Toolkit。
小包只是把环境改为首次下载，并没有把最终磁盘占用或总下载量缩减为小包大小。
系统要求：Windows 10/11 x64（系统自带 .NET Framework 4.x），NVIDIA GPU 与兼容驱动。
如主 EXE 没有显示窗口，先检查是否完整解压，查看 data/logs/setup.log。

修复和提示
- 缺少 Python / Python 库、库版本不符或 DLL 加载失败：打开“检查运行环境.exe”，安装或修复。
- NVIDIA 驱动或 GPU 不可用：点击“NVIDIA 驱动”前往官网安装驱动，重启后重新检查。
  也可明确选择“使用 CPU 继续”，运行速度会较慢；不会冒充 GPU 模式。
- 模型缺失或损坏：主窗口会自动从作者公开链接下载并校验，可在失败后重试。
- 网络失败：日志区会指出卡在 Python、PyTorch 还是 PyPI 依赖安装。
  请保证 GitHub/Astral、download.pytorch.org、pypi.org 、huggingface.co 以及作者模型链接可访问。
- 空间不足或没有写入权限：腾出空间，或解压到可写目录后重试。
- 安装失败可以重试；修复可能重新下载依赖，不删除歌曲或已导出的文件。
- 安装期间请勿移动软件或环境目录。该软件未作商业代码签名。

使用：导入歌曲 → 分离选区或整首 → 试听候选 1 / 2 → 选择候选写入目标轨 → 试听并导出。
局部换人时框选该段，可改选另一候选；新分离不会自动覆盖目标轨。
候选轨仅保留最近一次分离。旧版 3 秒参考模式仍可在“分离方式”中选择。
保留原有同步试听、外部参考、缩放/平移、局部重做、静音、撤销和 WAV/ZIP 导出。
data/models：模型；data/outputs：导出；data/cache：试听缓存；data/logs：日志。
旧版数据可在关闭软件后，把旧软件的 data 文件夹复制到本版旁边（先备份，避免覆盖新结果）。
编辑历史只在本次运行期间保留；退出前请导出。

验证范围：开发机 RTX 5080；RTX 5090 仍需接收方实机验收。
单首双人歌曲获得“进步非常明显”的用户反馈，不能推广到所有歌曲。
候选编号不代表固定歌手，可能串音或换人，需要逐段试听。
双轨模型原生输出 24 kHz 单声道，恢复原采样率不会增加高频细节。

代码：https://github.com/MarginalEmbers/singer-extractor-local
默认模型：Mel-Band RoFormer + UNMIXX
RoFormer：https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model
权重：https://huggingface.co/KimberleyJSN/melbandroformer
UNMIXX：https://github.com/jihoojung0106/unmixx
UNMIXX 论文：https://arxiv.org/abs/2601.12802
固定版本和 SHA-256：app/singer_extractor/two_stage_manifest.json

旧版对照模型引用：Jocelyn Xu、Minje Kim（2026），Singer-Informed Vocal Source Separation for Multi-Singer Music Mixtures。
论文：https://arxiv.org/abs/2608.14516
作者代码和权重链接：https://github.com/jocelynxu01/singer-separation-paper
变体：FiLM / target-vocal loss only + clean singer embedding。
本软件是工程封装，不是原创模型或作者官方应用。模型不随包分发，模型授权与应用 MIT License 分开。
安装助手 uv 0.12.7：https://github.com/astral-sh/uv/releases/tag/0.12.7
第三方许可见 LICENSES 和 THIRD_PARTY_NOTICES.md；安装后的库保留其原始许可文件。
