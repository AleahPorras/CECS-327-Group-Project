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

# room management
all_rooms = set()
rooms_lock = threading.Lock()

ready = threading.Event()
handshake_done = threading.Event() 
peer_found = threading.Event() 

# each peer keeps a "seen" of message IDs
def new_id():
    return str(uuid.uuid4())

# open TCP socket , send message and close
def send_msg(addr, obj):
    h, p = addr
    try:
        s = socket.socket()
        s.connect((h, p))
        s.sendall((json.dumps(obj) + "\n").encode())
        s.close()
    except OSError:
        pass

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

    # ##& incorporates new lamport clock times##
    current_time = msg.get("lamport", 0)
    updating_lamport_time(current_time)

    with room_state_lock:
        local_current_room = current_chatroom
        local_current_rooms = set(current_chatrooms) # make a copy
    
    global neighbors, members

    real_addr = tuple(msg.get("addr", tcp_addr))
    if real_addr != (MY_HOST, MY_PORT):
        with neighbors_lock:
            neighbors.add(real_addr)

    # drop duplicates
    mid = msg.get("msg_id")
    with seen_lock: 
        if mid in seen:
            return
        seen.add(mid)

    mtype    = msg.get("type")
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
        # We forward the *original* ping to propagate it
        forward(msg, exclude=real_addr)
        return

    ## Handler functions
    if mtype == "pong":
        # Pong is also a direct reply, no forward.
        if local_current_room is None or msg_room is None or msg_room == local_current_room:
            
            with console_lock:
                print(f"\r[handshake] <Timestamp:{current_time}> connection established with {real_addr}\n> ", end = "", flush = True)
            handshake_done.set()
        return
    
    # These types are also not forwarded
    if mtype == "member_sync":
        synced_members = msg.get("members",{})
        with members_lock:
            for r, user_set in synced_members.items():
                members.setdefault(r, set()).update(user_set)
        return

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
    
    if mtype == "flood":
        src = msg.get("user", "?")
        text = msg.get("text", "")
        
        with console_lock:
            print(f"\r[FLOOD] <Timestamp:{current_time}> {src}: {text}\n[{local_current_room}]> ", end="", flush=True)
        return

    if mtype == "join":
        with members_lock:
            members.setdefault(msg_room, set())
            if msg_user in members[msg_room]:
                # We already know, but we must *not* send name_taken
                # because this message might be for another peer.
                # Just exit silently.
                return 
            members[msg_room].add(msg_user)
        
        if msg_room == local_current_room:
            
            with console_lock:
                print(f"\r<Timestamp:{current_time}> {msg_user} <Timestamp:{current_time}> joined {msg_room}\n> ", end = "", flush = True)
        
        with rooms_lock:
            all_rooms.add(msg_room)
        return 

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
        return # Not for our active room, and we've already forwarded it.
    
    if mtype == "chat":
        
        with console_lock:
            print(f"\r[{msg_room}] <Timestamp:{current_time}> {msg_user}: {msg['text']}\n[{local_current_room}]> ", end = "", flush = True)
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

    # pick the first free port starting at BASE_PORT
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
    
def room_checker(chatroom_name):

    name = " ".join(chatroom_name.lower().split())

    with rooms_lock:
        existing_chatrooms = list(all_rooms)
    
    for room in existing_chatrooms:
        if " ".join(room.lower().split()) == name:
            return room
        
    return chatroom_name

def username_check(username):
    with members_lock:
        all_users = set().union(*members.values())

        if username in all_users:
            return True
    return False

# Commands that allow a user to manage which rooms they are currently in
def commands(user_input):
    if user_input.startswith("d/Join "):
        chatroom_name = user_input[len("d/Join "):].strip()
        # join_chatroom(chatroom_name)
        if not chatroom_name:
            with console_lock:
                print("Usage: d/Join <chatroom name>")
            return True
    
        true_chatroom = room_checker(chatroom_name)
        join_chatroom(true_chatroom)
        return True
    
    elif user_input.startswith("d/Switch "):
        chatroom_name = user_input[len("d/Switch "):].strip()
        global current_chatroom
        
        old_room = None
        do_switch = False
        
        
        with room_state_lock:
            if chatroom_name not in current_chatrooms:

                with console_lock:
                    print(f"You are not a member of {chatroom_name}.")
            elif current_chatroom == chatroom_name:

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


    elif user_input.startswith("d/Flood "):
        txt = user_input[len("d/Flood "):].strip()
        if not txt:

            with console_lock:
                print("Usage: Flood <message>")
            return True
        send_flood(txt)

        with console_lock:
            print("Global flood sent")
        return True

    elif user_input == "d/Rooms":

        with room_state_lock:
            local_chatrooms = list(current_chatrooms)
            local_active_room = current_chatroom

        room_counts = {}
        with members_lock:
            for chatroom in local_chatrooms:
                room_counts[chatroom] = len(members.get(chatroom, set()))

        with console_lock:
            print("Your active chatrooms:")
            for chatroom in local_chatrooms:
                num = room_counts[chatroom]
                print(f"    - {chatroom} : ({num} members){'  (active)' if chatroom == local_active_room else ''}")
        return True

    elif user_input.startswith("d/discoverTopic "):
        topic = " ".join(user_input[len("d/discoverTopic "):].lower().split())

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
    
    elif user_input.startswith("d/discoverRoom "):
        room = " ".join(user_input[len("d/discoverRoom "):].lower().split())

        with console_lock:
            txt = input("Enter your message: ")
        found_time = increment_timestamp()
        msg = {
                "type": "discoverRoom",
                "room": room,
                "msg_id": new_id(),
                "user": username,
                "text": txt,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
                "lamport": found_time,
            }
        forward(msg)
        return True
    
    elif user_input.startswith("d/help"): 

        with console_lock:
            print("\nAvailable commands:")
            print("     d/Join <chatroom>         - Joins a new chatroom")
            print("     d/Switch <chatroom>       - Switches to a different chatroom")
            print("     d/Rooms                   - Lists your current chatrooms")
            print("     d/Flood <message>         - Sends a message to everyone and every room")
            print("     d/discoverTopic <topic>   - Input topic you want to send message to, then will input a message to send")
            print("     d/help                  - Reprint comands\n")
        return True
    

    return False

