"""Loopback-only browser UI. All processing and exports stay on this computer."""

import os
from functools import lru_cache

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_OFFLINE"] = "1"

import gradio as gr

from .audio import crop_audio, read_audio
from .engine import Extractor, run_job
from .weights import ROOT

os.environ["GRADIO_TEMP_DIR"] = str(ROOT / ".cache" / "gradio")


@lru_cache(maxsize=1)
def get_extractor(device):
    return Extractor(device=device)


def hear_reference(song, reference_file, start):
    if not song and not reference_file:
        raise gr.Error("请先选择歌曲或参考音频。")
    try:
        audio, rate = read_audio(reference_file or song)
        clip, _ = crop_audio(audio, rate, float(start), 3.0)
        if len(clip) < 3 * rate:
            raise ValueError("这个位置之后不足 3 秒，请选择更早的起点。")
        return rate, clip
    except (ValueError, OSError) as exc:
        raise gr.Error(str(exc)) from exc


def process(
    song,
    reference_file,
    reference_start,
    preview_start,
    preview_duration,
    device,
    embedding_rate,
    whole=False,
    progress=gr.Progress(),
):
    if not song:
        raise gr.Error("请先选择歌曲。")
    progress(0, desc="正在检查模型并准备音频")
    try:
        engine = get_extractor(device)
        paths, report_path, report = run_job(
            engine,
            song,
            reference_file,
            float(reference_start),
            0.0 if whole else float(preview_start),
            None if whole else float(preview_duration),
            embedding_rate=int(embedding_rate),
            progress=lambda value, description: progress(value, desc=description),
        )
    except (ValueError, RuntimeError, OSError) as exc:
        raise gr.Error(str(exc)) from exc
    message = (
        f"已处理 {report['duration_seconds']:.2f} 秒音频；"
        f"耗时 {report['elapsed_seconds']:.2f} 秒；设备：{report['device']}。\n\n"
        "输出为单声道 WAV；请试听确认目标歌手、串音和失真。"
    )
    if report["target_peak"] > 1:
        message += "\n\n输出峰值超过 0 dBFS，导出的浮点 WAV 保留了数值；播放或混音时请降低音量。"
    return (
        str(paths["original"]),
        str(paths["target"]),
        message,
        [str(paths["target"]), str(paths["residual"]), str(report_path)],
    )


def process_full(
    song,
    reference_file,
    reference_start,
    preview_start,
    preview_duration,
    device,
    embedding_rate,
    progress=gr.Progress(),
):
    return process(
        song,
        reference_file,
        reference_start,
        preview_start,
        preview_duration,
        device,
        embedding_rate,
        whole=True,
        progress=progress,
    )


def build_app():
    with gr.Blocks(title="Singer Extractor · 目标歌手提取", analytics_enabled=False) as demo:
        gr.Markdown(
            "# 提取你想听的那位歌手\n"
            "选择歌曲和一段 **只有目标歌手演唱的 3 秒参考**，先试听，再导出整首。\n\n"
            "本地运行 · 研究原型 · 输出单声道 · 重叠和声可能仍有串音"
        )
        with gr.Row():
            with gr.Column():
                song = gr.File(label="1 · 选择歌曲", file_types=[".wav", ".flac", ".mp3", ".ogg"])
                reference = gr.File(
                    label="2 · 可选：单独的目标歌手参考音频（留空则使用歌曲）",
                    file_types=[".wav", ".flac", ".mp3", ".ogg"],
                )
                reference_start = gr.Number(
                    label="参考片段起点（秒），从这里取 3 秒", value=0, minimum=0
                )
                hear = gr.Button("试听这 3 秒参考")
                reference_audio = gr.Audio(label="目标歌手参考", interactive=False)
            with gr.Column():
                preview_start = gr.Number(label="3 · 预览起点（秒）", value=0, minimum=0)
                preview_duration = gr.Number(
                    label="预览时长（秒）", value=30, minimum=1, maximum=120
                )
                gr.Markdown("建议预览包含两人同时演唱的片段。参考中不要混入另一位歌手。")
                with gr.Accordion("设备与实验设置", open=False):
                    device = gr.Dropdown(["auto", "cuda", "cpu"], value="auto", label="计算设备")
                    embedding_rate = gr.Dropdown(
                        [16000, 44100],
                        value=16000,
                        label="参考音频处理采样率",
                        info="默认跟随歌手编码器训练设置；44100 用于对照上游预计算流程。",
                    )
                preview = gr.Button("提取预览片段", variant="primary")
                full = gr.Button("提取整首歌曲")
        with gr.Row():
            original_audio = gr.Audio(label="原音（同一片段，单声道）", interactive=False)
            target_audio = gr.Audio(label="提取的目标歌手", interactive=False)
        status = gr.Markdown("等待选择歌曲。模型准备好后，日常处理可以断网进行。")
        downloads = gr.File(
            label="下载：目标音轨 / 残差 / 处理记录", file_count="multiple", interactive=False
        )
        gr.Markdown(
            "整首导出保持原曲采样率、长度和时间位置。残差包含伴奏、其他歌手与分离误差。"
            "参考歌手未演唱的段落仍可能有残留，目前需要试听确认。"
        )
        inputs = [
            song,
            reference,
            reference_start,
            preview_start,
            preview_duration,
            device,
            embedding_rate,
        ]
        outputs = [original_audio, target_audio, status, downloads]
        hear.click(
            hear_reference, [song, reference, reference_start], reference_audio, api_name=False
        )
        preview.click(
            process,
            inputs,
            outputs,
            concurrency_id="inference",
            concurrency_limit=1,
            api_name=False,
        )
        full.click(
            process_full,
            inputs,
            outputs,
            concurrency_id="inference",
            concurrency_limit=1,
            api_name=False,
        )
    return demo


def launch():
    build_app().queue(default_concurrency_limit=1).launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        allowed_paths=[str(ROOT / "outputs")],
        blocked_paths=[str(ROOT / "models"), str(ROOT / ".venv"), str(ROOT / ".git")],
        max_file_size="500mb",
        theme=gr.themes.Soft(),
    )
