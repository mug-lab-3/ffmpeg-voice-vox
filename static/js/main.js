
import { ApiClient } from './api.js';
import { AppStore } from './store.js';

// --- Initialization ---

const api = new ApiClient();
const store = new AppStore();

const elements = {
    speaker: document.getElementById('speaker'),
    speedScale: document.getElementById('speedScale'),
    pitchScale: document.getElementById('pitchScale'),
    intonationScale: document.getElementById('intonationScale'),
    volumeScale: document.getElementById('volumeScale'),
    synthesisTiming: document.getElementById('synthesis-timing'),

    logTableBody: document.getElementById('log-table-body'),
    startStopBtn: document.getElementById('start-stop-btn'),
    outputDir: document.getElementById('outputDir'),
    browseBtn: document.getElementById('browseOutputDir'),
    dirStatus: document.getElementById('dir-status'),
    resolveStatus: document.getElementById('resolve-status'),
    voicevoxStatus: document.getElementById('voicevox-status'),
    serverStatus: document.getElementById('server-status'),

    // Settings (Direct Inputs)
    cfgInputs: {
        ffmpegPath: document.getElementById('cfg-ffmpeg-path'),
        inputDevice: document.getElementById('cfg-input-device'),
        modelPath: document.getElementById('cfg-model-path'),
        vadPath: document.getElementById('cfg-vad-path'),
        queueLength: document.getElementById('cfg-queue-length'),
        host: document.getElementById('cfg-host'),
        audioTrackIndex: document.getElementById('cfg-audio-track-index'),
        subtitleTrackIndex: document.getElementById('cfg-subtitle-track-index'),
        targetBin: document.getElementById('cfg-target-bin'),
        templateName: document.getElementById('cfg-template-name')
    }
};

const valueDisplays = {
    speedScale: document.getElementById('val-speedScale'),
    pitchScale: document.getElementById('val-pitchScale'),
    intonationScale: document.getElementById('val-intonationScale'),
    volumeScale: document.getElementById('val-volumeScale')
};

// --- Optimization Cache ---
// We keep this locally in UI layer because it's purely about rendering optimization
// derived from the store state.
let lastRenderedLogsJson = "";
let lastRenderedStateKey = "";

// --- App Entry Point ---

async function init() {
    // Set server status to connected initially (will be updated by SSE events)
    const serverStatusEl = document.getElementById('server-status');
    if (serverStatusEl) {
        serverStatusEl.classList.add('online');
    }

    setupStoreListeners();
    setupUIListeners();
    setupSSE();

    // Initial Load
    try {
        const [speakersRes, configRes, controlRes, logsRes] = await Promise.all([
            api.getSpeakers(),
            api.getConfig(),
            api.getControlState(),
            api.getLogs()
        ]);

        if (speakersRes.ok) store.setSpeakers(speakersRes.data);
        if (speakersRes.ok) store.setSpeakers(speakersRes.data);
        if (configRes.ok) {
            const data = configRes.data;
            store.setConfig(data.config, data.outputDir, data.resolve_available, data.voicevox_available);
        }
        if (controlRes.ok) store.setControlState(controlRes.data.enabled, controlRes.data.playback, controlRes.data.resolve_available, controlRes.data.voicevox_available);
        if (logsRes.ok) store.setLogs(logsRes.data);

    } catch (e) {
        console.error("Initialization failed", e);
    }
}

// --- Event Setup ---

function setupStoreListeners() {
    store.addEventListener('speakers_updated', renderSpeakers);
    store.addEventListener('config_updated', renderConfig);
    store.addEventListener('state_updated', () => {
        renderStartStopUI();
        renderResolveStatus();
        renderVoicevoxStatus();
        renderLogs(); // State changes affect button locks
    });
    store.addEventListener('logs_updated', renderLogs);
}

