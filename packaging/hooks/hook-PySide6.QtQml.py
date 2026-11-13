"""The QWidget UI uses WebEngine's built-in resources, no external QML applications.

Keep the QtQml shared libraries needed by WebEngine, but do not collect every
installed QML plugin (including unrelated Charts, 3D, demos and their dependencies).
"""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
