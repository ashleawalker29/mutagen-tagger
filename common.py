import os
import logging
import argparse
import time
import mutagen
from mutagen.id3 import ID3, ID3NoHeaderError, TCON, COMM
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


def get_track_metadata(sp, artist, track):
    """ Search for a track's information based on its artist name and song name. 

    Returns dictionary with metadata information for the given track.
    """
    # Initial metadata information. Everything is unknown at this stage.
    metadata = {'album':'Unknown'}

    try:
        results = sp.search(q='artist:' + artist + ' track:' + track, type='track')
        items = results['tracks']['items']
        if len(items):
            track_id = items[0]['id']
            track_info = sp.track(track_id)

            # Update metadata with album name
            metadata['album'] = track_info['album']['name']
            logging.debug(f'Retrieved album for {artist} - {track}: {metadata['album']}')

    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 429:
            retry_after = int(e.headers.get('Retry-After', 1))
            logging.warning(f'Rate limiting, sleeping for {retry_after} seconds')
            time.sleep(retry_after)
            return get_track_metadata(sp, artist, track)  
        else:
            logging.error(f'Spotify API error: {e}')
    except Exception as e:
        logging.error(f'Error during Spotify API call: {e}')

    return metadata


def get_known_metadata(file_path):
    """ Get the known metadata of a given file. 

    Returns dictionary with metadata information for the given file.
    """
    metadata = {'artist': None,
                'title': None,
                'comments': None,
                'album': None}
    try:
        # Load the file using mutagen
        audiofile = mutagen.File(file_path, easy=True)

        if audiofile:
            # Extract required tags artist and title.
            metadata['artist'] = audiofile.get('artist', [None])[0]
            metadata['title'] = audiofile.get('title', [None])[0]
            
            # Resuired to evaluate. Don't even bother with other tags if these aren't present.
            if not metadata['artist'] or not metadata['title']:
                logging.warning("Artist or title tag not found.")
                return metadata
            
            # Extract optional tag information.
            comments = audiofile.get('COMM::eng', [None])[0]  # Extracting comments, assuming 'eng' for English
            genre = audiofile.get('TCON', [None])[0]
            album = audiofile.get('TALB', [None])[0]

        else:
            logging.error(f"The file {file_path} is not an MP3 file or does not contain ID3 tags")

    except Exception as e:
        logging.error(f"An error occurred while extracting metadata: {e}")

    return metadata


def update_metadata_tag(file_path, tag_name, tag_info):
    """ Updates the given metadata tag of the specified file with the tag info."""
    try:
        audiofile = mutagen.File(file_path, easy=True)

        if audiofile is not None:
            # Update the given metadata tag using dictionary-style assignment
            audiofile[tag_name] = tag_info

            # Save the changes
            audiofile.save()
            logging.info(f"{tag_name.capitalize()} tag updated to '{tag_info}' for {file_path}")
        else:
            logging.info(f"The file {file_path} is not an MP3 file or does not contain ID3 tags")
    except Exception as e:
        logging.error(f"An error occurred while updating the genre: {e}")


def process_file_album(sp, file_path):
    known_file_metadata = get_known_metadata(file_path)

    if known_file_metadata['artist'] and known_file_metadata['title']:
        # Attempt to find a album if not already tagged
        if not known_file_metadata['album']:
            new_album = get_track_metadata(sp, known_file_metadata['artist'], known_file_metadata['title'])['album'] 

            # If a new album is found and it's different from 'Unknown'
            if new_album != 'Unknown' and new_album != known_file_metadata['album']:
                update_metadata_tag(file_path, 'album', new_album)

        else:
            logging.warning(f"Album for {known_file_metadata['artist']} - {known_file_metadata['title']} could not be determined or is already set.\n")
    else:
        logging.warning("Either artist or title or both were not found in the file's metadata.\n")