const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const repoRoot = path.resolve(root, "..");
const viteOrigin = "http://127.0.0.1:5173";
const apiOrigin = "http://127.0.0.1:5000";
const pythonInVenv = process.platform === "win32"
  ? path.join(repoRoot, "venv", "Scripts", "python.exe")
  : path.join(repoRoot, "venv", "bin", "python");
const python = process.env.PYTHON
  || (fs.existsSync(pythonInVenv) ? pythonInVenv : process.platform === "win32" ? "python" : "python3");

let backend = null;
const vite = spawn(process.execPath, [
  path.join(root, "node_modules", "vite", "bin", "vite.js"),
  "--host",
  "127.0.0.1",
  "--strictPort",
], { cwd: root, stdio: "inherit" });

let electron = null;
let shuttingDown = false;

function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of [backend, vite, electron]) {
    if (child && child.exitCode === null && child.signalCode === null) child.kill();
  }
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

function monitor(child, name) {
  child.on("error", (error) => {
    console.error(`Could not start ${name}:`, error);
    shutdown();
    process.exitCode = 1;
  });
  child.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`${name} exited unexpectedly with code ${code}`);
      shutdown();
      process.exitCode = code || 1;
    }
  });
}

monitor(vite, "Vite development server");

async function serviceIsReady(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForService(child, name, url) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (shuttingDown || child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`${name} exited before becoming ready`);
    }
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (response.ok) break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
  }
  if (Date.now() >= deadline && !shuttingDown) {
    throw new Error(`Timed out waiting for ${name}`);
  }
}

async function startElectron() {
  if (await serviceIsReady(`${apiOrigin}/api/state`)) {
    console.log("Using the already-running Flask backend");
  } else {
    backend = spawn(python, ["backend/server.py"], {
      cwd: repoRoot,
      stdio: "inherit",
    });
    monitor(backend, "Flask backend");
    await waitForService(backend, "Flask backend", `${apiOrigin}/api/state`);
  }

  await Promise.all([
    waitForService(vite, "Vite development server", viteOrigin),
  ]);
  if (shuttingDown) return;

  electron = spawn(require("electron"), ["."], {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, VITE_DEV_SERVER_URL: viteOrigin },
  });
  electron.on("error", (error) => {
    console.error("Could not start Electron:", error);
    shutdown();
    process.exitCode = 1;
  });
  electron.on("exit", (code) => {
    if (!shuttingDown) {
      shutdown();
      process.exitCode = code || 0;
    }
  });
}

startElectron().catch((error) => {
  if (!shuttingDown) console.error(error);
  shutdown();
  process.exitCode = 1;
});
