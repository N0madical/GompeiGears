import sys
from datetime import datetime, timezone, timedelta
from flask import send_from_directory, redirect, request, url_for, current_app, flash, jsonify
import sqlalchemy as sqla
from flask_login import login_required, current_user, login_user

from app import db, get_nav_pages, ms_login, vapid_public_key
from app.main.models import User, Bike, Station, Ride, Location, Report, Fleet
from app.main.forms import RentalForm, EndRentalForm, SetLockForm, CreateReportForm
from app.main import main_blueprint as bp_main

# Render_template handler
from flask import render_template as real_render_template
def render_template(*args, **kwargs):
    return real_render_template(*args, **kwargs, pages=get_nav_pages(current_user.is_authenticated and current_user.is_admin))

@bp_main.route('/', methods=['GET', 'POST'])
@bp_main.route('/index', methods=['GET', 'POST'])
def index():
    # if current_user.is_authenticated:
    #     print("already logged in")
    #     return redirect(url_for("main.home"))
    return render_template('index.html', title="Home")

@bp_main.route('/manifest.json')
def serve_manifest():
    return send_from_directory(current_app.static_folder, 'manifest.json', mimetype='application/manifest+json')

@bp_main.route('/home')
@login_required
def home():
    return render_template('home.html', title="Renter Home")

@bp_main.route('/help')
def user_help():
    return redirect("https://www.wpi.edu/offices/sustainability/campus-operations/transportation-options/gompeis-gears-bike-share")

@bp_main.route('/rental/manage', methods=['GET'])
def managerental():
    ride = current_user.get_current_ride()
    if ride is not None:
        return redirect(url_for("main.rental", bike_id=ride.bike.id))
    
    flash("You are not currently renting a bike")
    return redirect(url_for("main.home"))

@bp_main.route('/rental/<bike_id>', methods=['GET'])
@login_required
def rental(bike_id):
    rform = RentalForm()
    eform = EndRentalForm()
    lform = SetLockForm()

    # check if user's account is locked
    if current_user.locked:
        flash("Your account is locked")
        return redirect(url_for("main.home"))

    # check if user is already renting a bike other than this one
    ride = current_user.get_current_ride()
    if ride is not None and ride.bike.id != int(bike_id):
        flash("You are already renting a bike")
        return redirect(url_for("main.home"))

    bike = db.session.get(Bike, bike_id)

    # check if bike is available for rent
    if bike is None or (bike.station is None and ride is None) or not bike.available:
        flash("Bike is not available")
        return redirect(url_for("main.home"))

    return render_template('rental.html', title="Bike Rental", ride=ride, bike=bike, rform=rform, eform = eform, lform = lform, agreement=(None if current_user.signed_agreements else Fleet.get_fleet().user_agreement), utc=timezone.utc, vapid_public_key=vapid_public_key, has_notification_keys=current_user.has_notification_keys())

@bp_main.route('/rental/<bike_id>/start', methods=['POST'])
@login_required
def startride(bike_id):
    rform = RentalForm()

    # check if user's account is locked
    if current_user.locked:
        flash("Your account is locked")
        return jsonify({'message': 'error-account-locked', 'redirect': url_for('main.home')})

    # check if user is already renting a bike
    ride = current_user.get_current_ride()
    if ride is not None:
        # don't show this message if the correct bike is already selected
        if ride.bike.id != int(bike_id):
            flash("You are already renting a bike")
        
        return jsonify({'message': 'error-already-renting', 'redirect': url_for('main.rental', bike_id=ride.bike.id)})

    bike = db.session.get(Bike, bike_id)

    # check if bike is available for rent
    if bike is None or bike.station is None or not bike.available:
        flash("Bike is not available")
        return jsonify({'message': 'error-bike-unavailable', 'redirect': url_for('main.home')})

    if rform.validate_on_submit():
        if rform.notification_endpoint.data and rform.notification_p256dh_key.data and rform.notification_auth_key.data:
            current_user.set_notification_keys(rform.notification_endpoint.data, rform.notification_p256dh_key.data, rform.notification_auth_key.data)

        # check if user has agreed to the user agreement
        if not (current_user.signed_agreements or rform.signed_agreements.data):
            return jsonify({'message': 'error-user-agreement'})
        
        # if the user just signed the user agreement, save that
        if rform.signed_agreements.data:
            current_user.signed_agreements = True
            db.session.add(current_user)
            db.session.commit()

        # check if user is close enough to station
        location = bike.get_current_location()
        print(location.distance_from(Location(float(rform.lat.data), float(rform.long.data))))
        if not (bike.station.contains(Location(float(rform.lat.data), float(rform.long.data))) or (location is not None and location.distance_from(Location(float(rform.lat.data), float(rform.long.data))) < 60)):
            return jsonify({'message': 'error-too-far-bike'})

        # update bike status and create new ride
        bike.station = None
        ride = Ride(bike_id=bike.id, user_id=current_user.id, completed_ride=False, positive_rating=False)
        db.session.add(ride)
        db.session.add(bike)
        db.session.commit()
        return jsonify({'message': 'success', 'ride_date': ride.ride_date.replace(tzinfo=timezone.utc).timestamp() * 1000})

    return jsonify({'message': 'error-form-invalid'})

