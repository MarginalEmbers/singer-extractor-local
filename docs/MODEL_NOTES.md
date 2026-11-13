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

默认采用训练数据加载器的 16 kHz，提供 44.1 kHz 实验选项，并在每次报告中记录。
尚未使用真实歌曲比较两种选择，也尚未向作者确认该差异。

## 明确未验证的内容

- 没有复现论文的 SI-SDR/FAD 表格。
- 没有声称取得论文中的 5.58 dB。
- 没有真实歌声串音、音色保真或目标缺席的定量结论。
- 未验证三位以上歌手、同一歌手多轨叠唱的完整保留、重度混响和现场录音。
- 未验证先去伴奏一定比直接输入原曲好。

资料：[论文](https://arxiv.org/abs/2608.14516)、
[作者实现](https://github.com/jocelynxu01/singer-separation-paper/tree/3f6ce09d53750b55f52801a24efff369dbd04846)。
