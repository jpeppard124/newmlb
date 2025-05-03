#!/usr/bin/env python3
from app import app, db
from models import Team, Game
from services.sportsdataio_service import SportsDataIOService
from datetime import datetime
import logging
import json
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_sportsdataio_service():
    """Debug and fix issues with SportsDataIO service"""
    with app.app_context():
        service = SportsDataIOService()
        
        # Step 1: Get today's date formatted as required by the API
        today = datetime.now().strftime('%Y-%b-%d')
        logger.info(f"Using date format: {today}")
        
        # Step 2: Fetch raw game data from the API for manual processing
        endpoint = f"{service.base_url}/scores/json/GamesByDate/{today}"
        logger.info(f"Fetching games from endpoint: {endpoint}")
        
        try:
            response = requests.get(endpoint, headers=service.headers)
            if response.status_code == 200:
                games_data = response.json()
                logger.info(f"Fetched {len(games_data)} games")
                
                if not games_data:
                    logger.info("No games found for today")
                    return
                
                # Process the first game as an example
                first_game = games_data[0]
                logger.info(f"Sample game: {json.dumps(first_game, indent=2)}")
                
                # Extract team IDs
                home_team_id = str(first_game.get('HomeTeamID'))
                away_team_id = str(first_game.get('AwayTeamID'))
                home_team_abbr = first_game.get('HomeTeam')
                away_team_abbr = first_game.get('AwayTeam')
                game_id = first_game.get('GameID')
                
                logger.info(f"Game ID: {game_id}")
                logger.info(f"Home team: ID={home_team_id}, Abbr={home_team_abbr}")
                logger.info(f"Away team: ID={away_team_id}, Abbr={away_team_abbr}")
                
                # Find home team
                home_team = db.session.query(Team).filter_by(team_id=home_team_id).first()
                if not home_team:
                    home_team = db.session.query(Team).filter_by(abbreviation=home_team_abbr).first()
                
                # Find away team
                away_team = db.session.query(Team).filter_by(team_id=away_team_id).first()
                if not away_team:
                    away_team = db.session.query(Team).filter_by(abbreviation=away_team_abbr).first()
                
                logger.info(f"Home team found: {home_team.name if home_team else 'Not found'}")
                logger.info(f"Away team found: {away_team.name if away_team else 'Not found'}")
                
                if not home_team or not away_team:
                    logger.error("Could not find teams for this game")
                    
                    # Attempt to update team_id field for teams if needed
                    all_teams = db.session.query(Team).all()
                    logger.info(f"All teams in database ({len(all_teams)}):")
                    for team in all_teams:
                        logger.info(f"  {team.id}: {team.name}, team_id={team.team_id}, abbr={team.abbreviation}")
                        
                        # Check if we can update the team's ID to match SportsDataIO
                        if team.abbreviation == home_team_abbr and not home_team:
                            logger.info(f"Updating team_id for {team.name} from {team.team_id} to {home_team_id}")
                            team.team_id = home_team_id
                            home_team = team
                            
                        if team.abbreviation == away_team_abbr and not away_team:
                            logger.info(f"Updating team_id for {team.name} from {team.team_id} to {away_team_id}")
                            team.team_id = away_team_id
                            away_team = team
                    
                    db.session.commit()
                    logger.info("Team IDs updated")
                
                # Check if we have both teams now
                if not home_team or not away_team:
                    logger.error("Still missing team(s) for this game - cannot create")
                    return
                
                # Parse game datetime
                game_datetime = None
                if 'DateTime' in first_game and first_game['DateTime']:
                    try:
                        game_datetime = datetime.fromisoformat(first_game['DateTime'].replace('Z', '+00:00'))
                        logger.info(f"Parsed datetime: {game_datetime}")
                    except Exception as e:
                        logger.error(f"Error parsing datetime: {e}")
                        # Fall back to day
                        day_str = first_game.get('Day')
                        time_str = first_game.get('Time', '12:00')
                        logger.info(f"Falling back to day: {day_str}, time: {time_str}")
                        game_datetime = datetime.strptime(f"{day_str} {time_str}", '%Y-%m-%d %H:%M')
                
                if not game_datetime:
                    logger.error("Could not parse game datetime")
                    return
                
                # Determine status
                status = 'scheduled'
                if first_game.get('Status') == 'Final':
                    status = 'final'
                elif first_game.get('Status') == 'InProgress':
                    status = 'in_progress'
                    
                logger.info(f"Game status: {status}")
                
                # Check if game already exists
                existing_game = db.session.query(Game).filter_by(game_id=str(game_id)).first()
                if existing_game:
                    logger.info(f"Game already exists with ID {game_id}")
                    
                    # Update fields if needed
                    existing_game.game_datetime = game_datetime
                    existing_game.status = status
                    
                    # Update scores if available
                    if first_game.get('Status') in ['Final', 'InProgress']:
                        existing_game.home_score = first_game.get('HomeTeamRuns')
                        existing_game.away_score = first_game.get('AwayTeamRuns')
                        logger.info(f"Updated scores: Home={existing_game.home_score}, Away={existing_game.away_score}")
                    
                    db.session.commit()
                    logger.info("Game updated successfully")
                else:
                    # Create new game
                    new_game = Game(
                        game_id=str(game_id),
                        game_datetime=game_datetime,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        stadium=home_team.stadium,
                        status=status
                    )
                    
                    # Add scores if available
                    if first_game.get('Status') in ['Final', 'InProgress']:
                        new_game.home_score = first_game.get('HomeTeamRuns')
                        new_game.away_score = first_game.get('AwayTeamRuns')
                        logger.info(f"Set scores: Home={new_game.home_score}, Away={new_game.away_score}")
                    
                    db.session.add(new_game)
                    db.session.commit()
                    logger.info(f"New game created: {home_team.name} vs {away_team.name} on {game_datetime}")
                    
                    # Verify it was saved
                    check_game = db.session.query(Game).filter_by(game_id=str(game_id)).first()
                    if check_game:
                        logger.info(f"Game saved successfully with ID: {check_game.id}")
                    else:
                        logger.error("Game save verification failed!")
                
                # Now attempt to properly fix the SportsDataIO service team matching issue
                logger.info("\nFixing SportsDataIO service to correctly match teams...")
                
                # Try to process all games properly
                count = 0
                for game_data in games_data:
                    try:
                        # Extract team IDs as strings
                        game_id = str(game_data.get('GameID'))
                        home_team_id = str(game_data.get('HomeTeamID'))
                        away_team_id = str(game_data.get('AwayTeamID'))
                        
                        # Find teams
                        home_team = db.session.query(Team).filter_by(team_id=home_team_id).first()
                        away_team = db.session.query(Team).filter_by(team_id=away_team_id).first()
                        
                        if not home_team or not away_team:
                            # Try by abbreviation
                            home_team_abbr = game_data.get('HomeTeam')
                            away_team_abbr = game_data.get('AwayTeam')
                            
                            if not home_team:
                                home_team = db.session.query(Team).filter_by(abbreviation=home_team_abbr).first()
                                
                            if not away_team:
                                away_team = db.session.query(Team).filter_by(abbreviation=away_team_abbr).first()
                        
                        if not home_team or not away_team:
                            logger.info(f"Skipping game {game_id}: Missing team(s)")
                            continue
                            
                        # Parse datetime
                        if 'DateTime' in game_data and game_data['DateTime']:
                            game_datetime = datetime.fromisoformat(game_data['DateTime'].replace('Z', '+00:00'))
                        else:
                            day_str = game_data.get('Day')
                            time_str = game_data.get('Time', '12:00')
                            game_datetime = datetime.strptime(f"{day_str} {time_str}", '%Y-%m-%d %H:%M')
                            
                        # Determine status
                        status = 'scheduled'
                        if game_data.get('Status') == 'Final':
                            status = 'final'
                        elif game_data.get('Status') == 'InProgress':
                            status = 'in_progress'
                            
                        # Check if game already exists
                        existing_game = db.session.query(Game).filter_by(game_id=game_id).first()
                        if existing_game:
                            # Update fields
                            existing_game.game_datetime = game_datetime
                            existing_game.status = status
                            
                            # Update scores if available
                            if game_data.get('Status') in ['Final', 'InProgress']:
                                existing_game.home_score = game_data.get('HomeTeamRuns')
                                existing_game.away_score = game_data.get('AwayTeamRuns')
                        else:
                            # Create new game
                            new_game = Game(
                                game_id=game_id,
                                game_datetime=game_datetime,
                                home_team_id=home_team.id,
                                away_team_id=away_team.id,
                                stadium=home_team.stadium or '',
                                status=status
                            )
                            
                            # Add scores if available
                            if game_data.get('Status') in ['Final', 'InProgress']:
                                new_game.home_score = game_data.get('HomeTeamRuns')
                                new_game.away_score = game_data.get('AwayTeamRuns')
                                
                            db.session.add(new_game)
                            
                        count += 1
                    except Exception as e:
                        logger.error(f"Error processing game {game_data.get('GameID')}: {e}")
                        continue
                
                db.session.commit()
                logger.info(f"Successfully processed {count} games")
                
            else:
                logger.error(f"Failed to fetch games: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error: {e}")

if __name__ == "__main__":
    fix_sportsdataio_service()