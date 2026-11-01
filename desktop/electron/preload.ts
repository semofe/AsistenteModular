import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('asistenteDesktop', {
  platform: process.platform,
  version: process.versions.electron,
  chooseAccessTarget: (kind: 'application' | 'file' | 'folder' | 'browser') =>
    ipcRenderer.invoke('asistente:choose-access-target', kind) as Promise<string | null>,
  quitAssistant: () => ipcRenderer.invoke('asistente:quit-assistant') as Promise<boolean>,
  shutdownPc: () => ipcRenderer.invoke('asistente:shutdown-pc') as Promise<boolean>,
  showAssistant: () => ipcRenderer.invoke('asistente:show-assistant') as Promise<boolean>,
  hideAssistant: () => ipcRenderer.invoke('asistente:hide-assistant') as Promise<boolean>,
  onOpenSettings: (callback: () => void) => {
    const listener = () => callback()
    ipcRenderer.on('asistente:open-settings', listener)
    return () => ipcRenderer.removeListener('asistente:open-settings', listener)
  }
})
