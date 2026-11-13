# Library sources and replacement

The application source and build scripts are provided in this repository. The
following unmodified runtime libraries retain their own licenses and copyrights.
Release binaries include copies of their original license files when supplied by
the wheel, plus the accompanying LGPL/GPL license texts and additional notices.

| Library | Source / build information |
|---|---|
| Python 3.11.16 | https://www.python.org/downloads/source/ ; https://github.com/python/cpython/tree/v3.11.16 |
| PySide6 / Shiboken 6.12.0 | https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/ |
| Qt 6.12.0 | https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/ ; https://doc.qt.io/qt-6/windows-building.html |
| Qt WebEngine 6.140.0, including Chromium | https://code.qt.io/cgit/qt/qtwebengine.git/?h=v6.140.0 ; https://wiki.qt.io/QtWebEngine/Qt6Build |
| PyTorch 2.7.1 | https://github.com/pytorch/pytorch/tree/v2.7.1 |
| libsndfile | https://github.com/libsndfile/libsndfile ; wheel-specific notices in LICENSES/dependencies/soundfile |
| NumPy / SciPy | https://github.com/numpy/numpy ; https://github.com/scipy/scipy ; exact versions in DEPENDENCIES.json |
| NVIDIA CUDA 12.8 | https://docs.nvidia.com/cuda/archive/12.8.0/eula/index.html |
| NVIDIA cuDNN | https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html |

Qt/PySide use the applicable LGPL option. Qt WebEngine also includes Chromium's
third-party licenses, reproduced in `QtWebEngine-Third-Party-Notices.txt` from
https://doc-snapshots.qt.io/qtwebengine/qtwebengine-licensing.html .
For full corresponding source, include Qt WebEngine's Chromium submodule when
following the official source/build instructions. The runtime ships shared
libraries under `_internal/PySide6`, `_internal/shiboken6`, `_internal/torch/lib`
and `_internal/_soundfile_data` rather than statically linking them into the app.

You may replace the LGPL libraries with compatible modified builds, and reverse
engineer this application for debugging those modifications. This application
does not add restrictions to those rights. The repository includes the source and
packaging configuration needed to rebuild the application. The MIT license applies
to the application code; NVIDIA runtime libraries and research checkpoints have
separate terms. No model weight license is inferred from the application license.
