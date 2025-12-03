import socket, threading, json, sys, uuid, random, time

# network configuration
MY_HOST = "127.0.0.1"
BASE_PORT = 5000
MAX_PEERS = 100 # can be changed in the future
MY_PORT = None

# peer state
neighbors = set()
neighbors_lock = threading.Lock()

seen = set()
seen_lock = threading.Lock()

username = None # stores peer's username

current_chatroom = None
current_chatrooms = set()

members = {}
members_lock = threading.Lock()

subscriptions = set() # for fooding

console_lock = threading.Lock()
room_state_lock = threading.Lock()

##& ------For lamport clocks------##
timestamp = 0
lock_lamport = threading.Lock()

current_transaction_id = None
pinned_messages = {}

chat_history = [] 
history_lock = threading.Lock() 



#one global critical section for the whole node
critical_section_lock = threading.Lock()
critical_section_state = "idle"
critical_section_request_ts = None
critical_section_pending = set()
critical_section_deferred = set()

#Transaction /reservation sta
transaction_lock = threading.Lock()

# Local reservation table: station_id -> list of (start, end, username, tx_id)
reservations = {}

#empy set to keep track of transactions
transactions = {}

# Current transaction for this peer 
current_transaction_id = None

# Pinned messages
pinned_messages = {}

# room management
all_rooms = set()
rooms_lock = threading.Lock()

ready = threading.Event()
handshake_done = threading.Event() 
peer_found = threading.Event() 

# each peer keeps a log of message IDs
def new_id():
    return str(uuid.uuid4())

# open TCP socket , send message and close
def send_msg(addr, obj):
    #host and port rettreive 
    h, p = addr
    try:

        #creating the TCP socket and connectiong peers
        s = socket.socket()
        s.settimeout(2.0)
        s.connect((h, p))
        s.sendall((json.dumps(obj) + "\n").encode())
        s.close()

    #Handles errors during connection
    except (OSError, ConnectionRefusedError, TimeoutError):
       
        global neighbors, critical_section_pending, critical_section_state

        #we are assuming that the peer is dead and needs to be removed, removed the peer at the address that had the issue
        with neighbors_lock:
            neighbors.discard(addr)

        with critical_section_lock:
            
            #incase the criticle section is stock with a dead peer
            if critical_section_state == "requesting" and addr in critical_section_pending:
                
                #stating that there is a dead peer and that they must be removed from being able to vote
                with console_lock:
                    print(f"\n[System] Peer {addr} failed. Removing vote.")
                #then discarding that peer from the vote
                critical_section_pending.discard(addr)
                
                if not critical_section_pending:
                    critical_section_state = "in_cs"

                    with console_lock:
                        print("[CS] Entered CS (last voter failed).")

# connects peers to already existing peers
def network(port):
    if peer_found.is_set():
        return
    try:
        s = socket.create_connection((MY_HOST, port), timeout = 5)
        s.close()

        peer_found.set()
        
        
        with room_state_lock:
            local_room = current_chatroom
        found_time = increment_timestamp()
        msg = {
                    "type": "ping",
                    "lamport": found_time,
                    "msg_id": new_id(),
                    "addr": [MY_HOST, MY_PORT],
                    "room": local_room, # Use locked value
                    "ttl": 5,
        }
        send_msg((MY_HOST, port), msg)
        
        
        with console_lock:
            print(f"[bootstrap] connected to existing peer at {MY_HOST}:{port}")

    except (OSError, TimeoutError):
        pass
    except Exception as e:
        
        with console_lock:
            print(f"[network] unexpected error: {e}")
        pass

# first contact of a new peer to the network
def bootstrap():
    if MY_PORT == BASE_PORT:
        
        with console_lock:
            print("[bootstrap] I am the first peer, starting new network")
        return

    if MY_PORT is None:
        return

    ports = list(range(BASE_PORT, BASE_PORT + MAX_PEERS))
    random.shuffle(ports)
    threads = []

    for port in ports:
        if port == MY_PORT:
            continue
        
        t = threading.Thread(target = network, args = (port,), daemon= True)
        t.start()
        threads.append(t)
        
    # Wait for all threads to finish, don't use a racy 5-second timeout
    for t in threads:
        t.join() 
    
    # The check for peer_found is now handled reliably in the main() loop

# flood a message to all neighbors except the one you know
def forward(msg, exclude =None):
    #ttl = time to live
    ttl = msg.get("ttl", 0)
    if ttl <= 0:
        return
    msg = dict(msg)
    msg["ttl"] = ttl - 1
    with neighbors_lock:
        copy_list = list(neighbors)
    for n in copy_list:
        if exclude and n == exclude:
            continue
        send_msg(n, msg)

