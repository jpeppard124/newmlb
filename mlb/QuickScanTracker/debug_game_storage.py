import logging
from datetime import datetime, timedelta
from app import app, db
from models import Game, WeatherCondition, ParkFactor, Odds, Prediction, Team, PlayerStats

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_game_storage():
    """Debug the game storage process to identify data completeness issues"""
    
    with app.app_context():
        # Get upcoming games for the next week
        today = datetime.now()
        end_date = today + timedelta(days=7)
        
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date
        ).order_by(Game.game_datetime).all()
        
        logger.info(f"Found {len(upcoming_games)} upcoming games to check")
        
        data_issues = []
        for game in upcoming_games:
            game_issues = []
            
            # Check basic game data
            if not game.stadium:
                game_issues.append("Missing stadium info")
            
            if not game.home_team or not game.away_team:
                game_issues.append("Missing team info")
            
            # Check team data
            if game.home_team and not game.home_team.stadium:
                game_issues.append("Home team missing stadium info")
            
            if game.away_team and not game.away_team.stadium:
                game_issues.append("Away team missing stadium info")
            
            # Check weather data
            weather = db.session.query(WeatherCondition).filter_by(game_id=game.id).first()
            if not weather:
                game_issues.append("Missing weather data")
            elif weather.temperature is None:
                game_issues.append("Missing temperature data")
            
            # Check park factors
            if game.stadium:
                park_factor = db.session.query(ParkFactor).filter_by(stadium_name=game.stadium).first()
                if not park_factor:
                    game_issues.append("Missing park factor data")
            
            # Check odds data
            odds = db.session.query(Odds).filter_by(game_id=game.id).first()
            if not odds:
                game_issues.append("Missing odds data")
            
            # Add game to issues list if any problems found
            if game_issues:
                data_issues.append({
                    "game_id": game.id,
                    "teams": f"{game.away_team.name} @ {game.home_team.name}",
                    "datetime": game.game_datetime,
                    "issues": game_issues
                })
        
        # Print results
        print("\n===== GAME DATA COMPLETENESS CHECK =====")
        if not data_issues:
            print("✅ All games have complete data!")
        else:
            print(f"❌ Found {len(data_issues)} games with incomplete data:")
            
            for issue in data_issues:
                print(f"\nGame ID: {issue['game_id']} - {issue['teams']} ({issue['datetime']})")
                for item in issue['issues']:
                    print(f"  - {item}")
            
            # Provide summary of most common issues
            issue_types = {}
            for game in data_issues:
                for issue in game['issues']:
                    if issue in issue_types:
                        issue_types[issue] += 1
                    else:
                        issue_types[issue] = 1
            
            print("\nMost common issues:")
            for issue, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {issue}: {count} games")
        
        # Check type consistency for temperature data
        weather_records = db.session.query(WeatherCondition).all()
        type_issues = []
        
        for weather in weather_records:
            if weather.temperature and not isinstance(weather.temperature, (int, float)):
                type_issues.append(f"Game ID {weather.game_id}: temperature is {type(weather.temperature)}, value: {weather.temperature}")
        
        print("\n===== DATA TYPE CHECK =====")
        if not type_issues:
            print("✅ All temperature values have correct data type!")
        else:
            print(f"❌ Found {len(type_issues)} type issues:")
            for issue in type_issues:
                print(f"  - {issue}")

if __name__ == "__main__":
    print("Starting Game Data Diagnostic...")
    debug_game_storage()
    print("\nDiagnostic complete!")