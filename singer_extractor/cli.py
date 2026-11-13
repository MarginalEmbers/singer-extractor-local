import argparse
import json

from .engine import Extractor, run_job
from .weights import ROOT, download_weights


def main():
    parser = argparse.ArgumentParser(description="Local target singer extraction (experimental)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("download-models", help="Prepare two-stage and legacy author models")
    ui = commands.add_parser("ui", help="Open the local timeline interface")
    ui.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    ui.add_argument("--port", type=int, default=7860)
    commands.add_parser("doctor", help="Check GPU, packages and model hashes")
    extract = commands.add_parser("extract", help="Extract using a 3-second reference")
    extract.add_argument("song")
    extract.add_argument("--reference", help="Defaults to the input song")
    extract.add_argument("--reference-start", type=float, default=0)
    extract.add_argument("--start", type=float, default=0)
    extract.add_argument("--duration", type=float)
    extract.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    extract.add_argument("--embedding-rate", type=int, choices=[16000, 44100], default=44100)
    extract.add_argument("--output-dir", default=str(ROOT / "outputs"))
    args = parser.parse_args()
    try:
        if args.command == "download-models":
            from .two_stage_assets import prepare_assets

            prepare_assets(progress=lambda value, text: print(text, flush=True))
            download_weights()
        elif args.command == "ui":
            from .ui import launch

            launch(inbrowser=not args.no_browser, port=args.port)
        elif args.command == "doctor":
            from .doctor import diagnose

            print(json.dumps(diagnose(), ensure_ascii=False, indent=2))
        else:
            engine = Extractor(device=args.device)
            paths, report_path, _ = run_job(
                engine,
                args.song,
                args.reference,
                args.reference_start,
                args.start,
                args.duration,
                args.output_dir,
                args.embedding_rate,
            )
            print(f"Target: {paths['target']}\nReport: {report_path}")
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
