"""
Player Statistics Service for retrieving and ensuring player stats data completeness
"""

import logging
from datetime import datetime, timedelta
from app import db
from models import Game, PlayerStats, Team, DataUpdateLog
from .data_service_interface import DataServiceInterface

logger = logging.getLogger(__name__)

class PlayerStatsService(DataServiceInterface):
    """Service for managing player statistics data"""
    
    def __init__(self):
        super().__init__()
    
    def ensure_data(self, days_ahead=7):
        """
        Ensure all games have proper player statistics data
        
        This is automatically called by the data integrity system.
        
        Args:
            days_ahead: Number of days in the future to check
            
        Returns:
            bool: Whether the check was successful
        """
        with db.session.no_autoflush:
            logger.info("Checking player statistics data completeness")
            
            # Find games that need player stats
            games_needing_stats = self._find_games_needing_stats(days_ahead)
            
            if not games_needing_stats:
                logger.info("All games have complete player statistics")
                return True
                
            logger.info(f"Found {len(games_needing_stats)} games needing player statistics")
            
            # Update stats for each game
            updated_count = 0
            for game in games_needing_stats:
                try:
                    # Here you would call your real data source to get player stats
                    stats_updated = self._update_player_stats_for_game(game)
                    if stats_updated:
                        updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating player stats for game {game.id}: {e}")
            
            # Log the update
            self._log_update('update_player_stats', updated_count > 0, 
                           f"Updated player statistics for {updated_count} of {len(games_needing_stats)} games")
            
            return updated_count > 0
    
    def _find_games_needing_stats(self, days_ahead):
        """Find games that need player statistics updated"""
        today = datetime.now()
        end_date = today + timedelta(days=days_ahead)
        
        # Find upcoming games
        upcoming_games = db.session.query(Game).filter(
            Game.game_datetime >= today,
            Game.game_datetime <= end_date
        ).all()
        
        # Check which games need player stats
        games_needing_stats = []
        for game in upcoming_games:
            # In a real implementation, you would check if player stats are missing or outdated
            # This is just a placeholder for demonstration
            # In reality, you would query the PlayerStats table with game_id or player/team/date
            games_needing_stats.append(game)
            
        return games_needing_stats
    
    def _update_player_stats_for_game(self, game):
        """
        Update player statistics for a game by fetching real data from SportsDataIO
        
        Args:
            game: Game object to update stats for
            
        Returns:
            bool: Whether the update was successful
        """
        try:
            logger.info(f"Updating player stats for game {game.id}")
            
            # Use SportsDataIO service to fetch real player stats
            from services.sportsdataio_service import SportsDataIOService
            sportsdataio = SportsDataIOService()
            
            # Get the current year
            year = game.game_datetime.year
            
            # Fetch stats for home team
            home_stats_updated = False
            if game.home_team:
                logger.info(f"Fetching player stats for {game.home_team.name}")
                
                # Use the real API to fetch player stats for this team
                home_team_stats = sportsdataio.fetch_player_stats_by_team(
                    year, 
                    game.home_team.abbreviation
                )
                
                if home_team_stats:
                    home_stats_updated = True
                    logger.info(f"Successfully updated player stats for {len(home_team_stats)} players on {game.home_team.name}")
            
            # Fetch stats for away team
            away_stats_updated = False
            if game.away_team:
                logger.info(f"Fetching player stats for {game.away_team.name}")
                
                # Use the real API to fetch player stats for this team
                away_team_stats = sportsdataio.fetch_player_stats_by_team(
                    year, 
                    game.away_team.abbreviation
                )
                
                if away_team_stats:
                    away_stats_updated = True
                    logger.info(f"Successfully updated player stats for {len(away_team_stats)} players on {game.away_team.name}")
            
            # Also fetch any available starting lineups or probable pitchers
            lineup_updated = sportsdataio.fetch_starting_lineups_for_game(game)
            
            # Overall success if any component was updated
            return home_stats_updated or away_stats_updated or lineup_updated
            
        except Exception as e:
            logger.error(f"Error updating player stats for game {game.id}: {e}")
            return False