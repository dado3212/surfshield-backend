#----------------------------------------------------------------
# application.py
# 
# Jonathan Kramer
# 09/24/16
#----------------------------------------------------------------

#----------------------------------------------------------------
#                            IMPORTS
#----------------------------------------------------------------

from flask import Flask
from flask import request
from flask import jsonify
# from flask_sqlalchemy import SQLAlchemy

from bs4 import BeautifulSoup
from urllib.request import urlopen
import re

import os

import json
from watson_developer_cloud import ToneAnalyzerV3
import requests
requests.packages.urllib3.disable_warnings()

#----------------------------------------------------------------
#                          CONFIGURATION
#----------------------------------------------------------------

application = Flask(__name__)

DB_NAME = os.environ['RDS_DB_NAME']
DB_USERNAME = os.environ['RDS_USERNAME']
DB_PASSWORD = os.environ['RDS_PASSWORD']
DB_HOSTNAME = os.environ['RDS_HOSTNAME']
DB_PORT = os.environ['RDS_PORT']

DB_URI = 'postgres://%s:%s@%s:%s/%s' % (DB_USERNAME, DB_PASSWORD, DB_HOSTNAME, DB_PORT, DB_NAME)

application.config['SQLALCHEMY_DATABASE_URI'] = DB_URI

db = SQLAlchemy(application)

# To initialiate the DB
# 
# from application import db
# db.create_all()
# 

#----------------------------------------------------------------
#                      DATABASE CLASS DEFINITIONS
#----------------------------------------------------------------

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text)

    anger_score = db.Column(db.Float)
    cyberbulling_score = db.Column(db.Float)
    profanity_score = db.Column(db.Float)

    def __init__(self, url, anger_score, cyberbulling_score, profanity_score):
        self.url = url
        self.anger_score = anger_score
        self.cyberbulling_score = cyberbulling_score
        self.profanity_score = profanity_score

    def __repr__(self):
        return '<Rating for %s>' % self.url

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, unique=True)
    rating = db.Column(db.Float)
    count = db.Column(db.Integer)

    def __init__(self, url, rating):
        self.url = url
        self.rating = rating

    def __repr__(self):
        return '<Vote for %s>' % self.url

#----------------------------------------------------------------
#                         HELPER FUNCTIONS
#----------------------------------------------------------------

def textFromUrl(url):
	# soup = BeautifulSoup(html_doc, 'html.parser')
	html = urlopen(url)
	html = re.sub(r'<script type="text/javascript">[\s\S]*?</script>', '', html)
	html = re.sub(r'<a.*?>(.*?)</a>', r'\1 ', html)

	soup = BeautifulSoup(html, 'html.parser')
	pretty = soup.get_text()
	pretty = re.sub(r'\n', ' ', pretty)
	pretty = re.sub(r'\t', ' ', pretty)
	pretty = re.sub(r' +', ' ', pretty)
	return pretty

tone_analyzer = ToneAnalyzerV3(
   username="a0d6b309-06ae-4b3c-bb2e-2f32888b5365",
   password="yhlmAAsWiUKU",
   version='2016-05-19')

def makeWatsonCall(str):
	return(json.dumps(tone_analyzer.tone(text=str), indent=2))

def process_watson(str):
	parsed_json = json.loads(makeWatsonCall(str))
	anger = (parsed_json['document_tone']['tone_categories'][0]['tones'][0]['score'])
	return anger


def makeBarkCall (text):
	url = 'https://partner.bark.us/api/v1/messages?token=kUSvsx47Lg56kUfCfZDvQNKa'
	data = {'message': text}
	headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
	r = requests.post(url, data=json.dumps(data), headers=headers)

	return (r.text)

def process_bark(text):
	parsed_json = json.loads(makeBarkCall(text))
	
	# cyberbullying score (1-5)
	cyberLikely = parsed_json['results']['cyberbullying']['likelihood']
	cyberScore = 0
	
	if cyberLikely == "VERY_UNLIKELY":
		cyberScore = 1
	elif cyberLikely == "UNLIKELY":
		cyberScore = 2
	elif cyberLikely == "NEUTRAL":
		cyberScore = 3
	elif cyberLikely == "LIKELY":
		cyberScore = 4
	else:
		cyberScore = 5

	# profanity score (1 to 5)
	profaneSeverity = parsed_json['results']['profanity']['severity'] + 1
	bullyingArr = [cyberScore, profaneSeverity]
	return bullyingArr

#cyberScore input is an array with two elements
#the first element is the cyberbullying score and the second is the profanity severity
def calculateScore(audienceScore, angerScore, cyberScore):
	cyberBullying = cyberScore[0]
	profanity = cyberScore[1]
	angerScore = round((angerScore*4) + 1,1)
	averageScore = 0

	if (audienceScore is None):
		averageScore = round((cyberBullying+profanity+angerScore)/3,1)
	else:
		averageScore = round((cyberBullying+profanity+angerScore+audienceScore)/4,1)

	return averageScore

#----------------------------------------------------------------
#                            ROUTES
#----------------------------------------------------------------

@application.route("/", methods=['GET'])
def home():
    return application.send_static_file('home.html')

@application.route("/api/v0.1/rating", methods=['POST'])
def get_rating():
	data = request.get_json(force=True)
	url = data['url']
	text = data['text']

	if url is None:
		return "Bad request wahhh"

	# if text is null, grab the html ourselves
	if text is None:
		text = textFromUrl(url)

	# Send text to the various apis
	angerScore = process_watson(text)
	cyberScore = process_bark(text)

	# Get votes for this url from the DB
	audienceScore = 3

	# Calculate scores based on api return values and vote counts
	overall = calculateScore(None, angerScore, cyberScore)

	# Store scores in the DB
		# rating = Rating(url, response.anger_score, response.cyberbulling_score, response.profanity_score)
	# db.session.add(rating)
	# db.session.commit()

	# Send response
	response = jsonify(audience=audienceScore, anger = angerScore, cyberbulling = cyberScore[0], profanity = cyberScore[1], overall = overall);

	return response

@application.route("/api/v0.1/vote", methods=['POST'])
def record_vote():
    data = request.get_json(force=True)
    url = data['url']
    vote_score = data['vote_score']

    # Get the url from the votes list if it exists

    # Otherwise create a new vote


if __name__ == "__main__":
    application.run()