def handle_msg(msg, tcp_addr):

    ###& incorporates new lamport clock times##
    current_time = msg.get("lamport", 0)
    #since we are receiving a message we use the updating lamport time function (not incrememnt)
    updating_lamport_time(current_time)


    with room_state_lock:
        #sets to temp variables (so we don't have to put the whole thing in a whole lock)
        local_current_room = current_chatroom
        local_current_rooms = set(current_chatrooms) # make a copy
    
    #accessing global variables 
    global neighbors, members

    real_addr = tuple(msg.get("addr", tcp_addr))
    if real_addr != (MY_HOST, MY_PORT):
        with neighbors_lock:
            neighbors.add(real_addr)

    # drop duplicates
    message_id = msg.get("msg_id")
    with seen_lock: 
        if message_id in seen:
            return
        seen.add(message_id)
        #makes sure to clear if there are too many in the set
        if len(seen) > 100000:
            seen.pop()

    mtype = msg.get("type")

    if mtype == "cs_request":
        handle_cs_request(msg, real_addr)
        return
    
    if mtype == "cs_reply":
        handle_cs_reply(msg, real_addr)
        return
    
    if mtype == "tx_commit":
        handle_tx_commit(msg, real_addr)
        return
    
    if mtype == "tx_abort":
        handle_tx_abort(msg, real_addr)
        return

    msg_room = msg.get("room")
    msg_user = msg.get("user")

    if mtype == "ping":
        # Ping/Pong does not get forwarded, it's a direct conversation.
        if local_current_room is not None and msg_room is not None and msg_room != local_current_room:
            return
        found_time = increment_timestamp()
        send_msg(real_addr, {
            "type": "pong",
            "lamport": found_time,
            "msg_id": new_id(),
            "addr": [MY_HOST, MY_PORT],
            "room": local_current_room,
        })
        # Send member sync on ping
        with members_lock:
            if members: 
                found_time = increment_timestamp()
                members_json = {r: list(users) for r, users in members.items()}
                send_msg(real_addr, {
                    "type": "member_sync",
                    "lamport": found_time,
                    "msg_id": new_id(),
                    "addr": [MY_HOST, MY_PORT],
                    "members": members_json,
                })
                
        with rooms_lock:
            if all_rooms:
                found_time = increment_timestamp()
                send_msg(real_addr, {
                    "type": "room_announce",
                    "msg_id": new_id(),
                    "addr": [MY_HOST, MY_PORT],
                    "lamport": found_time,
                    "rooms": list(all_rooms),
                    "ttl": 3,
                })
        # Sends pinned messages on ping (so new users can view existing pinned messages)
        if pinned_messages:
            found_time = increment_timestamp()
            pins_payload = {}
            for room, (text, user, tx_id) in pinned_messages.items():
                pins_payload[room] = {
                    "text": text,
                    "user": user,
                    "tx_id": tx_id,
                }
            send_msg(real_addr, {
                "type": "pin_sync",
                "lamport": found_time,
                "msg_id": new_id(),
                "addr": [MY_HOST, MY_PORT],
                "pins": pins_payload,
            })
        # We forward the original ping 
        forward(msg, exclude=real_addr)
        return

    ## Handler functions
    if mtype == "pong":
        
        if local_current_room is None or msg_room is None or msg_room == local_current_room:
            
            with console_lock:
                print(f"\r[handshake] <Timestamp:{current_time}> connection established with {real_addr}\n> ", end = "", flush = True)
            handshake_done.set()
        return
    
    #updating members 
    if mtype == "member_sync":
        synced_members = msg.get("members",{})
        with members_lock:
            for r, user_set in synced_members.items():
                members.setdefault(r, set()).update(user_set)
        return

    if mtype == "pin_sync":
        pins = msg.get("pins", {})
        for room, pinned_message_data in pins.items():
            #text that is with the pinned message
            text = pinned_message_data.get("text")

            #who pinned the message
            user = pinned_message_data.get("user")

            #the transaction ID with the pinned message
            tx_id = pinned_message_data.get("tx_id")
            if text is None or user is None or tx_id is None:
                continue

            #pinned message for a specific room update 
            pinned_messages[room] = (text, user, tx_id)
        return

    #for getting the diffrent rooms 
    if mtype == "room_query":
        with rooms_lock:
            found_time = increment_timestamp()
            send_msg(real_addr, {
                "type": "room_response",
                "lamport": found_time,
                "msg_id": new_id(),
                "addr": [MY_HOST, MY_PORT],
                "rooms": list(all_rooms),
            })
        return
    
    #fetching rooms (used in if statement above )
    if mtype == "room_response":
        rooms = msg.get("rooms", [])
        with rooms_lock:
            all_rooms.update(rooms)
        return

    forward(msg, exclude=real_addr)

    if mtype == "room_announce":
        announced_rooms = msg.get("rooms", [])
        with rooms_lock:
            for r in announced_rooms:
                all_rooms.add(r)
        return
    
    #For when you want to send a message to all rooms
    if mtype == "flood":
        src = msg.get("user", "?")
        text = msg.get("text", "")
        
        with console_lock:
            print(f"\r[FLOOD] <Timestamp:{current_time}> {src}: {text}\n[{local_current_room}]> ", end="", flush=True)
        return

    #For when you want to join a new room
    if mtype == "join":
        with members_lock:
            members.setdefault(msg_room, set())
            if msg_user in members[msg_room]:
            
                return 
            members[msg_room].add(msg_user)
        
        if msg_room == local_current_room:
            
            with console_lock:
                print(f"\r<Timestamp:{current_time}> {msg_user} <Timestamp:{current_time}> joined {msg_room}\n> ", end = "", flush = True)
        
        with rooms_lock:
            all_rooms.add(msg_room)
        return 
    
    #For when you want to leave a room
    if mtype == "leave":
        user_was_in_room = False
        with members_lock:
            if msg_room in members and msg_user in members[msg_room]:
                members[msg_room].discard(msg_user)
                user_was_in_room = True
        
        if user_was_in_room and local_current_room == msg_room:
            
            with console_lock:
                print(f"\r<Timestamp:{current_time}> {msg_user} left {msg_room}\n> ", end = "", flush = True)
        return 

    #for when a message is being set to rooms with a specific word or phrase in their room name
    if mtype == "discoverTopic": 
        topic_name = msg.get("topic", "")
        for chatroom in local_current_rooms:
            if topic_name in " ".join(chatroom.lower().split()):
                
                with console_lock:
                    print(f"\r[{topic_name} ANNONCEMENT] <Timestamp:{current_time}> {msg_user}: {msg['text']}\n[{local_current_room}]> ", end = "", flush = True)
                break
        return

    if mtype =="focus_enter":
        if msg_room == local_current_room:
            
            with console_lock:
                print(f'\r[{msg_room}] <Timestamp:{current_time}> {msg_user} is now active here.\n[{local_current_room}]> ', end='', flush=True)
        return
    
    if mtype == "focus_leave":
        if msg_room == local_current_room:
            
            with console_lock:
                print(f"\r[{msg_room}] <Timestamp:{current_time}> {msg_user} has left the chat.\n[{local_current_room}]> ", end="", flush=True)
        return

    if msg_room is not None and msg_room != local_current_room:
        return 
    
    if mtype == "chat":
        
        # with console_lock:
        #     print(f"\r[{msg_room}] <Timestamp:{current_time}> {msg_user}: {msg['text']}\n[{local_current_room}]> ", end = "", flush = True)

        #make it easy to pass the standered message to the history 
        message_text = f"[{msg_room}] <Timestamp:{current_time}> {msg_user}: {msg['text']}"

        with history_lock:
            #takes the message the the lamport timestamp
            chat_history.append((current_time, message_text))
            #re orders the history log
            chat_history.sort(key=lambda x: x[0]) 

        with console_lock:
            #prints like normal to the terminal
            print(f"\r{message_text}\n[{local_current_room}]> ", end = "", flush = True)
        return

