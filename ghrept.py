#!/usr/bin/env python

"""
Author: John D. Anderson
Email: jander43@vols.utk.edu
Description: "grep"-ing for GitHub Repos Posted on Twitter
Usage:
    ghrept
    ghrept filter
    ghrept configure
    ghrept test-twitter-api
    ghrept test-slack-api
"""

# libs
import re
import os
import sys
import fire
import json
import twitter
import termcolor
import slackclient

# globals
BANNER = '''
                _____  _   _ ______    ______ ___________       _
               |  __ \| | | || ___ \   | ___ \_   _| ___ \     | |
               | |  \/| |_| || |_/ /___| |_/ / | | | |_/ / ___ | |_
               | | __ |  _  ||    // _ \  __/  | | | ___ \/ _ \| __|
               | |_\ \| | | || |\ \  __/ |     | | | |_/ / (_) | |_
                \____/\_| |_/\_| \_\___\_|     \_/ \____/ \___/ \__|
'''
FILTER_CONFIG = '.filterconfig.json'
TW_TOKENS = '.twitter_tokens'
SLK_TOKENS = '.slack_tokens'
TSTRM_MSG = '{2}{0}Twitter Stream {1}{0}'.format(29*'-', '{0}', '{1}')


# funcs
def compile_regex(words):
    """Adds word boundaries and returns compiled regex."""
    blocks = [r'\b{0}\b'.format(w) for w in words]
    return re.compile('|'.join(blocks), flags=re.I)


def tweet_highlight(text, word_list):
    """Takes in Tweet text and highlights the filtered word."""
    # lower, sort, and reverse word_list (for regex reasons)
    word_list = [w.lower() for w in word_list]
    word_list.sort(reverse=True)

    # get list of all matches
    match_exp = compile_regex(word_list)
    match_list = match_exp.findall(text)

    # loop over matches
    for match in match_list:
        # highlight words
        text = re.sub(r'\b{0}\b'.format(match),
                      '\x1b[31m{0}\x1b[33m'.format(match), text)

    # get highlighted text
    print '{0}\n'.format(termcolor.colored(text, 'yellow'))


def colortxt(text, cval='yellow'):
    """Simple wrapper func for termcolor.colored() method."""
    print '{0}\n'.format(termcolor.colored(text, cval))


def twitter_filters(func_list):
    """Wrapper func for list of functions to be used on Tweet filtering."""
    def wrapped_func(tweet):
        for func in func_list:
            func(tweet)

    # get new func
    return wrapped_func


def match_wrapper(regex, words, outlet, debug=False):
    """Store args with function and return."""
    def match_word(tweet):
        # check if word in text
        if regex.search(tweet):
            outlet(tweet, words)
        elif debug:
            colortxt(tweet, 'white')
    # return wrapped matcher
    return match_word


# classes
class ConfigTwitterApp(object):
    pass


class ConfigSlackApp(object):
    pass


class ConfigFilter(object):
    """Configure your filter file (e.g. .filterconfig.json)."""
    def __init__(self, filterfile):
        pass


class FilterStream(object):
    """Class to implement filtering of Twitter stream"""
    def __init__(self, config, debug):
        # set debug
        self._debug = debug

        # get twitter client
        self._twitter_feed = None

        # get slack client
        self._slack_feed = None

        # read in config file
        self.filter_config = self._read_config(config)

    def _read_config(self, infile):
        """Method to read in config file."""
        # try reading
        try:
            with open(infile, 'r') as configfile:
                output = json.loads(configfile.read())
        except IOError:
            sys.exit(colortxt('File {0} not found'.format(infile), 'red'))

        # finish
        return output

    def _setup_filters(self):
        """Get list of all the filters and outlets you will be using."""
        # start up Twitter OAuth
        self._twitter_feed = TwitterGHRePT()

        # list of filters
        filter_list = []

        # check loaded file
        if 'twitter' in self.filter_config:
            # # make sure entry for stdout is type dict
            # fwords = filter_config['twitter']
            # if type(fwords) is dict:
            # TODO
            print self.filter_config['twitter']

        if 'stdout' in self.filter_config:
            # make sure entry for stdout is type list
            fwords = self.filter_config['stdout']
            if type(fwords) is list:
                # get regex
                regex = compile_regex(fwords)

                # get match func
                filter_list.append(match_wrapper(regex, fwords,
                                                 tweet_highlight, self._debug))

        if 'slack' in self.filter_config:
            # # get slack auth
            # self._slack_feed = SlackGHRePT()
            # TODO
            print self.filter_config['slack']

        # return list of filter funcs
        return filter_list

    def filter_tweets(self):
        """Startup Twitter stream and filter."""
        # get list of filter functions from filter config file
        filter_funcs = twitter_filters(self._setup_filters())

        # pass filters func to Twitter stream
        self._twitter_feed.tweet_text_stream(filter_funcs)


