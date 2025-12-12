"""
Team Analyzer - AI-powered basketball team analysis.
Supports multiple providers: Google Gemini, OpenAI.
"""

import json
import base64
from io import BytesIO
from typing import Dict, List, Optional, Any
import requests

from .config import AnalysisConfig
from .prompts import get_system_prompt
from .context_builder import ContextBuilder


class TeamAnalyzer:
    """AI-powered team performance analyzer."""

    def __init__(self, provider: str = 'gemini', model: str = 'flash'):
        """
        Initialize team analyzer.

        Args:
            provider: 'gemini' or 'openai'
            model: Model variant ('flash'/'pro' for Gemini, 'mini'/'standard' for OpenAI)
        """
        self.provider = provider.lower()
        self.model = model
        self.context_builder = ContextBuilder()

        # Load API keys
        AnalysisConfig.load_api_keys()

        # Validate API key exists
        if not AnalysisConfig.has_api_key(self.provider):
            raise ValueError(f"No API key configured for {self.provider}. Please configure it first.")

        # Initialize client
        if self.provider == 'gemini':
            self._init_gemini()
        elif self.provider == 'openai':
            self._init_openai()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _init_gemini(self):
        """Initialize Google Gemini client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=AnalysisConfig.GEMINI_API_KEY)

            # Get model name from config
            model_name = AnalysisConfig.GEMINI_MODELS.get(self.model, AnalysisConfig.GEMINI_MODELS['flash'])

            # The debug script confirms that the model name needs the 'models/' prefix
            # The SDK should handle this, but we will be explicit to ensure it works.
            if not model_name.startswith('models/'):
                model_name = f"models/{model_name}"

            self.client = genai.GenerativeModel(model_name)

        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
        except Exception as e:
            raise e

    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            import openai
            self.client = openai.OpenAI(api_key=AnalysisConfig.OPENAI_API_KEY)
            self.model_name = AnalysisConfig.OPENAI_MODELS.get(self.model, AnalysisConfig.OPENAI_MODELS['mini'])
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

    def analyze_team_performance(self,
                                 team_name: str,
                                 stats: Dict[str, Any],
                                 shot_chart_image: Optional[bytes] = None,
                                 include_recommendations: bool = True,
                                 analysis_type: str = 'own') -> str:
        """
        Generate comprehensive team analysis report.

        Args:
            team_name: Name of the team
            stats: Dictionary containing team statistics
            shot_chart_image: Optional PNG/JPEG image of shot chart
            include_recommendations: Include tactical recommendations
            analysis_type: 'own' for own team analysis, 'opponent' for rival scouting

        Returns:
            Formatted analysis report as markdown text
        """
        # Build context from stats using ContextBuilder
        context = self.context_builder.build_team_context(
            team_name, stats, include_recommendations, analysis_type
        )

        # Generate analysis based on provider
        if self.provider == 'gemini':
            return self._analyze_with_gemini(context, shot_chart_image, analysis_type)
        elif self.provider == 'openai':
            return self._analyze_with_openai(context, shot_chart_image, analysis_type)

    def _analyze_with_gemini(self, context: str, image: Optional[bytes] = None, analysis_type: str = 'own') -> str:
        """Generate analysis using Google Gemini."""
        try:
            # Get appropriate system prompt
            system_prompt = get_system_prompt('gemini', analysis_type)

            # Prepare content
            if image:
                # Convert image to PIL Image for Gemini
                from PIL import Image
                import io

                pil_image = Image.open(io.BytesIO(image))

                prompt = [
                    system_prompt,
                    "\n\n",
                    context,
                    "\n\nThe shot chart visualization is attached. Use it to provide visual insights.",
                    pil_image
                ]
            else:
                prompt = f"{system_prompt}\n\n{context}"

            # Generate response
            response = self.client.generate_content(
                prompt,
                generation_config={
                    'temperature': AnalysisConfig.TEMPERATURE,
                    'max_output_tokens': AnalysisConfig.MAX_TOKENS,
                }
            )

            response_text = response.text
            return response_text

        except Exception as e:
            error_msg = str(e).lower()
            if 'quota' in error_msg or 'resource_exhausted' in error_msg:
                return "⚠️ **Cuota de API agotada**\n\nHa alcanzado el límite de su API key de Gemini. Por favor:\n- Espere unos minutos e intente nuevamente\n- O configure una nueva API key en Settings"
            elif 'rate' in error_msg or 'limit' in error_msg:
                return "⚠️ **Límite de velocidad alcanzado**\n\nHa realizado demasiadas solicitudes. Espere 1-2 minutos e intente nuevamente."
            else:
                return f"Error generating analysis: {str(e)}\n\nPlease check your API key and internet connection."

    def _analyze_with_openai(self, context: str, image: Optional[bytes] = None, analysis_type: str = 'own') -> str:
        """Generate analysis using OpenAI."""
        try:
            # Get appropriate system prompt
            system_content = get_system_prompt('openai', analysis_type)

            messages = [
                {
                    "role": "system",
                    "content": system_content
                }
            ]

            if image:
                # Encode image to base64
                img_b64 = base64.b64encode(image).decode('utf-8')

                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": context},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                })
            else:
                messages.append({
                    "role": "user",
                    "content": context
                })

            # Generate response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=AnalysisConfig.TEMPERATURE,
                max_tokens=AnalysisConfig.MAX_TOKENS
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error generating analysis: {str(e)}\n\nPlease check your API key and internet connection."

    def quick_analysis(self, team_name: str, stats: Dict) -> str:
        """
        Generate a quick text-only analysis (no images).
        Faster and uses fewer tokens.
        """
        return self.analyze_team_performance(
            team_name=team_name,
            stats=stats,
            shot_chart_image=None,
            include_recommendations=False
        )

    def analyze_player_for_scouting(self, player_name: str, player_stats: Dict[str, Any],
                                   league_stats: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate succinct scouting notes for an individual player (6-8 lines max).

        Args:
            player_name: Name of the player
            player_stats: Dictionary containing player statistics
            league_stats: Optional dictionary with league-wide statistics for comparison

        Returns:
            Formatted scouting notes as plain text with bullets
        """
        # Build compact context for player using ContextBuilder
        context = self.context_builder.build_player_context(player_name, player_stats, league_stats)

        # Generate analysis based on provider
        if self.provider == 'gemini':
            return self._analyze_player_with_gemini(context)
        elif self.provider == 'openai':
            return self._analyze_player_with_openai(context)

    def _analyze_player_with_gemini(self, context: str) -> str:
        """Generate player scouting notes using Gemini."""
        from .prompts import PROMPT_PLAYER_SCOUTING

        try:
            # Prepare prompt - same approach as team analysis
            prompt = f"{PROMPT_PLAYER_SCOUTING}\n\n{context}"

            # Generate response using SDK - same as _analyze_with_gemini
            response = self.client.generate_content(
                prompt,
                generation_config={
                    'temperature': AnalysisConfig.TEMPERATURE,
                    'max_output_tokens': AnalysisConfig.MAX_TOKENS,
                }
            )

            return response.text.strip()

        except Exception as e:
            error_msg = str(e).lower()
            if 'quota' in error_msg or 'resource_exhausted' in error_msg:
                return "⚠️ Cuota de API agotada. Intente de nuevo en unos minutos o use otra API key."
            elif 'rate' in error_msg or 'limit' in error_msg:
                return "⚠️ Límite de velocidad alcanzado. Espere unos segundos e intente nuevamente."
            else:
                return f"Error generando análisis: {str(e)}"

    def _analyze_player_with_openai(self, context: str) -> str:
        """Generate player scouting notes using OpenAI."""
        from .prompts import PROMPT_PLAYER_SCOUTING

        try:
            messages = [
                {
                    "role": "system",
                    "content": PROMPT_PLAYER_SCOUTING
                },
                {
                    "role": "user",
                    "content": context
                }
            ]

            # Generate response with lower max tokens for brevity
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=500  # Limit output length
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Error generando análisis: {str(e)}"

