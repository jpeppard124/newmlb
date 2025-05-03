#!/usr/bin/env python3
from app import app, db
from models import Team
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_teams():
    """Check team data stored in the database"""
    with app.app_context():
        teams = db.session.query(Team).order_by(Team.name).all()
        
        logger.info(f"Found {len(teams)} teams in database:")
        for team in teams:
            logger.info(f"{team.abbreviation}: {team.name} (ID: {team.id}, team_id: {team.team_id})")
            logger.info(f"  Stadium: {team.stadium or 'Not set'}")
            logger.info(f"  Location: {team.stadium_location or 'Not set'}")
        
        # Check for missing teams
        all_abbreviations = [team.abbreviation for team in teams]
        
        expected_abbreviations = [
            "ARI", "ATL", "BAL", "BOS", "CHC", "CIN", "CLE", "COL", "CHW", "DET",
            "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "OAK",
            "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH"
        ]
        
        # Find which teams are missing
        missing = [abbr for abbr in expected_abbreviations if abbr not in all_abbreviations]
        if missing:
            logger.warning(f"Missing teams: {', '.join(missing)}")
        
        # Check for aliases that might be different
        aliases = {
            "CHW": ["CWS", "CHI"],  # Chicago White Sox
            "OAK": ["A's", "Athletics"],
            "SD": ["SDP"],  # San Diego Padres
            "TB": ["TBR"],  # Tampa Bay Rays
            "SF": ["SFG"],  # San Francisco Giants
            "KC": ["KCR"],  # Kansas City Royals
            "WSH": ["WAS"]   # Washington Nationals
        }
        
        # Update stadium data for teams with different abbreviations
        stadium_data = {
            "CHW": {"stadium": "Guaranteed Rate Field", "stadium_location": "Chicago, IL"},
            "OAK": {"stadium": "Oakland Coliseum", "stadium_location": "Oakland, CA"}
        }
        
        for standard_abbr, alias_list in aliases.items():
            for alias in alias_list:
                team = db.session.query(Team).filter_by(abbreviation=alias).first()
                if team and standard_abbr in missing:
                    logger.info(f"Found team {team.name} with alias {alias} for standard abbreviation {standard_abbr}")
                    
                    # Update stadium data if needed
                    if standard_abbr in stadium_data:
                        team.stadium = stadium_data[standard_abbr]["stadium"]
                        team.stadium_location = stadium_data[standard_abbr]["stadium_location"]
                        logger.info(f"Updated stadium data for {team.name}")
        
        db.session.commit()
        
        return teams

if __name__ == "__main__":
    teams = check_teams()
    logger.info(f"Checked {len(teams)} teams in database")