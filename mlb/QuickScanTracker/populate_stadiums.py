#!/usr/bin/env python3
from app import app, db
from models import Team
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_stadium_data():
    """Populate MLB teams with their stadium information for weather lookups"""
    with app.app_context():
        # Stadium data for all 30 MLB teams
        stadium_data = [
            {"abbreviation": "ARI", "stadium": "Chase Field", "stadium_location": "Phoenix, AZ"},
            {"abbreviation": "ATL", "stadium": "Truist Park", "stadium_location": "Atlanta, GA"},
            {"abbreviation": "BAL", "stadium": "Oriole Park at Camden Yards", "stadium_location": "Baltimore, MD"},
            {"abbreviation": "BOS", "stadium": "Fenway Park", "stadium_location": "Boston, MA"},
            {"abbreviation": "CHC", "stadium": "Wrigley Field", "stadium_location": "Chicago, IL"},
            {"abbreviation": "CIN", "stadium": "Great American Ball Park", "stadium_location": "Cincinnati, OH"},
            {"abbreviation": "CLE", "stadium": "Progressive Field", "stadium_location": "Cleveland, OH"},
            {"abbreviation": "COL", "stadium": "Coors Field", "stadium_location": "Denver, CO"},
            {"abbreviation": "CWS", "stadium": "Guaranteed Rate Field", "stadium_location": "Chicago, IL"},
            {"abbreviation": "DET", "stadium": "Comerica Park", "stadium_location": "Detroit, MI"},
            {"abbreviation": "HOU", "stadium": "Minute Maid Park", "stadium_location": "Houston, TX"},
            {"abbreviation": "KC", "stadium": "Kauffman Stadium", "stadium_location": "Kansas City, MO"},
            {"abbreviation": "LAA", "stadium": "Angel Stadium", "stadium_location": "Anaheim, CA"},
            {"abbreviation": "LAD", "stadium": "Dodger Stadium", "stadium_location": "Los Angeles, CA"},
            {"abbreviation": "MIA", "stadium": "LoanDepot Park", "stadium_location": "Miami, FL"},
            {"abbreviation": "MIL", "stadium": "American Family Field", "stadium_location": "Milwaukee, WI"},
            {"abbreviation": "MIN", "stadium": "Target Field", "stadium_location": "Minneapolis, MN"},
            {"abbreviation": "NYM", "stadium": "Citi Field", "stadium_location": "Queens, NY"},
            {"abbreviation": "NYY", "stadium": "Yankee Stadium", "stadium_location": "Bronx, NY"},
            {"abbreviation": "OAK", "stadium": "Oakland Coliseum", "stadium_location": "Oakland, CA"},
            {"abbreviation": "PHI", "stadium": "Citizens Bank Park", "stadium_location": "Philadelphia, PA"},
            {"abbreviation": "PIT", "stadium": "PNC Park", "stadium_location": "Pittsburgh, PA"},
            {"abbreviation": "SD", "stadium": "Petco Park", "stadium_location": "San Diego, CA"},
            {"abbreviation": "SEA", "stadium": "T-Mobile Park", "stadium_location": "Seattle, WA"},
            {"abbreviation": "SF", "stadium": "Oracle Park", "stadium_location": "San Francisco, CA"},
            {"abbreviation": "STL", "stadium": "Busch Stadium", "stadium_location": "St. Louis, MO"},
            {"abbreviation": "TB", "stadium": "Tropicana Field", "stadium_location": "St. Petersburg, FL"},
            {"abbreviation": "TEX", "stadium": "Globe Life Field", "stadium_location": "Arlington, TX"},
            {"abbreviation": "TOR", "stadium": "Rogers Centre", "stadium_location": "Toronto, ON"},
            {"abbreviation": "WSH", "stadium": "Nationals Park", "stadium_location": "Washington, DC"}
        ]
        
        # Update team data
        count = 0
        for team_stadium in stadium_data:
            team = db.session.query(Team).filter_by(abbreviation=team_stadium["abbreviation"]).first()
            
            if team:
                logger.info(f"Updating stadium data for {team.name}")
                team.stadium = team_stadium["stadium"]
                team.stadium_location = team_stadium["stadium_location"]
                count += 1
            else:
                logger.warning(f"Team with abbreviation {team_stadium['abbreviation']} not found")
        
        db.session.commit()
        logger.info(f"Updated stadium information for {count} teams")
        
        return count

if __name__ == "__main__":
    count = populate_stadium_data()
    if count > 0:
        logger.info(f"Successfully updated stadium data for {count} teams")
    else:
        logger.error("Failed to update stadium data")