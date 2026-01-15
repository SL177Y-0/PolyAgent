"""Start the PolyAgent API server for frontend integration.

This script starts the FastAPI server that provides:
- REST API endpoints for bot control
- WebSocket endpoint for real-time updates
- Multi-bot management support

Usage:
    python start_api_server.py [--host HOST] [--port PORT]
"""
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api_server import run_api_server


def main():
    parser = argparse.ArgumentParser(description="PolyAgent API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    # Configure logging to console and logs/api_server.log
    log_dir = Path("logs"); log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "api_server.log"

    logger = logging.getLogger()
    logger.handlers = []
    logger.setLevel(getattr(logging, args.log_level.upper()))

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, args.log_level.upper()))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    fh.setLevel(getattr(logging, args.log_level.upper()))
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    app_logger = logging.getLogger(__name__)
    app_logger.info(f"Starting PolyAgent API Server on {args.host}:{args.port}")
    app_logger.info(f"API documentation: http://{args.host}:{args.port}/docs")
    app_logger.info(f"WebSocket endpoint: ws://{args.host}:{args.port}/ws")

    run_api_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
