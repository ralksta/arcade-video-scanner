import socketserver
import threading
import os
from arcade_scanner.config import config, PORT, find_free_port
from arcade_scanner.server.api_handler import FinderHandler

def start_server(use_ssl=False):
    """
    Initializes and starts the multi-threaded HTTP server.
    Changes the working directory to HIDDEN_DATA_DIR to serve thumbnails smoothly.
    Args:
        use_ssl (bool): If True, wraps the socket in SSL with a self-signed cert.
    """
    global PORT_ACTUAL
    
    # Allow address reuse to prevent "Address already in use" errors if the script is restarted quickly
    server = socketserver.ThreadingTCPServer(("", PORT), FinderHandler, bind_and_activate=False)
    server.allow_reuse_address = True
    
    try:
        server.server_bind()
        server.server_activate()
    except OSError as e:
        print(f"Error binding to port {PORT}: {e}")
        # fallback: find another port if PORT is somehow still taken
        new_port = find_free_port(PORT + 1)
        print(f"Attempting fallback to port {new_port}...")
        server = socketserver.ThreadingTCPServer(("", new_port), FinderHandler)
        PORT_ACTUAL = new_port
    else:
        PORT_ACTUAL = PORT
    
    # SSL Configuration
    if use_ssl:
        import ssl
        import subprocess
        
        cert_file = os.path.join(config.hidden_data_dir, "server.pem")
        
        # Generate self-signed cert if missing
        if not os.path.exists(cert_file):
            print("🔒 Generating self-signed SSL certificate...")
            try:
                # Use openssl to generate a cert valid for 365 days
                subprocess.check_call([
                    "openssl", "req", "-new", "-x509", "-keyout", cert_file,
                    "-out", cert_file, "-days", "365", "-nodes",
                    "-subj", "/CN=ArcadeScanner"
                ])
                print(f"✅ Certificate generated at: {cert_file}")
            except Exception as e:
                print(f"❌ Failed to generate SSL certificate: {e}")
                print("   Make sure 'openssl' is installed and in your PATH.")
                print("   Falling back to HTTP.")
                use_ssl = False
        
        if use_ssl and os.path.exists(cert_file):
            print("🔒 SSL Enabled")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_file)
            server.socket = context.wrap_socket(server.socket, server_side=True)
    
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    protocol = "https" if use_ssl else "http"
    print(f"Server started on port {PORT_ACTUAL} ({protocol})")
    return server, PORT_ACTUAL