# read one TCP and feed all messages on it into handle_msg function
def handle_conn(conn, addr):
    with conn:
        data = conn.recv(4096)
    for line in data.splitlines():
        if not line:
            continue
        msg = json.loads(line.decode())
        handle_msg(msg, addr)

# binds to host/port listen forever act like a server
def listener():
    global MY_PORT
    s = socket.socket()

    # pick the first free port 
    for port in range(BASE_PORT, BASE_PORT + MAX_PEERS):
        try:
            s.bind((MY_HOST, port))
            MY_PORT = port
            break
        except OSError:
            continue

    s.listen(100)
    
    with console_lock:
        print(f"[listen] {MY_HOST}:{MY_PORT}")
    ready.set()

    while True:
        c, a = s.accept() # loop so peer is always reachable
        threading.Thread(target=handle_conn, args=(c, a), daemon=True).start()

#Function that will be used for gettin the list of rooms (will be printed to terminal )
def query_rooms():
    found_time = increment_timestamp()
    msg = {
        "type": "room_query",
        "lamport": found_time,
        "msg_id": new_id(),
        "addr": [MY_HOST, MY_PORT],
        "ttl": 3,
    }
    forward(msg)
    time.sleep(2)
    
    with rooms_lock:
        return list(all_rooms)
    
#used to find which room the user is currently in
def room_checker(chatroom_name):
    name = " ".join(chatroom_name.lower().split())

    with rooms_lock:
        existing_chatrooms = list(all_rooms)
    
    for room in existing_chatrooms:
        if " ".join(room.lower().split()) == name:
            return room
        
    return chatroom_name

#used to see if we already have a user with a name that is being requested by a new user
def username_check(username):
    with members_lock:
        all_users = set().union(*members.values())

        if username in all_users:
            return True
    return False

