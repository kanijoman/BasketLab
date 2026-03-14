"""
Configuration for AI analysis.
Manages API keys and provider settings.
"""

import os
from pathlib import Path
from typing import Optional


class AnalysisConfig:
    """Configuration for AI analysis providers."""

    # Default provider
    DEFAULT_PROVIDER = 'groq'

    # API keys (load from environment or config file)
    GEMINI_API_KEY: Optional[str] = 'AIzaSyBfPMeN3hUN4XOct4D5VpClgnCa-JW45X8'
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = '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'

    # Model configurations
    GEMINI_MODELS = {
        'flash': 'gemini-2.0-flash-exp',  # Gemini 2.0 Flash (experimental, high RPM)
        'pro': 'gemini-pro-latest'        # Use the stable -latest tag
    }

    OPENAI_MODELS = {
        'mini': 'gpt-4o-mini',
        'standard': 'gpt-4o'
    }

    GROQ_MODELS = {
        'fast': 'llama-3.3-70b-versatile',  # Llama 3.3 70B (rápido y potente)
        'specdec': 'llama-3.3-70b-specdec'  # Con speculative decoding (más rápido)
    }

    # Analysis settings
    MAX_TOKENS = 8000  # Increased for complete HTML reports (was 2000)
    TEMPERATURE = 0.7

    @classmethod
    def _migrate_config_if_needed(cls):
        """One-time migration: copy ~/.metricsforall → ~/.basketlab on first run."""
        import shutil
        import logging
        old_dir = Path.home() / '.metricsforall'
        new_dir = Path.home() / '.basketlab'
        if old_dir.exists() and not new_dir.exists():
            try:
                shutil.copytree(str(old_dir), str(new_dir))
                logging.getLogger(__name__).warning(
                    "BasketLab: migrated config from %s to %s", old_dir, new_dir
                )
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).error(
                    "BasketLab: config migration failed: %s", exc
                )

    @classmethod
    def load_api_keys(cls):
        """Load API keys from environment variables or config file."""
        cls._migrate_config_if_needed()

        # Try environment variables first
        cls.GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        cls.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        cls.GROQ_API_KEY = os.getenv('GROQ_API_KEY')

        # Try config file if env vars not set
        config_file = Path.home() / '.basketlab' / 'config.txt'
        if config_file.exists():
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY='):
                        cls.GEMINI_API_KEY = line.split('=', 1)[1]
                    elif line.startswith('OPENAI_API_KEY='):
                        cls.OPENAI_API_KEY = line.split('=', 1)[1]
                    elif line.startswith('GROQ_API_KEY='):
                        cls.GROQ_API_KEY = line.split('=', 1)[1]

    @classmethod
    def save_api_key(cls, provider: str, api_key: str):
        """Save API key to config file."""
        config_dir = Path.home() / '.basketlab'
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / 'config.txt'

        # Read existing config
        lines = []
        if config_file.exists():
            with open(config_file, 'r') as f:
                lines = [line for line in f if not line.strip().startswith(f'{provider.upper()}_API_KEY=')]

        # Add new key
        lines.append(f'{provider.upper()}_API_KEY={api_key}\n')

        # Write back
        with open(config_file, 'w') as f:
            f.writelines(lines)

        # Update in memory
        if provider.lower() == 'gemini':
            cls.GEMINI_API_KEY = api_key
        elif provider.lower() == 'openai':
            cls.OPENAI_API_KEY = api_key
        elif provider.lower() == 'groq':
            cls.GROQ_API_KEY = api_key

    @classmethod
    def has_api_key(cls, provider: str) -> bool:
        """Check if API key is configured for provider."""
        cls.load_api_keys()

        if provider.lower() == 'gemini':
            return bool(cls.GEMINI_API_KEY)
        elif provider.lower() == 'openai':
            return bool(cls.OPENAI_API_KEY)
        elif provider.lower() == 'groq':
            return bool(cls.GROQ_API_KEY)

        return False


# Load keys on import
AnalysisConfig.load_api_keys()
