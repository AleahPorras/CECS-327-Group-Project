import  xmlrpc.client 
import zmq
import json
import threading
import sys

def message_subscriber(chatroom_name, user):
    BROKER_PUB = "tcp://127.0.0.1:5556" # connects to the broker
    TOPIC = f"room/{chatroom_name}" # subscribes to a topic/prefix

    ctx = zmq.Context.instance() # get zmq context
    sub = ctx.socket(zmq.SUB)   # create a SUB socket
    sub.connect(BROKER_PUB)
    sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC) # install a topic/prefix filter
    print(f"[Client] Subscribed to messages in {chatroom_name}.")
    # prompts user for message input
    print("You: ", end ="", flush=True)

    while True:
        try:
            # Receives messages from the broker
            broker_topic, broker_payload = sub.recv_multipart()
            topic = broker_topic.decode("utf-8")
            payload = json.loads(broker_payload.decode("utf-8"))

            # Ensures that the user's messages don't echo back to them
            if payload.get("user") != user:
                print(f"\n{payload['user']}: {payload['text']}\nYou: ", end ="",flush=True)

        except (KeyboardInterrupt, zmq.ZMQError):
            break

#----------------------functions ----------------------
def get_room_to_join():
    room_to_join = input("Enter the name of the room you would like to join: ")
    # Checks if the user provided a name for the room
    while room_to_join == None: 
        print("No name provided, try again.")
        room_to_join = input("Enter the name of the room you would like to join: ")
        
    return room_to_join

def get_room_to_create():
    room_to_create = input("Enter the name of the room you want to create: ") 
    # Checks if the user provided a name for the room
    while room_to_create == None: 
        print("No name provided, try again.")
        room_to_create = input("Enter the name of the room you would like to join: ")
        
    return room_to_create

def main():

    #acessing the server
    proxy = xmlrpc.client.ServerProxy('http://localhost:3000')

    try:
        user = input("What is your username?: ")

        chatroom = None
        while not chatroom:
            action = input("Would you like to join or create a room? (join/create): ")
            current_rooms = proxy.all_rooms()
            if action == "create" or action == "Create":
                chatroom_name = get_room_to_create()
                if proxy.create_room(chatroom_name, user):
                    print(f"Creating chatroom {chatroom_name}...\n")
                    chatroom = chatroom_name
                else:
                    print(f"Chatroom {chatroom_name} exists, join it instead.\n")
            
            elif action == "join" or action == "Join":
                print(f"Available Chatrooms:\n{current_rooms}")
                chatroom_name = get_room_to_join()
                if chatroom_name in current_rooms:
                    chatroom = chatroom_name
                else:
                    print(f"Chatroom {chatroom_name} does not exist.\n")
            else:
                print("You have not entered a valued response, please run again. ")
                print("Hint: You must have it printed exactly, either join or create")

        proxy.join_room(chatroom, user)

        thread = threading.Thread(target = message_subscriber, args = (chatroom, user))
        thread.start()

        while True:
            message = input()
            if message == 'exit' or message == 'Exit':
                print("\nExiting chat...")
                message = f"{user} has left the chat"
                proxy.send_message(chatroom, user, message)
                # proxy.exit_message(user)
                sys.exit()
            proxy.send_message(chatroom, user, message)
            print("You: ", end = "",flush=True)

    except KeyboardInterrupt:
        print("\nExiting chat...")
        

if __name__ == '__main__': 
    main()
#     ##EXAMPLE CALLING
#     #Calling the remote function and printing the list (place holder function)
#     ## We will call our functions like this 
#     # print(proxy.list_directory())

#     user = input("What is your username?: ")
#     action = input("Would you like to join or create a room? (join/create): ")
#     #---------------------------joining a room------------------------------
#     if action == "join" or action == "Join":
#         room = get_room_to_join()

#         #Calls the function from the server
#         current_rooms = proxy.all_rooms()
        
#         #Error handling for when a user tries to access a room that doesnt exist 
#         # * Will ask the user if they want to create the room with that name 
#         #   - Then creates the room by calling the function from the client 
#         # * Will ask if the user would rather put in a new name in case they put in the wrong name 
#         #   by mistake 
#         while room not in current_rooms: 
#             answer = input("This room does not exist, would you like to create it? yes/no: ")
#             if answer == "Yes" or answer == 'yes': 
                
#                 print("Creating the room...\n")
#                 output = proxy.create_room(room, user)
#                 print(f'List of all current rooms and members: {output}\n')
#                 print("Welcome to your new room!")
                
#             elif answer == "No" or answer == 'no':
#                 room = get_room_to_join()
#                 current_members = proxy.current_members(room)
            
#             # repeats if the user puts in a response that isn't correct 
#             else: 
#                 print("Not a correct response try again... ")
#             current_rooms = proxy.all_rooms()
            
#         # Carries out for all attmepts 
#         print("\n Joining the room...\n")

#         # fetching the current list of members 
#         current_members = proxy.current_members(room)

#         # adding the user to the room
#         output = proxy.join_room(room, user)
#         print(f"List of all current members: {current_members}\n")

#         # verification for the user that they have been added
#         print(f"{user} you have joined {room}\n")

#         # getting the current list of users in the room
#         current_members = proxy.current_members(room)

#         #returns to terminal to make sure that the list has changed from before
#         print(f"List of all current members: {current_members}\n")
        
    
#     #-----------------------------creating a room-------------------------------- 
#     elif action == "create" or action == "Create":

#         # calling client function that asks the user for a room they would want to create
#         room = get_room_to_create()

#         # gets the state of all rooms before new room is added
#         rooms_before = proxy.all_rooms()
#         print(f'Current list before adding: {rooms_before}\n')

#         print("Creating the room...\n")
        
#         # creates a new room and makes them thw owner 
#         output = proxy.create_room(room, user)
#         # adds the owner to the list of members
#         proxy.join_room(room, user)
#         # gets the updated list of members in the room
#         current_rooms =  proxy.all_rooms()

#         #prints out the list of members
#         print(f'List of all current rooms and members: {current_rooms}\n')

#     else: 
#         print("You have not entered a valued response, please run again. ")
#         print("Hint: You must have it printed exactly, either join or create")

    

