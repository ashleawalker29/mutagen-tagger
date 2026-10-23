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

    Returns dictionary with track information.
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


def extract_metadata(file_path):
    try:
        # Load the file using mutagen
        audiofile = mutagen.File(file_path, easy=True)
        #logging.info(f"targeting file: {audiofile}")
        # Check if it's an MP3 file with ID3 tags
        if audiofile is not None: #and isinstance(audiofile, mutagen.id3.ID3FileType):
            # Extract artist, title, comments, and genre
            artist = audiofile.get('artist', [None])[0]
            title = audiofile.get('title', [None])[0]
            comments = audiofile.get('COMM::eng', [None])[0]  # Extracting comments, assuming 'eng' for English
            # genre = audiofile.get('TCON', [None])[0]  # Extracting genre
            album = audiofile.get('TALB', [None])[0]  # Extracting album

            if artist and title:
                return artist, title, comments, album
            else:
                logging.warning("Artist or title tag not found.")
                return None, None, None, None
        else:
            logging.error(f"The file {file_path} is not an MP3 file or does not contain ID3 tags")
            return None, None, None, None

    except Exception as e:
        logging.error(f"An error occurred while extracting metadata: {e}")
        return None, None, None, None


def updateComments(file_path, new_album):
    try:
        # Try to load the ID3 tag, or create one if it doesn't exist
        try:
            audiofile = ID3(file_path)
        except ID3NoHeaderError:
            audiofile = ID3()

        # Check if the comments frame exists and read the current comments
        current_comments = ""
        if audiofile.getall("COMM"):
            for comm in audiofile.getall("COMM"):
                if comm.lang == 'eng':
                    current_comments = comm.text[0]
                    break

        # Update comments to include album only if not already present
        album_comment = f" Album: {new_album}"
        if album_comment not in current_comments:
            new_comments = f"{current_comments}{album_comment}" if current_comments else album_comment
            # Update or add the COMM frame with the new comments
            audiofile.add(COMM(encoding=3, lang='eng', desc='', text=new_comments))

            # Save the changes back to the file
            audiofile.save(file_path)
            logging.info(f"Comments updated for {file_path}")
        else:
            logging.info("Album already mentioned in comments, no update required.\n")
        
    except Exception as e:
        logging.error(f"An error occurred while updating comments: {e}")


def update_metadata_tag(file_path, tag_name, tag_info):
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
    artist, title, comments, album = extract_metadata(file_path)

    if artist and title:
        # Attempt to find a album if not already tagged
        new_album = get_track_metadata(sp, artist, title)['album'] if album is None else None

        # If a new album is found and it's different from 'Unknown'
        if new_album and new_album != 'Unknown':
            # Check if comments exist and prepare them for update
            comments = "" if comments is None else comments
            
            # Format the album comment and check if it's already in the comments
            album_comment = f"Album: {album}"
            if album_comment not in comments:
                update_metadata_tag(file_path, 'album', new_album)
                # Append the new album to the comments if it's not already mentioned
                new_comments = f"{comments} {album_comment}".strip()
                updateComments(file_path, new_comments)

            else:
                logging.info("Album already mentioned in comments, no update required.\n")
        elif album:  # If an existing album is found, check for comment update without altering the album tag
            album_comment = f"Album: {album}"
            if album_comment not in comments:
                new_comments = f"{comments} {album_comment}".strip()
                updateComments(file_path, new_comments)
            else:
                logging.info("Album already mentioned in comments, no update required.\n")
        else:
            logging.warning(f"Album for {artist} - {title} could not be determined or is already set.\n")
    else:
        logging.warning("Either artist or title or both were not found in the file's metadata.\n")