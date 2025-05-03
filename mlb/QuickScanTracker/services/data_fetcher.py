import logging
import time
import requests
from datetime import datetime, timedelta
from config import Config
from app import db
from models import Game, Team, Odds, WeatherCondition, PlayerStats, UmpireStats

logger = logging.getLogger(__name__)

class DataFetcher:
    """Base class for data fetching services"""
    def __init__(self):
        self.config = Config
        
    def _make_request(self, url, params=None, headers=None, max_retries=3, retry_delay=2):
        """Make a request with retries and error handling"""
        attempt = 0
        while attempt < max_retries:
            try:
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                attempt += 1
                if attempt == max_retries:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Request attempt {attempt} failed: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    def _get_upcoming_games(self, days_ahead=7):
        """Get a list of upcoming MLB games for data fetching"""
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)
        
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date,
            Game.status == 'scheduled'
        ).all()
        
        return upcoming_games

    def _get_in_progress_games(self):
        """Get a list of in-progress MLB games for real-time updates"""
        return db.session.query(Game).filter(Game.status == 'in_progress').all()
    
    def _find_or_create_team(self, team_id, name, abbreviation):
        """Find an existing team or create a new one"""
        team = db.session.query(Team).filter_by(team_id=team_id).first()
        if not team:
            team = Team(team_id=team_id, name=name, abbreviation=abbreviation)
            db.session.add(team)
            db.session.commit()
        return team
    
    def _find_or_create_game(self, game_id, home_team_id, away_team_id, game_datetime, stadium):
        """Find an existing game or create a new one"""
        game = db.session.query(Game).filter_by(game_id=game_id).first()
        if not game:
            game = Game(
                game_id=game_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                game_datetime=game_datetime,
                stadium=stadium
            )
            db.session.add(game)
            db.session.commit()
        return game
