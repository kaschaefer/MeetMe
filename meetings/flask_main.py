import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid
import bson
from bson.objectid import ObjectId
import sys
from pymongo import MongoClient

import json
import logging

import calculations
from calculations import getEventsFromAllCalendars
from calculations import getBlocks
from calculations import getPertinentInfo
from calculations import concatFreeTimes

# Date handling 
import arrow # Replacement for datetime, based on moment.js
# import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery




###
# Globals
###
import config
if __name__ == "__main__":
    CONFIG = config.configuration()
else:
    CONFIG = config.configuration(proxied=True)

#Database SetUp
MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST, 
    CONFIG.DB_PORT, 
    CONFIG.DB)

app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key=CONFIG.SECRET_KEY

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_KEY_FILE  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

####
# Database connection per server process
###

try: 
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.MeetMe

except:
    print("Failure opening database.  Is Mongo running? Correct password?")
    sys.exit(1)


#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
    return render_template('index.html')

@app.route("/createFinish")
def createFinish():
    return render_template('createFinish.html')

@app.route("/find")
def find():
    return render_template('find.html')

@app.route("/respond")
def respond():
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    #Get auth from google
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback_part2'))
    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.g.calendars = list_calendars(gcal_service)
    return render_template('respond.html')

@app.route("/create")
def create():
  app.logger.debug("Entering create")
  if 'begin_time' not in flask.session or 'begin_time' == "":
    init_session_values()
  return render_template('create.html')

@app.route("/ownerRespond")
def ownerRespond():
    app.logger.debug(flask.session)
    return render_template('ownerRespond.html')

@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars 
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return' 
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    if 'begin_time' not in flask.session or 'begin_time' == "":
        init_session_values()

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.g.calendars = list_calendars(gcal_service)
    return render_template('create.html')

@app.route("/update_Meeting")
def update_Meeting():
    app.logger.debug("Entering Update Meeting")
    #Get info from the request
    freeString = request.args.get('events')
    userFreeTimes = json.loads(freeString)
    userName = flask.session['current_name']
    meetingID = flask.session['current_meetingID']
    #Get the current database entry
    try:
        theMeetingTimes = collection.find_one({"_id": ObjectId(meetingID)})
        flask.session['current_meetingID'] = meetingID
    except:
        app.logger.debug("could not retrieve meeting information from the database")
    #Get the current availableTimes
    currentFreeTimes = theMeetingTimes["available_times"]
    begin_date = theMeetingTimes["range"][0]
    end_date = theMeetingTimes["range"][1]
    #Find the commonality between the two
    finalList = concatFreeTimes(currentFreeTimes, userFreeTimes, begin_date, end_date)
    updatedResponded = theMeetingTimes["already_responded"]
    updatedResponded.append(userName)
    collection.find_one_and_update({"_id": ObjectId(meetingID)}, { '$set': {"available_times": finalList, "already_responded": updatedResponded}})
    
    return flask.jsonify(result = userName)    
            



@app.route("/get_busy_times")
def get_busy_times():
    app.logger.debug("Entering get busy times")
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))
    
    gcal_service = get_gcal_service(credentials)
    calendars = json.loads(request.args.get('calendarIDs'))

    #Get beginning and end dates of date range
    begin = arrow.get(flask.session['begin_date'])
    begin_time = flask.session['begin_time']

    end = arrow.get(flask.session['end_date'])
    end_time = flask.session['end_time']

    app.logger.debug(end)
    app.logger.debug(end_time)
    app.logger.debug(begin)
    app.logger.debug(begin_time)
    app.logger.debug(calendars)
    #Call Function that will get all events that overlap the specified time and date range from the specified calendars
    #returns a list of events with event start, event finish, event summary, event description string
    allEvents = getEventsFromAllCalendars(gcal_service, calendars, begin, begin_time, end, end_time)
    
    #end of create list of strings
    app.logger.debug("Getting free and busy time blocks with the following events list:")
    app.logger.debug(allEvents)

    eventList = getBlocks(allEvents, begin, begin_time, end, end_time)
    #upon return from getBlocks, eventList is a list of our free/busy times for the given day/time range
    #turn the arrow objects into ISO strings before sending the information to the server
    for event in eventList:
        app.logger.debug(event)
    result = getPertinentInfo(eventList)
    return flask.jsonify(result = result)

