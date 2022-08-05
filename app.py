from __future__ import print_function
import os
import psycopg2
from flask import Flask, render_template, request, redirect
# from flask_login import UserMixin, LoginManager
import flask
# import jwt, time, random
from collections import defaultdict
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
app.secret_key = os.environ.get('SECRET_KEY')
# login_manager = LoginManager()
# login_manager.init_app(app)

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

@app.route('/',)
def index():
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
    try:
        events_result = service.events().list(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        print('events_result',events_result)
        return flask.redirect('mainsiteops')
        # events = events_result.get('items', [])
    except:
        print("exception when accessing events in index()")
        # return "please login with valid email"
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

@app.route('/mainsiteops', methods =["GET", "POST"])
def mainsiteops():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])
    print('credentials loaded from session')

    try:
        service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
        print('service built')
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        print('events_result',events_result)
        # return flask.redirect('mainsiteops')
        # events = events_result.get('items', [])
    except:
        print("exception when accessing events in mainsiteops")
        # return "please login with valid email"
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

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
                order by orders.res_date_start, users.email, reservations.dt_created''')

    rows = cur.fetchall()
    print('rows:',rows[-5:])
    # res date start, res date end, order id, renter id, order_dropoffs dt_sched, order_pickups dt_sched, 1 if dropoff needs event, 1 if pickup needs event
    # rows to main site ops columns mapping
    # i[0]: rental start
    # i[1]: customer name
    # i[2]: customer email
    # i[3]: customer phone
    # i[4]: customer location
    # i[5]: sub price
    # i[6]: deposit
    # i[7]: tax
    # i[8]: item id and name
    # i[9]: res date end
    # i[10]: is extended
    # i[11]: item link
    # i[12]: payment
    # i[13]: order id
    # i[14]: renter id
    # i[15]: order_dropoffs.dt_sched
    # i[16]: order_dropoffs.dt_completed
    # i[17]: order_pickups.dt_sched
    # i[18]: order_pickups.dt_completed
    # i[19]: reservations.dt_created

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
            #### if logi[-1] ie. chosen time is null, then append timeslots instead, and change link to the task id ###
            if type(logi[-1])==type(None):
                dropoff_time=logi[3] # show timeslots
                activate_makecalevents_url_dropoff=0
            else:
                dropoff_time=logi[-1]
                activate_makecalevents_url_dropoff=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],dropoff_time,str(logi[5])+' '+logi[6]+', '+logi[7]+', NY '+logi[8],logi[1],'','','',activate_makecalevents_url_dropoff,0))
            # print(logi)
        elif i[-1]==1 and i[-2]==0: # pickup needs event
            # print('pickup needs event')
            dts = i[5]
            rid = i[3]
            logi = [l for l in logistics if l[0]==dts and l[4]==rid][0]
            if type(logi[-1])==type(None):
                pickup_time=logi[3] # show timeslots
                activate_makecalevents_url_pickup=0
            else:
                pickup_time=logi[-1]
                activate_makecalevents_url_pickup=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','',pickup_time,str(logi[5])+' '+logi[6]+' '+logi[7]+' '+logi[8],logi[1],0,activate_makecalevents_url_pickup))
            # print(logi)
        elif i[-2]==1 and i[-1]==1: # both needs events
            # print('both need event')
            dts_d = i[4]
            dts_p = i[5]
            rid = i[3]
            logi_d = [l for l in logistics if l[0]==dts_d and l[4]==rid][0]
            logi_p = [l for l in logistics if l[0]==dts_p and l[4]==rid][0]
            if type(logi_d[-1])==type(None):
                dropoff_time=logi_d[3]
                activate_makecalevents_url_dropoff=0
            else:
                dropoff_time=logi_d[-1]
                activate_makecalevents_url_dropoff=1
            if type(logi_p[-1])==type(None):
                pickup_time=logi_p[3]
                activate_makecalevents_url_pickup=0
            else:
                pickup_time=logi_p[-1]
                activate_makecalevents_url_pickup=1
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],dropoff_time,str(logi_d[5])+' '+logi_d[6]+' '+logi_d[7]+' '+logi_d[8],logi_d[1],pickup_time,str(logi_p[5])+' '+logi_p[6]+' '+logi_p[7]+' '+logi_p[8],logi_p[1], activate_makecalevents_url_dropoff,activate_makecalevents_url_pickup))
        else: # neither needs event
            # print('else')
            logi_li.append((i[0],i[1],i[2],i[3],i[6],i[7],'','','','','','',0,0))

    # check for extensions and prepend appropriate pickup dates to pickup datetime column
    cur.execute("select * from extensions")
    extensions=cur.fetchall()
    ext_li=[] # holds the date that go in pickup datetime
    for i in rows:
        # if order number is in extensions, add extension values, else, add none
        e = [e[4] for e in extensions if e[0]==i[13]]
        if len(e)>0:
            # if multiple extensions on same item/order, multiple rows in extensions with same order id but res dates are changed
            # sort e by res_date_end, take the latest res_date_end
            e.sort()
            ext_li.append(e[-1])
        else:
            ext_li.append(i[9])

    cur.close()
    conn.close()

    # list to store calendar info: dropoff/pickup type, renter name, rental start (for dropoff), rental end (for pickup), chosen time, items, total due/deposit return, task id from ops (id=order id), renter address, renter phone, renter payment
    # add it to session so makecalevents can access https://stackoverflow.com/questions/27611216/how-to-pass-a-variable-between-flask-pages

    return render_template('index.html', rows=rows, logi_li=logi_li, ext_li=ext_li) #, activate_makecalevents_url=activate_makecalevents_url)
            # # return render_template("index.html")
    # return render_template("key.html")


# @app.route('/test')
# def test_api_request():
#     if 'credentials' not in flask.session:
#         return flask.redirect('authorize')
#
#     # Load credentials from the session.
#     credentials = google.oauth2.credentials.Credentials(
#       **flask.session['credentials'])
#     print('credentials loaded from session')
#
#     # try:
#     service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
#     print('service built')
#
#     # Call the Calendar API
#     now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
#
#     event = {
#       'summary': 'Google I/O 2021',
#       'location': '800 Howard St., San Francisco, CA 94103',
#       'description': 'A chance to hear more about Google\'s developer products.',
#       'start': {
#         'dateTime': '2022-07-13T09:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#       },
#       'end': {
#         'dateTime': '2022-07-28T17:00:00-07:00',
#         'timeZone': 'America/Los_Angeles',
#       },
#       'recurrence': [
#         'RRULE:FREQ=DAILY;COUNT=2'
#       ],
#       'attendees': [
#         {'email': 'lpage@example.com'},
#         {'email': 'sbrin@example.com'},
#       ],
#       'reminders': {
#         'useDefault': False,
#         'overrides': [
#           {'method': 'email', 'minutes': 24 * 60},
#           {'method': 'popup', 'minutes': 10},
#         ],
#       },
#     }
#
#     event = service.events().insert(calendarId='ah3354@columbia.edu', body=event).execute()
#     print('Event created: %s' % (event.get('htmlLink')))
#
#     return event.get('htmlLink')
#
#     # except: # HttpError as error:
#     #     print('An error occurred: %s') # % error)
#     #     return "error"

    # def credentials_to_dict(credentials):
    #     return {'token': credentials.token,
    #             'refresh_token': credentials.refresh_token,
    #             'token_uri': credentials.token_uri,
    #             'client_id': credentials.client_id,
    #             'client_secret': credentials.client_secret,
    #             'scopes': credentials.scopes,
    #             'id_token': credentials.id_token}
    # # Save credentials back to session in case access token was refreshed.
    # # ACTION ITEM: In a production app, you likely want to save these
    # #              credentials in a persistent database instead.
    # flask.session['credentials'] = credentials_to_dict(credentials)
    #
    #
    # # return flask.jsonify(**files)

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
    return flask.redirect(flask.url_for('mainsiteops'))



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

    # from db get items for the same user with the same set pickup/dropoff datetime
    # join orders and logistics and reservations, get item names, links, prices
    # or get items in same event from rows, event_li, logi_li from gfg

    ltype = request.args.get('ltype')
    print('ltype:',ltype)
    renter = request.args.get('renter')
    print('renter:',renter)
    rid = request.args.get('rid')
    print('renter id:',rid)
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
    notes = request.args.get("notes")
    email = request.args.get("email")


    conn = get_db_connection()
    cur = conn.cursor()

    if ltype=='dropoff':
        items_in_dropoff_query = """
            select distinct reservations.item_id, items.name,
            round( CAST(reservations.charge as numeric), 2),
            round( CAST(reservations.deposit as numeric), 2), round( CAST(reservations.tax as numeric), 2)
            from order_dropoffs
            inner join logistics on logistics.dt_sched=order_dropoffs.dt_sched and logistics.renter_id=order_dropoffs.renter_id
            inner join reservations on order_dropoffs.dropoff_date=reservations.date_started and order_dropoffs.renter_id=reservations.renter_id
            inner join items on reservations.item_id=items.id
            where reservations.is_calendared=TRUE and order_dropoffs.renter_id=%s and order_dropoffs.dropoff_date='%s' and logistics.chosen_time='%s'
        """%(rid,date,time)
        cur.execute(items_in_dropoff_query)
        rows = cur.fetchall()
        print('items in dropoff rows:',rows[-10:])

    elif ltype=='pickup':
        ### need to handle extensions!! order_pickups show post extension dates, but reservations.date_ended might not and the date associated with pickup time is the unextended date
        ### add extended dates in pickup date time columns?
        p_date=request.args.get("p_date")
        items_in_pickup_query = """
            select distinct reservations.item_id, items.name,
            round( CAST(reservations.charge as numeric), 2),
            round( CAST(reservations.deposit as numeric), 2), round( CAST(reservations.tax as numeric), 2)
            from order_pickups
            inner join logistics on logistics.dt_sched=order_pickups.dt_sched and logistics.renter_id=order_pickups.renter_id
            inner join reservations on order_pickups.pickup_date=reservations.date_ended and order_pickups.renter_id=reservations.renter_id
            inner join items on reservations.item_id=items.id
            where reservations.is_calendared=TRUE and order_pickups.renter_id=%s and order_pickups.pickup_date='%s' and logistics.chosen_time='%s'
        """%(rid,p_date,time)
        cur.execute(items_in_pickup_query)
        rows = cur.fetchall()
        print('items in pickup rows:',rows[-10:])

    cur.close()
    conn.close()

    ## user notes
    ## user email (to put in body or as attendee)
    print('date:',date)
    print('time:',time)
    # print('iname',iname)
    # print('ilink:',ilink)
    # put all items in same pickup/dropoff in a list
    # if len(rows)==1:
    iid_li=[i[0] for i in rows]
    iname_li=[i[1] for i in rows]
    ilink_li=['https://www.hubbub.shop/inventory/i/id='+str(i[0]) for i in rows]

    ### accurate for dropoffs only, if no extension is made before dropoff:
    charge_li=[i[2] for i in rows]  # extension charges not included
    deposit_li=[i[3] for i in rows] # extension deposits not included
    tax_li=[i[4] for i in rows] # extension taxes not included
    total = sum(charge_li)+sum(deposit_li)+sum(tax_li)
    print('iid_li',iid_li)
    print('iname_li',iname_li)
    print('ilink_li',ilink_li)
    print('charge_li',charge_li)
    print('deposit_li',deposit_li)
    print('tax_li',tax_li)
    print('total',total)
    print('tid:',tid)
    print('address:',address)
    print('phone:',phone)
    print('payment:',payment)
    if ltype=='dropoff':
        start_time_dt=datetime.datetime.strptime(date+' '+time,'%Y-%m-%d %H:%M:%S')
        start_time_str=date+'T'+time
    elif ltype=='pickup':
        start_time_dt=datetime.datetime.strptime(p_date+' '+time,'%Y-%m-%d %H:%M:%S')
        start_time_str=p_date+'T'+time
    print('start_time_dt',start_time_dt)
    print('start_time_str',start_time_str)
    end_time_dt=start_time_dt + datetime.timedelta(hours=1)
    end_time_str=end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str=end_time_str.replace(' ','T')
    end_time_dt_user=start_time_dt + datetime.timedelta(minutes=15)
    end_time_str_user=end_time_dt_user.strftime('%Y-%m-%d %H:%M:%S')
    end_time_str_user=end_time_str_user.replace(' ','T')
    print('end_time_dt',end_time_dt)
    print('end_time_str',end_time_str)
    print('email',email)
    print('notes',notes)

    items_html_ops="<ul>"
    for i in range(len(iname_li)):
        items_html_ops+= ("<li>"+"<a href=%s>(%s) %s</a>"%(ilink_li[i],iid_li[i],iname_li[i])+"</li>")
    items_html_ops+="</ul>"

    items_html_user="<ul>"
    for i in range(len(iname_li)):
        items_html_user+= ("<li>"+"<a href=%s>%s</a>"%(ilink_li[i],iname_li[i])+"</li>")
    items_html_user+="</ul>"

    if ltype=='dropoff':

        df_event_ops = {
            'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
            'description': """%s \n\nItems:%sTotal $%s from %s\n\nUser notes: %s\n\nUser phone: %s
             """%(tlink,items_html_ops,total,payment,notes,phone),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
            }
        print('df_event_ops',df_event_ops)


        summary = renter.split(" ")[0].capitalize()
        if len(rows)>1:
            summary+=" Items"
        else:
            summary+=" Item"
        summary+=" Drop-off"

        df_event_user = {
            'summary': summary,
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str_user,'timeZone':'America/New_York',}, # end_time_str
            'description': """Our Hub-Bud ___ will be dropping off the following:\n%sTotal due at drop-off: $%s \n\nPlease be prompt. Failure to show up after 30 minutes will result in a $5 drop-off attempt charge and a forfeit of guarantee of rental of the item(s).
             """%(items_html_user,total),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }

        ops_event = service.events().insert(calendarId='c_puitor2pblvjgid67mj32m6em0@group.calendar.google.com', body=df_event_ops).execute()
        user_event = service.events().insert(calendarId='c_puitor2pblvjgid67mj32m6em0@group.calendar.google.com', body=df_event_user).execute()

    elif ltype=='pickup':

        pu_event_ops = {
            'summary': renter.split(" ")[0].capitalize()+" "+renter.split(" ")[1].capitalize()+ ' '+ltype.capitalize(),
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str,'timeZone':'America/New_York',}, # end_time_str
            'description': """%s \n\nItems:%sUser notes: %s\n\nUser phone: %s
             """%(tlink,items_html_ops,notes,phone),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }
        print('pu_event_ops',pu_event_ops)


        summary = renter.split(" ")[0].capitalize()
        if len(rows)>1:
            summary+=" Items"
        else:
            summary+=" Item"
        summary+=" Pick-up"

        pu_event_user = {
            'summary': summary,
            'location': address,
            'start': {'dateTime':start_time_str, 'timeZone':'America/New_York',}, #start_time_str ## have to have T before time
            'end':{'dateTime': end_time_str_user,'timeZone':'America/New_York',}, # end_time_str
            'description': """Our Hub-Bud ___ will be picking up the following:\n%sPlease be prompt. Failure to show up after 30 minutes will result in a $5 pickup attempt charge. Please make sure each item is in a clean and usable state upon pickup, charges may be applied otherwise.\n(For mini-fridges, it is recommended to unplug and defrost them at least 24 hours before pick-up)
             """%(items_html_user),
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'popup', 'minutes': 30},
                ],
              },
        }

        ops_event = service.events().insert(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', body=pu_event_ops).execute()
        user_event = service.events().insert(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', body=pu_event_user).execute()

    # print('Event created: %s' % (event.get('htmlLink')))

    return """ops event created at <a href=%s>%s </a>, user event created at <a href=%s>%s </a>, double check for correctness and add attendees"""%(ops_event.get('htmlLink'),ops_event.get('htmlLink'),user_event.get('htmlLink'),user_event.get('htmlLink'))


@app.route('/clear')
def clear_credentials():
    print('clear:')
    print('flask.session',flask.session)
    if 'credentials' in flask.session:
        del flask.session['credentials']
        del flask.session['state']
        print('flask.session',flask.session)
    return ('Credentials have been cleared.<br><br>') # +
        # print_index_table())

@app.route('/calendar')
def calendar():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])
    print('credentials loaded from session')

    try:
        service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)
        print('service built')
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId='c_oclhvroroorb3fva3a85tqd2rc@group.calendar.google.com', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        print('events_result',events_result)
        # return flask.redirect('mainsiteops')
        # events = events_result.get('items', [])
    except:
        print("exception when accessing events in mainsiteops")
        return """
        please login with valid email<br>
        <a href="clear">clear credentials and try again</a>
        """

    month_dict = {'01':['Jan',31],'02':['Feb',28],'03':['Mar',31],'04':['Apr',30],'05':['May',31],'06':['Jun',30],
                  '07':['Jul',31],'08':['Aug',31],'09':['Sep',30],'10':['Oct',31],'11':['Nov',30],'12':['Dec',31]}

    zipcode_dict=defaultdict(lambda:"other")
    zipcode_dict['10027']='CU'
    zipcode_dict['10025']='CU'
    zipcode_dict['10012']='NYU'
    zipcode_dict['10003']='NYU'
    zipcode_dict['10014']='NYU'
    zipcode_dict['10011']='NYU'
    # zipcode_dict = {'10027':'CU','10025':'CU'}

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        select orders.id, cast(orders.res_date_start as varchar),
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'dropoff'
        from orders
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_dropoffs on orders.id=order_dropoffs.order_id
        left join logistics on logistics.dt_sched=order_dropoffs.dt_sched
        where res_date_start>'2022-08-01'
        order by res_date_start,email
    """)
    dropoff_rows=cur.fetchall()
    dropoff_rows = [list(i) for i in dropoff_rows]
    print("dropoff_rows")
    print(dropoff_rows)
    print("\n\n\n")


    cur.execute("""
        select orders.id, cast(orders.res_date_end as varchar),
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'pickup'
        from orders
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_pickups on orders.id=order_pickups.order_id
        left join logistics on logistics.dt_sched=order_pickups.dt_sched
        where res_date_end>'2022-08-01'
        order by res_date_end,email
    """)
    pickup_rows=cur.fetchall()
    pickup_rows = [list(i) for i in pickup_rows]
    print("pickup_rows")
    print(pickup_rows)
    print("\n\n\n")
    # check for extensions

    cur.execute("select extensions.order_id, cast(extensions.res_date_start as varchar), cast(extensions.res_date_end as varchar) from extensions")
    extensions=cur.fetchall()
    # ext_li=[] # holds the date that go in pickup datetime
    for i in pickup_rows:
        # if order number is in extensions, add extension values, else, add none
        e = [e[2] for e in extensions if e[0]==i[0]]
        if len(e)>0:
            # if multiple extensions on same item/order, multiple rows in extensions with same order id but res dates are changed
            # sort e by res_date_end, take the latest res_date_end
            e.sort()
            # ext_li.append(e[-1])
            i[1]=e[-1]
        # else:
        #     ext_li.append(i[3])
    print("pickup rows after extension check:")
    print(pickup_rows)

    ### rentals that end before 8/1 but have extensions that end after 8/1 ###
    # new query, change where to res_date_end<'2022-08-01' and extensions.res_date_end>'2022-08-01'
    cur.execute("""
        select orders.id, subquery.res_date_end,
        '(' || items.id || ') ' || items.name, users.email,
        users.address_zip, logistics.address_zip, coalesce(cast(logistics.timeslots as varchar),''), coalesce(cast(logistics.chosen_time as varchar),''),
        'pickup'
        from
        orders inner join
            (select extensions.order_id, cast(max(extensions.res_date_end) as varchar) as res_date_end
            from orders
            inner join extensions on orders.id=extensions.order_id
            where orders.res_date_end<'2022-08-01' and cast(extensions.res_date_end as varchar) > '2022-08-01'
            group by extensions.order_id) as subquery
        on orders.id=subquery.order_id
        inner join items on items.id=orders.item_id
        inner join users on users.id=orders.renter_id
        left join order_pickups on orders.id=order_pickups.order_id
        left join logistics on logistics.dt_sched=order_pickups.dt_sched
        order by res_date_end,email
    """)
    pickup_rows_ext=cur.fetchall()
    pickup_rows_ext = [list(i) for i in pickup_rows_ext]
    print("pickup_rows_ext")
    print(pickup_rows_ext)
    print("\n\n\n")

    pickup_rows.extend(pickup_rows_ext)

    print("pickup rows after extension check and adding pickup_rows_ext:")
    print(pickup_rows)
    print("\n\n\n")

    # make table starting august
    # for each month, first row is month name, next row is days (sun-sat), then it's dates and logistics data alternating
    # while there are logistics events: while current date < last logistics event on file
    html="""
        <style type="text/css">
          body {
            font-family: calibri;}
        </style>
        <a href="mainsiteops">Main site Ops view</a>
        <ul>
        <li>each entry starts with the task type (pickup or dropoff), location (CU or NYU), and time (precise time if Ops has scheduled a time, timeslots if user has submitted availability but Ops has not scheduled a time, empty if user has not submitted availability)</li>
        <li>location is CU if the zipcode on dropoff/pickup form (or the zipcode on file, if user has not filled out the form) is 10025 or 10027. location is NYU if the zipcode is one of the following: 10003, 10011, 10012, 10014. location is other if the zipcode is different from any of the above</li>
        </ul>
        <table>
          <tr>
            <th>Aug 2022</th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
            <th> </th>
          </tr>
         """
    all_events=dropoff_rows
    all_events.extend(pickup_rows)
    all_events=sorted(all_events, key=lambda x: (x[1],x[3],x[7],x[6])) # sort by date, email, time chosen, timeslots, empty times are first, then ascending
    print("\n\n\n")
    print("all_events")
    print(all_events)

    # make pandas df, order by date, combine orders for the same user of same type on same day (at same time?)
    # or do that without pandas? in a for loop, then sort list https://stackoverflow.com/questions/36955553/sorting-list-of-lists-by-the-first-element-of-each-sub-list
    prev_email=all_events[0][3]
    prev_type=all_events[0][-1]
    prev_day=all_events[0][1]
    i=1
    length=len(all_events)
    while i<length:
        # print('i',i)
        # print('prev email',prev_email)
        # print('prev type',prev_type)
        # print('prev_day',prev_day)
        # print('current email',all_events[i][3])
        # print('current type',all_events[i][-1])
        # print('current item',all_events[i][2])
        # length=len(all_events) #??
        if all_events[i][3]==prev_email and all_events[i][-1]==prev_type and all_events[i][1]==prev_day:
            # print('email, task type, and date = last one')
            prev_email=all_events[i][3]
            prev_type=all_events[i][-1]
            prev_day=all_events[i][1]
            all_events[i-1][2]+=', '+all_events[i][2] # append current item
            del all_events[i]
        elif all_events[i][3]!=prev_email or all_events[i][-1]!=prev_type or all_events[i][1]!=prev_day:
            # print('email, task type, or date != last one')
            prev_email=all_events[i][3]
            prev_type=all_events[i][-1]
            prev_day=all_events[i][1]
            i+=1
        length=len(all_events) #??
        # print('new length',length)
        # prev_email=all_events[i][3]
        # prev_type=all_events[i][-1]
        # i+=1
    print("\n\n\n")
    print("all_events_after mod:")
    print(all_events)

    # iterate through all upcoming dates, for each date output the events with that date
    upcoming_dates=sorted(list(set([i[1] for i in all_events])))
    # print('upcoming_dates',upcoming_dates)
    curr_year = '2022'
    curr_month = '08'
    curr_mo_index = 7
    months = ['01','02','03','04','05','06','07','08','09','10','11','12']
    years = ['2022','2023','2024','2025']
    # while i<=31:
    ## generate rows of dates of size 7, iterate through each row, add event data as needed
    date_rows=[[' ','1','2','3','4','5','6']]
    i=7
    while i<=31:
        date_rows.append([*range(i,min(31+1,i+7))])
        i+=7
    # for last entry in date_rows, count how many there are, append empties as needed
    if len(date_rows[-1])<7:
        date_rows[-1].extend([' ']*(7-len(date_rows[-1])))
    print(date_rows)

    # make dictionary of date:events ?
    # iterate through date_rows, add corresponding events to each day?
    # date_events_dict shows a list of lists for each date
    date_events_dict=defaultdict(lambda:[])
    for e in all_events:
        event_date=e[1]
        try:# if date exists
            date_events_dict[event_date].append(e)
        except:
            date_events_dict[event_date]=e
    print("\n\n\n")
    print('date_events_dict')
    print(date_events_dict)

    html+="""
        <tr>
          <th>Sun</th>
          <th>Mon</th>
          <th>Tue</th>
          <th>Wed</th>
          <th>Thu</th>
          <th>Fri</th>
          <th>Sat</th>
        </tr>

    """
    # <table>
    ######## new  ########
    print("\n\n\n")
    # remove each event entry after its added to html
    # while date_events_dict: # while there are entries in date_events_dict
    # while curr_mo_index < len(months) :
    while date_events_dict:
        event_rows=[]
        curr_month = months[curr_mo_index]
        print('curr_month',curr_month)
        curr_mo_date_events_dict=dict(filter(lambda i:i[0][5:7]==curr_month and i[0][:4]==curr_year,date_events_dict.items()))

        #### generate date_rows ####
        if curr_month=='08' and curr_year=='2022': # use the pregenerated one
            date_rows=date_rows
        else:
            html+="""
            <tr>
            <td> </td>
            </tr>
            <tr>
              <th>%s</th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
              <th> </th>
            </tr>
            """%(month_dict[curr_month][0]+" "+curr_year)
            html+="""
                <tr>
                  <th>Sun</th>
                  <th>Mon</th>
                  <th>Tue</th>
                  <th>Wed</th>
                  <th>Thu</th>
                  <th>Fri</th>
                  <th>Sat</th>
                </tr>
            """
            # see previous date_rows to see where 01 should start
            max_day=month_dict[curr_month][1]
            print('max day',max_day)
            start_position=len([i for i in date_rows[-1] if i!=' '])
            # generate first line
            if start_position==7:
                start_position=0
                date_rows=[[]]
            else:
                date_rows=[[' ']*start_position]
            date_rows[0].extend([*range(1,7-start_position+1)])
            print('first row of date_rows',date_rows)
            # generate the rest
            i=int(date_rows[0][-1])+1 # value to start with for next row
            print('i,value to start with for next row',i)
            while i<=max_day:
                date_rows.append([*range(i,min(max_day+1,i+7))])
                i+=7
            # for last entry in date_rows, count how many there are, append empties as needed
            if len(date_rows[-1])<7:
                date_rows[-1].extend([' ']*(7-len(date_rows[-1])))
            print(date_rows)

        for d in date_rows:
            html+="<tr>"
            for i in d:
                html+="<th>"+str(i)+"</th>"
            html+="</tr>"
            curr_event_row=[]
            html+="<tr>"
            for date in d:
                curr_date=curr_year+'-'+curr_month+'-'+str(date) if len(str(date))==2 else curr_year+'-'+curr_month+'-0'+str(date)
                # print('curr_date',curr_date)
                try:
                    event_data="<td>"
                    curr_date_events_sorted=sorted(curr_mo_date_events_dict[curr_date], key=lambda x: (x[7],x[6])) # sort events in a day by chosen time, then timeslots
                    for i in curr_date_events_sorted: # for each event in curr_date
                        # print('i',i)
                        event_data_time = i[7] # if chosen time exists, use that, else use timeslots
                        if event_data_time=="":
                            event_data_time=i[6]
                        event_data_zipcode=i[5]
                        if not event_data_zipcode: # if zipcode in logistics form exists, use that, else use zipcode in account
                            event_data_zipcode=i[4]
                        event_data_location = zipcode_dict[event_data_zipcode]
                        event_data+=i[-1]+", "+event_data_location+", "+event_data_time+": "+i[2]+"<br>"

                    event_data+="</td>"
                    # print('event_data in try:',event_data)

                    html+=event_data
                    print('date_events_dict date entry to delete:',date_events_dict[curr_date])
                    del date_events_dict[curr_date]
                    print('date_events_dict after deletion:')
                    print(date_events_dict)
                    # html+="<td>"+str(curr_mo_date_events_dict[curr_date])+"</td>"
                    # curr_event_row.append(curr_mo_date_events_dict[curr_date])
                except Exception as e:
                    # print(e)
                    # print('except')
                    html+="<td></td>"
                    # curr_event_row.append([])
                # print('curr_event_row',curr_event_row)
                # del date_events_dict[date]
            html+="</tr>"
            event_rows.append(curr_event_row)
            print('event_rows',event_rows)
            print("\n")


        if curr_mo_index==len(months)-1: # at last month, or months[11]='12'
            curr_mo_index=0 # reset to months[0]
            curr_year = str(int(curr_year)+1)
        else:
            curr_mo_index+=1

    ######## end of new ########

    #### old ####
    # # go through date_rows, add corresponding events
    # event_rows=[]
    # # for d in date_rows:
    # #     curr_event_row=[]
    # curr_mo_date_events_dict=dict(filter(lambda i:i[0][5:7]==curr_month and i[0][:4]==curr_year,date_events_dict.items()))
    # print("\n\n\n")
    # print("curr_mo_date_events_dict")
    # print(curr_mo_date_events_dict)
    #     # if d[]
    # for d in date_rows: # day without leading 0
    #     # print('d',d)
    #     html+="<tr>"
    #     for i in d:
    #         html+="<th>"+str(i)+"</th>"
    #     html+="</tr>"
    #     curr_event_row=[]
    #     html+="<tr>"
    #     for date in d:
    #         curr_date=curr_year+'-'+curr_month+'-'+str(date) if len(str(date))==2 else curr_year+'-'+curr_month+'-0'+str(date)
    #         # print('curr_date',curr_date)
    #         try:
    #             event_data="<td>"
    #             curr_date_events_sorted=sorted(curr_mo_date_events_dict[curr_date], key=lambda x: (x[7],x[6])) # sort events in a day by chosen time, then timeslots
    #             for i in curr_date_events_sorted: # for each event in curr_date
    #                 # print('i',i)
    #                 event_data_time = i[7] # if chosen time exists, use that, else use timeslots
    #                 if event_data_time=="":
    #                     event_data_time=i[6]
    #                 event_data_zipcode=i[5]
    #                 if not event_data_zipcode: # if zipcode in logistics form exists, use that, else use zipcode in account
    #                     event_data_zipcode=i[4]
    #                 event_data_location = zipcode_dict[event_data_zipcode]
    #                 event_data+=i[-1]+", "+event_data_location+", "+event_data_time+": "+i[2]+"<br>"
    #             event_data+="</td>"
    #             # print('event_data in try:',event_data)
    #
    #             html+=event_data
    #             # html+="<td>"+str(curr_mo_date_events_dict[curr_date])+"</td>"
    #             # curr_event_row.append(curr_mo_date_events_dict[curr_date])
    #         except Exception as e:
    #             # print(e)
    #             # print('except')
    #             html+="<td></td>"
    #             # curr_event_row.append([])
    #         # print('curr_event_row',curr_event_row)
    #     html+="</tr>"
    #     event_rows.append(curr_event_row)
    #     print('event_rows',event_rows)
    #     print("\n")

    #### old ####

    html+="</table>"
    # print()

    # if date is in current month, proceed to add date numbers and corresponding events on each date
    # if date is in next month, add month header, then sat-sun row, then add date numbers and corresponding events

    return html
    # return(render_template('calendar.html'))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, ssl_context='adhoc')