# Commands that allow a user to manage which rooms they are currently in
def commands(user_input):
    #User command to join a new room
    if user_input.startswith("d/Join "):
        #getting the room the user wanted to join
        chatroom_name = user_input[len("d/Join "):].strip()
        # join_chatroom(chatroom_name)
        if not chatroom_name:
            #when trying to use the command but not providing a room
            with console_lock:
                print("Usage: d/Join <chatroom name>")
            return True
    
        true_chatroom = room_checker(chatroom_name)
        join_chatroom(true_chatroom)
        return True
    
    #Command to swtich to a diff room when in a room
    elif user_input.startswith("d/Switch "):
        chatroom_name = user_input[len("d/Switch "):].strip()
        global current_chatroom
        
        old_room = None
        do_switch = False
        
        
        with room_state_lock:
            if chatroom_name not in current_chatrooms:
                #when a user tries to wtich to a room without joining it first 
                with console_lock:
                    print(f"You are not a member of {chatroom_name}.")
            elif current_chatroom == chatroom_name:
                #trying to switch to a room they are already in 
                with console_lock:
                    print(f"Already active in {chatroom_name}.")
            else:
                old_room = current_chatroom
                current_chatroom = chatroom_name
                do_switch = True
        
        if do_switch:
            if old_room:
                forward({
                    "type": "focus_leave",
                    "msg_id": new_id(),
                    "user": username,
                    "room": old_room,
                    "addr": [MY_HOST, MY_PORT],
                    "ttl": 5,
                    "lamport": increment_timestamp(), ##& Adds lamport time to the message output ##
                })
            

            with console_lock:
                print(f"Switched to chatroom: {chatroom_name}")

            # If room has pinned message, show after switching
            pm = pinned_messages.get(chatroom_name)
            if pm:
                text, user, tx_id = pm
                with console_lock:
                    print(f"[PINNED in {chatroom_name}] {user}: {text}")

            forward({
                "type": "focus_enter",
                "msg_id": new_id(),
                "user": username,
                "room": chatroom_name,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
                "lamport": increment_timestamp(), ##& Adds lamport time to the message output ##
            })
        return True

    #User wants to enter criticle section
    elif user_input.startswith("d/CS"):
        request_cs ()
        return True

    #User no longer wants to be in criticle section
    elif user_input.startswith("d/Done"):
        #releases the criticle section for other users 
        release_cs()
        return True

    # Pin message in current room
    elif user_input.startswith("d/Pin "):
        #sep the command from the message they want pinned
        text = user_input[len("d/Pin "):].strip()
        #trying to pin with no text provided 
        if not text:
            with console_lock:
                print("Usage: d/Pin <message text>")
            return True

        with room_state_lock:
            room = current_chatroom
        if not room:
            #trying to pin a messge when not in a room yet (not possible but just in case)
            with console_lock:
                print("You must be in a room to pin a message.")
            return True

        # Run a single-operation transaction for this pin
        #starting transaction
        begin_transaction()
        #adding the pin to a room
        add_pin_op(room, text)
        #sending transaction
        commit_transaction()
        return True

    #for when a user wants to send a message to all rooms (reach all nodes they can)
    elif user_input.startswith("d/Flood "):
        #sep command from message to be flooded 
        txt = user_input[len("d/Flood "):].strip()
        if not txt:

            with console_lock:
                print("Usage: Flood <message>")
            return True
        send_flood(txt)

        #success
        with console_lock:
            print("Global flood sent")
        return True

    #to get the list of rooms a user is in 
    elif user_input == "d/Rooms":

        with room_state_lock:
            #gets what rooms they are in 
            local_chatrooms = list(current_chatrooms)
            #which room they are currently in 
            local_active_room = current_chatroom

        #keeps track of how many members are in each
        room_counts = {}
        with members_lock:
            #going through each of the rooms the user is in 
            for chatroom in local_chatrooms:
                #how many members are in 1 room
                room_counts[chatroom] = len(members.get(chatroom, set()))

        with console_lock:
            #displying findings to user 
            print("Your active chatrooms:")
            for chatroom in local_chatrooms:
                num = room_counts[chatroom]
                print(f"    - {chatroom} : ({num} members){'  (active)' if chatroom == local_active_room else ''}")
        return True

    #when you want to send a message to a specific topic such as rooms with the work Animal
    elif user_input.startswith("d/discoverTopic "):
        #sep the command from the users topic
        topic = " ".join(user_input[len("d/discoverTopic "):].lower().split())

        #Then asks for the user to enter a message they want to send 
        with console_lock:
            txt = input("Enter your message: ")
        found_time = increment_timestamp()
        msg = {
                "type": "discoverTopic",
                "topic": topic,
                "msg_id": new_id(),
                "user": username,
                "text": txt,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
                "lamport": found_time, ##& Adds lamport time to the message output ##
            }
        forward(msg)
        return True
    
    # elif user_input.startswith("d/discoverRoom "):
    #     room = " ".join(user_input[len("d/discoverRoom "):].lower().split())

    #     with console_lock:
    #         txt = input("Enter your message: ")
    #     found_time = increment_timestamp()
    #     msg = {
    #             "type": "discoverRoom",
    #             "room": room,
    #             "msg_id": new_id(),
    #             "user": username,
    #             "text": txt,
    #             "addr": [MY_HOST, MY_PORT],
    #             "ttl": 5,
    #             "lamport": found_time,
    #         }
    #     forward(msg)
    #     return True
    
    # User wants to see the commands again 
    elif user_input.startswith("d/Help"): 

        #re print of commands
        with console_lock:
            print("\nAvailable commands:")
            print("     d/Join <chatroom>         - Joins a new chatroom")
            print("     d/Switch <chatroom>       - Switches to a different chatroom")
            print("     d/Rooms                   - Lists your current chatrooms")
            print("     d/Flood <message>         - Sends a message to everyone and every room")
            print("     d/discoverTopic <topic>   - Input topic you want to send message to, then will input a message to send")
            print("     d/Pin <message>           - Pin a message in the current room (uses a transaction)")
            print("     d/CS                      - Requests CS mode")
            print("     d/Done                    - Leaves CS mode")
            print("     d/History                 - Shows history of received messages (mostly for testing ti view ordering)")  
            print("     d/Help                    - Reprint comands\n")

        
        return True
    
    #When ou want to see the messages they recivied (making sure lamport timestamps are goopd and ordering is correct)
    elif user_input == "d/History":
        with history_lock:
           #getting the history  
            history_copy = list(chat_history)
            
        with console_lock:
            #printing out each message with their timestamp  (also displays the room)
            print("\n Chat History (Lamport Time)")
            for timestamp, line in history_copy:
                print(f' - {line}')
           
        return True
    

    return False

