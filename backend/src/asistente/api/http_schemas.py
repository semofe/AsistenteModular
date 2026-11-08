"""HTTP request validation models."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    fragments: list[str] | None = Field(default=None, max_length=12)
    use_rvc: bool = False
    engine: str = Field(default="edge", pattern="^(edge|kokoro|elevenlabs|fish|custom)$")
    voice: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    endpoint: str | None = Field(default=None, max_length=500)


class CredentialRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)


class VoicePreferencesRequest(BaseModel):
    engine: str = Field(pattern="^(edge|kokoro|elevenlabs|fish|custom)$")
    edge_voice: str = Field(max_length=100)
    elevenlabs_voice_id: str = Field(max_length=100)
    fish_reference_id: str = Field(max_length=100)
    custom_endpoint: str = Field(max_length=500)
    custom_voice: str = Field(max_length=100)
    custom_model: str = Field(max_length=100)
    rvc_enabled: bool
    voice_output: bool


class LLMConfigRequest(BaseModel):
    provider: Literal["gemini", "ollama"]
    gemini_model: str = Field(min_length=1, max_length=150)
    ollama_model: str = Field(min_length=1, max_length=150)


class ConversationPreferencesRequest(BaseModel):
    web_search_enabled: bool


class FileAccessPreferencesRequest(BaseModel):
    folders: list[str] = Field(default_factory=list, max_length=30)
    extensions: list[str] = Field(default_factory=list, max_length=30)


class AssistantProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class AccessEntryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["application", "file", "folder"]
    target: str = Field(min_length=1, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    spoken_name: str | None = Field(default=None, max_length=120)
    close_policy: Literal["process", "window"] = "process"


class SpokenNameRequest(BaseModel):
    spoken_name: str = Field(min_length=1, max_length=120)


class BrowserConfigRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    activation_word: str = Field(min_length=1, max_length=80)
    executable: str = Field(min_length=1, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class WebsiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class ActivationSettingsRequest(BaseModel):
    enabled: bool
    inactivity_seconds: int = Field(ge=30, le=1800)
    show_on_wake: bool = True
    hide_on_timeout: bool = True


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    category: str = Field(default="general", max_length=60)


class ReminderRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: str = Field(min_length=16, max_length=50)
    action_type: Literal["notify", "open_access"] = "notify"
    access_id: str | None = None


class RoutineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    time_of_day: str = Field(min_length=5, max_length=5)
    days: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    access_ids: list[str] = Field(min_length=1, max_length=20)

READABLE_FILE_EXTENSIONS = {"txt", "md", "csv", "json", "docx"}
