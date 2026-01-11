
/**
 * Application State Store
 * Emits events when state changes
 */
export class AppStore extends EventTarget {
    constructor() {
        super();
        this.state = {
            speakers: {},
            config: {},
            isSynthesisEnabled: false,
            isResolveAvailable: false,
            isVoicevoxAvailable: false,
            serverPlaybackState: { is_playing: false, filename: null, remaining: 0 },
            logs: [],
            outputDir: ""
        };
    }

    /**
     * Update methods - these trigger events
     */
    setSpeakers(speakers) {
        this.state.speakers = speakers;
        this._emit('speakers_updated');
    }

    setConfig(config, outputDir, resolveAvailable, voicevoxAvailable) {
        this.state.config = { ...this.state.config, ...config };
        if (outputDir !== undefined) this.state.outputDir = outputDir;
        if (resolveAvailable !== undefined) this.state.isResolveAvailable = resolveAvailable;
        if (voicevoxAvailable !== undefined) this.state.isVoicevoxAvailable = voicevoxAvailable;
        this._emit('config_updated');
    }

    setControlState(enabled, playback, resolveAvailable, voicevoxAvailable) {
        let changed = false;

        if (this.state.isSynthesisEnabled !== enabled) {
            this.state.isSynthesisEnabled = enabled;
            changed = true;
        }

        if (playback) {
            // Deep check or just replace? Replace is simpler for this struct
            this.state.serverPlaybackState = playback;
            changed = true; // Always assume playback updates might need re-render due to time/status
        }

        if (resolveAvailable !== undefined && this.state.isResolveAvailable !== resolveAvailable) {
            this.state.isResolveAvailable = resolveAvailable;
            changed = true;
        }

        if (voicevoxAvailable !== undefined && this.state.isVoicevoxAvailable !== voicevoxAvailable) {
            this.state.isVoicevoxAvailable = voicevoxAvailable;
            changed = true;
        }

        if (changed) this._emit('state_updated');
    }

    setLogs(logs) {
        // Optimization check could act here, but we'll let UI decide or do strict check
        this.state.logs = logs;
        this._emit('logs_updated');
    }

    updateResolveStatus(available) {
        if (this.state.isResolveAvailable !== available) {
            this.state.isResolveAvailable = available;
            this._emit('state_updated');
        }
    }

    updateVoicevoxStatus(available) {
        if (this.state.isVoicevoxAvailable !== available) {
            this.state.isVoicevoxAvailable = available;
            this._emit('state_updated');
        }
    }

    updatePlaybackState(isPlaying, filename, requestId) {
        this.state.serverPlaybackState = { is_playing: isPlaying, filename: filename, request_id: requestId };
        this._emit('state_updated'); // Re-uses state_updated as it affects UI locks
    }

    updateSynthesisState(isEnabled) {
        if (this.state.isSynthesisEnabled !== isEnabled) {
            this.state.isSynthesisEnabled = isEnabled;
            this._emit('state_updated');
        }
    }

    /**
     * Getters
     */
    get speakers() { return this.state.speakers; }
    get config() { return this.state.config; }
    get isSynthesisEnabled() { return this.state.isSynthesisEnabled; }
    get isResolveAvailable() { return this.state.isResolveAvailable; }
    get isVoicevoxAvailable() { return this.state.isVoicevoxAvailable; }
    get playbackState() { return this.state.serverPlaybackState; }
    get logs() { return this.state.logs; }
    get outputDir() { return this.state.outputDir; }

    /**
     * Private helper to dispatch events
     */
    _emit(type, detail = {}) {
        this.dispatchEvent(new CustomEvent(type, { detail }));
    }
}
