/// <reference types="vite/client" />

interface Window {
  asistenteDesktop?: {
    platform: string
    version: string
    chooseAccessTarget: (kind: 'application' | 'file' | 'folder' | 'browser') => Promise<string | null>
    quitAssistant: () => Promise<boolean>
    shutdownPc: () => Promise<boolean>
    showAssistant: () => Promise<boolean>
    hideAssistant: () => Promise<boolean>
    onOpenSettings: (callback: () => void) => () => void
  }
}
