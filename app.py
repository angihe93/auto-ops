from __future__ import print_function
import os
import psycopg2
from flask import Flask, render_template, request, redirect
import flask
import bcrypt
import datetime
import pytz
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.oauth2.credentials
import google_auth_oauthlib.flow

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
            # return flask.redirect(flask.url_for('mainsiteops'))
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('''select cast(orders.res_date_start as varchar), lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ', ' || users.address_apt || ', NY ' || users. address_zip as address,
                        '$' || cast(round( CAST(reservations.charge as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.deposit as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.tax as numeric), 2) as varchar),
                        '(' || items.id || ') ' || items.name, cast(orders.res_date_end as varchar),
                        reservations.is_extended, 'https://www.hubbub.shop/inventory/i/id=' || cast(items.id as varchar), '@' || users.payment,
                        orders.id, orders.renter_id, order_dropoffs.dt_sched, order_dropoffs.dt_completed, order_pickups.dt_sched, order_pickups.dt_completed,
                        reservations.dt_created
                        from orders
                        inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
                        inner join items on items.id=orders.item_id
                        inner join users on users.id=orders.renter_id
                        inner join profiles on profiles.id=users.id
                        left join order_dropoffs on orders.id=order_dropoffs.order_id
                        left join order_pickups on orders.id=order_pickups.order_id
                        order by orders.res_date_start, reservations.dt_created''')

            rows = cur.fetchall()
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
                    logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],logi[-1],str(logi[5])+' '+logi[6]+', '+logi[7]+', NY '+logi[8],logi[1],'','',''))
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
            # # return render_template("index.html")
    return render_template("key.html")

# @app.route('/mainsiteops')
# def mainsiteops():
#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute('''select cast(orders.res_date_start as varchar), lower(replace(users.name,',',' ')), users.email, profiles.phone, users.address_num || ' ' || users.address_street || ', ' || users.address_apt || ', NY ' || users. address_zip as address,
#                 '$' || cast(round( CAST(reservations.charge as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.deposit as numeric), 2) as varchar), '$' || cast(round( CAST(reservations.tax as numeric), 2) as varchar),
#                 '(' || items.id || ') ' || items.name, cast(orders.res_date_end as varchar),
#                 reservations.is_extended, 'https://www.hubbub.shop/inventory/i/id=' || cast(items.id as varchar), '@' || users.payment,
#                 orders.id, orders.renter_id, order_dropoffs.dt_sched, order_dropoffs.dt_completed, order_pickups.dt_sched, order_pickups.dt_completed,
#                 reservations.dt_created
#                 from orders
#                 inner join reservations on orders.renter_id=reservations.renter_id and orders.item_id=reservations.item_id and orders.res_date_start = reservations.date_started and orders.res_date_end = reservations.date_ended
#                 inner join items on items.id=orders.item_id
#                 inner join users on users.id=orders.renter_id
#                 inner join profiles on profiles.id=users.id
#                 left join order_dropoffs on orders.id=order_dropoffs.order_id
#                 left join order_pickups on orders.id=order_pickups.order_id
#                 order by orders.res_date_start, reservations.dt_created''')
#
#     rows = cur.fetchall()
#     # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
#     event_li = []
#     for i in rows:
#         if type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # both dropoff and pickup needs events
#             event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,1)) # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
#         elif type(i[15])!=type(None) and type(i[16])==type(None) and type(i[17])==type(None) and type(i[18])==type(None): # only dropoff need event
#             event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],1,0))
#         elif type(i[15])!=type(None) and type(i[16])!=type(None) and type(i[17])!=type(None) and type(i[18])==type(None): # only pickup need event
#             event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,1))
#         else: # neither needs event yet
#             event_li.append((i[0],i[9],i[13],i[14],i[15],i[17],0,0))
#
#     cur.execute("select * from logistics")
#     logistics = cur.fetchall()
#
#     logi_li = [] # everything in event_li except dt_sched, plus chosen time, address, notes for pick up and dropoff
#     # res date start, res date end, order id, renter id, 1 if dropoff needs event, 1 if pickup needs event
#     # add logistics data, where either dropoff needs event or pickup needs event, add the corresponding logistics row
#     for i in event_li:
#         if i[-2]==1 and i[-1]==0: # dropoff needs event
#             # print('dropoff needs event')
#             # join with logstics on dt_sched and renter_id, make sure dt_sched is from order_dropoffs
#             dts = i[4]
#             rid = i[3]
#             logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
#             logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],logi[-1],str(logi[5])+' '+logi[6]+', '+logi[7]+', NY '+logi[8],logi[1],'','',''))
#             # print(logi)
#         elif i[-1]==1 and i[-2]==0: # pickup needs event
#             # print('pickup needs event')
#             dts = i[5]
#             rid = i[3]
#             logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
#             logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','',logi[-1],str(logi[5])+' '+logi[6]+' '+logi[7]+' '+logi[8],logi[1]))
#             # print(logi)
#         elif i[-2]==1 and i[-1]==1: # both needs events
#             # print('both need event')
#             dts_d = i[4]
#             dts_p = i[5]
#             rid = i[3]
#             logi_d = [l for l in logistics if l[0]==dts_d and l[4]==rid][0]
#             logi_p = [l for l in logistics if l[0]==dts_p and l[4]==rid][0]
#             logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],logi_d[-1],str(logi_d[5])+' '+logi_d[6]+' '+logi_d[7]+' '+logi_d[8],logi_d[1],logi_p[-1],str(logi_p[5])+' '+logi_p[6]+' '+logi_p[7]+' '+logi_p[8],logi_p[1]))
#         else: # neither needs event
#             # print('else')
#             logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','','','',''))
#
#
#     cur.close()
#     conn.close()
#
#     # list to store calendar info: dropoff/pickup type, renter name, rental start (for dropoff), rental end (for pickup), chosen time, items, total due/deposit return, task id from ops (id=order id), renter address, renter phone, renter payment
#     # add it to session so makecalevents can access https://stackoverflow.com/questions/27611216/how-to-pass-a-variable-between-flask-pages
#
#     return render_template('index.html', rows=rows, logi_li=logi_li)
#     # return render_template("index.html")

