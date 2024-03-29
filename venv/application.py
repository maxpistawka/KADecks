from flask import Flask, flash, render_template, redirect, session, request, jsonify
from flask_mysqldb import MySQL
from datetime import date
from hgtk.exception import NotHangulException
from supermemo2 import SMTwo
import hgtk
import os
from textblob import TextBlob
from werkzeug.utils import secure_filename
import config

today = date.today()
application = Flask(__name__, template_folder='template')
secret = os.urandom(24)
application.config['MYSQL_HOST'] = "localhost"
application.config['MYSQL_USER'] = "Max"
application.config['MYSQL_PASSWORD'] = config.password
application.config['MYSQL_DB'] = config.db

mysql = MySQL(application)
currID = -1
application.config["SECRET_KEY"] = secret
UPLOAD_FOLDER = 'static/imgs/'
ALLOWED_EXTENSIONS = {'png', 'jpg'}
application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def verify():
    global currID
    if int(session.get('userid', -1)) > 0:
        currID = int(session.get('userid', -1))
        return False
    else:
        return True


@application.route('/', methods=['GET', 'POST'])
def index():
    global currID
    try:
        if not verify():
            return redirect("/main", 301)
        if request.method == 'POST':
            if request.form['btn_identifier'] == 'signup_identifier':
                try:
                    username = request.form['username']
                    email = request.form['email']
                    password = request.form['password']
                    try:
                        cur = mysql.connection.cursor()
                        cur.execute("INSERT INTO users (username,pass, email, date_registered) VALUES (%s, %s, %s, %s)",
                                    (username, password, email, today))
                        mysql.connection.commit()
                        cur.close()
                        flash('Account Created')
                        redirect('/login', 301)
                    except mysql.connector.Error as err:
                        flash("Something went wrong: {}".format(err))
                except:
                    flash('Invalid Credentials')
    except:
        flash('Invalid Credentials')
        return render_template('signup.html')
    return render_template('signup.html')


@application.route('/login', methods=['GET', 'POST'])
def login():
    global currID
    try:
        if not verify():
            return redirect("/main", 301)
        if request.method == 'POST':
            if request.form['btn_identifier'] == 'login_identifier':
                email = request.form['email']
                password = request.form['password']
                try:
                    cur = mysql.connection.cursor()
                    cur.execute("SELECT * FROM users WHERE email = '" + email + "' AND pass = '" + password + "'")
                    result = cur.fetchone()
                    if result:
                        currID = result[0]
                        cur.close()
                        session['userid'] = currID
                        return redirect("/main", code=301)
                except mysql.connector.Error as err:
                    flash("Something went wrong: {}".format(err))
            flash('Invalid Credentials')
    except:
        return render_template('login.html')
    return render_template('login.html')


@application.route('/main', methods=['GET', 'POST'])
def main():
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        cur.execute("INSERT INTO decks (title, date_created, admin_user_id) VALUES (%s, %s, %s)",
                    (request.form['title'], today, currID))
        mysql.connection.commit()
        cur.execute("SELECT * FROM decks ORDER BY (deck_id) DESC LIMIT 1")
        deck_id = cur.fetchone()[0]
        cur.execute("INSERT INTO decks_user (deck_id, user_id) VALUES (%s, %s)", (deck_id, currID))
        mysql.connection.commit()
        return redirect("/deck/" + str(deck_id) + "/review", 301)
    user_decks = user_deck_finder()
    decks = deck_finder()
    return render_template('main.html', user_decks=user_decks, decks=decks)


def user_deck_finder():
    query = "SELECT * FROM decks_user WHERE user_id = " + str(currID)
    cur = mysql.connection.cursor()
    cur.execute(query)
    unfilteredDecks = cur.fetchall()
    ids = []
    for deck in unfilteredDecks:
        ids.append(deck[0])
    decks = []
    for name in ids:
        cur.execute("SELECT * FROM decks WHERE deck_id = " + str(name))
        deck = cur.fetchone()
        decks.append([str(deck[1]), deck[0]])
    return decks


