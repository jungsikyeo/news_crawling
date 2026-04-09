const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

let mainWindow = null;
let backendProcess = null;
let quitting = false;

const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

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
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, "icon.png")
    : path.join(__dirname, "..", "assets", "icon.png");

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    title: "NewsDesk",
    icon: iconPath,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.loadURL(BACKEND_URL);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

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
