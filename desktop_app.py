"""Windowed executable entry point; never opens the user's web browser."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from singer_extractor.desktop import main

    main()