function setupUIListeners() {
    // Voicevox Config Inputs
    const vvKeys = ['speaker', 'speedScale', 'pitchScale', 'intonationScale', 'volumeScale', 'synthesisTiming'];
    vvKeys.forEach(key => {
        elements[key].addEventListener('input', (e) => {
            if (valueDisplays[key]) {
                valueDisplays[key].textContent = Number(e.target.value).toFixed(2);
            }
        });

        elements[key].addEventListener('change', async (e) => {
            let val;
            if (key === 'speaker') {
                val = parseInt(e.target.value);
            } else if (key === 'synthesisTiming') {
                val = e.target.value; // Keep as string ("immediate" or "on_demand")
            } else {
                val = parseFloat(e.target.value);
            }
            const mapping = {
                'speaker': 'speaker_id',
                'speedScale': 'speed_scale',
                'pitchScale': 'pitch_scale',
                'intonationScale': 'intonation_scale',
                'volumeScale': 'volume_scale',
                'synthesisTiming': 'timing'
            };
            const res = await api.updateSynthesisConfig({ [mapping[key]]: val });
            if (!res.ok && res.status === 422) {
                await showAlert("Validation Error", res.data.message || "Invalid value");
                // Restore previous valid value using data from error response
                if (res.data.config) {
                    store.setConfig(res.data.config, res.data.outputDir, res.data.resolve_available, res.data.voicevox_available);
                } else {
                    renderConfig(); // Fallback
                }
            }
        });
    });


    // FFmpeg Config Inputs (Auto-save)
    const ffmpegKeys = Object.keys(elements.cfgInputs);
    // Helper to saves config
    const saveDomainConfig = async (domain) => {
        const sanitizeStr = (val) => val || ""; // Ensure empty string instead of null/undefined
        const sanitizeInt = (val, defaultVal) => {
            const parsed = parseInt(val);
            return isNaN(parsed) ? defaultVal : parsed;
        };

        try {
            let res;
            if (domain === 'ffmpeg') {

                const currentFFmpeg = {
                    ffmpeg_path: sanitizeStr(elements.cfgInputs.ffmpegPath.value),
                    input_device: sanitizeStr(elements.cfgInputs.inputDevice.value),
                    model_path: sanitizeStr(elements.cfgInputs.modelPath.value),
                    vad_model_path: sanitizeStr(elements.cfgInputs.vadPath.value),
                    queue_length: sanitizeInt(elements.cfgInputs.queueLength.value, 10),
                    host: sanitizeStr(elements.cfgInputs.host.value) || "127.0.0.1" // Host requires valid value or default
                };
                res = await api.updateFFmpegConfig(currentFFmpeg);
            } else if (domain === 'resolve') {
                const updates = {};
                const audioIdx = parseInt(elements.cfgInputs.audioTrackIndex.value);
                const subIdx = parseInt(elements.cfgInputs.subtitleTrackIndex.value);

                // Only send updates if valid number, otherwise let backend/store keep current or use defaults if full object
                if (!isNaN(audioIdx)) updates.audio_track_index = audioIdx;
                if (!isNaN(subIdx)) updates.subtitle_track_index = subIdx;

                // For strings, send "" if empty
                updates.target_bin = sanitizeStr(elements.cfgInputs.targetBin.value);
                updates.template_name = sanitizeStr(elements.cfgInputs.templateName.value);

                res = await api.updateResolveConfig(updates);
            }

            if (res && !res.ok) {
                const title = res.status === 422 ? "Validation Error" : "Save Error (Check Console)";
                const msg = res.data?.message || "Unknown error occurred";
                await showAlert(title, msg);

                if (res.status === 422 && res.data?.config) {
                    store.setConfig(res.data.config, res.data.outputDir, res.data.resolve_available, res.data.voicevox_available);
                } else {
                    renderConfig();
                }
            }
        } catch (e) {
            console.error("Auto-save failed", e);
        }
    };

    ffmpegKeys.forEach(key => {
        const input = elements.cfgInputs[key];
        input.addEventListener('change', () => {
            const domain = ['audioTrackIndex', 'subtitleTrackIndex', 'targetBin', 'templateName'].includes(key) ? 'resolve' : 'ffmpeg';
            saveDomainConfig(domain);
        });
    });

    // Device Refresh
    const refreshBtn = document.getElementById('refresh-devices');
    refreshBtn.addEventListener('click', async () => {
        const ffmpegPath = elements.cfgInputs.ffmpegPath.value;
        if (!ffmpegPath) {
            await showAlert("Notice", "Please set FFmpeg path first");
            return;
        }

        refreshBtn.classList.add('rotating'); // Add rotation class if we have one, or just disable
        refreshBtn.disabled = true;

        try {
            const res = await api.getAudioDevices(ffmpegPath);
            if (res.ok && res.data.status === 'ok') {
                populateDeviceSelect(res.data.devices);
            } else {
                await showAlert("Error", res.data.message || "Failed to list devices");
            }
        } catch (e) {
            await showAlert("Error", "Failed to fetch device list");
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.classList.remove('rotating');
        }
    });

    // Resolve Bins Refresh
    const refreshBinsBtn = document.getElementById('refresh-resolve-bins');
    refreshBinsBtn.addEventListener('click', async () => {
        if (!store.isResolveAvailable) {
            await showAlert("Notice", "DaVinci Resolve is not connected");
            return;
        }

        refreshBinsBtn.classList.add('rotating');
        refreshBinsBtn.disabled = true;

        try {
            const res = await api.getResolveBins();
            if (res.ok && res.data.status === 'ok') {
                populateResolveBins(res.data.bins);
            } else {
                await showAlert("Error", res.data.message || "Failed to list bins");
            }
        } catch (e) {
            await showAlert("Error", "Failed to fetch Resolve bins");
        } finally {
            refreshBinsBtn.disabled = false;
            refreshBinsBtn.classList.remove('rotating');
        }
    });

    // Resolve Clips Refresh
    const refreshClipsBtn = document.getElementById('refresh-resolve-clips');
    refreshClipsBtn.addEventListener('click', async () => {
        if (!store.isResolveAvailable) {
            await showAlert("Notice", "DaVinci Resolve is not connected");
            return;
        }

        refreshClipsBtn.classList.add('rotating');
        refreshClipsBtn.disabled = true;

        try {
            const res = await api.getResolveClips();
            if (res.ok && res.data.status === 'ok') {
                populateResolveClips(res.data.clips);
            } else {
                await showAlert("Error", res.data.message || "Failed to list clips");
            }
        } catch (e) {
            await showAlert("Error", "Failed to fetch Resolve clips");
        } finally {
            refreshClipsBtn.disabled = false;
            refreshClipsBtn.classList.remove('rotating');
        }
    });

    // Browse Buttons
    const setupBrowse = (btnId, inputKey) => {
        const btn = document.getElementById(btnId);
        btn.addEventListener('click', async () => {
            try {
                const res = await api.browseFile();
                if (res.ok && res.data.status === 'ok') {
                    elements.cfgInputs[inputKey].value = res.data.path;
                    // Trigger save
                    await saveDomainConfig('ffmpeg');

                    // If we just set ffmpeg path, might want to refresh devices
                    if (inputKey === 'ffmpegPath') {
                        // Auto-trigger refresh handled by user click for now, or we can do it automatically?
                        // Let's do it if device list is empty
                        if (elements.cfgInputs.inputDevice.options.length <= 1) {
                            refreshBtn.click();
                        }
                    }
                }
            } catch (e) {
                console.error("Browse failed", e);
            }
        });
    };

    setupBrowse('browse-ffmpeg-path', 'ffmpegPath');
    setupBrowse('browse-model-path', 'modelPath');
    setupBrowse('browse-vad-path', 'vadPath');


    // Output Directory Browse
    elements.browseBtn.addEventListener('click', async () => {
        if (elements.browseBtn.classList.contains('disabled') || elements.browseBtn.disabled) return;

        setUILocked(true, "Selecting Directory...");
        try {
            const res = await api.browseDirectory();
            if (res.ok && res.data.status === 'ok') {
                const path = res.data.path;
                elements.outputDir.value = path;
                // Server reloads logs automatically on config change
                const updateRes = await api.updateSystemConfig({ output_dir: path });
                if (!updateRes.ok && updateRes.status === 422) {
                    await showAlert("Validation Error", updateRes.data.message);
                    if (updateRes.data.config) {
                        store.setConfig(updateRes.data.config, updateRes.data.outputDir, updateRes.data.resolve_available, updateRes.data.voicevox_available);
                    } else {
                        renderConfig();
                    }
                    return;
                }

                // Refresh logs specifically after dir change
                const logRes = await api.getLogs();
                if (logRes.ok) store.setLogs(logRes.data);
            } else if (res.data.status === 'error') {
                await showAlert("Error", res.data.message);
            }
        } catch (e) {
            await showAlert("Error", "Failed to browse directory");
        } finally {
            setUILocked(false);
        }
    });

    // Start/Stop
    elements.startStopBtn.addEventListener('click', handleStartStopClick);

    // Collapsible Sections
    const headers = document.querySelectorAll('.settings-header');
    headers.forEach(header => {
        header.addEventListener('click', () => {
            const group = header.closest('.settings-group');
            if (group) {
                group.classList.toggle('collapsed');
            }
        });
    });
}

