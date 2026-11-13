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

Python dependencies retain their respective licenses and are installed separately.
