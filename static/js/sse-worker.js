/**
 * SharedWorker for SSE (Server-Sent Events)
 * Maintains a single EventSource connection and broadcasts messages to all connected tabs.
 */

let eventSource = null;
const ports = new Set();

self.onconnect = (event) => {
    const port = event.ports[0];
    ports.add(port);

    port.onmessage = (e) => {
        if (e.data.type === 'init') {
            setupEventSource(e.data.url);
        }
    };

    port.start();

    // Remove port on disconnect
    // Note: Close event is not reliable, but typically worker handles it via port GC or explicit close
};

function setupEventSource(url) {
    if (eventSource) {
        // Already connected or connecting to same/different URL.
        // For simplicity, we assume one URL is used.
        return;
    }

    console.log('[SSE Worker] Connecting to:', url);
    eventSource = new EventSource(url);

    eventSource.onopen = () => {
        broadcast({ type: '_worker_open' });
    };

    eventSource.onmessage = (e) => {
        broadcast({ type: '_worker_message', data: e.data });
    };

    eventSource.onerror = (err) => {
        console.error('[SSE Worker] Error:', err);
        broadcast({ type: '_worker_error' });

        // EventSource automatically reconnects, but we notify tabs
    };
}

function broadcast(msg) {
    const deadPorts = [];
    ports.forEach(port => {
        try {
            port.postMessage(msg);
        } catch (e) {
            deadPorts.push(port);
        }
    });

    deadPorts.forEach(port => ports.delete(port));
}
