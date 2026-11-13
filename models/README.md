# 模型文件

运行项目根目录的 `download_models.bat`，或：

```powershell
.\.venv\Scripts\python.exe -m singer_extractor.cli download-models
```

需要 `embedding.pth` 和 `film.pth`，共约 29 MB。下载链接来自
[论文作者仓库](https://github.com/jocelynxu01/singer-separation-paper)。
文件 ID、SHA-256 和架构参数见 `manifest.json`。下载后以及模型加载前都会核对校验值。

推理阶段不自动下载权重。模型不在 Git 版本控制和源代码压缩包中。
网络受限时，可按 manifest 中的 ID 打开
`https://drive.google.com/file/d/文件ID/view`，手动下载并按上述名称保存到本目录。

模型权重不属于本项目的 MIT 授权范围，详见 `THIRD_PARTY_NOTICES.md`。
