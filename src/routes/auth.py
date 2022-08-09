from flask import Blueprint, url_for, redirect, session, request

from google_auth_oauthlib.flow import Flow


bp = Blueprint("auth", __name__)

@bp.route('/authorize')
def authorize():
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = Flow.from_client_secrets_file(
      'google-credentials.json', scopes=SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # flow.redirect_uri = 'https://localhost:8080/oauth2callback'

    authorization_url, state = flow.authorization_url(
      # Enable offline access so that you can refresh an access token without

      # re-prompting the user for permission. Recommended for web server apps.
      access_type='offline',

      # Enable incremental authorization. Recommended as a best practice.
      include_granted_scopes='true'
    )

    # Store the state so the callback can verify the auth server response.
    session['state'] = state
    print('in authorize: session',session)

    return redirect(authorization_url)


@bp.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    print('in oauth2callback: session',session)

    state = session['state']
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    flow = Flow.from_client_secrets_file(
      'google-credentials.json',
      scopes=SCOPES,
      state=state
    )

    flow.redirect_uri = url_for('oauth2callback', _external=True)
    # flow.redirect_uri = 'https://localhost:8080/oauth2callback'


    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'  # https://stackoverflow.com/a/59052439/19228216
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.

    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials

    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'id_token': credentials.id_token
    }

    # return redirect(url_for('test_api_request')) # test_api_request
    return redirect( url_for('mainsiteops') )


@bp.route('/clear')
def clear_credentials():
    print('clear:')
    print('session',session)
    if 'credentials' in session:
        del session['credentials']
        del session['state']
        print('session',session)
    return ('Credentials have been cleared.<br><br> <a href="authorize">login</a>') # +
        # print_index_table())
