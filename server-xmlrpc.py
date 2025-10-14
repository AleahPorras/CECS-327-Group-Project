import xmlrpc.server 
import os

#!___________________________     INITIALIZING     __________________________
#For the list_directory() function
#directory = os.path.dirname(os.path.abspath(__file__))

#creation of the server (listens to the address)
server = xmlrpc.server.SimpleXMLRPCServer(('localhost',3000), logRequests = True)


list_of_chat_rooms = {}

#!___________________________ FUNCTION DEFINITIONS __________________________
## Example function, we need to create our own functions 
# def list_directory():
#     return os.listdir(directory)


#& FUNCTION THAT CREATES A NEW ROOM, ADDS THE CREATOR TO ROOM
def create_room(room_to_create, user): # later on will implement an "owned by:" parameter
    """Creates a new chatroom that different clients can join. Will check if a chatroom with the same name already exists."""
    # Appends the new chatroom to the list of existing chatrooms
    list_of_chat_rooms[room_to_create] = {
        'owner': user,
        'members': [], # where we will store the members of the chatroom
    }
    # Confirmation message that chatroom has been created
    print(f"Chatroom {room_to_create} has been created.\n")

    list_of_chat_rooms[room_to_create]['members'].append(user)
    # Confirmation message that chatroom owner has entered the room.
    print("BELLO BELLO BELLO BELLO WELCOME TO THE START OF YOUR CHAT HISTORY!!")
    print(f"Chatroom owner {user} has entered the room {room_to_create}.")
    return list_of_chat_rooms


#& FUNCTION THAT ADDS A USER TO A ROOM
def join_room(room_to_join, user): 
    """Will allow the user to join rooms they are intrested in."""

    list_of_chat_rooms[room_to_join]['members'].append(user)
    # Confirmation message that a user has entered the chatroom.
    
    updated_members = list_of_chat_rooms[room_to_join]['members']
    print(f"Welcome {user}! You have entered the room {room_to_join}.")

    return updated_members



#!___________________________ FUNCTION REGISTRATION ___________________________
#registering the function 
# server.register_function(list_directory)
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

