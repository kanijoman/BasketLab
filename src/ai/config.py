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
    DEFAULT_PROVIDER = 'gemini'

    # API keys (load from environment or config file)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Model configurations
    GEMINI_MODELS = {
        'flash': 'gemini-2.0-flash-exp',  # Gemini 2.0 Flash (experimental, high RPM)
        'pro': 'gemini-pro-latest'        # Use the stable -latest tag
    }

    OPENAI_MODELS = {
        'mini': 'gpt-4o-mini',
        'standard': 'gpt-4o'
    }

    # Analysis settings
    MAX_TOKENS = 8000  # Increased for complete HTML reports (was 2000)
    TEMPERATURE = 0.7

    @classmethod
    def load_api_keys(cls):
        """Load API keys from environment variables or config file."""
        # Try environment variables first
        cls.GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        cls.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

        # Try config file if env vars not set
        config_file = Path.home() / '.metricsforall' / 'config.txt'
        if config_file.exists():
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY='):
                        cls.GEMINI_API_KEY = line.split('=', 1)[1]
                    elif line.startswith('OPENAI_API_KEY='):
                        cls.OPENAI_API_KEY = line.split('=', 1)[1]

    @classmethod
    def save_api_key(cls, provider: str, api_key: str):
        """Save API key to config file."""
        config_dir = Path.home() / '.metricsforall'
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

    @classmethod
    def has_api_key(cls, provider: str) -> bool:
        """Check if API key is configured for provider."""
        cls.load_api_keys()

        if provider.lower() == 'gemini':
            return bool(cls.GEMINI_API_KEY)
        elif provider.lower() == 'openai':
            return bool(cls.OPENAI_API_KEY)

        return False


# Load keys on import
AnalysisConfig.load_api_keys()
