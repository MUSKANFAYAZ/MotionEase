const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");

const API_ORIGIN = "http://127.0.0.1:5000";
const allowedPaths = new Set([
  "/",
  "/status",
  "/api/state",
  "/api/voice/status",
  "/api/suggestions",
  "/api/autocomplete/learn",
  "/api/voice/start",
  "/api/voice/stop",
  "/api/interaction/events",
  "/start-eye-tracking",
  "/stop-eye-tracking",
  "/start-voice-control",
  "/stop-voice-control",
]);

ipcMain.handle("motion:request", async (_event, options) => {
  if (!options || !allowedPaths.has(options.path)) {
    throw new Error("Requested backend operation is not allowed");
  }
  const method = options.method || "GET";
  if (!["GET", "POST"].includes(method)) {
    throw new Error("Unsupported backend method");
  }

  const response = await fetch(`${API_ORIGIN}${options.path}`, {
    method,
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: AbortSignal.timeout(5000),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || data.message || `Backend returned ${response.status}`);
  }
  return data;
});

function createWindow() {
  const window = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 760,
    minHeight: 600,
    backgroundColor: "#111827",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  window.webContents.on("console-message", (_event, details) => {
    if (details.level === 3) {
      console.error(
        `Renderer error: ${details.message} (${details.sourceId}:${details.line})`,
      );
    }
  });
  window.webContents.on("did-fail-load", (
    _event,
    errorCode,
    errorDescription,
    validatedURL,
    isMainFrame,
  ) => {
    if (isMainFrame && errorCode !== -3) {
      console.error(
        `Could not load MotionEase UI: ${errorDescription} (${errorCode}) at ${validatedURL}`,
      );
    }
  });
  window.webContents.on("render-process-gone", (_event, details) => {
    console.error(`MotionEase renderer stopped: ${details.reason}`);
  });

  const devServer = process.env.VITE_DEV_SERVER_URL;
  if (devServer) {
    window.loadURL(devServer).catch((error) => {
      console.error(`Could not open MotionEase dev server at ${devServer}:`, error);
    });
  } else {
    window.loadFile(path.join(__dirname, "..", "dist", "index.html")).catch((error) => {
      console.error("Could not open the built MotionEase UI:", error);
    });
  }

  if (process.env.MOTIONEASE_DEVTOOLS === "1") {
    window.webContents.openDevTools({ mode: "detach" });
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
