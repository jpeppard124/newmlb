import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pybaseball
from .data_fetcher import DataFetcher
from app import db
from models import PlayerStats, Team, Game, DataUpdateLog
from config import Config

logger = logging.getLogger(__name__)

class StatcastService(DataFetcher):
    """Service for fetching advanced baseball statistics from Statcast via pybaseball"""
    def __init__(self):
        super().__init__()
        self.config = Config()
        
    def update_player_stats_with_statcast(self, days_back=30):
        """
        Fetch Statcast data and update player statistics with advanced metrics
        
        Args:
            days_back: Number of days of data to fetch (default: 30)
            
        Returns:
            bool: Whether the update was successful
        """
        try:
            logger.info(f"Fetching Statcast data for last {days_back} days")
            
            # Calculate date range for data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates as strings for pybaseball (YYYY-MM-DD)
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # Fetch Statcast data for all players in date range
            statcast_data = self._fetch_statcast_data(start_str, end_str)
            if statcast_data is None or statcast_data.empty:
                logger.warning("No Statcast data retrieved")
                return False
                
            # Process and store the data
            success = self._process_statcast_data(statcast_data)
            
            # Log the update
            self._log_update(success, f"Updated Statcast data for {start_str} to {end_str}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating Statcast data: {e}")
            self._log_update(False, f"Error updating Statcast data: {e}")
            return False
    
    def _fetch_statcast_data(self, start_date, end_date):
        """
        Fetch Statcast data for a date range
        
        Args:
            start_date: Start date string in YYYY-MM-DD format
            end_date: End date string in YYYY-MM-DD format
            
        Returns:
            pandas.DataFrame: Statcast data
        """
        try:
            logger.info(f"Fetching Statcast data from {start_date} to {end_date}")
            
            # Use pybaseball to fetch Statcast data
            # This may take some time for large date ranges
            df = pybaseball.statcast(start_dt=start_date, end_dt=end_date)
            
            if df is None or df.empty:
                logger.warning("No data returned from Statcast")
                return None
                
            logger.info(f"Successfully fetched {len(df)} Statcast events")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching Statcast data: {e}")
            return None
    
    def _process_statcast_data(self, df):
        """
        Process Statcast data and update player statistics
        
        Args:
            df: pandas.DataFrame containing Statcast data
            
        Returns:
            bool: Whether the update was successful
        """
        try:
            # We'll need to group this data by player
            player_stats = self._aggregate_player_stats(df)
            
            # Update the database with this new data
            updated_count = 0
            for player_id, stats in player_stats.items():
                # Get the player's team
                team = self._get_team_by_mlb_id(stats.get('team', ''))
                
                # Update player stats in the database
                if team:
                    success = self._update_player_stats(
                        player_id=player_id,
                        name=stats.get('name', ''),
                        team_id=team.id,
                        stats=stats
                    )
                    if success:
                        updated_count += 1
            
            logger.info(f"Updated Statcast metrics for {updated_count} players")
            return True
            
        except Exception as e:
            logger.error(f"Error processing Statcast data: {e}")
            return False
    
    def _aggregate_player_stats(self, df):
        """
        Aggregate Statcast data by player
        
        Args:
            df: pandas.DataFrame containing Statcast data
            
        Returns:
            dict: Dictionary of player stats by player ID
        """
        try:
            # Group by player
            player_stats = {}
            
            # Process batters
            batters = df.groupby('batter')
            
            for batter_id, group in batters:
                if pd.isna(batter_id):
                    continue
                    
                # Get player name
                player_names = group['player_name'].unique()
                player_name = player_names[0] if len(player_names) > 0 else ''
                
                # Get player team
                teams = group['batting_team'].unique()
                team = teams[0] if len(teams) > 0 else ''
                
                # Count total batted ball events
                batted_ball_events = group[group['type'] == 'X']
                total_events = len(batted_ball_events)
                
                if total_events > 0:
                    # Calculate exit velocity (when available)
                    exit_velo = batted_ball_events['launch_speed'].mean()
                    
                    # Calculate barrel percent
                    barrels = len(batted_ball_events[batted_ball_events['launch_speed_angle'] >= 6])
                    barrel_pct = barrels / total_events * 100 if total_events > 0 else 0
                    
                    # Calculate expected weighted on-base average (xwOBA)
                    # This is a complex metric that requires the xwOBA values from Statcast
                    xwoba_values = batted_ball_events['estimated_woba_using_speedangle'].dropna()
                    xwoba = xwoba_values.mean() if len(xwoba_values) > 0 else None
                    
                    # Store player stats
                    player_stats[str(int(batter_id))] = {
                        'name': player_name,
                        'team': team,
                        'exit_velocity': exit_velo,
                        'barrel_pct': barrel_pct,
                        'xwoba': xwoba,
                        'total_batted_ball_events': total_events
                    }
            
            # Process pitchers (add advanced pitching metrics)
            pitchers = df.groupby('pitcher')
            
            for pitcher_id, group in pitchers:
                if pd.isna(pitcher_id):
                    continue
                    
                # Get player name
                player_names = group['player_name'].unique()
                player_name = player_names[0] if len(player_names) > 0 else ''
                
                # Get player team
                teams = group['pitching_team'].unique()
                team = teams[0] if len(teams) > 0 else ''
                
                # Count total pitching events
                total_events = len(group)
                
                if total_events > 0:
                    # Calculate advanced pitching metrics
                    # Average spin rate
                    spin_rate_values = group['release_spin_rate'].dropna()
                    avg_spin_rate = spin_rate_values.mean() if len(spin_rate_values) > 0 else None
                    
                    # Average velocity
                    velo_values = group['release_speed'].dropna()
                    avg_velo = velo_values.mean() if len(velo_values) > 0 else None
                    
                    # Expected weighted on-base average (xwOBA) against
                    xwoba_values = group['estimated_woba_using_speedangle'].dropna()
                    xwoba_against = xwoba_values.mean() if len(xwoba_values) > 0 else None
                    
                    # Store pitcher stats
                    pitcher_stats = {
                        'name': player_name,
                        'team': team,
                        'avg_spin_rate': avg_spin_rate,
                        'avg_velocity': avg_velo,
                        'xwoba_against': xwoba_against,
                        'total_pitching_events': total_events
                    }
                    
                    # If we already have this player as a batter, merge the stats
                    player_id = str(int(pitcher_id))
                    if player_id in player_stats:
                        player_stats[player_id].update(pitcher_stats)
                    else:
                        # Otherwise, add new pitcher entry
                        player_stats[player_id] = pitcher_stats
            
            return player_stats
            
        except Exception as e:
            logger.error(f"Error aggregating player stats from Statcast: {e}")
            return {}
    
    def _update_player_stats(self, player_id, name, team_id, stats):
        """
        Update player statistics in the database with Statcast data
        
        Args:
            player_id: MLB player ID
            name: Player name
            team_id: Database team ID
            stats: Dictionary of player statistics
            
        Returns:
            bool: Whether the update was successful
        """
        try:
            # Find existing player stats record
            player_stat = db.session.query(PlayerStats).filter_by(
                player_id=player_id,
                team_id=team_id,
                date=datetime.now().date()
            ).first()
            
            # Create new record if not found
            if not player_stat:
                player_stat = PlayerStats(
                    player_id=player_id,
                    name=name,
                    team_id=team_id,
                    date=datetime.now().date()
                )
                db.session.add(player_stat)
            
            # Update with Statcast metrics
            if 'exit_velocity' in stats and stats['exit_velocity'] is not None:
                player_stat.exit_velocity = float(stats['exit_velocity'])
                
            if 'barrel_pct' in stats and stats['barrel_pct'] is not None:
                player_stat.barrel_pct = float(stats['barrel_pct'])
                
            if 'xwoba' in stats and stats['xwoba'] is not None:
                player_stat.xwoba = float(stats['xwoba'])
                
            if 'avg_spin_rate' in stats and stats['avg_spin_rate'] is not None:
                player_stat.avg_spin_rate = float(stats['avg_spin_rate'])
                
            if 'avg_velocity' in stats and stats['avg_velocity'] is not None:
                player_stat.avg_velocity = float(stats['avg_velocity'])
                
            if 'xwoba_against' in stats and stats['xwoba_against'] is not None:
                player_stat.xwoba_against = float(stats['xwoba_against'])
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating player stats with Statcast data: {e}")
            return False
    
    def _get_team_by_mlb_id(self, team_abbrev):
        """
        Find team by MLB team abbreviation
        
        Args:
            team_abbrev: MLB team abbreviation
            
        Returns:
            Team or None: Database team object or None if not found
        """
        try:
            # Convert MLB team abbreviation to database team
            team_mapping = {
                'ARI': 'Diamondbacks',
                'ATL': 'Braves',
                'BAL': 'Orioles',
                'BOS': 'Red Sox',
                'CHC': 'Cubs',
                'CIN': 'Reds',
                'CLE': 'Guardians',
                'COL': 'Rockies',
                'CWS': 'White Sox',
                'DET': 'Tigers',
                'HOU': 'Astros',
                'KC': 'Royals',
                'LAA': 'Angels',
                'LAD': 'Dodgers',
                'MIA': 'Marlins',
                'MIL': 'Brewers',
                'MIN': 'Twins',
                'NYM': 'Mets',
                'NYY': 'Yankees',
                'OAK': 'Athletics',
                'PHI': 'Phillies',
                'PIT': 'Pirates',
                'SD': 'Padres',
                'SEA': 'Mariners',
                'SF': 'Giants',
                'STL': 'Cardinals',
                'TB': 'Rays',
                'TEX': 'Rangers',
                'TOR': 'Blue Jays',
                'WSH': 'Nationals'
            }
            
            # Look up team name from abbreviation
            team_name = team_mapping.get(team_abbrev)
            
            if team_name:
                # Query the database for the team
                team = db.session.query(Team).filter(Team.name.like(f'%{team_name}%')).first()
                return team
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding team by MLB ID: {e}")
            return None
    
    def _log_update(self, success, details):
        """
        Log a data update operation
        
        Args:
            success: Whether the update was successful
            details: Details or error message
        """
        try:
            log_entry = DataUpdateLog(
                task='update_statcast',
                success=success,
                details=details
            )
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error logging Statcast update: {e}")
    
    def fetch_player_statcast_data(self, player_id, days_back=30):
        """
        Fetch detailed Statcast data for a specific player
        
        Args:
            player_id: MLB player ID
            days_back: Number of days of data to fetch (default: 30)
            
        Returns:
            pandas.DataFrame: Player's Statcast data
        """
        try:
            # Calculate date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates for pybaseball
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"Fetching Statcast data for player {player_id} from {start_str} to {end_str}")
            
            # Fetch player data directly
            # This requires player's last name, first name and player ID
            # We can look up the player's name in our database first
            player = db.session.query(PlayerStats).filter_by(player_id=player_id).first()
            
            if player:
                name_parts = player.name.split(', ', 1)
                if len(name_parts) >= 2:
                    last_name, first_name = name_parts
                    
                    # Use pybaseball to fetch player-specific data
                    player_data = pybaseball.statcast_batter(start_dt=start_str, end_dt=end_str, player_id=int(player_id))
                    
                    if player_data is not None and not player_data.empty:
                        logger.info(f"Successfully fetched {len(player_data)} Statcast events for player {player_id}")
                        return player_data
            
            logger.warning(f"No player data found for ID {player_id} or no Statcast data available")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching player Statcast data: {e}")
            return None