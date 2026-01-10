const CONFIG_API = '/api/config';
const SPEAKERS_API = '/api/speakers';
const LOGS_API = '/api/logs';
const CONTROL_STATE_API = "/api/control/state";
const CONTROL_PLAY_API = "/api/control/play";
const CONTROL_DELETE_API = "/api/control/delete";
const CONTROL_RESOLVE_INSERT_API = "/api/control/resolve_insert";
const SYSTEM_BROWSE_API = "/api/system/browse";

const elements = {
    speaker: document.getElementById('speaker'),
    speedScale: document.getElementById('speedScale'),
    pitchScale: document.getElementById('pitchScale'),
    intonationScale: document.getElementById('intonationScale'),
    volumeScale: document.getElementById('volumeScale'),
    status: document.getElementById('status-msg'),
    logTableBody: document.getElementById('log-table-body'),
    startStopBtn: document.getElementById('start-stop-btn'),
    outputDir: document.getElementById('outputDir'),
    browseBtn: document.getElementById('browseOutputDir'),
    dirStatus: document.getElementById('dir-status'),
    resolveStatus: document.getElementById('resolve-status')
};

// Global State
let isSynthesisEnabled = true;
let isResolveAvailable = false;
let serverPlaybackState = { is_playing: false, filename: null, remaining: 0 };

// Speaker name cache
let speakerMap = {};
// Log cache for optimization
let lastLogsJson = "";

const valueDisplays = {
    speedScale: document.getElementById('val-speedScale'),
    pitchScale: document.getElementById('val-pitchScale'),
    intonationScale: document.getElementById('val-intonationScale'),
    volumeScale: document.getElementById('val-volumeScale')
};

// Initialize
async function init() {
    await loadSpeakers();
    await loadConfig();
    await loadControlState();
    setupListeners();
    // Poll log and control state more frequently for smooth sync
    startPolling();
}

function startPolling() {
    setInterval(async () => {
        // Background tabs shouldn't poll logs to save resources
        // Instead, send a lightweight heartbeat to keep server alive
        if (document.hidden) {
            await sendHeartbeat();
            return;
        }

        await loadControlState(); // Check state first
        await loadLogs();
    }, 1000); // 1s polling
}

async function sendHeartbeat() {
    // Heartbeat every 10 seconds effectively (since we return early above loop)
    // But setInterval is 1s. Simple counter or timestamp check is better.
    const now = Date.now();
    if (!window.lastHeartbeat || now - window.lastHeartbeat > 10000) {
        window.lastHeartbeat = now;
        try {
            await fetch('/api/heartbeat');
        } catch (e) {
            // Ignore errors in background
        }
    }
}

async function loadLogs() {
    try {
        const res = await fetch(LOGS_API);
        const logs = await res.json();
        const currentJson = JSON.stringify(logs);

        // Optimize: Only render if data changed or we suspect a state change needs re-render (e.g. playback update handled separately but logs might reflect it)
        // Usually playback state is separate, but we use it in renderLogs. 
        // Ideally we should also check if serverPlaybackState changed meaningfully for rendering.
        // For now, strict log content check plus explicit re-render calls when playback starts are enough, 
        // as polling will pick up log updates. 
        // If we want to animate play button via re-render, we need to be careful. 
        // Actually, we should just update the class of the existing button if only playback state changes, but full re-render is simpler.
        // To fix flickering, CSS handles hover. Re-rendering is fine if it doesn't happen 60fps, but 1s is okay IF styles are CSS.
        // But preventing unnecessary DOM thrashing is still good.
        if (currentJson === lastLogsJson && !window.forceLogRender) {
            // We still need to update play buttons state if playback changed but logs didn't?
            // renderLogs uses serverPlaybackState. 
            // Let's rely on forceLogRender or just check if playback state changed.
            // For simplicity to fix flicker: The CSS fix solves flicker even with re-render.
            // Optimization: skip re-render if identical.
            // But we need to update 'playing' class if playback state changed.
            // Let's just always render for now, but rely on CSS for stable hover.
            // actually, the user specifically mentioned flickering, which even with CSS might happen if DOM node is replaced under cursor.
            // So: preventing re-render is CRITICAL for stable hover if we replace DOM.
            // We need to compare logs AND playback state.
            const playbackKey = `${serverPlaybackState.is_playing}_${serverPlaybackState.filename}`;
            if (currentJson === lastLogsJson && window.lastPlaybackKey === playbackKey) {
                return;
            }
            window.lastPlaybackKey = playbackKey;
        }

        lastLogsJson = currentJson;
        window.forceLogRender = false;
        renderLogs(logs);
    } catch (e) {
        console.error("Log fetch failed", e);
    }
}