class SlackGHRePT(object):
    """Class to implement a basic Slack client for use with GHRePTBot."""
    def __init__(self):
        # get token
        slk_token = self._slack_token()

        # get Slack instance
        self._slk_instance = slackclient.SlackClient(slk_token)

    def _slack_token(self):
        """Authorize bot to access Slack team."""
        return os.environ.get('SLACK_API_TOKEN')

    def post_msg(self, msg, channel):
        """Post msg to a Slack channel."""
        # check for pound char
        if len(channel.split('#')) == 2:
            channel = channel.split('#')[1]

        # send message
        self._slk_instance.api_call('chat.postMessage', as_user='true',
                                    channel='#{0}'.format(channel), text=msg)


class TwitterGHRePT(object):
    """Class to implement a basic Twitter client for use with GHRePTBot."""
    def __init__(self):
        # get OAuth
        oauth = self._twitter_oauth()

        # set domain
        domain = 'userstream.twitter.com'

        # get Twitter instance
        self._tw_instance = twitter.TwitterStream(auth=oauth, domain=domain)

    def _twitter_oauth(self):
        """Creating dict of environment variables for Twitter OAuth."""
        # env variables
        envd = {
                    'TCK': 'TWITTER_CONSUMER_KEY',
                    'TCS': 'TWITTER_CONSUMER_SECRET',
                    'TAT': 'TWITTER_ACCESS_TOKEN',
                    'TATS': 'TWITTER_ACCESS_TOKEN_SECRET'
        }

        # dict comp
        toked = {key: os.environ.get(value) for key, value in envd.iteritems()}

        # return OAuth
        return twitter.OAuth(toked['TAT'], toked['TATS'], toked['TCK'],
                             toked['TCS'])

    def tweet_text_stream(self, func=colortxt):
        """Get the actual content of the tweet, and no meta info."""
        # loop
        try:
            # announce start
            colortxt(TSTRM_MSG.format('Started', ''), 'green')
            # loop over stream
            for tweet in self._tw_instance.user():
                try:
                    func(tweet['text'].encode('utf-8'))
                except KeyError:
                    colortxt('Data {0} Skipped'.format(tweet.keys()), 'green')
        # exit on Ctrl-C
        except KeyboardInterrupt:
            sys.exit(colortxt(TSTRM_MSG.format('Stopped', '\n\n'), 'red'))


class GHRePTBot(object):
    """Class to implement GHRePT methods for CLI and automation."""
    def __init__(self):
        # TODO
        colortxt(BANNER, 'green')

    def help(self, slack=None, twitter=None, stdout=None):
        """Help method for GHRePTBot. Prints usage on default."""
        pass

    def filter(self, configfile=FILTER_CONFIG, debug=False):
        """Simple method to filter and post tweets."""
        # load config file and setup sh*t
        ghrept_filter = FilterStream(configfile, True if debug else False)

        # run
        ghrept_filter.filter_tweets()

    def configure(self, filterconfig=None, twitter=None, slack=None):
        """Method to configure tokens or filter settings."""
        # # control flow on config
        # if filterconfig:
        #     # call filterconfig
        #     ConfigFilter(FILTER_CONFIG if filterconfig == '' else filterconfig)
        #
        # if twitter:
        #     ConfigTwitterApp(TW_TOKENS if twitter == '' else twitter)
        #
        # if slack:
        #     ConfigSlackApp(SLK_TOKENS if slack == '' else slack)
        pass

    def setup(self):
        """Export necessary tokens to run GHRePTBot."""
        pass

    def test_twitter_api(self):
        """Get tweets from home timeline stream."""
        # start client
        TwitterGHRePT().tweet_text_stream()

    def test_slack_api(self, msg="GHRePTBot Test Message", channel='general'):
        """Post test message to Slack."""
        # post
        SlackGHRePT().post_msg(msg, channel)

    def test_highlight(self, text):
        # words to match
        words = ["at", "the", "he", "she", "a", "in", "on", "with", "is"]

        # highlight
        tweet_highlight(text, words)

    def test_matcher(self, text):
        # words to match
        words = ["at", "the", "he", "she", "a", "in", "on", "with", "is"]

        # get matcher
        regex = compile_regex(words)

        # create matcher
        matcher = match_wrapper(regex, words, tweet_highlight, debug=True)

        # run matcher
        matcher(text)


# executable
if __name__ == '__main__':

    # get fire instance
    fire.Fire(GHRePTBot)
