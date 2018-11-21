import os
from flask import Flask, render_template, request, flash, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from models import db, Users, Polls, Topics, Options, UserPolls
from flask_admin import Admin
from admin import AdminView, TopicView
from sqlalchemy import exc
import sys
# import tkinter
# from tkinter import messagebox, Tk
from pymsgbox import *
# Blueprints
from api.api import api
import pyqrcode
# celery factory
import config
from celery import Celery
from io import BytesIO


def make_celery(votr):
    celery = Celery(
        votr.import_name, backend=votr.config['CELERY_RESULT_BACKEND'],
        broker=votr.config['CELERY_BROKER']
    )
    celery.conf.update(votr.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with votr.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask

    return celery

votr = Flask(__name__)

votr.register_blueprint(api)

# load config from the config file we created earlier
if os.getenv('APP_MODE') == "PRODUCTION":
    votr.config.from_object('production_settings')
else:
    votr.config.from_object('config')

db.init_app(votr)  # Initialize the database
db.create_all(app=votr)  # Create the database

migrate = Migrate(votr, db, render_as_batch=True)

# create celery object
celery = make_celery(votr)

admin = Admin(votr, name='Dashboard', index_view=TopicView(Topics, db.session, url='/admin', endpoint='admin'))
admin.add_view(AdminView(Users, db.session))
admin.add_view(AdminView(Polls, db.session))
admin.add_view(AdminView(Options, db.session))
admin.add_view(AdminView(UserPolls, db.session))


@votr.route('/')
def home():
    return render_template('index.html')


@votr.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        # get the user details from the form
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        usergroup = request.form['usergroup']

        # hash the password
        password = generate_password_hash(password)

        user = Users(email=email, username=username, password=password, user_group=usergroup)

        # db.session.add(user)
        # db.session.commit()

        try:
            db.session.add(user)
            db.session.commit()
        except exc.SQLAlchemyError as e:
            #tkMessageBox.showerror("Error", "User Already Exists")
            # root = Tk()
            # root.withdraw()
            # messagebox.showerror("Error", str(e))
            errormsg = "Error" + str(e)
            alert(text=errormsg, title='Error', button='OK')


        # return redirect(url_for('home'))
        print('hello')
        session['username'] = request.form['username']
        # print (redirect(url_for('two_factor_setup')))
        return redirect(url_for('two_factor_setup'))
        flash('Thanks for signing up please login')
    # it's a GET request, just render the template
    #print(render_template('signup.html'))
    return render_template('signup.html')


# Function for two factor setup
@votr.route('/twofactor')
def two_factor_setup():
    print('inside')
    print (session)
    if 'username' not in session:
        return redirect(url_for('home'))
    user = Users.query.filter_by(username=session['username']).first()
    if user is None:
        return redirect(url_for('home'))
    # since this page contains the sensitive qrcode, make sure the browser
    # does not cache it
    return render_template('two-factor-setup.html'), 200, {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'}


# Function to generate QR Code
@votr.route('/qrcode')
def qrcode():
    if 'username' not in session:
        abort(404)
    user = Users.query.filter_by(username=session['username']).first()
    if user is None:
        abort(404)

    # for added security, remove username from session
    del session['username']

    # render qrcode for FreeTOTP
    url = pyqrcode.create(user.get_totp_uri())
    stream = BytesIO()
    url.svg(stream, scale=5)
    return stream.getvalue(), 200, {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'}


@votr.route('/login', methods=['POST'])
def login():
    # we don't need to check the request type as flask will raise a bad request
    # error if a request aside from POST is made to this url

    username = request.form['username']
    password = request.form['password']
    token = request.form['token']
    print("------------\nToken-----------",token)
    # search the database for the User
    user = Users.query.filter_by(username=username).first()
    print('Votr_user', user)
    print('User_passwoord',user.password)
    # if form.validate_on_submit():
    #     user = User.query.filter_by(username=form.username.data).first()
    #     if user is None or not user.verify_password(form.password.data) or \
    #             not user.verify_totp(form.token.data):
    #         flash('Invalid username, password or token.')
    #         return redirect(url_for('login'))

    if user:
        
        password_hash = user.password
        # submitted_token = user.token
        print(check_password_hash(password_hash, password))
        print(user.verify_totp(token))
        if check_password_hash(password_hash, password) and user.verify_totp(token):
            # The hash matches the password in the database log the user in
            session['user'] = username
            # user_type = session['user']
            # print (session, 'lol', type(session))
            # print(user_type)
            flash('Login was succesfull')
        else:
            print('lol')
    else:
        # user wasn't found in the database
        flash('Username or password is incorrect please try again', 'error')

    return redirect(request.args.get('next') or url_for('home'))


@votr.route('/logout')
def logout():
    if 'user' in session:
        session.pop('user')

        flash('We hope to see you again!')

    return redirect(url_for('home'))


@votr.route('/polls', methods=['GET'])
def polls():
    return render_template('polls.html')


@votr.route('/polls/<poll_name>')
def poll(poll_name):

    return render_template('index.html')