def deck_finder():
    cur = mysql.connection.cursor()
    query = "SELECT * FROM decks WHERE deck_id NOT IN (SELECT deck_id FROM decks_user WHERE user_id = " + str(
        currID) + ")"
    cur.execute(query)
    unfilteredDecks = cur.fetchall()
    decks = []
    for deck in unfilteredDecks:
        decks.append([str(deck[1]), deck[0]])
    return decks


@application.route('/subscribe_deck/<string:deck_id>')
def subscribe(deck_id):
    if verify():
        return redirect("/", 301)
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO decks_user (deck_id, user_id) VALUES (%s, %s)", (deck_id, currID))
        mysql.connection.commit()
        cur.close()
    except:
        flash("Invalid")
    return redirect("/main", 301)


@application.route('/deck/<string:deck_id>/edit', methods=['GET', 'POST'])
def deck_edit(deck_id):
    if verify():
        return redirect("/", 301)
    if is_not_admin(deck_id):
        return redirect('/main')
    cur = mysql.connection.cursor()
    cur.execute("SELECT admin_user_id FROM decks WHERE deck_id = " + deck_id)
    res = cur.fetchone()
    if str(res[0]) != str(currID):
        return redirect("/deck/" + str(deck_id) + "/review", 301)
    if request.method == 'POST':
        if request.form['btn_identifier'] == 'add_identifier':
            english = request.form['english']
            korean = request.form['korean']
            ends = ends_generator(korean)
            cur.execute("INSERT INTO vocabulary (deck_id, korean, english, endings) VALUES (%s, %s, %s, %s)",
                        (deck_id, korean, english, ends))
            mysql.connection.commit()
            flash("Added " + english + ": " + korean)
        elif request.form['btn_identifier'] == 'title_identifier':
            cur.execute("UPDATE decks SET title = '" + request.form['title'] + "' WHERE deck_id = " + str(deck_id))
            mysql.connection.commit()
            flash("Changed Title")
    cur.execute("SELECT * FROM vocabulary WHERE deck_id = " + str(deck_id))
    vocab = cur.fetchall()
    return render_template("edit.html", deckid=deck_id, vocabs=vocab)


def ends_generator(kor):
    ends = ""
    for s in range(len(kor) - 1):
        try:
            decomposed = hgtk.letter.decompose(kor[s])
            if decomposed[-1]:
                try:
                    nextDecomposed = hgtk.letter.decompose(kor[s + 1])
                    ends += decomposed[-1] + nextDecomposed[0]
                except NotHangulException:
                    """ nothing """
        except NotHangulException:
            """ not Hangul """
    return ends


@application.route('/unsubscribe/<string:deck_id>')
def unsubscribe(deck_id):
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM decks_user WHERE deck_id = " + str(deck_id) + " AND user_id = " + str(currID))
    mysql.connection.commit()
    flash("Unsubscribed from " + deck_id)
    return redirect("/main", 301)


@application.route('/deletevocab/<string:vocab_id>/<string:deck_id>')
def delete_vocab(vocab_id, deck_id):
    if verify():
        return redirect("/", 301)
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM logs WHERE vocab_id = " + str(vocab_id))
        cur.execute("DELETE FROM vocabulary WHERE vocab_id = " + str(vocab_id))
        mysql.connection.commit()
    except mysql.connector.Error as err:
        flash("Error Deleting Vocab")
    flash("Deleted vocabulary")
    return redirect('/deck/' + deck_id + "/edit")


