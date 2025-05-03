#!/usr/bin/env python3
import logging
from app import app, db
from models import Game, Team, Prediction
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_routes():
    """Debug route issues to identify why games aren't displaying"""
    with app.app_context():
        try:
            # Check if we have any games in the database
            all_games = db.session.query(Game).all()
            logger.info(f"Total games in database: {len(all_games)}")
            
            # Try fetching upcoming games with the exact same logic as the route
            today = datetime.now().date()
            days_ahead = 7  # Show games for the next week
            
            upcoming_games = db.session.query(Game).filter(
                Game.game_datetime >= datetime.now(),
                Game.game_datetime < datetime.now() + timedelta(days=days_ahead),
                Game.status != 'final'
            ).order_by(Game.game_datetime).all()
            
            logger.info(f"Found {len(upcoming_games)} upcoming games with new query")
            
            # Show details of first 5 games
            for i, game in enumerate(upcoming_games[:5]):
                logger.info(f"{i+1}. {game.away_team.name} @ {game.home_team.name} - {game.game_datetime}")
                logger.info(f"   Game ID: {game.id}, API Game ID: {game.game_id}")
                logger.info(f"   Status: {game.status}, Stadium: {game.stadium}")
                
            # Check for any games not being pulled by filter
            other_games = db.session.query(Game).filter(
                ~Game.id.in_([g.id for g in upcoming_games])
            ).all()
            
            logger.info(f"Found {len(other_games)} other games not matching filter")
            for i, game in enumerate(other_games[:5]):
                logger.info(f"{i+1}. {game.away_team.name} @ {game.home_team.name} - {game.game_datetime}")
                logger.info(f"   Game ID: {game.id}, API Game ID: {game.game_id}")
                logger.info(f"   Status: {game.status}, Stadium: {game.stadium}")
                
            # Check for any errors in game template relationships
            try:
                for game in upcoming_games[:5]:
                    # Access related objects to see if they raise errors
                    logger.info(f"Checking relations for game {game.id}")
                    logger.info(f"Home team: {game.home_team.name}")
                    logger.info(f"Away team: {game.away_team.name}")
            except Exception as e:
                logger.error(f"Error accessing game relations: {e}")
                
            # Check template filters
            from app import format_date, format_time
            for game in upcoming_games[:2]:
                try:
                    logger.info(f"Testing template filters:")
                    logger.info(f"Date: {format_date(game.game_datetime)}")
                    logger.info(f"Time: {format_time(game.game_datetime)}")
                except Exception as e:
                    logger.error(f"Error with template filters: {e}")
                    
            return {
                "total_games": len(all_games),
                "upcoming_games": len(upcoming_games),
                "other_games": len(other_games)
            }
            
        except Exception as e:
            logger.error(f"Error debugging routes: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    results = debug_routes()
    logger.info(f"Debug results: {results}")