#joining a new room
def join_chatroom(new_chatroom):
    global current_chatroom

    send_join_msg = False
    with members_lock:
        members.setdefault(new_chatroom, set())
        #if user is not in the room yet
        if username not in members[new_chatroom]:
            #adds them to the room
            members[new_chatroom].add(username)
            send_join_msg = True
        else:
            #so user can't join a group they are already in (join message remains false )
            with console_lock:
                print(f"You are listed as a member of {new_chatroom}.")


    with room_state_lock:
        #adding this chat room to the users list
        current_chatrooms.add(new_chatroom)
        #making them currently active in the room they joined (automatically puts them in that room when they join )
        current_chatroom = new_chatroom

    with rooms_lock:
        all_rooms.add(new_chatroom)

    #message that will be sent when someone joins a new room (sends to the members of that room that they joined to let them know someone else is now there )
    if send_join_msg:
        join_time = increment_timestamp()
        join_msg = {
            "type": "join",
            "msg_id": new_id(),
            "user": username,
            "room": new_chatroom,
            "addr": [MY_HOST, MY_PORT],
            "ttl": 5,
            "lamport": join_time, ##& Adds lamport time to the message output ##
        }
        #forwarding
        forward(join_msg)

    focus_time = increment_timestamp()
    forward({
    "type": "focus_enter",
    "msg_id": new_id(),
    "user": username,
    "room": new_chatroom,
    "addr": [MY_HOST, MY_PORT],
    "ttl": 5,
    "lamport": focus_time, ##& Adds lamport time to the message output ##
})

    #for displaying the pinned message (if a chat has one)
    pinned_message = pinned_messages.get(new_chatroom)
    if pinned_message: 
        text, user, tx_id = pinned_message
        with console_lock:
            print(f"[Pinned in {new_chatroom}] {user}: {text}")

#function for 
def send_flood(text):
    msg ={
        "type": "flood",
        "msg_id": new_id(),
        "user": username,
        "text": text,
        "addr": [MY_HOST, MY_PORT],
        "ttl": 5,
        "lamport": increment_timestamp(),
        
    }
    forward(msg)

    with console_lock:
        print("send global flood")

# def lamport_timestamp_lookup():
#     with lock_lamport:
#         return timestamp
    
##& gets logical clock value for sent messages ##
def increment_timestamp():
    #getting the timestamp
    global timestamp
    with lock_lamport:
        #increment the timestamp by 1
        timestamp += 1
        return timestamp

##& Updates the current clock time ##
def updating_lamport_time(current_time):
    #getting the timestamp (global)
    global timestamp
    with lock_lamport:
        #comparing the global timestamp to the one attached to the process that send the message sees which oe is larger, incrmeents by 1
        timestamp = max(timestamp, current_time) + 1 # increments the max lamport time each time a new message is sent
        return timestamp

def request_cs():
    global critical_section_state, critical_section_request_ts, critical_section_pending

    with critical_section_lock:
        if critical_section_state =="in_cs":
            with console_lock:
                print("You are already in CS mode.")
            return
        if critical_section_state =="requesting":
            with console_lock:
                print("[CS] You are already requesting CS mode.")
                return
        critical_section_state = "requesting"
        critical_section_request_ts = increment_timestamp()
        with neighbors_lock:
            critical_section_pending = set(neighbors)
    if not critical_section_pending:
        with critical_section_lock:
            critical_section_state = "in_cs"
        with console_lock:
            print("[CS] Entered CS.")
        return
    msg = {
        "type": "cs_request",
        "msg_id": new_id(),
        "lamport": critical_section_request_ts,
        "addr": [MY_HOST, MY_PORT],
        "ttl": 5,
    }
    forward(msg)

    with console_lock:
        print(f"[CS] Requesting CS at Lamport {critical_section_request_ts}")

def release_cs():
    global critical_section_state, critical_section_request_ts, critical_section_pending

    with critical_section_lock:
        if critical_section_state != "in_cs":
            with console_lock:
                print("[CS] You are not in CS mode.")
            return

        critical_section_state = "idle"
        critical_section_request_ts = None
        to_reply = list(critical_section_deferred)
        critical_section_deferred.clear()

    for addr in to_reply:
        send_cs_reply(addr)
    with console_lock:
        print("[CS] Left CS and send deferred messages.")

def handle_cs_request(msg, real_addr):
    # reply immediately if in idle, defer if in_cs
    # if both requesting, compare priority
    global critical_section_state, critical_section_request_ts

    req_ts = msg.get("lamport", 0)
    requester = tuple(msg.get("addr", real_addr))

    with critical_section_lock:
        if critical_section_state == "idle":
            send_cs_reply(requester)
            return
        if critical_section_state == "in_cs":
            critical_section_deferred.add(requester)
            return

    my_ts = critical_section_request_ts
    my_id = (MY_HOST, MY_PORT)
    their_id = requester

    my_priority = (my_ts if my_ts is not None else float("inf"), my_id)
    their_priority = (req_ts, their_id)

    if their_priority < my_priority:
        send_cs_reply(requester)
    else:
        critical_section_deferred.add(requester)

def send_cs_reply(addr):
    lam = increment_timestamp()
    msg = {
        "type": "cs_reply",
        "msg_id": new_id(),
        "lamport": lam,
        "addr": [MY_HOST, MY_PORT],
        "ttl": 5,
    }
    send_msg(addr, msg)

