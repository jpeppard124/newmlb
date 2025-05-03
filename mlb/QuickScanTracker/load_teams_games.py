#!/usr/bin/env python3
from app import app, db
from models import Team, Game
from services.sportsdataio_service import SportsDataIOService
from datetime import datetime, timedelta
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_teams_and_games():
    """Load initial teams and upcoming games data from SportsDataIO"""
    with app.app_context():
        # Check if we need to initialize
        team_count = db.session.query(Team).count()
        
        service = SportsDataIOService()
        
        # Step 1: Load teams if needed
        if team_count == 0:
            logger.info("No teams found in the database, loading teams from SportsDataIO...")
            teams_data = service.fetch_teams()
            
            if teams_data:
                logger.info(f"Loaded {len(teams_data)} teams from SportsDataIO")
            else:
                logger.error("Failed to load teams from SportsDataIO")
                return False
        else:
            logger.info(f"Found {team_count} teams in the database")
        
        # Step 2: Load upcoming games for the next 7 days
        logger.info("Loading upcoming games for the next 7 days...")
        
        # Get today's date
        today = datetime.now().date()
        
        # Load games for each day
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime('%Y-%b-%d')
            
            logger.info(f"Loading games for {date_str}...")
            try:
                # Fetch games for this date
                games_data = service.fetch_games(date_str)
                
                if games_data:
                    logger.info(f"Loaded {len(games_data)} games for {date_str}")
                else:
                    logger.info(f"No games found for {date_str}")
            except Exception as e:
                logger.error(f"Error loading games for {date_str}: {e}")
        
        # Step 3: Check how many games we have in the database
        game_count = db.session.query(Game).count()
        logger.info(f"Total games in database: {game_count}")
        
        # Return success if we have teams and games
        return team_count > 0 and game_count > 0

if __name__ == "__main__":
    result = load_teams_and_games()
    if result:
        logger.info("Successfully loaded teams and games")
    else:
        logger.error("Failed to load teams and games")