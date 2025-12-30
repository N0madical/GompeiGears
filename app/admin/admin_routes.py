import math
import re
from tokenize import String

from app.admin import admin_blueprint as bp_admin
import datetime
import time
from datetime import timedelta, timezone
from flask import redirect, url_for, flash, jsonify, request
import sqlalchemy as sqla
from flask_login import current_user
import json
from sqlalchemy import or_, join, and_

from app import db, ms_login, get_nav_pages, moment
from app.main.models import User, Bike, Station, Ride, Location, Location, Report, Fleet
from app.admin.admin_forms import UserSortForm, BikeSortForm, FleetEditForm, StationEditForm, StationDeleteForm, ReportSortForm, MessagingForm
from app.main.forms import SetLockForm, EndRentalForm
from app.main.routes import render_template

def admin_required(func):
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated and current_user.is_admin:
            return func(*args, **kwargs)
        else:
            flash("You need admin permission to access this page", "error")
            return redirect(url_for("main.index"))
    wrapper.__name__ = func.__name__
    return wrapper

@bp_admin.route('/admin', methods=['GET', 'POST'])
@admin_required
def index():
    return redirect(url_for("admin.load_admin_rides"))
    

@bp_admin.route('/admin/rides', methods=['GET'])
@admin_required
def load_admin_rides():
    sform = BikeSortForm()
    return render_template('admin_index.html',
                           title="Completed Rides",
                           form = sform)

@bp_admin.route('/admin/rides/filter', methods=['POST'])
@admin_required
def filter_admin_rides():
    data = request.get_json()
    search_data = data['search']
    my_date = data['date'] #how many days old of dates to accept
    overtime = data['overtime'] #boolean
    comp_data = int(data['completed']) == 1 #integer
    results = sqla.select(Ride).join(User).join(Bike).where(Ride.completed_ride == comp_data)
    results = db.session.scalars(results
                                 .where(
                                    or_(User.name.contains(search_data),
                                        User.email.contains(search_data),
                                        Bike.name.contains(search_data)))
                                 .where(
                                    or_(Ride.ride_date >= datetime.datetime.now(timezone.utc) - datetime.timedelta(days=int(my_date)),
                                        int(my_date) == 0))
                                .where(or_(overtime == False,
                                    and_(comp_data == True,
                                        Ride.duration >= datetime.timedelta(hours=12)),
                                    and_(comp_data == False,
                                        Ride.ride_date <= datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=12))))
                                .order_by(Ride.ride_date)).all()
    result = []
    

    for r in results:
        # handle duration of ongoing rides
        ride_duration = r.duration if r.duration else (datetime.datetime.now() - r.ride_date)
        hours, seconds = divmod(ride_duration.seconds + (ride_duration.days*86400), 3600)
        the_duration = (str(hours) + " hours, " if hours > 0 else "") + str(round(seconds/60)) + " minutes"
        end_time = r.ride_date + ride_duration
        result.append({'user_name': r.user.get_first_name(),
                    'bike_id': r.bike_id,
                    'timestamp': re.sub(r"0(?=.:)", "", r.ride_date.strftime("%b %-d, %Y at %I:%M %p")),
                    'start_time' : r.ride_date.isoformat(),
                    'end_time' : end_time.isoformat(),
                    'user_email': r.user.get_email(),
                    'bike': r.bike.get_name(),
                    'duration': str(the_duration).split('.', 2)[0],
                    'pos_rating': r.positive_rating})
    
    # overview data
    num_reports = len(db.session.scalars(sqla.select(Report).where(Report.completed == False)).all())
    num_trips = len(db.session.scalars(sqla.select(Ride).join(Bike).where(Bike.available == True).where(Ride.completed_ride == False)).all())
    broken = db.session.scalars(sqla.select(Bike.name).select_from(join(Bike, Report)).distinct()).all()
    rides_month = len(db.session.scalars(sqla.select(Ride).where(Ride.ride_date > datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30))).all())
    reports_month = len(db.session.scalars(sqla.select(Report).where(Report.timestamp > datetime.datetime.now() - datetime.timedelta(days=30))).all())
    bikes_out = len(db.session.scalars(sqla.select(Bike).where(Bike.available == False)).all())

    return jsonify({
        'message': "success", 'result': result, 'num_reports': num_reports,
        'num_trips': num_trips, 'broken_bikes': broken, 'rides_month': rides_month,
        'reports_month': reports_month, 'bikes_out': bikes_out
    })

@bp_admin.route('/admin/rides/path', methods=['POST'])
@admin_required
def get_ride_path():
    data = request.get_json()
    bike_id = int(data['bike_id'])
    start_time = int(datetime.datetime.fromisoformat(data['start_time']).timestamp())
    end_time = int(datetime.datetime.fromisoformat(data['end_time']).timestamp()) + 18900 # Add 15 minutes to end time to account for tag ping time
    location_icon = url_for('static', filename='pins/location.svg')
    locations = db.session.scalars(sqla.select(Location)
                                   .where(Location.bike_id == bike_id)
                                   .where(Location.timestamp >= start_time)
                                   .where(Location.timestamp <= end_time)
                                   .order_by(Location.timestamp)).all()
    for location in locations: print(datetime.datetime.fromtimestamp(location.timestamp))
    location_list = list(map(lambda x: x.get_coords(), locations))
    distance = round(sum([math.sqrt((y[0] - x[0])**2 + (y[1] - x[1])**2) for x, y in zip(location_list[:-1], location_list[1:])]) * 60, 2)
    return jsonify({'message':'success', 'path':location_list, 'location_icon':location_icon, 'distance':distance})

