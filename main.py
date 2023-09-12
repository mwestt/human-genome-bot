import json
import os
from twitter import HumanGenomeBot


def main(request):
    
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
    bot.commit()

if __name__ == '__main__':
    request = None
    main(request)