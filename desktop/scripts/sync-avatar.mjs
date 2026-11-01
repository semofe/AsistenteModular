import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const legacySource = fileURLToPath(new URL('../../assets/avatars/asistente.glb', import.meta.url))
const source = existsSync(legacySource) ? legacySource : fileURLToPath(new URL('../../assets/avatars/assistant.glb', import.meta.url))
const destination = fileURLToPath(new URL('../public/models/assistant.glb', import.meta.url))

if (existsSync(source)) {
  mkdirSync(dirname(destination), { recursive: true })
  copyFileSync(source, destination)
  console.log('Avatar sincronizado.')
} else {
  // Retira la copia generada para que no aparezca un avatar antiguo.
  rmSync(destination, { force: true })
  console.log('Sin modelo 3D: se mostrará el círculo animado.')
}
