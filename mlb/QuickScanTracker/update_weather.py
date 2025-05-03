from app import app, db
from services.weather_service import WeatherService
from models import Game, WeatherCondition
from datetime import datetime

def update_weather():
    """Update weather data for all upcoming games"""
    with app.app_context():
        # Get all scheduled games
        games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.now(),
            Game.status == 'scheduled'
        ).all()
        
        # Initialize weather service
        weather_service = WeatherService()
        
        print(f"Updating weather for {len(games)} upcoming games")
        
        # Update weather for each game
        for game in games:
            try:
                # Delete any existing weather data to ensure fresh data
                db.session.query(WeatherCondition).filter_by(game_id=game.id).delete()
                db.session.commit()
                
                # Fetch new weather data
                weather_data = weather_service.fetch_weather_for_game(game.id)
                
                if weather_data:
                    print(f"Updated weather for {game.home_team.abbreviation} vs {game.away_team.abbreviation} - {game.game_datetime}")
                    print(f"  Temperature: {weather_data.get('temperature')}°F, {weather_data.get('weather_description')}")
                else:
                    print(f"Failed to update weather for game {game.id}")
            except Exception as e:
                print(f"Error updating weather for game {game.id}: {e}")
                db.session.rollback()
        
        print("Weather update complete!")

if __name__ == "__main__":
    update_weather()