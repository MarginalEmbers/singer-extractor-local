"""Standalone Qt window with a bundled web engine, model setup and native downloads."""

import argparse
import logging
import sys
import threading
from pathlib import Path

from . import __version__
from .desktop_backend import APP_NAME, DesktopBackend, portable_directory
from .environment import startup_advice


def configure_logging(directory):
    from logging.handlers import RotatingFileHandler

    logs = directory / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        logs / "desktop.log", maxBytes=4 * 1024**2, backupCount=2, encoding="utf8"
    )
    logging.basicConfig(
        level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s"
    )
    # Windowed Python has no console; libraries must still have writable streams.
    if sys.stdout is None:
        sys.stdout = open(logs / "runtime.log", "a", encoding="utf8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    sys.excepthook = lambda kind, value, tb: logging.error(
        "Unhandled error", exc_info=(kind, value, tb)
    )
    threading.excepthook = lambda args: logging.error(
        "Worker error", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--data-dir", type=Path, default=portable_directory())
    parser.add_argument(
        "--self-test", type=Path, help="Write a frozen-runtime diagnostic JSON and exit"
    )
    parser.add_argument("--offline", action="store_true", help="Do not download missing models")
    args = parser.parse_args()
    args.data_dir = args.data_dir.resolve()
    configure_logging(args.data_dir)
    if args.self_test:
        from .portable_check import diagnose_bundle

        diagnose_bundle(args.data_dir, args.self_test, download=not args.offline)
        return

    from PySide6.QtCore import QLockFile, QThread, QTimer, QUrl, Qt, Signal
    from PySide6.QtGui import QAction, QDesktopServices, QIcon
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QLabel,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    icon = Path(__file__).parent / "web" / "app.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    lock = QLockFile(str(args.data_dir / "desktop.lock"))
    if not lock.tryLock(0):
        QMessageBox.information(None, APP_NAME, "程序已经在运行，请切换到已有窗口。")
        return

    class Prepare(QThread):
        message = Signal(str)
        ready = Signal(str)
        failed = Signal(str)

        def __init__(self, backend):
            super().__init__()
            self.backend = backend
            backend.progress = lambda value, text: self.message.emit(text)

        def run(self):
            try:
                self.ready.emit(self.backend.start(download=not args.offline))
            except Exception as exc:
                logging.exception("Desktop startup failed")
                self.backend.stop()
                self.failed.emit(startup_advice(exc) + "\n\n详细信息：" + str(exc))

    class LocalPage(QWebEnginePage):
        def acceptNavigationRequest(self, url, kind, is_main_frame):
            return (
                url.toString().startswith(window.backend.url + "/")
                or url.toString() == window.backend.url
            )

        def javaScriptConsoleMessage(self, level, message, line, source):
            logging.info("UI %s:%s %s", source, line, message)

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{APP_NAME} · v{__version__}")
            self.resize(1440, 980)
            self.setMinimumSize(1000, 700)
            self.backend = None
            self.worker = None
            self.profile = None
            self.view = None
            self.closing = False
            self.stop_thread = None
            self.loading = QWidget()
            layout = QVBoxLayout(self.loading)
            layout.setContentsMargins(90, 70, 90, 70)
            layout.addStretch()
            title = QLabel(APP_NAME)
            title.setStyleSheet("font-size:30px;font-weight:600")
            layout.addWidget(title)
            self.message = QLabel("正在启动…")
            self.message.setWordWrap(True)
            layout.addWidget(self.message)
            self.progress = QProgressBar()
            self.progress.setRange(0, 0)
            layout.addWidget(self.progress)
            hint = QLabel("首次启动自动准备模型；完成后音频在本机处理，无需打开浏览器。")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            self.retry = QPushButton("重试")
            self.retry.clicked.connect(self.prepare)
            self.retry.hide()
            layout.addWidget(self.retry)
            layout.addStretch()
            self.setCentralWidget(self.loading)
            files = self.menuBar().addMenu("文件")
            outputs = QAction("打开导出文件夹", self)
            outputs.triggered.connect(lambda: self.open_folder("outputs"))
            files.addAction(outputs)
            exit_action = QAction("退出", self)
            exit_action.triggered.connect(self.close)
            files.addAction(exit_action)
            help_menu = self.menuBar().addMenu("帮助")
            logs = QAction("打开日志文件夹", self)
            logs.triggered.connect(lambda: self.open_folder("logs"))
            help_menu.addAction(logs)
            about = QAction("关于", self)
            about.triggered.connect(
                lambda: QMessageBox.information(
                    self,
                    APP_NAME,
                    f"{APP_NAME}\nv{__version__}\n\n使用本机运行环境与独立桌面窗口。\n"
                    "研究模型可能有串音，导出前请试听。\n\n"
                    "模型：Jocelyn Xu、Minje Kim 的 Singer-Informed Vocal Source Separation\n"
                    "for Multi-Singer Music Mixtures（2026），FiLM / target-vocal loss only。\n"
                    "论文：https://arxiv.org/abs/2608.14516\n"
                    "作者代码：https://github.com/jocelynxu01/singer-separation-paper\n"
                    "本程序是工程封装，不是原创模型或作者官方应用。\n\n"
                    "模型授权与应用 MIT License 分开；详见 THIRD_PARTY_NOTICES.md 与 LICENSES。",
                )
            )
            help_menu.addAction(about)
            self.statusBar().showMessage("本机运行 · 首次准备模型需要联网")
            QTimer.singleShot(0, self.prepare)

        def open_folder(self, name):
            path = args.data_dir / name
            path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

        def prepare(self):
            self.retry.hide()
            self.progress.show()
            self.backend = DesktopBackend(args.data_dir)
            self.worker = Prepare(self.backend)
            self.worker.message.connect(self.message.setText)
            self.worker.ready.connect(self.show_timeline)
            self.worker.failed.connect(self.show_error)
            self.worker.start()

        def show_error(self, message):
            if self.closing:
                return
            self.message.setText("启动未完成：\n" + message)
            self.progress.hide()
            self.retry.show()

        def show_timeline(self, url):
            if self.closing:
                return
            self.profile = QWebEngineProfile(self)
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            self.profile.downloadRequested.connect(self.download)
            self.view = QWebEngineView(self)
            page = LocalPage(self.profile, self.view)
            page.settings().setAttribute(
                QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True
            )
            self.view.setPage(page)
            self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.view.loadFinished.connect(self.page_loaded)
            self.setCentralWidget(self.view)
            self.view.setUrl(QUrl(url))
            self.statusBar().showMessage("本机运行 · 关闭前请导出 · 导出文件位于 data/outputs")

        def page_loaded(self, ok):
            if not ok and not self.closing:
                QMessageBox.warning(self, APP_NAME, "界面加载失败，请重新启动。详情见 data/logs。")

        def download(self, request):
            output = args.data_dir / "downloads"
            output.mkdir(exist_ok=True)
            path, _ = QFileDialog.getSaveFileName(
                self, "另存导出文件", str(output / request.downloadFileName())
            )
            if not path:
                request.cancel()
                return
            request.setDownloadDirectory(str(Path(path).parent))
            request.setDownloadFileName(Path(path).name)
            request.accept()

        def closeEvent(self, event):
            if self.closing:
                event.accept()
                return
            if self.backend and self.backend.has_edits():
                answer = QMessageBox.question(
                    self,
                    "关闭软件",
                    "关闭后编辑历史不会保留，已导出的文件不受影响。\n是否关闭？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
            event.ignore()
            self.closing = True
            self.setEnabled(False)
            self.statusBar().showMessage("正在停止本机任务…")
            if self.backend:
                self.backend.cancelled.set()
            self.finish_close()

        def finish_close(self):
            if self.worker and self.worker.isRunning():
                QTimer.singleShot(100, self.finish_close)
                return
            if not self.stop_thread:
                if self.backend is None:
                    self.close()
                    return
                self.stop_thread = threading.Thread(target=self.backend.stop, daemon=True)
                self.stop_thread.start()
            if self.stop_thread.is_alive():
                QTimer.singleShot(100, self.finish_close)
                return
            self.close()

    window = Window()
    window.show()
    try:
        app.exec()
    finally:
        lock.unlock()
