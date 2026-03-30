import os
from http.server import ThreadingHTTPServer

from youtube_insights.web_app import Handler


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
