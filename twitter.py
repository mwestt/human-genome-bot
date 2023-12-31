import os
import json
import tweepy
import collections
import numpy as np
import pandas as pd
from urllib.request import urlopen  
from git.repo import Repo
from google.cloud import storage

class HumanGenomeBot():


    def __init__(self, auth_dict=None, chrome_dict=None, api_version='v2'):
        self.auth_dict = auth_dict
        self.chrome_dict = json.load(open('chrome_dict.json'))
        self.API_KEY = self.auth_dict['api_key']
        self.API_SECRET = self.auth_dict['api_key_secret']
        self.ACCESS_TOKEN = self.auth_dict['access_token']
        self.ACCESS_SECRET = self.auth_dict['access_token_secret']

        self.api_version = api_version
        self.api, self.client = self.authenticate(version=self.api_version)


    def authenticate(self, version='v2'):
        """Authenticate using OAuth 1.0a User Context, for Twitter API v1 or v2."""
        
        # v1 API needed for media upload even if using v2 API (on free tier)
        auth = tweepy.OAuth1UserHandler(
            self.API_KEY, self.API_SECRET, self.ACCESS_TOKEN, self.ACCESS_SECRET
        )
        api = tweepy.API(auth)
        
        client = None
        if version == 'v2':
            client = tweepy.Client(
                consumer_key=self.API_KEY,
                consumer_secret=self.API_SECRET,
                access_token=self.ACCESS_TOKEN,
                access_token_secret=self.ACCESS_SECRET
            )
        
        return api, client


    def commit(self, message='commit from python'):
        """Commit most recent tweet text file to repo."""

        repo = Repo()

        try:
            repo.index.add(['tmp/next_tweet.txt'])
        except ValueError:
            repo.index.add(['/tmp/next_tweet.txt'])

        repo.index.commit(message)

        origin = repo.remotes[0]
        origin.push()


    def gcp_read(self):
        
        client = storage.Client()
        bucket = client.get_bucket('human-genome-bucket')
        blob = bucket.get_blob('next_tweet.txt')
        data = blob.download_as_text()

        return data


    def gcp_write(self, next_tweet):

        client = storage.Client()
        bucket = client.get_bucket('human-genome-bucket')
        blob = bucket.get_blob('next_tweet.txt')
        blob.upload_from_string(next_tweet)


    def tweet(self, tweet_length=280, commit=False, augment_repeats=True):
        """Make the next tweet in the sequence. Identifies the correct region
        of the genome, downloads the relevant chromosome from UCSC, and Tweets
        via Tweepy client."""
        
        # Get most recent tweet - chromosome and index
        # GCloud flow - read from bucket
        file = self.gcp_read()
        print(file)

        file_list = file.split(',')
        chromosome = file_list[0].split('=')[-1]
        index = int(file_list[1].split('=')[-1])
        last_tweet = file_list[2].split('=')[-1]
        end_index = file_list[3].split('=')[-1]

        if chromosome == 'Job done.':
            self.client.create_tweet(text='The end.')
            print(chromosome)
            return chromosome

        try: 
            chromosome = int(chromosome)
        except ValueError:
            pass
        
        # Tweet header tweet if first sequence in a new chromosome
        if index == 0:
            header_tweet = 'Chromosome {}'.format(chromosome)        
            self.client.create_tweet(text=header_tweet)

        # Open relevant chromosome
        # seq = pd.read_csv('genome/chr{}.fa'.format(chromosome))  # Loading local copy
        
        print("Downloading Chromosome {} from UCSC...".format(chromosome))
        URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr{}.fa.gz".format(chromosome)
        url = urlopen(URL)
        
        output = open('/tmp/zipFile.gz', 'wb')        
        output.write(url.read())
        output.close()
        print('Done')

        seq = pd.read_csv('/tmp/zipFile.gz', compression='gzip')  
        os.remove('/tmp/zipFile.gz')

        one_long = ''.join(seq['>chr{}'.format(chromosome)])
        n_tweets = len(one_long) // tweet_length

        # Get tweet based on slice of chromosome string
        tweet = one_long[index*tweet_length:index*tweet_length + tweet_length]
        end_index = index*tweet_length + tweet_length  # Can be used to refactor above slicing for dynamic tweet length

        try:  # Try and tweet
            self.client.create_tweet(text=tweet)
        except tweepy.errors.Forbidden:  # Duplication, may cause Twitter API 403

            if augment_repeats == True:  # Add diacritics at random if sequence repeated
                
                augment_dict = {
                    'A': 'Ą', 'C': 'Ç', 'T':'Ţ', 'G':'Ģ', 'N':'Ņ',
                    'a': 'ą', 'c': 'ç', 't':'ţ', 'g': 'ģ'
                }

                # Get indices of modal character
                modal_char = collections.Counter(tweet).most_common(1)[0][0]
                char_indices = [i for i, letter in enumerate(tweet) if letter == modal_char]

                # Select random subset of indices corresponding to position of modal char
                # n = np.random.randint(1, 6)
                n = 2
                augment_pos = np.random.choice(char_indices, size=n, replace=False)

                # Perform augmentation
                alternative = augment_dict[modal_char]  # Select alternative glyph to replace
                tweet_list = list(tweet)
                tweet_augment = ''.join([alternative if i in augment_pos else tweet_list[i] for i in range(len(tweet_list))])

                # Tweet augmented tweet
                self.client.create_tweet(text=tweet_augment)

        if index == n_tweets:
            index = 0
            chromosome = self.chrome_dict[str(chromosome)]
        else:
            index += 1

        # Save chromosome, index, and last tweet to storage bucket or disk
        next_tweet = 'chromosome={},index={},last_tweet={},end_index={}'.format(chromosome, index, tweet, end_index)
        self.gcp_write(next_tweet)

        if commit:
            self.commit(message='chromosome={},index={}'.format(chromosome, index))

        return tweet


if __name__ == '__main__':

    try:
        # Local version
        auth_dict=json.load(open('auth.json'))
    except:
        # GCP version
        auth_dict = {
            'api_key': os.environ.get("CONSUMER_KEY"),
            'api_key_secret': os.environ.get("CONSUMER_SECRET"),
            'access_token': os.environ.get("ACCESS_TOKEN"),
            'access_token_secret': os.environ.get("ACCESS_TOKEN_SECRET")
        }

    bot = HumanGenomeBot(auth_dict)
    bot.tweet()
