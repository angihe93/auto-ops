from __future__ import print_function
import os
import psycopg2
from flask import Flask, render_template, request, redirect
import bcrypt
import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.oauth2.credentials
import google_auth_oauthlib.flow

app = Flask(__name__)

host = os.environ.get('DB_HOST')
database = os.environ.get('DB_DB')
user = os.environ.get('DB_USER')
password = os.environ.get('DB_PW')

def get_db_connection():
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password)
    return conn


@app.route('/', methods =["GET", "POST"])
def gfg():
    if request.method == "POST":
        key = request.form.get("key")
        if bcrypt.checkpw(bytes(key,encoding='utf-8'),b'$2b$12$h4LsLf0upvAPCiKTZFnxnOj25gp9OTmeRtca3y8eULezXvdlF3O1C'):
            conn = get_db_connection()
            cur = conn.cursor()
            # cur.execute('SELECT * FROM orders;')
            # cur.execute('''select orders.res_date_start, lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ' ' || users.address_apt || ' ' || users. address_zip as address,
            #             '$' || cast(round( CAST(reservations.charge as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.deposit as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.tax as numeric), 2) as varchar),
            #             '(' || items.id || ') ' || items.name, orders.res_date_end,
            #             reservations.is_extended, 'https://www.hubbub.shop/inventory/i/id=' || cast(items.id as varchar), '@' || users.payment,
            #             orders.id, orders.renter_id
            #             from orders
            #             inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
            #             inner join items on items.id=orders.item_id
            #             inner join users on users.id=orders.renter_id
            #             inner join profiles on profiles.id=users.id
            #             order by orders.res_date_start, users.name''')
            cur.execute('''select cast(orders.res_date_start as varchar), lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ' ' || users.address_apt || ' ' || users. address_zip as address,
                        '$' || cast(round( CAST(reservations.charge as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.deposit as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.tax as numeric), 2) as varchar),
                        '(' || items.id || ') ' || items.name, cast(orders.res_date_end as varchar),
                        reservations.is_extended, 'https://www.hubbub.shop/inventory/i/id=' || cast(items.id as varchar), '@' || users.payment,
                        orders.id, orders.renter_id, order_dropoffs.dt_sched, order_dropoffs.dt_completed, order_pickups.dt_sched, order_pickups.dt_completed
                        from orders
                        inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
                        inner join items on items.id=orders.item_id
                        inner join users on users.id=orders.renter_id
                        inner join profiles on profiles.id=users.id
                        left join order_dropoffs on orders.id=order_dropoffs.order_id
                        left join order_pickups on orders.id=order_pickups.order_id
                        order by orders.res_date_start, users.name''')
            # orders = cur.fetchall()
            rows = cur.fetchall()
            # print('rows',rows[-5:])

            # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
            event_li = []
            for i in rows:
                if type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # both dropoff and pickup needs events
                    event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,1)) # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
                elif type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])==type(None) and type(i[18])==type(None): # only dropoff need event
                    event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,0))
                elif type(i[15])!=type(None) and type(i[16])!=type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # only pickup need event
                    event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,1))
                else: # neither needs event yet
                    event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,0))

            cur.execute("select * from logistics")
            logistics = cur.fetchall()

            logi_li = [] # everything in event_li except dt_sched, plus chosen time, address, notes for pick up and dropoff
            # res date start, res date end, order id, renter id, 1 if dropoff needs event, 1 if pickup needs event
            # add logistics data, where either dropoff needs event or pickup needs event, add the corresponding logistics row
            for i in event_li:
                if i[-2]==1 and i[-1]==0: # dropoff needs event
                    # print('dropoff needs event')
                    # join with logstics on dt_sched and renter_id, make sure dt_sched is from order_dropoffs
                    dts = i[4]
                    rid = i[3]
                    logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
                    logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],logi[-1],str(logi[5])+' '+logi[6]+' '+logi[7]+' '+logi[8],logi[1],'','',''))
                    # print(logi)
                elif i[-1]==1 and i[-2]==0: # pickup needs event
                    # print('pickup needs event')
                    dts = i[5]
                    rid = i[3]
                    logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
                    logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','',logi[-1],str(logi[5])+' '+logi[6]+' '+logi[7]+' '+logi[8],logi[1]))
                    # print(logi)
                elif i[-2]==1 and i[-1]==1: # both needs events
                    # print('both need event')
                    dts_d = i[4]
                    dts_p = i[5]
                    rid = i[3]
                    logi_d = [l for l in logistics if l[0]==dts_d and l[4]==rid][0]
                    logi_p = [l for l in logistics if l[0]==dts_p and l[4]==rid][0]
                    logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],logi_d[-1],str(logi_d[5])+' '+logi_d[6]+' '+logi_d[7]+' '+logi_d[8],logi_d[1],logi_p[-1],str(logi_p[5])+' '+logi_p[6]+' '+logi_p[7]+' '+logi_p[8],logi_p[1]))
                else: # neither needs event
                    # print('else')
                    logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','','','',''))


            cur.close()
            conn.close()

            # list to store calendar info: dropoff/pickup type, renter name, rental start (for dropoff), rental end (for pickup), chosen time, items, total due/deposit return, task id from ops (id=order id), renter address, renter phone, renter payment
            # add it to session so makecalevents can access https://stackoverflow.com/questions/27611216/how-to-pass-a-variable-between-flask-pages

            return render_template('index.html', rows=rows, logi_li=logi_li)
            # return render_template("index.html")
    return render_template("key.html")


@app.route('/makecalevents', methods =["GET", "POST"])
def makecalevents():
    # see the tasks where time is scheduled
    # click on tasks to send cal events for, with option to edit
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        print("os.path.exists('token.json')")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        print('not creds or not creds.valid')
        if creds and creds.expired and creds.refresh_token:
            print("creds and creds.expired and creds.refresh_token")
            creds.refresh(Request())
        else:
            print("else")
            # flow = InstalledAppFlow.from_client_secrets_file(
            #     'google-credentials.json', SCOPES)
            # # creds = flow.run_local_server(port=0)
            # creds = flow.run_local_server(port=8080)
            flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                'google-credentials.json', scopes=SCOPES)
            flow.redirect_uri = 'https://auto-ops.herokuapp.com/makecalevents'

            authorization_url, state = flow.authorization_url(
                # Enable offline access so that you can refresh an access token without
                # re-prompting the user for permission. Recommended for web server apps.
                access_type='offline',
                # Enable incremental authorization. Recommended as a best practice.
                include_granted_scopes='true')
        return redirect(authorization_url)
        # Save the credentials for the next run
        # with open('token.json', 'w') as token:
        #     token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

        event = {
          'summary': 'Google I/O 2015',
          'location': '800 Howard St., San Francisco, CA 94103',
          'description': 'A chance to hear more about Google\'s developer products.',
          'start': {
            'dateTime': '2022-07-13T09:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
          },
          'end': {
            'dateTime': '2022-07-28T17:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
          },
          # 'recurrence': [
          #   'RRULE:FREQ=DAILY;COUNT=2'
          # ],
          'attendees': [
            {'email': 'lpage@example.com'},
            {'email': 'sbrin@example.com'},
          ],
          'reminders': {
            'useDefault': False,
            'overrides': [
              {'method': 'email', 'minutes': 24 * 60},
              {'method': 'popup', 'minutes': 10},
            ],
          },
        }

        event = service.events().insert(calendarId='ah3354@columbia.edu', body=event).execute()
        print('Event created: %s' % (event.get('htmlLink')))

    except HttpError as error:
        print('An error occurred: %s' % error)


    return render_template("makecalevents.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
