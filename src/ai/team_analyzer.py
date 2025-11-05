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

    def _format_stat_with_quartile(self,
                                   stat_name: str,
                                   value: float,
                                   quartiles: Dict[str, float],
                                   higher_is_better: Optional[bool] = True,
                                   is_percentage: bool = False,
                                   format_str: str = ".1f") -> str:
        """
        Format a statistic with quartile comparison and strength/weakness indicator.

        Args:
            stat_name: Name of the statistic
            value: Team's value for this stat
            quartiles: Dictionary with 'q1', 'q2' (median), 'q3', 'min', 'max' keys
            higher_is_better: True if higher values are better, False if lower is better, None if neutral
            is_percentage: Whether to display with % symbol
            format_str: Format string for the value (e.g., ".1f" for 1 decimal)

        Returns:
            Formatted string with value, quartile, and assessment
        """
        # Handle None or missing values
        if value is None:
            return f"- **{stat_name}**: N/A"

        # Convert to float to ensure it's numeric
        try:
            value = float(value)
        except (ValueError, TypeError):
            return f"- **{stat_name}**: N/A"

        # Format the value
        if is_percentage:
            value_str = f"{value:{format_str}}%"
        else:
            value_str = f"{value:{format_str}}"

        # If no quartile data, return just the value
        if not quartiles or not any(k in quartiles for k in ['q1', 'q2', 'q3']):
            return f"- **{stat_name}**: {value_str}"

        # Determine quartile position
        q1 = quartiles.get('q1', 0)
        q2 = quartiles.get('q2', 0)  # median
        q3 = quartiles.get('q3', 0)

        # Handle None values in quartiles
        if q1 is None or q2 is None or q3 is None:
            return f"- **{stat_name}**: {value_str}"

        # Classify into quartile
        if value <= q1:
            quartile_pos = "Q1 (cuartil inferior)"
            strength_level = 1
        elif value <= q2:
            quartile_pos = "Q2 (por debajo de la mediana)"
            strength_level = 2
        elif value <= q3:
            quartile_pos = "Q3 (por encima de la mediana)"
            strength_level = 3
        else:
            quartile_pos = "Q4 (cuartil superior)"
            strength_level = 4

        # Determine if this is a strength or weakness
        if higher_is_better is None:
            assessment = ""  # Neutral stat
        elif higher_is_better:
            if strength_level >= 3:
                assessment = " ✓ FORTALEZA"
            elif strength_level == 1:
                assessment = " ✗ DEBILIDAD"
            else:
                assessment = ""
        else:  # Lower is better
            if strength_level <= 2:
                assessment = " ✓ FORTALEZA"
            elif strength_level == 4:
                assessment = " ✗ DEBILIDAD"
            else:
                assessment = ""

        # Build the output
        try:
            median_str = f"{q2:{format_str}}%" if is_percentage else f"{q2:{format_str}}"
        except (ValueError, TypeError):
            median_str = "N/A"

        return f"- **{stat_name}**: {value_str} [{quartile_pos}, mediana liga: {median_str}]{assessment}"

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

            print(f"[Gemini] Initializing with model: {model_name}")
            self.client = genai.GenerativeModel(model_name)
            print("[Gemini] Successfully initialized.")

        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
        except Exception as e:
            print(f"[Gemini] CRITICAL ERROR during initialization: {e}")
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
        # Build context from stats
        context = self._build_analysis_context(team_name, stats, include_recommendations, analysis_type)

        # Generate analysis based on provider
        if self.provider == 'gemini':
            return self._analyze_with_gemini(context, shot_chart_image, analysis_type)
        elif self.provider == 'openai':
            return self._analyze_with_openai(context, shot_chart_image, analysis_type)

    def _build_analysis_context(self,
                                team_name: str,
                                stats: Dict[str, Any],
                                include_recommendations: bool,
                                analysis_type: str = 'own') -> str:
        """Build comprehensive analysis context from team statistics.

        Constructs a structured markdown document containing team statistics
        with league-wide quartile comparisons. Each statistic is annotated
        with strength/weakness indicators based on quartile position:
        - Q4 (top 25%): 🔥 Fortaleza (Strength)
        - Q1 (bottom 25%): ⚠️ Debilidad (Weakness)
        - Q2/Q3 (middle 50%): No annotation

        The context includes:
        - Season overview (games played, wins/losses, record)
        - Offensive statistics (points, FG%, 3P%, FT%, assists, etc.)
        - Defensive statistics (points allowed, rebounds, steals, blocks)
        - Advanced metrics (ORtg, DRtg, pace, eFG%, TS%, etc.)
        - Per-game and percentage-based statistics
        - Quartile-based comparisons across all 26+ metrics

        Args:
            team_name: Name of the team being analyzed
            stats: Dictionary containing team_stats and league_stats
            include_recommendations: Whether to request strategic recommendations

        Returns:
            Formatted markdown string with annotated statistics ready for AI analysis

        Note:
            League quartiles are calculated using linear interpolation at the
            25th, 50th, and 75th percentiles across all teams in the league.
        """
        sections = []

        # Header
        sections.append(f"# Análisis de Equipo de Baloncesto: {team_name}\n")

        # Team overall season statistics if available
        if 'team_stats' in stats and stats['team_stats']:
            team_stats = stats['team_stats']
            league_stats = stats.get('league_stats', {})

            sections.append("## Estadísticas Generales de Temporada\n")

            if team_stats.get('games_played', 0) > 0:
                sections.append(f"- **Partidos jugados**: {team_stats['games_played']}")

                # Basic stats with quartile comparison
                sections.append(self._format_stat_with_quartile(
                    "Puntos por partido",
                    team_stats.get('points_per_game', 0),
                    league_stats.get('points_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Puntos recibidos por partido",
                    team_stats.get('points_allowed_per_game', 0),
                    league_stats.get('points_allowed_per_game', {}),
                    higher_is_better=False
                ))
                sections.append(self._format_stat_with_quartile(
                    "Rebotes por partido",
                    team_stats.get('rebounds_per_game', 0),
                    league_stats.get('rebounds_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Asistencias por partido",
                    team_stats.get('assists_per_game', 0),
                    league_stats.get('assists_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Robos por partido",
                    team_stats.get('steals_per_game', 0),
                    league_stats.get('steals_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Tapones por partido",
                    team_stats.get('blocks_per_game', 0),
                    league_stats.get('blocks_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Pérdidas por partido",
                    team_stats.get('turnovers_per_game', 0),
                    league_stats.get('turnovers_per_game', {}),
                    higher_is_better=False
                ))
                sections.append("")

                sections.append("### Porcentajes de Tiro\n")
                sections.append(self._format_stat_with_quartile(
                    "Tiros de 2 puntos (%)",
                    team_stats.get('fg2_percentage', 0),
                    league_stats.get('fg2_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Tiros de 3 puntos (%)",
                    team_stats.get('fg3_percentage', 0),
                    league_stats.get('fg3_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Tiros libres (%)",
                    team_stats.get('ft_percentage', 0),
                    league_stats.get('ft_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Porcentaje de triples (% de tiros que son 3PT)",
                    team_stats.get('three_point_rate', 0),
                    league_stats.get('three_point_rate', {}),
                    higher_is_better=None,  # Neutral - depends on strategy
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Four Factors (Factores de Dean Oliver)\n")
                sections.append(self._format_stat_with_quartile(
                    "eFG% (Effective Field Goal %)",
                    team_stats.get('effective_fg_percentage', 0),
                    league_stats.get('efg_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "TOV% (Turnover Rate)",
                    team_stats.get('turnover_rate', 0),
                    league_stats.get('turnover_rate', {}),
                    higher_is_better=False,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "ORB% (Offensive Rebound Rate)",
                    team_stats.get('offensive_rebound_rate', 0),
                    league_stats.get('offensive_rebound_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "FTr (Free Throw Rate)",
                    team_stats.get('free_throw_rate', 0),
                    league_stats.get('free_throw_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "TS% (True Shooting %)",
                    team_stats.get('true_shooting_percentage', 0),
                    league_stats.get('true_shooting', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Estadísticas de Juego (Playmaking & Defense)\n")
                sections.append(self._format_stat_with_quartile(
                    "Assist Rate (asistencias por 100 posesiones)",
                    team_stats.get('assist_rate', 0),
                    league_stats.get('assist_rate', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "AST/FG% (% de canastas asistidas)",
                    team_stats.get('assist_fg_rate', 0),
                    league_stats.get('assist_fg_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Steal Rate (robos por 100 posesiones)",
                    team_stats.get('steal_rate', 0),
                    league_stats.get('steal_rate', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Block Rate (tapones por 100 posesiones)",
                    team_stats.get('block_rate', 0),
                    league_stats.get('block_rate', {}),
                    higher_is_better=True
                ))
                sections.append("")

                sections.append("### Rebotes\n")
                sections.append(self._format_stat_with_quartile(
                    "DRB% (Defensive Rebound Rate)",
                    team_stats.get('defensive_rebound_rate', 0),
                    league_stats.get('defensive_rebound_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Ratings de Eficiencia\n")
                sections.append(self._format_stat_with_quartile(
                    "Rating Ofensivo (puntos por 100 posesiones)",
                    team_stats.get('offensive_rating', 0),
                    league_stats.get('offensive_rating', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Rating Defensivo (puntos permitidos por 100 posesiones)",
                    team_stats.get('defensive_rating', 0),
                    league_stats.get('defensive_rating', {}),
                    higher_is_better=False
                ))
                sections.append(self._format_stat_with_quartile(
                    "Net Rating (diferencia ORtg - DRtg)",
                    team_stats.get('net_rating', 0),
                    league_stats.get('net_rating', {}),
                    higher_is_better=True
                ))
                sections.append(self._format_stat_with_quartile(
                    "Ritmo/Pace (posesiones por partido)",
                    team_stats.get('pace', 0),
                    league_stats.get('possessions_per_game', {}),
                    higher_is_better=None  # Neutral stat
                ))
                sections.append("")

        # Zone performance if available
        if 'zone_stats' in stats and stats['zone_stats']:
            sections.append("## Zone Performance Statistics\n")

            zone_data = []
            for zone_key, data in stats['zone_stats'].items():
                if data['total'] > 0:
                    zone_info = data.get('zone_info', {})
                    zone_name = zone_info.get('name', zone_key)
                    made = data['made']
                    total = data['total']
                    pct = data['percentage']
                    points = zone_info.get('points', 2)

                    zone_data.append(
                        f"- **{zone_name}** ({points}PT): {made}/{total} shots ({pct:.1f}%)"
                    )

            sections.append('\n'.join(zone_data))
            sections.append('')

        # Overall statistics
        if 'total_shots' in stats:
            sections.append("## Overall Statistics\n")
            sections.append(f"- Total shots attempted: {stats['total_shots']}")

            if 'unclassified_shots' in stats:
                classified = stats['total_shots'] - stats['unclassified_shots']
                sections.append(f"- Classified shots: {classified}")

            sections.append('')

        # 2PT vs 3PT breakdown
        if 'zone_stats' in stats:
            two_pt_made = sum(d['made'] for d in stats['zone_stats'].values()
                            if d['total'] > 0 and d.get('zone_info', {}).get('points') == 2)
            two_pt_total = sum(d['total'] for d in stats['zone_stats'].values()
                             if d['total'] > 0 and d.get('zone_info', {}).get('points') == 2)
            three_pt_made = sum(d['made'] for d in stats['zone_stats'].values()
                              if d['total'] > 0 and d.get('zone_info', {}).get('points') == 3)
            three_pt_total = sum(d['total'] for d in stats['zone_stats'].values()
                               if d['total'] > 0 and d.get('zone_info', {}).get('points') == 3)

            if two_pt_total > 0 or three_pt_total > 0:
                sections.append("## Shot Type Breakdown\n")

                if two_pt_total > 0:
                    two_pt_pct = (two_pt_made / two_pt_total) * 100
                    sections.append(f"- **2-Point shots**: {two_pt_made}/{two_pt_total} ({two_pt_pct:.1f}%)")

                if three_pt_total > 0:
                    three_pt_pct = (three_pt_made / three_pt_total) * 100
                    sections.append(f"- **3-Point shots**: {three_pt_made}/{three_pt_total} ({three_pt_pct:.1f}%)")

                sections.append('')

        # Analysis request
        sections.append("\n---\n")
        sections.append("PETICION DE ANALISIS:\n")
        sections.append("Genera un informe HTML completo y detallado basado en las estadisticas anteriores.\n")
        sections.append("REGLAS CRITICAS:")
        sections.append("1. Las estadisticas marcadas con [+] FORTALEZA son puntos fuertes - explicalas TODAS")
        sections.append("2. Las estadisticas marcadas con [-] DEBILIDAD son puntos debiles - explicalas TODAS")
        sections.append("3. NO reinterpretes los cuartiles - CONFIA en las marcas [+] y [-] proporcionadas")
        sections.append("4. Minimo 1000 palabras de contenido real y detallado")
        sections.append("5. Si hay datos de zonas de tiro, analiza las zonas calientes y frias\n")

        if include_recommendations:
            if analysis_type == 'opponent':
                sections.append("TIPO DE ANALISIS: SCOUTING RIVAL")
                sections.append("Este informe es para un ENTRENADOR que se va a ENFRENTAR a este equipo.")
                sections.append("Enfoca todo el analisis en COMO NEUTRALIZAR sus fortalezas y EXPLOTAR sus debilidades.\n")
                sections.append("Incluye secciones obligatorias:")
                sections.append("- Puntos Fuertes del Rival: Todas las estadisticas [+] y COMO NEUTRALIZARLAS")
                sections.append("- Debilidades del Rival: Todas las estadisticas [-] y COMO EXPLOTARLAS")
                sections.append("- Analisis de Zonas de Tiro: Donde son peligrosos y donde defenderles mejor")
                sections.append("- Perfil del Rival: Su estilo de juego y como contrarrestarlo")
                sections.append("- Plan Tactico Defensivo: Como defender contra sus fortalezas")
                sections.append("- Plan Tactico Ofensivo: Como atacar sus debilidades")
                sections.append("- Enfoque de Entrenamiento: Preparacion especifica para este partido")
            else:
                sections.append("TIPO DE ANALISIS: SCOUTING PROPIO")
                sections.append("Este informe es para mejorar el rendimiento del PROPIO equipo.\n")
                sections.append("Incluye secciones obligatorias:")
                sections.append("- Puntos Fuertes Clave: Todas las estadisticas [+] con explicaciones")
                sections.append("- Debilidades Criticas: Todas las estadisticas [-] con impacto")
                sections.append("- Analisis de Tiro por Zonas: Interpretacion del shot chart")
                sections.append("- Perfil de Equipo: Caracterizacion del estilo de juego")
                sections.append("- Recomendaciones Tacticas: Estrategias basadas en fortalezas/debilidades")
                sections.append("- Enfoque de Entrenamiento: Top 5 prioridades con ejercicios especificos")

        return '\n'.join(sections)

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

            # Log response details
            response_text = response.text
            print(f"[Gemini] Response generated successfully ({len(response_text)} chars)")

            # Check if response was truncated
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = str(candidate.finish_reason)
                    if 'MAX_TOKENS' in finish_reason or 'LENGTH' in finish_reason:
                        print(f"[Gemini] WARNING: Response truncated! Increase MAX_TOKENS (current: {AnalysisConfig.MAX_TOKENS})")
                        print(f"[Gemini] Response preview: {response_text[:200]}...")
                        print(f"[Gemini] Response ending: ...{response_text[-200:]}")

            return response_text

        except Exception as e:
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
