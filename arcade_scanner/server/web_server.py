import socketserver
import threading
import os
from arcade_scanner.config import config, PORT, find_free_port
from arcade_scanner.server.api_handler import FinderHandler

def start_server():
    """
    Initializes and starts the multi-threaded HTTP server.
    Changes the working directory to HIDDEN_DATA_DIR to serve thumbnails smoothly.
    """
    global PORT_ACTUAL
    # os.chdir(HIDDEN_DATA_DIR) # Removed to keep CWD at project root
    
    # Allow address reuse to prevent "Address already in use" errors if the script is restarted quickly
    server = socketserver.ThreadingTCPServer(("", PORT), FinderHandler, bind_and_activate=False)
    server.allow_reuse_address = True
    try:
        server.server_bind()
        server.server_activate()
    except OSError as e:
        print(f"Error binding to port {PORT}: {e}")
        # fallback: find another port if PORT is somehow still taken
        # from arcade_scanner.app_config import find_free_port
        new_port = find_free_port(PORT + 1)
        print(f"Attempting fallback to port {new_port}...")
        server = socketserver.ThreadingTCPServer(("", new_port), FinderHandler)
        PORT_ACTUAL = new_port
    else:
        PORT_ACTUAL = PORT
    
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    print(f"Server started on port {PORT_ACTUAL}")
    return server, PORT_ACTUAL
