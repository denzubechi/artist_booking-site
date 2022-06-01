#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
from distutils.log import error
import json
import sys
import dateutil.parser
import babel
from flask import (
    Flask, 
    render_template, 
    request, 
    Response, 
    flash, 
    redirect,
    abort, 
    url_for,
    jsonify
)
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
from sqlalchemy import true
from forms import *
from flask_wtf import Form
from flask_migrate import Migrate
from models import db, Venue, Artist, Show, Genre
from datetime import datetime
import re
from operator import itemgetter # for sorting lists of tuples

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db = SQLAlchemy(app)

# connect to a local postgresql database
migrate = Migrate(app, db)

#----------------------------------------------------------------------------#
# Models
#----------------------------------------------------------------------------#

from models import *
#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#

def format_datetime(value, format='medium'):
  date = dateutil.parser.parse(value)
  if format == 'full':
      format="EEEE MMMM, d, y 'at' h:mma"
  elif format == 'medium':
      format="EE MM, dd, y h:mma"
  return babel.dates.format_datetime(date, format, locale='en')

app.jinja_env.filters['datetime'] = format_datetime

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
  return render_template('pages/home.html')


#  Venues
#  ----------------------------------------------------------------

@app.route('/venues')
def venues():
    data = []
    results = Venue.query.distinct(Venue.city, Venue.state).all()
    for result in results:
        city_state_unit = {
            "city": result.city,
            "state": result.state
        }
        venues = Venue.query.filter_by(city=result.city, state=result.state).all()

        # format each venue
        formatted_venues = []
        for venue in venues:
            formatted_venues.append({
                "id": venue.id,
                "name": venue.name,
                "num_upcoming_shows": len(list(filter(lambda x: x.start_time > datetime.now(), venue.shows)))
            })
        
        city_state_unit["venues"] = formatted_venues
        data.append(city_state_unit)
   
    return render_template('pages/venues.html', areas=data)


@app.route('/venues/search', methods=['POST'])
def search_venues():
    search_term = request.form.get('search_term', '')

    # Use filter, not filter_by when doing LIKE search (i=insensitive to case)
    #implement search on artists with partial string search. Ensure it is case-insensitive.
    venues = Venue.query.filter(Venue.name.ilike('%' + search_term + '%')).all()
    #Showcases Each Venues
    venues_list = []
    current_time = datetime.now()
    for venue in venues:
        venue_shows = Show.query.filter_by(venue_id=venue.id).all()
        num_upcoming = 0
        for show in venue_shows:
            if show.start_time > current_time:
                num_upcoming += 1

        venues_list.append({
            "id": venue.id,
            "name": venue.name,
            "num_upcoming_shows": num_upcoming 
        })

    response = {
        "count": len(venues),
        "data": venues_list
    }
    return render_template('pages/search_venues.html', results=response, search_term=search_term)


    
@app.route('/venues/<int:venue_id>')
def show_venue(venue_id):
  venue = Venue.query.get_or_404(venue_id)
  past_shows = []
  upcoming_shows = []
  for show in venue.shows:
    temp_show = {
        'artist_id': show.artist_id,
        'artist_name': show.artist.name,
        'artist_image_link': show.artist.image_link,
        'start_time': show.start_time.strftime("%m/%d/%Y, %H:%M")
    }
    if show.start_time <= datetime.now():
        past_shows.append(temp_show)
    else:
        upcoming_shows.append(temp_show)

  data = {
    "id" : venue.id,
    "name": venue.name,
    "genres": venue.genres,
    "city": venue.city,
    "state": venue.state,
    "address": venue.address,
    "phone": venue.phone,
    "website": venue.website,
    "facebook_link": venue.facebook_link,
    "seeking_talent": venue.seeking_talent,
    "seeking_description": venue.seeking_description,
    "image_link": venue.image_link,
    "upcoming_shows": upcoming_shows,
    "past_shows": past_shows,
    "upcoming_shows_count": len(upcoming_shows),
    "past_shows_count": len(past_shows)
  }
  return render_template('pages/show_venue.html', venue=data)

#  Create Venue
#  ----------------------------------------------------------------

