from app import create_app, db
from app.main.models import User, Bike, Ride, Report, Location, Station, Location, Fleet
from config  import Config
import datetime
from datetime import timezone

import sqlalchemy as sqla
import sqlalchemy.orm as sqlo
import os

try:
    os.remove("gears.db")
except:
    pass

create_app(Config).app_context().push()

db.create_all()

fleet1 = Fleet(id=1, user_agreement="https://drive.google.com/file/d/147I0zCKz7B8zP5tZSdI2vs4DXY2YYm6z/preview", contact_email="gompei@wpi.edu", contact_phone="1234567890")
db.session.add(fleet1)
db.session.commit()

station1 = Station(name = "Founders", lat1 = 42.27390291668952, long1= -71.80572315424227, lat2= 42.27389397948656, long2=-71.80565934565058, lat3=42.27385277906371, long3=-71.80566570030405, lat4=42.273865935087834, long4=-71.80574084557868)
db.session.add(station1)
station2 = Station(name = "Fountain", lat1=42.27459643190141, long1=-71.8076911143144, lat2=42.274588653624086, long2=-71.80746756495398, lat3=42.27449683776706, long3=-71.80751622778007, lat4=42.27452661381543, long4=-71.8077203335524)
db.session.add(station2)
station3 = Station(name = "Quad", lat1=42.27350076207461, long1=-71.80999912706223, lat2=42.273477462405545, long2=-71.80989454001032, lat3=42.27344224188129, long3=-71.8099190043795, lat4=42.27345823028531, long4=-71.81001203380755)
db.session.add(station3)
db.session.commit()

bike1 = Bike(id=100, name = "WPI100", station_id = None, locked = True)
bike1.locations.add(Location(latitude = 42.273794084170866, longitude = -71.8018545052814))
db.session.add(bike1)
bike2 = Bike(id=101, name = "WPI101", station_id = station1.id, locked = True)
bike2.locations.add(Location(latitude = 42.273849289118836, longitude = -71.80570434830426))
db.session.add(bike2)
bike3 = Bike(id=102, name = "WPI102", station_id = station2.id, locked = True)
bike3.locations.add(Location(latitude = 42.274525968899695, longitude = -71.80761271820109))
db.session.add(bike3)
db.session.commit()
bike4 = Bike(id=115, name = "WPI115", station_id = station2.id, locked = True, available = False)
bike4.locations.add(Location(latitude = 42.2750137, longitude = -71.8066868))
db.session.add(bike4)
db.session.commit()

user1 = User(id="1", email = "gompei@wpi.edu", name = "Pi, Gompei")
db.session.add(user1)
user2 = User(id="2", email = "george@wpi.edu", name = "McGeorgeson, George")
db.session.add(user2)
user3 = User(id="3", email = "gina@wpi.edu", name = "Ginston, Gina")
db.session.add(user3)
db.session.commit()

ride1 = Ride(bike_id = bike1.id, user_id = user2.id, completed_ride = False, positive_rating = False)
db.session.add(ride1)
db.session.commit()

ride2 = Ride(bike_id = bike2.id, user_id = user3.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=100), duration = datetime.timedelta(hours=1), completed_ride = True, positive_rating = True)
db.session.add(ride2)
db.session.commit()

ride3 = Ride(bike_id = bike1.id, user_id = user2.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=10), duration = datetime.timedelta(hours=2), completed_ride = True, positive_rating = False)
db.session.add(ride3)
db.session.commit()

ride4 = Ride(bike_id = bike2.id, user_id = user3.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=2), completed_ride = False, positive_rating = False)
db.session.add(ride4)
db.session.commit()

ride5 = Ride(bike_id = bike3.id, user_id = user1.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=60), duration = datetime.timedelta(hours=20), completed_ride = True, positive_rating = True)
db.session.add(ride5)
db.session.commit()

ride6 = Ride(bike_id = bike3.id, user_id = user2.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=3), completed_ride = False, positive_rating = False)
db.session.add(ride6)
db.session.commit()