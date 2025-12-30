import re
from datetime import datetime, timezone, timedelta
from app import db, vapid_private_key
from typing import Optional
import sqlalchemy as sqla
import sqlalchemy.orm as sqlo
import math
from flask_login import UserMixin
from pywebpush import WebPusher, WebPushException, webpush

class Location:
    latitude : float
    longitude : float

    def __init__ (self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    # gets the distance between two locations in meters
    def distance_from (self, coord):
        return 637101 * math.acos(math.sin(coord.latitude)*math.sin(self.latitude) + math.cos(coord.latitude)*math.cos(self.latitude)*math.cos(coord.longitude - self.longitude))

class User(UserMixin, db.Model):
    id : sqlo.Mapped[str] = sqlo.mapped_column(primary_key=True)
    name : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(100))
    preferred_name : sqlo.Mapped[Optional[str]] = sqlo.mapped_column(sqla.String(100))
    email : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(120), unique = True)
    phone : sqlo.Mapped[Optional[str]] = sqlo.mapped_column(sqla.String(10))
    locked : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=False, nullable=False)
    signed_agreements : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=False, nullable=False) # tracked whether a user has signed user agreements
    is_admin : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=False, nullable=False)
    notification_endpoint : sqlo.Mapped[Optional[str]] = sqlo.mapped_column(sqla.String(512))
    notification_p256dh_key : sqlo.Mapped[Optional[str]] = sqlo.mapped_column(sqla.String(32))
    notification_auth_key : sqlo.Mapped[Optional[str]] = sqlo.mapped_column(sqla.String(128))

    rides : sqlo.WriteOnlyMapped['Ride'] = sqlo.relationship(back_populates = 'user')

    # Returns user's preferred name or first name for use in UI
    def get_name(self):
        if self.preferred_name != "" and self.preferred_name is not None:
            return self.preferred_name

        return self.get_first_name()

    def get_email(self):
        return self.email

    def get_full_name(self):
        return self.name

    def get_first_name(self):
        name_split = self.name.split(", ")
        if len(name_split) >= 1:
            return name_split[1]
        else:
            return self.name

    def get_last_name(self):
        return self.name.split(", ")[0]

    def get_rides(self):
        return db.session.scalars(self.rides.select()).all()

    def get_current_ride(self):
        return db.session.scalars(self.rides.select().where(Ride.completed_ride == False)).one_or_none()

    def get_id(self):
        return self.id

    reports : sqlo.WriteOnlyMapped['Report'] = sqlo.relationship(back_populates = 'user')

    def get_reports(self):
        return db.session.scalars(self.reports.select()).all()

    def has_notification_keys(self):
        return self.notification_auth_key is not None and self.notification_p256dh_key is not None and self.notification_endpoint is not None
    
    def clear_notification_keys(self):
        self.notification_endpoint = None
        self.notification_p256dh_key = None
        self.notification_auth_key = None
        db.session.add(self)
        db.session.commit()

    def set_notification_keys(self, endpoint, p256dh, auth):
        try:
            # try initializing a pusher to ensure credentials are valid
            pusher = WebPusher(
                subscription_info=dict(endpoint=endpoint, keys=dict(p256dh=p256dh, auth=auth))
            )
            pusher.encode(b'test')
        except:
            return False
        
        self.notification_endpoint = endpoint
        self.notification_p256dh_key = p256dh
        self.notification_auth_key = auth
        db.session.add(self)
        db.session.commit()
        return True
    
    def send_notification(self, message):
        fleet = Fleet.get_fleet()
        print("sending notification to " + self.get_full_name())

        try:
            webpush(
                subscription_info=dict(endpoint=self.notification_endpoint, keys=dict(p256dh=self.notification_p256dh_key, auth=self.notification_auth_key)),
                data=message,
                vapid_private_key=vapid_private_key,
                vapid_claims=dict(sub="mailto:"+fleet.contact_email),
                ttl=86400
            )
            return True
        except WebPushException as e:
            if e.response and e.response.status_code:
                print(e.response.status_code)
                # these status codes indicate that the notification endpoint is no longer valid (ex. user denied permission later) and should be deleted
                if e.response.status_code == 401 or e.response.status_code == 403 or e.response.status_code == 404 or e.response.status_code == 410:
                    self.clear_notification_keys()
            return False