@app.route('/venues/create', methods=['GET'])
def create_venue_form():
  form = VenueForm()
  return render_template('forms/new_venue.html', form=form)


@app.route('/venues/create', methods=['POST'])
def create_venue_submission():
    form = VenueForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    #Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) 
    genres = form.genres.data
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('create_venue_submission'))

    else:
        error_in_insert = False

        try:
            # creates the new venue with all fields but not genre yet
            new_venue = Venue(name=name, city=city, state=state, address=address, phone=phone, \
                seeking_talent=seeking_talent, seeking_description=seeking_description, image_link=image_link, \
                website=website, facebook_link=facebook_link)
            # adding genres and taking a list of string
            for genre in genres:
                # fetch_genre = session.query(Genre).filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    new_venue.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    new_venue.genres.append(new_genre)  # Create a new Genre item and append it
            db.session.add(new_venue)
            db.session.commit()
        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_venue_submission()')
            db.session.rollback()
        finally:
            db.session.close()
        if not error_in_insert:
            flash('Venue ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Venue ' + name + ' could not be listed.')
            print("Error in create_venue_submission()")
            abort(500)



#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
  artists = db.session.query(Artist.id, Artist.name).all()
  return render_template('pages/artists.html', artists=artists)

@app.route('/artists/search', methods=['POST'])
def search_artists():
    search_term = request.form.get('search_term', '')
    artists = Artist.query.filter(
        Artist.name.ilike(f"%{search_term}%") |
        Artist.city.ilike(f"%{search_term}%") |
        Artist.state.ilike(f"%{search_term}%")
    ).all()
    response = {
        "count": len(artists),
        "data": []
    }

    for artist in artists:
        temp = {}
        temp["name"] = artist.name
        temp["id"] = artist.id

        upcoming_shows = 0
        for show in artist.shows:
            if show.start_time > datetime.now():
                upcoming_shows = upcoming_shows + 1
        temp["upcoming_shows"] = upcoming_shows

        response["data"].append(temp)

    return render_template('pages/search_artists.html', results=response, search_term=search_term)

@app.route('/artists/<int:artist_id>')
def show_artist(artist_id):
  artist = Artist.query.get_or_404(artist_id)
  past_shows = []
  upcoming_shows = []
  for show in artist.shows:
    temp_show = {
        'venue_id': show.venue_id,
        'venue_name': show.venue.name,
        'venue_image_link': show.venue.image_link,
        'start_time': show.start_time.strftime("%m/%d/%Y, %H:%M")
    }
    if show.start_time <= datetime.now():
        past_shows.append(temp_show)
    else:
        upcoming_shows.append(temp_show)

  data = {
    "id" : artist.id,
    "name": artist.name,
    "genres": artist.genres,
    "city": artist.city,
    "phone": artist.phone,
    "website": artist.website,
    "facebook_link": artist.facebook_link,
    "seeking_venue": artist.seeking_venue,
    "seeking_description": artist.seeking_description,
    "image_link": artist.image_link,
    "upcoming_shows": upcoming_shows,
    "past_shows": past_shows,
    "upcoming_shows_count": len(upcoming_shows),
    "past_shows_count": len(past_shows)

  }
  return render_template('pages/show_artist.html', artist=data)

