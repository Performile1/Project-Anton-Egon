/**
 * Anton Egon - Electron Preload Script
 * Secure bridge between Electron main process and renderer process
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer
contextBridge.exposeInMainWorld('electronAPI', {
    // Platform info
    platform: process.platform,
    
    // System tray actions
    setMood: (mood) => ipcRenderer.invoke('set-mood', mood),
    setOutfit: (outfit) => ipcRenderer.invoke('set-outfit', outfit),
    
    // Actions
    triggerAction: (action) => ipcRenderer.invoke('trigger-action', action),
    
    // Mini-player
    showMiniPlayer: () => ipcRenderer.invoke('show-mini-player'),
    hideMiniPlayer: () => ipcRenderer.invoke('hide-mini-player'),
    
    // Notifications
    showNotification: (title, message) => ipcRenderer.invoke('show-notification', title, message),
    
    // Backend status
    getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
    
    // Store
    getStoreValue: (key) => ipcRenderer.invoke('get-store-value', key),
    setStoreValue: (key, value) => ipcRenderer.invoke('set-store-value', key, value)
});

// Listen for backend events
ipcRenderer.on('backend-ready', () => {
    console.log('Backend is ready');
});

ipcRenderer.on('backend-error', (event, error) => {
    console.error('Backend error:', error);
});

ipcRenderer.on('meeting-detected', (event, platform) => {
    console.log('Meeting detected:', platform);
});