function renderLogs(logs) {
    elements.logTableBody.innerHTML = '';
    // Newest first
    const reversed = logs.slice().reverse();

    reversed.forEach(entry => {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid #333';

        if (typeof entry === 'string') {
            // Legacy support
            const cell = document.createElement('td');
            cell.colSpan = 7;
            cell.textContent = entry;
            cell.style.padding = '8px';
            cell.style.color = '#888';
            row.appendChild(cell);
        } else {
            // Structured log
            const timeCell = document.createElement('td');
            timeCell.textContent = entry.timestamp;
            timeCell.style.padding = '8px';
            timeCell.style.color = '#888';

            const fileCell = document.createElement('td');
            fileCell.textContent = entry.filename || '-';
            fileCell.style.padding = '8px';
            fileCell.style.color = '#aaa';
            fileCell.style.fontSize = '0.85em';

            const textCell = document.createElement('td');
            textCell.textContent = entry.text;
            textCell.style.padding = '8px';
            textCell.style.fontWeight = 'bold';

            const durCell = document.createElement('td');
            durCell.textContent = entry.duration;
            durCell.style.padding = '8px';
            durCell.style.color = '#aaa';

            const configCell = document.createElement('td');
            const cfg = entry.config;
            const spName = speakerMap[cfg.speaker_id] || `ID:${cfg.speaker_id}`;
            configCell.innerHTML = `<span style="color: var(--primary)">${spName}</span> <span style="font-size: 0.8em; color: #666;">(x${cfg.speed_scale.toFixed(2)})</span>`;
            configCell.style.padding = '8px';

            const resolveCell = document.createElement('td');
            resolveCell.style.padding = '8px';
            resolveCell.style.textAlign = 'center';

            if (entry.filename && entry.filename !== "Error" && isResolveAvailable) {
                const rsvBtn = document.createElement('button');
                // Film/Timeline Icon
                const rsvIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>`;
                rsvBtn.className = 'btn-icon-resolve';
                rsvBtn.innerHTML = rsvIcon;

                if (isSynthesisEnabled) {
                    // Disabled when synthesis is running
                    rsvBtn.disabled = true;
                    rsvBtn.title = "Stop server to insert";
                } else {
                    // Enabled when stopped
                    rsvBtn.disabled = false;
                    rsvBtn.title = "Insert to DaVinci Resolve";
                    rsvBtn.onclick = () => insertToResolve(entry.filename, rsvBtn);
                }

                resolveCell.appendChild(rsvBtn);
            }

            const playCell = document.createElement('td');
            playCell.style.padding = '8px';
            playCell.style.textAlign = 'center';

            if (entry.filename && entry.filename !== "Error" && entry.filename !== "Skipped") {
                const playBtn = document.createElement('button');
                playBtn.id = `btn-${entry.filename}`; // Add ID for easier selection
                // Play Icon (SVG)
                // Visually fix center alignment by nudging right
                const playIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
                playBtn.className = 'btn-icon-play';
                playBtn.innerHTML = playIcon;

                // Determine if this file is currently playing
                const isThisPlaying = serverPlaybackState.is_playing && serverPlaybackState.filename === entry.filename;

                if (isThisPlaying) {
                    // setPlayingStyle(playBtn);
                    playBtn.classList.add('playing', 'playing-anim');
                    playBtn.disabled = true;
                    // Actually playing state might want to allow stop? but API control/play is just play.
                    // For now match previous logic: disabled style but active look.
                } else {
                    // Replay is only enabled when synthesis is STOPPED
                    if (isSynthesisEnabled) {
                        playBtn.disabled = true;
                        playBtn.title = "Stop server to replay";
                    } else {
                        playBtn.title = "Play audio";
                        playBtn.disabled = false;
                        playBtn.onclick = () => playAudio(entry.filename, playBtn);
                    }
                }

                playCell.appendChild(playBtn);
            }

            // Delete Button
            const deleteCell = document.createElement('td');
            deleteCell.style.padding = '8px';
            deleteCell.style.textAlign = 'center';

            if (entry.filename && entry.filename !== "Error") {
                const delBtn = document.createElement('button');
                // Trash Icon
                const trashIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
                delBtn.innerHTML = trashIcon;

                delBtn.className = 'btn-icon-delete';
                delBtn.innerHTML = trashIcon;
                delBtn.title = "Delete file";
                delBtn.onclick = () => deleteFile(entry.filename);

                deleteCell.appendChild(delBtn);
            }

            row.appendChild(timeCell);
            row.appendChild(fileCell);
            row.appendChild(textCell);
            row.appendChild(durCell);
            row.appendChild(configCell);
            row.appendChild(resolveCell);
            row.appendChild(deleteCell);

            // Insert Play at beginning
            row.insertBefore(playCell, row.firstChild);
        }
        elements.logTableBody.appendChild(row);
    });
}

async function loadSpeakers() {
    try {
        const res = await fetch(SPEAKERS_API);
        const speakers = await res.json();
        speakerMap = speakers;

        elements.speaker.innerHTML = '';
        for (const [id, name] of Object.entries(speakers)) {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = name;
            elements.speaker.appendChild(option);
        }
    } catch (e) {
        console.error("Failed to load speakers", e);
        elements.status.textContent = "Error loading speakers";
    }
}

async function loadConfig() {
    try {
        const res = await fetch(CONFIG_API);
        const config = await res.json();

        // Apply to UI
        for (const key in config) {
            if (elements[key]) {
                elements[key].value = config[key];
                if (valueDisplays[key]) {
                    valueDisplays[key].textContent = Number(config[key]).toFixed(2);
                }
            }
        }

        // Handle Output Dir
        if (config.outputDir) {
            elements.outputDir.value = config.outputDir;
            elements.dirStatus.textContent = "";
        } else {
            elements.dirStatus.textContent = "Please set an output directory to start.";
            elements.dirStatus.style.color = "#ff6b6b";
        }

        // Handle Resolve Status Update
        if (config.resolve_available !== undefined) {
            updateResolveStatus(config.resolve_available);
        }

        // Initial UI State update happens in loadControlState->updateStartStopUI usually,
        // but checking empty dir is needed here too.
        checkStartability();

    } catch (e) {
        console.error("Failed to load config", e);
    }
}

function setupListeners() {
    const keys = ['speaker', 'speedScale', 'pitchScale', 'intonationScale', 'volumeScale'];

    keys.forEach(key => {
        elements[key].addEventListener('input', (e) => {
            // Update display immediately for sliders
            if (valueDisplays[key]) {
                valueDisplays[key].textContent = Number(e.target.value).toFixed(2);
            }
        });

        elements[key].addEventListener('change', async (e) => {
            // Send update on commit (mouse up for sliders)
            const value = (key === 'speaker') ? parseInt(e.target.value) : parseFloat(e.target.value);
            await updateConfig(key, value);
        });
    });



    elements.browseBtn.addEventListener('click', async () => {
        if (elements.browseBtn.classList.contains('disabled') || elements.browseBtn.disabled) return;

        setUILocked(true, "Selecting Directory...");

        try {
            const res = await fetch(SYSTEM_BROWSE_API, { method: 'POST' });
            const data = await res.json();

            if (data.status === 'ok') {
                const path = data.path;
                elements.outputDir.value = path;
                await updateConfig('outputDir', path, true);

                // UX Refinement: Wait for logs to be fetched and rendered BEFORE unlocking
                // The server has already reloaded the history in updateConfig call
                await loadLogs();
            } else if (data.status === 'cancelled') {
                // Do nothing
            } else {
                await showAlert("Error", data.message || "Failed to open dialog");
            }
        } catch (e) {
            console.error("Browse failed", e);
            await showAlert("Error", "Failed to trigger directory browser");
        } finally {
            setUILocked(false);
        }
    });

    elements.startStopBtn.addEventListener('click', async () => {
        if (elements.startStopBtn.classList.contains('disabled')) return;
        await toggleControlState();
    });
}

function setUILocked(locked, message = "") {
    let overlay = document.getElementById('loading-overlay');

    // Create overlay if not exists
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        overlay.style.zIndex = '9999';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.backdropFilter = 'blur(2px)';
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.3s';
        overlay.style.pointerEvents = 'none'; // Initially click-through but becomes blocking when active

        const spinner = document.createElement('div');
        spinner.className = 'spinner'; // Assuming no spinner css exists, we add inline
        spinner.style.width = '40px';
        spinner.style.height = '40px';
        spinner.style.border = '4px solid rgba(255, 255, 255, 0.3)';
        spinner.style.borderTop = '4px solid var(--primary, #a8df65)';
        spinner.style.borderRadius = '50%';
        spinner.style.marginBottom = '15px';

        // Add spinner animation
        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .spinner { animation: spin 1s linear infinite; }
        `;
        document.head.appendChild(style);

        const msgEl = document.createElement('div');
        msgEl.id = 'loading-msg';
        msgEl.style.color = 'white';
        msgEl.style.fontSize = '1.2em';
        msgEl.style.fontWeight = '500';

        overlay.appendChild(spinner);
        overlay.appendChild(msgEl);
        document.body.appendChild(overlay);
    }

    const msgEl = document.getElementById('loading-msg');

    if (locked) {
        if (msgEl) msgEl.textContent = message;
        overlay.style.pointerEvents = 'all';
        overlay.style.opacity = '1';

        // Disable main buttons
        elements.browseBtn.disabled = true;
        elements.startStopBtn.classList.add('disabled-temp');
        elements.outputDir.disabled = true;
    } else {
        overlay.style.opacity = '0';
        overlay.style.pointerEvents = 'none';

        // Re-enable
        elements.browseBtn.disabled = false;
        elements.startStopBtn.classList.remove('disabled-temp');
        elements.outputDir.disabled = false;

        // Restore logical state
        checkStartability();
        updateStartStopUI(); // Ensure consistent state
    }
}

async function loadControlState() {
    try {
        const res = await fetch(CONTROL_STATE_API);
        const data = await res.json();
        isSynthesisEnabled = data.enabled;
        if (data.playback) {
            serverPlaybackState = data.playback;
        }
        if (data.resolve_available !== undefined) {
            updateResolveStatus(data.resolve_available);
        }
        updateStartStopUI();
    } catch (e) {
        console.error("Failed to load control state", e);
    }
}

async function toggleControlState() {
    const newState = !isSynthesisEnabled;

    // If we are enabling, basic client-side check first (server double checks)
    if (newState) {
        if (!elements.outputDir.value.trim()) {
            await showAlert("Configuration Error", "Please set an output directory first.");
            return;
        }
    }

    try {
        const res = await fetch(CONTROL_STATE_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newState })
        });
        const data = await res.json();

        if (data.status === 'ok') {
            isSynthesisEnabled = data.enabled;
            updateStartStopUI();
        } else {
            // Error from server (e.g. invalid dir)
            await showAlert("Error", data.message || "Failed to change state");
            // Revert UI state if needed (usually handled by next poll, but good to ensure)
            loadControlState();
        }
    } catch (e) {
        console.error("Failed to toggle state", e);
        await showAlert("Connection Error", `Failed to communicate with server: ${e.message}`);
    }
}

