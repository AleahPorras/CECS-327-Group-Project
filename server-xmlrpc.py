import xmlrpc.server 
import zmq
import json

#!___________________________     INITIALIZING     __________________________
#For the list_directory() function
#directory = os.path.dirname(os.path.abspath(__file__))

#creation of the server (listens to the address)
server = xmlrpc.server.SimpleXMLRPCServer(('localhost',3000), logRequests = True)

# merging from publisher.py
BROKER = "tcp://127.0.0.1:5555"
ctx = zmq.Context.instance()
push = ctx.socket(zmq.PUSH) # pushes messages to the broker.py
push.connect(BROKER)
print(f"[Server] Connected to broker at {BROKER}.")

# Keeps track of all chat rooms, members, and owners
list_of_chat_rooms = {}

#!___________________________ FUNCTION DEFINITIONS __________________________



#& VALIDATION FUNCTIONS
# returns  the state of all rooms, the rooms, members, and owners
def all_rooms():
    
    return list(list_of_chat_rooms.keys())

#returns the state of just the members of a room
def current_members(room_to_join):
    list_of_members = list_of_chat_rooms[room_to_join]['members']
    return list_of_members

#& FUNCTION THAT CREATES A NEW ROOM, ADDS THE CREATOR TO ROOM
def create_room(room_to_create, user): # later on will implement an "owned by:" parameter
    """Creates a new chatroom that different clients can join. Will check if a chatroom with the same name already exists."""

    # Error message when a chatroom that already exists is inputed
    if room_to_create in list_of_chat_rooms:
        return f"Error: The chatroom {room_to_create} already exists."

    # Appends the new chatroom to the list of existing chatrooms
    list_of_chat_rooms[room_to_create] = {
        'owner': [],
        'members': [], # where we will store the members of the chatroom
    }
    # Confirmation message that chatroom has been created
    print(f"Chatroom {room_to_create} has been created.\n")

    list_of_chat_rooms[room_to_create]['owner'].append(user)
    # Confirmation message that chatroom owner has entered the room.
    print("BELLO BELLO BELLO BELLO WELCOME TO THE START OF YOUR CHAT HISTORY!!")
    print(f"Chatroom owner {user} has entered the room {room_to_create}.")
    return list_of_chat_rooms

#& FUNCTION THAT ADDS A USER TO A ROOM
def join_room(room_to_join, user): 
    """Will allow the user to join rooms they are intrested in."""

    # Error message when a chatroom that does not exist is inputed
    if room_to_join not in list_of_chat_rooms:
        return f"Error: The chatroom {room_to_join} does not exist."

    # appends the current user to the members
    list_of_chat_rooms[room_to_join]['members'].append(user)

    # Confirmation message that a user has entered the chatroom.

    updated_members = list_of_chat_rooms[room_to_join]['members']
    print(f"Welcome {user}! They have entered the room {room_to_join}.")

    # returns the new list of members
    return updated_members

#& FUNCTION THAT SENDS MESSAGE TO THE BROKER
def send_message(chatroom_name, user, message):
    # Error message when a chatroom that does not exist is inputed
    if chatroom_name not in list_of_chat_rooms:
        return f"Error: The chatroom {chatroom_name} does not exist."
    
    topic = f"room/{chatroom_name}"

    payload = {"user": user, "text": message}

    try:
        # Formats the message 
        message_to_broker = {"topic": topic, "payload": payload}

        # Pushes message to the broker
        push.send_json(message_to_broker)
        print(f"Sent message to chatroom {topic}: {payload}")
        return True
    except Exception:
        return False


#!___________________________ FUNCTION REGISTRATION ___________________________
#registering the functions

server.register_function(all_rooms)
server.register_function(send_message)
server.register_function(current_members)

server.register_function(create_room)
server.register_function(join_room)


#!___________________________     SERVER CALLING    ___________________________
if __name__ == '__main__': 
    try:
        ## Successful 
        print('Connecting to ThisCord Server...')
        #starting the server
        server.serve_forever()

    except KeyboardInterrupt:
        ## Not Sucessful
        print('Unable to connect, try again later')

        print('Unable to connect, try again later')

