from __future__ import annotations

import argparse
import multiprocessing
import os
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="KQ4DLB Dashboard Matrix")
    parser.add_argument(
        "--host",
        default=os.getenv("DASHBOARD_MATRIX_HOST", "0.0.0.0"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("DASHBOARD_MATRIX_PORT", "8080")),
    )
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    if args.open_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    from app.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=os.getenv("DASHBOARD_MATRIX_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
