from dotenv import load_dotenv
from flask import Flask, redirect, request, jsonify, render_template, session, make_response
from requests import post, get
import base64
import requests
import random
import string
import urllib.parse as urlparse
import os
import json
import time

load_dotenv()

app = Flask(__name__)

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv('REDIRECT_URI')
app.secret_key = os.getenv('SECRET_KEY')
app.config['SESSION_COOKIE_NAME'] = "users Cookie"



#generates and returns random string that will be used to provide protection against
#cross-site request forgery
def gen_random_string(length):
    random_string = string.ascii_letters + string.digits
    return ''.join(random.choice(random_string) for i in range(length))



#function that allows users to login using spotify credentials
@app.route("/login")
def login():
    #checks to see if access token exists in session, if not proceed with the login flow
    access_token = session.get('access_token')
    if access_token:
        return redirect("http://localhost:8888//artists/short_term")
   
    
    state = gen_random_string(16)
    scope = 'user-top-read user-read-recently-played'

    #the authorization URL
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'scope': scope,
        'redirect_uri': redirect_uri,
        'state': state,
        'show_dialog': True
    }
    auth_url = 'https://accounts.spotify.com/authorize?' + urlparse.urlencode(auth_params)

    #redirect the user to the authorization URL
    return redirect(auth_url)


# Callback URL for receiving the authorization code from Spotify
@app.route("/callback")
def get_token():
    
    code = request.args.get('code') or None
    state = request.args.get('state') or None
    
    #checks to make sure the state matches
    if state is None:
        return redirect('/#' + urlparse.urlencode({'error': 'state_mismatch'}))
    else:

        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": "Basic " + base64.b64encode((client_id + ':' + client_secret).encode('utf-8')).decode('utf-8')
        }
        data = {"code": code, "redirect_uri": redirect_uri, "grant_type": "authorization_code"}
        result = requests.post(url, data=data, headers=headers)
        
        # Check if the response is successful (status code 200)
        if result.status_code == 200:
            #saves all the important data in the session
            data = result.json()
            session['access_token'] = data.get('access_token')
            session['refresh_token'] = data.get('refresh_token')
            session['expires_in'] = data.get('expires_in')

            return redirect("http://localhost:8888/artists/short_term")
        else:
            return redirect('/#' + urlparse.urlencode({'error': 'invalid_token'}))


#function that allows the program to get a refresh token if the access token expires
def refresh_token():
    access_token = session.get('access_token', None)
    if not access_token:
        raise "exception"
    
    now = int(time.time())
    is_expired = session.get('expires_in') - now < 60

    #checks if the token is expried, if not just return the access token. 
    #If it is then it uses the refresh token to get a new access token.
    if is_expired:
        result = requests.post(
            'https://accounts.spotify.com/api/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': session.get('refresh_token'),
            },
            headers={
                'Authorization': 'Basic ' + base64.b64encode((client_id + ':' + client_secret).encode('utf-8')).decode('utf-8'),
            }
        )
        data = result.json()
        access_token = data.get('access_token')

    return access_token

