const { app, BrowserWindow, Notification, ipcMain, nativeImage, Tray, Menu, shell, dialog } = require("electron");
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
    if (!quitting && mainWindow) {
      dialog.showErrorBox(
        "NewsDesk 오류",
        `백엔드 서버가 종료되었습니다 (코드: ${code}).\n앱을 다시 시작해 주세요.`
      );
      quitting = true;
      app.quit();
    }
  });
}

function waitForBackend(timeout = 45000) {
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
    const pid = backendProcess.pid;
    backendProcess = null;
    try {
      // Windows: taskkill /T kills the entire process tree (자식 프로세스 포함)
      const result = spawn("taskkill", ["/pid", String(pid), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
      });
      result.on("exit", () => {
        // 프로세스 트리가 제대로 종료되지 않았을 경우, 포트를 점유하는 프로세스 추가 정리
        const { execSync } = require("child_process");
        try {
          const out = execSync('netstat -ano | findstr ":8000" | findstr "LISTEN"', { windowsHide: true }).toString();
          const match = out.match(/\s(\d+)\s*$/m);
          if (match) {
            spawn("taskkill", ["/pid", match[1], "/T", "/F"], { stdio: "ignore", windowsHide: true });
          }
        } catch (_) { /* no listener on port — ok */ }
      });
    } catch (_) {
      // ignore — process may already be dead
    }
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

  // 외부 링크(target="_blank")를 시스템 기본 브라우저에서 열기
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

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

// 렌더러에서 캐시 삭제 요청 수신
ipcMain.handle("clear-cache", async () => {
  const ses = mainWindow?.webContents?.session;
  if (ses) {
    await ses.clearCache();
    await ses.clearStorageData({ storages: ["cachestorage", "shadercache", "serviceworkers"] });
  }
});

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
  } catch (e) {
    console.error(e.message);
    dialog.showErrorBox(
      "NewsDesk 시작 실패",
      "백엔드 서버를 시작할 수 없습니다.\n다른 NewsDesk가 이미 실행 중이거나, 포트 8000이 사용 중일 수 있습니다."
    );
    killBackend();
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