function updateStartStopUI() {
    const btn = elements.startStopBtn;
    const dirInput = elements.outputDir;
    const browseBtn = elements.browseBtn;

    if (isSynthesisEnabled) {
        btn.textContent = "STOP";
        btn.style.backgroundColor = "#ff6b6b"; // Red-ish for STOP action
        btn.title = "Click to Stop Synthesis";
        btn.classList.remove('disabled');
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';

        // Lock Input when Running
        dirInput.disabled = true;
        browseBtn.disabled = true;
        browseBtn.style.opacity = '0.5';
        dirInput.style.opacity = '0.5';

    } else {
        btn.textContent = "START";
        btn.style.backgroundColor = "var(--primary)"; // Green-ish for START action
        btn.title = "Click to Start Synthesis";

        // Unlock Input when Stopped
        dirInput.disabled = false;
        browseBtn.disabled = false;
        browseBtn.style.opacity = '1';
        dirInput.style.opacity = '1';

        checkStartability();
    }
}

function checkStartability() {
    const btn = elements.startStopBtn;
    if (isSynthesisEnabled) return; // Should be handled by updateStartStopUI YES branch

    const hasDir = elements.outputDir.value.trim().length > 0;

    if (hasDir) {
        btn.classList.remove('disabled');
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    } else {
        btn.classList.add('disabled');
        btn.style.opacity = '0.5';
        btn.style.cursor = 'not-allowed';
    }
}


