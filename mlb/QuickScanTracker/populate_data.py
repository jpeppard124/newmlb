#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import Team, Game, ApiKey
from services.sportsdataio_service import SportsDataIOService
from services.odds_service import OddsService
from services.weather_service import WeatherService
from prediction.engine import PredictionEngine
from datetime import datetime

def populate_data():
    """Populate the database with real data"""
    print("Starting data population...")
    
    # Initialize services
    sportsdataio_service = SportsDataIOService()
    odds_service = OddsService()
    weather_service = WeatherService()
    prediction_engine = PredictionEngine()
    
    with app.app_context():
        # 1. Fetch and store teams
        print("Fetching teams...")
        teams = sportsdataio_service.fetch_teams()
        print(f"Fetched {len(teams)} teams")
        
        # 2. Fetch and store upcoming games
        print("Fetching upcoming games...")
        games_count = sportsdataio_service.update_games(days_ahead=7)
        print(f"Fetched {games_count} games")
        
        # 3. Update odds for games
        print("Updating odds...")
        odds_service.update_all_odds()
        
        # 4. Update weather forecasts
        print("Updating weather forecasts...")
        weather_service.update_all_game_weather()
        
        # 5. Generate predictions for upcoming games
        print("Generating predictions...")
        today = datetime.now().date()
        games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.combine(today, datetime.min.time())
        ).limit(5).all()
        
        for game in games:
            print(f"Generating prediction for game: {game.game_id}")
            prediction = prediction_engine.generate_prediction(game.id)
            if prediction:
                print(f"✓ Prediction generated for game {game.id}")
            else:
                print(f"✗ Failed to generate prediction for game {game.id}")
        
        print("Data population complete!")

if __name__ == "__main__":
    populate_data()