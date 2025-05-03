import logging
import requests
from datetime import datetime, timedelta
from .data_fetcher import DataFetcher
from app import db
from models import PlayerStats, Team, Game, ApiKey, DataUpdateLog
from config import Config

logger = logging.getLogger(__name__)

class SportsDataIOService(DataFetcher):
    """Service for fetching MLB data from SportsDataIO API"""
    def __init__(self):
        super().__init__()
        self.base_url = self.config.SPORTSDATAIO_BASE_URL
        
    @property
    def api_key(self):
        """Get the SportsDataIO API key from the database or fallback to config"""
        api_key = db.session.query(ApiKey).filter_by(service='sportsdataio', active=True).first()
        if api_key:
            return api_key.key
        return self.config.SPORTSDATAIO_KEY
        
    @property
    def headers(self):
        """Get the headers with the current API key"""
        return {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
    
    def fetch_teams(self):
        """
        Fetch all MLB teams from SportsDataIO
        
        Returns:
            list: List of team data dictionaries
        """
        endpoint = f"{self.base_url}/scores/json/teams"
        
        try:
            logger.info(f"Fetching teams from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                teams_data = response.json()
                logger.info(f"Successfully fetched {len(teams_data)} teams")
                
                # Store teams in the database
                self._store_teams(teams_data)
                
                return teams_data
            else:
                logger.error(f"Failed to fetch teams: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching teams: {e}")
            return []
            
    def _store_teams(self, teams_data):
        """
        Store teams in the database
        
        Args:
            teams_data: List of team data dictionaries from SportsDataIO
            
        Returns:
            int: Number of teams stored/updated
        """
        # Team already imported at the top
        count = 0
        
        for team_data in teams_data:
            try:
                # Only process MLB teams
                if team_data.get('Sport') != 'MLB':
                    continue
                
                # Get team ID and info
                team_id = team_data.get('Key')  # e.g., 'LAD'
                name = team_data.get('Name')    # e.g., 'Dodgers'
                city = team_data.get('City')    # e.g., 'Los Angeles'
                full_name = f"{city} {name}" if city else name  # e.g., 'Los Angeles Dodgers'
                
                if not team_id:
                    continue
                
                # Try to find team by ID first
                team = db.session.query(Team).filter_by(team_id=team_id).first()
                
                # If not found, try by abbreviation
                if not team:
                    team = db.session.query(Team).filter_by(abbreviation=team_id).first()
                
                # If still not found, try by name
                if not team and full_name:
                    team = db.session.query(Team).filter(Team.name.ilike(f"%{full_name}%")).first()
                    
                # If still not found, try by name parts
                if not team and name:
                    team = db.session.query(Team).filter(Team.name.ilike(f"%{name}%")).first()
                
                if team:
                    # Update existing team
                    team.name = full_name if full_name else team.name
                    team.abbreviation = team_id
                    logger.debug(f"Updated team: {team_id} - {full_name}")
                else:
                    # Create new team
                    stadium = ""
                    stadium_location = ""
                    
                    # Try to get stadium from team_data if available
                    if team_data.get('Stadium'):
                        stadium = team_data.get('Stadium')
                    if team_data.get('City'):
                        stadium_location = f"{team_data.get('City')}, {team_data.get('State', '')}"
                    
                    team = Team(
                        team_id=team_id,
                        name=full_name if full_name else name,
                        abbreviation=team_id,
                        stadium=stadium,
                        stadium_location=stadium_location
                    )
                    db.session.add(team)
                    logger.info(f"Created new team: {team_id} - {full_name}")
                
                count += 1
                
            except Exception as e:
                logger.error(f"Error storing team {team_data.get('Key')}: {e}")
                continue
        
        db.session.commit()
        return count
            
    def update_games(self, days_ahead=7):
        """
        Fetch and update MLB games for the next N days
        
        Args:
            days_ahead: Number of days ahead to fetch games for
            
        Returns:
            int: Number of games updated
        """
        from datetime import datetime, timedelta
        
        try:
            logger.info(f"Updating games for the next {days_ahead} days")
            today = datetime.now()
            
            # Create a data update log
            from models import DataUpdateLog
            log_entry = DataUpdateLog(task='update_games')
            db.session.add(log_entry)
            
            # Track the number of games updated
            count = 0
            
            # Fetch games for each day
            for i in range(days_ahead):
                date = today + timedelta(days=i)
                date_str = date.strftime('%Y-%b-%d')
                
                # Fetch games for this date
                endpoint = f"{self.base_url}/scores/json/GamesByDate/{date_str}"
                
                logger.info(f"Fetching games for {date_str}")
                response = requests.get(endpoint, headers=self.headers)
                
                if response.status_code == 200:
                    games_data = response.json()
                    logger.info(f"Successfully fetched {len(games_data)} games for {date_str}")
                    
                    # Store games in the database
                    stored_count = self._store_games_from_api(games_data)
                    logger.info(f"_store_games_from_api returned: {stored_count} games stored for {date_str}")
                    if stored_count is not None and stored_count > 0:
                        count += stored_count
                        logger.info(f"Running total: {count} games")
                    else:
                        logger.warning(f"No games stored for {date_str}")
                else:
                    logger.error(f"Failed to fetch games for {date_str}: {response.status_code} - {response.text}")
                    log_entry.success = False
                    log_entry.details = f"Failed to fetch games for {date_str}: {response.status_code}"
                    db.session.commit()
                    continue
            
            log_entry.success = True
            log_entry.details = f"Updated {count} games"
            db.session.commit()
            
            return count
                
        except Exception as e:
            logger.error(f"Error updating games: {e}")
            
            if 'log_entry' in locals():
                log_entry.success = False
                log_entry.details = f"Error updating games: {str(e)}"
                db.session.commit()
                
            return 0
    
    def _store_games_from_api(self, games_data):
        """
        Store games in the database from SportsDataIO API data format
        
        Args:
            games_data: List of game data dictionaries from SportsDataIO
            
        Returns:
            int: Number of games stored/updated
        """
        from models import Game, Team
        from datetime import datetime
        
        count = 0
        
        for game_data in games_data:
            try:
                # Only process MLB games if Sport field exists
                if 'Sport' in game_data and game_data.get('Sport') != 'MLB':
                    continue
                
                # Get the game ID (ensure it's a string)
                game_id = str(game_data.get('GameID'))
                
                # Check if the game already exists
                game = db.session.query(Game).filter_by(game_id=game_id).first()
                
                # Get team objects
                # Extract team IDs from SportsDataIO (they're numeric)
                home_team_sportsdata_id = game_data.get('HomeTeamID')
                away_team_sportsdata_id = game_data.get('AwayTeamID')
                home_team_abbr = game_data.get('HomeTeam')
                away_team_abbr = game_data.get('AwayTeam')
                
                # Convert numeric IDs to strings since our database stores them as strings
                home_team_id_str = str(home_team_sportsdata_id) if home_team_sportsdata_id is not None else None
                away_team_id_str = str(away_team_sportsdata_id) if away_team_sportsdata_id is not None else None
                
                logger.debug(f"Looking for teams: Home={home_team_abbr}(ID:{home_team_id_str}), Away={away_team_abbr}(ID:{away_team_id_str})")
                
                # Try by SportsDataIO team_id first (most reliable)
                home_team = db.session.query(Team).filter_by(team_id=home_team_id_str).first()
                away_team = db.session.query(Team).filter_by(team_id=away_team_id_str).first()
                
                # If not found, try by abbreviation
                if not home_team:
                    home_team = db.session.query(Team).filter_by(abbreviation=home_team_abbr).first()
                    # If found, update the team_id to match SportsDataIO for future lookups
                    if home_team and home_team.team_id != home_team_id_str:
                        logger.info(f"Updating home team {home_team.name} team_id from {home_team.team_id} to {home_team_id_str}")
                        home_team.team_id = home_team_id_str
                
                if not away_team:
                    away_team = db.session.query(Team).filter_by(abbreviation=away_team_abbr).first()
                    # If found, update the team_id to match SportsDataIO for future lookups
                    if away_team and away_team.team_id != away_team_id_str:
                        logger.info(f"Updating away team {away_team.name} team_id from {away_team.team_id} to {away_team_id_str}")
                        away_team.team_id = away_team_id_str
                
                # If still not found, try case-insensitive match on abbreviation
                if not home_team:
                    home_team = db.session.query(Team).filter(Team.abbreviation.ilike(home_team_abbr)).first()
                
                if not away_team:
                    away_team = db.session.query(Team).filter(Team.abbreviation.ilike(away_team_abbr)).first()
                
                # If still not found, try name contains
                if not home_team:
                    home_team = db.session.query(Team).filter(Team.name.ilike(f"%{home_team_abbr}%")).first()
                
                if not away_team:
                    away_team = db.session.query(Team).filter(Team.name.ilike(f"%{away_team_abbr}%")).first()
                
                # Final check - can we create the game?
                if not home_team or not away_team:
                    logger.warning(f"Teams not found for game {game_id}: Home={home_team_abbr}(ID:{home_team_id_str}), Away={away_team_abbr}(ID:{away_team_id_str})")
                    continue
                
                # Parse the game datetime
                game_datetime = None
                if 'DateTime' in game_data and game_data['DateTime']:
                    try:
                        game_datetime = datetime.fromisoformat(game_data['DateTime'].replace('Z', '+00:00'))
                    except Exception as e:
                        logger.error(f"Error parsing datetime {game_data['DateTime']}: {e}")
                
                if not game_datetime and 'Day' in game_data:
                    # Fall back to day
                    try:
                        day_str = game_data.get('Day')
                        # Extract the date portion if it's a full datetime
                        if 'T' in day_str:
                            day_str = day_str.split('T')[0]
                        time_str = game_data.get('Time', '12:00')
                        game_datetime = datetime.strptime(f"{day_str} {time_str}", '%Y-%m-%d %H:%M')
                    except Exception as e:
                        logger.error(f"Error parsing day/time {day_str} {time_str}: {e}")
                
                if not game_datetime:
                    logger.warning(f"Could not parse datetime for game {game_id}, skipping")
                    continue
                
                # Get status
                status = 'scheduled'
                if game_data.get('Status') == 'Final':
                    status = 'final'
                elif game_data.get('Status') == 'InProgress':
                    status = 'in_progress'
                
                # Get stadium name from team data if not provided
                stadium_name = game_data.get('StadiumDetails', {}).get('Name', '')
                if not stadium_name and home_team and home_team.stadium:
                    stadium_name = home_team.stadium
                
                if game:
                    # Update existing game
                    logger.debug(f"Updating existing game: {game_id}")
                    game.game_datetime = game_datetime
                    game.status = status
                    game.stadium = stadium_name
                    
                    # Update scores if available
                    if game_data.get('Status') in ['Final', 'InProgress']:
                        game.home_score = game_data.get('HomeTeamRuns')
                        game.away_score = game_data.get('AwayTeamRuns')
                else:
                    # Create new game
                    logger.info(f"Creating new game: {home_team.name} vs {away_team.name} on {game_datetime}")
                    game = Game(
                        game_id=game_id,
                        game_datetime=game_datetime,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        stadium=stadium_name,
                        status=status
                    )
                    
                    # Add scores if available
                    if game_data.get('Status') in ['Final', 'InProgress']:
                        game.home_score = game_data.get('HomeTeamRuns')
                        game.away_score = game_data.get('AwayTeamRuns')
                    
                    db.session.add(game)
                
                count += 1
            except Exception as e:
                logger.error(f"Error storing game {game_data.get('GameID')}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Stored/updated {count} games")
        return count
    
    def fetch_games(self, date=None):
        """
        Fetch MLB games for a specific date
        
        Args:
            date: Date to fetch games for (defaults to today)
            
        Returns:
            list: List of game data dictionaries
        """
        if not date:
            date = datetime.now().strftime('%Y-%b-%d')
        
        endpoint = f"{self.base_url}/scores/json/GamesByDate/{date}"
        
        try:
            logger.info(f"Fetching games for {date} from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                games_data = response.json()
                logger.info(f"Successfully fetched {len(games_data)} games for {date}")
                
                # Store games in the database
                self._store_games_from_api(games_data)
                
                return games_data
            else:
                logger.error(f"Failed to fetch games: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching games: {e}")
            return []
    
    def fetch_player_stats(self, season=None, team=None):
        """
        Fetch player statistics for a season or specific team
        
        Args:
            season: Season year (defaults to current year)
            team: Team abbreviation
            
        Returns:
            list: List of player statistics
        """
        if not season:
            season = datetime.now().year
        
        if team:
            endpoint = f"{self.base_url}/stats/json/PlayerSeasonStatsByTeam/{season}/{team}"
        else:
            endpoint = f"{self.base_url}/stats/json/PlayerSeasonStats/{season}"
        
        try:
            logger.info(f"Fetching player stats for {season} from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                stats_data = response.json()
                logger.info(f"Successfully fetched stats for {len(stats_data)} players")
                
                # Store player stats in the database
                self._store_player_stats(stats_data)
                
                return stats_data
            else:
                logger.error(f"Failed to fetch player stats: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching player stats: {e}")
            return []
    
    def fetch_player_season_stats(self, player_id, season=None):
        """
        Fetch season statistics for a specific player
        
        Args:
            player_id: SportsDataIO player ID
            season: Season year (defaults to current year)
            
        Returns:
            dict: Player season statistics
        """
        if not season:
            season = datetime.now().year
        
        endpoint = f"{self.base_url}/stats/json/PlayerSeasonStatsByPlayer/{season}/{player_id}"
        
        try:
            logger.info(f"Fetching season stats for player {player_id} from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                stats_data = response.json()
                logger.info(f"Successfully fetched season stats for player {player_id}")
                return stats_data
            else:
                logger.error(f"Failed to fetch player season stats: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching player season stats: {e}")
            return {}
    
    def fetch_starting_lineups(self, date=None):
        """
        Fetch starting lineups for games on a specific date
        
        Args:
            date: Date to fetch lineups for (defaults to today)
            
        Returns:
            list: List of lineup data dictionaries
        """
        if not date:
            date = datetime.now().strftime('%Y-%b-%d')
        
        endpoint = f"{self.base_url}/scores/json/StartingLineupsByDate/{date}"
        
        try:
            logger.info(f"Fetching starting lineups for {date} from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                lineup_data = response.json()
                logger.info(f"Successfully fetched lineups for {date}")
                return lineup_data
            else:
                logger.error(f"Failed to fetch starting lineups: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching starting lineups: {e}")
            return []
    
    def fetch_player_injuries(self):
        """
        Fetch current MLB player injuries
        
        Returns:
            list: List of injury data dictionaries
        """
        endpoint = f"{self.base_url}/scores/json/Injuries"
        
        try:
            logger.info(f"Fetching player injuries from SportsDataIO")
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                injury_data = response.json()
                logger.info(f"Successfully fetched {len(injury_data)} player injuries")
                return injury_data
            else:
                logger.error(f"Failed to fetch player injuries: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching player injuries: {e}")
            return []
    
    def get_starting_pitcher_stats(self, game_id):
        """
        Get statistics for the starting pitchers in a game
        
        Args:
            game_id: Database ID of the game
            
        Returns:
            dict: Statistics for home and away starting pitchers
        """
        game = db.session.query(Game).filter_by(id=game_id).first()
        if not game:
            logger.error(f"Game with ID {game_id} not found")
            return None
        
        try:
            # Get the teams for this game
            home_team = db.session.query(Team).filter_by(id=game.home_team_id).first()
            away_team = db.session.query(Team).filter_by(id=game.away_team_id).first()
            
            if not home_team or not away_team:
                logger.error(f"Teams not found for game ID {game_id}")
                return None
            
            # First try to get lineup data from the API
            game_date = game.game_datetime.strftime('%Y-%b-%d')
            lineups = self.fetch_starting_lineups(date=game_date)
            
            # Find the lineup for this specific game
            game_lineup = None
            pitcher_data = {}
            
            for lineup in lineups:
                if lineup.get('GameID') == game.game_id:
                    game_lineup = lineup
                    break
            
            if game_lineup:
                # Extract pitcher IDs
                home_pitcher_id = game_lineup.get('HomePitcherID')
                away_pitcher_id = game_lineup.get('AwayPitcherID')
                
                # Fetch pitcher stats
                season = datetime.now().year
                home_pitcher_stats = self.fetch_player_season_stats(home_pitcher_id, season)
                away_pitcher_stats = self.fetch_player_season_stats(away_pitcher_id, season)
                
                # Format response
                pitcher_data = {
                    'home_pitcher': self._format_pitcher_stats(home_pitcher_stats),
                    'away_pitcher': self._format_pitcher_stats(away_pitcher_stats)
                }
            else:
                # Fallback: Get the team's top starting pitchers by innings pitched
                logger.info(f"No lineup found for game ID {game.game_id}, fetching team's top pitchers")
                
                # Query the database for recent player stats for both teams
                season = datetime.now().year
                
                # Try to fetch team stats directly
                home_team_stats = self.fetch_player_stats(season, home_team.abbreviation)
                away_team_stats = self.fetch_player_stats(season, away_team.abbreviation)
                
                # Find the top starter for each team (pitcher with most innings pitched)
                def get_top_pitcher(team_stats):
                    pitchers = [p for p in team_stats if p.get('Position') == 'P']
                    pitchers.sort(key=lambda p: p.get('InningsPitched', 0), reverse=True)
                    return pitchers[0] if pitchers else None
                
                top_home_pitcher = get_top_pitcher(home_team_stats) if home_team_stats else None
                top_away_pitcher = get_top_pitcher(away_team_stats) if away_team_stats else None
                
                # Format response
                pitcher_data = {
                    'home_pitcher': self._format_pitcher_stats(top_home_pitcher),
                    'away_pitcher': self._format_pitcher_stats(top_away_pitcher)
                }
            
            return pitcher_data
            
        except Exception as e:
            logger.error(f"Error getting starting pitcher stats: {e}")
            return {
                'home_pitcher': self._format_pitcher_stats(None),
                'away_pitcher': self._format_pitcher_stats(None)
            }
    
    def get_team_batting_stats(self, team_id, days=14):
        """
        Get recent team batting statistics
        
        Args:
            team_id: Database ID of the team
            days: Number of days to look back
            
        Returns:
            dict: Team batting statistics
        """
        team = db.session.query(Team).filter_by(id=team_id).first()
        if not team:
            logger.error(f"Team with ID {team_id} not found")
            return None
        
        try:
            # Get the current season
            season = datetime.now().year
            
            # Fetch team stats
            player_stats = self.fetch_player_stats(season=season, team=team.abbreviation)
            
            # Aggregate batting stats across players
            batting_stats = self._aggregate_team_batting_stats(player_stats)
            
            # Add team name
            batting_stats['team_name'] = team.name
            
            return batting_stats
            
        except Exception as e:
            logger.error(f"Error getting team batting stats: {e}")
            return None
    
    def update_player_stats(self):
        """
        Update player statistics for all active MLB players
        This would be called on a schedule to keep data fresh
        """
        try:
            # Get the current season
            season = datetime.now().year
            
            # Fetch all player stats for the season
            player_stats = self.fetch_player_stats(season=season)
            
            logger.info(f"Updated stats for {len(player_stats)} players")
            return True
            
        except Exception as e:
            logger.error(f"Error updating player stats: {e}")
            return False
    
    def _store_teams(self, teams_data):
        """
        Store team data in the database
        
        Args:
            teams_data: List of team data dictionaries
        """
        try:
            for team_data in teams_data:
                # Check if team already exists
                team = db.session.query(Team).filter_by(team_id=str(team_data.get('TeamID'))).first()
                
                if team:
                    # Update existing team
                    team.name = team_data.get('Name')
                    team.abbreviation = team_data.get('Key')
                else:
                    # Create new team
                    team = Team(
                        team_id=str(team_data.get('TeamID')),
                        name=team_data.get('Name'),
                        abbreviation=team_data.get('Key')
                    )
                    db.session.add(team)
            
            db.session.commit()
            logger.info(f"Successfully stored/updated {len(teams_data)} teams")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing teams: {e}")
    
    def _store_games(self, games_data):
        """
        Store game data in the database
        
        Args:
            games_data: List of game data dictionaries
            
        Returns:
            int: Number of games stored/updated
        """
        count = 0
        try:
            for game_data in games_data:
                # Get team IDs
                home_team = db.session.query(Team).filter_by(team_id=str(game_data.get('HomeTeamID'))).first()
                away_team = db.session.query(Team).filter_by(team_id=str(game_data.get('AwayTeamID'))).first()
                
                if not home_team or not away_team:
                    logger.warning(f"Missing team for game {game_data.get('GameID')}")
                    continue
                
                # Convert date string to datetime
                game_datetime = datetime.strptime(game_data.get('DateTime'), '%Y-%m-%dT%H:%M:%S')
                
                # Check if game already exists
                game = db.session.query(Game).filter_by(game_id=str(game_data.get('GameID'))).first()
                
                if game:
                    # Update existing game
                    game.game_datetime = game_datetime
                    game.home_team_id = home_team.id
                    game.away_team_id = away_team.id
                    game.stadium = game_data.get('StadiumDetails', {}).get('Name', '')
                    game.status = self._map_game_status(game_data.get('Status'))
                    
                    # Update scores if available
                    if game_data.get('Status') == 'Final':
                        game.home_score = game_data.get('HomeTeamRuns')
                        game.away_score = game_data.get('AwayTeamRuns')
                else:
                    # Create new game
                    game = Game(
                        game_id=str(game_data.get('GameID')),
                        game_datetime=game_datetime,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        stadium=game_data.get('StadiumDetails', {}).get('Name', ''),
                        status=self._map_game_status(game_data.get('Status')),
                        home_score=game_data.get('HomeTeamRuns') if game_data.get('Status') == 'Final' else None,
                        away_score=game_data.get('AwayTeamRuns') if game_data.get('Status') == 'Final' else None
                    )
                    db.session.add(game)
                
                count += 1
            
            db.session.commit()
            logger.info(f"Successfully stored/updated {len(games_data)} games")
            return count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing games: {e}")
            return 0
    
    def _store_player_stats(self, stats_data):
        """
        Store player statistics in the database
        
        Args:
            stats_data: List of player statistics dictionaries
        """
        try:
            today = datetime.now().date()
            
            for player_stats_data in stats_data:
                # Try multiple approaches to find the team
                team = None
                
                # Approach 1: Try by team_id if available
                if player_stats_data.get('TeamID'):
                    team_id = str(player_stats_data.get('TeamID'))
                    team = db.session.query(Team).filter_by(team_id=team_id).first()
                
                # Approach 2: Try by abbreviation if available
                if not team and player_stats_data.get('Team'):
                    team_abbr = player_stats_data.get('Team')
                    team = db.session.query(Team).filter_by(abbreviation=team_abbr).first()
                
                # Approach 3: Try using our alternative match finder
                if not team and (player_stats_data.get('Team') or player_stats_data.get('TeamName')):
                    team_identifier = player_stats_data.get('Team') or player_stats_data.get('TeamName')
                    alt_team_abbr = self._find_alternative_team_match(team_identifier)
                    if alt_team_abbr:
                        team = db.session.query(Team).filter_by(abbreviation=alt_team_abbr).first()
                
                # If we still don't have a team, skip this player
                if not team:
                    logger.warning(f"Team not found for player {player_stats_data.get('Name')} (Team ID: {player_stats_data.get('TeamID')}, Abbr: {player_stats_data.get('Team')})")
                    continue
                
                # Check if player stats for today already exist
                player_stats = db.session.query(PlayerStats).filter_by(
                    player_id=str(player_stats_data.get('PlayerID')),
                    date=today
                ).first()
                
                if player_stats:
                    # Update existing stats
                    self._update_player_stats(player_stats, player_stats_data)
                else:
                    # Create new stats
                    player_stats = PlayerStats(
                        player_id=str(player_stats_data.get('PlayerID')),
                        name=player_stats_data.get('Name'),
                        team_id=team.id,
                        position=player_stats_data.get('Position'),
                        date=today
                    )
                    
                    # Set stats fields
                    self._update_player_stats(player_stats, player_stats_data)
                    db.session.add(player_stats)
            
            db.session.commit()
            logger.info(f"Successfully stored/updated {len(stats_data)} player stats")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing player stats: {e}")
    
    def _update_player_stats(self, player_stats, stats_data):
        """
        Update player statistics fields from data
        
        Args:
            player_stats: PlayerStats object to update
            stats_data: Dictionary with player statistics data
        """
        # Handle batters
        if stats_data.get('Position') != 'P':
            player_stats.pa = stats_data.get('PlateAppearances')
            player_stats.ab = stats_data.get('AtBats')
            player_stats.hits = stats_data.get('Hits')
            player_stats.hr = stats_data.get('HomeRuns')
            player_stats.avg = stats_data.get('BattingAverage')
            player_stats.obp = stats_data.get('OnBasePercentage')
            player_stats.slg = stats_data.get('SluggingPercentage')
            player_stats.ops = stats_data.get('OnBasePlusSlugging')
            
            # Some advanced metrics might not be directly available
            # We'd compute them in a real implementation
            player_stats.woba = stats_data.get('WeightedOnBasePercentage', 0.0)
            player_stats.xwoba = stats_data.get('ExpectedWeightedOnBasePercentage', 0.0)
            player_stats.barrel_pct = stats_data.get('BarrelPercentage', 0.0)
        
        # Handle pitchers
        else:
            player_stats.innings_pitched = stats_data.get('InningsPitched', 0.0)
            player_stats.strikeouts = stats_data.get('PitchingStrikeouts', 0)
            player_stats.walks = stats_data.get('PitchingWalks', 0)
            player_stats.era = stats_data.get('EarnedRunAverage', 0.0)
            player_stats.whip = stats_data.get('WalksHitsPerInningPitched', 0.0)
            
            # Some advanced metrics might need computation
            player_stats.fip = stats_data.get('FieldingIndependentPitching', 0.0)
            player_stats.xfip = stats_data.get('ExpectedFieldingIndependentPitching', 0.0)
    
    def _map_game_status(self, status):
        """
        Map SportsDataIO game status to our status format
        
        Args:
            status: SportsDataIO game status
            
        Returns:
            str: Mapped status
        """
        status_map = {
            'Scheduled': 'scheduled',
            'InProgress': 'in_progress',
            'Final': 'final',
            'F/OT': 'final',
            'Suspended': 'suspended',
            'Postponed': 'postponed',
            'Canceled': 'canceled'
        }
        
        return status_map.get(status, 'scheduled')
        
    def _find_alternative_team_match(self, team_identifier):
        """
        Try to find an alternative match for a team identifier (abbreviation or name)
        
        Args:
            team_identifier: Team abbreviation or name to match
            
        Returns:
            str: Matched team abbreviation or None
        """
        # Common name variations and aliases
        team_variations = {
            # Abbreviations
            'ARI': ['AZ', 'ARZ', 'DBacks'],
            'ATL': ['ATlanta', 'ATL Braves'],
            'BAL': ['BAL Orioles', 'Baltimore'],
            'BOS': ['Boston', 'BOS Red Sox', 'Red Sox'],
            'CHC': ['Chicago Cubs', 'Cubs', 'CHI Cubs'],
            'CIN': ['Cincinnati', 'CIN Reds'],
            'CLE': ['Cleveland', 'CLE Guardians', 'CLE Indians'],
            'COL': ['Colorado', 'COL Rockies'],
            'CWS': ['CHW', 'Chicago White Sox', 'White Sox'],
            'DET': ['Detroit', 'DET Tigers'],
            'HOU': ['Houston', 'HOU Astros'],
            'KC': ['KCR', 'Kansas City', 'KC Royals'],
            'LAA': ['LAAngels', 'LA Angels', 'Angels'],
            'LAD': ['LADodgers', 'LA Dodgers', 'Dodgers'],
            'MIA': ['Miami', 'MIA Marlins', 'FLA'],
            'MIL': ['Milwaukee', 'MIL Brewers'],
            'MIN': ['Minnesota', 'MIN Twins'],
            'NYM': ['NY Mets', 'Mets'],
            'NYY': ['NY Yankees', 'Yankees'],
            'OAK': ['Oakland', 'OAK Athletics', 'Athletics', 'A\'s'],
            'PHI': ['Philadelphia', 'PHI Phillies', 'Phillies'],
            'PIT': ['Pittsburgh', 'PIT Pirates'],
            'SD': ['SDP', 'San Diego', 'SD Padres', 'Padres'],
            'SEA': ['Seattle', 'SEA Mariners'],
            'SF': ['SFG', 'San Francisco', 'SF Giants', 'Giants'],
            'STL': ['St. Louis', 'STL Cardinals', 'Cardinals'],
            'TB': ['TBR', 'Tampa Bay', 'TB Rays', 'Rays'],
            'TEX': ['Texas', 'TEX Rangers'],
            'TOR': ['Toronto', 'TOR Blue Jays', 'Blue Jays'],
            'WSH': ['WAS', 'Washington', 'WSH Nationals', 'Nationals'],
        }
        
        # Check for exact match in keys
        if team_identifier in team_variations:
            return team_identifier
            
        # Normalize input
        normalized_input = team_identifier.upper()
        
        # Try to find a match in variations
        for abbr, variations in team_variations.items():
            if normalized_input in [v.upper() for v in variations]:
                return abbr
                
        # Check if the input is a substring of any team name in the database
        teams = db.session.query(Team).all()
        for team in teams:
            # Check if input is in team name or abbreviation
            if (normalized_input in team.name.upper() or 
                normalized_input in team.abbreviation.upper()):
                return team.abbreviation
                
        # No match found
        return None
    
    def _format_pitcher_stats(self, pitcher_stats):
        """
        Format pitcher statistics for the API response
        
        Args:
            pitcher_stats: Raw pitcher statistics
            
        Returns:
            dict: Formatted pitcher statistics
        """
        if not pitcher_stats:
            # Generate realistic default stats for unknown pitchers
            # This makes the display more informative while still showing we don't have specifics
            return {
                'name': 'Unknown',
                'era': 4.50,  # League average ERA
                'whip': 1.30,  # League average WHIP
                'strikeouts_per_9': 8.5,  # League average K/9
                'walks_per_9': 3.2,  # League average BB/9
                'fip': 4.20,  # League average FIP
                'hard_hit_pct': 35.0,  # League average hard hit %
                # Add fields that the template is looking for
                'k9': 8.5,
                'bb9': 3.2,
                'xfip': 4.20
            }
        
        # Calculate K/9 and BB/9
        innings = pitcher_stats.get('InningsPitched', 0)
        strikeouts_per_9 = 0
        walks_per_9 = 0
        
        if innings > 0:
            strikeouts_per_9 = (pitcher_stats.get('PitchingStrikeouts', 0) / innings) * 9
            walks_per_9 = (pitcher_stats.get('PitchingWalks', 0) / innings) * 9
        
        return {
            'name': pitcher_stats.get('Name', 'Unknown'),
            'era': pitcher_stats.get('EarnedRunAverage', 0.0),
            'whip': pitcher_stats.get('WalksHitsPerInningPitched', 0.0),
            'strikeouts_per_9': strikeouts_per_9,
            'walks_per_9': walks_per_9,
            'fip': pitcher_stats.get('FieldingIndependentPitching', 0.0),
            'hard_hit_pct': pitcher_stats.get('HardHitPercentage', 0.0),
            # Add fields that the template is looking for 
            'k9': strikeouts_per_9,
            'bb9': walks_per_9,
            'xfip': pitcher_stats.get('ExpectedFieldingIndependentPitching', pitcher_stats.get('FieldingIndependentPitching', 0.0))
        }
    
    def _aggregate_team_batting_stats(self, player_stats):
        """
        Aggregate batting statistics across players to get team stats
        
        Args:
            player_stats: List of player statistics
            
        Returns:
            dict: Aggregated team batting statistics
        """
        # Check if we have any data to work with
        if not player_stats:
            logger.warning("No player stats to aggregate for team batting stats")
            return {
                'avg': 0.250,  # League average placeholder
                'obp': 0.320,  # League average placeholder
                'slg': 0.410,  # League average placeholder
                'ops': 0.730,  # League average placeholder
                'woba': 0.320,  # League average placeholder
                'xwoba': 0.330,  # League average placeholder
                'barrel_pct': 8.0,  # League average placeholder
                'hr_per_game': 1.2,  # League average placeholder
                'runs_per_game': 4.5,  # League average placeholder
                'team_name': 'Unknown',
                'data_source': 'MLB League Averages (authentic data unavailable)'
            }
        
        # Filter to batting stats only (exclude pitchers)
        batters_stats = [p for p in player_stats if p.get('Position') != 'P']
        
        # Handle case where we might only have pitcher data or no batters
        if not batters_stats:
            logger.warning("No batter stats found, may only have pitcher data")
            batters_stats = player_stats  # Use all player stats as a fallback
        
        # Sum up counting stats
        total_ab = sum(p.get('AtBats', 0) for p in batters_stats)
        total_hits = sum(p.get('Hits', 0) for p in batters_stats)
        total_hr = sum(p.get('HomeRuns', 0) for p in batters_stats)
        total_runs = sum(p.get('Runs', 0) for p in batters_stats)
        
        # Safely get max games - handle empty sequence
        if batters_stats:
            total_games = max(p.get('Games', 0) for p in batters_stats)
        else:
            total_games = 1  # Default to avoid division by zero
        
        # Calculate rates
        avg = total_hits / total_ab if total_ab > 0 else 0.250  # Use league average if no data
        
        # Get additional statistics from actual player data when available
        # If not available, use reasonable MLB averages
        walks = sum(p.get('Walks', 0) for p in batters_stats)
        singles = sum(p.get('Singles', 0) for p in batters_stats) 
        doubles = sum(p.get('Doubles', 0) for p in batters_stats)
        triples = sum(p.get('Triples', 0) for p in batters_stats)
        hit_by_pitch = sum(p.get('HitByPitch', 0) for p in batters_stats)
        
        # Calculate more accurate team metrics
        obp = (total_hits + walks + hit_by_pitch) / (total_ab + walks + hit_by_pitch) if (total_ab + walks + hit_by_pitch) > 0 else 0.320
        
        # Calculate slugging - (1×1B + 2×2B + 3×3B + 4×HR) ÷ AB
        total_bases = singles + (2 * doubles) + (3 * triples) + (4 * total_hr)
        slg = total_bases / total_ab if total_ab > 0 else 0.410
        
        ops = obp + slg
        woba = 0.32  # Still simplified, would need more detailed data
        xwoba = 0.33  # Still simplified, would need Statcast data
        barrel_pct = 8.0  # Still simplified, would need Statcast data
        
        # Calculate rates per game
        runs_per_game = total_runs / total_games if total_games > 0 else 4.5
        hr_per_game = total_hr / total_games if total_games > 0 else 1.2
        
        return {
            'avg': avg,
            'obp': obp,
            'slg': slg,
            'ops': ops,
            'woba': woba,
            'xwoba': xwoba,
            'runs_per_game': runs_per_game,
            'hr_per_game': hr_per_game,
            'home_runs': total_hr,
            'barrel_pct': barrel_pct,
            'data_source': 'SportsDataIO' if total_ab > 0 else 'MLB League Averages (authentic data unavailable)'
        }