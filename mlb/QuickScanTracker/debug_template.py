#!/usr/bin/env python3
import logging
from app import app, db
from models import Game, Team, Prediction, PerformanceLog
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_template_rendering():
    """Debug template rendering to identify why games aren't displaying"""
    with app.app_context():
        try:
            # Get today's date
            today = datetime.now().date()
            days_ahead = 7  # Show games for the next week
            
            # Get upcoming games for the next week
            upcoming_games = db.session.query(Game).filter(
                Game.game_datetime >= datetime.now(),
                Game.game_datetime < datetime.now() + timedelta(days=days_ahead),
                Game.status != 'final'
            ).order_by(Game.game_datetime).all()
            
            logger.info(f"Found {len(upcoming_games)} upcoming games")
            
            # Get the latest prediction for each game
            game_predictions = {}
            for game in upcoming_games:
                prediction = db.session.query(Prediction).filter(
                    Prediction.game_id == game.id
                ).order_by(Prediction.timestamp.desc()).first()
                
                if prediction:
                    game_predictions[game.id] = prediction
            
            # Get performance summary (last 7 days)
            performance_summary = db.session.query(PerformanceLog).filter(
                PerformanceLog.date >= (today - timedelta(days=7)),
                PerformanceLog.bet_type == 'all_bets'
            ).order_by(PerformanceLog.date.desc()).all()
            
            # Calculate overall ROI - with additional safety for empty data
            total_profit = sum([log.profit_loss for log in performance_summary]) if performance_summary else 0
            total_bets = sum([log.total_bets for log in performance_summary]) if performance_summary else 0
            overall_roi = (total_profit / total_bets * 100) if total_bets > 0 else 0
            
            # Attempt to manually render the template
            from flask import render_template
            
            with app.test_request_context():
                # Render the template with our data
                html = render_template(
                    'index.html',
                    upcoming_games=upcoming_games,
                    game_predictions=game_predictions,
                    performance_summary=performance_summary,
                    overall_roi=overall_roi,
                    today=today
                )
                
                # Check if the games section appears in the HTML
                games_section_start = '{% if upcoming_games %}'
                games_section_end = '{% else %}'
                games_section_found = 'upcoming_games' in html
                
                logger.info(f"Games section found in rendered HTML: {games_section_found}")
                
                # Look for evidence of game rendering
                team_names_found = []
                for game in upcoming_games[:5]:
                    home_team = game.home_team.name
                    away_team = game.away_team.name
                    if home_team in html and away_team in html:
                        team_names_found.append(f"{away_team} @ {home_team}")
                
                logger.info(f"Team names found in HTML: {len(team_names_found)}")
                for team_pair in team_names_found:
                    logger.info(f"  - {team_pair}")
                
                # Check for the "No upcoming games" message
                no_games_message = "No upcoming games scheduled for today"
                no_games_message_found = no_games_message in html
                
                logger.info(f"'No upcoming games' message found: {no_games_message_found}")
                
                # Look for any error messages in the HTML
                error_section_start = '{% if error %}'
                error_section_found = 'error' in html
                
                logger.info(f"Error section found in HTML: {error_section_found}")
                
                # Create a simplified test template and try to render it
                test_template = """
                <!DOCTYPE html>
                <html>
                <head><title>Test</title></head>
                <body>
                    <h1>Test Template</h1>
                    <p>Game count: {{ upcoming_games|length }}</p>
                    <ul>
                    {% for game in upcoming_games %}
                        <li>{{ game.away_team.name }} @ {{ game.home_team.name }} - {{ game.game_datetime }}</li>
                    {% endfor %}
                    </ul>
                </body>
                </html>
                """
                
                with open('templates/test.html', 'w') as f:
                    f.write(test_template)
                
                # Try rendering the test template
                test_html = render_template(
                    'test.html',
                    upcoming_games=upcoming_games
                )
                
                test_game_count = f"Game count: {len(upcoming_games)}"
                test_games_rendered = test_game_count in test_html
                
                logger.info(f"Test template rendered with games: {test_games_rendered}")
                
                # Write test HTML to file for inspection
                with open('test_output.html', 'w') as f:
                    f.write(test_html)
                
                # Let's test rendering directly with Flask's renderer
                from jinja2 import Template
                direct_template = Template("""
                Game count: {{ upcoming_games|length }}
                {% for game in upcoming_games %}
                {{ game.away_team.name }} @ {{ game.home_team.name }}
                {% endfor %}
                """)
                
                direct_html = direct_template.render(upcoming_games=upcoming_games)
                logger.info(f"Direct template output: {direct_html}")
                
                return {
                    "game_count": len(upcoming_games),
                    "games_section_found": games_section_found,
                    "team_names_found": len(team_names_found),
                    "no_games_message_found": no_games_message_found
                }
                
        except Exception as e:
            logger.error(f"Error debugging template: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}

if __name__ == "__main__":
    results = debug_template_rendering()
    logger.info(f"Debug results: {results}")