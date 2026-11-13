# 哦，金金的音道分离

根据一段目标歌手的参考声音，从双人歌曲中尝试提取该歌手的人声。
面向 Windows + NVIDIA GPU，提供中文多轨时间线、片段预览和完整 WAV 导出。

**v0.3.0：Windows 独立桌面版。** 无需自己安装 Python，无需打开浏览器。
[下载发布版](https://github.com/MarginalEmbers/singer-extractor-local/releases/tag/v0.3.0) · [更新记录](CHANGELOG.md)

模型基于 **Jocelyn Xu、Minje Kim（2026）** 的
[Singer-Informed Vocal Source Separation for Multi-Singer Music Mixtures](https://arxiv.org/abs/2608.14516)
及[作者公开代码与权重链接](https://github.com/jocelynxu01/singer-separation-paper)。
使用 **FiLM / target-vocal loss only + clean singer embedding**。
本项目负责桌面界面、分段推理和导出，是工程封装，不是原创模型或作者官方应用。

**状态：实验原型。** 已接入作者公开的 FiLM 权重；没有真实歌曲试听结论。
分离结果可能包含另一位歌手、伴奏残留或失真，不能保证去除全部串音。

## 它做什么

- 选择歌曲，再选择目标歌手独唱的 3 秒参考片段。
- 参考可来自这首歌，也可来自单独的音频文件。
- 波形拖选 3 秒参考和预览范围，支持缩放、平移与精确时间输入。
- 原曲、目标 A、残差共用播放位置，支持循环选区和同位置切换试听。
- 先处理指定片段，再处理整首；可重做局部、手动静音和撤销。
- 导出目标音轨、残差音轨和不含文件路径的 JSON 处理记录。
- 整首导出保留输入采样率、样本数量和时间位置；输出为单声道 32-bit float WAV。
- 在本机运行；界面只监听 `127.0.0.1`，不加载 CDN 或在线推理服务。

这是**按歌手提取**，目标歌手自己的主唱、和声、叠唱都属于目标。
它不支持按旋律挑选声部，也没有自动标注歌手时间段的功能。

## Windows 桌面版

1. 从 Releases 下载 Windows 便携包，**完整解压**到可写文件夹。
2. 双击 `哦，金金的音道分离.exe`，打开独立软件窗口。
3. 首次启动自动从作者公开地址下载并校验约 29 MB 模型；之后可离线处理。

保留 EXE 旁的 `_internal` 文件夹；转发给朋友时请发完整压缩包。
运行环境已包含 Python、Qt WebEngine、PyTorch 2.7.1+cu128 和 CUDA 运行库。
仍需要机器本身的 NVIDIA 驱动，无需安装 Python、uv 或 CUDA Toolkit。
界面使用内置引擎，本机服务监听随机 `127.0.0.1` 端口；不会启动外部浏览器。

导出在软件旁 `data/outputs`，可从“文件 → 打开导出文件夹”进入。
模型、缓存、日志分别在 `data/models`、`data/cache`、`data/logs`。
程序未作商业代码签名；发布页提供 SHA-256 用于核对下载文件。
Windows x64 + RTX 5080 已测试；RTX 5090 尚需在接收方电脑验收。
详见[验证记录](docs/VALIDATION.md)和[桌面构建说明](docs/DESKTOP_BUILD.md)。

## 源代码运行（开发者）

源代码版保留原有浏览器入口。下面的安装步骤不适用于已经下载桌面便携包的用户。

1. 安装 NVIDIA 驱动，以及官方 [uv](https://docs.astral.sh/uv/getting-started/installation/)。
2. 下载仓库 ZIP 并解压，或使用 Git 克隆。
3. 双击 `setup.bat`，创建独立 Python 3.11 环境并安装依赖。
4. 双击 `download_models.bat`，下载并校验作者的两个模型文件。
5. 双击 `check_environment.bat` 检查显卡，再双击 `start.bat`。
6. 浏览器会打开 `http://127.0.0.1:7860`。处理期间保留启动窗口；关闭窗口即停止服务。

安装不会替换系统 Python。PyTorch 使用固定的 `2.7.1+cu128` 构建，支持本项目
RTX 5080 测试环境；朋友的 RTX 5090 尚需单独验收。下载 PyTorch 约需 3 GB。
首次安装完成后，音频推理不需要访问网络。详细验证范围见 [验证记录](docs/VALIDATION.md)。

## 第一次使用

1. 导入 WAV、FLAC、MP3 或 OGG；其他格式先转换为 WAV。
2. 工具切换到“参考 3 秒（原曲）”，在原曲波形上拖动绿色参考区域，找到只有 A 演唱的片段。也可导入单独参考文件。
3. 点击“循环试听这 3 秒”，确认没有选错人，也没有混入另一位歌手。
4. 工具切回“框选预览”，在原曲波形拖选一段重叠演唱，点击“提取 / 重做选区”。
5. 播放时切换三个音轨旁的“试听”，比较同一位置。可打开“循环选区”；灰色表示尚未处理。
6. 换参考或框选有问题的片段，再次提取。确认只有 B 的区域可手动静音；操作可撤销。
7. 满意后“处理整首歌曲”，再“导出整首”。也可以只导出已处理的选区。

没有歌曲时，可点击“载入功能自检音频”验证流程；它是合成音，不用于判断歌声分离质量。

快捷键：Space 播放/暂停，A/B 对比原曲/目标，I/O 设置选区边界，Ctrl+Z 撤销。
输入框和按钮聚焦时保留控件自己的键盘行为。缩放后通过下方“平移”滑块移动视图。

点击导出后，桌面版结果保存在软件旁 `data/outputs/`，源代码版保存在项目 `outputs/` 下。
每次导出使用独立目录，不覆盖以前的结果。
页面同时提供目标、残差、JSON 和 ZIP 下载。未处理区域必须先提取或明确标记静音才能导出。
片段重做在选区内部采用约 5 ms 淡化，选区外的样本保持不变。
`residual.wav` 是“单声道原音减去目标输出”，包含伴奏、其他歌手以及分离误差，
**不是保证纯净的另一位歌手音轨**。模型也不能保证目标未出现时完全静音。

输出采用浮点 WAV，避免超出幅度范围时在写文件阶段削波。界面试听对三个音轨应用
相同的安全增益，导出保留模型原始幅度；若峰值超过 0 dBFS，请在混音软件中降低音量。
没有做分段响度归一化。

时间线项目和撤销历史仅在本次运行期间可用，**关闭软件前请导出**。
最多保留 3 个项目，撤销最多 10 步（历史超过 64 MB 时会提前淘汰旧步骤，至少保留最近一步）。
本版限制单文件 500 MB、最长 60 分钟；长音频会占用较多内存和缓存磁盘。
桌面版 `data/cache/`、源代码版 `.cache/workspaces-v2/` 保留本机试听缓存，
不是可重新打开的工程文件；关闭软件后可手动清理。

从 v0.1 升级：覆盖源代码后重新运行 `setup.bat`，已有模型无需重复下载。
若浏览器仍显示旧界面，请刷新页面。

## 命令行

在 **Windows PowerShell 的项目根目录**运行：

```powershell
# 从歌曲第 20 秒开始取 3 秒参考，预览第 60 秒之后的 30 秒
.\.venv\Scripts\python.exe -m singer_extractor.cli extract "D:\Music\duet.wav" --reference-start 20 --start 60 --duration 30 --device cuda

# 用单独参考文件提取整首，参考取该文件的前 3 秒
.\.venv\Scripts\python.exe -m singer_extractor.cli extract "D:\Music\duet.wav" --reference "D:\Music\singer-a.wav" --device cuda

# 检查环境与模型文件
.\.venv\Scripts\python.exe -m singer_extractor.cli doctor
```

示例路径需要替换为你自己的文件。CPU 模式可用 `--device cpu`，速度应单独测量。
片段输出从文件第 0 秒开始，原曲位置记录在 `report.json` 的 `start_seconds` 中。

## 模型与工程选择

本项目基于 Jocelyn Xu 和 Minje Kim 的
[Singer-Informed Vocal Source Separation for Multi-Singer Music Mixtures](https://arxiv.org/abs/2608.14516)
及[作者代码](https://github.com/jocelynxu01/singer-separation-paper)，不宣称原创模型。

- 选择 **FiLM / target-vocal loss only** 权重；本项目不是论文最高分 Concat 变体的复现。
- 歌曲转为 44.1 kHz 单声道，6 秒分段、1 秒重叠处理，再恢复原始采样率和长度。
- 参考片段固定为 3 秒，默认按歌手编码器训练代码使用 16 kHz。
- 上游预计算脚本保留原始采样率，存在与编码器训练设置不一致的情况。因此界面保留
  44.1 kHz 参考采样率作为实验选项，并在处理记录中保存选择。
- 分段推理与论文整段评估不同，可能影响音质。论文指标不能作为本应用的实测指标。

具体核对记录见 [模型说明](docs/MODEL_NOTES.md)。代码、模型、歌曲的授权范围不同，
见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 开发与测试

在 Windows PowerShell 的项目根目录运行：

```powershell
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
# 另外安装 Node.js 22+ 后，验证时间线播放与选区逻辑
node --test tests/web.test.mjs
```

没有下载模型时，真实权重集成测试会跳过，其余测试仍可运行。
测试中的合成音只验证程序行为，不是歌声分离效果证明。

Git 不跟踪模型、音频、导出结果、缓存和运行环境。

## 接下来

- 用真实双人歌曲比较换参考、目标缺席、同时唱和声等情况。
- 比较直接提取与先去伴奏两条路线。
- 增加可保存和重新打开的工程文件，以及更细致的歌手片段标注。
- 在 RTX 5090 上验收桌面便携版，并测量长音频的性能。

应用代码采用 MIT License；外部模型权重不在此授权范围内。
