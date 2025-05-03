import logging
import threading
import time
import os
import json
from datetime import datetime, timedelta
import schedule

from app import db
from config import Config
from services.sportsdataio_service import SportsDataIOService
from services.odds_service import OddsService
from services.weather_service import WeatherService
from prediction.engine import PredictionEngine

# Set up logging
logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduling and running periodic tasks"""
    def __init__(self):
        self.config = Config
        self.sports_data_service = SportsDataIOService()
        self.odds_service = OddsService()
        self.weather_service = WeatherService()
        self.prediction_engine = PredictionEngine()
        self.scheduler_thread = None
        self.stop_scheduler = False
        self.data_dir = "data/sportsdataio"
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.scheduler_thread is not None and self.scheduler_thread.is_alive():
            logger.warning("Scheduler is already running")
            return
        
        self.stop_scheduler = False
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Scheduler started")
        
        # Run initial data fetch at startup
        self.fetch_initial_data()
    
    def stop(self):
        """Stop the scheduler"""
        self.stop_scheduler = True
        if self.scheduler_thread is not None:
            self.scheduler_thread.join(timeout=10)
        logger.info("Scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        # Schedule daily tasks
        schedule.every().day.at("00:01").do(self.update_teams)
        schedule.every().day.at("06:00").do(self.update_games)
        schedule.every().day.at("09:00").do(self.update_player_stats)
        schedule.every().day.at("10:00").do(self.update_injuries)
        
        # Schedule hourly tasks
        schedule.every(1).hours.do(self.update_lineups_and_games)
        schedule.every(3).hours.do(self.update_weather)
        
        # Schedule frequent tasks
        schedule.every(15).minutes.do(self.update_odds)
        schedule.every(30).minutes.do(self.generate_predictions)
        
        while not self.stop_scheduler:
            schedule.run_pending()
            time.sleep(1)
    
    def fetch_initial_data(self):
        """Fetch initial data at startup"""
        logger.info("Fetching initial data...")
        
        try:
            # Fetch teams
            self.update_teams()
            
            # Fetch upcoming games
            self.update_games()
            
            # Fetch player stats
            self.update_player_stats()
            
            # Fetch injuries
            self.update_injuries()
            
            # Fetch lineups for today's games
            self.update_lineups_and_games()
            
            # Fetch weather for upcoming games
            self.update_weather()
            
            # Fetch odds
            self.update_odds()
            
            # Generate initial predictions
            self.generate_predictions()
            
            logger.info("Initial data fetch completed")
            
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
    
    def update_teams(self):
        """Update MLB teams data"""
        logger.info("Updating teams...")
        try:
            # Fetch teams from SportsDataIO
            teams = self.sports_data_service.fetch_teams()
            
            # Store the raw response for offline use if needed
            self._store_api_response(teams, 'teams.json')
            
            logger.info(f"Updated {len(teams)} teams")
            return True
        except Exception as e:
            logger.error(f"Error updating teams: {e}")
            return False
    
    def update_games(self):
        """Update MLB games for the next week"""
        logger.info("Updating games...")
        try:
            # Current date
            today = datetime.now()
            
            # Fetch games for the next 7 days
            all_games = []
            for i in range(7):
                date = today + timedelta(days=i)
                date_str = date.strftime('%Y-%b-%d')
                
                games = self.sports_data_service.fetch_games(date=date_str)
                all_games.extend(games)
                
                # Store the raw response for each day
                self._store_api_response(games, f'games_{date_str}.json')
            
            logger.info(f"Updated {len(all_games)} games for the next week")
            return True
        except Exception as e:
            logger.error(f"Error updating games: {e}")
            return False
    
    def update_player_stats(self):
        """Update player statistics"""
        logger.info("Updating player stats...")
        try:
            # Update player stats for all teams
            self.sports_data_service.update_player_stats()
            
            # We don't need to store this response as it's already stored in the database
            logger.info("Updated player stats")
            return True
        except Exception as e:
            logger.error(f"Error updating player stats: {e}")
            return False
    
    def update_injuries(self):
        """Update player injuries"""
        logger.info("Updating injuries...")
        try:
            # Fetch current injuries
            injuries = self.sports_data_service.fetch_player_injuries()
            
            # Store the raw response for offline use if needed
            self._store_api_response(injuries, 'injuries.json')
            
            logger.info(f"Updated {len(injuries)} injuries")
            return True
        except Exception as e:
            logger.error(f"Error updating injuries: {e}")
            return False
    
    def update_lineups_and_games(self):
        """Update starting lineups and game statuses"""
        logger.info("Updating lineups and game statuses...")
        try:
            # Current date
            today = datetime.now().strftime('%Y-%b-%d')
            
            # Fetch lineups for today's games
            lineups = self.sports_data_service.fetch_starting_lineups(date=today)
            
            # Store the raw response for offline use if needed
            self._store_api_response(lineups, f'lineups_{today}.json')
            
            # Update today's games (to update scores and statuses)
            games = self.sports_data_service.fetch_games(date=today)
            
            logger.info(f"Updated {len(lineups)} lineups and {len(games)} game statuses")
            return True
        except Exception as e:
            logger.error(f"Error updating lineups and game statuses: {e}")
            return False
    
    def update_weather(self):
        """Update weather forecasts for upcoming games"""
        logger.info("Updating weather forecasts...")
        try:
            # Update weather for all upcoming games
            self.weather_service.update_all_game_weather(days_ahead=7)
            
            logger.info("Updated weather forecasts")
            return True
        except Exception as e:
            logger.error(f"Error updating weather forecasts: {e}")
            return False
    
    def update_odds(self):
        """Update betting odds"""
        logger.info("Updating odds...")
        try:
            # Update odds from all sources
            self.odds_service.update_all_odds()
            
            logger.info("Updated odds")
            return True
        except Exception as e:
            logger.error(f"Error updating odds: {e}")
            return False
    
    def generate_predictions(self):
        """Generate predictions for upcoming games"""
        logger.info("Generating predictions...")
        try:
            # Generate predictions for upcoming games
            count = self.prediction_engine.generate_all_predictions(days_ahead=3)
            
            logger.info(f"Generated {count} predictions")
            return True
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return False
    
    def _store_api_response(self, data, filename):
        """Store API response data to a JSON file for offline use if needed"""
        if not data:
            logger.warning(f"No data to store for {filename}")
            return
        
        try:
            # Create full path
            filepath = os.path.join(self.data_dir, filename)
            
            # Store data
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Stored API response to {filepath}")
        except Exception as e:
            logger.error(f"Error storing API response: {e}")