class Station(db.Model):
    id : sqlo.Mapped[int] = sqlo.mapped_column(primary_key=True)
    name : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(100))
    lat1 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    long1 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    lat2 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    long2 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    lat3 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    long3 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    lat4 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    long4 : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

    def get_details(self):
        return {'name': self.get_name(), 'pos': self.get_polygon()}

    def contains (self, checkLocation):
        pairs = (((self.lat1, self.long1), (self.lat2, self.long2)), ((self.lat2, self.long2), (self.lat3, self.long3)), ((self.lat3, self.long3), (self.lat4, self.long4)), ((self.lat4, self.long4), (self.lat1, self.long1)))
        inside = False

        for pair in pairs:
            if checkLocation.longitude > min(pair[0][1], pair[1][1]) and checkLocation.longitude <= max(pair[0][1], pair[1][1]) and checkLocation.latitude <= max(pair[0][0], pair[1][0]):
                intersection = (checkLocation.longitude - pair[0][1]) * (pair[1][0] - pair[0][0]) / (pair[1][1] - pair[0][1]) + pair[0][0]
                if pair[0][0] == pair[1][0] or checkLocation.latitude <= intersection:
                    inside = not inside

        return inside

    bikes : sqlo.WriteOnlyMapped['Bike'] = sqlo.relationship(back_populates = 'station', passive_deletes=True)

    def get_bikes(self):
        return db.session.scalars(self.bikes.select()).all()

    def get_polygon(self):
        return [[self.lat1, self.long1],[self.lat2, self.long2],[self.lat3, self.long3],[self.lat4, self.long4]]

class Bike(db.Model):
    id : sqlo.Mapped[int] = sqlo.mapped_column(primary_key=True)
    name : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(6), index = True, unique = True)
    station_id : sqlo.Mapped[Optional[int]] = sqlo.mapped_column(sqla.ForeignKey(Station.id), nullable = True)
    locked : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean)
    # when a bike is checked out for mainenance, it is not available to be rented.
    available : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=True)

    station : sqlo.Mapped[Station] = sqlo.relationship(back_populates = 'bikes')

    reports : sqlo.WriteOnlyMapped['Report'] = sqlo.relationship(back_populates = 'bike')

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

    def get_details(self):
        location = self.get_current_location()
        return {'name':self.name, 'id':self.id,
                'pos':[location.latitude, location.longitude] if location else None,
                'lastseen':location.get_time_formatted() if location else None,
                'locked':self.locked,
                'avaliable':self.available,
                'station':self.station_id,
                'status':str(self.get_report_severity())}

    def get_reports(self):
        return db.session.scalars(self.reports.select()).all()

    def get_report_severity(self):
        reports = self.get_reports()
        report_dict = {}
        for report in reports:
            report_dict[report.category] = report_dict.get(report.category, 0) + 1
        for category in report_dict:
            if report_dict[category] >= 2:
                return category
        return -1

    rides : sqlo.WriteOnlyMapped['Ride'] = sqlo.relationship(back_populates = 'bike')

    def get_rides(self):
        return db.session.scalars(self.rides.select()).all()

    def get_name(self):
        return self.name

    def get_current_ride(self):
        return db.session.scalars(self.rides.select().where(Ride.completed_ride == False)).one_or_none()

    def start_ride(self, userID):
        current_ride = Ride(bike_id=self.id, user_id=userID, completed_ride=False, positive_rating=False)
        self.station_id = None
        db.session.add(current_ride)
        db.session.add(self)
        db.session.commit()
        return current_ride

    def finish_ride(self, station, rideID, rating):
        current_ride = db.session.get(Ride, rideID)
        current_ride.completed_ride = True
        current_ride.positive_rating = rating
        current_ride.duration = datetime.now(timezone.utc) - current_ride.ride_date.replace(tzinfo=timezone.utc)
        self.station_id = station
        db.session.add(current_ride)
        db.session.add(self)
        db.session.commit()
        return current_ride

    locations : sqlo.WriteOnlyMapped['Location'] = sqlo.relationship(back_populates ='bike')

    def get_locations(self):
        return db.session.scalars(self.locations.select().order_by(Location.timestamp.desc())).all()

    def get_current_location(self):
        return db.session.scalars(self.locations.select().order_by(Location.timestamp.desc())).first()

