import warnings
from unicodedata import category

warnings.filterwarnings("ignore")

import unittest
from app import create_app, db
from app.main.models import Station, User, Bike, Ride, Report, Location, Fleet
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    
class TestModels(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_fleet(self):
        fleet = Fleet.get_fleet()
        self.assertIsNotNone(fleet)
        fleet.contact_email = "gompei@wpi.edu"
        db.session.add(fleet)
        db.session.commit()

        # call get_fleet again to make sure it isn't recreated
        fleet = Fleet.get_fleet()
        self.assertEqual(fleet.contact_email, "gompei@wpi.edu")
    
    def test_station_contains(self):
        s1 = Station(name="s1", lat1=0, long1=0, lat2=2, long2=0, lat3=2, long3=2, lat4=0, long4=2)
        self.assertTrue(s1.contains(Location(bike_id=0, latitude=1, longitude=1)), "square: center is inside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=-1, longitude=-1)), "square: lower left is outside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=1, longitude=-1)), "square: below is outside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=1, longitude=3)), "square: above is outside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=3, longitude=1)), "square: right is outside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=-1, longitude=1)), "square: left is outside")
        self.assertFalse(s1.contains(Location(bike_id=0, latitude=3, longitude=3)), "square: upper right is outside")

        s2 = Station(name="s2", lat1=0, long1=0, lat2=0, long2=2, lat3=2, long3=2, lat4=2, long4=0)
        self.assertTrue(s2.contains(Location(bike_id=0, latitude=1, longitude=1)), "square2: center is inside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=-1, longitude=-1)), "square2: lower left is outside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=1, longitude=-1)), "square2: below is outside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=1, longitude=3)), "square2: above is outside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=3, longitude=1)), "square2: right is outside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=-1, longitude=1)), "square2: left is outside")
        self.assertFalse(s2.contains(Location(bike_id=0, latitude=3, longitude=3)), "square2: upper right is outside")

        s3 = Station(name="s3", lat1=0, long1=4, lat2=2, long2=3, lat3=4, long3=4, lat4=2, long4=0)
        self.assertTrue(s3.contains(Location(bike_id=0, latitude=2, longitude=1)), "v: middle is inside")
        self.assertTrue(s3.contains(Location(bike_id=0, latitude=1, longitude=3)), "v: left corner is inside")
        self.assertTrue(s3.contains(Location(bike_id=0, latitude=3, longitude=3)), "v: right corner is inside")
        self.assertFalse(s3.contains(Location(bike_id=0, latitude=2, longitude=4)), "v: upper concave is outside")
        self.assertFalse(s3.contains(Location(bike_id=0, latitude=0, longitude=0)), "v: lower left is outside")
        self.assertFalse(s3.contains(Location(bike_id=0, latitude=4, longitude=0)), "v: lower right is outside")
    
    def test_user_notifications(self):
        u1 = User(id='1', name="gompei", email="gompei@wpi.edu")
        db.session.add(u1)
        db.session.commit()

        self.assertFalse(u1.set_notification_keys("", "", ""))
        self.assertFalse(u1.set_notification_keys("https://push.example.com/push/jerngkjerbngekjrtbngekjtbngejkbn", "wjtejktbnerkjbnwlekrjgbnwerjkgbnwjkrebngwjkerbngortwigbnrotngortinorkefnwoironwk", "gjiekngwjkrengwjkernf"))
        self.assertTrue(u1.set_notification_keys("https://updates.push.services.mozilla.com/wpush/v2/gAAAAABpMwqVN0Dwg-r7x1Azm6qqoIIMNo3F1hbtQXbcK48n2MnszsWUy40Xm4n2epLccr1W1co0oGZgolRCex1HpWLavDCVo7CrEY2mkTSLHCrk1f0Gc-Tg2PmPdjlEvLq2hFNEpN_BgKxWHaeszuXgGeKBeE_Mzx-z5EpSEGrFnZLzcHOHC98", "BLv7r3fEORbv1XGq_KdzImkRRFyuYuIrbsRc9bag2v_taz_UxIjYfwibIvZDI0XIR9sXfy2Q7xwvxJtSJlocak0", "CvBimGKvEPzdOS6oxqDLOQ"))

        self.assertIsNotNone(u1.notification_endpoint)
        self.assertIsNotNone(u1.notification_p256dh_key)
        self.assertIsNotNone(u1.notification_auth_key)

        u1.clear_notification_keys()

        self.assertIsNone(u1.notification_endpoint)
        self.assertIsNone(u1.notification_p256dh_key)
        self.assertIsNone(u1.notification_auth_key)

    def test_user_rides(self):
        u1 = User(id='1', name="gompei", email="gompei@wpi.edu")
        db.session.add(u1)

        b1 = Bike(name = "WPI001", station_id = None, locked = True)
        db.session.add(b1)
        b2 = Bike(name = "WPI002", station_id = None, locked = True)
        db.session.add(b2)
        db.session.commit()

        r1 = Ride(bike_id=b1.id, user_id=u1.id, completed_ride=True, positive_rating=True)
        db.session.add(r1)
        r2 = Ride(bike_id=b2.id, user_id=u1.id, completed_ride=True, positive_rating=True)
        db.session.add(r2)
        db.session.commit()

        self.assertEqual(r1.user.id, u1.id)

        rides = u1.get_rides()
        self.assertEqual(len(rides), 2)
        self.assertEqual(rides[0].bike_id, r1.bike_id)
        self.assertEqual(rides[1].bike_id, r2.bike_id)
        self.assertIsNone(u1.get_current_ride())

        r3 = Ride(bike_id=b1.id, user_id=u1.id, completed_ride=False, positive_rating=True)
        db.session.add(r3)
        db.session.commit()

        self.assertEqual(u1.get_current_ride().bike_id, r3.bike_id)

    def test_user_id(self):
        u1 = User(id='1', name="Pi, Gompei", email="gompei@wpi.edu", preferred_name="Gompslord")
        db.session.add(u1)

        self.assertEqual(u1.get_name(), "Gompslord")
        self.assertEqual(u1.get_first_name(), "Gompei")
        self.assertEqual(u1.get_last_name(), "Pi")
        self.assertEqual(u1.get_id(), "1")
    
    def test_user_reports(self):
        u1 = User(id='1', name="gompei", email="gompei@wpi.edu")
        db.session.add(u1)

        b1 = Bike(name = "WPI001", station_id = None, locked = True)
        db.session.add(b1)
        b2 = Bike(name = "WPI002", station_id = None, locked = True)
        db.session.add(b2)
        db.session.commit()

        r1 = Report(bike_id=b1.id, user_id=u1.id, description="bike no worky")
        db.session.add(r1)
        r2 = Report(bike_id=b1.id, user_id=u1.id, description="bike no worky")
        db.session.add(r2)
        db.session.commit()

        self.assertEqual(r1.user.id, u1.id)

        reports = u1.get_reports()
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0].bike_id, r1.bike_id)
        self.assertEqual(reports[1].bike_id, r2.bike_id)

        self.assertEqual(b1.get_report_severity(), 0)
        self.assertEqual(b2.get_report_severity(), -1)
        self.assertEqual(b2.get_reports(), [])
    
    def test_station_bikes(self):
        s1 = Station(name = "Founders", lat1 = 42.27390291668952, long1= -71.80572315424227, lat2= 42.27389397948656, long2=-71.80565934565058, lat3=42.27385277906371, long3=-71.80566570030405, lat4=42.273865935087834, long4=-71.80574084557868)
        db.session.add(s1)
        s2 = Station(name = "Fountain", lat1=42.27459643190141, long1=-71.8076911143144, lat2=42.274588653624086, long2=-71.80746756495398, lat3=42.27449683776706, long3=-71.80751622778007, lat4=42.27452661381543, long4=-71.8077203335524)
        db.session.add(s2)
        s3 = Station(name = "Quad", lat1=42.27350076207461, long1=-71.80999912706223, lat2=42.273477462405545, long2=-71.80989454001032, lat3=42.27344224188129, long3=-71.8099190043795, lat4=42.27345823028531, long4=-71.81001203380755)
        db.session.add(s3)
        db.session.commit()

        b1 = Bike(name = "WPI001", station_id = s1.id, locked = True)
        db.session.add(b1)
        b2 = Bike(name = "WPI002", station_id = s2.id, locked = True)
        db.session.add(b2)
        b3 = Bike(name = "WPI003", station_id = None, locked = True)
        db.session.add(b3)
        b4 = Bike(name = "WPI004", station_id = s1.id, locked = True)
        db.session.add(b4)
        db.session.commit()

        self.assertEqual(b1.station.id, s1.id)
        self.assertIsNone(b3.station)

        bikes = s1.get_bikes()
        self.assertEqual(len(bikes), 2)
        self.assertEqual(bikes[0].id, b1.id)
        self.assertEqual(bikes[1].id, b4.id)

        self.assertEqual(bikes[1].get_details()['station'], s1.id)
        self.assertEqual(s2.get_details()['pos'], s2.get_polygon())
        self.assertEqual(s2.get_bikes(), [b2])
    
    def test_bike_rides(self):
        u1 = User(id='1', name="gompei", email="gompei@wpi.edu")
        db.session.add(u1)
        u2 = User(id='2', name="george", email="george@wpi.edu")
        db.session.add(u2)

        b1 = Bike(name = "WPI001", station_id = None, locked = True)
        db.session.add(b1)
        db.session.commit()

        r1 = Ride(bike_id=b1.id, user_id=u1.id, completed_ride=True, positive_rating=True)
        db.session.add(r1)
        r2 = Ride(bike_id=b1.id, user_id=u2.id, completed_ride=True, positive_rating=True)
        db.session.add(r2)
        db.session.commit()

        self.assertEqual(r1.bike.id, b1.id)

        rides = b1.get_rides()
        self.assertEqual(len(rides), 2)
        self.assertEqual(rides[0].user.id, u1.id)
        self.assertEqual(rides[1].user.id, u2.id)
        self.assertIsNone(b1.get_current_ride())

        r3 = Ride(bike_id=b1.id, user_id=u2.id, completed_ride=False, positive_rating=True)
        db.session.add(r3)
        db.session.commit()

        self.assertEqual(b1.get_current_ride().user.id, u2.id)

    def test_bike_locations(self):
        b1 = Bike(name = "WPI001", station_id = None, locked = True)
        db.session.add(b1)
        b2 = Bike(name = "WPI002", station_id = None, locked = True)
        db.session.add(b2)
        db.session.commit()

        l1 = Location(bike_id=b1.id, latitude=0, longitude=0, timestamp=1763518447)
        db.session.add(l1)
        l2 = Location(bike_id=b1.id, latitude=1, longitude=0, timestamp=1763518449)
        db.session.add(l2)
        db.session.commit()

        self.assertEqual(l1.bike.id, b1.id)

        locationHistory = b1.get_locations()
        self.assertEqual(len(locationHistory), 2)
        self.assertEqual(locationHistory[0].latitude, l2.latitude)
        self.assertEqual(locationHistory[1].latitude, l1.latitude)

        self.assertEqual(b1.get_current_location().latitude, l2.latitude)
        self.assertIsNone(b2.get_current_location())

    def test_report_severity(self):
        u1 = User(id='1', name="gompei", email="gompei@wpi.edu")
        b1 = Bike(id=100, name="WPI100", station_id=None, locked=True)
        b2 = Bike(id=101, name="WPI101", station_id=None, locked=True)
        r1 = Report(bike_id=b1.id, category=3, user_id=u1.id, description="bike no worky")
        r2 = Report(bike_id=b1.id, category=3, user_id=u1.id, description="frame is broken :(")
        r3 = Report(bike_id=b1.id, category=3, user_id=u1.id, description="so sad")
        r4 = Report(bike_id=b2.id, category=3, user_id=u1.id, description="so happy")
        for item in [u1, b1, b2, r1, r2, r3, r4]: db.session.add(item)
        db.session.commit()

        self.assertEqual(b1.get_report_severity(), 3)
        self.assertEqual(b2.get_report_severity(), -1)

if __name__ == '__main__':
    unittest.main(verbosity=1)