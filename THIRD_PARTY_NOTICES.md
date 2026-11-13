# Third-party components

This application is an engineering wrapper and inference adaptation, not a new
separation model or an official implementation by the paper's authors.

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
on first launch, checked against `models/manifest.json`, and stored in `data/models`.
Neither the portable package nor the GitHub source archive includes the checkpoints.
