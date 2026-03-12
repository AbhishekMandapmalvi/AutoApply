const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { startBackend, stopBackend, getPort } = require('./python-backend');
const { createTray, destroyTray } = require('./tray');

let mainWindow = null;
let splashWindow = null;

// ---------------------------------------------------------------------------
// Single instance lock
// ---------------------------------------------------------------------------

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ---------------------------------------------------------------------------
// IPC handlers (exposed via preload.js)
// ---------------------------------------------------------------------------

ipcMain.handle('open-external', (_event, url) => {
  if (typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
    shell.openExternal(url);
  }
});

ipcMain.handle('get-version', () => app.getVersion());

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 300,
    frame: false,
    transparent: false,
    resizable: false,
    alwaysOnTop: true,
    backgroundColor: '#0f1923',
    show: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
}

function createMainWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 850,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#0f1923',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${port}`);

  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
  });

  // Minimize to tray instead of closing
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  createTray(mainWindow, app);
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.on('ready', async () => {
  // Clear cached static files to prevent stale JS modules after updates
  const ses = require('electron').session.defaultSession;
  await ses.clearCache();

  createSplashWindow();

  try {
    const { port } = await startBackend();
    createMainWindow(port);
  } catch (err) {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }

    dialog.showErrorBox(
      'AutoApply — Startup Error',
      `Failed to start the backend:\n\n${err.message}\n\nMake sure Python 3.11+ is installed and accessible from the command line.`
    );
    app.quit();
  }
});

app.on('before-quit', async (event) => {
  if (app._isShuttingDown) return;
  app._isShuttingDown = true;

  event.preventDefault();
  destroyTray();

  try {
    await stopBackend();
  } catch {
    // Force quit regardless
  }

  app.exit(0);
});

app.on('window-all-closed', () => {
  // On macOS, apps stay active until Cmd+Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // macOS dock click — show window
  if (mainWindow) {
    mainWindow.show();
  }
});