@bp_admin.route('/admin/fleet', methods=['GET', 'POST'])
@admin_required
def fleet_settings():
    fleet = Fleet.get_fleet()
    fform = FleetEditForm(obj=fleet)

    if fform.validate_on_submit():
        if fleet.user_agreement != fform.user_agreement.data:
            for user in db.session.scalars(sqla.select(User)):
                user.signed_agreements = False
                db.session.add(user)

        fleet.user_agreement = fform.user_agreement.data
        fleet.contact_email = fform.contact_email.data
        fleet.contact_phone = fform.contact_phone.data

        db.session.add(fleet)
        db.session.commit()

        flash("Updated Fleet Settings")
    
    stations = db.session.scalars(sqla.select(Station))

    return render_template('admin_fleet_settings.html',
        title="Fleet Settings",
        form = fform,
        stations = stations)

@bp_admin.route('/admin/fleet/station/<id>', methods=['GET', 'POST'])
@admin_required
def station_edit(id):
    try:
        station = db.session.get(Station, int(id))
    except:
        if id == "new":
            station = Station(lat1=42.274420293596066,long1=-71.80782654034687,lat2=42.27452029359607,long2=-71.80782654034687,lat3=42.27452029359607,long3=-71.80772654034686,lat4=42.274420293596066,long4=-71.80772654034686)
        else:
            flash("Station not found")
            return redirect(url_for('admin.fleet_settings'))

    sform = StationEditForm(obj=station)
    dform = StationDeleteForm()

    if sform.validate_on_submit():
        station.name = sform.name.data
        station.lat1 = float(sform.lat1.data)
        station.long1 = float(sform.long1.data)
        station.lat2 = float(sform.lat2.data)
        station.long2 = float(sform.long2.data)
        station.lat3 = float(sform.lat3.data)
        station.long3 = float(sform.long3.data)
        station.lat4 = float(sform.lat4.data)
        station.long4 = float(sform.long4.data)

        db.session.add(station)
        db.session.commit()

        flash("Updated station {}".format(station.name))
        return redirect(url_for('admin.fleet_settings'))

    return render_template('admin_station_edit.html',
        title="Edit Station",
        form = sform,
        dform = dform,
        id = id)

@bp_admin.route('/admin/fleet/station/<id>/delete', methods=['POST'])
@admin_required
def station_delete(id):
    try:
        station = db.session.get(Station, int(id))
    except:
        flash("Station not found")
        return redirect(url_for('admin.fleet_settings'))

    dform = StationDeleteForm()

    if dform.validate_on_submit():
        if len(station.get_bikes()) > 0:
            flash("Cannot delete station currently containing bikes")
            return redirect(url_for("admin.station_edit", id=id))

        db.session.delete(station)
        db.session.commit()

        flash("Deleted station {}".format(station.name))
        return redirect(url_for('admin.fleet_settings'))

    flash("Failed to delete station")
    return redirect(url_for("admin.station_edit", id=id))


@bp_admin.route('/admin/assets')
@admin_required
def assets():
    lform = SetLockForm()
    eform = EndRentalForm()

    return render_template('assets.html', title="Assets", lform = lform, eform=eform)


@bp_admin.route('/admin/assets/mapDetails', methods=['POST'])
@admin_required
def get_map_details():
    # Get all bikes that have a location in a list
    bikes = db.session.scalars(sqla.select(Bike)).all()
    bike_list = [bike.get_details() if bike.get_current_location() else {} for bike in bikes]

    # Get all stations in a list
    stations = db.session.scalars(sqla.select(Station)).all()
    station_list = [station.get_details() for station in stations]

    pin_red = url_for('static', filename='pins/pin_red.svg')
    pin_white = url_for('static', filename='pins/pin0.svg')
    pin_orange = url_for('static', filename='pins/pin_orange.svg')
    pin_gray = url_for('static', filename='pins/pin_gray.svg')

    return jsonify({'message':'success', 'bikes':bike_list, 'stations':station_list,
                    'pin_red':pin_red, 'pin_white':pin_white, 'pin_orange':pin_orange, 'pin_gray':pin_gray})


@bp_admin.route('/admin/reports', methods=['GET'])
@admin_required
def load_admin_reports():
    sform = ReportSortForm()
    return render_template('admin_report.html', title="Reports", form = sform)