function populateDeviceSelect(devices) {
    const select = elements.cfgInputs.inputDevice;
    const currentValue = select.value; // Try to preserve selection if possible or logic relies on config

    // Clear (keep first placeholder)
    select.innerHTML = '<option value="" disabled>Select Device</option>';

    if (!devices || devices.length === 0) {
        const opt = document.createElement('option');
        opt.disabled = true;
        opt.textContent = "No devices found";
        select.appendChild(opt);
        return;
    }

    devices.forEach(dev => {
        const opt = document.createElement('option');
        opt.value = dev;
        opt.textContent = dev;
        select.appendChild(opt);
    });

    // Restore value from store if matches, or current value if just refreshing
    // Actually store.config has the authoritative value.
    // But if we just opened app, renderConfig might have set value but options weren't there.
    if (store.config?.ffmpeg?.input_device) {
        select.value = store.config.ffmpeg.input_device;
    } else if (currentValue) {
        select.value = currentValue;
    }
}

function populateResolveBins(bins) {
    const select = elements.cfgInputs.targetBin;
    const currentValue = select.value || (store.config?.resolve?.target_bin) || "VoiceVox Captions";

    select.innerHTML = '';

    // Always add manual entry option or ensure logic handles missing?
    // Actually, API returns strings.
    // If list is empty, maybe keep current? 
    // But API should return at least "root" if connected.

    if (bins && bins.length > 0) {
        bins.forEach(bin => {
            const opt = document.createElement('option');
            opt.value = bin;
            opt.textContent = bin;
            select.appendChild(opt);
        });
    }

    // Restore selection or add if missing
    select.value = currentValue;
    if (select.value !== currentValue) {
        const opt = document.createElement('option');
        opt.value = currentValue;
        opt.textContent = currentValue + " (Custom/New)";
        select.appendChild(opt);
        select.value = currentValue;
    }
}

function populateResolveClips(clips) {
    const select = elements.cfgInputs.templateName;
    const currentValue = select.value || (store.config?.resolve?.template_name) || "Auto";

    // Clear (always keep Auto)
    select.innerHTML = '<option value="Auto">Auto</option>';

    if (clips && clips.length > 0) {
        clips.forEach(clip => {
            if (clip === "Auto") return; // Skip if already there
            const opt = document.createElement('option');
            opt.value = clip;
            opt.textContent = clip;
            select.appendChild(opt);
        });
    }

    // Restore selection
    select.value = currentValue;
    // If current value is not in new list and not Auto, it will show blank or keep first.
    // We should ensure it's valid.
    if (select.value !== currentValue && currentValue !== "Auto") {
        // Option lost, but keep the value if possible so it shows up in logic?
        // Actually select.value will be empty if not found.
        const opt = document.createElement('option');
        opt.value = currentValue;
        opt.textContent = currentValue + " (Missing)";
        opt.disabled = true;
        select.appendChild(opt);
        select.value = currentValue;
    }
}



const tabChannel = new BroadcastChannel('voicevox_tab_control');
let isTabActive = true;

