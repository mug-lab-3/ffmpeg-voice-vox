const CONFIG_API = '/api/config';
const SPEAKERS_API = '/api/speakers';
const LOGS_API = '/api/logs';
const CONTROL_STATE_API = "/api/control/state";
const CONTROL_PLAY_API = "/api/control/play";
const CONTROL_DELETE_API = "/api/control/delete";

const elements = {
    speaker: document.getElementById('speaker'),
    speedScale: document.getElementById('speedScale'),
    pitchScale: document.getElementById('pitchScale'),
    intonationScale: document.getElementById('intonationScale'),
    volumeScale: document.getElementById('volumeScale'),
    status: document.getElementById('status-msg'),
    logTableBody: document.getElementById('log-table-body'),
    startStopBtn: document.getElementById('start-stop-btn')
};

// Global State
let isSynthesisEnabled = true;
let serverPlaybackState = { is_playing: false, filename: null, remaining: 0 };

// Speaker name cache
let speakerMap = {};

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
            const spName = speakerMap[cfg.speaker] || `ID:${cfg.speaker}`;
            configCell.innerHTML = `<span style="color: var(--primary)">${spName}</span> <span style="font-size: 0.8em; color: #666;">(x${cfg.speedScale.toFixed(2)})</span>`;
            configCell.style.padding = '8px';

            const playCell = document.createElement('td');
            playCell.style.padding = '8px';
            playCell.style.textAlign = 'center';

            if (entry.filename && entry.filename !== "Error" && entry.filename !== "Skipped") {
                const playBtn = document.createElement('button');
                playBtn.id = `btn-${entry.filename}`; // Add ID for easier selection
                // Play Icon (SVG)
                // Visually fix center alignment by nudging right
                const playIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
                playBtn.innerHTML = playIcon;

                playBtn.style.backgroundColor = 'transparent';
                playBtn.style.color = 'var(--primary)';
                playBtn.style.border = '1px solid var(--primary)';
                playBtn.style.borderRadius = '50%';
                playBtn.style.width = '32px';
                playBtn.style.height = '32px';
                playBtn.style.padding = '0';
                playBtn.style.display = 'inline-flex';
                playBtn.style.alignItems = 'center';
                playBtn.style.justifyContent = 'center';
                playBtn.style.cursor = 'pointer';
                playBtn.style.transition = 'all 0.2s';

                // Determine if this file is currently playing
                const isThisPlaying = serverPlaybackState.is_playing && serverPlaybackState.filename === entry.filename;

                if (isThisPlaying) {
                    setPlayingStyle(playBtn);
                } else {
                    // Replay is only enabled when synthesis is STOPPED
                    if (isSynthesisEnabled) {
                        playBtn.disabled = true;
                        playBtn.style.opacity = '0.3';
                        playBtn.style.borderColor = '#555';
                        playBtn.style.color = '#555';
                        playBtn.style.cursor = 'not-allowed';
                        playBtn.title = "Stop server to replay";
                    } else {
                        playBtn.onmouseover = () => { playBtn.style.backgroundColor = 'rgba(168, 223, 101, 0.1)'; };
                        playBtn.onmouseout = () => { playBtn.style.backgroundColor = 'transparent'; };
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

                delBtn.style.backgroundColor = 'transparent';
                delBtn.style.color = '#ff6b6b'; // Red
                delBtn.style.border = 'none';
                delBtn.style.cursor = 'pointer';
                delBtn.style.padding = '4px';
                delBtn.style.opacity = '0.7';
                delBtn.style.transition = 'opacity 0.2s';

                delBtn.onmouseover = () => { delBtn.style.opacity = '1'; };
                delBtn.onmouseout = () => { delBtn.style.opacity = '0.7'; };

                delBtn.onclick = () => deleteFile(entry.filename);

                deleteCell.appendChild(delBtn);
            }

            row.appendChild(timeCell);
            row.appendChild(fileCell);
            row.appendChild(textCell);
            row.appendChild(durCell);
            row.appendChild(configCell);
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

    elements.startStopBtn.addEventListener('click', async () => {
        await toggleControlState();
    });
}

async function loadControlState() {
    try {
        const res = await fetch(CONTROL_STATE_API);
        const data = await res.json();
        isSynthesisEnabled = data.enabled;
        if (data.playback) {
            serverPlaybackState = data.playback;
        }
        updateStartStopUI();
    } catch (e) {
        console.error("Failed to load control state", e);
    }
}

async function toggleControlState() {
    const newState = !isSynthesisEnabled;
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
        }
    } catch (e) {
        console.error("Failed to toggle state", e);
    }
}

function updateStartStopUI() {
    const btn = elements.startStopBtn;
    if (isSynthesisEnabled) {
        btn.textContent = "STOP";
        btn.style.backgroundColor = "#ff6b6b"; // Red-ish for STOP action
        btn.title = "Click to Stop Synthesis";
    } else {
        btn.textContent = "START";
        btn.style.backgroundColor = "var(--primary)"; // Green-ish for START action
        btn.title = "Click to Start Synthesis";
    }
}


function setPlayingStyle(btnElement) {
    const playingIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="playing-anim"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;

    btnElement.innerHTML = playingIcon;
    btnElement.disabled = true;
    btnElement.style.opacity = '1';
    btnElement.style.color = '#fff';
    btnElement.style.backgroundColor = 'var(--primary)';
    btnElement.style.borderColor = 'var(--primary)';
    btnElement.onmouseover = null;
    btnElement.onmouseout = null;

    // Add animation style if not present
    if (!document.getElementById('playing-style')) {
        const style = document.createElement('style');
        style.id = 'playing-style';
        style.innerHTML = `
            @keyframes pulse-opacity {
                0% { opacity: 0.6; }
                50% { opacity: 1; }
                100% { opacity: 0.6; }
            }
            .playing-anim {
                animation: pulse-opacity 1s infinite;
            }
        `;
        document.head.appendChild(style);
    }
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

async function updateConfig(key, value) {
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
        }
    } catch (e) {
        console.error("Update failed", e);
        elements.status.textContent = "Error updating";
    }
}

init();
