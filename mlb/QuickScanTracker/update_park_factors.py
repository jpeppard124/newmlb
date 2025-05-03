from app import app, db
from services.park_factor_service import ParkFactorService
from models import Game
from datetime import datetime

def update_park_factors():
    """Check and update all park factors for upcoming games"""
    with app.app_context():
        # Get all scheduled games
        games = db.session.query(Game).filter(
            Game.game_datetime >= datetime.now(),
            Game.status == 'scheduled'
        ).all()
        
        # Initialize park factor service
        park_service = ParkFactorService()
        
        print(f"Updating park factors for {len(games)} upcoming games")
        
        # Check park factors for each game
        for game in games:
            try:
                # Get the stadium
                stadium = game.stadium
                
                if not stadium:
                    print(f"No stadium set for game {game.id}, updating from home team")
                    if game.home_team and game.home_team.stadium:
                        game.stadium = game.home_team.stadium
                        db.session.commit()
                        stadium = game.stadium
                        print(f"Updated game stadium to {stadium}")
                    else:
                        print(f"Error: No stadium available for game {game.id}")
                        continue
                
                # Get the park factor
                park_factor = park_service.get_park_factor(stadium)
                
                if park_factor:
                    print(f"Park factor for {stadium}:")
                    print(f"  Runs factor: {park_factor['runs_factor']} ({park_factor['runs_label']})")
                    print(f"  HR factor: {park_factor['hr_factor']} ({park_factor['hr_label']})")
                    
                    # Calculate weather-adjusted factors
                    adjusted = park_service.calculate_weather_adjusted_factors(game.id)
                    if adjusted and 'weather_adjusted_run_factor' in adjusted:
                        print(f"  Weather-adjusted run factor: {adjusted['weather_adjusted_run_factor']:.1f}")
                    
                else:
                    print(f"No park factor found for stadium {stadium}")
            except Exception as e:
                print(f"Error processing park factor for game {game.id}: {e}")
                
        print("Park factor check complete!")

if __name__ == "__main__":
    update_park_factors()