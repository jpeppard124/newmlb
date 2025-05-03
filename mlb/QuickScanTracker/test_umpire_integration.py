#!/usr/bin/env python
"""
Test script for umpire integration

This script tests the integration of umpire data in the prediction engine.
It requires the TESTING environment variable to be set to enable test mode.
"""

import os
import random
import sys
import logging
from datetime import datetime, timedelta

from app import app, db
from models import Game, Team, UmpireStats, game_umpire
from prediction.engine import PredictionEngine
from services.umpire_service import UmpireService

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_test_umpires():
    """Ensure we have some test umpire data in the database"""
    with app.app_context():
        # Check if we already have umpires
        existing_umpires = UmpireStats.query.count()
        if existing_umpires > 0:
            logger.info(f"Found {existing_umpires} existing umpires in the database")
            return
        
        # Create test umpires with varied tendencies
        logger.info("Creating test umpires...")
        test_umpires = [
            {
                'name': 'Joe West',
                'umpire_id': 'west_joe',
                'games_called': 120,
                'kzone_size': 0.9,  # Smaller strike zone
                'runs_per_game': 9.2,  # More runs than average
                'strikeouts_per_game': 7.5,
                'k_boost': 0.85,  # Fewer strikeouts (pitcher unfriendly)
                'bb_boost': 1.15,  # More walks
                'r_boost': 1.2,   # More runs
                'ba_boost': 1.1,  # Higher batting average
                'obp_boost': 1.15, # Higher on-base percentage
                'slg_boost': 1.08  # Higher slugging
            },
            {
                'name': 'Angel Hernandez',
                'umpire_id': 'hernandez_angel',
                'games_called': 95,
                'kzone_size': 1.1,  # Larger strike zone
                'runs_per_game': 8.3,
                'strikeouts_per_game': 9.8,
                'k_boost': 1.25,  # More strikeouts (pitcher friendly)
                'bb_boost': 0.8,  # Fewer walks
                'r_boost': 0.85,  # Fewer runs
                'ba_boost': 0.9,  # Lower batting average
                'obp_boost': 0.85, # Lower on-base percentage
                'slg_boost': 0.92  # Lower slugging
            },
            {
                'name': 'CB Bucknor',
                'umpire_id': 'bucknor_cb',
                'games_called': 80,
                'kzone_size': 1.05,
                'runs_per_game': 8.9,
                'strikeouts_per_game': 8.4,
                'k_boost': 1.0,  # Average strikeouts
                'bb_boost': 1.0,  # Average walks
                'r_boost': 1.0,  # Average runs
                'ba_boost': 1.0,  # Average batting
                'obp_boost': 1.0, # Average on-base
                'slg_boost': 1.0  # Average slugging
            }
        ]
        
        # Insert umpires
        for umpire_data in test_umpires:
            umpire = UmpireStats(**umpire_data)
            db.session.add(umpire)
        
        db.session.commit()
        logger.info(f"Added {len(test_umpires)} test umpires to the database")

def get_random_game():
    """Get a random upcoming game from the database"""
    with app.app_context():
        # Get upcoming games
        now = datetime.now()
        future = now + timedelta(days=5)
        
        upcoming_games = Game.query.filter(
            Game.game_datetime >= now,
            Game.game_datetime <= future,
            Game.status == 'scheduled'
        ).all()
        
        if not upcoming_games:
            logger.error("No upcoming games found. Please load game data first.")
            return None
        
        # Choose a random game
        game = random.choice(upcoming_games)
        logger.info(f"Selected game: {game.id} - Home: {game.home_team.name} vs Away: {game.away_team.name}")
        return game

def assign_random_umpire(game):
    """Assign a random umpire to the specified game"""
    with app.app_context():
        # Get all umpires
        umpires = UmpireStats.query.all()
        if not umpires:
            logger.error("No umpires found in the database")
            return False
        
        # Choose a random umpire
        umpire = random.choice(umpires)
        
        # Check if game already has an umpire
        if game.umpires:
            logger.info(f"Game {game.id} already has umpire(s) assigned. Removing...")
            # Remove existing associations
            for existing_umpire in game.umpires:
                db.session.execute(
                    db.delete(game_umpire).where(
                        game_umpire.c.game_id == game.id,
                        game_umpire.c.umpire_id == existing_umpire.id
                    )
                )
        
        # Assign the new umpire
        db.session.execute(
            game_umpire.insert().values(
                game_id=game.id,
                umpire_id=umpire.id,
                position='home_plate',
                assigned_at=datetime.utcnow()
            )
        )
        
        db.session.commit()
        logger.info(f"Assigned umpire {umpire.name} (id={umpire.id}) to game {game.id}")
        return True

def test_prediction_with_umpire(game_id):
    """Generate a prediction for a game with an umpire assigned"""
    with app.app_context():
        engine = PredictionEngine()
        prediction = engine.generate_prediction(game_id)
        
        if not prediction:
            logger.error(f"Failed to generate prediction for game {game_id}")
            return
        
        logger.info("\n===== PREDICTION RESULTS =====")
        logger.info(f"Home win probability: {prediction.home_win_probability:.2%}")
        logger.info(f"Predicted score: {prediction.predicted_home_runs:.1f} - {prediction.predicted_away_runs:.1f}")
        
        if prediction.explanation_text:
            logger.info("\n===== EXPLANATION =====")
            for line in prediction.explanation_text:
                logger.info(line)
        
        return prediction

def main():
    """Main test function"""
    # Check if we're in testing mode
    if not os.environ.get("TESTING", "").lower() == "true":
        logger.error("This script requires TESTING=true environment variable to be set")
        logger.error("Please run: export TESTING=true before running this script")
        sys.exit(1)
    
    # Ensure we have test umpires
    ensure_test_umpires()
    
    # Get a random game
    game = get_random_game()
    if not game:
        sys.exit(1)
    
    # Assign a random umpire to the game
    assign_random_umpire(game)
    
    # Generate a prediction
    test_prediction_with_umpire(game.id)
    
    logger.info("Test completed successfully")

if __name__ == "__main__":
    main()