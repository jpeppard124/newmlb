#!/usr/bin/env python3
import os
import sys
from app import app, db

def reset_database():
    """Drop all tables and recreate them"""
    print("Resetting database...")
    
    with app.app_context():
        # Import models to ensure they're registered with SQLAlchemy
        import models
        
        # Drop all tables
        db.drop_all()
        print("All tables dropped.")
        
        # Create tables from models
        db.create_all()
        print("Tables created successfully.")
        
        # Re-initialize API keys
        from initialize_keys import initialize_api_keys
        initialize_api_keys()

if __name__ == "__main__":
    reset_database()