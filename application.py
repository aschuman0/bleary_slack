#!bin/python
'''
bleary-slack
a flask-based API for use with slack slash commands
aaron@urbanairship.com

more usage example and config options can be found in the README

test cURL
curl -v -X POST http://127.0.0.1:5000/api/v1/send/ -d "token=local_test&text='all'"
'''

import json
import sys
import datetime
import thread

import urbanairship as ua 
from flask import Flask, render_template, request, abort
import requests

expected_tokens = [] # list of possible input tokens

application = Flask(__name__)

def get_android_platform_opts(notification, timestamp):
	android_opts = {}
	android = notification['android']

	for k,v in android.iteritems():
		if k == 'alert':
			android_opts['alert'] = '%s\n%s' % (v, timestamp)
		if k == 'collapse_key':
			android_opts['collapse_key'] = v
		if k == 'time_to_live':
			android_opts['time_to_live'] = v
		if k == 'delay_while_idle':
			android_opts['delay_while_idle'] = v
		if k == 'extra':
			android_opts['extra'] = v
		if k == 'local_only':
			android_opts['local_only'] = v

	return android_opts

def get_ios_platform_opts(notification, timestamp):
	ios_opts = {}
	ios = notification['ios']

	for k,v in ios.iteritems():
		if k == 'alert':
			ios_opts['alert'] = '%s\n%s' % (v, timestamp)
		if k == 'badge':
			ios_opts['badge'] = v
		if k == 'sound':
			ios_opts['sound'] = v
		if k == 'content_available' or k == 'content-available':
			ios_opts['content_available'] = v
		if k == 'extra':
			ios_opts['extra'] = v
		if k == 'expiry':
			ios_opts['expiry'] = v
		if k == 'category':
			ios_opts['category'] = v
		if k == 'title':
			ios_opts['title'] = v

	return ios_opts

def get_actions(test):
	if 'actions' in test:
		pos_actions = {}

		for k,v in test['actions'].iteritems():
			if k == 'add_tag':
				pos_actions['add_tag'] = v
			if k == 'remove_tag':
				pos_actions['remove_tag'] = v
			if k == 'share':
				pos_actions['share'] = v
			if k == 'open':
				pos_actions['open'] = v
			if k == 'app_defined':
				pos_actions['app_defined'] = v

	return pos_actions

def get_interactive(test):
	interactive_opts = {}

	if 'type' in test['interactive']:
		interactive_opts['type'] = test['interactive']['type']
		for k,v in test['interactive'].iteritems():
			if k == 'button_actions':
				interactive_opts['button_actions'] = v

	return interactive_opts

def notification(test):
	utcnow = datetime.datetime.utcnow()
	timestamp = utcnow.strftime('%Y-%m-%d %H:%M')

	notification = test['notification']
	notification_opts = {}

	if 'actions' in test:
		notification_opts['actions'] = get_actions(test)

	if 'interactive' in test:
		notification_opts['interactive'] = get_interactive(test)

	if 'alert' in notification:
		notification_opts['alert'] = '%s\n%s' % (notification['alert'], timestamp)

	if 'ios' in notification:
		notification_opts['ios'] = get_ios_platform_opts(notification, 
			timestamp)

	if 'android' in notification:
		notification_opts['android'] = get_android_platform_opts(notification,
			timestamp)

	return ua.notification(**notification_opts)

def audience(test):
	audience = test['audience']

	if audience == 'all':
		push_audience = ua.all_
	elif 'device_token' in audience:
		push_audience = ua.push.audience.device_token(audience['device_token'])
	elif 'ios_channel' in audience:
		push_audience = ua.push.audience.ios_channel(audience['ios_channel'])
	elif 'android_channel' in audience:
		push_audience = ua.push.audience.android_channel(audience['android_channel'])
	elif 'tag'in audience:
		push_audience = ua.push.audience.tag(audience['tag'])
	elif 'alias' in audience:
		push_audience = ua.push.audience.alias(audience['alias'])
	# elif 'named_user' in audience: #no named user support yet
	# 	push_audience = ua.push.audience.named_user(audience['named_user'])
	elif 'segment' in audience:
		push_audience = ua.push.audience.segment(audience['segment'])
	else:
		push_audience = None

	return push_audience

def device_types(test):
	device_types = test['device_types']

	if device_types == 'all':
		push_device_types = ua.all_
	else:
		push_device_types = device_types

	return push_device_types

def message(test):
	message = test['message']
	if 'title' in message and 'body' in message:
		message_opts = {}

		for k,v in test['message'].iteritems():
			if k == 'title':
				message_opts['title'] = v
			if k == 'body':
				message_opts['body'] = v
			if k == 'extra':
				message_opts['extra'] = v

		return ua.message(**message_opts)

	else:
		return None

def parse_alert_text(push):
	attrs = dir(push)
	
	if 'notification' in attrs:
		notification = push.notification
	elif 'push' in attrs:
		notification = push.push.notification

	if 'ios' in notification:
		alert_text = notification['ios']['alert']
	elif 'android' in notification:
		alert_text = notification['android']['alert']
	elif notification['alert'] is not None:
		alert_text = notification['alert']
	else:
		alert_text = 'Non alerting'

	return alert_text

def parse_response_text(response):
	if response.push_ids:
		response_ids = ', '.join(response.push_ids)
	elif response.operation_id:
		response_ids = response.operation_id
	else:
		response_ids = 'none'

	return response_ids

def ok_output(response, push, config_dict):
	alert_text = parse_alert_text(push)
	response_ids = parse_response_text(response)

	alert_text = alert_text.replace("\n", " | ")
	styled_out = '%s %s | %s' % ('[ OK ]',
							 alert_text,
							 response_ids)

	cl_output(styled_out)
	slack_output(None, config_dict, styled_out)