'''
function that takes in data_type (artists and tracks) and time_range (short_term, meduim_term, long_term) 
to access Spotify's Web API and return a render template that neatly displays the data.
'''
def get_data(data_type, time_range):

    # Get the access token from the session, if session is empty, it redirects user to login page
    try:
        access_token = refresh_token()
    except:
        print("user not logged in")
        return redirect('/login')

    if access_token is None:
        return redirect('/#' + urlparse.urlencode({'error': 'access_token_missing'}))

    # Make a GET request to the Spotify API to get the user's top artists/tracks based on the time_range
    if time_range != "medium_term" :
        url = "https://api.spotify.com/v1/me/top/" + data_type + "?time_range=" + time_range
    else:
        url = "https://api.spotify.com/v1/me/top/" + data_type + "/"
    headers = {'Authorization': 'Bearer '  + access_token}
    result = requests.get(url, headers=headers)

    # Check if the response is successful (status code 200)
    if result.status_code == 200:
    
        json_result = json.loads(result.content)['items']
        user_type_data = []
        rank = 1
        
        #Neatly organizes the relevent data in a dictionary based on the data_type (artists)
        if data_type == 'artists': 
            for user_data in json_result:
                artist_data = {
                    'rank' : rank,
                    'name': user_data['name'],
                    'images': user_data['images'][1]['url'],
                    'spotify_url': user_data['external_urls']['spotify'],
                    'genres' : user_data['genres']
                }
                rank += 1
                user_type_data.append(artist_data)

            #Passes in the data_type and time_range to the artists.html file and returns the render template for it
            return render_template("artists.html", user_data = user_type_data, data_type = data_type, time_range = time_range)
        else:
            
            #Neatly organizes the relevent data in a dictionary based on the data_type (tracks)
            for user_data in json_result:
                track_data = {
                    'rank' : rank,
                    'artist_name': user_data['artists'][0]['name'],
                    'album_name' : user_data['album']['name'], 
                    'track_name': user_data['name'],
                    'images': user_data['album']['images'][1]['url'],
                    'spotify_url': user_data['uri'],
                }
                rank += 1
         
                user_type_data.append(track_data)

        #Passes in the data_type and time_range to the tracks.html file and returns the render template for it
        return render_template("tracks.html", user_data = user_type_data, data_type = data_type, time_range = time_range)
    else:
        #returns error if the esponse is unsuccessful
        
        return "Error: Failed to retrieve top artists/tracks from Spotify API"    


@app.route("/history")
def history():
      # Get the access token from the session
    try:
        access_token = refresh_token()
    except:
        print("user not logged in")
        return redirect('/login')

    if access_token is None:
        return redirect('/#' + urlparse.urlencode({'error': 'access_token_missing'}))

    # Make a GET request to the Spotify API to get the user's top artists
    url = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
    headers = {'Authorization': 'Bearer '  + access_token}
    result = requests.get(url, headers=headers)

    # Check if the response is successful (status code 200)
    if result.status_code == 200:
        json_result = json.loads(result.content)['items']
        user_type_data = []
        rank = 1

        # Neatly organizes the relevent data in a dictionary based on the data_type (artists)
        for user_data in json_result:
            history_data = {
                'rank' : rank,
                'artist_name': user_data['track']['artists'][0]['name'],
                'album_name' : user_data['track']['album']['name'], 
                'track_name': user_data['track']['name'],
                'images': user_data['track']['album']['images'][1]['url'],
                'spotify_url': user_data['track']['uri'],
            }
            rank += 1
         
            user_type_data.append(history_data)
        
        #Passes in the data_type to the history.html file and returns the render template for it
        print(user_type_data)
        return render_template("history.html", user_data = user_type_data, data_type = 'history')
    else:
        #returns error if the esponse is unsuccessful
        return "Error: Failed to retrieve track history from Spotify API" 
        

# Function that returns get_data function. Passes in artists and short_term.
@app.route("/artists/short_term")
def get_short_term_top_artist():
    return get_data('artists', 'short_term')

# Function that returns get_data function. Passes in artists and medum_term.
@app.route("/artists/medium_term")
def get_meduim_term_top_artist():
    return get_data('artists', 'medium_term')

# Function that returns get_data function. Passes in artists and long_term.
@app.route("/artists/long_term")
def get_long_term_top_artist():
    return get_data('artists', 'long_term')

# Function that returns get_data function. Passes in tracks and short_term.
@app.route("/tracks/short_term")
def get_short_term_top_tracks():
    return get_data('tracks', 'short_term')

# Function that returns get_data function. Passes in tracks and medum_term.
@app.route("/tracks/medium_term")
def get_meduim_term_top_tracks():
    return get_data('tracks', 'medium_term')

# Function that returns get_data function. Passes in tracks and long_term.
@app.route("/tracks/long_term")
def get_long_term_top_tracks():
    return get_data('tracks', 'long_term')

# Function for the home page that returns the render template for the home.html
@app.route("/")
def home():
    return render_template("home.html")

@app.route('/logout')
def logout():
    # Performs logout tasks, clearing session data
    session.clear()
    # Redirect the user to the home page after logout
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True, port=8888)
    
