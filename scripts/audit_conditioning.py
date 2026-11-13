"""Offline reference-rate diagnostic on three independent vocal stems.

This small artificial-mixture test is not a representative quality benchmark.
No audio is downloaded or uploaded. See docs/MODEL_NOTES.md for source URLs.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import torch

from singer_extractor.audio import read_audio, resample_exact
from singer_extractor.engine import Extractor


def rms(wave):
    return float(np.sqrt(np.mean(np.asarray(wave, dtype=np.float64) ** 2)))


def si_sdr(predicted, target):
    predicted = np.asarray(predicted, dtype=np.float64).copy()
    target = np.asarray(target, dtype=np.float64).copy()
    predicted -= predicted.mean()
    target -= target.mean()
    projection = target * np.dot(predicted, target) / max(np.dot(target, target), 1e-20)
    return float(
        10
        * np.log10(
            max(np.dot(projection, projection), 1e-20)
            / max(np.sum((predicted - projection) ** 2), 1e-20)
        )
    )


def audit(engine, paths):
    rate = 44100
    sources, references, metadata = {}, {}, []
    for index, path in enumerate(paths, 1):
        audio, original_rate = read_audio(path)
        audio = resample_exact(audio, original_rate, rate)
        if len(audio) < 8 * rate:
            raise ValueError(f"{path.name}: at least 8 seconds required")
        reference, clip = audio[: 3 * rate], audio[int(3.5 * rate) : 8 * rate]
        if min(rms(reference), rms(clip)) < 1e-5:
            raise ValueError(f"{path.name}: reference or test clip is nearly silent")
        references[index] = reference
        sources[index] = (clip * (0.1 / rms(clip))).astype(np.float32)
        metadata.append(
            {
                "index": index,
                "file": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    records = []
    for a, b in itertools.combinations(sources, 2):
        mixture = sources[a] + sources[b]
        for target, other in ((a, b), (b, a)):
            for embedding_rate in (16000, 44100):

                def extract(wave, target=target, embedding_rate=embedding_rate):
                    return engine.extract(wave, rate, references[target], rate, embedding_rate)

                output = extract(mixture)
                absent = extract(sources[other])
                alone = extract(sources[target])
                score = si_sdr(output, sources[target])
                baseline = si_sdr(mixture, sources[target])
                records.append(
                    {
                        "pair": [a, b],
                        "target": target,
                        "embedding_rate": embedding_rate,
                        "target_si_sdr_db": score,
                        "interferer_si_sdr_db": si_sdr(output, sources[other]),
                        "mixture_target_si_sdr_db": baseline,
                        "target_si_sdri_db": score - baseline,
                        "solo_target_si_sdr_db": si_sdr(alone, sources[target]),
                        "absent_output_rms_vs_input_db": float(
                            20 * np.log10(max(rms(absent), 1e-20) / rms(sources[other]))
                        ),
                        "absent_output_rms_vs_solo_target_db": float(
                            20 * np.log10(max(rms(absent), 1e-20) / max(rms(alone), 1e-20))
                        ),
                    }
                )
                print(json.dumps(records[-1]), flush=True)

    summary = {}
    for embedding_rate in (16000, 44100):
        rows = [r for r in records if r["embedding_rate"] == embedding_rate]
        summary[embedding_rate] = {
            "evaluations": len(rows),
            "target_si_sdri_mean_db": float(np.mean([r["target_si_sdri_db"] for r in rows])),
            "target_better_than_mixture_count": sum(r["target_si_sdri_db"] > 0 for r in rows),
            "target_closer_than_interferer_count": sum(
                r["target_si_sdr_db"] > r["interferer_si_sdr_db"] for r in rows
            ),
        }
    return {
        "scope": "Three short independent stems; three equal-RMS artificial mixtures, "
        "both target directions. No accompaniment. Not a representative benchmark.",
        "reference_seconds": [0, 3],
        "evaluation_seconds": [3.5, 8],
        "source_rms": 0.1,
        "inference": "Extractor.extract: 6-second chunks, 1-second overlap; pad/trim final chunk",
        "device": engine.device,
        "gpu": torch.cuda.get_device_name() if engine.device == "cuda" else None,
        "model_hashes": {item["name"]: item["sha256"] for item in engine.config["files"]},
        "sources": metadata,
        "summary": summary,
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs=3, type=Path, help="Three independent vocal WAV files")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = Extractor(args.model_dir, args.device)
    report = audit(engine, args.sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
