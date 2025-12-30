import os
import datetime
import time
import re
from datetime import timezone
from urllib.parse import urlencode

import pytest
from flask import jsonify
import requests

from app import create_app, db
from app.main.models import User, Station, Bike, Ride, Location, Fleet, Report
from config import Config
from flask_login import login_user, current_user
import sqlalchemy as sqla


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SECRET_KEY = 'bad-bad-key'
    WTF_CSRF_ENABLED = False
    DEBUG = True
    TESTING = True


@pytest.fixture(scope='module')
def test_client():
    # create the flask application ; configure the app for tests
    flask_app = create_app(config_class=TestConfig)

    # db.init_app(flask_app)
    # Flask provides a way to test your application by exposing the Werkzeug test Client
    # and handling the context locals for you.
    testing_client = flask_app.test_client()
 
    # Establish an application context before running the tests.
    ctx = flask_app.test_request_context()
    ctx.push()
 
    yield  testing_client 
    # this is where the testing happens!
 
    ctx.pop()


@pytest.fixture
def init_database(request,test_client):
    # Create the database and the database table
    db.create_all()

    user1 = User(id="1", name = "Pi, Gompei", email = "gompei@wpi.edu", is_admin = True, signed_agreements = True)
    db.session.add(user1)
    user2 = User(id="2", name = "McGeorgeson, George", email = "george@wpi.edu")
    db.session.add(user2)
    user3 = User(id="3", email = "gina@wpi.edu", name = "Ginston, Gina")
    db.session.add(user3)

    station1 = Station(name = "Founders", lat1 = 42.27390291668952, long1= -71.80572315424227, lat2= 42.27389397948656, long2=-71.80565934565058, lat3=42.27385277906371, long3=-71.80566570030405, lat4=42.273865935087834, long4=-71.80574084557868)
    db.session.add(station1)

    db.session.commit()

    login_user(user1, test_client)

    location1 = Location(latitude=42, longitude=-72, bike_id=100)
    db.session.add(location1)
    bike1 = Bike(id=100, name = "WPI100", station_id = station1.id, locked = True)
    db.session.add(bike1)

    location2 = Location(latitude=43, longitude=-71, bike_id=101)
    db.session.add(location2)
    bike2 = Bike(id=101, name = "WPI101", locked = True)
    db.session.add(bike2)

    location3 = Location(latitude=40, longitude=-70, bike_id=102)
    db.session.add(location3)
    bike3 = Bike(id=102, name="WPI102", locked=False)
    db.session.add(bike3)

    location4 = Location(latitude=41, longitude=-72, bike_id=110)
    db.session.add(location4)
    bike4 = Bike(id=110, name="WPI110", locked=True, available=False)
    db.session.add(bike4)

    ride1 = Ride(bike_id=bike1.id, user_id=user2.id, ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=100), duration = datetime.timedelta(hours=1), completed_ride=True, positive_rating=False)
    db.session.add(ride1)
    db.session.commit()

    fleet = Fleet.get_fleet()
    fleet.user_agreement = "https://drive.google.com/file/d/147I0zCKz7B8zP5tZSdI2vs4DXY2YYm6z/preview"
    fleet.contact_email = "gompei@wpi.edu"
    fleet.contact_phone = "1234567890"
    db.session.add(fleet)

    db.session.commit()

    yield  # this is where the testing happens!

    db.session.close()
    db.drop_all()


