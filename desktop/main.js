#!/usr/bin/env node
/**
 * Anton Egon - Electron Main Process
 * Spawns Python backend and provides desktop features:
 * - System Tray
 * - Global Hotkeys
 * - Auto-detect Teams/Meet
 * - Mini-Player overlay
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, Notification, globalShortcut, screen } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const Store = require('electron-store');
const localShortcut = require('electron-localshortcut');
const notifier = require('node-notifier');

// ─── CONFIGURATION ───────────────────────────────────────────────

const store = new Store();
const isDev = process.argv.includes('--dev');

// Backend configuration
const PYTHON_CMD = process.platform === 'win32' ? 'python' : 'python3';
const BACKEND_SCRIPT = path.join(__dirname, '..', 'ui', 'web_dashboard.py');
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';

// ─── STATE ───────────────────────────────────────────────────────

let mainWindow = null;
let miniPlayerWindow = null;
let pythonProcess = null;
let tray = null;
let isBackendRunning = false;

// ─── PYTHON BACKEND SPAWNING ───────────────────────────────────────

function spawnPythonBackend() {
    console.log('Spawning Python backend...');
    
    // Spawn Python backend
    pythonProcess = spawn(PYTHON_CMD, [BACKEND_SCRIPT], {
        cwd: path.join(__dirname, '..'),
        stdio: ['ignore', 'pipe', 'pipe']
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python] ${data}`);
        // Check if backend is ready
        if (data.toString().includes('Starting web dashboard') || data.toString().includes('Uvicorn running')) {
            isBackendRunning = true;
            console.log('Backend is ready');
        }
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python Error] ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python backend exited with code ${code}`);
        isBackendRunning = false;
        pythonProcess = null;
        
        // Restart if unexpected exit
        if (code !== 0 && app.isReady()) {
            console.log('Restarting Python backend...');
            setTimeout(spawnPythonBackend, 2000);
        }
    });

    pythonProcess.on('error', (err) => {
        console.error('Failed to spawn Python backend:', err);
        showNotification('Error', 'Failed to start backend. Check Python installation.');
    });
}

function killPythonBackend() {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
        isBackendRunning = false;
    }
}

// ─── MAIN WINDOW ──────────────────────────────────────────────────

function createMainWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 600,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        icon: path.join(__dirname, 'build', 'icon.png'),
        title: 'Anton Egon - Dashboard'
    });

    // Load the web dashboard
    mainWindow.loadURL(`http://${BACKEND_HOST}:${BACKEND_PORT}`);

    // Dev tools in dev mode
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Register local shortcuts (only when window focused)
    registerLocalShortcuts();
}

// ─── MINI-PLAYER OVERLAY ──────────────────────────────────────────

function createMiniPlayer() {
    if (miniPlayerWindow) {
        miniPlayerWindow.focus();
        return;
    }

    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    miniPlayerWindow = new BrowserWindow({
        width: 400,
        height: 300,
        x: width - 420,
        y: height - 320,
        frame: false,
        alwaysOnTop: true,
        resizable: true,
        transparent: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    miniPlayerWindow.loadURL(`http://${BACKEND_HOST}:${BACKEND_PORT}?mode=mini`);
    
    miniPlayerWindow.on('closed', () => {
        miniPlayerWindow = null;
    });
}

// ─── SYSTEM TRAY ─────────────────────────────────────────────────

function createTray() {
    const iconPath = path.join(__dirname, 'build', 'tray-icon.png');
    const trayIcon = nativeImage.createFromPath(iconPath);
    
    // Create tray
    tray = new Tray(trayIcon);

    // Context menu
    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Show Dashboard',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                } else {
                    createMainWindow();
                }
            }
        },
        {
            label: 'Mini-Player',
            click: () => createMiniPlayer()
        },
        { type: 'separator' },
        {
            label: 'Mood',
            submenu: [
                { label: 'Neutral', click: () => setMood('neutral') },
                { label: 'Professional', click: () => setMood('professional') },
                { label: 'Friendly', click: () => setMood('friendly') },
                { label: 'Serious', click: () => setMood('serious') }
            ]
        },
        {
            label: 'Outfit',
            submenu: [
                { label: 'Skjorta 1', click: () => setOutfit('outfit_shirt_01') },
                { label: 'Skjorta 2', click: () => setOutfit('outfit_shirt_02') },
                { label: 'T-shirt', click: () => setOutfit('outfit_tshirt') },
                { label: 'Glasögon', click: () => setOutfit('outfit_glasses') },
                { label: 'Casual', click: () => setOutfit('outfit_casual') }
            ]
        },
        { type: 'separator' },
        {
            label: 'Freeze Video (F9)',
            click: () => triggerAction('freeze')
        },
        {
            label: 'Emergency Kill (F10)',
            click: () => triggerAction('kill')
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                killPythonBackend();
                app.quit();
            }
        }
    ]);

    tray.setToolTip('Anton Egon - AI Meeting Representative');
    tray.setContextMenu(contextMenu);

    // Click to show window
    tray.on('click', () => {
        if (mainWindow) {
            mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
        } else {
            createMainWindow();
        }
    });
}

// ─── GLOBAL HOTKEYS ──────────────────────────────────────────────

function registerGlobalShortcuts() {
    // F9: Freeze video
    globalShortcut.register('F9', () => {
        triggerAction('freeze');
        showNotification('Anton Egon', 'Video frozen');
    });

    // F10: Emergency kill
    globalShortcut.register('F10', () => {
        triggerAction('kill');
        showNotification('Anton Egon', 'Emergency kill activated');
    });

    // Cmd/Ctrl+Shift+A: Quick ingest
    const ingestKey = process.platform === 'darwin' ? 'Command+Shift+A' : 'Ctrl+Shift+A';
    globalShortcut.register(ingestKey, () => {
        triggerAction('quick_ingest');
        showNotification('Anton Egon', 'Quick ingest activated');
    });

    console.log('Global shortcuts registered');
}

function unregisterGlobalShortcuts() {
    globalShortcut.unregisterAll();
}

function registerLocalShortcuts() {
    if (!mainWindow) return;

    // Local shortcuts (only when window focused)
    localShortcut.register(mainWindow, 'CmdOrCtrl+R', () => {
        mainWindow.reload();
    });

    localShortcut.register(mainWindow, 'CmdOrCtrl+Shift+I', () => {
        mainWindow.webContents.openDevTools();
    });
}

// ─── ACTIONS ───────────────────────────────────────────────────────

function setMood(mood) {
    store.set('mood', mood);
    // Send to backend via API
    if (isBackendRunning) {
        fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/mood`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mood })
        }).catch(err => console.error('Failed to set mood:', err));
    }
    showNotification('Anton Egon', `Mood set to ${mood}`);
}

function setOutfit(outfit) {
    store.set('outfit', outfit);
    // Send to backend via API
    if (isBackendRunning) {
        fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/outfit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ outfit })
        }).catch(err => console.error('Failed to set outfit:', err));
    }
    showNotification('Anton Egon', `Outfit changed to ${outfit}`);
}

function triggerAction(action) {
    // Send to backend via API
    if (isBackendRunning) {
        fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        }).catch(err => console.error('Failed to trigger action:', err));
    }
}

// ─── AUTO-DETECT TEAMS/MEET ───────────────────────────────────────

function detectMeetingApps() {
    // Windows: Check for Teams/Meet processes
    if (process.platform === 'win32') {
        exec('tasklist', (err, stdout) => {
            if (err) return;
            
            const hasTeams = stdout.toLowerCase().includes('teams.exe');
            const hasMeet = stdout.toLowerCase().includes('chrome.exe'); // Simplified
            
            if (hasTeams && !store.get('teams_notified', false)) {
                showNotification('Anton Egon', 'Teams detected. Join as Notetaker?');
                store.set('teams_notified', true);
            }
        });
    }
    
    // macOS: Check for Teams/Meet
    if (process.platform === 'darwin') {
        exec('ps aux', (err, stdout) => {
            if (err) return;
            
            const hasTeams = stdout.toLowerCase().includes('microsoft teams');
            const hasMeet = stdout.toLowerCase().includes('google meet');
            
            if (hasTeams && !store.get('teams_notified', false)) {
                showNotification('Anton Egon', 'Teams detected. Join as Notetaker?');
                store.set('teams_notified', true);
            }
        });
    }
}

// ─── NOTIFICATIONS ──────────────────────────────────────────────────

function showNotification(title, message) {
    new Notification({
        title,
        body: message,
        silent: false
    }).show();
}

// ─── APP LIFECYCLE ─────────────────────────────────────────────────

app.whenReady().then(() => {
    console.log('Anton Egon starting...');
    
    // Spawn Python backend
    spawnPythonBackend();
    
    // Wait for backend to be ready
    setTimeout(() => {
        createMainWindow();
        createTray();
        registerGlobalShortcuts();
        
        // Start meeting app detection
        setInterval(detectMeetingApps, 5000);
    }, 3000);
});

app.on('window-all-closed', () => {
    // Don't quit on macOS when all windows closed (keep tray active)
    if (process.platform !== 'darwin') {
        killPythonBackend();
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
    }
});

app.on('will-quit', () => {
    unregisterGlobalShortcuts();
    killPythonBackend();
});

// ─── ERROR HANDLING ───────────────────────────────────────────────

process.on('uncaughtException', (err) => {
    console.error('Uncaught exception:', err);
    showNotification('Error', 'An unexpected error occurred. Check logs.');
});
