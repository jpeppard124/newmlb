#!/usr/bin/env python3
import os
import sys
import json
from app import app, db
from models import Team, Game
from services.sportsdataio_service import SportsDataIOService
from datetime import datetime

def get_sample_game_data():
    """Fetch and save sample game data to debug team matching issues"""
    print("Fetching sample game data...")
    
    with app.app_context():
        # Create the service
        service = SportsDataIOService()
        
        # Fetch games for today
        date = datetime.now().strftime('%Y-%b-%d')
        print(f"Fetching games for {date}...")
        
        endpoint = f"{service.base_url}/scores/json/GamesByDate/{date}"
        response = service.headers
        print(f"Using headers: {service.headers}")
        
        import requests
        response = requests.get(endpoint, headers=service.headers)
        
        if response.status_code == 200:
            games_data = response.json()
            print(f"Successfully fetched {len(games_data)} games")
            
            # Save the first game to a file for inspection
            if games_data:
                first_game = games_data[0]
                
                # Save to a file
                with open('sample_game.json', 'w') as f:
                    json.dump(first_game, f, indent=2)
                
                print(f"Saved first game to sample_game.json")
                
                # Print the keys present in game data
                print(f"Game data keys: {list(first_game.keys())}")
                
                # Print some key attributes
                print(f"Game ID: {first_game.get('GameID')}")
                print(f"Home Team: {first_game.get('HomeTeam')}")
                print(f"Away Team: {first_game.get('AwayTeam')}")
                print(f"Status: {first_game.get('Status')}")
                print(f"Date/Time: {first_game.get('DateTime')}")
            else:
                print("No games found for today")
        else:
            print(f"Failed to fetch games: {response.status_code} - {response.text}")
            
        # Compare with teams in the database
        all_teams = db.session.query(Team).all()
        print(f"\nTeams in database: {len(all_teams)}")
        
        for team in all_teams:
            print(f"Team: id={team.id}, team_id={team.team_id}, name={team.name}, abbreviation={team.abbreviation}")
        
if __name__ == "__main__":
    get_sample_game_data()