def test_start_rental_view(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental
    THEN check that information about the bike is displayed
    """

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Rent WPI100" in response.data

def test_start_rental_view_locked(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and with a locked account
    THEN check that the correct error message is displayed
    """

    user = db.session.get(User, 1)
    user.locked = True
    db.session.add(user)
    db.session.commit()

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Your account is locked" in response.data

def test_start_rental_view_user_agreement(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and without having signed the user agreement
    THEN check that the correct error message is displayed
    """

    user = db.session.get(User, 1)
    user.signed_agreements = False
    db.session.add(user)
    db.session.commit()

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"You must accept our user agreement in order to rent a bike." in response.data

def test_start_rental_view_bike_nonexistant(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and with a bike ID that doesn't exist
    THEN check that the correct error message is displayed
    """

    response = test_client.get('/rental/7',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Bike is not available" in response.data

def test_start_rental_view_bike_in_use(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and with a bike that is already in use
    THEN check that the correct error message is displayed
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(2)
    db.session.add(bike)
    db.session.commit()

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Bike is not available" in response.data

def test_start_rental_view_bike_unavailable(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and with a bike that is marked as unavailable
    THEN check that the correct error message is displayed
    """

    bike = db.session.get(Bike, 100)
    bike.available = False
    db.session.add(bike)
    db.session.commit()

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Bike is not available" in response.data


def test_start_rental_view_bike_already_renting(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and when the user is already renting a bike
    THEN check that the correct error message is displayed
    """

    bike1 = db.session.get(Bike, 100)
    bike2 = db.session.get(Bike, 101)
    bike1.start_ride(1)
    db.session.add(bike1)
    db.session.add(bike2)
    db.session.commit()

    response = test_client.get('/rental/' + str(bike2.id),
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"You are already renting a bike" in response.data


def test_start_rental_view_bike_already_renting_same_bike(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with no active rental and when the user is already renting a bike and requests the same bike that they are renting
    THEN check that the user is redirected to the manage bike page
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.get('/rental/' + str(bike.id),
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Currently Renting" in response.data


def test_start_rental_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST)
    THEN check that the rental is started and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    response = test_client.post('/rental/' + str(bike.id) + '/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    user = db.session.get(User, 1)
    assert user.get_current_ride().bike.id == bike.id

def test_start_rental_success_sign_agreement(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) with a user who just signed the user agreement
    THEN check that the rental is started and returned data reflects that, and the user signing the agreement is saved
    """

    user = db.session.get(User, 1)
    user.signed_agreements = False
    db.session.add(user)
    db.session.commit()

    bike = db.session.get(Bike, 100)
    response = test_client.post('/rental/' + str(bike.id) + '/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587, signed_agreements=True),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    user = db.session.get(User, 1)
    assert user.get_current_ride().bike.id == bike.id
    assert user.signed_agreements

def test_start_rental_fail_already_renting(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) when the user is already renting a bike
    THEN check that the rental is not started and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/101/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-already-renting" in response.data

    user = db.session.get(User, 1)
    assert user.get_current_ride().bike.id == bike.id


def test_start_rental_fail_not_nearby(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) when the user is not near the bike they choose to rent
    THEN check that the rental is not started and returned data reflects that
    """

    response = test_client.post('/rental/100/start',
                                data=dict(lat=0, long=0),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-too-far-bike" in response.data

    user = db.session.get(User, 1)
    assert user.get_current_ride() is None


def test_start_rental_fail_bike_in_use(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) when the requested bike is in use
    THEN check that the rental is not started and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(2)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/' + str(bike.id) + '/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-bike-unavailable" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride().user.id == '2'

def test_start_rental_fail_bike_unavailable(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) when the requested bike is marked as unavailable
    THEN check that the rental is not started and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.available = False
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/' + str(bike.id) + '/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-bike-unavailable" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None

def test_start_rental_fail_bike_nonexistant(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) when the requested bike does not exist
    THEN check that the rental is not started and returned data reflects that
    """

    response = test_client.post('/rental/jgwknergwljkern/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-bike-unavailable" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None

def test_start_rental_fail_account_locked(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) with a locked account
    THEN check that the rental is not started and returned data reflects that
    """

    user = db.session.get(User, 1)
    user.locked = True
    db.session.add(user)
    db.session.commit()

    response = test_client.post('/rental/100/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-account-locked" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None

def test_start_rental_fail_user_agreement(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/start' form is submitted (POST) without signing the user agreement
    THEN check that the rental is not started and returned data reflects that
    """

    user = db.session.get(User, 1)
    user.signed_agreements = False
    db.session.add(user)
    db.session.commit()

    response = test_client.post('/rental/100/start',
                                data=dict(lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-user-agreement" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None

def test_bike_status_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>' page is viewed (GET) with an active rental
    THEN check page reflects the bike's current status
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.get('/rental/100',
                               follow_redirects=True)

    assert response.status_code == 200
    assert b"Currently Renting" in response.data
    assert b"Bike is locked" in response.data


def test_setlock_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/setlock' form is submitted (POST)
    THEN check that the bike is locked/unlocked and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(1)
    bike.locked = True
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/setlock',
                                data=dict(state='unlocked', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    bike = db.session.get(Bike, bike.id)
    assert not bike.locked

def test_setlock_admin_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/setlock' form is submitted (POST) by an admin on a bike they are not currently renting
    THEN check that the bike is locked/unlocked and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(2)
    bike.locked = True
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/setlock',
                                data=dict(state='unlocked', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    bike = db.session.get(Bike, bike.id)
    assert not bike.locked


def test_setlock_fail_no_rental(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/setlock' form is submitted (POST) while the user has no active rental
    THEN check that the bike is not locked/unlocked and returned data reflects that
    """

    user = db.session.get(User, 1)
    user.is_admin = False # this test needs a non-admin user as admins can lock/unlock any bike
    db.session.add(user)

    bike = db.session.get(Bike, 100)
    bike.locked = True
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/setlock',
                                data=dict(state='unlocked', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-no-ride" in response.data

    bike = db.session.get(Bike, bike.id)
    assert bike.locked

def test_setlock_fail_wrong_rental(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/setlock' form is submitted (POST) with a bike the user is not currently riding
    THEN check that the bike is not locked/unlocked and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.start_ride(1)
    bike.locked = True
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/101/setlock',
                                data=dict(state='unlocked', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-wrong-ride" in response.data

    bike = db.session.get(Bike, bike.id)
    assert bike.locked


def test_return_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/end' form is submitted (POST)
    THEN check that the rental is ended and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.station_id = None
    bike.locked = True
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride() is None
    assert DBbike.station.id == 1

def test_return_admin_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/end' form is submitted (POST) by an admin on a bike they are not currently renting
    THEN check that the rental is ended and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.station_id = None
    bike.locked = True
    bike.start_ride(2)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"success" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride() is None
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride() is None
    assert DBbike.station.id == 1


def test_return_fail_unlocked(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id/end' form is submitted (POST) while the bike is unlocked
    THEN check that the rental is not ended and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.station = None
    bike.locked = False
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-not-locked" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride().bike.id == bike.id
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride().user.id == '1'


def test_return_fail_not_nearby(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/end' form is submitted (POST) while the bike is not near a station
    THEN check that the rental is not ended and returned data reflects that
    """

    bike = db.session.get(Bike, 100)
    bike.station = None
    bike.locked = True
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=0, long=0),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-too-far-station" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride().bike.id == bike.id
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride().user.id == '1'


def test_return_fail_no_rental(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/end' form is submitted (POST) while the user does not have an active rental
    THEN check that returned data reflects that
    """

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-no-ride" in response.data

def test_return_fail_wrong_rental(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/rental/<bike_id>/end' form is submitted (POST) while the user is renting a different bike
    THEN check that the rental is not ended and returned data reflects that
    """

    bike = db.session.get(Bike, 101)
    bike.station = None
    bike.locked = True
    bike.start_ride(1)
    db.session.add(bike)
    db.session.commit()

    response = test_client.post('/rental/100/end',
                                data=dict(rating='positive', lat=42.27387630416786, long=-71.80569690484587),
                                follow_redirects=True)

    assert response.status_code == 200
    assert b"error-wrong-ride" in response.data

    DBuser = db.session.get(User, 1)
    assert DBuser.get_current_ride().bike.id == bike.id
    DBbike = db.session.get(Bike, bike.id)
    assert DBbike.get_current_ride().user.id == '1'

def test_fleet_settings_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' form is submitted (POST)
    THEN check that the fleet settings are updated and returned page reflects that
    """

    response = test_client.post('/admin/fleet',
        data=dict(user_agreement="https://wpi.edu", contact_email="gompei@wpi.edu", contact_phone="1234567890"),
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Updated Fleet Settings" in response.data

    fleet = Fleet.get_fleet()
    assert fleet.user_agreement == "https://wpi.edu"
    assert fleet.contact_email == "gompei@wpi.edu"
    assert fleet.contact_phone == "1234567890"

def test_fleet_settings_change_user_agreement(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' form is submitted (POST) with a new user agreement URL
    THEN check that all users' will be required to accepted the user agreement again
    """

    signed = False
    for user in db.session.scalars(sqla.select(User)):
        signed = True
        break

    assert signed

    response = test_client.post('/admin/fleet',
        data=dict(user_agreement="https://wpi.edu", contact_email="gompei@wpi.edu", contact_phone="1234567890"),
        follow_redirects=True)

    assert response.status_code == 200
    assert b"Updated Fleet Settings" in response.data

    for user in db.session.scalars(sqla.select(User)):
        assert not user.signed_agreements

def test_fleet_settings_fail_invalid_url(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' form is submitted (POST) with an invalid user agreement URL
    THEN check that the fleet settings are not updated and returned page reflects that
    """

    response = test_client.post('/admin/fleet',
        data=dict(user_agreement="wpi.edu", contact_email="gompei@wpi.edu", contact_phone="1234567890"),
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Updated Fleet Settings" not in response.data

    fleet = Fleet.get_fleet()
    assert fleet.user_agreement != "wpi.edu"

def test_fleet_settings_fail_invalid_email(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' form is submitted (POST) with an invalid contact email
    THEN check that the fleet settings are not updated and returned page reflects that
    """

    response = test_client.post('/admin/fleet',
        data=dict(user_agreement="https://wpi.edu", contact_email="gompei", contact_phone="1234567890"),
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Updated Fleet Settings" not in response.data

    fleet = Fleet.get_fleet()
    assert fleet.contact_email != "gompei"

def test_fleet_settings_fail_invalid_phone(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' form is submitted (POST) with an invalid contact phone
    THEN check that the fleet settings are not updated and returned page reflects that
    """

    response = test_client.post('/admin/fleet',
        data=dict(user_agreement="https://wpi.edu", contact_email="gompei@wpi.edu", contact_phone="1234"),
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Updated Fleet Settings" not in response.data

    fleet = Fleet.get_fleet()
    assert fleet.contact_phone != "1234"

def test_fleet_settings_prefill(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' page is requested (GET)
    THEN check that the fleet settings are prefilled with their current values
    """

    fleet = Fleet.get_fleet()
    fleet.user_agreement = "https://github.com"
    fleet.contact_email = "gabe@github.com"
    fleet.contact_phone = "0987654321"
    db.session.add(fleet)
    db.session.commit()

    response = test_client.get('/admin/fleet',
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b"https://github.com" in response.data
    assert b"gabe@github.com" in response.data
    assert b"0987654321" in response.data

def test_admin_home_page_content(test_client, init_database):

    response = test_client.get('/admin', follow_redirects = True)
    assert response.status_code == 200
    assert b"Completed Rides" in response.data


def test_map_data_response(test_client, init_database):
    response = test_client.get('/admin', follow_redirects=True)
    assert response.status_code == 200

    # filter by user_id = 2, should only have a bike wpi001
    response = test_client.post('/admin',
                                data=dict(date=1, duration=6, user=2),
                                follow_redirects=True)
    assert response.status_code == 200
    assert b"4.434444444444445" not in response.data
    # assert b"19.434444444444445" in response.data

def test_fleet_settings_station_list(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet' page is requested (GET)
    THEN check that the correct list of stations is displayed
    """

    response = test_client.get('/admin/fleet',
        follow_redirects=True)

    assert response.status_code == 200
    assert b"Founders" in response.data

def test_create_station_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/new' form is submitted (POST)
    THEN check that a station is created and the returned page reflects that
    """

    response = test_client.post('/admin/fleet/station/new',
        follow_redirects=True,
        data=dict(name="New Station", lat1=0, lat2=0, lat3=0, lat4=0, long1=0, long2=0, long3=0, long4=0))

    assert db.session.scalars(sqla.select(Station).where(Station.name == "New Station")) is not None
    assert response.status_code == 200
    assert b"Updated station New Station" in response.data

def test_edit_station_prefill(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>' page is viewed (GET)
    THEN check that the station's current data is prefilled into the form
    """

    response = test_client.get('/admin/fleet/station/1',
        follow_redirects=True)

    assert response.status_code == 200
    assert b"Edit Station" in response.data
    assert b"Founders" in response.data

def test_edit_station_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>' form is submitted (POST)
    THEN check that the station is updated and the returned page reflects that
    """

    response = test_client.post('/admin/fleet/station/1',
        follow_redirects=True,
        data=dict(name="New Station", lat1=0, lat2=0, lat3=0, lat4=0, long1=0, long2=0, long3=0, long4=0))

    assert db.session.get(Station, 1).name == "New Station"
    assert response.status_code == 200
    assert b"Updated station New Station" in response.data

def test_edit_station_fail_nonexistant(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>' form is submitted (POST) with a station that does not exist
    THEN check that the correct error message is displayed
    """

    response = test_client.post('/admin/fleet/station/jkernbwgjknerkjgwne',
        follow_redirects=True,
        data=dict(name="New Station", lat1=0, lat2=0, lat3=0, lat4=0, long1=0, long2=0, long3=0, long4=0))

    assert response.status_code == 200
    assert b"Station not found" in response.data

def test_delete_station_success(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>/delete' form is submitted (POST)
    THEN check that the station is deleted and the returned page reflects that
    """

    station = db.session.get(Station, 1)
    for bike in station.get_bikes():
        bike.station = None
        db.session.add(bike)
    db.session.commit()

    response = test_client.post('/admin/fleet/station/1/delete',
        follow_redirects=True)

    assert response.status_code == 200
    assert b'Deleted station Founders' in response.data
    assert db.session.get(Station, 1) is None

def test_delete_station_fail_nonexistant(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>/delete' form is submitted (POST) with a station that does not exist
    THEN check that the correct error message is displayed
    """

    response = test_client.post('/admin/fleet/station/wejkrnwnejrktnekj/delete',
        follow_redirects=True)

    assert response.status_code == 200
    assert b'Station not found' in response.data

def test_delete_station_fail_has_bikes(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/fleet/station/<id>/delete' form is submitted (POST) while the station currently has bikes
    THEN check that the station is not deleted and the returned page reflects that
    """

    response = test_client.post('/admin/fleet/station/1/delete',
        follow_redirects=True)

    assert response.status_code == 200
    assert b'Cannot delete station currently containing bikes' in response.data
    assert b'Edit Station' in response.data
    assert db.session.get(Station, 1) is not None

def test_map_response_data(test_client, init_database):
    response = test_client.post('/mapDetails',
                                data=dict(),
                                follow_redirects=True)

    assert response.status_code == 200
    bike2 = db.session.get(Bike, 100)
    assert bike2.name in str(response.data)
    station1 = db.session.get(Station, 1)
    assert station1.name in str(response.data)

def test_map_page(test_client, init_database):
    response = test_client.get('/home', follow_redirects=True)
    assert response.status_code == 200
    assert b"Scan" in response.data
    assert b"Account" in response.data

def test_admin_users_page(test_client, init_database):
    response = test_client.get('/admin/users', follow_redirects = True)
    assert response.status_code == 200
    assert b"User Name" in response.data

def test_admin_users_toggle_admin(test_client, init_database):

    user4 = User(id="4", email = "four@wpi.edu", name = "quad, four")
    db.session.add(user4)
    db.session.commit()

    user_id = user4.id

    url="/admin/users/toggle/admin?" + urlencode({"user_id": user_id})

    response = test_client.get(url, follow_redirects = True)
    assert response.status_code == 200
    assert b"is_admin toggled" in response.data

def test_admin_users_toggle_banned(test_client, init_database):

    user4 = User(id="4", email = "four@wpi.edu", name = "quad, four")
    db.session.add(user4)
    db.session.commit()

    user_id = user4.id

    url="/admin/users/toggle/banned?" + urlencode({"user_id": user_id})

    response = test_client.get(url, follow_redirects = True)
    assert response.status_code == 200
    assert b"is_banned toggled" in response.data

def test_admin_user_filter_admin(test_client, init_database):
    
    user5 = User(id="5", email = "five@wpi.edu", name = "quint, five", is_admin=True, locked=False)
    db.session.add(user5)
    user6 = User(id="6", email = "six@wpi.edu", name = "hex, six", is_admin=False, locked=False)
    db.session.add(user6)
    user7 = User(id="7", email = "seven@wpi.edu", name = "sept, seven", is_admin=False, locked=True)
    db.session.add(user7)
    db.session.commit()

    response = test_client.post('/admin/users/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "", "admin": True, "banned": False},
                                follow_redirects=True)
    assert response.status_code == 200
    

    data = response.json
    assert len(data['result']) == 2
    assert b"five@wpi.edu" in response.data
    assert b"six@wpi.edu" not in response.data
    assert b"seven@wpi.edu" not in response.data

def test_admin_user_filter_banned(test_client, init_database):
    
    user5 = User(id="5", email = "five@wpi.edu", name = "quint, five", is_admin=True, locked=False)
    db.session.add(user5)
    user6 = User(id="6", email = "six@wpi.edu", name = "hex, six", is_admin=False, locked=False)
    db.session.add(user6)
    user7 = User(id="7", email = "seven@wpi.edu", name = "sept, seven", is_admin=False, locked=True)
    db.session.add(user7)
    db.session.commit()

    response = test_client.post('/admin/users/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "", "admin": False, "banned": True},
                                follow_redirects=True)
    assert response.status_code == 200
    

    data = response.json
    assert len(data['result']) == 1
    assert b"five@wpi.edu" not in response.data
    assert b"six@wpi.edu" not in response.data
    assert b"seven@wpi.edu" in response.data

def test_admin_user_filter_search(test_client, init_database):
    
    user5 = User(id="5", email = "five@wpi.edu", name = "quint, five", is_admin=True, locked=False)
    db.session.add(user5)
    user6 = User(id="6", email = "six@wpi.edu", name = "hex, six", is_admin=False, locked=False)
    db.session.add(user6)
    user7 = User(id="7", email = "seven@wpi.edu", name = "sept, seven", is_admin=False, locked=True)
    db.session.add(user7)
    db.session.commit()

    response = test_client.post('/admin/users/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "six", "admin": False, "banned": False},
                                follow_redirects=True)
    assert response.status_code == 200
    

    data = response.json
    assert len(data['result']) == 1
    assert b"five@wpi.edu" not in response.data
    assert b"six@wpi.edu" in response.data
    assert b"seven@wpi.edu" not in response.data
def test_messaging_page(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' page is viewed
    THEN check that a form is displayed with the correct list of users
    """

    response = test_client.get('/admin/messaging',
        follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Send Messages' in response.data

    for user in db.session.scalars(sqla.select(User)):
        assert '<option value="{}">{}</option>'.format(user.id, user.email).encode() in response.data

def test_messaging_fail_no_recipients(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' form is submitted with no recipients selected
    THEN check the correct error message is displayed
    """

    response = test_client.post('/admin/messaging',
        follow_redirects=True,
        data=dict(recipients='', recipients_all='', mock=True, subject='test', body='test'))
    
    assert response.status_code == 200
    assert b'No recipients selected' in response.data

def test_messaging_success_single_recipient(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' form is submitted with one recipient selected
    THEN check that a message would be sent
    """

    u1 = db.session.get(User, 1)
    u1.notification_endpoint = 'a'
    u1.notification_auth_key = 'a'
    u1.notification_p256dh_key = 'a'
    db.session.add(u1)
    db.session.commit()

    response = test_client.post('/admin/messaging',
        follow_redirects=True,
        data=dict(recipients='1', recipients_all='', mock=True, subject='test', body='test'))
    
    assert response.status_code == 200
    assert b'"1"' in response.data
    assert b'"no_keys": 0'

def test_messaging_success_single_recipient_no_keys(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' form is submitted with one recipient selected who doesn't have notification keys set
    THEN check that a message would be sent
    """

    u1 = db.session.get(User, 1)
    u1.notification_endpoint = None
    u1.notification_auth_key = None
    u1.notification_p256dh_key = None
    db.session.add(u1)
    db.session.commit()

    response = test_client.post('/admin/messaging',
        follow_redirects=True,
        data=dict(recipients='1', recipients_all='', mock=True, subject='test', body='test'))
    
    assert response.status_code == 200
    assert b'"1"' in response.data
    assert b'"no_keys": 1'

def test_messaging_success_multiple_recipients(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' form is submitted with multiple recipients selected
    THEN check that messages would be sent
    """

    response = test_client.post('/admin/messaging',
        follow_redirects=True,
        data=dict(recipients='1, 2', recipients_all='', mock=True, subject='test', body='test'))
    
    assert response.status_code == 200
    assert b'"1"' in response.data
    assert b'"2"' in response.data

def test_messaging_success_all_recipients(test_client, init_database):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/admin/messaging' form is submitted with all recipients selected
    THEN check that messages would be sent
    """

    response = test_client.post('/admin/messaging',
        follow_redirects=True,
        data=dict(recipients='', recipients_all=True, mock=True, subject='test', body='test'))
    
    assert response.status_code == 200

    for user in db.session.scalars(sqla.select(User)):
        assert '"{}"'.format(user.id).encode() in response.data


def test_get_admin_rides(test_client, init_database):
    response = test_client.get('/admin/rides', follow_redirects=True)
    assert response.status_code == 200
    assert b"Bike Statistics:" in response.data

def test_filter_no_searchbar_admin_rides(test_client, init_database):
    # add rides

    ride1 = Ride(bike_id = 100, user_id = "2", completed_ride = False, positive_rating = False)
    db.session.add(ride1)

    ride3 = Ride(bike_id = 100, user_id = "2", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=10), duration = datetime.timedelta(hours=2), completed_ride = True, positive_rating = False)
    db.session.add(ride3)

    ride4 = Ride(bike_id = 101, user_id = "3", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=10), completed_ride = False, positive_rating = False)
    db.session.add(ride4)

    ride5 = Ride(bike_id = 102, user_id = "1", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=60), duration = datetime.timedelta(hours=20), completed_ride = True, positive_rating = True)
    db.session.add(ride5)

    ride6 = Ride(bike_id = 102, user_id = "2", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=3), completed_ride = False, positive_rating = False)
    db.session.add(ride6)
    db.session.commit()

    response = test_client.post('/admin/rides/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "", "date": 7, "overtime": False, "completed": True},
                                follow_redirects=True)
    assert response.status_code == 200
    
    # checks if the json contains rides in the right order
    data = response.json
    db_data = db.session.scalars(sqla.select(Ride)
                                 .where(Ride.completed_ride == True)
                                 .where(Ride.ride_date >= datetime.datetime.now(timezone.utc) - datetime.timedelta(days=int(7)))
                                 .order_by(Ride.ride_date)).all()
    for i in range(len(data['result'])):
        # checks primary key of each ride to ensure it is the same ride
        assert data['result'][i]['bike_id'] == db_data[i].bike_id
        assert data['result'][i]['timestamp'] == re.sub(r"0(?=.:)", "", db_data[i].ride_date.strftime("%b %-d, %Y at %I:%M %p"))
        assert data['result'][i]['user_name'] == db.session.get(User, db_data[i].user_id).get_first_name()

    # checks the page data is accurate
    assert data['num_reports'] == 0
    assert data['rides_month'] == 5
    assert data['broken_bikes'] == []
    assert data['bikes_out'] == 1

def test_filter_searchbar_admin_rides(test_client, init_database):
    # add rides
    
    ride1 = Ride(bike_id = 100, user_id = "2", completed_ride = False, positive_rating = False)
    db.session.add(ride1)

    ride3 = Ride(bike_id = 100, user_id = "2", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=10), duration = datetime.timedelta(hours=2), completed_ride = True, positive_rating = False)
    db.session.add(ride3)

    ride4 = Ride(bike_id = 101, user_id = "3", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=10), completed_ride = False, positive_rating = False)
    db.session.add(ride4)

    ride5 = Ride(bike_id = 102, user_id = "1", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=60), duration = datetime.timedelta(hours=20), completed_ride = True, positive_rating = True)
    db.session.add(ride5)

    ride6 = Ride(bike_id = 102, user_id = "2", ride_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=3), completed_ride = False, positive_rating = False)
    db.session.add(ride6)
    db.session.commit()

    response = test_client.post('/admin/rides/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "102", "date": 0, "overtime": True, "completed": True},
                                follow_redirects=True)
    assert response.status_code == 200
    
    # checks if the json contains rides in the right order
    data = response.json
    db_data = db.session.scalars(sqla.select(Ride)
                                 .where(Ride.bike_id == db.session.scalars(sqla.select(Bike).where(Bike.name.contains("102"))).first().get_id())
                                 .where(Ride.user_id == db.session.scalars(sqla.select(User).where(User.email == "gompei@wpi.edu")).first().get_id())).first()
    assert len(data['result']) == 1
    # checks primary key of each ride to ensure it is the same ride
    assert data['result'][0]['bike_id'] == db_data.bike_id
    assert data['result'][0]['timestamp'] == re.sub(r"0(?=.:)", "", db_data.ride_date.strftime("%b %-d, %Y at %I:%M %p"))
    assert data['result'][0]['user_name'] == db.session.get(User, db_data.user_id).get_first_name()

    # checks the page data is accurate
    assert data['num_reports'] == 0
    assert data['rides_month'] == 5
    assert data['broken_bikes'] == []
    assert data['bikes_out'] == 1





def test_get_admin_reports(test_client, init_database):
    response = test_client.get('/admin/reports', follow_redirects=True)
    assert response.status_code == 200
    assert b"Maintenance Reports" in response.data

def test_filter_no_searchbar_admin_reports(test_client, init_database):
    # add reports

    report1 = Report(bike_id = 101,
                     user_id = 1,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 101, user 1, cat 1',
                     completed = False)
    report2 = Report(bike_id = 102,
                     user_id = 2,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 102, user 2, cat 1',
                     completed = False)
    report3 = Report(bike_id = 101,
                     user_id = 3,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 101, user 3, cat 1',
                     completed = True)
    report4 = Report(bike_id = 102,
                     user_id = 1,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 0,
                     description = 'bike 102, user 1, cat 0',
                     completed = True)
    db.session.add(report1)
    db.session.add(report2)
    db.session.add(report3)
    db.session.add(report4)

    db.session.commit()
    response = test_client.post('/admin/reports/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "", "category": 0, "completed": True},
                                follow_redirects=True)
    assert response.status_code == 200
    
    # checks if the json contains rides in the right order
    data = response.json
    db_data = db.session.scalars(sqla.select(Report)
                                 .where(Report.category == 0)
                                 .where(Report.completed == True)).all()
    for i in range(len(data['result'])):
        # checks primary key of each ride to ensure it is the same ride
        assert data['result'][i]['bike_id'] == db_data[i].bike_id
        assert data['result'][i]['user_id'] == db_data[i].user_id
        assert data['result'][i]['timestamp'] == db_data[i].timestamp.isoformat()

def test_filter_searchbar_admin_reports(test_client, init_database):
    # add rides

    report1 = Report(bike_id = 101,
                     user_id = 1,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 101, user 1, cat 1',
                     completed = False)
    report2 = Report(bike_id = 102,
                     user_id = 2,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 102, user 2, cat 1',
                     completed = False)
    report3 = Report(bike_id = 101,
                     user_id = 3,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 1,
                     description = 'bike 101, user 3, cat 1',
                     completed = True)
    report4 = Report(bike_id = 102,
                     user_id = 1,
                     timestamp = datetime.datetime.now(timezone.utc),
                     category = 0,
                     description = 'bike 102, user 1, cat 0',
                     completed = True)
    db.session.add(report1)
    db.session.add(report2)
    db.session.add(report3)
    db.session.add(report4)

    db.session.commit()
    response = test_client.post('/admin/reports/filter', 
                                headers = {'Content-type': 'application/json'},
                                json={"search": "WPI10", "category": 1, "completed": False},
                                follow_redirects=True)
    assert response.status_code == 200
    
    # checks if the json contains rides in the right order
    data = response.json
    db_data = db.session.scalars(sqla.select(Report)
                                 .where(Report.category == 1)
                                 .where(Report.completed == False)).all()
    for i in range(len(data['result'])):
        # checks primary key of each ride to ensure it is the same ride
        assert data['result'][i]['bike_id'] == db_data[i].bike_id
        assert data['result'][i]['user_id'] == db_data[i].user_id
        assert data['result'][i]['timestamp'] == db_data[i].timestamp.isoformat()


def test_admin_map_response_data(test_client, init_database):
    response = test_client.post('/admin/assets/mapDetails',
                                data=dict(),
                                follow_redirects=True)

    # Valid response
    assert response.status_code == 200

    # Normal map data
    bike2 = db.session.get(Bike, 100)
    assert bike2.name in str(response.data)
    station1 = db.session.get(Station, 1)
    assert station1.name in str(response.data)

    # Admin map data
    bike4 = db.session.get(Bike, 110)
    assert bike4.name in str(response.data)
    assert b'pin_gray' in response.data


def test_admin_assets_page(test_client, init_database):
    response = test_client.get('/admin/assets', follow_redirects=True)

    assert response.status_code == 200

    # Test bike shown and admin avaliability
    bike2 = db.session.get(Bike, 100)
    assert bike2.name in str(response.data)

    assert b'Unavailable' in response.data
    assert b'scanner' in response.data

    # Page bike data is updated via javscript based on map zoom, so test_admin_map_response_data handles testing interactivity


def test_update_account(test_client, init_database):
    user = db.session.get(User, 1)
    login_user(user)
    assert user.preferred_name == None
    assert user.phone == None

    response = test_client.post('/auth/update', data=dict(phone='832 420 6769', preferred='Katelle Africa', unsubscribe_notifications=False), follow_redirects=True)

    user = db.session.get(User, current_user.id)

    print(response.data)
    assert user.phone == '8324206769'
    assert user.preferred_name == 'Katelle Africa'
    assert user.get_name() == "Katelle Africa"
    assert user.get_first_name() == "Gompei"