@bp_admin.route('/admin/reports/filter', methods=['POST'])
@admin_required
def filter_admin_reports():
    data = request.get_json()
    search_data = data['search']
    cat_data = data['category']
    comp_data = int(data['completed']) == 1
    results = db.session.scalars(sqla.select(Report)
                                 .join(User).join(Bike)
                                 .where(Report.completed == comp_data)
                                 .where(or_(Report.category == cat_data, cat_data == '0'))
                                 .where(or_(User.name.contains(search_data),
                                                        User.email.contains(search_data),
                                                        Bike.name.contains(search_data)))
                                 ).all()
    result = []
    
    for r in results:
        result.append({'name': r.user.get_first_name(),
                    'bike_id': r.bike_id,
                    'user_id': r.user_id,
                    'timestamp': r.timestamp.isoformat(),
                    'email': r.user.get_email(),
                    'bike': r.bike.get_name(),
                    'cat': r.category,
                    'desc': r.description,
                    'comp': r.completed,
                    'avail': r.bike.available})
    return jsonify({
        'message': "success",
        'result': result
    })

@bp_admin.route('/admin/reports/toggle/bike', methods=['POST'])
@admin_required
def report_toggle_bike_availability():
    the_bike_id = request.args.get('bike_id')
    the_bike = db.session.get(Bike, the_bike_id)
    the_bike.available = False if the_bike.available else True
    db.session.add(the_bike)
    db.session.commit()

    return jsonify({'message': 'success', 'available': the_bike.available})


@bp_admin.route('/admin/reports/toggle/report', methods=['POST'])
@admin_required
def report_toggle_report_completion():
    the_bike_id = request.args.get('bike_id')
    the_user_id = request.args.get('user_id')
    the_timestamp = datetime.datetime.fromisoformat(request.args.get('timestamp'))
    the_report = db.session.scalars(sqla.select(Report).where(Report.user_id == the_user_id).where(Report.bike_id == the_bike_id).where(Report.timestamp == the_timestamp)).first()
    the_report.completed = False if the_report.completed else True
    db.session.add(the_report)
    db.session.commit()

    return jsonify({'message': 'completion toggled'}) 

@bp_admin.route('/admin/users', methods=['GET'])
@admin_required
def load_admin_users():
    uform = UserSortForm()
    return render_template('admin_users.html', title="Users", form = uform)

@bp_admin.route('/admin/users/filter', methods=['POST'])
@admin_required
def filter_admin_users():
    data = request.get_json()
    search_data = data['search']
    is_admin = data['admin']
    is_banned = data['banned']
    results = db.session.scalars(sqla.select(User))
    print(is_banned)
    print(search_data)
    if search_data == "":
        results = sqla.select(User)
    else:
        results = sqla.select(User).where(or_(
            User.name.contains(search_data),
            User.email.contains(search_data)))
    results = results.where(or_(is_banned == False, User.locked == is_banned)).where(or_(is_admin == False, User.is_admin == is_admin))
    results = results.order_by(User.name)
    results = db.session.scalars(results).all()
    for r in results:
        print(r)
    result = []
    
    for r in results:
        result.append({'name': r.get_first_name(),
                    'user_id': r.get_id(),
                    'email': r.get_email(),
                    'admin': r.is_admin,
                    'banned': r.locked,
                    'subscribed': r.has_notification_keys()})
    return jsonify({
        'message': "success",
        'result': result
    })

@bp_admin.route('/admin/users/toggle/admin', methods=['GET', 'POST'])
@admin_required
def user_toggle_admin():
    the_user_id = request.args.get('user_id')
    the_user = db.session.get(User, the_user_id)
    the_user.is_admin = False if the_user.is_admin else True
    db.session.add(the_user)
    db.session.commit()

    return jsonify({'message': 'is_admin toggled'})

@bp_admin.route('/admin/users/toggle/banned', methods=['GET', 'POST'])
@admin_required
def user_toggle_banned():
    the_user_id = request.args.get('user_id')
    the_user = db.session.get(User, the_user_id)
    the_user.locked = False if the_user.locked else True
    db.session.add(the_user)
    db.session.commit()

    return jsonify({'message': 'is_banned toggled'})
    
@bp_admin.route('/admin/messaging', methods=['GET', 'POST'])
@admin_required
def messaging():
    form = MessagingForm()

    if form.validate_on_submit():
        no_keys = 0
        success = 0
        fail = 0

        recipients = form.recipients.data

        if form.recipients_all.data:
            recipients = db.session.scalars(sqla.select(User)).all()

        for recipient in recipients:
            if recipient.has_notification_keys():
                if not form.mock.data and recipient.send_notification(json.dumps(dict(title=form.subject.data, body=form.body.data))):
                    success += 1
                else:
                    fail += 1
            else:
                no_keys += 1
        
        if success == 0 and fail == 0 and no_keys == 0:
            flash("No recipients selected")
            return render_template('messaging.html',
                title="Messaging",
                form = form)
        
        if form.mock.data:
            return jsonify(dict(recipients=list(map(lambda u : u.id, recipients)), no_keys=no_keys))
        
        flash("Notified {} users ({} failed, {} not subscribed)".format(success, fail, no_keys))

    return render_template('messaging.html',
        title="Messaging",
        form = form)
    
