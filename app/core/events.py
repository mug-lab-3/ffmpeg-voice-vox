import queue
import json
import threading
import time

class EventManager:
    def __init__(self):
        self.listeners = []
        self.lock = threading.Lock()

    def subscribe(self):
        """Register a new listener queue."""
        q = queue.Queue(maxsize=500) # Increased buffer to prevent dropped events
        with self.lock:
            self.listeners.append(q)
        return q

    def unsubscribe(self, q):
        """Remove a listener queue."""
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def publish(self, event_type: str, data: dict = None):
        """Broadcast event to all listeners."""
        msg = {
            "type": event_type,
            "data": data or {}
        }
        encoded = f"data: {json.dumps(msg)}\n\n"

        with self.lock:
            active_listeners = list(self.listeners)

        for q in active_listeners:
            try:
                q.put_nowait(encoded)
            except queue.Full:
                pass

    def start_heartbeat(self):
        """Start a background thread to keep connections alive."""
        def loop():
            while True:
                time.sleep(10) # 10s heartbeat
                # Send a comment line to keep connection open without triggering msg handler
                # OR send a ping event. Let's send a ping event for debug visibility
                self.publish("ping", {})

        t = threading.Thread(target=loop, daemon=True)
        t.start()

# Global instance
event_manager = EventManager()
event_manager.start_heartbeat()
