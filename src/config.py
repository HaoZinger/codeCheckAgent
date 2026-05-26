# Configuration management for CodeCheckAgent
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


# ----- Provider Presets -----

@dataclass
class ProviderPreset:
    """Pre-configured provider settings."""
    name: str
    api_base: str
    api_key_env: str
    default_model: str
    description: str
    supports_json_mode: bool = True


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        name="openai",
        api_base="",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o",
        description="OpenAI (GPT-4o, GPT-4-turbo, etc.)",
        supports_json_mode=True,
    ),
    "deepseek-v4": ProviderPreset(
        name="deepseek-v4",
        api_base="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-v4-pro",
        description="DeepSeek V4 Pro",
        supports_json_mode=True,
    ),
    "custom": ProviderPreset(
        name="custom",
        api_base="",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o",
        description="Custom OpenAI-compatible endpoint",
        supports_json_mode=False,
    ),
}


# ----- Config Data Classes -----

@dataclass
class AgentConfig:
    """Configuration for a single agent type."""
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 16384
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    timeout_seconds: int = 120
    use_json_mode: bool = True


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    max_rounds: int = 3
    max_file_chars: int = 4000
    output_dir: str = "./codecheck_output"


@dataclass
class Config:
    """Top-level configuration."""
    provider: str = "openai"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    reviewer: AgentConfig = field(default_factory=AgentConfig)
    fixer: AgentConfig = field(default_factory=AgentConfig)
    validator: AgentConfig = field(default_factory=AgentConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    supported_extensions: list[str] = field(default_factory=lambda: [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
        ".kt", ".scala", ".sql", ".sh", ".bash", ".ps1", ".yaml", ".yml",
        ".json", ".xml", ".html", ".css", ".scss", ".md", ".txt"
    ])

    def apply_provider_preset(self):
        """Apply provider preset for api_base, api_key, default model, and json_mode."""
        if self.provider not in PROVIDER_PRESETS:
            print(f"[Config] Warning: Unknown provider '{self.provider}', using 'custom'")
            self.provider = "custom"

        preset = PROVIDER_PRESETS[self.provider]

        # Set api_base from preset if not explicitly set
        if not self.api_base and preset.api_base:
            self.api_base = preset.api_base

        # Try to get API key from provider-specific env var if not already set
        if not self.api_key and preset.api_key_env:
            self.api_key = os.environ.get(preset.api_key_env)

        # Also try generic OPENAI_API_KEY as fallback
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY")

        # Apply default model from preset (only if not explicitly overridden)
        if preset.default_model:
            for agent_cfg in [self.reviewer, self.fixer, self.validator]:
                if not agent_cfg.model or agent_cfg.model == "gpt-4o":
                    agent_cfg.model = preset.default_model

        # Apply json_mode from preset
        if not preset.supports_json_mode:
            for agent_cfg in [self.reviewer, self.fixer, self.validator]:
                agent_cfg.use_json_mode = False

        return self

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        # Provider
        if "provider" in data:
            config.provider = data["provider"]

        # API settings
        if "api_key" in data:
            config.api_key = data["api_key"]
        if "api_base" in data:
            config.api_base = data["api_base"]

        # Agent configs
        for agent_name in ["reviewer", "fixer", "validator"]:
            if agent_name in data:
                agent_data = data[agent_name]
                agent_config = getattr(config, agent_name)
                for key in ["model", "temperature", "max_tokens", "max_retries",
                           "retry_delay_seconds", "timeout_seconds", "use_json_mode"]:
                    if key in agent_data:
                        setattr(agent_config, key, agent_data[key])

        # Orchestrator config
        if "orchestrator" in data:
            orch_data = data["orchestrator"]
            for key in ["max_rounds", "max_file_chars", "output_dir"]:
                if key in orch_data:
                    setattr(config.orchestrator, key, orch_data[key])

        # Supported extensions
        if "supported_extensions" in data:
            config.supported_extensions = data["supported_extensions"]

        # Apply provider preset (respects explicitly set values)
        config.apply_provider_preset()

        return config

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables only."""
        config = cls()
        config.apply_provider_preset()
        return config

    def summary(self) -> str:
        """Return a human-readable config summary."""
        preset = PROVIDER_PRESETS.get(self.provider)
        json_mode_str = "ON" if self.reviewer.use_json_mode else "OFF"
        lines = [
            f"  Provider:   {self.provider} ({preset.description if preset else 'unknown'})",
            f"  API Base:   {self.api_base or '(default)'}",
            f"  Model:      {self.reviewer.model}",
            f"  JSON Mode:  {json_mode_str}",
            f"  Max Rounds: {self.orchestrator.max_rounds}",
            f"  Output Dir: {self.orchestrator.output_dir}",
        ]
        return "\n".join(lines)