# Bleary Slack

## Installation
1. Clone repo locally
2. Install virtualenv if it is not already installed `pip install virtualenv`
3. Create a new virtualenv in Bleary directory  `virtualenv .`
4. Activate bleary's virtualenv `source bin/activate`
5. Install needed packages `pip install -r requirements.txt`
6. You should be good to go. When done, use `deactivate` to close bleary's virtualenv. You'll need to activate the virtualenv each time you use bleary by using the command in step 4.

## JSON Configuration Files
Bleary requires 2 files in the root dir (or elsewhere passed in as args): `tests.json` and `config.json`. Examples are provided in this repo.

### config.json
This file contains the app key, app secret and master secret for the app that you're pushing to as well as slack webhooks to output to. The Slack webhook keys must be included but can be `null`.

This file is not included in this repo, but must be created to run Bleary.

Example:
```json
{
	"appkey" : "<app_key>",
	"mastersecret" : "<master_secret>",
    "slack_url" : null,
    "slack_verbose" : null
}
```

You will also need to add to the list of expected tokens in the `application.py` file. This is provided by slack when creating the slash command integration.

### tests.json
This is a JSON file which contains all the information used to create different types of push.
The `command` key for each dictionary is used as part of the slask command.
Do not use `all` as this is reserved for other commands.

Example:
```json
  {
    "command": "broadcast",
    "audience": "all",
    "notification": {
      "alert": "broadcast"
    },
    "device_types": [
      "ios",
      "android"
    ]
  }
```

