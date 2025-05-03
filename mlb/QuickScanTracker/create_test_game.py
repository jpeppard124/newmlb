#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import Team, Game
from datetime import datetime, timedelta

def create_test_game():
    """Create a test game directly to test database connectivity"""
    print("Creating a test game...")
    
    with app.app_context():
        # Find some teams
        yankees = db.session.query(Team).filter_by(abbreviation="NYY").first()
        rays = db.session.query(Team).filter_by(abbreviation="TB").first()
        
        if not yankees or not rays:
            print("Could not find required teams!")
            return
            
        print(f"Found teams: {yankees.name} vs {rays.name}")
        
        # Create a game tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Create game ID based on date (to ensure uniqueness)
        game_id = f"TEST_{tomorrow.strftime('%Y%m%d')}"
        
        # Check if the test game already exists
        existing = db.session.query(Game).filter_by(game_id=game_id).first()
        if existing:
            print(f"Test game already exists with ID {game_id}")
            return
            
        # Create new game
        game = Game(
            game_id=game_id,
            game_datetime=tomorrow,
            home_team_id=yankees.id,
            away_team_id=rays.id,
            stadium=yankees.stadium,
            status='scheduled'
        )
        
        try:
            db.session.add(game)
            db.session.commit()
            print(f"Successfully created test game: {yankees.name} vs {rays.name} on {tomorrow}")
            
            # Verify it exists
            check = db.session.query(Game).filter_by(game_id=game_id).first()
            if check:
                print(f"Verified game saved with ID: {check.id}")
            else:
                print("ERROR: Game was not saved properly!")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating game: {e}")

if __name__ == "__main__":
    create_test_game()