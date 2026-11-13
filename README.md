# 哦，金金的音道分离

从双人歌曲中先分离伴奏，再生成两条候选人声；试听后选择要保留的声音。
面向 Windows + NVIDIA GPU，提供中文多轨时间线、片段预览和完整 WAV 导出。

**v0.5.0：双阶段分离，只发布 Windows 精简在线安装版。**
[下载发布版](https://github.com/MarginalEmbers/singer-extractor-local/releases/tag/v0.5.0) · [更新记录](CHANGELOG.md)

默认模型是 [Mel-Band RoFormer](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model)
加 [UNMIXX](https://github.com/jihoojung0106/unmixx)，
UNMIXX 论文为 [Untangling Highly Correlated Singing Voices Mixtures](https://arxiv.org/abs/2601.12802)。
旧版 Singer-informed FiLM 参考歌手模式仍可选。本项目是工程封装，不是原创模型或作者官方应用。

**实验版。** 一首真实双人歌曲的试听获得用户“进步非常明显”的反馈；这不代表所有歌曲，
也未逐段确认整首的歌手身份。候选编号不等于固定歌手，可能出现串音、失真或中途换人。
目标仍是保留同一歌手的主唱和和声，但目前不能保证收齐该歌手的所有声音。

## 它做什么

- 默认双轨分离无需独唱参考：原曲 → 去伴奏 → 候选 1 / 2 → 试听选择 → 目标轨。
- 五轨同位置试听：原曲、两条候选、选定目标、残差；支持循环、缩放、平移和精确选区。
- 选中的候选可写入整首或局部；发现换人时框选该段，改选另一候选。也可静音和撤销。
- 每次分离只更新候选轨，**不会自动改写目标轨**；最新候选替换上次候选，已选入的目标保留。
- 保留旧版 3 秒参考、独立参考文件及 FiLM 对照模式，参考默认修正为 44.1 kHz。
- 导出目标、残差和不含歌曲路径的 JSON 记录；单声道浮点 WAV，保持原采样率、长度和时间位置。
- 所有音频留在本机；只连接官方依赖及作者模型下载地址，不使用在线音频推理服务。

## Windows 桌面版

1. 从 Releases 下载 `Windows-Online.zip`，**完整解压**到可写文件夹。
2. 双击 `哦，金金的音道分离.exe`。环境缺失时，点击“安装运行环境”。
3. 首次安装会下载约 **3–4 GB** Python、Qt 和 GPU 推理库；请预留至少 **12 GiB** 空间。
4. 检查通过后点击“启动软件（GPU）”，从作者公开地址准备并校验约 919 MB 双阶段模型与来源代码。
5. 此后双击主 EXE，自动检查并打开独立窗口，模型就绪后可离线处理。

小包不再内置 Python/PyTorch，**减少的是发布包大小，不是总下载量或最终磁盘占用**。
发布包约 **17 MB**；Python、Qt、CUDA 运行库和模型均在首次使用时另行下载。
保留 EXE 旁的 `app`、`tools`、锁文件和文件清单，转发时请发整个 ZIP。
环境装在 `%LOCALAPPDATA%\JinjinAudio\runtime-cu128-py311-v1`，不修改系统 Python 或 PATH。
仍使用 PyTorch **2.7.1+cu128**；保留 CUDA GPU 加速；新版使用新的双阶段模型。
需要 Windows 10/11 x64（系统自带 .NET Framework 4.x）和兼容的 NVIDIA 驱动，无需 CUDA Toolkit。
“检查运行环境.exe”可重新检查或修复：Python、依赖版本、DLL 加载、GPU 实际运算、模型和写入权限。
GPU 不可用时明确提示更新驱动，可选择 CPU 继续；DLL 错误提供微软 VC++ x64 运行库入口。
安装失败显示步骤和日志，允许重试；模型缺失/损坏由主窗口重新下载。
界面使用内置引擎，本机服务监听随机 `127.0.0.1` 端口；不会启动外部浏览器。

本次不发布完整便携包。旧版已安装环境可复用；如提示新增依赖缺失，按界面安装或修复即可。

导出在软件旁 `data/outputs`，可从“文件 → 打开导出文件夹”进入。
模型、缓存、日志分别在 `data/models`、`data/cache`、`data/logs`。
程序未作商业代码签名；发布页提供 SHA-256 用于核对下载文件。
Windows x64 + RTX 5080 已测试；RTX 5090 尚需在接收方电脑验收。
详见[验证记录](docs/VALIDATION.md)和[桌面构建说明](docs/DESKTOP_BUILD.md)。

## 源代码运行（开发者）

源代码版保留原有浏览器入口。下面的安装步骤不适用于已经下载桌面发布包的用户。

1. 安装 NVIDIA 驱动，以及官方 [uv](https://docs.astral.sh/uv/getting-started/installation/)。
2. 下载仓库 ZIP 并解压，或使用 Git 克隆。
3. 双击 `setup.bat`，创建独立 Python 3.11 环境并安装依赖。
4. 双击 `download_models.bat`，准备并校验双阶段与旧版对照模型。
5. 双击 `check_environment.bat` 检查显卡，再双击 `start.bat`。
6. 浏览器会打开 `http://127.0.0.1:7860`。处理期间保留启动窗口；关闭窗口即停止服务。

安装不会替换系统 Python。PyTorch 使用固定的 `2.7.1+cu128` 构建，支持本项目
RTX 5080 测试环境；朋友的 RTX 5090 尚需单独验收。下载 PyTorch 约需 3 GB。
首次安装完成后，音频推理不需要访问网络。详细验证范围见 [验证记录](docs/VALIDATION.md)。

## 第一次使用

1. 导入 WAV、FLAC、MP3 或 OGG；其他格式先转换为 WAV。
2. 保持“分离方式”为“双轨分离（推荐）”，框选约 30–60 秒试听片段，或直接处理整首。
3. 点击“分离 / 重做选区”或“处理整首歌曲”，等待两阶段完成。
4. 分别点击候选 1 / 2 的“试听”，确认哪一轨以想要的歌手为主；编号不固定。
5. 右侧选择“候选 1”或“候选 2”，点击“将选中候选写入选区 / 整首”。此时目标轨才更新。
6. 若局部换人，可框选那段、改选另一候选并写入选区；静音、撤销和局部重做仍可用。
7. 试听目标轨后导出。整首导出要求目标轨所有区域已选入或明确静音。

只有使用“参考歌手提取（旧版对照）”时，才需要选择 3 秒独唱参考。
该模式可能额外下载约 29 MB 作者权重，不作为当前推荐路线。

没有歌曲时，可点击“载入功能自检音频”验证流程；它是合成音，不用于判断歌声分离质量。

快捷键：Space 播放/暂停，A/B 对比原曲/目标，I/O 设置选区边界，Ctrl+Z 撤销。
输入框和按钮聚焦时保留控件自己的键盘行为。缩放后通过下方“平移”滑块移动视图。

点击导出后，桌面版结果保存在软件旁 `data/outputs/`，源代码版保存在项目 `outputs/` 下。
每次导出使用独立目录，不覆盖以前的结果。
页面同时提供目标、残差、JSON 和 ZIP 下载。未处理区域必须先提取或明确标记静音才能导出。
片段重做在选区内部采用约 5 ms 淡化，选区外的样本保持不变。
`residual.wav` 是“单声道原音减去目标输出”，包含伴奏、其他歌手以及分离误差，
**不是保证纯净的另一位歌手音轨**。模型也不能保证目标未出现时完全静音。

输出采用浮点 WAV，避免超出幅度范围时在写文件阶段削波。界面试听对所有音轨应用
相同的安全增益，导出保留模型原始幅度；若峰值超过 0 dBFS，请在混音软件中降低音量。
没有做分段响度归一化。

时间线项目和撤销历史仅在本次运行期间可用，**关闭软件前请导出**。
最多保留 3 个项目，撤销最多 10 步（历史超过 64 MB 时会提前淘汰旧步骤，至少保留最近一步）。
本版限制单文件 500 MB、最长 60 分钟；长音频会占用较多内存和缓存磁盘。
桌面版 `data/cache/`、源代码版 `.cache/workspaces-v2/` 保留本机试听缓存，
不是可重新打开的工程文件；关闭软件后可手动清理。

源代码升级：覆盖源代码后重新运行 `setup.bat`，已有模型无需重复下载。
若浏览器仍显示旧界面，请刷新页面。

## 命令行（旧版 FiLM 对照）

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

默认管线保留输入立体声进行 44.1 kHz Mel-Band RoFormer 去伴奏，使用作者 8 秒分段、50% 重叠配置。
再将混合人声转为 24 kHz 单声道送入 UNMIXX，使用 60 秒长段、30 秒重叠进行候选匹配和拼接。
模型先后加载并释放，降低显存占用。最终恢复输入采样率和样本数量；**升采样不会恢复 12 kHz 以上的细节**。
重叠匹配比较两种排列，帮助减少换人，但无法证明歌手身份；静音、相近声线、复杂和声仍可能失败。
重做不同选区后，候选编号可能变化，需要重新试听。

固定版本、SHA-256 和作者链接保存在 `singer_extractor/two_stage_manifest.json`。
下载原始归档后先校验，再只提取推理所需文件；每次加载前核对并恢复被修改的来源文件。
第三方实现与权重不放入 GitHub 源码或安装包，不宣称其适用本项目的 MIT 授权。
完整引用与授权边界见 [第三方说明](THIRD_PARTY_NOTICES.md)。

以下保留旧版 FiLM 的工程说明：

本项目基于 Jocelyn Xu 和 Minje Kim 的
[Singer-Informed Vocal Source Separation for Multi-Singer Music Mixtures](https://arxiv.org/abs/2608.14516)
及[作者代码](https://github.com/jocelynxu01/singer-separation-paper)，不宣称原创模型。

- 选择 **FiLM / target-vocal loss only** 权重；本项目不是论文最高分 Concat 变体的复现。
- 歌曲转为 44.1 kHz 单声道，6 秒分段、1 秒重叠处理，再恢复原始采样率和长度。
- 参考片段固定为 3 秒，当前源码默认使用 44.1 kHz，与公开的分离模型参考特征生成流程一致。
  已发布的 v0.4.0 及更早版本默认使用 16 kHz；旧版本可在“模型与设备”中手动选择 44.1 kHz。
- 编码器自身训练加载器使用 16 kHz，但分离模型使用预先计算的特征，两者不能混为一谈。
  2026-11-13 的小样本对照支持改用 44.1 kHz，仍存在提错歌手的失败案例；这不是质量保证。
  界面保留 16 kHz 作为旧版对照，每次处理记录保存实际选择。
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