@application.route('/deck/<string:deck_id>/review')
def deck_review(deck_id):
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = " + str(currID))
    username = cur.fetchone()[0];
    cur = mysql.connection.cursor()
    query = "SELECT profile_pic FROM users WHERE user_id = " + str(currID)
    cur.execute(query)
    result = cur.fetchone()
    query = "SELECT title FROM decks WHERE deck_id = " + deck_id
    cur.execute(query)
    deckname = cur.fetchone()[0]
    cur.execute("SELECT COUNT(user_id) FROM logs WHERE user_id = %s AND deck_id = %s", (currID, deck_id))
    vocabCount = cur.fetchone()[0]
    filename = ""
    if result:
        if result[0] is None:
            hasPic = False
        else:
            hasPic = True
            filename = result[0]
    currVocab = get_next_vocab(deck_id)
    if currVocab is None:
        if is_not_admin(deck_id):
            return redirect('/main')
        return redirect('/deck/' + deck_id + "/edit")
    return render_template("reviewfront.html", vocabCount=vocabCount, deckname=deckname,
                           username=username, vocab=currVocab, deckid=deck_id,
                           userid=str(currID), hasPic=hasPic, pic="imgs/" + filename)


def is_not_admin(deck_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT admin_user_id FROM decks WHERE deck_id = " + deck_id)
    res = cur.fetchone()
    return str(res[0]) != str(currID)


@application.route('/profile/<string:user_id>', methods=['GET', 'POST'])
def profile_view(user_id):
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = " + str(user_id))
    username = cur.fetchone()[0];
    cur = mysql.connection.cursor()
    query = "SELECT profile_pic FROM users WHERE user_id = " + str(user_id)
    cur.execute(query)
    result = cur.fetchone()
    filename = ""
    if result:
        if result[0] is None:
            hasPic = False
        else:
            hasPic = True
            filename = result[0]
    cur.execute("SELECT COUNT(user_id) FROM logs WHERE user_id = " + str(user_id))
    vocabCount = cur.fetchone()[0]
    cur.execute("SELECT COUNT(user_id) FROM decks_user WHERE user_id = " + str(user_id))
    deckCount = cur.fetchone()[0]
    return render_template("profile.html", username=username, vocabCount=vocabCount,
                           deckCount=deckCount, hasPic=hasPic, pic="imgs/" + filename)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@application.route('/profile/<string:user_id>/edit', methods=['GET', 'POST'])
def profile_edit(user_id):
    if verify():
        return redirect("/", 301)
    if str(currID) != user_id:
        return redirect('/profile/' + user_id)
    hasPic = False
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = " + str(user_id))
    username = cur.fetchone()[0];
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                directoryPath = os.path.join(application.config['UPLOAD_FOLDER'], filename)
                file.save(directoryPath)
                insert_query = "UPDATE users SET profile_pic = %s WHERE user_id = %s"
                values = (filename, user_id)
                cur = mysql.connection.cursor()
                cur.execute(insert_query, values)
                mysql.connection.commit()
                cur.execute("SELECT COUNT(user_id) FROM logs WHERE user_id = " + str(user_id))
                vocabCount = cur.fetchone()[0]
                cur.execute("SELECT COUNT(user_id) FROM decks_user WHERE user_id = " + str(user_id))
                deckCount = cur.fetchone()[0]
                return render_template("profileedit.html", username=username, vocabCount=vocabCount,
                                       deckCount=deckCount, hasPic=True, pic="imgs/" + filename)
            except:
                flash("File not supported")
                return render_template("profileedit.html", username=username, vocabCount=vocabCount,
                                       deckCount=deckCount, hasPic=False, pic="imgs/" + filename)
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(user_id) FROM logs WHERE user_id = " + str(user_id))
    vocabCount = cur.fetchone()[0]
    cur.execute("SELECT COUNT(user_id) FROM decks_user WHERE user_id = " + str(user_id))
    deckCount = cur.fetchone()[0]
    query = "SELECT profile_pic FROM users WHERE user_id = " + str(user_id)
    cur.execute(query)
    result = cur.fetchone()
    filename = ""
    if result:
        if result[0] is None:
            hasPic = False
        else:
            hasPic = True
            filename = result[0]
    return render_template("profileedit.html", userid=currID, username=username, vocabCount=vocabCount,
                           deckCount=deckCount, hasPic=hasPic, pic="imgs/" + filename)


@application.route('/reviews', methods=['GET', 'POST'])
def give_review():
    if verify():
        return redirect("/", 301)
    if request.method == 'POST':
        try:
            message = request.form['msg']
            if len(message) < 500:
                flash('Review Submitted!')
                cur = mysql.connection.cursor()
                blob = TextBlob(message)
                sentiment_val = blob.sentiment.polarity
                cur.execute(
                    "INSERT INTO reviews (message,sentiment_val, date_created, user_id) VALUES (%s, %s, %s, %s)",
                    (message, sentiment_val, today, currID))
                mysql.connection.commit()
                cur.close()
                return render_template('givereview.html')
        except:
            flash('Invalid')
            """# nothing"""
    return render_template("givereview.html")


def urgency_calc(score, deck_id, vocab_id):
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM logs WHERE vocab_id = " + str(vocab_id) + " AND user_id = " + str(currID))
    log = cur.fetchone()
    if log is None:
        review = SMTwo.first_review(score)
        cur.execute(
            "INSERT INTO logs (deck_id, vocab_id, user_id, next_date, easiness, review_interval, repetitions) " +
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (int(deck_id), int(vocab_id), int(currID), review.review_date,
             review.easiness, review.interval, review.repetitions))
    else:
        review = SMTwo(log[5], log[6], log[7]).review(score)
        cur.execute(
            "UPDATE logs SET next_date = %s, easiness = %s, review_interval = %s, repetitions = %s WHERE log_id = "
            + str(log[0]), (review.review_date, review.easiness, review.interval, review.repetitions))
    mysql.connection.commit()


def get_next_vocab(deck_id):
    if verify():
        return redirect("/", 301)
    cur = mysql.connection.cursor()
    # Any to-dos?
    cur.execute(
        "SELECT * FROM logs WHERE deck_id = %s AND user_id = %s AND next_date <= %s ORDER BY next_date ASC LIMIT 1",
        (deck_id, currID, today))
    log = cur.fetchone()
    if log is not None:
        cur.execute("SELECT * FROM vocabulary WHERE vocab_id = " + str(log[2]))
        return cur.fetchone()
    # Any no-log vocab? (a vocab that belongs to the deck that a user has no logs for)
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM vocabulary WHERE vocab_id NOT IN (SELECT vocab_id FROM logs WHERE user_id = %s AND " +
                "deck_id = %s) AND deck_id = %s", (str(currID), deck_id, deck_id))
    vocab = cur.fetchone()
    if vocab:
        return vocab
    # Any to-do in the future vocab?
    cur.execute(
        "SELECT * FROM logs WHERE deck_id = %s AND user_id = %s AND next_date >= NOW() ORDER BY next_date ASC LIMIT 1",
        (deck_id, currID))
    log = cur.fetchone()
    if log:
        cur.execute("SELECT * FROM vocabulary WHERE vocab_id = " + str(log[2]))
        return cur.fetchone()
    # Random One
    cur.execute("SELECT * FROM vocabulary WHERE deck_id = " + str(deck_id) + " ORDER BY RAND() LIMIT 1")
    return cur.fetchone()


@application.route('/api/datapoint/<string:deck_id>')
def api_datapoint(deck_id):
    if verify():
        return redirect("/", 301)
    vocab = get_next_vocab(deck_id)
    dictionary_to_return = {
        'korean': vocab[2],
        'english': vocab[3],
        'endings': vocab[4],
        'vocabid': vocab[0],
    }
    return jsonify(dictionary_to_return)


@application.route('/log/<string:deck_id>/<string:vocab_id>/<string:rating>')
def log(deck_id, vocab_id, rating):
    if verify():
        return redirect("/", 301)
    score = int(rating)
    urgency_calc(score, deck_id, vocab_id)
    mysql.connection.commit()
    return jsonify({'error': 'No error.'})


if __name__ == "__main__":
    application.run(debug=True)


