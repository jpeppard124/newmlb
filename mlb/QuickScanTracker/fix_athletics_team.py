#!/usr/bin/env python3
from app import app, db
from models import Team
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_athletics_team():
    """Update the Oakland Athletics team with correct stadium info"""
    with app.app_context():
        # Find the Athletics team
        team = db.session.query(Team).filter_by(abbreviation='ATH').first()
        
        if team:
            logger.info(f"Found team: {team.name}")
            
            # Update stadium info
            team.stadium = 'Oakland Coliseum'
            team.stadium_location = 'Oakland, CA'
            
            db.session.commit()
            logger.info(f"Updated stadium info for {team.name}")
            
            return True
        else:
            logger.warning("Athletics team not found")
            return False

if __name__ == "__main__":
    success = fix_athletics_team()
    if success:
        logger.info("Successfully updated Athletics team")
    else:
        logger.error("Failed to update Athletics team")