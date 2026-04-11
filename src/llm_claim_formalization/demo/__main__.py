import uvicorn
import webbrowser
import threading
import time
import socket

def find_available_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

def open_browser(port):
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")

if __name__ == "__main__":
    port = find_available_port()
    print(f"\n🚀 Starting LLM Claim Formalization Demo on port {port}")
    print(f"📱 Opening http://localhost:{port} in your browser...")
    print(f"⏹️  Press Ctrl+C to stop\n")

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run(
        "llm_claim_formalization.demo.server:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