@bp_main.route('/rental/<bike_id>/end', methods=['POST'])
@login_required
def endride(bike_id):
    eform = EndRentalForm()

    ride = current_user.get_current_ride()

    if ride is None and current_user.is_admin:
        bike = db.session.get(Bike, int(bike_id))
        ride = bike.get_current_ride()

        if ride is None:
            return jsonify({'message': 'error-no-ride'})

    if ride is None:
        flash('You are not currently riding a bike')
        return jsonify({'message': 'error-no-ride', 'redirect': url_for('main.home')})
    if ride.bike.id != int(bike_id):
        return jsonify({'message': 'error-wrong-ride', 'redirect': url_for('main.rental', bike_id=ride.bike.id)})

    bike = ride.bike

    if eform.validate_on_submit():
        if not bike.locked:
            return jsonify({'message': 'error-not-locked'})

        stations = db.session.query(Station).all()
        nearby_station = None
        for station in stations:
            if station.contains(Location(float(eform.lat.data), float(eform.long.data))):
                nearby_station = station
                break

        if nearby_station is None:
            return jsonify({'message': 'error-too-far-station'})

        ride.completed_ride = True
        ride.positive_rating = eform.rating.data == 'positive'
        ride.duration = datetime.now(timezone.utc) - ride.ride_date.replace(tzinfo=timezone.utc)
        bike.station_id = nearby_station.id
        db.session.add(ride)
        db.session.add(bike)
        db.session.commit()

        if eform.report_issue.data:
            flash("Bike returned")
            return jsonify({'message': 'success', 'redirect': url_for('main.create_report', the_bike_id = bike.get_id())})
        else:
            flash("Bike returned")
            return jsonify({'message': 'success', 'redirect': url_for('main.home')})

    return jsonify({'message': 'error-form-invalid'})

@bp_main.route('/rental/<bike_id>/setlock', methods=['POST'])
@login_required
def setlock(bike_id):
    lform = SetLockForm()

    ride = current_user.get_current_ride()

    if ride is None and not current_user.is_admin:
        flash('You are not currently riding a bike')
        return jsonify({'message': 'error-no-ride', 'redirect': url_for('main.home')})
    if ride and ride.bike.id != int(bike_id):
        return jsonify({'message': 'error-wrong-ride', 'redirect': url_for('main.rental', bike_id=ride.bike.id)})

    bike = ride.bike if ride else db.session.get(Bike, int(bike_id))

    if lform.validate_on_submit():
        bike.locked = lform.state.data == 'locked'
        # eventually do something here to actually lock/unlock bike, for now we just update the database
        db.session.add(bike)
        db.session.commit()

        return jsonify({'message': 'success', 'lock_status': bike.locked})
    else:
        return jsonify({'message': 'error-form-invalid'})


@bp_main.route('/mapDetails', methods=['POST'])
@login_required
def get_map_details():
    # Get all bikes that have a location in a list
    bikes = db.session.scalars(sqla.select(Bike).where(Bike.station_id != None).where(Bike.available == True)).all()
    bike_list = [bike.get_details() if bike.get_current_location() else {} for bike in bikes]

    # Get all stations in a list
    stations = db.session.scalars(sqla.select(Station)).all()
    station_list = [station.get_details() for station in stations]

    pin_red = url_for('static', filename='pins/pin_red.svg')
    pin_orange = url_for('static', filename='pins/pin_orange.svg')

    return jsonify({'message':'success', 'bikes':bike_list, 'stations':station_list, 'pin_red':pin_red, 'pin_orange':pin_orange})


@bp_main.route('/report/create', methods=['GET', 'POST'])
def create_report():
    rform = CreateReportForm()
    if request.method == 'POST':
        if rform.validate_on_submit():
            the_report = Report(bike_id = rform.bike_id.data.get_id(),
                                user_id = current_user.get_id(),
                                timestamp = datetime.now(timezone.utc),
                                category = rform.category.data,
                                description = rform.description.data,
                                completed = False)
            print(db.session.scalars(sqla.select(Report)).all())
            db.session.add(the_report)
            db.session.commit()
            flash("Your report has been Submitted")
            return redirect(url_for('main.home'))
    elif request.method == 'GET':
        the_bike_id = request.args.get('the_bike_id')
        if the_bike_id is not None:
            the_bike = db.session.scalars(sqla.select(Bike).where(Bike.id == the_bike_id)).first()
            rform.bike_id.data = the_bike
    else:
        pass
    

    return render_template('create_report.html', title="Create Report", form = rform, fleet = Fleet.get_fleet())