def handle_cs_reply(msg, real_addr):
    global critical_section_state, critical_section_pending

    sender = real_addr
    with critical_section_lock:
        if critical_section_state != "requesting":
            return
        critical_section_pending.discard(sender)
        if not critical_section_pending:
            critical_section_state = "in_cs"
            with console_lock:
                print ("[CS] All replies received. Entering CS mode.")

def with_global_cs(fn):
    global critical_section_state, critical_section_pending
  
   
    request_cs()

    # Busywait until we are in CS mode
    while True:
        with critical_section_lock:
            if critical_section_state == "in_cs":
                break
            current_pending = list(critical_section_pending)
        # time.sleep(0.05)
        for node in current_pending:
            try:
                
                s = socket.socket()
                s.settimeout(1.0) 
                s.connect(node)
                s.close()
            except (OSError, ConnectionRefusedError, TimeoutError):
               
                with neighbors_lock:
                    neighbors.discard(node)
                with critical_section_lock:
                     if node in critical_section_pending:
                         print(f"[System] Node {node} detected dead during wait.")
                         critical_section_pending.discard(node)
                        
                         if not critical_section_pending:
                             critical_section_state = "in_cs"

    time.sleep(1.0) 
    try:
        fn()
    finally:
        release_cs()


def begin_transaction():
    #Start a new local transaction for the current user
    global current_transaction_id

    with transaction_lock:
        if current_transaction_id is not None:
            with console_lock:
                print(f"[TX] A transaction is already active: {current_transaction_id}")
            return

        tx_id = new_id()
        current_transaction_id = tx_id
        transactions[tx_id] = {
            "user": username,
            "ops": [],
            "status": "active",
        }

    with console_lock:
        print(f"[TX] Began transaction {tx_id} for user {username}")


def add_reservation_op(station_id, start, end):
    #Add a reservation operation to the current transaction
    global current_transaction_id
    with transaction_lock:
        if current_transaction_id is None:
            with console_lock:
                print("[TX] No active transaction. Use tx/begin first.")
            return
        tx = transactions.get(current_transaction_id)
        if not tx or tx["status"] != "active":
            with console_lock:
                print(f"[TX] Cannot add operations, transaction is {tx['status'] if tx else 'unknown'}")
            return
        tx["ops"].append(("reserve", station_id, start, end))

    with console_lock:
        print(f"[TX] Added reserve({station_id}, {start}, {end}) to {current_transaction_id}")

def add_pin_op(room_name, text):
    #Add a pin message operation to the current transaction
    global current_transaction_id
    with transaction_lock:
        if current_transaction_id is None:
            with console_lock:
                print("[TX] No active transaction. Use tx/begin first.")
            return
        tx = transactions.get(current_transaction_id)
        if not tx or tx["status"] != "active":
            with console_lock:
                print(f"[TX] Cannot add operations, transaction is {tx['status'] if tx else 'unknown'}")
            return
        tx["ops"].append(("pin", room_name, text))

    with console_lock:
        print(f"[TX] Added pin({room_name}, {text!r}) to {current_transaction_id}")

def times_overlap(start1, end1, start2, end2):
   
    return not (end1 <= start2 or end2 <= start1)


def validate_transaction(tx_id, tx):

    ops = tx["ops"]

    for op in ops:
        if not op:
            continue
        kind = op[0]
       
        if kind == "reserve":
            _, station_id, start, end = op
            existing = reservations.get(station_id, [])
            for (s, e, u, other_tx) in existing:
                if times_overlap(start, end, s, e) and other_tx != tx_id:
                    return False

        
        elif kind == "pin":
            _, room_name, text = op
            if room_name in pinned_messages:
                existing_text, existing_user, existing_tx_id = pinned_messages[room_name]
                if existing_tx_id != tx_id:
                     return False


        # # Now we know it's a reserve op: ("reserve", station_id, start, end)
        # _, station_id, start, end = op
        # existing = reservations.get(station_id, [])
        # for (s, e, u, other_tx) in existing:
        #     # If time windows overlap and it's not the same transaction, it's a conflict
        #     if times_overlap(start, end, s, e) and other_tx != tx_id:
        #         return False

    return True

def apply_transaction(tx_id, tx):
    #Apply all operations in a committed transaction 
    ops = tx["ops"]
    user = tx["user"]
    for op in ops:
        kind = op[0]

        if kind == "reserve":
            _, station_id, start, end = op
            reservations.setdefault(station_id, []).append(
                (start, end, user, tx_id)
            )

        elif kind == "pin":
            _, room_name, text = op
            pinned_messages[room_name] = (text, user, tx_id)

            # If this is our current room, show the pinned message nicely
            with room_state_lock:
                local_room = current_chatroom
            if room_name == local_room:
                with console_lock:
                    print(
                        f"\r[PINNED in {room_name}] {user}: {text}\n[{local_room}]> ",
                        end="",
                        flush=True,
                    )

def broadcast_tx_commit(tx_id, tx):
    # Broadcast a commit message so all peers apply the transaction
    found_time = increment_timestamp()
    msg = {
        "type": "tx_commit",
        "msg_id": new_id(),
        "lamport": found_time,
        "addr": [MY_HOST, MY_PORT],
        "tx_id": tx_id,
        "user": tx["user"],
        "ops": tx["ops"],
        "ttl": 5,
    }
    forward(msg)


