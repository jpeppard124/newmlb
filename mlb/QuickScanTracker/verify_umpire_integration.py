#!/usr/bin/env python
"""
Verification script for umpire integration

This simplified script checks if the umpire service and model are properly configured.
"""

import os
import sys
from app import app, db
from models import UmpireStats, Game, game_umpire
from services.umpire_service import UmpireService

def check_umpire_service():
    """Check if UmpireService is properly configured"""
    print("Checking UmpireService configuration...")
    
    with app.app_context():
        service = UmpireService()
        
        # Check if the service has a config and the testing flag is set
        if not hasattr(service, 'config'):
            print("ERROR: UmpireService doesn't have a config attribute")
            return False
            
        if not hasattr(service.config, 'TESTING'):
            print("ERROR: Config doesn't have TESTING attribute")
            return False
            
        print(f"UmpireService config.TESTING = {service.config.TESTING}")
        
        # Check if we have umpires in the database
        umpire_count = UmpireStats.query.count()
        print(f"Found {umpire_count} umpires in the database")
        
        # Check game-umpire relationships
        game_umpire_count = db.session.execute(db.select(game_umpire)).all()
        print(f"Found {len(game_umpire_count)} game-umpire assignments")
        
        # Test getting umpire factors for a game
        games = Game.query.limit(1).all()
        if games:
            game = games[0]
            print(f"Testing get_umpire_factors for game {game.id}...")
            factors = service.get_umpire_factors(game.id)
            if factors:
                print(f"SUCCESS: Got umpire factors: {factors}")
            else:
                print("NOTE: No umpire factors returned (this is OK if no umpire is assigned)")
        else:
            print("WARNING: No games found in database to test")
            
    return True

def main():
    print("=== Umpire Integration Verification ===")
    check_umpire_service()
    print("\nVerification completed!")

if __name__ == "__main__":
    main()