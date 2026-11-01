"""Almacén seguro de credenciales de Asistente Modular."""

from __future__ import annotations

import os


class CredentialStore:
    SERVICE = "asistente-assistant"
    ENV_NAMES = {
        "gemini": "GEMINI_API_KEY",
        "elevenlabs": "ELEVENLABS_API_KEY",
        "fish": "FISH_AUDIO_API_KEY",
        "custom": "ASISTENTE_CUSTOM_TTS_API_KEY",
    }

    def get(self, provider: str) -> str | None:
        env_name = self.ENV_NAMES.get(provider)
        if env_name and (value := os.environ.get(env_name)):
            return value
        try:
            import keyring

            value = keyring.get_password(self.SERVICE, provider)
            if value is None and provider == "gemini":
                value = keyring.get_password("asistente", "gemini")
            return value
        except Exception:
            return None

    def set(self, provider: str, value: str) -> None:
        if provider not in self.ENV_NAMES:
            raise ValueError("Proveedor de credenciales desconocido.")
        if len(value.strip()) < 8:
            raise ValueError("La clave parece incompleta.")
        import keyring

        keyring.set_password(self.SERVICE, provider, value.strip())

    def delete(self, provider: str) -> None:
        if provider not in self.ENV_NAMES:
            raise ValueError("Proveedor de credenciales desconocido.")
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("Falta instalar keyring para guardar credenciales.") from exc
        locations = [(self.SERVICE, provider)]
        if provider == "gemini":
            locations.append(("asistente", "gemini"))
        for service, username in locations:
            try:
                keyring.delete_password(service, username)
            except keyring.errors.PasswordDeleteError:
                pass

    def status(self) -> dict[str, bool]:
        return {provider: self.get(provider) is not None for provider in self.ENV_NAMES}
