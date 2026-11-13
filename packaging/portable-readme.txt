哦，金金的音道分离 · Windows 桌面便携版

使用方法
1. 把压缩包完整解压到可写文件夹。
2. 双击“哦，金金的音道分离.exe”。无需安装 Python，也不会打开浏览器。
3. 第一次启动会自动下载并校验约 29 MB 模型，请保持联网。
4. 模型准备完成后，可断网进行本机音频处理。

请保留 EXE 旁的 _internal 文件夹，不要只把 EXE 单独复制给朋友。
包中包含 Python、Qt 界面引擎、PyTorch 和 CUDA 运行库，因此体积较大。
显卡仍需要机器本身已有的 NVIDIA 驱动；不需要单独安装 CUDA Toolkit。

操作
导入歌曲 → 拖选 A 独唱的 3 秒作为参考 → 框选一个片段试听 → 处理整首 → 导出。
可以同步对比原曲、目标 A、残差，局部重做、静音与撤销。
没有歌曲时，可使用“功能自检音频”检查操作流程，它不是音质示例。

文件在哪里
data/models：首次下载的模型，下次启动重复使用。
data/outputs：已导出的目标、残差、处理记录和 ZIP。
data/cache：时间线试听缓存，关闭软件后可手动清理。
data/logs：错误日志。启动失败可发送日志供排查。
菜单“文件 → 打开导出文件夹”可以直接找到结果。

重要说明
编辑历史仅在本次运行期间保留，关闭前请导出。
这是研究原型，复杂和声可能串音或失真；请试听确认。
Windows x64 + NVIDIA GPU；开发机 RTX 5080 已测，RTX 5090 尚待接收方验收。
本版本没有商业代码签名，Windows 可能显示“未知发布者”。请核对来源和 SHA-256。

代码和构建方法：https://github.com/MarginalEmbers/singer-extractor-local
模型引用
Jocelyn Xu、Minje Kim（2026）：Singer-Informed Vocal Source Separation for Multi-Singer Music Mixtures。
论文：https://arxiv.org/abs/2608.14516
作者代码：https://github.com/jocelynxu01/singer-separation-paper
使用变体：FiLM / target-vocal loss only；参考编码器使用作者 clean embedding 权重。
权重下载地址和 SHA-256 见 _internal/models/manifest.json，下载链接来自作者仓库。
推理网络基于作者代码及 Open-Unmix（https://github.com/sigsep/open-unmix-pytorch）改编。
本程序提供界面、分段推理和打包，不宣称原创模型，也不是作者官方应用。
模型来自论文作者公开地址，未随安装包再分发；模型授权不包含在本程序 MIT License 内。
第三方组件许可见 THIRD_PARTY_NOTICES.md 和 LICENSES 文件夹。
