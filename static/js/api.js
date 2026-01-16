
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
    CONTROL_UPDATE_TEXT: '/api/control/update_text',
    SYSTEM_BROWSE: '/api/system/browse',
    SYSTEM_BROWSE_FILE: '/api/system/browse_file',
    FFMPEG_DEVICES: '/api/ffmpeg/devices',
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

    async updateSynthesisConfig(config) {
        return this._fetchJson(`${this.endpoints.CONFIG}/synthesis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    }

    async updateResolveConfig(config) {
        return this._fetchJson(`${this.endpoints.CONFIG}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    }

    async updateSystemConfig(config) {
        return this._fetchJson(`${this.endpoints.CONFIG}/system`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
    }

    async updateFFmpegConfig(config) {
        return this._fetchJson(`${this.endpoints.CONFIG}/ffmpeg`, {
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

    async playAudio(id, request_id = null) {
        return this._fetchJson(this.endpoints.CONTROL_PLAY, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, request_id })
        });
    }

    async deleteFile(id) {
        return this._fetchJson(this.endpoints.CONTROL_DELETE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
    }

    async updateText(id, text) {
        return this._fetchJson(this.endpoints.CONTROL_UPDATE_TEXT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, text })
        });
    }

    async insertToResolve(id) {
        return this._fetchJson(this.endpoints.CONTROL_RESOLVE_INSERT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
    }

    async browseDirectory() {
        return this._fetchJson(this.endpoints.SYSTEM_BROWSE, {
            method: 'POST'
        });
    }

    async browseFile() {
        return this._fetchJson(this.endpoints.SYSTEM_BROWSE_FILE, {
            method: 'POST'
        });
    }

    async getAudioDevices() {
        return this._fetchJson(this.endpoints.FFMPEG_DEVICES);
    }

    async getResolveBins() {
        return this._fetchJson('/api/resolve/bins');
    }

    async getResolveClips() {
        return this._fetchJson('/api/resolve/clips');
    }
}
