#!/usr/bin/env python3
from app import app, db
from models import Game
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_games():
    """Check games stored in the database"""
    with app.app_context():
        # Get upcoming games
        upcoming_games = db.session.query(Game).filter(Game.game_datetime > datetime.now()).order_by(Game.game_datetime).all()
        
        logger.info(f"Found {len(upcoming_games)} upcoming games:")
        for i, game in enumerate(upcoming_games[:10]):  # Show first 10 games
            logger.info(f"{i+1}. {game.away_team.name} @ {game.home_team.name} - {game.game_datetime}")
            logger.info(f"   Stadium: {game.stadium or 'Not set'}")
            logger.info(f"   Status: {game.status}")
            
        # Check if we have odds for any games
        games_with_odds = db.session.query(Game).join(Game.odds).distinct().all()
        logger.info(f"Found {len(games_with_odds)} games with odds")
        
        # Check if we have weather for any games
        games_with_weather = db.session.query(Game).join(Game.weather_conditions).distinct().all()
        logger.info(f"Found {len(games_with_weather)} games with weather data")
        
        # Check if we have predictions for any games
        games_with_predictions = db.session.query(Game).join(Game.predictions).distinct().all()
        logger.info(f"Found {len(games_with_predictions)} games with predictions")
        
        return {
            "upcoming_games": len(upcoming_games),
            "games_with_odds": len(games_with_odds),
            "games_with_weather": len(games_with_weather),
            "games_with_predictions": len(games_with_predictions)
        }

if __name__ == "__main__":
    stats = check_games()
    logger.info(f"Game statistics: {stats}")