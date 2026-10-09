import argparse
import json
import sys

from .api import create_app
from .config import Config


def main():
    parser = argparse.ArgumentParser(description="ULTRON loopback agent")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = Config()
    if args.port:
        config.port = args.port
    # Desktop parent consumes this pipe; do not put the token into a URL or log file.
    print(json.dumps({"event": "session", "port": config.port, "token": config.token}), flush=True)
    import uvicorn
    app = create_app(config)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=config.port, access_log=False, log_level="warning"))
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)
    server.run()


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        import multiprocessing
        multiprocessing.freeze_support()
    main()
