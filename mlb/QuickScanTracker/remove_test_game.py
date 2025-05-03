#!/usr/bin/env python3
import os
import sys
from app import app, db
from models import Game

def remove_test_game():
    """Remove any test games from the database"""
    print("Removing test games...")
    
    with app.app_context():
        # Find test games (they have game_id starting with TEST_)
        test_games = db.session.query(Game).filter(Game.game_id.like('TEST_%')).all()
        
        print(f"Found {len(test_games)} test games to remove")
        
        # Delete them
        for game in test_games:
            db.session.delete(game)
            
        db.session.commit()
        print("Test games removed successfully")

if __name__ == "__main__":
    remove_test_game()