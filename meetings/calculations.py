import arrow
import logging

#This function takes a gcal service, a list of calendars, and a dateTime range and returns
# a list of all events from the list of calendars that fall within or overlap that dateTime range
def getEventsFromAllCalendars(gcal_service, calendars, begin, begin_time, end, end_time):
    b_hrs, b_mins = begin_time.split(':')
    e_hrs, e_mins = end_time.split(':')
    showEvents = []

    # Get all events from the given calendars
    for calendar in calendars:
        calendarID = str(calendar)
        page_token = None
        # For each day in the given date range on the given calendar (sorted)
        for day in arrow.Arrow.span_range('day', begin, end):

            day_start = arrow.get(day[0])
            day_end = arrow.get(day[1])

            #While there are still more events to get
            while True:
                #Get the appropriate time range
                current_begin = day[0].shift(hours=+int(b_hrs), minutes=+int(b_mins))
                current_end = day[1].replace(hour=int(e_hrs), minute=int(e_mins))
                events = gcal_service.events().list(calendarId=calendarID, pageToken=page_token, timeMax=current_end, timeMin=current_begin).execute()
                
                #For each event in the list of events
                for event in events['items']:
                    eventStart = event['start']
                    eventFinish = event['end']
                    #Check for transparent events
                    if 'transparency' in event and event['transparency'] == "transparent":
                        continue
                    showEvents.append(event)
                page_token = events.get('nextPageToken')
                if not page_token:
                   break
    
    finished_events = [ ]
    for event in showEvents:
        eventDetails = []
        string = " "
        #If the event has a start time, it is not an all day event
        #String holds a String representation of what the event's detais are (for displaying)
        #Start date is either a date with no start time
        #or start date is a DateTime object
        if 'dateTime' in event['start']:
            start_time = arrow.get(event['start']['dateTime'])
            string = str(beautify_date(start_time))
            string = string + " " + str(beautify_time(start_time))
            end_time = arrow.get(event['end']['dateTime'])
            string = string + " - " + str(beautify_time(end_time)) + ": "
            string = string + event['summary']
        #Event is all day, so don't try to parse times
        else:
            start_time = arrow.get(event['start']['date'])
            start_time = start_time.replace(tzinfo='US/Pacific', hour=int(b_hrs), minute=int(b_mins))
            end_time = start_time.replace(hour=int(e_hrs), minute=int(e_mins))
            string = str(beautify_date(start_time))
            string = string + " :" + event['summary']
        #end if/else statement
        #create a list of event summaries and their start date
        eventDetails = [start_time, end_time, event['summary'], string]
        finished_events.append(eventDetails)
    #end for loop

    #the events are already sorted by time, so I need to sort them by date
    #finished_events.sort(key=lambda i: i[1])

    #now create a new list with just the strings
    #fin_events = [ ]
    #for event in finished_events:
    #    fin_events.append(event[0])

    #return a list of strings that includes the event date, start and end times, and summary       

    return finished_events

def getBlocks(eventList, beginDate, beginTime, endDate, endTime):
    #Get hours and minutes of begin and end time for later use
    b_hrs, b_mins = beginTime.split(':')
    e_hrs, e_mins = endTime.split(':')

    #sort the list of events by start time
    sortedEvents = sorted(eventList, key=lambda k: k[0])
    print("The sorted events are: ")
    for thing in sortedEvents:
        print(thing)

    #create an empty list to store the blocks in
    already_processed = [ ]

    for day in arrow.Arrow.span_range('day', beginDate, endDate):
        for time_block in sortedEvents:
            joined = False
            if time_block[0] > day[0] and time_block[1] < day[1]:
                for current_block in already_processed:
                    if current_block[0] > day[0] and current_block[1] < day[1]:
                        # if time_block start time is later than current_block start time
                        if time_block[0] > current_block[0]:
                            # if time_block end time is later than current_block end time
                            if time_block[1] > current_block[1]:
                                current_block[1] = time_block[1]
                                joined = True
                            # time_block end time is earlier than current_block end time
                            else:
                                joined = True

                        # if time_block end time is earlier current_block end time
                        elif time_block[1] < current_block[1]:
                            #if time_block start time is earlier current_block start time
                            if time_block[0] < current_block[0]:
                                current_block[0] = time_block[0]
                                joined = True
                        #if time block start time is earlier than current block start
                        # AND time block end is later than current block end
                        elif time_block[0] < current_block[0]:
                            if time_block[1] > current_block[1]:
                                current_block[0] = time_block[0]
                                current_block[1] = time_block[1]
                                joined = True
                    
                #endfor
                if not joined:
                    already_processed.append(time_block)

    #endfor
    print("Free Blocks is exiting")
    for thing in already_processed:
        print(thing)
    print(already_processed)
    return

def beautify_date(date):
    try: 
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

def beautify_time(time):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"