const { app, BrowserWindow, Notification, ipcMain, nativeImage, Tray, Menu } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

let mainWindow = null;
let backendProcess = null;
let tray = null;
let quitting = false;

const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function getIconPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "icon.png")
    : path.join(__dirname, "..", "assets", "icon.png");
}

function getBackendCommand() {
  if (app.isPackaged) {
    const exePath = path.join(
      process.resourcesPath,
      "backend",
      "NewsDesk.exe"
    );
    return { cmd: exePath, args: [], cwd: path.dirname(exePath) };
  }
  // Dev mode: run backend/main.py directly
  const projectRoot = path.join(__dirname, "..");
  return {
    cmd: "python",
    args: [path.join(projectRoot, "backend", "main.py")],
    cwd: projectRoot,
  };
}

function startBackend() {
  const { cmd, args, cwd } = getBackendCommand();
  backendProcess = spawn(cmd, args, {
    cwd,
    stdio: "pipe",
    windowsHide: true,
  });

  backendProcess.stdout?.on("data", (d) => console.log(`[backend] ${d}`));
  backendProcess.stderr?.on("data", (d) => console.error(`[backend] ${d}`));
  backendProcess.on("exit", (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
    if (mainWindow && !quitting) {
      try { mainWindow.close(); } catch (_) { /* already destroyed */ }
    }
  });
}

function waitForBackend(timeout = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const req = http.get(`${BACKEND_URL}/api/crawl/status`, (res) => {
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - start > timeout) {
          reject(new Error("Backend startup timeout"));
        } else {
          setTimeout(check, 300);
        }
      });
      req.setTimeout(1000, () => {
        req.destroy();
        setTimeout(check, 300);
      });
    };
    check();
  });
}

function killBackend() {
  if (backendProcess && !backendProcess.killed) {
    try {
      // Windows: taskkill /T kills the entire process tree
      spawn("taskkill", ["/pid", String(backendProcess.pid), "/T", "/F"], {
        stdio: "ignore",
      });
    } catch (_) {
      // ignore — process may already be dead
    }
    backendProcess = null;
  }
}

async function createWindow() {
  const icon = nativeImage.createFromPath(getIconPath());

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    title: "NewsDesk",
    icon,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.loadURL(BACKEND_URL);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  // 시스템 트레이 — Windows 알림 아이콘 표시에 필요
  tray = new Tray(icon);
  tray.setToolTip("NewsDesk");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "열기", click: () => mainWindow?.show() },
    { label: "종료", click: () => { quitting = true; app.quit(); } },
  ]));
  tray.on("click", () => mainWindow?.show());
}

// Windows 알림에 앱 이름 표시
app.setAppUserModelId("NewsDesk");

// 렌더러에서 알림 요청 수신
ipcMain.on("show-notification", (_event, title, body) => {
  const icon = nativeImage.createFromPath(getIconPath());
  new Notification({ title, body, icon }).show();
});

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
  } catch (e) {
    console.error(e.message);
    app.quit();
    return;
  }
  await createWindow();
});

app.on("window-all-closed", () => {
  quitting = true;
  killBackend();
  if (tray) { tray.destroy(); tray = null; }
  app.quit();
});

app.on("before-quit", () => {
  quitting = true;
  killBackend();
});

// Suppress error dialogs on exit
process.on("uncaughtException", (err) => {
  console.error("Uncaught:", err);
  killBackend();
  app.quit();
});
