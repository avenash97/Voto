from os import getenv

from models import db, Users, Polls, Topics, Options, UserPolls
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from config import SQLALCHEMY_DATABASE_URI
import unicodedata
if getenv('APP_MODE') == 'PRODUCTION':
    from production_settings import SQLALCHEMY_DATABASE_URI



api = Blueprint('api', 'api', url_prefix='/api')

##############################################################################################################################

import random
public, private = ((243, 391), (507, 391))

'''
Euclid's algorithm for determining the greatest common divisor
Use iteration to make it faster for larger integers
'''
def gcd(a, b):
    while b != 0:
        a, b = b, a % b
    return a

'''
Euclid's extended algorithm for finding the multiplicative inverse of two numbers
'''
def multiplicative_inverse(e, phi):
    d = 0
    x1 = 0
    x2 = 1
    y1 = 1
    temp_phi = phi
    
    while e > 0:
        temp1 = temp_phi/e
        temp2 = temp_phi - temp1 * e
        temp_phi = e
        e = temp2
        
        x = x2- temp1* x1
        y = d - temp1 * y1
        
        x2 = x1
        x1 = x
        d = y1
        y1 = y
    
    if temp_phi == 1:
        return d + phi

'''
Tests to see if a number is prime.
'''
def is_prime(num):
    if num == 2:
        return True
    if num < 2 or num % 2 == 0:
        return False
    for n in xrange(3, int(num**0.5)+2, 2):
        if num % n == 0:
            return False
    return True

def generate_keypair(p, q):
    if not (is_prime(p) and is_prime(q)):
        raise ValueError('Both numbers must be prime.')
    elif p == q:
        raise ValueError('p and q cannot be equal')
    #n = pq
    n = p * q

    #Phi is the totient of n
    phi = (p-1) * (q-1)

    #Choose an integer e such that e and phi(n) are coprime
    e = random.randrange(1, phi)

    #Use Euclid's Algorithm to verify that e and phi(n) are comprime
    g = gcd(e, phi)
    while g != 1:
        e = random.randrange(1, phi)
        g = gcd(e, phi)

    #Use Extended Euclid's Algorithm to generate the private key
    d = multiplicative_inverse(e, phi)
    
    #Return public and private keypair
    #Public key is (e, n) and private key is (d, n)
    return ((e, n), (d, n))

def encrypt(pk, plaintext):
    #Unpack the key into it's components
    key, n = pk
    #Convert each letter in the plaintext to numbers based on the character using a^b mod m
    cipher = [(ord(char) ** key) % n for char in plaintext]
    #Return the array of bytes
    #print(type(cipher))
    x = int(''.join(map(str,cipher)))
    print (x)
    print(type(x))
    return x

def decrypt(pk, ciphertext):
    #Unpack the key into its components
    key, n = pk
    #Generate the plaintext based on the ciphertext and key using a^b mod m
    plain = [chr((char ** key) % n) for char in ciphertext]
    #Return the array of bytes as a string
    return ''.join(plain)


##############################################################################################################################


# BATCH = LOGIN; REDIRECT = /POLLS/BATCH; QUERY = BATCH

@api.route('/polls', methods=['GET', 'POST'])
# retrieves/adds polls from/to the database
def api_polls():
    if request.method == 'POST':

        # get the poll and save it in the database
        poll = request.get_json()

        # simple validation to check if all values are properly set
        for key, value in poll.items():
            if not value:
                return jsonify({'message': 'value for {} is empty'.format(key)})

        title = poll['title']
        batch = poll['batch']
        options_query = lambda option: Options.query.filter(Options.name.like(option))

        options = [Polls(option=Options(name=option))
                   if options_query(option).count() == 0
                   else Polls(option=options_query(option).first()) for option in poll['options']
                   ]
        eta = datetime.utcfromtimestamp(poll['close_date'])
        new_topic = Topics(title=title, poll_group=batch,options=options, close_date=eta)
        #poll_group = Polls()
        #db.session.add(poll_group)
        db.session.add(new_topic)
        db.session.commit()

        # run the task
        from tasks import close_poll

        close_poll.apply_async((new_topic.id, SQLALCHEMY_DATABASE_URI), eta=eta)

        return jsonify({'message': 'Poll was created succesfully'})

    else:
        # it's a GET request, return dict representations of the API
        user = session['user']
        # print('User:', user)
        # user = unicodedata.normalize('NFKD', user).encode('ascii','ignore')
        # print('UpdatedUser:', user)
        user_info =  Users.query.filter_by(username=user).first()
        # print('User Info: ', user_info)
        # user_type = unicodedata.normalize('NFKD', user_info.user_group).encode('ascii','ignore')
        user_type = user_info.user_group
        


        polls = Topics.query.filter_by(status=True, poll_group=user_type).join(Polls).order_by(Topics.id.desc()).all()
        all_polls = Topics.query.filter_by(status=True, poll_group='all').join(Polls).order_by(Topics.id.desc()).all()
        for x in all_polls:
            polls.append(x)
        print(type(polls))
        all_polls = {'Polls':  [poll.to_json() for poll in polls]}

        return jsonify(all_polls)


@api.route('/polls/options')
def api_polls_options():

    all_options = [option.to_json() for option in Options.query.all()]

    return jsonify(all_options)


@api.route('/poll/vote', methods=['PATCH'])
def api_poll_vote():
    poll = request.get_json()

    poll_title, option = (poll['poll_title'], poll['option'])

    join_tables = Polls.query.join(Topics).join(Options)

    # Get topic and username from the database
    topic = Topics.query.filter_by(title=poll_title, status=True).first()
    user = Users.query.filter_by(username=session['user']).first()

    # if poll was closed in the background before user voted
    if not topic:
        return jsonify({'message': 'Sorry! this poll has been closed'})

    # filter options
    option = join_tables.filter(Topics.title.like(poll_title), Topics.status == True).filter(Options.name.like(option)).first()

    # check if the user has voted on this poll
    encrypted_msg = int(encrypt(private, str(user.id)))
    poll_count = UserPolls.query.filter_by(topic_id=topic.id).filter_by(user_id=encrypted_msg).count()
    #poll_count = UserPolls.query.filter_by(topic_id=topic.id).filter_by(user_id=encrypted_msg).count()
    if poll_count > 0:
        return jsonify({'message': 'Sorry! multiple votes are not allowed'})

    if option:
        # record user and poll
        #print(public, private)
        encrypted_msg = int(encrypt(private, str(user.id)))
        #decrypt(public, encrypted_msg)
        user_poll = UserPolls(topic_id=topic.id, user_id=encrypted_msg)
        #user_poll = UserPolls(topic_id=topic.id, user_id=user.id)
        db.session.add(user_poll)

        # increment vote_count by 1 if the option was found
        option.vote_count += 1
        db.session.commit()

        return jsonify({'message': 'Thank you for voting'})

    return jsonify({'message': 'option or poll was not found please try again'})


@api.route('/poll/<poll_name>')
def api_poll(poll_name):

    poll = Topics.query.filter(Topics.title.like(poll_name)).first()

    return jsonify({'Polls': [poll.to_json()]}) if poll else jsonify({'message': 'poll not found'})
