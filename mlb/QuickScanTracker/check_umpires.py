#!/usr/bin/env python
"""
Simple check for umpire data in the database
"""
from app import app, db
from models import UmpireStats, Game

with app.app_context():
    print("Checking for umpire data in the database...")
    umpires = UmpireStats.query.all()
    print(f"Found {len(umpires)} umpires")
    
    for umpire in umpires:
        print(f"- {umpire.name}: k_boost={umpire.k_boost}, r_boost={umpire.r_boost}")
    
    games = Game.query.limit(3).all()
    print(f"\nFound {len(games)} games (showing first 3)")
    
    for game in games:
        print(f"- Game {game.id}: {game.home_team.name} vs {game.away_team.name}")
        if hasattr(game, 'umpires') and game.umpires:
            print(f"  Assigned umpires: {', '.join([u.name for u in game.umpires])}")
        else:
            print("  No umpires assigned")