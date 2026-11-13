# 模型接入记录

核对来源：作者仓库提交 `3f6ce09d53750b55f52801a24efff369dbd04846`。
本项目使用作者发布的 clean embedding + FiLM（无 residual loss）权重。

## 参数与计算

| 项目 | 设置 |
|---|---|
| 输入 | 单声道，44,100 Hz |
| 分离 STFT | Hann window，4096 点，hop 1024，center=True |
| 有效输入频率 bins | 1487，对应上游 16 kHz bandwidth 设置 |
| 输出频率 bins | 2049 |
| 分离网络 | 512 hidden size，3 层双向 LSTM，2 处 FiLM |
| 歌手编码器 | 2 层 GRU，hidden size 32，FFT 1024，hop 256 |
| 参考 | 3 秒，按峰值归一化 |
| 波形重建 | 预测幅度 + 混合音频相位，ISTFT 指定原分段长度 |
| 长音频 | 6 秒窗口，1 秒重叠，交叉淡化并按权重归一化 |

权重采用 `torch.load(..., weights_only=True)` 读取，先核对 SHA-256，
再执行 `load_state_dict(..., strict=True)`。缺少模型时直接报错，不使用随机参数代替。

## 为什么不默认使用 Concat

核对的上游 `OpenUnmix_Embedding.forward()` 先把 32 维参考特征接在完整
2049 个频率 bins 后，再截取前 `max_bin + emb_dim` 个值。
使用 `max_bin=1487` 时，只保留前 1519 个值，追加的参考特征不在其中。

在这份代码及这组参数下，固定输入、改变参考特征，输出最大绝对差为 0。
这是对公开实现特定配置的代码核对，**不等于已经审计或复现论文全部实验**。
不能通过修改裁剪顺序就声称修好了既有训练权重；训练行为也可能随之改变。

因此本应用先使用条件路径明确的 FiLM。改写后的 FiLM 与上游类加载相同权重，
对同一测试张量的输出最大绝对差为 0（CPU，float32）。
真实 FiLM 权重测试也检查了：更换参考音频后，输出确实不同。
这些检查证明条件路径可用，不证明输出一定属于正确歌手。

## 参考采样率的不一致

歌手编码器训练数据加载器 `singer_embedding/Customized_DatasetSV.py` 使用
`librosa.load(..., sr=16000)`；`scripts/precalculate_embeddings.py` 使用 `sr=None`。
上游歌曲准备流程又使用 44.1 kHz。不能把两条流程当作完全一致。

已发布的 v0.4.0 及更早版本默认使用 16 kHz，这只对应编码器训练加载器，
没有对应到分离模型消费的预计算特征。当前源码改为默认 44.1 kHz，保留 16 kHz 对照。
`train_1model_duet_1embedding_film.py` 直接载入 `DUET_clean_embeddings`，
`precalculate_embeddings.py` 对原采样率音频取 3 秒并按峰值归一化，歌曲构造脚本输出 44.1 kHz。
权重附带配置记录歌曲采样率为 44.1 kHz，但未明确记录参考采样率，训练提交为 `fb672c9`。
因此这个修正依据公开流程及下述小样本实验，尚未获得作者对训练过程的确认。

## 2026-11-13：真实音频诊断

用户反馈歌曲输出同时保留两位歌手。该次参考片段未确认是单人独唱，
也没有独立人声真值，不能为这首歌计算有效的目标歌手 SI-SDR。

核对两份权重的 SHA-256 与严格加载均通过；使用相同真实音频和权重，
改写编码器与公开编码器的特征最大差为 0，完整 6 秒推理波形相对 RMS 差约 `6e-6`，
最大绝对差小于 `2.5e-5`（RTX 5080、float32）。
同一首歌的 10 个不同参考位置、两种参考采样率共 20 次运行，输出确实不同。
这些结果排除了明显的权重损坏或参考条件完全失效，不能证明识别了正确身份。

进一步使用 [UNMIXX 作者示例页](https://unmixx.github.io/) 标记为 Ground Truth 的
3 条 [MedleyVox](https://zenodo.org/records/7984549) 独立人声：
LizNelson_Rainfall、NightPanther_Fire、Meaxic_TakeAStep。
选取不同艺术家曲目的音轨两两人工混合，共 3 组，每组分别提取两条目标，计 6 次。
每条独立轨前 0–3 秒作参考，3.5–8 秒用于混合，两者不重叠；
每条源轨归一化至 RMS 0.1，不加伴奏；使用应用实际的 6 秒分段、尾部补零流程。

| 参考采样率 | 相比不处理的 SI-SDR 平均改善 | 有改善的次数 |
|---|---:|---:|
| 16 kHz（旧默认） | -4.28 dB | 2 / 6 |
| 44.1 kHz（新默认） | +4.58 dB | 5 / 6 |

这是 3 条短音轨上的诊断，不是完整 MedleyVox 评测，不是论文复现，
也不是用户歌曲的质量分数。示例页按独立音轨标记真值，未额外核验歌手身份标注。
44.1 kHz 下仍有一次改善为 -7.55 dB，输出更接近干扰人声。
在对应的“目标缺席、仅有另一条人声”测试中，输出 RMS 比输入还高 1.13 dB，
说明当前模型不能可靠保证目标不唱时静音。不能用平均分掩盖这个失败。

复现脚本为 `scripts/audit_conditioning.py`，逐条记录在
`docs/validation/model-audit-2026-11-13.json`。测试音频未纳入仓库。
数据采用 MedleyVox 的 CC BY-NC-SA 4.0 条款，与应用 MIT 许可分别适用。

复现时，从 JSON 中的 `sources[].url` 下载 3 条样例，按索引保存为
`.cache/audit/public-source-1.wav` 至 `public-source-3.wav`。
在已安装项目依赖和官方权重的 Windows PowerShell 项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_conditioning .cache/audit/public-source-1.wav .cache/audit/public-source-2.wav .cache/audit/public-source-3.wav --model-dir models --device cuda --output .cache/audit/report.json
```

脚本只进行本地计算，不上传或自动下载音频；对照报告保留每条输入的 SHA-256。

## 明确未验证的内容

- 没有复现论文的 SI-SDR/FAD 表格。
- 没有声称取得论文中的 5.58 dB。
- 尚无有代表性的真实歌曲串音、音色保真或目标缺席评测；以上仅为小样本诊断。
- 未验证三位以上歌手、同一歌手多轨叠唱的完整保留、重度混响和现场录音。
- 未验证先去伴奏一定比直接输入原曲好。

资料：[论文](https://arxiv.org/abs/2608.14516)、
[作者实现](https://github.com/jocelynxu01/singer-separation-paper/tree/3f6ce09d53750b55f52801a24efff369dbd04846)。
