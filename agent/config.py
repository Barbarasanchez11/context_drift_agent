from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    datahub_gms_url: str = "http://localhost:8080"
    datahub_token: str | None = None

    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    llm_model: str = "claude-sonnet-4-6"

    poll_interval_seconds: int = 30
    dataset_urns: str = ""

    use_mcp_context: bool = True
    use_adversarial_judge: bool = False

    def get_urns(self) -> list[str]:
        # URNs are pipe-separated because URNs themselves contain commas
        return [u.strip() for u in self.dataset_urns.split("|") if u.strip()]

    def get_api_key(self) -> str:
        key_map = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "groq": self.groq_api_key,
        }
        key = key_map.get(self.llm_provider)
        if not key:
            raise ValueError(
                f"No API key configured for provider '{self.llm_provider}'. "
                f"Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY in your .env file."
            )
        return key
