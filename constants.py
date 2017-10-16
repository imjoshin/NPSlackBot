DEBUG = False

BASE_CURL = "curl -X POST -H 'Content-type: application/json' %s"
SLACK_CURL = "curl -X POST -H 'Content-type: application/json' --data '%s' %s"
SLACK_USER = "SpacegameBot"
SLACK_ICON = "http://joshjohnson.io/images/np.png"

CURL_TIMEOUT = 10
GAME_ID = "5816445419388928"
SLEEP_TIME = 120
TURN_FILE = "turndata-%s.json" % (GAME_ID)
