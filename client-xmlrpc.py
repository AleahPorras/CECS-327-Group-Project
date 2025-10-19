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
    print(f"[Client] Subscribed to messages in {chatroom_name}.")
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

        thread = threading.Thread(target = message_subscriber, args = (chatroom, user), daemon=True)
        thread.start()

        while True:
            print(f"({user})You: ", end = "", flush = True)
            message = input()
            if message == 'exit' or message == 'Exit':
                print("\nExiting chat...")
                break
            proxy.send_message(chatroom, user, message)
            # print("You > ", end = "", flush = True) #, end = "",flush=True)

    except KeyboardInterrupt:
        print("\nExiting chat...")

if __name__ == '__main__': 
    main()
