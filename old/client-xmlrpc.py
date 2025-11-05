import xmlrpc.client 
import zmq
import json
import threading

def message_subscriber(chatroom_name, user):
    BROKER_PUB = "tcp://127.0.0.1:5556" # connects to the broker
    TOPIC = f"room/{chatroom_name}" # subscribes to a topic/prefix

    ctx = zmq.Context.instance() # get zmq context
    sub = ctx.socket(zmq.SUB)   # create a SUB socket
    sub.connect(BROKER_PUB)
    sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC) # install a topic/prefix filter
    # print("You : ", end ="", flush=True)

    while True:
        try:
            # Receives messages from the broker
            broker_topic, broker_payload = sub.recv_multipart()
            topic = broker_topic.decode("utf-8")
            payload = json.loads(broker_payload.decode("utf-8"))

            # Ensures that the user's messages don't echo back to them
            if payload.get("user") != user:
                print(f"\r{payload['user']}: {payload['text']}")
                print(f"({user})You: ", end ="",flush=True)
                # print("You > ", end ="", flush=True)

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
        # gets username
        user = input("What is your username?: ")

        # empty value used for storing desired chatroom
        chatroom = None
        while not chatroom:
            action = input("Would you like to join or create a room? (join/create): ")
            # rpc call to list all available rooms
            current_rooms = proxy.all_rooms()
            if action == "create" or action == "Create":
                chatroom_name = get_room_to_create()
                # checks if chatroom with same name already exists
                if proxy.create_room(chatroom_name, user):
                    print(f"Creating chatroom {chatroom_name}...\n")
                    # assigns current chatroom name to empty value
                    chatroom = chatroom_name
                else:
                    print(f"Chatroom {chatroom_name} exists, join it instead.\n")
            
            elif action == "join" or action == "Join":
                # displays all available chatrooms and their members
                print(f"Available Chatrooms:")
                for room in current_rooms:
                    print(room)
                    print(proxy.current_members(room))
                # calls function to get the room name
                chatroom_name = get_room_to_join()
                if chatroom_name in current_rooms: # verifies if chatroom name exists
                    chatroom = chatroom_name
                else:
                    print(f"Chatroom {chatroom_name} does not exist.\n")
            else:
                print("You have not entered a valued response, please run again. ")
                print("Hint: You must have it printed exactly, either join or create")

        # calls rpc function to let a user join the specific chatroom
        proxy.join_room(chatroom, user)

        thread = threading.Thread(target = message_subscriber, args = (chatroom, user), daemon=True)
        thread.start()

        print(f"[Client] Subscribed to messages in {chatroom_name}.")

        while True:
            # prompts user to enter first message
            print(f"({user})You: ", end = "", flush = True)
            message = input()
            if message == 'exit' or message == 'Exit':
                print("\nExiting chat...")
                proxy.remove_user(chatroom, user) # calls rpc function to remove user from chatroom
                exit_message = f"{user} exited the chatroom."
                proxy.send_message(chatroom, "[ThisCordBot]", exit_message) # confirmation message sent to other clients inside same chatroom
                break
            proxy.send_message(chatroom, user, message) # rpc function that sends regular messages to other clients

    except KeyboardInterrupt:
        print("\nExiting chat...")
        proxy.remove_user(chatroom, user)

if __name__ == '__main__': 
    main()