class Ride(db.Model):
    bike_id : sqlo.Mapped[int] = sqlo.mapped_column(sqla.ForeignKey(Bike.id), primary_key=True)
    user_id : sqlo.Mapped[int] = sqlo.mapped_column(sqla.ForeignKey(User.id), primary_key=True)
    ride_date: sqlo.Mapped[datetime] = sqlo.mapped_column(default = lambda : datetime.now(timezone.utc), primary_key = True)
    duration: sqlo.Mapped[Optional[timedelta]] = sqlo.mapped_column(sqla.Interval)
    distance : sqlo.Mapped[float] = sqlo.mapped_column(default=0)
    completed_ride : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=False, nullable=False)
    # compelted_ride is true if complete, false if in progress
    positive_rating : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean)
    # rating is true if thumbs up and false if thumbs down

    user : sqlo.Mapped[User] = sqlo.relationship(back_populates = 'rides')
    bike : sqlo.Mapped[Bike] = sqlo.relationship(back_populates = 'rides')

class Report(db.Model):
    bike_id : sqlo.Mapped[int] = sqlo.mapped_column(sqla.ForeignKey(Bike.id), primary_key=True)
    user_id : sqlo.Mapped[int] = sqlo.mapped_column(sqla.ForeignKey(User.id), primary_key=True)
    timestamp: sqlo.Mapped[Optional[datetime]] = sqlo.mapped_column(default = lambda : datetime.now(timezone.utc), primary_key=True)
    category: sqlo.Mapped[int] = sqlo.mapped_column(default=0, nullable=False)
    description : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(1500))
    completed : sqlo.Mapped[bool] = sqlo.mapped_column(sqla.Boolean, default=False, nullable=False)

    user : sqlo.Mapped[User] = sqlo.relationship(back_populates = 'reports')
    bike : sqlo.Mapped[Bike] = sqlo.relationship(back_populates = 'reports')

class Location(db.Model):
    id : sqlo.Mapped[int] = sqlo.mapped_column(primary_key=True)

    bike_id : sqlo.Mapped[int] = sqlo.mapped_column(sqla.ForeignKey(Bike.id))
    timestamp : sqlo.Mapped[int] = sqlo.mapped_column(default = lambda : int(datetime.now().timestamp()))
    latitude : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())
    longitude : sqlo.Mapped[float] = sqlo.mapped_column(sqla.Float())

    def __init__(self, latitude, longitude, bike_id = 0, timestamp = int(datetime.now().timestamp())):
        self.latitude = latitude
        self.longitude = longitude
        self.bike_id = bike_id
        self.timestamp = timestamp

    def distance_from (self, coord):
        return 637101 * math.acos(math.sin(coord.latitude)*math.sin(self.latitude) + math.cos(coord.latitude)*math.cos(self.latitude)*math.cos(coord.longitude - self.longitude))

    def get_time_formatted(self):
        return re.sub(r"0(?=.:)", "", datetime.fromtimestamp(self.timestamp).strftime('%b %d, %Y at %I:%M%p'))

    def get_coords(self):
        return [self.latitude, self.longitude]

    bike : sqlo.Mapped[Bike] = sqlo.relationship(back_populates = 'locations')

class Fleet(db.Model):
    id : sqlo.Mapped[int] = sqlo.mapped_column(primary_key=True)# there should only ever be one fleet, but it still needs a primary key
    user_agreement : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(256))
    contact_email : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(256))
    contact_phone : sqlo.Mapped[str] = sqlo.mapped_column(sqla.String(10))

    @staticmethod
    def get_fleet():
        fleet = db.session.get(Fleet, 1)

        if fleet is None:
            fleet = Fleet(id=1, user_agreement="", contact_email="", contact_phone="")
            db.session.add(fleet)
            db.session.commit()

        return fleet