from __future__ import annotations

import socket
import threading
import time
import webbrowser

import uvicorn


def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    for port in range(start_port, start_port + max_attempts):
        ipv4_available = False
        ipv6_available = False

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_v4:
                sock_v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                sock_v4.bind(("0.0.0.0", port))
                ipv4_available = True
        except OSError:
            pass

        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock_v6:
                sock_v6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                sock_v6.bind(("::", port))
                ipv6_available = True
        except OSError:
            pass

        if ipv4_available and ipv6_available:
            return port

    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")


def open_browser(port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


if __name__ == "__main__":
    port = find_available_port()
    print(f"\nStarting LLM Claim Formalization Demo on port {port}")
    print(f"Opening http://localhost:{port} in your browser...")
    print("Press Ctrl+C to stop\n")

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run(
        "llm_claim_formalization.demo.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
