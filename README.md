# MeetMe Web Application
Authors: Michal Young, Mikaela Schaefer

Contact: kaelas@uoregon.edu

## Description
This program runs a Python/Flask server that controls authentication and queries for a web application that interacts with 
the Google Calendar API. Somebody proposes a meeting and specifies date and time ranges.  The application helps prepare an invitation, which is sent out to other attendees.  Each attendee responds with their availability for the meeting.  For both the meeting proposer and the attendees, the application draws information from selected Google calendars to narrow the potential times down to times that do not conflict with existing non-transparent (that is, busy) events. To be able to use this application, you will need to download and host your own version.

### Design Choices
#### Privacy
I chose to only store users' free times because I thought that this method would store the least amount of personal data possible out of all possible implementations. I do not allow anyone to see anyone else's busy times, including the person planning the event. I also do not ask for users' email addresses or any other personal information. To be fair, this allows anyone who gets ahold of the unique Meeting ID and the full name of someone who is invited to the meeting to respond to the meeting request. However, since responding to the meeting request does not reveal anything about other users' and since Google authentication is required to access the users' calendars, I do not think that this poses a great security risk.

#### UX
I chose to implement a multi-page design over a single-page design because in some rare instances, it is helpful for the user to be able to navigate "backwards" through the control flow. While I understand this could be done using single-page web design, I did not think I had the time to implement this.

### My Thoughts
#### What Works
The application, on the whole, works as expected. A meeting "owner" is able to see when all of the people they invited are available. Users' free times are correctly integrated into the group's free time. All day events are handled well and users can change their selection of calendars if they wish. Each page is simple and easy to read, and scales down to phone-size without loosing too much readability. Dates and times are printed in a very easy to read manner and the pages are not cluttered with information.

#### What Doesn't
*The application does not generate a "final" meeting time email, similar to the invitiation email that is generated when you make a new meeting request. 
*Meeting invitees are not made aware of the date/time range that the meeting will be in until they select their calendars, which I think is poor UI
*The application does not handle the case where there are no available meeting times
*The code is pretty repetitive at times, the result of a project done at the last minute

### Next Version
The next version of the application would fix the above problems as follows:
*Application would generate an email to send to invitees with finalized date and time
*A meeting owner would be able to choose a meeting duration and only see available times for at least that duration. The application already has the functionality to implement this in the crop function (I just didn't have time)
*The date and time range chosen by the meeting owner would be displayed on the page when another user is responding to that meeting request
*The code would be cleaner (Sorry!) with repetitive logic factored into classes and functions
*The application would notify the meeting owner if there were no available times left in the database entry so that the owner could either change the date/time range or make a new request
*Would also fix these known bugs:
####Known Bugs
*There is a timezone issue, such that if you try to schedule a meeting in a range that extends past 6pm, the application breaks. However, the application works for all times from 12:00am to 5:59pm.
*If a user *only* has transparent events in their calendar and no other events, the event list for that user is empty and the application breaks. A very simple fix, but one I simply did not have time to implement.