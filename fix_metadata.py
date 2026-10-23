""" The main file for fixing metadata given a directory full of audio files. """
# Import first-party packages
import os
import logging
import argparse

# Import third-party packages
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Import from other files
import secrets
import common


def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s: %(message)s')

    # Set up arguments parser
    parser = argparse.ArgumentParser(description="Update genre metadata in MP3 files.")
    parser.add_argument("-p", "--path", type=str, 
    					help="Path to the MP3 file or directory containing MP3 files", 
    					required=True)
    args = parser.parse_args()

    # Set up Spotify API credentials using values from secrets.py
    client_id = secrets.CLIENT_ID
    client_secret = secrets.CLIENT_SECRET
    client_credentials_manager = SpotifyClientCredentials(client_id=client_id, 
    													  client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    # Expand user-provided path
    expanded_path = os.path.expanduser(args.path)
    if os.path.isdir(expanded_path):
        for filename in os.listdir(expanded_path):
            if filename.endswith('.mp3'):
                file_path = os.path.join(expanded_path, filename)
                logging.info('Found: ' + file_path)
                
                common.process_file(sp, file_path)

    elif os.path.isfile(expanded_path) and expanded_path.endswith('.mp3'):
        common.process_file(sp, expanded_path)
    else:
        logging.error(f"The specified path does not exist or is not an MP3 file: {expanded_path}\n")

if __name__ == "__main__":
    main()