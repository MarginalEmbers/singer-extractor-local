# Third-party components

This application is an engineering wrapper and inference adaptation, not a new
separation model or an official implementation by the paper's authors.

## Default two-stage pipeline (v0.5.0)

- **UNMIXX: Untangling Highly Correlated Singing Voices Mixtures**:
  [paper](https://arxiv.org/abs/2601.12802),
  [author repository](https://github.com/jihoojung0106/unmixx), pinned commit
  `8e750521b5942f4717656cac86a23cf0bd90dea5`; checkpoint `ckpt/best.ckpt`.
- **Mel-Band RoFormer**: [implementation and training credits](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model),
  pinned commit `25f44ffb55ee3c301281bba21b2d6d311cb69ae2`;
  [KimberleyJSN weights](https://huggingface.co/KimberleyJSN/melbandroformer),
  revision `ac9b0614ab3cd7f77219e18ba494dfd93956c348`, `MelBandRoformer.ckpt`.
  See the upstream README for its original paper, lucidrains, ZFTurbo and dataset contributor credits.

The online installer does **not** redistribute these upstream implementations or
checkpoints. On first use it downloads pinned archives/weights directly from the
above sources, validates SHA-256, and extracts an allowlist of inference files.
No blanket MIT grant is asserted for these models, checkpoints, training data or
upstream code; consult the respective authors for applicable use/redistribution terms.

The application's adapter omits UNMIXX training/Hub imports and replaces only the
base-class metadata constructor and an identity-length padding helper. RoFormer
absolute imports are redirected to isolate the downloaded modules. Learned network
operations and strict checkpoint loading are retained. The application implements
long-window inference, overlap assignment, candidate selection and timeline editing.
Author-demo agreement and the limits of the local quality checks are documented in
`docs/MILESTONE_M1.md`; paper scores are not claimed as application benchmarks.

Third-party runtime dependencies include PyYAML, librosa, NumPy/SciPy, einops,
rotary-embedding-torch, beartype, numba/llvmlite and their dependencies. They are
installed from PyPI using pinned versions; their original license notices remain
in the dedicated runtime, separate from this application's MIT license.

## Legacy reference-conditioned pipeline

`singer_extractor/models.py` adapts the FiLM and singer-embedding inference
architecture from the `open-unmix-pytorch/` directory of:

- Jocelyn Xu and Minje Kim, [Singer-Informed Vocal Source Separation for
  Multi-Singer Music Mixtures](https://arxiv.org/abs/2608.14516).
- [Research code](https://github.com/jocelynxu01/singer-separation-paper), commit
  `3f6ce09d53750b55f52801a24efff369dbd04846`.
- [Open-Unmix](https://github.com/sigsep/open-unmix-pytorch), copyright 2019 Inria
  (Fabian-Robert Stöter, Antoine Liutkus).

The upstream Open-Unmix directory contains an MIT license, reproduced in
`LICENSES/Open-Unmix-MIT.txt`. The adapted architecture preserves the published
parameter names and computation order; training and dataset code are not bundled.

The application MIT license covers this repository's code. It does not grant
rights to the authors' model weights, training datasets, or users' recordings.
Weights are downloaded from the authors' links and are not committed or included
in source archives. Refer to the authors for their weight use and redistribution
terms; this repository does not assert that the checkpoints are MIT-licensed.

## Windows desktop distribution

The v0.5.0 **online package** ships the application source and the unmodified
uv 0.12.7 Windows installer helper ([source and release](https://github.com/astral-sh/uv/releases/tag/0.12.7)).
Its MIT and Apache-2.0 license texts are in `LICENSES/uv-MIT.txt` and
`LICENSES/uv-APACHE.txt`. It does not ship Python, PyTorch, CUDA or Qt binaries.
At the user's installation request, uv obtains Python 3.11.16, PyTorch 2.7.1+cu128
from the official PyTorch index, and dependencies from PyPI using the pinned
`requirements-runtime.lock` / `requirements-ui.lock` files. Installed packages
retain their original license files in the dedicated runtime's site-packages.
Qt shared libraries remain separate and replaceable in that environment; the
application imposes no additional restriction on modification or debugging.
The launcher's package-integrity check can be regenerated with the documented
build script when modifying the distributed application files.

The following description applies to the larger **v0.3.0 portable package**:

The Windows portable build bundles Python 3.11.16, PyTorch 2.7.1+cu128 and its
CUDA runtime libraries, PySide6 / Shiboken 6.12.0, Qt 6.12.0, Qt WebEngine
6.140.0 and the runtime dependencies pinned in `requirements-desktop.lock`.
Dependency licenses are separate from the MIT license of this application's code.
The binary package includes original notices in `LICENSES/dependencies`, the
Python license, LGPL/GPL texts, and a `DEPENDENCIES.json` build-environment inventory.
The inventory may also list build/test tools that are not imported by the application.

Qt/PySide are used under their applicable open-source terms. The shared libraries
remain separate and replaceable under `_internal/PySide6` and `_internal/shiboken6`.
This application imposes no additional restriction on modifying these libraries or
reverse engineering for debugging modifications to them. See
[library source locations](LICENSES/LIBRARY_SOURCES.md) and
[build instructions](docs/DESKTOP_BUILD.md) for rebuilding the application.
Unused QML plugins and the virtual keyboard are excluded from the desktop bundle.

NVIDIA's CUDA, cuDNN and related libraries retain NVIDIA's terms and notices;
they are not licensed under this application's MIT license. The application does
not bundle an NVIDIA driver or CUDA development toolkit.

Model checkpoints are fetched from the links published by the research authors
on first launch, checked against `singer_extractor/two_stage_manifest.json` (default) or `models/manifest.json` (legacy), and stored in `data/models`.
Neither the portable package nor the GitHub source archive includes the checkpoints.
