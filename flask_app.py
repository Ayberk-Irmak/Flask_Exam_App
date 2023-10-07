from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import re
import time
import random
import requests
from datetime import datetime

app = Flask(__name__)

app.secret_key = 'xyzsdfg'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('database/user-system.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_appcontext
def teardown_db(e=None):
    close_db()

with app.app_context():
    cursor = get_db().cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                    userid INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT,
                    password TEXT,
                    score INTEGER DEFAULT 0  -- New column: User's score
                )''')
    get_db().commit()

def login_user(user):
    session['loggedin'] = True
    session['userid'] = user['userid']
    session['name'] = user['name']
    session['email'] = user['email']

def score(session):
    cursor = get_db().cursor()
    user_id = session['userid']
    cursor.execute('SELECT score FROM user WHERE userid = ?', (user_id,))
    user = cursor.fetchone()
    score = user['score']
    return score

def check_login():
    return 'loggedin' in session

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM user WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        
        if user:
            login_user(user)  
            score_value = score(session)
            message = 'Logged in successfully!'
            return render_template('home.html', message=message, score=score_value)
        else:
            message = 'Please enter correct email / password!'
    
    return render_template('login.html', message=message)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('userid', None)
    session.pop('email', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and 'name' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['name']
        password = request.form['password']
        password_repeat = request.form['password_repeat']
        email = request.form['email']
        
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM user WHERE email = ?', (email,))
        account = cursor.fetchone()
        
        if account:
            message = 'Username is already in use!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Incorrect Email Format!'
        elif not username or not password or not email:
            message = 'Please Fill Out the Form!!'
        elif password != password_repeat:
            message = "The entered passwords don't match!"
        else:
            cursor.execute('INSERT INTO user (name, email, password) VALUES (?, ?, ?)', (username, email, password))
            get_db().commit()
            message = 'You have successfully registered!'
            user = cursor.execute('SELECT * FROM user WHERE email = ?', (email,)).fetchone()
            time.sleep(1)
            login_user(user)  
            return render_template('home.html', message=message)
    
    elif request.method == 'POST':
        message = 'Please fill out the form!'
    
    return render_template('register.html', message=message)

@app.route('/home', methods=['GET'])
def home():
    if check_login():
        score_value = score(session)
        city_name = request.args.get('city_name') 
        api_key = "YOUR_API_KEY"  

        api_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={api_key}"
        response = requests.get(api_url)
        weather_data = response.json()

        morning_temperatures = []
        evening_temperatures = []

        for item in weather_data['list']:
            if '03:00:00' in item['dt_txt'] or '18:00:00' in item['dt_txt']:
                temperature_celsius = item['main']['temp'] - 273.15  
                if '03:00:00' in item['dt_txt']:
                    morning_temperatures.append(round(temperature_celsius, 2))
                else:
                    evening_temperatures.append(round(temperature_celsius, 2))

        morning_temperatures = morning_temperatures[:3]
        evening_temperatures = evening_temperatures[:3]

        return render_template('home.html', today_morning=morning_temperatures[0], today_evening=evening_temperatures[0],
                            tomorrow_morning=morning_temperatures[1], tomorrow_evening=evening_temperatures[1],
                            day_after_morning=morning_temperatures[2], day_after_evening=evening_temperatures[2], score=score_value)
    return redirect(url_for('login'))

@app.route('/exam')
def exam():
    if check_login():
        cursor = get_db().cursor()
        cursor.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT 1')
        rows = cursor.fetchall()
        questions = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]
        score_value = score(session)

        session['questions'] = questions

        return render_template('exam.html', questions=questions, score=score_value)
    return redirect(url_for('login'))

@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    if check_login():
        questions = session.get('questions') 

        user_id = session['userid']
        cursor = get_db().cursor()
        cursor.execute('SELECT score FROM user WHERE userid = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            score_value = user['score']
        else:
            score_value = 0 

        for question in questions:
            question_id = question['question_id']
            selected_option = int(request.form.get('question' + str(question_id), -1))
            correct_option = question['correct_option']

            if selected_option == correct_option:
                score_value += 5

        cursor.execute('UPDATE user SET score = ? WHERE userid = ?', (score_value, user_id))
        get_db().commit()

        result = 'Correct Answer' if selected_option == correct_option else 'Wrong Answer'
        
        return result
    
    return redirect(url_for('login'))

@app.route('/leader', methods=['GET'])
def leaderboard():
    if check_login():
        cursor = get_db().cursor()
        cursor.execute('SELECT name, score FROM user ORDER BY score DESC')
        leaderboard = cursor.fetchall()
        score_value = score(session)
    
        return render_template('leader.html', leaderboard=leaderboard, score=score_value)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
