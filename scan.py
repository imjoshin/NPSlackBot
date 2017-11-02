import subprocess, time, json, datetime, os, sys
import constants, auth

lastPlayerNotified = False

def main():
	global lastPlayerNotified
	lastPlayerNotified = False

	while(1):
		apiUrl = auth.API_DATA_URL % (constants.GAME_ID)
		command = constants.BASE_CURL % (apiUrl)

		# make call
		try:
			process = subprocess.check_output(('timeout %d {}' % (constants.CURL_TIMEOUT)).format(command), shell=True, stderr=subprocess.PIPE)
		except subprocess.CalledProcessError as exc:
			if exc.returncode == 124:
				log("Reached timeout of %d seconds on curl." % (constants.CURL_TIMEOUT))
				time.sleep(constants.SLEEP_TIME)
				continue

		currentTurn = json.loads(process)
		processCurl(currentTurn)
		time.sleep(constants.SLEEP_TIME)

def processCurl(currentTurn):
	global lastPlayerNotified

	# read data file
	with open(constants.TURN_FILE, 'a+') as turnFile:
		# if first scan
		if os.path.getsize(constants.TURN_FILE) is 0:
			currentTurn['turn_num'] = 1
			turnFile.write(json.dumps([currentTurn]))
			log("First scan! Starting turn #%d! Wrote to %s." % (currentTurn['turn_num'], constants.TURN_FILE))
			return

		turnData = json.loads(turnFile.read())
		currentTurn['turn_num'] = len(turnData) + 1

		lastTurn = turnData[len(turnData) - 1]

		# if this scan has a different end time than the last turn saved (i.e. new turn)
		if (str(currentTurn['turn_based_time_out']) != str(lastTurn['turn_based_time_out'])):
			if not constants.DEBUG:
				turnData.append(currentTurn)
				turnFile.seek(0)
				turnFile.truncate()
				turnFile.write(json.dumps(turnData))
			log("Starting turn #%d! Wrote to %s." % (currentTurn['turn_num'], constants.TURN_FILE))
			postToSlack(currentTurn, lastTurn)
			lastPlayerNotified = False
		elif not lastPlayerNotified:
			playersNotReady = 0
			for player in currentTurn['players']:
				if not player['ready']:
					playersNotReady += 1
					playerToPost = player

			if playersNotReady is 1:
				postLastPlayerToSlack(playerToPost)
				lastPlayerNotified = True

def postToSlack(currentTurn, lastTurn):
	log("Posting to slack...")

	players = sorted(currentTurn['players'], key=lambda k: k['rank'])

	for player in players:
		# get this player last turn
		for lastPlayer in lastTurn['players']:
			if player['name'] == lastPlayer['name']:
				player['lastTurn'] = lastPlayer

	if constants.CONDENSED_POST:
		postToSlackCondensed(players, currentTurn)
	else:
		postToSlackFull(players, currentTurn)

