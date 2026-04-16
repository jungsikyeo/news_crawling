const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  showNotification: (title, body) => ipcRenderer.send("show-notification", title, body),
  clearCache: () => ipcRenderer.invoke("clear-cache"),
});
