import json
from app.logging_config import get_logger
from queue import Queue, Empty
from flask import Blueprint, Response, request
from app.live.ticker import add_client, remove_client

logger = get_logger("routes.stream")
stream_bp = Blueprint('stream', __name__)

@stream_bp.route('/api/stream')
def stream_prices():
    """
    Server-Sent Events (SSE) endpoint to stream real-time Kite ticker prices
    to the frontend dashboard.
    """
    def event_stream():
        q = Queue()
        add_client(q)
        try:
            while True:
                # Wait for a new price tick from the background ticker thread
                try:
                    message = q.get(timeout=15)
                    yield f"data: {json.dumps(message)}\n\n"
                except Empty:
                    # Send a heartbeat ping every 15 seconds to keep the connection alive
                    yield ": ping\n\n"
        except GeneratorExit:
            logger.info("Client disconnected from SSE stream.")
        finally:
            remove_client(q)

    response = Response(event_stream(), mimetype="text/event-stream")
    
    # We must allow CORS for the stream endpoint if frontend is on a different port
    # Standard CORS headers might not be enough for streaming if not handled globally
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no' # Disable buffering in nginx
    
    return response