@app.route('/test')
def test_api_request():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])
    print('credentials loaded from session')

    # try:
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
    print('service built')

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    # print('Getting the upcoming 10 events')
    # events_result = service.events().list(calendarId='primary', timeMin=now,
    #                                       maxResults=10, singleEvents=True,
    #                                       orderBy='startTime').execute()
    # events = events_result.get('items', [])
    #
    # if not events:
    #     print('No upcoming events found.')
    #     return
    #
    # # Prints the start and name of the next 10 events
    # for event in events:
    #     start = event['start'].get('dateTime', event['start'].get('date'))
    #     print(start, event['summary'])
    #
    event = {
      'summary': 'Google I/O 2021',
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
      'recurrence': [
        'RRULE:FREQ=DAILY;COUNT=2'
      ],
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

    return event.get('htmlLink')

    # except: # HttpError as error:
    #     print('An error occurred: %s') # % error)
    #     return "error"

    def credentials_to_dict(credentials):
        return {'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'id_token': credentials.id_token}
    # Save credentials back to session in case access token was refreshed.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    flask.session['credentials'] = credentials_to_dict(credentials)


    # return flask.jsonify(**files)

@app.route('/authorize')
def authorize():
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      'google-credentials.json', scopes=SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    # flow.redirect_uri = 'https://localhost:8080/oauth2callback'

    authorization_url, state = flow.authorization_url(
      # Enable offline access so that you can refresh an access token without
      # re-prompting the user for permission. Recommended for web server apps.
      access_type='offline',
      # Enable incremental authorization. Recommended as a best practice.
      include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state
    print('in authorize: flask.session',flask.session)

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    print('in oauth2callback: flask.session',flask.session)
    state = flask.session['state']
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      'google-credentials.json', scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    # flow.redirect_uri = 'https://localhost:8080/oauth2callback'


    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'  # https://stackoverflow.com/a/59052439/19228216
    flow.fetch_token(authorization_response=authorization_response)

    def credentials_to_dict(credentials):
        return {'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'id_token': credentials.id_token}
    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session['credentials'] = credentials_to_dict(credentials)

    # return flask.redirect(flask.url_for('test_api_request')) # test_api_request
    return flask.redirect(flask.url_for('gfg'))



# @app.route('/makecalevents/<ltype>', methods =["GET", "POST"])
@app.route('/makecalevents', methods =["GET", "POST"])
# def makecalevents(ltype): # include this in return of oauth2callback
def makecalevents():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])
    print('credentials loaded from session')

    # try:
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
    print('service built')

    ltype = request.args.get('ltype')
    print('ltype:',ltype)
    renter = request.args.get('renter')
    print('renter:',renter)
    date = request.args.get('date')
    time = request.args.get('time')
    ### check in db if there are other items being pickedup/dropped off for the same user at the same time
    iname = request.args.get('item_name')
    ilink = request.args.get('item_link')
    tid = request.args.get('tid')
    tlink = 'https://admin.hubbub.shop/task/'+ltype+'/id='+tid
    address = request.args.get("address")
    phone = request.args.get("phone")
    payment = request.args.get("payment")
    print('date:',date)
    print('time:',time)
    print('iname',iname)
    print('ilink:',ilink)
    print('tid:',tid)
    print('address:',address)
    print('phone:',phone)
    print('payment:',payment)
    start_time_dt=datetime.datetime.strptime(date+' '+time,'%Y-%m-%d %H:%M:%S')
    start_time_str=date+'T'+time
    print('start_time_dt',start_time_dt)
    end_time_dt=start_time_dt + datetime.timedelta(hours=1)
    end_time_str=end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str=end_time_str.replace(' ','T')
    print('end_time_dt',end_time_dt)
    print('end_time_str',end_time_str)
    df_event = {
        'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
        'location': address,
        'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
        'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
        'description': """ %s \n\nTotal $ from %s
         """%(tlink,payment),
        'reminders': {
            'useDefault': False,
            'overrides': [
            {'method': 'popup', 'minutes': 30},
            ],
          },
        # 'tag':,
        }
    print('df_event',df_event)

    pu_event = {
        'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
        'location': address,
        'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
        'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
        'description': """ %s \n\nDeposit $ to %s
         """%(tlink,payment),
        'reminders': {
            'useDefault': False,
            'overrides': [
            {'method': 'popup', 'minutes': 30},
            ],
          },
    }

    if ltype=='dropoff':
        event = service.events().insert(calendarId='c_puitor2pblvjgid67mj32m6em0@group.calendar.google.com', body=df_event).execute()
    elif ltype=='pickup':
        event = service.events().insert(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', body=pu_event).execute()
    print('Event created: %s' % (event.get('htmlLink')))

    return """event created at <a href=%s>%s </a>, double check for accuracy and add attendees"""%(event.get('htmlLink'),event.get('htmlLink'))



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, ssl_context='adhoc')