function setupSSE() {
    const streamUrl = new URL(api.getStreamUrl(), window.location.href).href;
    const serverStatusEl = document.getElementById('server-status');

    // 1. Tab Exclusion Logic
    tabChannel.postMessage({ type: 'new_tab_opened', timestamp: Date.now() });
    tabChannel.onmessage = (e) => {
        if (e.data.type === 'new_tab_opened') {
            console.log('[Tab] Another tab opened. This tab will deactivate.');
            deactivateTab();
        }
    };

    function deactivateTab() {
        isTabActive = false;
        // Try to close, but it might be blocked by browser
        window.close();

        // UI feedback if close failed
        document.body.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; background:#1e1e2e; color:#cdd6f4; font-family:sans-serif; text-align:center; padding:20px;">
                <h1 style="color:#f38ba8;">Tab Deactivated</h1>
                <p>別のタブでWebUIが新しく開かれたため、このタブの通信を停止しました。</p>
                <button onclick="location.reload()" style="margin-top:20px; padding:10px 20px; background:#a8df65; border:none; border-radius:4px; font-weight:bold; cursor:pointer; color:#1e1e2e;">このタブを再度有効にする</button>
            </div>
        `;
        if (worker) worker.port.close();
    }

    // 2. SSE Sharing Logic
    let worker = null;
    if (window.SharedWorker) {
        try {
            worker = new SharedWorker('/static/js/sse-worker.js');
            worker.port.start();
            worker.port.postMessage({ type: 'init', url: streamUrl });

            worker.port.onmessage = (e) => {
                if (!isTabActive) return;
                const msg = e.data;
                if (msg.type === '_worker_open') {
                    console.log('[SSE] Connection established via worker');
                    if (serverStatusEl) serverStatusEl.classList.add('online');
                } else if (msg.type === '_worker_message') {
                    try {
                        handleServerEvent(JSON.parse(msg.data));
                    } catch (err) {
                        console.error("SSE Parse Error", err);
                    }
                } else if (msg.type === '_worker_error') {
                    console.error('[SSE] Connection error in worker');
                    if (serverStatusEl) serverStatusEl.classList.remove('online');
                }
            };
            return; // Successful SharedWorker setup
        } catch (e) {
            console.error('[SSE] Failed to initialize SharedWorker, falling back to EventSource', e);
        }
    }

    // Fallback if SharedWorker not available
    const evtSource = new EventSource(streamUrl);
    evtSource.onopen = () => {
        console.log('[SSE] Connection established (fallback)');
        if (serverStatusEl) serverStatusEl.classList.add('online');
    };
    evtSource.onmessage = (e) => {
        if (!isTabActive) return;
        try {
            handleServerEvent(JSON.parse(e.data));
        } catch (err) {
            console.error("SSE Parse Error", err);
        }
    };
    evtSource.onerror = (err) => {
        console.error('[SSE] Connection error', err);
        if (serverStatusEl) serverStatusEl.classList.remove('online');
    };
}

// --- Logic Handlers ---

async function handleStartStopClick() {
    if (elements.startStopBtn.classList.contains('disabled')) return;

    const newState = !store.isSynthesisEnabled;

    // Pre-flight check
    if (newState && !store.outputDir.trim()) {
        await showAlert("Configuration Error", "Please set an output directory first.");
        return;
    }

    elements.startStopBtn.classList.add('disabled-temp');

    // Debounce "Processing..." text to avoid flicker on fast responses
    // Only show if it takes longer than 300ms
    const loadingTimer = setTimeout(() => {
        elements.startStopBtn.textContent = "Processing...";
    }, 300);

    try {
        const res = await api.toggleControlState(newState);
        clearTimeout(loadingTimer);

        if (!res.ok || res.data.status !== 'ok') {
            await showAlert("Error", res.data.message || "Failed to change state");
            renderStartStopUI(); // Revert
        }
        // Success handled by SSE state_update
    } catch (e) {
        clearTimeout(loadingTimer);
        await showAlert("Connection Error", e.message);
        renderStartStopUI(); // Revert
    }
}

async function handleServerEvent(msg) {
    switch (msg.type) {
        case "playback_change":
            store.updatePlaybackState(msg.data.is_playing, msg.data.filename, msg.data.request_id);
            break;
        case "state_update":
            store.updateSynthesisState(msg.data.is_enabled);
            break;
        case "log_update":
            // Logs are heavy, so we fetch them when notified rather than sending in event
            const lRes = await api.getLogs();
            if (lRes.ok) store.setLogs(lRes.data);
            break;
        case "config_update":
            const cRes = await api.getConfig();
            if (cRes.ok) {
                let fullConfig = cRes.data.config || cRes.data;
                if (cRes.data.ffmpeg) {
                    fullConfig = { ...fullConfig, ffmpeg: cRes.data.ffmpeg };
                }
                store.setConfig(fullConfig, cRes.data.outputDir, cRes.data.resolve_available);
            }
            break;
        case "resolve_status":
            store.updateResolveStatus(msg.data.available);
            break;
        case "voicevox_status":
            store.updateVoicevoxStatus(msg.data.available);
            break;
        case "server_restart":
            console.log('[SSE] Server restart detected. Reloading...');
            location.reload();
            break;
    }
}

// --- Rendering Logic ---

function renderSpeakers() {
    const speakers = store.speakers;
    elements.speaker.innerHTML = '';
    for (const [id, name] of Object.entries(speakers)) {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        elements.speaker.appendChild(option);
    }
    // Restore selected value if exists in config
    if (store.config.speaker_id) {
        elements.speaker.value = store.config.speaker_id;
    }
}

function renderConfig() {
    const config = store.config;
    const outputDir = store.outputDir;

    // Map config keys to elements
    // Note: Store config keys match API (snake_case generally or mixed depending on server)
    // Server returns synthesis config as: {speaker_id, speed_scale...}

    // Helper to try setting value
    const setIfExists = (el, val) => {
        if (el && val !== undefined) el.value = val;
    };

    setIfExists(elements.speaker, config.speaker_id);
    setIfExists(elements.speedScale, config.speed_scale);
    setIfExists(elements.pitchScale, config.pitch_scale);
    setIfExists(elements.intonationScale, config.intonation_scale);
    setIfExists(elements.volumeScale, config.volume_scale);
    setIfExists(elements.synthesisTiming, config.timing);

    // Update value displays
    if (config.speed_scale !== undefined) valueDisplays.speedScale.textContent = config.speed_scale.toFixed(2);
    if (config.pitch_scale !== undefined) valueDisplays.pitchScale.textContent = config.pitch_scale.toFixed(2);
    if (config.intonation_scale !== undefined) valueDisplays.intonationScale.textContent = config.intonation_scale.toFixed(2);
    if (config.volume_scale !== undefined) valueDisplays.volumeScale.textContent = config.volume_scale.toFixed(2);

    // Output Directory
    elements.outputDir.value = outputDir || "";
    if (outputDir) {
        elements.dirStatus.textContent = "";
    } else {
        elements.dirStatus.textContent = "Please set an output directory to start.";
        elements.dirStatus.style.color = "#ff6b6b";
    }

    // Resolve Status
    renderResolveStatus();
    // Voicevox Status
    renderVoicevoxStatus();
    // Start/Stop UI dependence on config (dir)
    renderStartStopUI();

    // Render FFmpeg Settings
    if (config.ffmpeg) {
        const setIfExists = (el, val) => { if (el && val !== undefined) el.value = val; };
        setIfExists(elements.cfgInputs.ffmpegPath, config.ffmpeg.ffmpeg_path);

        // Special handling for Select element to ensure value is visible
        if (config.ffmpeg.input_device) {
            const sel = elements.cfgInputs.inputDevice;
            // Check if option exists
            let exists = false;
            for (let i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === config.ffmpeg.input_device) {
                    exists = true;
                    break;
                }
            }
            if (!exists) {
                const opt = document.createElement('option');
                opt.value = config.ffmpeg.input_device;
                opt.textContent = config.ffmpeg.input_device;
                sel.appendChild(opt);
            }
            sel.value = config.ffmpeg.input_device;
        }

        setIfExists(elements.cfgInputs.modelPath, config.ffmpeg.model_path);
        setIfExists(elements.cfgInputs.vadPath, config.ffmpeg.vad_model_path);
        setIfExists(elements.cfgInputs.queueLength, config.ffmpeg.queue_length);
        setIfExists(elements.cfgInputs.host, config.ffmpeg.host);
    }

    // Render Resolve Settings
    if (config.resolve) {
        setIfExists(elements.cfgInputs.audioTrackIndex, config.resolve.audio_track_index);
        setIfExists(elements.cfgInputs.subtitleTrackIndex, config.resolve.subtitle_track_index);

        // Target Bin Selection
        const binSel = elements.cfgInputs.targetBin;
        if (config.resolve.target_bin) {
            let exists = false;
            for (let i = 0; i < binSel.options.length; i++) {
                if (binSel.options[i].value === config.resolve.target_bin) {
                    exists = true; break;
                }
            }
            if (!exists) {
                const opt = document.createElement('option');
                opt.value = config.resolve.target_bin;
                opt.textContent = config.resolve.target_bin;
                binSel.appendChild(opt);
            }
            binSel.value = config.resolve.target_bin;
        }

        // Template Name Selection
        const sel = elements.cfgInputs.templateName;
        if (config.resolve.template_name) {
            // Check if option exists
            let exists = false;
            for (let i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value === config.resolve.template_name) {
                    exists = true;
                    break;
                }
            }
            if (!exists) {
                const opt = document.createElement('option');
                opt.value = config.resolve.template_name;
                opt.textContent = config.resolve.template_name;
                sel.appendChild(opt);
            }
            sel.value = config.resolve.template_name;
        } else {
            sel.value = "Auto";
        }
    }
}

function renderResolveStatus() {
    const available = store.isResolveAvailable;
    const el = elements.resolveStatus;
    if (!el) return;

    // Icon color
    const color = available ? "#a8df65" : "#666";
    const statusText = available ? "CONNECTED" : "DISCONNECTED";

    el.innerHTML = `
        <span class="online">
            ${SvgIcons.resolve}
            <span class="fs-tiny fw-bold ml-2">RESOLVE: ${statusText}</span>
        </span>
    `;
    if (available) {
        el.classList.add('online');
    } else {
        el.classList.remove('online');
    }
}

function renderVoicevoxStatus() {
    const available = store.isVoicevoxAvailable;
    const el = elements.voicevoxStatus;
    if (!el) return;

    // Color: Green if connected, Red if disconnected (to warn start is impossible)
    const color = available ? "#a8df65" : "#ff6b6b";
    const statusText = available ? "CONNECTED" : "DISCONNECTED";

    el.innerHTML = `
        <span class="${available ? 'online' : ''}">
            ${SvgIcons.voicevox}
            <span class="fs-tiny fw-bold ml-2">VOICEVOX: ${statusText}</span>
        </span>
    `;
    if (available) {
        el.classList.add('online');
    } else {
        el.classList.remove('online');
    }
}

function renderStartStopUI() {
    const btn = elements.startStopBtn;
    const dirInput = elements.outputDir;
    const browseBtn = elements.browseBtn;
    const isEnabled = store.isSynthesisEnabled;
    const hasDir = store.outputDir && store.outputDir.trim().length > 0;

    // Reset temp disabled state
    btn.classList.remove('disabled-temp');

    if (isEnabled) {
        btn.textContent = "STOP";
        btn.classList.add('btn-stop');
        btn.classList.remove('btn-primary');
        btn.title = "Click to Stop Synthesis";
        btn.classList.remove('disabled');

        dirInput.disabled = true;
        browseBtn.disabled = true;
        browseBtn.classList.add('disabled-opacity');
        dirInput.classList.add('disabled-opacity');
    } else {
        btn.textContent = "START";
        btn.classList.remove('btn-stop');
        btn.classList.add('btn-primary');
        btn.title = "Click to Start Synthesis";

        dirInput.disabled = false;
        browseBtn.disabled = false;
        browseBtn.classList.remove('disabled-opacity');
        dirInput.classList.remove('disabled-opacity');

        // Check startability
        if (hasDir && store.isVoicevoxAvailable) {
            btn.classList.remove('disabled');
            btn.title = "Click to Start Synthesis";
        } else {
            btn.classList.add('disabled');
            if (!store.isVoicevoxAvailable) {
                btn.title = "VOICEVOX is disconnected. Please start VOICEVOX.";
            } else {
                btn.title = "Please set an output directory to start.";
            }
        }
    }
}

function renderLogs() {
    const logs = store.logs;
    const currentJson = JSON.stringify(logs);

    // Create a key representing the state that affects log row interactivity
    const playbackKey = `${store.playbackState.is_playing}_${store.playbackState.filename}`;
    const synthesisKey = store.isSynthesisEnabled;
    const resolveKey = store.isResolveAvailable;
    const voicevoxKey = store.isVoicevoxAvailable;
    const stateKey = `${playbackKey}_${synthesisKey}_${resolveKey}_${voicevoxKey}`;

    if (currentJson === lastRenderedLogsJson && stateKey === lastRenderedStateKey) {
        return;
    }

    lastRenderedLogsJson = currentJson;
    lastRenderedStateKey = stateKey;

    const displayLogs = logs.slice(); // Oldest first
    const tableBody = elements.logTableBody;
    const container = tableBody.closest('div');
    const previousScrollTop = container ? container.scrollTop : 0;

    // We'll follow the same smart-update logic as before to avoid full DOM thrashing
    const existingRows = new Map();
    Array.from(tableBody.children).forEach(row => {
        const filename = row.getAttribute('data-filename');
        if (filename) existingRows.set(filename, row);
        else row.remove();
    });

    let hasNewItem = false;

    displayLogs.forEach(entry => {
        if (typeof entry === 'string') return;
        const filename = entry.filename;
        if (!filename) return;

        let row = existingRows.get(filename);
        if (!row) {
            row = createLogRow(entry);
            hasNewItem = true;
        } else {
            existingRows.delete(filename);
            updateLogRow(row, entry);
        }
        tableBody.appendChild(row);
    });

    existingRows.forEach(row => row.remove());

    // Auto-scroll logic only if enabled, otherwise maintain pos
    if (hasNewItem && store.isSynthesisEnabled) {
        scrollToBottom();
    } else if (container) {
        container.scrollTop = previousScrollTop;
    }
}

// --- Log Row DOM Helpers ---

function createLogRow(entry) {
    const row = document.createElement('tr');
    row.classList.add('log-row');
    row.setAttribute('data-filename', entry.filename);


    // Columns: Play, ID (with tooltip), Text, Dur, Config, Resolve, Delete
    // Just simpler construction here
    row.innerHTML = `
        <td class="col-play text-center"></td>
        <td class="text-center text-muted fs-small" title="Created at: ${new Date(entry.timestamp).toLocaleString()}">${entry.id}</td>
        <td class="col-text fw-bold"></td>
        <td class="col-duration text-muted">${entry.filename.startsWith("pending_") ? "--" : entry.duration}</td>
        <td class="col-config"></td>
        <td class="col-resolve text-center"></td>
        <td class="col-delete text-center"></td>
    `;

    // Populate dynamic/complex bits that were easier to do with innerHTML but now need specific element refs
    // actually, let's just use updateLogRow to fill the interactive bits
    updateLogRow(row, entry);
    return row;
}

function updateLogRow(row, entry) {
    // Re-bind Speaker Name in config cell (might have changed if speakers reloaded?)
    const configCell = row.querySelector('.col-config');
    const spName = store.speakers[entry.config.speaker_id] || `ID:${entry.config.speaker_id}`;
    configCell.innerHTML = `<span class="text-primary">${spName}</span> <span class="text-muted fs-small">(x${entry.config.speed_scale.toFixed(2)})</span>`;

    // Tooltip with all config details
    const cfg = entry.config;
    const formatVal = (val) => (val !== undefined && val !== null) ? val : '-';

    const tooltipText = [
        `Speaker: ${spName}`,
        `Speed: ${formatVal(cfg.speed_scale)}`,
        `Pitch: ${formatVal(cfg.pitch_scale)}`,
        `Intonation: ${formatVal(cfg.intonation_scale)}`,
        `Volume: ${formatVal(cfg.volume_scale)}`
    ];

    if (cfg.pre_phoneme_length !== undefined) tooltipText.push(`Pre-Phoneme: ${cfg.pre_phoneme_length}`);
    if (cfg.post_phoneme_length !== undefined) tooltipText.push(`Post-Phoneme: ${cfg.post_phoneme_length}`);
    if (cfg.timing) tooltipText.push(`Timing: ${cfg.timing}`);

    configCell.title = tooltipText.join('\n');

    // Text Editing Logic
    const textCell = row.querySelector('.col-text');
    const isLocked = store.isSynthesisEnabled || store.playbackState.is_playing;

    // Only update content if NOT currently focused (to avoid jumping cursor)
    if (document.activeElement !== textCell) {
        textCell.textContent = entry.text;
        textCell.dataset.originalText = entry.text;
    }

    if (!isLocked) {
        textCell.contentEditable = "true";
        textCell.classList.remove('text-locked');
        textCell.style.cursor = "text";
        textCell.title = "Click to edit";

        // Attach events only once ideally, but reassignment is okay for simple handlers
        textCell.onfocus = () => {
            textCell.dataset.originalText = textCell.textContent; // Sync on focus
            textCell.classList.add('editing');
        };
        textCell.onblur = () => {
            textCell.classList.remove('editing');
            doUpdateText(entry.id, textCell);
        };
        textCell.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                textCell.blur(); // Triggers update
            }
        };
    } else {
        textCell.contentEditable = "false";
        textCell.classList.add('text-locked');
        textCell.style.cursor = "not-allowed";
        textCell.title = "Editing disabled while running/playing";
        textCell.onfocus = null;
        textCell.onblur = null;
        textCell.onkeydown = null;
    }

    // Button States
    const isThisPlaying = store.playbackState.is_playing && store.playbackState.filename === entry.filename;
    const isPending = entry.filename && entry.filename.startsWith("pending_");

    // Play Button
    const playCell = row.querySelector('.col-play');
    let playBtn = playCell.querySelector('button');
    if (!playBtn) {
        playBtn = document.createElement('button');
        playBtn.className = 'btn-icon-play';
        playCell.appendChild(playBtn);
    }

    if (isThisPlaying) {
        playBtn.innerHTML = PlayIcons.playing;
        playBtn.classList.add('playing', 'playing-anim');
        playBtn.disabled = true;
        playBtn.style.color = ""; // Start/Reset color
        playBtn.style.borderColor = "";
    } else {
        playBtn.innerHTML = PlayIcons.play;
        playBtn.classList.remove('playing', 'playing-anim');
        playBtn.disabled = isLocked;
        playBtn.title = isLocked ? "Function disabled while running/playing" : "Play audio";
        playBtn.onclick = isLocked ? null : () => doPlay(entry.id, playBtn);

        // On-demand (pending) items get red Play button
        if (isPending) {
            playBtn.classList.add('btn-on-demand');
        } else {
            playBtn.classList.remove('btn-on-demand');
        }
    }

    // Resolve Button
    const rsvCell = row.querySelector('.col-resolve');
    rsvCell.innerHTML = ''; // Clear to rebuild state easier
    if (entry.filename && entry.filename !== "Error" && store.isResolveAvailable) {
        const rsvBtn = document.createElement('button');
        rsvBtn.className = 'btn-icon-resolve';
        rsvBtn.innerHTML = SvgIcons.resolve;
        rsvBtn.disabled = isLocked;
        rsvBtn.title = isLocked ? "Wait for current task" : "Insert to DaVinci Resolve";
        if (!isLocked) {
            rsvBtn.onclick = () => doResolveInsert(entry.id, rsvBtn);
        }
        rsvCell.appendChild(rsvBtn);
    }

    // Delete Button
    const delCell = row.querySelector('.col-delete');
    delCell.innerHTML = '';
    if (entry.filename && entry.filename !== "Error") {
        const delBtn = document.createElement('button');
        delBtn.className = 'btn-icon-delete';
        delBtn.innerHTML = SvgIcons.delete;
        delBtn.disabled = isLocked;
        delBtn.title = isLocked ? "Wait for current task" : "Delete file";
        if (!isLocked) {
            delBtn.onclick = () => doDelete(entry.id, entry.filename);
        }
        delCell.appendChild(delBtn);
    }
}

// --- Action Implementations ---

async function doPlay(id, btn) {
    // 1. Provisional UI Lock: Prevent other playback interactions immediately
    const allPlayBtns = document.querySelectorAll('.btn-icon-play');
    allPlayBtns.forEach(b => b.disabled = true);

    // Optimistic visual update for the clicked button
    btn.classList.add('playing', 'playing-anim');

    // Generate Request ID
    const requestId = crypto.randomUUID();

    try {
        // 2. Send Request with ID
        const res = await api.playAudio(id, requestId);

        if (res.ok && res.data.status === 'ok') {
            // Request Accepted. 
            // The server queue will eventually trigger "playback_change" event.
            // We do NOT manualy unlock buttons here. 
            // We rely on SSE to update the state and thus re-render the buttons enabled/disabled.
            // This ensures meaningful "Playing" or "Queued" UI state during the transition.
        } else {
            await showAlert("Playback Failed", res.data?.message || "Unknown error");
            // Revert state on error
            btn.classList.remove('playing', 'playing-anim');
            allPlayBtns.forEach(b => b.disabled = false); // Unlock

            // Refresh logs to reset state
            const lRes = await api.getLogs();
            if (lRes.ok) store.setLogs(lRes.data);
        }
    } catch (e) {
        console.error("Play failed", e);
        // Revert state
        btn.classList.remove('playing', 'playing-anim');
        allPlayBtns.forEach(b => b.disabled = false); // Unlock
    }
}

async function doDelete(id, filename) {
    if (await showConfirmDialog(filename)) {
        try {
            const res = await api.deleteFile(id);
            if (res.ok && res.data.status === 'ok') {
                const lRes = await api.getLogs();
                if (lRes.ok) store.setLogs(lRes.data);
            } else {
                await showAlert("Delete Failed", res.data?.message);
            }
        } catch (e) {
            await showAlert("Error", "Delete request failed");
        }
    }
}


async function doUpdateText(id, cell) {
    const newText = cell.textContent.trim();
    const oldText = cell.dataset.originalText;

    if (newText === oldText) return;
    if (!newText) {
        cell.textContent = oldText;
        await showAlert("Notice", "Text cannot be empty");
        return;
    }

    try {
        const res = await api.updateText(id, newText);
        if (res.ok && res.data.status === 'ok') {
            // Success. SSE will trigger refresh.
        } else {
            cell.textContent = oldText;
            await showAlert("Update Failed", res.data?.message || "Unknown Error");
        }
    } catch (e) {
        console.error(e);
        cell.textContent = oldText;
        await showAlert("Error", "Update request failed");
    }
}

async function doResolveInsert(id, btn) {
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.5';
    }
    try {
        const res = await api.insertToResolve(id);
        if (res.ok && res.data.status === 'ok') {
            if (btn) {
                btn.style.color = '#fff'; // Flash white
                setTimeout(() => {
                    btn.style.color = '';
                    btn.disabled = false;
                    btn.style.opacity = '1';
                }, 1000);
            }
        } else {
            await showAlert("Insert Failed", res.data?.message);
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        }
    } catch (e) {
        await showAlert("Error", "Req failed");
        if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    }
}

// --- Utils & Modals ---

function scrollToBottom() {
    const container = elements.logTableBody.closest('div');
    if (container) container.scrollTop = container.scrollHeight;
}

function setUILocked(locked, message = "") {
    let overlay = document.getElementById('loading-overlay');

    // Lazy create overlay if missing (same logic as before)
    if (!overlay) {
        createOverlay();
        overlay = document.getElementById('loading-overlay');
    }

    const msgEl = document.getElementById('loading-msg');

    if (locked) {
        if (msgEl) msgEl.textContent = message;
        overlay.style.pointerEvents = 'all';
        overlay.style.opacity = '1';
        elements.browseBtn.disabled = true;
        elements.startStopBtn.classList.add('disabled-temp');
        elements.outputDir.disabled = true;
    } else {
        overlay.style.opacity = '0';
        overlay.style.pointerEvents = 'none';
        elements.browseBtn.disabled = false;
        elements.startStopBtn.classList.remove('disabled-temp');
        elements.outputDir.disabled = false;
        renderStartStopUI(); // Ensure consistent
    }
}

function createOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    // ... Copying simple styles or injecting css class would be better but keeping consistent for now
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background-color:rgba(0,0,0,0.7);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;backdrop-filter:blur(2px);opacity:0;transition:opacity 0.3s;pointer-events:none;";

    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    // Assuming CSS for .spinner exists or we inject it
    if (!document.getElementById('spinner-style')) {
        const style = document.createElement('style');
        style.id = 'spinner-style';
        style.innerHTML = `@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } } .spinner { width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid var(--primary, #a8df65); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px; }`;
        document.head.appendChild(style);
    }

    const msgEl = document.createElement('div');
    msgEl.id = 'loading-msg';
    msgEl.style.cssText = "color:white;font-size:1.2em;font-weight:500;";

    overlay.appendChild(spinner);
    overlay.appendChild(msgEl);
    document.body.appendChild(overlay);
}