def error_output(response, push, config_dict):
	alert_text = parse_alert_text(push)
	alert_text = alert_text.replace("\n", " | ")

	styled_out = '%s %s' % ('[FAIL]',
							 alert_text)
	cl_output(styled_out)
	slack_output(None, config_dict, styled_out)

def total_output(total_ok, total_error, config_dict):
	output_str = '%s %i OK | %i ERROR | %i Total | %.2f %% Failure Rate' % (
							'[INFO]',
							total_ok,
							total_error,
							total_error + total_ok,
							100.0 * (float(total_error) / (float(total_error) + float(total_ok))))
	cl_output(output_str)
	slack_output(output_str, config_dict)

def cl_output(output_str):
	print(output_str)

def slack_output(output_str, config_dict, verbose_str=None):
	if config_dict['slack_webhook'] and output_str is not None:
		requests.post(config_dict['slack_webhook'],
                      data=json.dumps({'text': output_str}))
	if config_dict['slack_verbose'] and verbose_str is not None:
		requests.post(config_dict['slack_verbose'],
                      data=json.dumps({'text': verbose_str}))

def create_push_obj(test, airship):
	push = airship.create_push()
	push.audience = audience(test)
	push.notification = notification(test)
	push.device_types = device_types(test)
	if 'message' in test:
		push.message = message(test)
	return push

def create_schedule_obj(test, airship):
	schedule = airship.create_scheduled_push()
	schedule.push = create_push_obj(test, airship)
	schedule_info = test['schedule']
	
	if 'name' in schedule_info:
		schedule.name = schedule_info['name']

	if 'delta' in schedule_info:
		delta_time = datetime.datetime.utcnow() + datetime.timedelta(
													**schedule_info['delta'])
		schedule.schedule = ua.scheduled_time(delta_time)
	elif 'time' in schedule_info:
		schedule_time = datetime.datetime.strptime(
							schedule_info['time'], 
							'%Y-%m-%dT%H:%M:%S')
		schedule.schedule = ua.scheduled_time(schedule_time)

	return schedule

def create_plt_obj(test, airship):
	plt = airship.create_scheduled_push()
	plt.push(test, airship)
	plt_info = test['plt']
	
	if 'name' in plt_info:
		plt.name = plt_info['name']
	
	if 'time' in plt_info:
		plt_time = datetime.datetime.strptime(plt_info['time'], 
			'%Y-%m-%dT%H:%M:%S')
		plt.schedule = ua.local_scheduled_time(plt_time)

	return plt

def load_config(config_file_path):
	with open(config_file_path, 'r') as f:
		config_dict = json.load(f)
		return config_dict

def load_tests(tests_file_path, test):
	with open(tests_file_path, 'r') as f:
		tests_dict = json.load(f)

		if test == 'all':
			return tests_dict
		else:
			for item in tests_dict:
				if item['command'] == test:
					return [item]

def send_pushes(push_list, repeat, config_dict):
	repeat_counter = 0
	total_ok = 0
	total_error = 0

	while repeat_counter < repeat:
		repeat_counter += 1
		result = None

		for push in push_list:
			try:
				result = push.send()
				total_ok += 1
				ok_output(result, push, config_dict)
			except ua.common.AirshipFailure as result:
				total_error += 1
				error_output(result, push, config_dict)

		total_output(total_ok, total_error, config_dict)

def send(test='all', repeat=1, config_file='./config.json', test_file='./tests.json'):
	tests_list = []

	config_dict = load_config(config_file)
	test_dict = load_tests(test_file, test)

	airship = ua.Airship(config_dict['app_key'], config_dict['master_secret'])

	for test in test_dict:
		if 'schedule' in test:
			tests_list.append(create_schedule_obj(test,airship))
		else:
			tests_list.append(create_push_obj(test, airship))

	send_pushes(tests_list, repeat, config_dict)

def help(tests):
	help_string = 'Command | Description'

	for test in tests:
		help_string = help_string + '\n%s | %s' % (test['command'], test['description'])

	return help_string

@application.route('/api/v1/send/', methods=['POST'])
def api_send():
	try:
		info = request.form
	except:
		print "[WARN] Improper request."
		return 'Something bad happened. Try again.'
	
	# load tests file
	tests = load_tests('./tests.json', 'all')

	# check for proper token
	token = info['token']
	print 'input token was %s' % token
	if token not in expected_tokens:
		print "recevied request with improper token id: %s" % info['token']
		return 'Bad auth token. Nothing sent.'

	# split input args to command and attempts
	try:
		input_args = info['text'].split()
		command = input_args[0]
	except:
		return 'Could not parse argument. Try /bleary help for more.'
	
	# check if there is a repeat value / check if value is int / assign 1 if it doesn't exist
	if len(input_args) == 2:
		if input_args[1].isdigit():
			attempts = int(input_args[1])
		else:
			return 'Number of attempts not recognized.'
	else:
		attempts = 1

	# build commands list for validation
	test_commands = list()
	for test in tests:
		add_command = test['command']
		test_commands.append(add_command)

	# send help if requested
	if command == 'help':
		return help(tests)

	# make sure command exists
	if command not in test_commands and command != 'all':
		return 'Command %s not valid. Use /bleary help to list tests.' % (command)

	# send tests
	thread.start_new_thread(send, (command, attempts))

	return 'Sending %s %s time(s). Results in #bleary and #bleary_debug.' % (command, str(attempts))

if __name__ == '__main__':
	application.run(debug=True)
	