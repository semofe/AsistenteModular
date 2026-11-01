# Subir Asistente Modular a GitHub

Estos pasos publican el código de `Asistente_Final/AsistenteModularData`, no las dependencias instaladas. La estructura de carpetas debe quedar en la raíz del repositorio de GitHub.

## 1. Crear un repositorio vacío

Inicia sesión en [GitHub](https://github.com/new) y crea un repositorio, por ejemplo `Asistente_Final`.

- Elige la visibilidad que quieras: privado o público.
- Déjalo vacío: no añadas README, `.gitignore` ni licencia desde el formulario. El proyecto ya tiene sus archivos locales.
- Copia la URL HTTPS que GitHub muestra, por ejemplo `https://github.com/TU_USUARIO/Asistente_Final.git`.

No incluyas contraseñas o tokens en la URL.

## 2. Abrir la carpeta correcta

En PowerShell:

```powershell
Set-Location "C:\Users\Sergio\Desktop\Asistente_Final\AsistenteModularData"
git --version
Get-ChildItem
```

Debes ver `README.md`, `.gitignore`, `backend`, `desktop`, `scripts` y `docs`.

## 3. Iniciar Git

Para este primer repositorio:

```powershell
git init -b main
git config user.name "TU NOMBRE"
git config user.email "TU_CORREO_O_CORREO_NOREPLY_DE_GITHUB"
```

La identidad se configura solo para este proyecto. Puedes obtener un correo `noreply` desde [Settings → Emails](https://github.com/settings/emails) si no quieres publicar tu correo personal en los commits.

Si la carpeta ya tuviera un repositorio, revisa primero `git status` y `git remote -v`; no necesitas volver a inicializarlo.

## 4. Revisar qué se va a subir

```powershell
git status --short
git add --dry-run .
```

El `.gitignore` excluye:

- `node_modules`, `.venv`, `.venv-voice` y metadatos Python generados.
- Compilados `out`, `dist`, `build` y `desktop/public/models`.
- `.env`, bases SQLite, registros, cachés y temporales.
- La carpeta `voice`, pesos de modelos y avatares GLB/VRM.
- Pesos y audios externos de `assets/voices` y modelos de `assets/avatars`; conserva sus README.

Se incluyen código, pruebas, guías, `config/defaults`, `desktop/package.json`, **`desktop/package-lock.json`**, `backend/pyproject.toml` y `backend/requirements-voice-worker.txt`.

No necesitas subir el `electron.exe` de 200 MB ni las DLL de los entornos. En otro equipo se recuperan mediante el instalador. Los modelos excluidos se descargan siguiendo `docs/INSTALACION.md`.

Si un recurso ya estuviera versionado, añadirlo a `.gitignore` no lo elimina del índice. Revisa `git ls-files` y retira únicamente la ruta concreta del seguimiento con `git rm --cached`, usando `-r` solo si es una carpeta. Esto no borra la copia del disco, pero revisa la ruta antes de ejecutarlo.

## 5. Crear el primer commit

```powershell
git add .
git diff --cached --stat
git diff --cached
git commit -m "Version inicial de Asistente Modular"
```

Revisa los archivos antes de confirmar; el diff debe contener código y documentación, no claves ni datos personales.

## 6. Conectar y subir

Reemplaza `TU_USUARIO` por tu cuenta:

```powershell
git remote add origin https://github.com/TU_USUARIO/Asistente_Final.git
git push -u origin main
```

Git para Windows con Git Credential Manager puede abrir el navegador para iniciar sesión. Si un cliente te pide autenticación distinta, consulta [las opciones oficiales de autenticación](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github); no uses la contraseña de tu cuenta como contraseña Git HTTPS.

Si `origin` ya existe, consulta `git remote -v`. Cambia la URL con `git remote set-url origin ...` solo si apunta al repositorio equivocado. Si GitHub rechaza el push porque el repositorio remoto ya tiene commits, conserva ambos historiales y resuelve la integración; no fuerces el push para seguir esta guía.

## 7. Verificar y descargar en otro equipo

Abre el repositorio en GitHub: el README y las carpetas del código deben verse en la raíz. Luego puedes instalarlo desde cero:

```powershell
git clone https://github.com/TU_USUARIO/Asistente_Final.git AsistenteModularData
Set-Location AsistenteModularData
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Completa programas externos y modelos con [INSTALACION.md](INSTALACION.md).

## 8. Subir cambios posteriores

```powershell
git status
git add .
git diff --cached --stat
git commit -m "Describe el cambio realizado"
git push
```

Esta guía sigue el flujo de [GitHub para código alojado localmente](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

## Recursos y licencias

El proyecto no incluye todavía una licencia de distribución del código. Antes de ofrecerlo para reutilización, elige la licencia que quieras otorgar y añádela como `LICENSE`. Los modelos, avatares y voces conservan sus condiciones propias: no se publican automáticamente junto al código.
