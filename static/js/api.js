
/**
 * API Client Configuration
 */
const ENDPOINTS = {
    CONFIG: '/api/config',
    SPEAKERS: '/api/speakers',
    LOGS: '/api/logs',
    CONTROL_STATE: '/api/control/state',
    CONTROL_PLAY: '/api/control/play',
    CONTROL_DELETE: '/api/control/delete',
    CONTROL_RESOLVE_INSERT: '/api/control/resolve_insert',
    SYSTEM_BROWSE: '/api/system/browse',
    STREAM: '/api/stream'
};

export class ApiClient {
    constructor() {
        this.endpoints = ENDPOINTS;
    }

    /**
     * Helper to handle fetch responses
     */
    async _fetchJson(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const data = await res.json();
            return {
                ok: res.ok,
                status: res.status,
                data: data
            };
        } catch (e) {
            console.error(`API Error (${url}):`, e);
            throw e;
        }
    }

    getStreamUrl() {
        return this.endpoints.STREAM;
    }

    async getSpeakers() {
        return this._fetchJson(this.endpoints.SPEAKERS);
    }

    async getConfig() {
        return this._fetchJson(this.endpoints.CONFIG);
    }

    async updateConfig(config) {
        return this._fetchJson(this.endpoints.CONFIG, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    }

    async getLogs() {
        return this._fetchJson(this.endpoints.LOGS);
    }

    async getControlState() {
        return this._fetchJson(this.endpoints.CONTROL_STATE);
    }

    async toggleControlState(enabled) {
        return this._fetchJson(this.endpoints.CONTROL_STATE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
    }

    async playAudio(filename) {
        return this._fetchJson(this.endpoints.CONTROL_PLAY, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
    }

    async deleteFile(filename) {
        return this._fetchJson(this.endpoints.CONTROL_DELETE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
    }

    async insertToResolve(filename) {
        return this._fetchJson(this.endpoints.CONTROL_RESOLVE_INSERT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
    }

    async browseDirectory() {
        return this._fetchJson(this.endpoints.SYSTEM_BROWSE, {
            method: 'POST'
        });
    }
}