def join_chatroom(new_chatroom):
    global current_chatroom

    send_join_msg = False
    with members_lock:
        members.setdefault(new_chatroom, set())
        if username not in members[new_chatroom]:
            members[new_chatroom].add(username)
            send_join_msg = True
        else:

            with console_lock:
                print(f"You are listed as a member of {new_chatroom}.")


    with room_state_lock:
        current_chatrooms.add(new_chatroom)
        current_chatroom = new_chatroom

    with rooms_lock:
        all_rooms.add(new_chatroom)

    if send_join_msg:
        found_time = increment_timestamp()
        join_msg = {
            "type": "join",
            "msg_id": new_id(),
            "user": username,
            "room": new_chatroom,
            "addr": [MY_HOST, MY_PORT],
            "ttl": 5,
            "lamport": found_time, ##& Adds lamport time to the message output ##
        }
        forward(join_msg)

    forward({
    "type": "focus_enter",
    "msg_id": new_id(),
    "user": username,
    "room": new_chatroom,
    "addr": [MY_HOST, MY_PORT],
    "ttl": 5,
    "lamport": found_time, ##& Adds lamport time to the message output ##
})

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
    global timestamp
    with lock_lamport:
        timestamp += 1
        return timestamp

##& Updates the current clock time ##
def updating_lamport_time(current_time):
    global timestamp
    with lock_lamport:
        timestamp = max(timestamp, current_time) + 1 # increments the max lamport time each time a new message is sent
        return timestamp

def main():
    global username, current_chatroom

    threading.Thread(target=listener, daemon=True).start()
    ready.wait()

    with console_lock:
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
    
    while username_check(username):
        with console_lock:
            print(f"[SYSTEM] Username '{username}' is already taken. Please choose another.")
            username = input("Enter a new username: ").strip()
            
            # In case the user just hits Enter, assign a new random name
            if not username:
                username = f"user{uuid.uuid4().hex[:4]}"
    
    with console_lock:
        print("\nQuerying network for available rooms...")
    available_rooms = query_rooms()
    
    if available_rooms:
        with console_lock:
            print("\nAvailable rooms:")
        for idx, r in enumerate(available_rooms, 1):
            with members_lock:
                member_count = len(members.get(r, set()))
            print(f"  {idx}. {r} ({member_count} members)")
    else:
        with console_lock:
            print("No rooms found. Create one!")
        
    room = input("\nEnter room name: ").strip() or "lobby"
    answer = input(f"Is this the room you want to join? Check spellling. (y/n): ")
    while answer.lower()== 'n' or answer.lower() == 'no': 
        room = input("\nEnter room name: ").strip() or "lobby"
        answer = input(f"Is this the room you want to join? Check spellling. (y/n): ")

    
    true_chatroom = room_checker(room)
    join_chatroom(true_chatroom)


    with console_lock:
        print("\nAvailable commands:")
        print("     d/Join <chatroom>         - Joins a new chatroom")
        print("     d/Switch <chatroom>       - Switches to a different chatroom")
        print("     d/Rooms                   - Lists your current chatrooms")
        print("     d/Flood <message>         - Sends a message to everyone and every room")
        print("     d/discoverTopic <topic>   - Input topic you want to send message to, then will input a message to send")
        print("     d/help                  - Reprint comands\n")

    while True:
        try:

            with room_state_lock:
                    prompt_room = current_chatroom
                
            # Take input WITHOUT holding the console lock
            text = input(f"[{prompt_room}]> ").strip()

            if not text:
                continue

            if text.lower() in ("exit", "quit"):

                with room_state_lock:
                    chatrooms_copy = set(current_chatrooms)
                
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