#  Update
#  ----------------------------------------------------------------
@app.route('/artists/<int:artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
    # Taken mostly from edit_venue()

    # Get the existing artist from the database
    artist = Artist.query.get(artist_id)  # Returns object based on primary key, or None.  Guessing get is faster than filter_by
    if not artist:
        # User typed in a URL that doesn't exist, redirect home
        return redirect(url_for('index'))
    else:
        # Otherwise, valid artist.  We can prepopulate the form with existing data like this.
        # Prepopulate the form with the current values.  This is only used by template rendering!
        form = ArtistForm(obj=artist)

    # genres needs to be a list of genre strings for the template
    genres = [ genre.name for genre in artist.genres ]
    
    artist = {
        "id": artist_id,
        "name": artist.name,
        "genres": genres,
        # "address": artist.address,
        "city": artist.city,
        "state": artist.state,
        # Put the dashes back into phone number
        "phone": (artist.phone[:3] + '-' + artist.phone[3:6] + '-' + artist.phone[6:]),
        "website": artist.website,
        "facebook_link": artist.facebook_link,
        "seeking_venue": artist.seeking_venue,
        "seeking_description": artist.seeking_description,
        "image_link": artist.image_link
    }
    return render_template('forms/edit_artist.html', form=form, artist=artist)


@app.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
    # Much of this code from edit_venue_submission()
    form = ArtistForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    # address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('edit_artist_submission', artist_id=artist_id))

    else:
        error_in_update = False

        # Insert form data into DB
        try:
            # First get the existing artist object
            artist = Artist.query.get(artist_id)
            # artist = Artist.query.filter_by(id=artist_id).one_or_none()

            # Update fields
            artist.name = name
            artist.city = city
            artist.state = state
            # artist.address = address
            artist.phone = phone

            artist.seeking_venue = seeking_venue
            artist.seeking_description = seeking_description
            artist.image_link = image_link
            artist.website = website
            artist.facebook_link = facebook_link

            # First we need to clear (delete) all the existing genres off the artist otherwise it just adds them
            
            # For some reason this didn't work! Probably has to do with flushing/lazy, etc.
            # for genre in artist.genres:
            #     artist.genres.remove(genre)
                        
            # artist.genres.clear()  # Either of these work.
            artist.genres = []
            
            # genres can't take a list of strings, it needs to be assigned to db objects
            # genres from the form is like: ['Alternative', 'Classical', 'Country']
            for genre in genres:
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    artist.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    artist.genres.append(new_genre)  # Create a new Genre item and append it

            # Attempt to save everything
            db.session.commit()
        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_artist_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_update:
            # on successful db update, flash success
            flash('Artist ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_artist', artist_id=artist_id))
        else:
            flash('An error occurred. Artist ' + name + ' could not be updated.')
            print("Error in edit_artist_submission()")
            abort(500)


@app.route('/venues/<int:venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
    # Get the existing venue from the database
    # venue = Venue.query.filter_by(id=venue_id).one_or_none()    # Returns one, None, or exception if more than one
    venue = Venue.query.get(venue_id)  # Returns object based on primary key, or None.  Guessing get is faster than filter_by
    if not venue:
        # User typed in a URL that doesn't exist, redirect home
        return redirect(url_for('index'))
    else:
        # Otherwise, valid venue.  We can prepopulate the form with existing data like this:
        form = VenueForm(obj=venue)

    # Prepopulate the form with the current values.  This is only used by template rendering!
    # genres needs to be a list of genre strings for the template
    genres = [ genre.name for genre in venue.genres ]
    
    venue = {
        "id": venue_id,
        "name": venue.name,
        "genres": genres,
        "address": venue.address,
        "city": venue.city,
        "state": venue.state,
        # Put the dashes back into phone number
        "phone": (venue.phone[:3] + '-' + venue.phone[3:6] + '-' + venue.phone[6:]),
        "website": venue.website,
        "facebook_link": venue.facebook_link,
        "seeking_talent": venue.seeking_talent,
        "seeking_description": venue.seeking_description,
        "image_link": venue.image_link
    }

    
    return render_template('forms/edit_venue.html', form=form, venue=venue)


@app.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
    # Much of this code same as /venue/create view.
    form = VenueForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('edit_venue_submission', venue_id=venue_id))

    else:
        error_in_update = False

        try:
            # First get the existing venue object
            venue = Venue.query.get(venue_id)

            # Update fields
            venue.name = name
            venue.city = city
            venue.state = state
            venue.address = address
            venue.phone = phone

            venue.seeking_talent = seeking_talent
            venue.seeking_description = seeking_description
            venue.image_link = image_link
            venue.website = website
            venue.facebook_link = facebook_link

            # First we need to clear (delete) all the existing genres off the venue otherwise it just adds them
            
            # For some reason this didn't work! Probably has to do with flushing/lazy, etc.
            # for genre in venue.genres:
            #     venue.genres.remove(genre)
                        
            # venue.genres.clear()  # Either of these work.
            venue.genres = []
            
            # genres can't take a list of strings, it needs to be assigned to db objects
            # genres from the form is like: ['Alternative', 'Classical', 'Country']
            for genre in genres:
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    venue.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    venue.genres.append(new_genre)  # Create a new Genre item and append it

            db.session.commit()
        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_venue_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_update:
            flash('Venue ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_venue', venue_id=venue_id))
        else:
            flash('An error occurred. Venue ' + name + ' could not be updated.')
            print("Error in edit_venue_submission()")
            abort(500)