def postToSlackCondensed(players, turn):
	attachments = []

	for player in players:
		rankDif = getRankDif(player, player['lastTurn'], True)
		status = "BOT: " if player['conceded'] is 1 else "AFK: " if player['conceded'] is 2 else ""

		tech = 0
		for techName in player['tech']:
			tech += int(player['tech'][techName]['level'])
		#tech = tech / len(player['tech'])

		title = '%d. %s%s %s' % (player['rank'], status, player['name'], rankDif)
		text = ':np-star: %d :np-ship: %d :np-res: %d\n:np-econ: %d :np-ind: %d :np-sci: %d' % (player['total_stars'], player['total_strength'], tech, player['total_economy'], player['total_industry'], player['total_science'])

		attachments.append({
			'color': player['color'],
			#'author_icon': 'https://np.ironhelmet.com/images/avatars/160/%d.jpg' % (player['avatar']),
			'title': title,
			'text': text
		})

	# add turn end footer
	turnEnd = datetime.datetime.fromtimestamp(int(turn['turn_based_time_out'] / 1000)).strftime('%a, %b %-d at %-I:%M:%S %p')
	cycleText = ", and a new cycle starts" if turn['tick'] % turn['production_rate'] is 0 else ""
	text = '<!here> Turn *%d* just started%s! It ends %s.\nHere is the leaderboard:' % (turn['turn_num'], cycleText, turnEnd)

	post = {
        'username': constants.SLACK_USER,
        'channel': auth.SLACK_CHANNEL if not constants.DEBUG else auth.SLACK_CHANNEL_DEBUG,
        'icon_url': constants.SLACK_ICON,
        'attachments': attachments,
		'text': text
    }

	command = constants.SLACK_CURL % (json.dumps(post), auth.SLACK_HOOK)
	process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def postToSlackFull(players, turn):
	turnEnd = datetime.datetime.fromtimestamp(int(turn['turn_based_time_out'] / 1000)).strftime('%a, %b %-d at %-I:%M:%S %p')
	cycleText = ", and a new cycle starts" if turn['tick'] % turn['production_rate'] is 0 else ""
	text = '<!here> Turn *%d* just started%s! It ends %s.\nHere is the leaderboard:' % (turn['turn_num'], cycleText, turnEnd)

	post = {
		'username': constants.SLACK_USER,
		'channel': auth.SLACK_CHANNEL if not constants.DEBUG else auth.SLACK_CHANNEL_DEBUG,
		'icon_url': constants.SLACK_ICON,
		'text': text
	}

	command = constants.SLACK_CURL % (json.dumps(post), auth.SLACK_HOOK)

	process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	time.sleep(.5)

	for player in players:
		rankDif = getRankDif(player, player['lastTurn'], False)
		status = "BOT: " if player['conceded'] is 1 else "AFK: " if player['conceded'] is 2 else ""

		title = '%d. %s%s' % (player['rank'], status, player['name'])
		text = 'Rank: %s\n:np-star: %d :np-ship: %d\n:np-econ: %d :np-ind: %d :np-sci: %d' % (rankDif, player['total_stars'], player['total_strength'], player['total_economy'], player['total_industry'], player['total_science'])

		post = {
	        'username': title,
	        'channel': auth.SLACK_CHANNEL if not constants.DEBUG else auth.SLACK_CHANNEL_DEBUG,
	        'icon_url': 'https://np.ironhelmet.com/images/avatars/160/%d.jpg' % (player['avatar']),
	        'attachments': [{
				'color': player['color'],
				'text': text
			}]
	    }

		command = constants.SLACK_CURL % (json.dumps(post), auth.SLACK_HOOK)
		process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		time.sleep(.5)

def getRankDif(player, playerLastTurn, isCondensed):
	# determine rank change
	if player['rank'] > playerLastTurn['rank']:
		return "(:red-down: %d )" % (player['rank'] - playerLastTurn['rank'])
	elif player['rank'] < playerLastTurn['rank']:
		return "(:green-up: %d )" % (playerLastTurn['rank'] - player['rank'])
	else:
		return "" if isCondensed else "No change"


def postLastPlayerToSlack(player):
	# add turn end footer
	text = '*%s* is the only one left to take their turn!' % (player['name'])

	post = {
		'username': constants.SLACK_USER,
		'channel': auth.SLACK_CHANNEL if not constants.DEBUG else auth.SLACK_CHANNEL_DEBUG,
		'icon_url': constants.SLACK_ICON,
		'attachments': [{
			'color': player['color'],
			'text': text,
			"mrkdwn_in": ["text"]
		}],
	}

	command = constants.SLACK_CURL % (json.dumps(post), auth.SLACK_HOOK)
	process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def log(str):
	logFile = "log" if not constants.DEBUG else "log_debug"
	p = "%s : %s" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), str)
	print(p)
	with open(logFile, "a") as l:
		l.write("%s\n" % p)

if __name__ == "__main__":
	main()
