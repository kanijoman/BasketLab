"""
Example: Shot Chart Visualization from FEB JSON Data

This script demonstrates how to visualize basketball shot data from FEB JSON files.
"""

from src.shotcharts import ShotChartVisualizer, plot_shot_chart
import matplotlib.pyplot as plt


def example_basic_shot_chart():
    """Example 1: Basic shot chart for a single team."""
    print("Example 1: Basic shot chart - Home team")
    
    fig = plot_shot_chart(
        'src/JSON_samples/feb_game.json',
        team=0,  # Home team
        title='Home Team Shot Chart - All Quarters',
        save_path='example_home_team.png'
    )
    plt.show()


def example_filtered_by_quarter():
    """Example 2: Shot chart filtered by quarter."""
    print("\nExample 2: Shot chart for Q3 only")
    
    viz = ShotChartVisualizer()
    shots = viz.load_shots_from_json('src/JSON_samples/feb_game.json')
    
    fig = viz.plot_shots(
        shots,
        team=1,  # Away team
        quarter=3,  # Third quarter only
        title='Away Team - 3rd Quarter',
        save_path='example_quarter_3.png'
    )
    plt.show()


def example_player_shot_chart():
    """Example 3: Shot chart for a specific player."""
    print("\nExample 3: Shot chart for player #15")
    
    viz = ShotChartVisualizer()
    shots = viz.load_shots_from_json('src/JSON_samples/feb_game.json')
    
    fig = viz.plot_shots(
        shots,
        player='15',  # Player with dorsal #15
        title='Player #15 Shot Chart',
        save_path='example_player_15.png'
    )
    plt.show()


def example_comparison():
    """Example 4: Side-by-side comparison of both teams."""
    print("\nExample 4: Side-by-side team comparison")
    
    viz = ShotChartVisualizer()
    shots = viz.load_shots_from_json('src/JSON_samples/feb_game.json')
    
    # Create figure with 2 subplots
    # Note: We create our own figure for side-by-side comparison
    
    # Home team
    home_shots = [s for s in shots if int(s['team']) == 0]
    home_made = sum(1 for s in home_shots if int(s['m']) == 1)
    
    # Away team
    away_shots = [s for s in shots if int(s['team']) == 1]
    away_made = sum(1 for s in away_shots if int(s['m']) == 1)
    
    print(f"Home team: {home_made}/{len(home_shots)} ({home_made/len(home_shots)*100:.1f}%)")
    print(f"Away team: {away_made}/{len(away_shots)} ({away_made/len(away_shots)*100:.1f}%)")
    
    # Create separate charts
    viz.plot_shots(home_shots, title='Home Team', save_path='comparison_home.png')
    viz.plot_shots(away_shots, title='Away Team', save_path='comparison_away.png')
    
    print("Comparison charts saved!")


def example_custom_styling():
    """Example 5: Shot chart with custom court styling."""
    print("\nExample 5: Custom styled shot chart")
    
    viz = ShotChartVisualizer()
    shots = viz.load_shots_from_json('src/JSON_samples/feb_game.json')
    
    fig = viz.plot_shots(
        shots,
        team=0,
        court_color='#E8F4F8',  # Light blue court
        line_color='#2C5F8D',    # Dark blue lines
        figsize=(14, 14),         # Larger figure
        legend_loc='lower center',  # Legend below court (avoids overlapping)
        title='Home Team Shot Chart - Custom Style',
        save_path='example_custom_style.png',
        dpi=200  # Higher resolution
    )
    plt.show()


def example_shot_statistics():
    """Example 6: Analyze shot statistics."""
    print("\nExample 6: Shot statistics analysis")
    
    viz = ShotChartVisualizer()
    shots = viz.load_shots_from_json('src/JSON_samples/feb_game.json')
    
    print(f"Total shots in game: {len(shots)}")
    
    # By team
    for team_id in [0, 1]:
        team_shots = [s for s in shots if int(s['team']) == team_id]
        made = sum(1 for s in team_shots if int(s['m']) == 1)
        missed = len(team_shots) - made
        
        team_name = "Home" if team_id == 0 else "Away"
        print(f"\n{team_name} Team:")
        print(f"  Total shots: {len(team_shots)}")
        print(f"  Made: {made} ({made/len(team_shots)*100:.1f}%)")
        print(f"  Missed: {missed} ({missed/len(team_shots)*100:.1f}%)")
        
        # By quarter
        print(f"  By quarter:")
        for q in range(1, 5):
            q_shots = [s for s in team_shots if int(s['quarter']) == q]
            if q_shots:
                q_made = sum(1 for s in q_shots if int(s['m']) == 1)
                print(f"    Q{q}: {q_made}/{len(q_shots)} ({q_made/len(q_shots)*100:.1f}%)")


if __name__ == "__main__":
    print("="*60)
    print("FIBA Shot Chart Visualization Examples")
    print("="*60)
    
    # Uncomment the examples you want to run:
    
    example_basic_shot_chart()
    # example_filtered_by_quarter()
    # example_player_shot_chart()
    # example_comparison()
    # example_custom_styling()
    # example_shot_statistics()
    
    print("\n" + "="*60)
    print("Done! Check the generated images.")
    print("="*60)
