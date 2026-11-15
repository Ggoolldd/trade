"""Local loopback Uvicorn smoke, using a reserved ephemeral socket."""

import socket
import threading
import time

import httpx
import uvicorn

from app.main import create_app


def test_uvicorn_serves_loopback_and_shuts_down() -> None:
    application = create_app()
    server = uvicorn.Server(uvicorn.Config(application, log_level="warning"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert server.started, "Uvicorn did not start"
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
                assert client.get("/health/ready").json()["status"] == "ready"
                assert client.get("/openapi.json").status_code == 200
        finally:
            server.should_exit = True
            worker.join(timeout=10)
        assert not worker.is_alive(), "Uvicorn did not stop"
    assert application.state.ready is False