function setPlayingStyle(btnElement) {
    // Legacy support or fallback if needed, but now handled by CSS classes
    btnElement.classList.add('playing', 'playing-anim');
}

async function playAudio(filename, btnElement) {
    setPlayingStyle(btnElement);

    try {
        const res = await fetch(CONTROL_PLAY_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const data = await res.json();

        if (data.status === 'ok') {
            // Set local timeout to reset based on duration
            // Note: The periodic poll will also keep checking, this is for immediate feedback
            const durationMs = data.duration * 1000;
            setTimeout(() => {
                // We let the polling handle the reset to avoid race conditions 
                // or we can force a poll
                loadControlState().then(loadLogs);
            }, durationMs + 200); // Add small buffer
        } else {
            console.error("Play error", data.message);
            await showAlert("Playback Failed", data.message);
            // Force refresh
            loadLogs();
        }
    } catch (e) {
        console.error("Play request failed", e);
        loadLogs();
    }
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

async function deleteFile(filename) {
    const confirmed = await showConfirmDialog(filename);
    if (!confirmed) return;

    try {
        const res = await fetch(CONTROL_DELETE_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            // Update logs immediately
            loadLogs();
        } else {
            await showAlert("Delete Failed", data.message);
        }
    } catch (e) {
        console.error("Delete request failed", e);
        await showAlert("Error", "Delete request failed");
    }
}

async function insertToResolve(filename, btnElement) {
    if (btnElement) {
        btnElement.disabled = true;
        btnElement.style.opacity = '0.5';
    }

    try {
        const res = await fetch(CONTROL_RESOLVE_INSERT_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const data = await res.json();

        if (data.status === 'ok') {
            // Success animation or feedback could go here
            if (btnElement) {
                btnElement.style.color = '#fff';
                setTimeout(() => {
                    // Re-enable if still stopped? Wait for rerender or just reset style
                    // Actually, renderLogs runs frequently, so state resets.
                    // Just purely for visual feedback:
                    btnElement.style.color = '#a8df65';
                    btnElement.disabled = false;
                    btnElement.style.opacity = '1';
                }, 1000);
            }
        } else {
            await showAlert("Insert Failed", data.message || "Unknown error");
            if (btnElement) {
                btnElement.disabled = false;
                btnElement.style.opacity = '1';
            }
        }
    } catch (e) {
        console.error("Resolve insert failed", e);
        await showAlert("Error", "Failed to communicate with server");
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.style.opacity = '1';
        }
    }
}

function updateResolveStatus(available) {
    isResolveAvailable = available;
    const el = elements.resolveStatus;
    if (available) {
        el.innerHTML = `<span style="width: 6px; height: 6px; border-radius: 50%; background-color: #a8df65;"></span> Connected`;
        el.style.color = "#a8df65";
        el.style.borderColor = "#a8df65";
    } else {
        el.innerHTML = `<span style="width: 6px; height: 6px; border-radius: 50%; background-color: #555;"></span> Not Found`;
        el.style.color = "#666";
        el.style.borderColor = "#444";
    }
}

async function updateConfig(key, value, isOutputDir = false) {
    elements.status.textContent = "Updating...";
    elements.status.classList.add('active');

    try {
        const payload = {};
        payload[key] = value;

        const res = await fetch(CONFIG_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.status === 'ok') {
            elements.status.textContent = "State: Synced";
            setTimeout(() => {
                elements.status.classList.remove('active');
            }, 500);

            if (isOutputDir) {
                elements.dirStatus.textContent = "Directory Set!";
                elements.dirStatus.style.color = "var(--primary)";
                setTimeout(() => { elements.dirStatus.textContent = ""; }, 2000);
                checkStartability();
            }
        }
    } catch (e) {
        console.error("Update failed", e);
        elements.status.textContent = "Error updating";
        if (isOutputDir) {
            elements.dirStatus.textContent = "Update failed";
        }
    }
}

init();
