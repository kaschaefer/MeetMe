# proj7-Gcal
Snarf appointment data from a selection of a user's Google calendars 
Authors: Michal Young, Mikaela Schaefer

Contact: kaelas@uoregon.edu

## Description
This program runs a Python/Flask server that controls authentication and queries for a web application that interacts with 
the Google Calendar API.
On the client side, users are asked to provide authentication. The user chooses a range of dates, times, and which
public calendars they would like to include in the search. Then the web application sends a request to the server
for events in the chosen calendars that overlap the specified time and date ranges.

### To Do
At the moment, this program reverts to displaying default times after the user submits their chosen time range. However, the correct events are still shown. Thus, for the project to be complete, this small problem must be fixed.