#  Delete
#  ----------------------------------------------------------------
@app.route("/venues/<venue_id>/delete", methods={"GET"})
def delete_venue(venue_id):
    try:
        venue = Venue.query.get(venue_id)
        db.session.delete(venue)
        db.session.commit()
        flash("Venue " + venue.name + " was deleted successfully!")
    except:
        db.session.rollback()
        print(sys.exc_info())
        flash("Venue was not deleted successfully.")
    finally:
        db.session.close()

    return redirect(url_for("index"))
#  Create Artist
#  ----------------------------------------------------------------

@app.route('/artists/create', methods=['GET'])
def create_artist_form():
  form = ArtistForm(request.form)
  return render_template('forms/new_artist.html', form=form)
@app.route('/artists/create', methods=['POST'])
def create_artist_submission():

    # Much of this code is similar to create_venue view
    form = ArtistForm(request.form)

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    # address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('create_artist_submission'))

    else:
        error_in_insert = False

        # Insert form data into DB
        try:
            # creates the new artist with all fields but not genre yet
            new_artist = Artist(name=name, city=city, state=state, phone=phone, \
                seeking_venue=seeking_venue, seeking_description=seeking_description, image_link=image_link, \
                website=website, facebook_link=facebook_link)
            # genres can't take a list of strings, it needs to be assigned to db objects
            # genres from the form is like: ['Alternative', 'Classical', 'Country']
            for genre in genres:
                # fetch_genre = session.query(Genre).filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    new_artist.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    new_artist.genres.append(new_genre)  # Create a new Genre item and append it

            db.session.add(new_artist)
            db.session.commit()
        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_artist_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_insert:
            # on successful db insert, flash success
            flash('Artist ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Artist ' + name + ' could not be listed.')
            print("Error in create_artist_submission()")
            abort(500)

#Delete Artist
@app.route("/artists/<artist_id>/delete", methods=["GET"])
def delete_artist(artist_id):
    try:
        artist = Artist.query.get(artist_id)
        db.session.delete(artist)
        db.session.commit()
        flash("Artist " + artist.name+ " was deleted successfully!")
    except:
        db.session.rollback()
        print(sys.exc_info())
        flash("Artist was not deleted successfully.")
    finally:
        db.session.close()

    return redirect(url_for("index"))


#  Shows
#  ----------------------------------------------------------------

@app.route('/shows')
def shows():
    data = []

    shows = Show.query.all()
    for show in shows:
        temp = {}
        temp["venue_id"] = show.venue.id
        temp["venue_name"] = show.venue.name
        temp["artist_id"] = show.artist.id
        temp["artist_name"] = show.artist.name
        temp["artist_image_link"] = show.artist.image_link
        temp["start_time"] = show.start_time.strftime("%m/%d/%Y, %H:%M:%S")
        
        data.append(temp)
    
    return render_template('pages/shows.html', shows=data)


@app.route('/shows/create')
def create_shows():
  # renders form. do not touch.
  form = ShowForm(request.form)
  return render_template('forms/new_show.html', form=form)

@app.route('/shows/create', methods=['POST'])
def create_show_submission():
    form = ShowForm(request.form)
    
    artist_id = form.artist_id.data.strip()
    venue_id = form.venue_id.data.strip()
    start_time = form.start_time.data

    error_in_insert = False
    try:
      new_show = Show(
                artist_id=artist_id,
                venue_id=venue_id,
                start_time=start_time
      )
      db.session.add(new_show)      
      db.session.commit()
    except Exception:
      error_in_insert =True
      print(sys.exc_info())
      flash('Show was not successfully listed.')
      db.session.rollback()
    finally:
      db.session.close()
    if error_in_insert: 
      flash('Error Occcured, Show was not successfully listed.')
    else:
      flash('Show was successfully listed')

    return render_template('pages/home.html')

  

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000)

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
