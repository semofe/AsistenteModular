import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, screen, session, Tray, type OpenDialogOptions } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

let backend: ChildProcess | undefined
let quitting = false
let clearingConversation = false
let assistantWindow: BrowserWindow | undefined
let tray: Tray | undefined

function showAssistant(): void {
  assistantWindow?.show()
  assistantWindow?.focus()
}

function hideAssistant(): void {
  assistantWindow?.hide()
}

function openSettings(): void {
  showAssistant()
  const window = assistantWindow
  if (!window) return
  if (window.webContents.isLoading()) {
    window.webContents.once('did-finish-load', () => window.webContents.send('asistente:open-settings'))
    return
  }
  window.webContents.send('asistente:open-settings')
}

function createTray(): void {
  const projectIcon = path.resolve(__dirname, '../../../assets/icons/asistente-tray.png')
  const packagedIcon = path.join(process.resourcesPath, 'assets', 'icons', 'asistente-tray.png')
  const iconPath = existsSync(projectIcon) ? projectIcon : packagedIcon
  let trayImage = nativeImage.createFromPath(iconPath)
  if (trayImage.isEmpty()) trayImage = nativeImage.createFromPath(process.execPath)
  tray = new Tray(trayImage.resize({ width: 16, height: 16 }))
  tray.setToolTip('Asistente Modular · Asistente activo')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Mostrar Asistente Modular', click: showAssistant },
    { label: 'Ocultar Asistente Modular', click: hideAssistant },
    { label: 'Configuración', click: openSettings },
    { type: 'separator' },
    { label: 'Salir de Asistente Modular', click: () => app.quit() }
  ]))
  tray.on('double-click', showAssistant)
}

function startBackend(): void {
  const projectRoot = path.resolve(__dirname, '../../../')
  const backendRoot = path.join(projectRoot, 'backend')
  const projectPython = path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
  const python = process.env.ASISTENTE_PYTHON ?? (existsSync(projectPython) ? projectPython : 'python')
  backend = spawn(python, ['-m', 'asistente.api.server'], {
    cwd: backendRoot,
    env: {
      ...process.env,
      PYTHONPATH: path.join(backendRoot, 'src')
    },
    windowsHide: true,
    stdio: 'inherit'
  })
  backend.on('error', (error) => {
    console.error(`No se pudo iniciar el backend con ${python}:`, error)
  })
  backend.on('exit', (code, signal) => {
    if (!quitting) {
      console.error(`El backend terminó inesperadamente (código ${code}, señal ${signal}).`)
    }
  })
}

async function clearConversationHistory(): Promise<void> {
  try {
    await fetch('http://127.0.0.1:8765/api/conversation/history', {
      method: 'DELETE',
      signal: AbortSignal.timeout(3000)
    })
  } catch {
    // The backend may already be stopping; quitting must still remain immediate.
  }
}

function createWindow(): void {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  const window = new BrowserWindow({
    width: Math.min(400, width),
    height: Math.min(760, height),
    minWidth: Math.min(360, width),
    minHeight: Math.min(520, height),
    title: 'Asistente',
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false
    }
  })
  assistantWindow = window
  window.on('closed', () => { assistantWindow = undefined })

  if (process.env.ELECTRON_RENDERER_URL) {
    void window.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void window.loadFile(path.join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  ipcMain.handle('asistente:show-assistant', () => {
    showAssistant()
    return true
  })
  ipcMain.handle('asistente:hide-assistant', () => {
    hideAssistant()
    return true
  })
  ipcMain.handle('asistente:quit-assistant', () => {
    setImmediate(() => app.quit())
    return true
  })
  ipcMain.handle('asistente:shutdown-pc', () => {
    const shutdown = path.join(process.env.WINDIR ?? 'C:\\Windows', 'System32', 'shutdown.exe')
    const shutdownProcess = spawn(shutdown, ['/s', '/t', '0'], {
      windowsHide: true,
      detached: true,
      stdio: 'ignore'
    })
    shutdownProcess.unref()
    return true
  })
  ipcMain.handle('asistente:choose-access-target', async (event, kind: string) => {
    if (!['application', 'file', 'folder', 'browser'].includes(kind)) return null
    const owner = BrowserWindow.fromWebContents(event.sender)
    const userStartMenu = path.join(
      app.getPath('appData'),
      'Microsoft',
      'Windows',
      'Start Menu',
      'Programs'
    )
    const sharedStartMenu = path.join(
      process.env.ProgramData ?? 'C:\\ProgramData',
      'Microsoft',
      'Windows',
      'Start Menu',
      'Programs'
    )
    const applicationStart = existsSync(userStartMenu) ? userStartMenu : sharedStartMenu
    const defaultPath = ['application', 'browser'].includes(kind) && existsSync(applicationStart)
      ? applicationStart
      : app.getPath('documents')
    const options: OpenDialogOptions = {
      title: kind === 'browser' ? 'Seleccionar navegador' : kind === 'application' ? 'Seleccionar aplicación' : kind === 'folder' ? 'Seleccionar carpeta' : 'Seleccionar archivo',
      buttonLabel: 'Seleccionar',
      defaultPath,
      properties: kind === 'folder' ? ['openDirectory'] : ['openFile'],
      filters: kind === 'browser'
        ? [{ name: 'Navegadores', extensions: ['exe'] }]
        : kind === 'application'
        ? [{ name: 'Aplicaciones y accesos directos', extensions: ['exe', 'lnk'] }]
        : undefined
    }
    const result = owner
      ? await dialog.showOpenDialog(owner, options)
      : await dialog.showOpenDialog(options)
    return result.canceled ? null : result.filePaths[0] ?? null
  })
  session.defaultSession.setPermissionRequestHandler((_contents, permission, callback) => {
    callback(permission === 'media')
  })
  startBackend()
  createWindow()
  createTray()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', (event) => {
  if (!clearingConversation) {
    event.preventDefault()
    clearingConversation = true
    void clearConversationHistory().finally(() => app.quit())
    return
  }
  quitting = true
  backend?.kill()
})
