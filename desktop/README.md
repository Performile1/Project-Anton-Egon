# Anton Egon - Desktop App (Electron)

Cross-platform desktop application for Anton Egon AI Meeting Representative.

## Architecture

The desktop app uses **Electron** as a wrapper around the existing Python/FastAPI backend:

- **Backend (Python):** Runs as a local server (`ui/web_dashboard.py`) on port 8000
- **Frontend (Electron):** Loads the web dashboard in an iframe with desktop enhancements
- **IPC Bridge:** Secure communication between Electron and renderer process

## Desktop Features

### System Tray
- Quick access to mood, outfit, and actions
- Shows/hides main window
- Mini-player toggle

### Global Hotkeys (work even when app is minimized)
- **F9:** Freeze video (simulates network lag)
- **F10:** Emergency kill-switch
- **Cmd/Ctrl+Shift+A:** Quick ingest of selected file

### Auto-Detection
- Detects when Teams/Meet is launched
- Shows notification to join as Notetaker

### Mini-Player
- Floating overlay window (always on top)
- Quick controls during meetings
- Positioned near bottom-right corner

## Installation

### Prerequisites
- **Node.js** 18+ (https://nodejs.org/)
- **Python** 3.11+ (https://www.python.org/)
- **npm** (comes with Node.js)

### Development Mode
```bash
cd desktop
npm install
npm start
```

### Building

#### Windows (.exe)
```bash
cd desktop
./build-windows.bat
# or
npm run build:win
```
Output: `dist/AntonEgon-{version}-setup.exe`

#### macOS (.dmg)
```bash
cd desktop
chmod +x build-mac.sh
./build-mac.sh
# or
npm run build:mac
```
Output: `dist/Anton Egon-{version}.dmg`

#### Both Platforms
```bash
npm run build:all
```

## Build Resources

Before building, ensure you have the required icons in `desktop/build/`:

- `icon.png` - 512x512 PNG (Linux)
- `icon.ico` - Windows icon (256x256)
- `icon.icns` - macOS icon (Apple Silicon + Intel)
- `tray-icon.png` - System tray icon (32x32 or 64x64)

### Generating Icons
```bash
npm install -g electron-icon-builder
electron-icon-builder --input=icon.png --output=./build
```

## macOS Code Signing

For macOS distribution, you need:
- Apple Developer Certificate
- `entitlements.mac.plist` (included)
- Code signing identity

Edit `package.json` to set your signing identity:
```json
"mac": {
  "identity": "YOUR_APPLE_IDENTITY"
}
```

## Project Structure

```
desktop/
├── main.js              # Electron main process
├── preload.js           # IPC bridge
├── package.json         # Electron config
├── renderer/
│   └── index.html       # Frontend loader
├── build/
│   ├── README.md        # Build resources guide
│   └── entitlements.mac.plist  # macOS entitlements
├── build-windows.bat    # Windows build script
└── build-mac.sh         # macOS build script
```

## Troubleshooting

### Backend won't start
- Ensure Python 3.11+ is installed
- Check that `../ui/web_dashboard.py` exists
- Verify dependencies: `pip install -r ../requirements.txt`

### Build fails
- Ensure Node.js 18+ is installed
- Delete `node_modules` and `dist`, then `npm install` again
- Check for missing build resources (icons)

### Global hotkeys not working
- On Windows, run as Administrator
- On macOS, grant accessibility permissions in System Settings
- Check for conflicting shortcuts in other apps

### macOS Gatekeeper blocking app
- Right-click app → Open (first time only)
- Or disable Gatekeeper for testing:
  ```bash
  sudo spctl --master-disable
  ```

## Development

### Adding new IPC handlers

1. Add handler in `main.js`:
```javascript
ipcMain.handle('my-action', async (event, arg) => {
    // your code
    return result;
});
```

2. Expose in `preload.js`:
```javascript
contextBridge.exposeInMainWorld('electronAPI', {
    myAction: (arg) => ipcRenderer.invoke('my-action', arg)
});
```

3. Use in renderer:
```javascript
const result = await window.electronAPI.myAction(arg);
```

### Adding new global hotkeys

In `main.js`:
```javascript
globalShortcut.register('CmdOrCtrl+K', () => {
    triggerAction('my-custom-action');
});
```

## License

MIT License - See LICENSE file in root directory.
