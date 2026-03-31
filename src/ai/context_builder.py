"""
Context Builder - Build analysis contexts for AI processing.

This module constructs structured context strings from team and player
statistics for AI analysis, including quartile comparisons and prompts.
"""

from typing import Dict, Any, Optional
from .statistics_formatter import StatisticsFormatter


class ContextBuilder:
    """Build analysis contexts for team and player statistics."""

    def __init__(self):
        """Initialize context builder with formatter."""
        self.formatter = StatisticsFormatter()

    def build_team_context(self,
                          team_name: str,
                          stats: Dict[str, Any],
                          include_recommendations: bool,
                          analysis_type: str = 'own') -> str:
        """
        Build comprehensive analysis context from team statistics.

        Constructs a structured markdown document containing team statistics
        with league-wide quartile comparisons, differentials vs league median,
        and consistency (CV) data. Each statistic is annotated with
        strength/weakness indicators based on quartile position.

        Args:
            team_name: Name of the team being analyzed
            stats: Dictionary containing team_stats, league_stats, and optional
                   consistency {stat_key: {mean, std, cv, n}}
            include_recommendations: Whether to request strategic recommendations
            analysis_type: 'own', 'scouting'/'opponent' for rival scouting,
                           or 'individual' (falls back to own)

        Returns:
            Formatted markdown string with annotated statistics ready for AI analysis
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
                sections.append(self.formatter.format_stat_with_quartile(
                    "Puntos por partido",
                    team_stats.get('points_per_game', 0),
                    league_stats.get('points_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Puntos recibidos por partido",
                    team_stats.get('points_allowed_per_game', 0),
                    league_stats.get('points_allowed_per_game', {}),
                    higher_is_better=False
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Rebotes por partido",
                    team_stats.get('rebounds_per_game', 0),
                    league_stats.get('rebounds_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Asistencias por partido",
                    team_stats.get('assists_per_game', 0),
                    league_stats.get('assists_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Robos por partido",
                    team_stats.get('steals_per_game', 0),
                    league_stats.get('steals_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Tapones por partido",
                    team_stats.get('blocks_per_game', 0),
                    league_stats.get('blocks_per_game', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Pérdidas por partido",
                    team_stats.get('turnovers_per_game', 0),
                    league_stats.get('turnovers_per_game', {}),
                    higher_is_better=False
                ))
                sections.append("")

                sections.append("### Porcentajes de Tiro\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "Tiros de 2 puntos (%)",
                    team_stats.get('fg2_percentage', 0),
                    league_stats.get('fg2_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Tiros de 3 puntos (%)",
                    team_stats.get('fg3_percentage', 0),
                    league_stats.get('fg3_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Tiros libres (%)",
                    team_stats.get('ft_percentage', 0),
                    league_stats.get('ft_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Porcentaje de triples (% de tiros que son 3PT)",
                    team_stats.get('three_point_rate', 0),
                    league_stats.get('three_point_rate', {}),
                    higher_is_better=None,  # Neutral - depends on strategy
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Four Factors (Factores de Dean Oliver)\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "eFG% (Effective Field Goal %)",
                    team_stats.get('effective_fg_percentage', 0),
                    league_stats.get('efg_percentage', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "TOV% (Turnover Rate)",
                    team_stats.get('turnover_rate', 0),
                    league_stats.get('turnover_rate', {}),
                    higher_is_better=False,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "ORB% (Offensive Rebound Rate)",
                    team_stats.get('offensive_rebound_rate', 0),
                    league_stats.get('offensive_rebound_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "FTr (Free Throw Rate)",
                    team_stats.get('free_throw_rate', 0),
                    league_stats.get('free_throw_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "TS% (True Shooting %)",
                    team_stats.get('true_shooting_percentage', 0),
                    league_stats.get('true_shooting', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Estadísticas de Juego (Playmaking & Defense)\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "Assist Rate (asistencias por 100 posesiones)",
                    team_stats.get('assist_rate', 0),
                    league_stats.get('assist_rate', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "AST/FG% (% de canastas asistidas)",
                    team_stats.get('assist_fg_rate', 0),
                    league_stats.get('assist_fg_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Steal Rate (robos por 100 posesiones)",
                    team_stats.get('steal_rate', 0),
                    league_stats.get('steal_rate', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Block Rate (tapones por 100 posesiones)",
                    team_stats.get('block_rate', 0),
                    league_stats.get('block_rate', {}),
                    higher_is_better=True
                ))
                sections.append("")

                sections.append("### Rebotes\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "DRB% (Defensive Rebound Rate)",
                    team_stats.get('defensive_rebound_rate', 0),
                    league_stats.get('defensive_rebound_rate', {}),
                    higher_is_better=True,
                    is_percentage=True
                ))
                sections.append("")

                sections.append("### Ratings de Eficiencia\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "Rating Ofensivo (puntos por 100 posesiones)",
                    team_stats.get('offensive_rating', 0),
                    league_stats.get('offensive_rating', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Rating Defensivo (puntos permitidos por 100 posesiones)",
                    team_stats.get('defensive_rating', 0),
                    league_stats.get('defensive_rating', {}),
                    higher_is_better=False
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "Net Rating (diferencia ORtg - DRtg)",
                    team_stats.get('net_rating', 0),
                    league_stats.get('net_rating', {}),
                    higher_is_better=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
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

        # ── Differentials vs league median ──────────────────────────────────
        if 'team_stats' in stats and stats['team_stats']:
            team_stats = stats['team_stats']
            league_stats = stats.get('league_stats', {})

            # Key stats with (team_key, league_key, label, higher_good)
            diff_stats = [
                ('points_per_game',         'points_per_game',        'Puntos/P',     True),
                ('points_allowed_per_game', 'points_allowed_per_game','Puntos recib.', False),
                ('rebounds_per_game',       'rebounds_per_game',      'Rebotes/P',    True),
                ('assists_per_game',        'assists_per_game',       'Asistencias/P', True),
                ('turnovers_per_game',      'turnovers_per_game',     'Pérdidas/P',   False),
                ('offensive_rating',        'offensive_rating',       'ORtg',         True),
                ('defensive_rating',        'defensive_rating',       'DRtg',         False),
                ('net_rating',              'net_rating',             'Net Rating',   True),
                ('effective_fg_percentage', 'efg_percentage',         'eFG%',         True),
                ('true_shooting_percentage','true_shooting',          'TS%',          True),
            ]

            diff_lines = []
            for team_key, league_key, label, higher_good in diff_stats:
                tval = team_stats.get(team_key)
                lq   = league_stats.get(league_key, {})
                median = lq.get('q2') if isinstance(lq, dict) else None
                if tval is not None and median is not None:
                    try:
                        diff = float(tval) - float(median)
                        sign = '+' if diff >= 0 else ''
                        good = (diff > 0) == higher_good
                        marker = '[+]' if good else '[-]'
                        diff_lines.append(f"  {marker} {label}: {sign}{diff:.1f} vs media liga ({float(median):.1f})")
                    except (TypeError, ValueError):
                        pass

            if diff_lines:
                sections.append("### Diferenciales vs Liga (equipo − media de la competición)\n")
                sections.extend(diff_lines)
                sections.append("")

        # ── Consistency / dispersion (CV) ───────────────────────────────────
        consistency = stats.get('consistency', {})
        if consistency:
            cv_labels = {
                'points_per_game':         'Puntos/P',
                'points_allowed_per_game': 'Puntos recib./P',
                'rebounds_per_game':       'Rebotes/P',
                'assists_per_game':        'Asistencias/P',
                'turnovers_per_game':      'Pérdidas/P',
                'offensive_rating':        'ORtg',
                'defensive_rating':        'DRtg',
                'net_rating':              'Net Rating',
                'effective_fg_percentage': 'eFG%',
                'true_shooting':           'TS%',
                'fg3_percentage':          'T3%',
            }
            sections.append("### Consistencia partido a partido (Coeficiente de Variación)\n")
            sections.append("CV < 15% = Consistente | 15–30% = Variabilidad moderada | > 30% = Alta variabilidad\n")
            for stat_key, label in cv_labels.items():
                entry = consistency.get(stat_key)
                if entry and isinstance(entry, dict):
                    cv = entry.get('cv')
                    mean = entry.get('mean')
                    if cv is not None and mean is not None:
                        if cv < 15:
                            nivel = 'Consistente'
                        elif cv < 30:
                            nivel = 'Variabilidad moderada'
                        else:
                            nivel = 'Alta variabilidad'
                        sections.append(f"  - {label}: media={float(mean):.1f}, CV={float(cv):.1f}% → {nivel}")
            sections.append("")
        else:
            sections.append("### Consistencia\n")
            sections.append("  - Datos de consistencia no disponibles para esta liga.\n")

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
            if analysis_type in ('opponent', 'scouting'):
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

    def build_player_context(self,
                            player_name: str,
                            player_stats: Dict[str, Any],
                            league_stats: Optional[Dict[str, Any]] = None) -> str:
        """
        Build compact player analysis context with key statistics.

        Args:
            player_name: Name of the player
            player_stats: Dictionary containing player statistics
            league_stats: Optional dictionary with league-wide statistics for comparison

        Returns:
            Formatted context string for player analysis
        """
        sections = []

        sections.append(f"# Análisis de Scouting: {player_name}\n")
        sections.append(f"**Equipo**: {player_stats.get('team_name', 'N/A')}\n")
        sections.append(f"**Dorsal**: {player_stats.get('dorsal', 'N/A')}\n\n")

        # Basic stats
        games = player_stats.get('games_played', 0)
        if games > 0:
            sections.append("## Estadísticas Principales\n")
            sections.append(f"- **Partidos jugados**: {games}")
            sections.append(f"- **Minutos/partido**: {player_stats.get('mpg', 0):.1f}")
            sections.append(f"- **Puntos/partido**: {player_stats.get('ppg', 0):.1f}")
            sections.append(f"- **Rebotes/partido**: {player_stats.get('rpg', 0):.1f}")
            sections.append(f"- **Asistencias/partido**: {player_stats.get('apg', 0):.1f}")
            sections.append(f"- **Pérdidas/partido**: {player_stats.get('topg', 0):.1f}\n")

            # Shooting percentages
            sections.append("## Porcentajes de Tiro\n")
            sections.append(self.formatter.format_stat_with_quartile(
                "TL%", player_stats.get('ft_pct', 0),
                league_stats.get('ft_pct', {}) if league_stats else {},
                is_percentage=True
            ))
            sections.append(self.formatter.format_stat_with_quartile(
                "T2%", player_stats.get('fg2_pct', 0),
                league_stats.get('fg2_pct', {}) if league_stats else {},
                is_percentage=True
            ))
            sections.append(self.formatter.format_stat_with_quartile(
                "T3%", player_stats.get('fg3_pct', 0),
                league_stats.get('fg3_pct', {}) if league_stats else {},
                is_percentage=True
            ))
            sections.append(self.formatter.format_stat_with_quartile(
                "TS%", player_stats.get('ts', 0),
                league_stats.get('ts', {}) if league_stats else {},
                is_percentage=True
            ))

            # Advanced stats (most relevant for scouting)
            if player_stats.get('usage', 0) > 0:
                sections.append("\n## Estadísticas Avanzadas\n")
                sections.append(self.formatter.format_stat_with_quartile(
                    "USG% (Uso del balón)", player_stats.get('usage', 0),
                    league_stats.get('usage', {}) if league_stats else {},
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "AST% (Porcentaje de asistencias)", player_stats.get('ast_pct', 0),
                    league_stats.get('ast_pct', {}) if league_stats else {},
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "TO% (Porcentaje de pérdidas)", player_stats.get('tov_pct', 0),
                    league_stats.get('tov_pct', {}) if league_stats else {},
                    higher_is_better=False,
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "ORtg (Rating ofensivo)", player_stats.get('orating', 0),
                    league_stats.get('orating', {}) if league_stats else {}
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "DRtg (Rating defensivo)", player_stats.get('drating', 0),
                    league_stats.get('drating', {}) if league_stats else {},
                    higher_is_better=False
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "STL% (Porcentaje de robos)", player_stats.get('stl_pct', 0),
                    league_stats.get('stl_pct', {}) if league_stats else {},
                    is_percentage=True
                ))
                sections.append(self.formatter.format_stat_with_quartile(
                    "BLK% (Porcentaje de tapones)", player_stats.get('blk_pct', 0),
                    league_stats.get('blk_pct', {}) if league_stats else {},
                    is_percentage=True
                ))

        sections.append("\n---\n")
        sections.append("**Tarea**: Genera notas de scouting SUCINTAS (máximo 6-8 líneas) ")
        sections.append("identificando las 2-3 fortalezas principales, 1-2 debilidades clave, ")
        sections.append("y una línea sobre el perfil de juego.")

        return "\n".join(sections)