@app.route("/get_data", methods=['POST'])
def get_data():
    name = request.form.get('fullName')
    meetingID = request.form.get('meetingID')
    app.logger.debug("Got a get_data request with name " + str(name) + " and meetingID " + str(meetingID))
    try:
        theMeetingTimes = collection.find_one({"_id": ObjectId(meetingID)})
        flask.session['current_meetingID'] = meetingID
    except:
        app.logger.debug("could not retrieve meeting information from the database")

    #Is the person who's looking for information the owner of the meeting
    if theMeetingTimes["owner"] == name:
        handle_owner_request(theMeetingTimes["invitees"], theMeetingTimes["already_responded"], theMeetingTimes["available_times"])
        return flask.redirect(flask.url_for('ownerRespond'))
    else:
        isAValidName = False
        alreadyResponded = False
        #Is the person an invitee
        for person in theMeetingTimes["invitees"]:
            if person == name:
                isAValidName = True
                break

        #did the person already respond
        for person in theMeetingTimes["already_responded"]:
            if person == name:
                alreadyResponded = True
                break

        if (isAValidName and not alreadyResponded):
            #new response:
            handle_new_response(theMeetingTimes["range"])
            flask.session['current_name'] = name
            app.logger.debug("Checking credentials for Google calendar access")
            credentials = valid_credentials()
            #Get auth from google
            if not credentials:
               app.logger.debug("Redirecting to authorization")
               return flask.redirect(flask.url_for('oauth2callback_part2'))
        
        else:
            if(isAValidName and alreadyResponded):
                flask.flash("You already responded to the meeting request!")
            else:
                flask.flash("The name you entered is not on the list of invitees. Please check spelling and try again")
            return flask.redirect(flask.url_for("find"))

    return flask.redirect(flask.url_for("respond"))

#Decide whether the owner of the meeting is ready to finalize the meeting time or not
def handle_owner_request(listOfInvitees, listOfAlreadyResponded, availableTimes):
    slackers = []
    notFinished = False
    app.logger.debug("Handling owner request")
    for person in listOfInvitees:
        if person not in listOfAlreadyResponded:
            slackers.append(person)
            notFinished = True
        #endif
    #endfor
    if (notFinished):
        flask.session['slackers'] = slackers
    else:
        flask.session['meetingFinished'] = True
        flask.session['freeTimes'] = availableTimes
    return

def handle_new_response(aList):
    #initialize time range so that we can use the get busy function and whatnot
    flask.session['begin_date'] = aList[0]
    flask.session['end_date'] = aList[1]
    flask.session['begin_time'] = aList[2]
    flask.session['end_time'] = aList[3]
    return

@app.route("/new_Meeting")
def new_Meeting():
    app.logger.debug("I'm making a new entry in the database")
    
    eventString = request.args.get('events')
    eventList = json.loads(eventString)
    owner = request.args.get('owner')
    names = request.args.get('invitees')
    startDate = flask.session['begin_date']
    startTime = flask.session['begin_time']
    endDate = flask.session['end_date']
    endTime = flask.session['end_time']
    dt_range = [startDate, endDate, startTime, endTime]
    names = names.split(',')
    betterNames = []
    for name in names:
        betterNames.append(name.strip())

    newMeeetingInfo = add_new_meeting(eventList, betterNames, owner, dt_range)
    reslt = newMeeetingInfo["result"]
    flask.session['new_meeting_id'] = newMeeetingInfo["id"]

    return flask.jsonify(result = reslt)

def add_new_meeting(eventList, invitees, owner, dt_range):
    app.logger.debug("I'm in add_new_meeting")
    already_responded = []
    record = { "owner": owner,
        "invitees": invitees,
        "already_responded": already_responded,
        "available_times": eventList,
        "range": dt_range
    }
    app.logger.debug(record)
    try:
        inserted = collection.insert_one(record)
        _id = str(inserted.inserted_id)
        print(_id)
        rslt = True
    except:
        app.logger.debug("Insertion of memo failed")
        _id = "0"
        rslt = False
    app.logger.debug("I'm returning from add_new_meeting")
    return {"result": rslt, "id": _id}
####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST: 
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable. 
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead. 
#
####

def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 
  
  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

@app.route('/oauth2callback_part2')
def oauth2callback_part2():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback_part2', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function. 
  
  ## The *second* time we enter here, it's a callback 
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1. 
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('respond'))


#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use. 
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")
    daterange = request.form.get('daterange')
    flask.session['begin_time'] = request.form.get('begin_time')
    flask.session['end_time'] = request.form.get('end_time')
    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1], 
      flask.session['begin_date'], flask.session['end_date']))
    return flask.redirect(flask.url_for("choose"))

####
#
#   Initialize session variables 
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main. 
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("8:00")
    flask.session["end_time"] = interpret_time("17:00")
    app.logger.debug("Initializing values")

def interpret_time( text ):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try: 
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        as_arrow = as_arrow.replace(year=2016) #HACK see below
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
              .format(text))
        raise
    return as_arrow.isoformat()
    #HACK #Workaround
    # isoformat() on raspberry Pi does not work for some dates
    # far from now.  It will fail with an overflow from time stamp out
    # of range while checking for daylight savings time.  Workaround is
    # to force the date-time combination into the year 2016, which seems to
    # get the timestamp into a reasonable range. This workaround should be
    # removed when Arrow or Dateutil.tz is fixed.
    # FIXME: Remove the workaround when arrow is fixed (but only after testing
    # on raspberry Pi --- failure is likely due to 32-bit integers on that platform)


def interpret_date( text ):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
      as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
          tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####
  
def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict.
    The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")  
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal: 
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]

        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })
    return sorted(result, key=cal_sort_key)


def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"
    
#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running under green unicorn)
  app.run(port=CONFIG.PORT,host="0.0.0.0")
    
