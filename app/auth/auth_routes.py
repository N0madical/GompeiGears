from flask import Flask, redirect, url_for, flash, make_response
from app.auth import auth_blueprint as bp_auth
from app import ms_login, get_nav_pages, login, db
from app.auth.auth_forms import AccountForm
from app.main.models import User
from app.main.routes import render_template
from flask_login import login_required, login_user, logout_user, current_user
import sqlalchemy as sqla

@login.user_loader
def load_user(id):
    return db.session.get(User, id)

# For testing purposes ONLY
@bp_auth.route('/autologin', methods=['GET'])
def autologin():
    print("auto logging into user 1")
    user = db.session.get(User, "1")
    if not user:
        user = User(id="1", email="gompeiTester@wpi.edu", name="Pi, Gompei")
    login_user(user)
    user.is_admin = True
    db.session.add(current_user)
    db.session.commit()
    return redirect(url_for('main.home'))

@bp_auth.route("/account", methods=["GET"])
@ms_login.login_required
def account(*, context):
    if not current_user.is_authenticated or current_user.id != context['user'].get("oid"):
        print("re-logging")
        user = db.session.scalars(sqla.select(User).filter(User.id == context['user'].get("oid"))).one_or_none()
        if user is None:
            new_user = User(id=context['user'].get("oid"), name=context['user'].get("name"), email=context['user'].get("preferred_username"))
            login_user(new_user)
            db.session.add(new_user)
            db.session.commit()
            user = new_user
        else:
            login_user(user)
        print(user)

    form = AccountForm()
    form.preferred.data = current_user.preferred_name
    if current_user.phone is not None:
        form.phone.data = "({}) {}-{}".format(current_user.phone[0:3], current_user.phone[3:6], current_user.phone[6:10])

    return render_template(
        'account.html',
        user=context['user'],
        title="Account",
        form=form,
        has_notification_keys=current_user.has_notification_keys()
    )

@bp_auth.route("/auth/update", methods=["POST"])
@login_required
def update():
    form = AccountForm()

    if form.validate_on_submit():
        user = db.session.get(User, current_user.id)
        user.preferred_name = form.preferred.data
        if form.phone.data is not None:
            user.phone = form.phone.data.national_number
        else:
            user.phone = None
        if form.unsubscribe_notifications.data:
            user.clear_notification_keys()
        db.session.add(user)
        db.session.commit()
        flash('Account updated successfully!')
    else:
        print(form.errors)

    return redirect(url_for("auth.account"))

@bp_auth.route("/auth/logoutFlask", methods=["GET"])
@login_required
def logout():
    print("Logging User Out")
    logout_user()
    return redirect(url_for("identity.logout"))