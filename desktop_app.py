"""Windowed executable entry point; never opens the user's web browser."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        from singer_extractor.desktop import main

        main()
    except Exception as exc:
        import logging

        logging.exception("Desktop could not start")
        if sys.platform == "win32":
            import ctypes

            from singer_extractor.environment import startup_advice

            ctypes.windll.user32.MessageBoxW(
                None, startup_advice(exc) + "\n\n" + str(exc), "哦，金金的音道分离", 0x10
            )
        raise SystemExit(1) from exc