def broadcast_tx_abort(tx_id, tx):
    #Broadcast an abort message so all peers roll back the transaction
    found_time = increment_timestamp()
    msg = {
        "type": "tx_abort",
        "msg_id": new_id(),
        "lamport": found_time,
        "addr": [MY_HOST, MY_PORT],
        "tx_id": tx_id,
        "user": tx["user"],
        "ttl": 5,
    }
    forward(msg)


def commit_transaction():
    #Commit the current transaction using the global CS for atomicity
    global current_transaction_id
    with transaction_lock:
        if current_transaction_id is None:
            with console_lock:
                print("[TX] No active transaction to commit.")
            return
        tx_id = current_transaction_id

    def do_commit():
        # This runs inside the distributed critical section
        with transaction_lock:
            tx = transactions.get(tx_id)
            if not tx or tx["status"] != "active":
                with console_lock:
                    print(f"[TX] Cannot commit, transaction {tx_id} not active.")
                return

            # Validate operations against current reservations
            if not validate_transaction(tx_id, tx):
                tx["status"] = "aborted"
                broadcast_tx_abort(tx_id, tx)
                with console_lock:
                    print(f"[TX] Transaction {tx_id} aborted due to conflicts.")
                return

            # Apply changes locally
            apply_transaction(tx_id, tx)
            tx["status"] = "committed"

        # Notify everyone to apply the same transaction
        broadcast_tx_commit(tx_id, tx)

        with console_lock:
            print(f"[TX] Transaction {tx_id} committed.")

    with_global_cs(do_commit)

    # Clear current_tx_id after commit/abort path
    with transaction_lock:
        current_transaction_id = None


def abort_transaction():
    #Abort the current transaction explicitly
    global current_transaction_id
    with transaction_lock:
        if current_transaction_id is None:
            with console_lock:
                print("[TX] No active transaction to abort.")
            return
        tx_id = current_transaction_id
        tx = transactions.get(tx_id)
        if not tx or tx["status"] != "active":
            with console_lock:
                print(f"[TX] Cannot abort, transaction {tx_id} not active.")
            return
        tx["status"] = "aborted"

    broadcast_tx_abort(tx_id, tx)

    with console_lock:
        print(f"[TX] Transaction {tx_id} aborted by user.")

    with transaction_lock:
        current_transaction_id = None


def handle_tx_commit(msg, real_addr):
    #Handle a tx_commit message from another peer
    tx_id = msg.get("tx_id")
    user = msg.get("user")
    ops = msg.get("ops", [])

    with transaction_lock:
        # Create or update local record
        tx = transactions.setdefault(tx_id, {
            "user": user,
            "ops": ops,
            "status": "committed",
        })
        tx["ops"] = ops
        tx["status"] = "committed"
        apply_transaction(tx_id, tx)

    
    should_print = False
    with room_state_lock:
        my_room = current_chatroom
    
  
    if user == username:
        should_print = True
    else:
        for op in ops:
           
            if op[0] == "pin" and op[1] == my_room:
                should_print = True
                break
            

    if should_print:
        with console_lock:
            print(f"\r[TX] Commit received for {tx_id} (user={user}). Data updated.\n[{my_room}]> ", end="", flush=True)


def handle_tx_abort(msg, real_addr):
    #Handle a tx_abort message from another peer
    tx_id = msg.get("tx_id")
    user = msg.get("user")

    with transaction_lock:
        tx = transactions.setdefault(tx_id, {
            "user": user,
            "ops": [],
            "status": "aborted",
        })
        tx["status"] = "aborted"
        # Rollback: remove any reservations tagged with this tx_id
        for station_id, lst in list(reservations.items()):
            new_lst = [entry for entry in lst if entry[3] != tx_id]
            reservations[station_id] = new_lst

    with console_lock:
        print(f"\r[TX] Abort received for {tx_id} (user={user}). Any tentative changes rolled back.\n> ", end="", flush=True)


