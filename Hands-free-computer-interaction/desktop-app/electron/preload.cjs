const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("motionEase", {
  request: (path, method = "GET", body) =>
    ipcRenderer.invoke("motion:request", { path, method, body }),
});
