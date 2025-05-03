from app import app, db
from models import Game, WeatherCondition
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_yankees_weather():
    """Update the Yankees game weather to 73°F."""
    
    with app.app_context():
        # Find Yankees game (could be home or away)
        yankees_games = db.session.query(Game).filter(
            (Game.home_team.has(name='New York Yankees')) | 
            (Game.away_team.has(name='New York Yankees')),
            Game.game_datetime >= datetime.now()
        ).all()
        
        if not yankees_games:
            logger.error("No upcoming Yankees games found")
            return
        
        logger.info(f"Found {len(yankees_games)} upcoming Yankees games")
        
        for game in yankees_games:
            logger.info(f"Updating weather for Yankees game {game.id} at {game.stadium}")
            
            # Get weather condition for this game
            weather = db.session.query(WeatherCondition).filter_by(game_id=game.id).first()
            
            if weather:
                # Update to 73°F
                old_temp = weather.temperature
                weather.temperature = 73.0
                db.session.commit()
                logger.info(f"Updated Yankees game {game.id} weather from {old_temp}°F to 73.0°F")
            else:
                logger.warning(f"No weather data found for Yankees game {game.id}")
                
                # Create new weather record with 73°F
                weather = WeatherCondition(
                    game_id=game.id,
                    temperature=73.0,
                    humidity=50,
                    wind_speed=8,
                    wind_direction="S",
                    precipitation_chance=10,
                    weather_description="Sunny"
                )
                db.session.add(weather)
                db.session.commit()
                logger.info(f"Created new weather record for Yankees game {game.id} with 73.0°F")

if __name__ == "__main__":
    print("Updating Yankees game weather to 73°F")
    update_yankees_weather()
    print("Update complete")