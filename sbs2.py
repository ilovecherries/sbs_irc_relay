import requests
import threading
import json

class SBS2MessageLongPoller:
    """
    Creates a message long poller that infinitely loops forever until it is 
    destroyed. It will initially poll for one message for the first ID, then
    use it in order to infinitely keep polling for messages.

    In order to use it correctly, I would recommend doing the following steps:
    1. Instantiating a LongPoller object for your client instance.
    2. Create a new Thread and then set the target to the run_forever() 
       function
    """
    def __init__(self, api_url, callback, authtoken):
        self.api_url = api_url
        self.callback = callback
        self.authtoken = authtoken
        # create an initial poll in order to get the last ID sent
        comments_settings = {
            'reverse': True,
            'limit': 1
        }
        # this is in case that the request times out
        data = {}
        try:
            r = requests.get(
                f'{self.api_url}Read/chain/?requests=comment-' +
                json.dumps(comments_settings, separators=(',', ':')) +
                '&requests=user.0createUserId&content.0parentId'
            )
            data = r.json()
        except:
            pass
        self.last_id = data['comment'][0]['id']
    
    def run_forever(self):
        """Infinite event loop that will send data if successful"""
        headers={'Authorization': f'Bearer {self.authtoken}'}
        while True:
            listener_settings = {
                'lastId': self.last_id,
                'chains': ['comment.0id', 'user.1createUserId', 'content.1parentId']
            }
            r = requests.get(
                f"{self.api_url}Read/listen?actions=" +
                json.dumps(listener_settings, separators=(',', ':')),
                headers=headers
            )
            data = r.json()
            self.last_id = data['lastId']
            self.callback(data)

class SBS2:
    def __init__(self):
        self.api_url = 'https://smilebasicsource.com/api/'
        self.users = {}
        self.rooms = {}
        self.userid = 12

        self.message_ids = []
        self.tags = []
        
    def login(self, username, password):
        """Gets the auth token from the API and saves it"""
        r = requests.post(self.api_url + 'User/authenticate',
            json={
                'username': username,
                'password': password
            }
        )

        self.authtoken = r.text
    
    def connect(self):
        """Starts polling from website in infinite loop"""
        if not self.authtoken:
            raise Exception()

        self.longpoller = SBS2MessageLongPoller(
            self.api_url,
            self.poll_message,
            self.authtoken
        )
        thread = threading.Thread(target=self.longpoller.run_forever)
        thread.daemon = True
        thread.start()
    
    def poll_message(self, data):
        """Is run whenever a long poll is completed"""
        # update users
        self.users.update({
            user['id']: user 
            for user in data['chains']['user']
        })
        # update channels?
        self.rooms.update({
            content['id']: {}
            for content in data['chains']['content']
        })
        self.on_userList(0)
        # send messages to irc
        for i in data['chains']['comment']:
            # remove newline if first line is JSON
            if '\n' in i['content']:
                try:
                    msgdata = json.loads(i['content'][:i['content'].index('\n')])
                    i['content'] = i['content'][i['content'].index('\n')+1:]
                except json.decoder.JSONDecodeError:
                    pass
            self.on_message(i)
    
    def send_message(self, room_id, content):
        settings = {
            'm': '12y'
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.authtoken}'
        }
        requests.post(
            f'{self.api_url}Comment', 
            headers=headers, 
            json={
                'parentId': int(room_id),
                'content': json.dumps(settings)+'\n'+content
            }
        )
        pass