function showConfirmDialog(filename) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const msg = document.getElementById('modal-msg');
        const btnYes = document.getElementById('modal-confirm');
        const btnNo = document.getElementById('modal-cancel');

        msg.textContent = `Are you sure you want to delete:\n${filename}?`;
        modal.classList.add('active');

        const cleanup = () => {
            modal.classList.remove('active');
            btnYes.onclick = null;
            btnNo.onclick = null;
        };

        btnYes.onclick = () => { cleanup(); resolve(true); };
        btnNo.onclick = () => { cleanup(); resolve(false); };
    });
}

function showAlert(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('alert-modal');
        const titleEl = document.getElementById('alert-title');
        const msgEl = document.getElementById('alert-msg');
        const btnOk = document.getElementById('alert-ok');

        titleEl.textContent = title;
        msgEl.textContent = message;
        modal.classList.add('active');

        const cleanup = () => {
            modal.classList.remove('active');
            btnOk.onclick = null;
        };

        btnOk.onclick = () => { cleanup(); resolve(); };
    });
}

// Icons
const SvgIcons = {
    resolve: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>`,
    delete: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
    voicevox: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line><line x1="8" y1="22" x2="16" y2="22"></line></svg>`
};

const PlayIcons = {
    play: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`,
    playing: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="playing-anim"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`
};

// Start
init();
