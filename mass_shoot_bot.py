#!/usr/bin/env python
# encoding: utf-8
"""
There is a mass shooting on average every day in the United States.
Here are the shootings on this day last year.
https://twitter.com/mass_shoot_bot
"""
import argparse
import csv
import datetime
import os.path
import sys
import webbrowser

import inflect  # pip install inflect
import twitter  # pip install twitter
import yaml  # pip install pyyaml
from dateutil.parser import parse  # pip install python-dateutil
from dateutil.relativedelta import relativedelta
from pytz import timezone  # pip install pytz

# from pprint import pprint


def timestamp():
    """ Print a timestamp and the filename with path """
    print(datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p") + " " + __file__)


def load_yaml(filename):
    """
    File should contain:
    consumer_key: TODO_ENTER_YOURS
    consumer_secret: TODO_ENTER_YOURS
    access_token: TODO_ENTER_YOURS
    access_token_secret: TODO_ENTER_YOURS
    wordnik_api_key: TODO_ENTER_YOURS
    """
    with open(filename) as f:
        data = yaml.load(f)

    if not data.keys() >= {
        "access_token",
        "access_token_secret",
        "consumer_key",
        "consumer_secret",
    }:
        sys.exit("Twitter credentials missing from YAML: " + filename)

    if "last_shooting" not in data:
        data["last_shooting"] = None

    return data


def save_yaml(filename, data):
    """
    Save data to filename in YAML format
    """
    with open(filename, "w") as yaml_file:
        yaml_file.write(yaml.dump(data, default_flow_style=False))


def tweet_it(string, credentials, image=None, location=None):
    """ Tweet string and image using credentials """
    if len(string) <= 0:
        return

    # Create and authorise an app with (read and) write access at:
    # https://dev.twitter.com/apps/new
    # Store credentials in YAML file
    auth = twitter.OAuth(
        credentials["access_token"],
        credentials["access_token_secret"],
        credentials["consumer_key"],
        credentials["consumer_secret"],
    )
    t = twitter.Twitter(auth=auth)

    if location and not args.test:
        place_id = place_id_for_location(t, location)

    print("TWEETING THIS:\n" + string)

    if args.test:
        print("(Test mode, not actually tweeting)")
    else:

        if image:
            print("Upload image")

            # Send images along with your tweets.
            # First just read images from the web or from files the regular way
            with open(image, "rb") as imagefile:
                imagedata = imagefile.read()
            t_up = twitter.Twitter(domain="upload.twitter.com", auth=auth)
            id_img = t_up.media.upload(media=imagedata)["media_id_string"]

            if place_id:
                result = t.statuses.update(
                    status=string,
                    media_ids=id_img,
                    display_coordinates=True,
                    place_id=place_id,
                )
            else:
                result = t.statuses.update(status=string, media_ids=id_img)
        elif place_id:
            result = t.statuses.update(
                status=string, display_coordinates=True, place_id=place_id
            )
            print(place_id)
        else:
            result = t.statuses.update(status=string)

        url = (
            "http://twitter.com/"
            + result["user"]["screen_name"]
            + "/status/"
            + result["id_str"]
        )
        print("Tweeted:\n" + url)
        if not args.no_web:
            webbrowser.open(url, new=2)  # 2 = open in a new tab, if possible


def place_id_for_location(t, location):
    """Look up place_id from Twitter using a city/state info"""
    # https://dev.twitter.com/rest/reference/get/geo/search
    query = location
    contained_within = "96683cc9126741d1"  # USA

    place = t.geo.search(
        query=query,
        granularity="city",
        contained_within=contained_within,
        max_results=1,
    )

    place_id = place["result"]["places"][0]["id"]
    print("Location:", location)
    print("Place ID:", place_id)

    return place_id


def filename_for_year(year, version):
    filename = year + version + ".csv"
    print("Filename:", filename)

    filename = os.path.join(args.csv, filename)
    print("Filename:", filename)

    return filename


def get_location(shooting):
    """
    Old format CSV has a single Location field,
    for example: "San Francisco, CA".
    New format CSV has State,"City Or County",Address fields.
    Return something like a city and state.
    Don't really need street-level.
    New new format CSV State,"City Or County",Address fields
    """
    try:
        location = shooting["Location"]
    except KeyError:
        city_or_county = shooting["City Or County"]
        state = shooting["State"]
        location = city_or_county + ", " + state
    return location


def format_shooting(shooting):

    try:
        dead = int(shooting["Dead"])
        injured = int(shooting["Injured"])
    except KeyError:  # 2016 format is different
        dead = int(shooting["# Killed"])
        injured = int(shooting["# Injured"])

    if dead > 0:
        d = p.number_to_words(dead, threshold=10)
        pd = p.plural("person", dead)
    if injured > 0:
        i = p.number_to_words(injured, threshold=10)
        pi = p.plural("person", injured)

    if dead > 0 and injured > 0:
        shot = f"{d} {pd} shot dead and {i} injured"
    elif dead > 0 and injured == 0:
        shot = f"{d} {pd} shot dead"
    elif dead == 0 and injured > 0:
        shot = f"{i} {pi} shot and injured"

    location = get_location(shooting)
    try:
        date = shooting["Date"]
    except KeyError:  # 2016 format is different
        date = shooting["Incident Date"]
    text = f"{date}: {shot} in {location}"

    if "Article1" in shooting and shooting["Article1"] != "":
        text += " " + shooting["Article1"]

    return text


def massshooting():

    pacific = timezone("US/Pacific")
    now = datetime.datetime.now(pacific)
    # now = eastern.localize(now)

    # TEMP TEST this year
    # now = now + relativedelta(years=1)
    # now = now + relativedelta(days=5)
    # TEMP TEST this year

    print("US/Pacific now:", now)

    last_year = str(now.year - 1)
    print("This year:", now.year)
    print("Last year:", last_year)

    this_day_last_year = now - relativedelta(years=1)
    print("this_day_last_year:", this_day_last_year)

    filename = filename_for_year(last_year, "MASTER")
    if not os.path.isfile(filename):
        filename = filename_for_year(last_year, "CURRENT")

    with open(filename, "r") as infile:
        reader = csv.DictReader(infile)

        # shootings = list(reader)
        todays_shootings = []
        for rownum, row in enumerate(reader):
            try:
                indate = parse(row["Date"])
            except KeyError:  # 2016 format is different
                indate = parse(row["Incident Date"])
            if indate.date() == this_day_last_year.date():
                todays_shootings.append(row)

    if not todays_shootings:
        print("No shootings today")
        return None, None

    # Already had one today?
    if data["last_shooting"] in todays_shootings:
        # Yes. Which one?
        already_today = todays_shootings.index(data["last_shooting"])
        # Which next?
        next_today = already_today + 1
        if next_today >= len(todays_shootings):
            print("No more shootings today")
            return None, None
        next_shooting = todays_shootings[next_today]
    else:
        print("This is the first today")
        next_shooting = todays_shootings[0]

    # Update YAML
    data["last_shooting"] = next_shooting

    print("Next:", next_shooting)
    print("Next:", format_shooting(next_shooting))

    location = get_location(next_shooting)
    return format_shooting(next_shooting), location


if __name__ == "__main__":

    timestamp()

    parser = argparse.ArgumentParser(
        description="There is a mass shooting on average every day in the United "
        "States. Here are the shootings on this day last year.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--csv", default="data/", help="Directory for CSV file")
    parser.add_argument(
        "-y",
        "--yaml",
        default="/Users/hugo/Dropbox/bin/data/mass_shoot_bot.yaml",
        help="YAML file location containing Twitter keys and secrets",
    )
    parser.add_argument(
        "-nw",
        "--no-web",
        action="store_true",
        help="Don't open a web browser to show the tweeted tweet",
    )
    parser.add_argument(
        "-x",
        "--test",
        action="store_true",
        help="Test mode: go through the motions but don't tweet anything",
    )
    args = parser.parse_args()

    data = load_yaml(args.yaml)

    p = inflect.engine()
    tweet, location = massshooting()

    if tweet:
        tweet_it(tweet, data, location=location)

    if not args.test:
        save_yaml(args.yaml, data)

# End of file
