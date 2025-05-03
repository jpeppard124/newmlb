from app import app, db
from models import ParkFactor, Game

def check_park_factors():
    """Check park factors stored in the database"""
    with app.app_context():
        # Check total count
        count = db.session.query(ParkFactor).count()
        print(f"Total park factors in database: {count}")
        
        # Check some specific stadiums
        stadiums = ['Yankee Stadium', 'Fenway Park', 'Dodger Stadium', 'Wrigley Field']
        for stadium in stadiums:
            pf = db.session.query(ParkFactor).filter_by(stadium_name=stadium).first()
            if pf:
                print(f"\n{stadium}:")
                print(f"  Runs factor: {pf.runs_factor}")
                print(f"  HR factor: {pf.hr_factor}")
                print(f"  Elevation: {pf.elevation}")
            else:
                print(f"\n{stadium}: Not found")
        
        # Check game stadium mapping
        games = db.session.query(Game).limit(5).all()
        print("\nGame stadium mapping:")
        for game in games:
            print(f"Game {game.id}: {game.away_team.abbreviation} @ {game.home_team.abbreviation} - Stadium: {game.stadium}")
            if game.stadium:
                pf = ParkFactor.get_by_stadium(game.stadium)
                if pf:
                    print(f"  Has park factor: Yes")
                else:
                    print(f"  Has park factor: No")
            else:
                print(f"  No stadium set for this game")

if __name__ == "__main__":
    check_park_factors()