def main():
    global username, current_chatroom

    threading.Thread(target=listener, daemon=True).start()
    ready.wait()

    with console_lock:
        #cuteeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
        print("")
        print("████████╗██╗░░██╗██╗░██████╗░█████╗░░█████╗░██████╗░██████╗░")
        print("╚══██╔══╝██║░░██║██║██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗")
        print("░░░██║░░░███████║██║╚█████╗░██║░░╚═╝██║░░██║██████╔╝██║░░██║")
        print("░░░██║░░░██╔══██║██║░╚═══██╗██║░░██╗██║░░██║██╔══██╗██║░░██║")
        print("░░░██║░░░██║░░██║██║██████╔╝╚█████╔╝╚█████╔╝██║░░██║██████╔╝")
        print("░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═════╝░░╚════╝░░╚════╝░╚═╝░░╚═╝╚═════╝░ ©")
        print("")
        #asks for username, does a random one if one isn't inputed 
        username = input("Enter your username: ").strip() or f"user{uuid.uuid4().hex[:4]}"
    
    if MY_PORT != BASE_PORT:

        with console_lock:
            print("[bootstrap] Waiting for a handshake...")
        while not handshake_done.is_set():
            peer_found.clear()

            bootstrap()# uses the fixed t.join() 

            if peer_found.is_set():

                with console_lock:
                    print(f"[bootstrap] Peer found. Waiting for handshake response.")
                if handshake_done.wait(timeout=5):

                    with console_lock:
                        print("[bootstrap] Handshake successful!")
                    break
                else:

                    with console_lock:
                        print("[bootstrap] Handshake timed out. Retrying.")
            else:

                with console_lock:
                    print("[bootstrap] No peers found, trying again.")
                time.sleep(5)
    
    #When a user name is already taken, makes sure the user doesnt continute without pickign a new 
    while username_check(username):
        with console_lock:
            print(f"[SYSTEM] Username '{username}' is already taken. Please choose another.")
            username = input("Enter a new username: ").strip()
            
            # In case the user just hits Enter, assign a new random name
            if not username:
                username = f"user{uuid.uuid4().hex[:4]}"
    
    with console_lock:
        # print("")
        # print("████████╗██╗░░██╗██╗░██████╗░█████╗░░█████╗░██████╗░██████╗░")
        # print("╚══██╔══╝██║░░██║██║██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗")
        # print("░░░██║░░░███████║██║╚█████╗░██║░░╚═╝██║░░██║██████╔╝██║░░██║")
        # print("░░░██║░░░██╔══██║██║░╚═══██╗██║░░██╗██║░░██║██╔══██╗██║░░██║")
        # print("░░░██║░░░██║░░██║██║██████╔╝╚█████╔╝╚█████╔╝██║░░██║██████╔╝")
        # print("░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═════╝░░╚════╝░░╚════╝░╚═╝░░╚═╝╚═════╝░ ©")
        print("\nQuerying network for available rooms...")
    #getting rooms that currently have members
    available_rooms = query_rooms()
    
    #prints rooms if there are some 
    if available_rooms:
        with console_lock:
            print("\nAvailable rooms:")
        for idx, r in enumerate(available_rooms, 1):
            with members_lock:
                member_count = len(members.get(r, set()))
            print(f"  {idx}. {r} ({member_count} members)")
    #me4asn there are currently no rooms that the user can join, but they can create a new one 
    else:
        with console_lock:
            print("No rooms found. Create one!")
    
    #user can enter what room they want to join or what room they want to create (if room doens't exist it creates it )
    room = input("\nEnter room name: ").strip() or "lobby"
    #incase user makes a spelling mistake they don't have to rerun the program
    answer = input(f"Is this the room you want to join? Check spellling. (y/n): ")
    #the reenter in case the user wants to be in a diff room they originall inputted 
    while answer.lower()== 'n' or answer.lower() == 'no': 
        room = input("\nEnter room name: ").strip() or "lobby"
        answer = input(f"Is this the room you want to join? Check spellling. (y/n): ")

    
    true_chatroom = room_checker(room)
    #join the room they want to enter 
    join_chatroom(true_chatroom)

    #print the list of commands they can use
    with console_lock:
        print("\nAvailable commands:")
        print("     d/Join <chatroom>         - Joins a new chatroom")
        print("     d/Switch <chatroom>       - Switches to a different chatroom")
        print("     d/Rooms                   - Lists your current chatrooms")
        print("     d/Flood <message>         - Sends a message to everyone and every room")
        print("     d/discoverTopic <topic>   - Input topic you want to send message to, then will input a message to send")
        print("     d/CS                      - Requests CS mode")
        print("     d/Done                    - Leaves CS mode")
        print("     d/Pin <message>           - Pin a message in the current room (uses a transaction)")
        print("     d/History                 - Shows history of received messages (mostly for testing ti view ordering)")  
        print("     d/Help                    - Reprint comands\n")
        


    while True:
        try:
            #the room they want to write to 
            with room_state_lock:
                    prompt_room = current_chatroom
                
            # Take input WITHOUT holding the console lock
            text = input(f"[{prompt_room}]> ").strip()

            if not text:
                continue
            
            #means the user wants to leave 
            if text.lower() in ("exit", "quit"):

                with room_state_lock:
                    chatrooms_copy = set(current_chatrooms)
                
                #sends a leave message to every room they were in, and "leave means they will be removed from the memeber list 
                for room in chatrooms_copy:
                    found_time = increment_timestamp()
                    leave_msg = {
                        "type": "leave",
                        "msg_id": new_id(),
                        "user": username,
                        "room": room,
                        "addr": [MY_HOST, MY_PORT],
                        "ttl": 5,
                        "lamport": found_time, ##& Adds lamport time to the message output ##
                    }
                    forward(leave_msg)

                #prints to the user that they are being exitied 
                with console_lock:
                    print("exiting...")
                break

            # Handle room management commands
            if commands(text):
                continue

            # Send chat message to active room
            with room_state_lock:
                local_room = current_chatroom
            
            found_time = increment_timestamp()
            msg = {
                "type": "chat",
                "msg_id": new_id(),
                "user": username,
                "room": local_room,
                "text": text,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
                "lamport": found_time, ##& Adds lamport time to the message output ##
            }
            forward(msg)

        #when user does ctrl c on the keyboared to forcefully exit the chat 
        except KeyboardInterrupt:
            
            with room_state_lock:
                local_room = current_chatroom
            found_time = increment_timestamp()
            leave_msg = {
                "type": "leave",
                "msg_id": new_id(),
                "user": username,
                "room": local_room,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
                "lamport": found_time, ##& Adds lamport time to the message output ##
            }
            forward(leave_msg)
            
            with console_lock:
                print("\nKeyboard Interrupt detected.\nUser forcefully exited program.")
            break
            
if __name__ == "__main__":
    main()
