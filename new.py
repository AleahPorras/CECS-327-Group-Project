import socket, threading, json, sys, uuid, random, time


# network configuration
MY_HOST = "127.0.0.1"
BASE_PORT = 5000
MAX_PEERS = 100
MY_PORT = None

# peer state
neighbors = set()
neighbors_lock = threading.Lock()
seen = set()
seen_lock = threading.Lock()
username = None
room = None
members = {}
members_lock = threading.Lock()

# Tracks consecutive failures for each neighbor address
neighbor_failures = {}
MAX_FAILURES = 3

# room management
all_rooms = set()
rooms_lock = threading.Lock()

ready = threading.Event()
handshake_done = threading.Event() # makes sure both the ping and pong are sent and recieved from bootstrap

#each peer keeps a "seen" of message IDs, so peers can tell duplicates when flooding
def new_id():
    return str(uuid.uuid4())

# open TCP socket , send message and close (includes Dead Peer Detection    )
def send_msg(addr, obj):
    h, p = addr
    try:
        s = socket.socket()
        s.connect((h, p))
        s.sendall((json.dumps(obj) + "\n").encode())
        s.close()

        # If successful, reset failure count
        with neighbors_lock:
            neighbor_failures.pop(addr, None)
    except OSError as e:
        # Connection or send failed, this peer might be dead
        with neighbors_lock:
            # Increment failure count
            neighbor_failures[addr] = neighbor_failures.get(addr, 0) + 1
            print(f"[dead peer check] Connection to {addr} failed ({neighbor_failures[addr]}/{MAX_FAILURES}).")
            
            # Remove peer if max failures reached
            if neighbor_failures[addr] >= MAX_FAILURES:
                print(f"[dead peer check] Removing dead peer: {addr}")
                neighbors.discard(addr)
                neighbor_failures.pop(addr, None)
        # We catch and silence the error here, ensuring the app doesn't crash
        pass

# first contact of a new peer to the network
# sends a ping to known peer, and that peer answer with pong and both added to their neighbors
# look for a running peer , if none is found, it is the first peer
def bootstrap():

    if MY_PORT == BASE_PORT:
        print("[bootstrap] I am the first peer, starting new network")
        return

    if MY_PORT is None:
        return

    found = False
    ports = list(range(BASE_PORT, BASE_PORT + MAX_PEERS))
    random.shuffle(ports)

    for port in ports:
        if port == MY_PORT:
            continue
        try:
            s = socket.create_connection((MY_HOST, port), timeout=0.5)
            s.close()
            msg = {
                "type": "ping",
                "msg_id": new_id(),
                "addr": [MY_HOST, MY_PORT],
                "room": room,
                "ttl": 5,   # the message can be forwarded at most 5 hops.
            }
            send_msg((MY_HOST, port), msg)
            print(f"[bootstrap] connected to existing peer at {MY_HOST}:{port}")
            found = True
            # break
        except OSError:
            continue

    if not found:
        print("[bootstrap] no existing peers found; starting new network")

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
#Proactive Dead Peer Checking
def dead_peer_checker():
    """Periodically pings all neighbors to check for liveness."""
    while True:
        time.sleep(10) # Check every 10 seconds
        
        with neighbors_lock:
            if not neighbors:
                continue
            peers_to_check = list(neighbors)

        # Send a health check ping to all neighbors
        for peer_addr in peers_to_check:
            # Skip if already marked for deletion in the send_msg logic
            if neighbor_failures.get(peer_addr, 0) >= MAX_FAILURES:
                continue
                
            ping_msg = {
                "type": "ping",
                "msg_id": new_id(),
                "addr": [MY_HOST, MY_PORT],
                "room": room, # Use current room context
                "ttl": 1, # Only one hop is needed for a health check
            }
            send_msg(peer_addr, ping_msg)
        
        # After the check, clean up any failed peers that were handled by send_msg
        with neighbors_lock:
            # Explicit removal check after sending pings (redundant but safe)
            for addr, failures in list(neighbor_failures.items()):
                if failures >= MAX_FAILURES:
                    neighbors.discard(addr)
                    neighbor_failures.pop(addr)

def handle_msg(msg, tcp_addr):
    global neighbors, members

    # --- Robust Parsing and Validation ---
    try:
        real_addr = tuple(msg.get("addr", tcp_addr))
        if len(real_addr) != 2:
             print(f"[error] Invalid address format received: {real_addr}")
             return
             
        mid = msg.get("msg_id")
        mtype = msg.get("type")
        msg_room = msg.get("room")
        msg_user = msg.get("user")
    except Exception as e:
        print(f"[error] Failed to parse message fields: {e}")
        return
        
    # 1. Add sender as neighbor (unless it's myself)
    if real_addr != (MY_HOST, MY_PORT):
        with neighbors_lock:
            neighbors.add(real_addr)
            # If a message is received, reset failure tracking
            neighbor_failures.pop(real_addr, None)

    # 2. Drop duplicates
    with seen_lock: 
        if mid in seen:
            return
        # Only add to seen if it's a message that should be forwarded/processed
        if mtype not in ("pong", "room_response", "member_sync"):
            seen.add(mid)

    # if mtype not in ("ping", "pong", "name_taken"):
    #     forward(msg, exclude=real_addr)
    if mtype == "ping":
        # only reply to pings for my room
        if room is not None and msg_room is not None and msg_room != room:
            return
        send_msg(real_addr, {
            "type": "pong",
            "msg_id": new_id(),
            "addr": [MY_HOST, MY_PORT],
            "room": room,
        })
        # focuses on sending current members to all new peers
        with members_lock:
            if members: # runs if there are other members available
                members_json = {room: list(users) for room, users in members.items()} # keeps track of all the current members
                send_msg(real_addr, {
                    "type": "member_sync",
                    "msg_id": new_id(),
                    "addr": [MY_HOST, MY_PORT],
                    "members": members_json, # returns the entire dictionary
                 })
                
        with rooms_lock:
            if all_rooms:
                send_msg(real_addr, {
                    "type": "room_announce",
                    "msg_id": new_id(),
                    "addr": [MY_HOST, MY_PORT],
                    "rooms": list(all_rooms),
                    "ttl": 3,
                })
        forward(msg, exclude=real_addr)
        return

    ## Handler functions

    if mtype == "pong":
        # only count handshake if same room
        if room is None or msg_room is None or msg_room == room:
            print(f"\r[handshake] connection established with {real_addr}\n> ", end = "", flush = True)
            handshake_done.set()
        return
    
    if mtype == "member_sync":
        synced_members = msg.get("members",{}) # gets member from each peer
        with members_lock:
            for room, user_set in synced_members.items():
                members.setdefault(room, set()).update(user_set) # merges the current member dictionary with the peer's
        return

    if mtype == "room_announce":
        announced_rooms = msg.get("rooms", [])
        with rooms_lock:
            all_rooms.update(announced_rooms)
        # Forward, as this is a broadcast type message
        forward(msg, exclude=real_addr)
        return
    
    if mtype == "room_query":
        with rooms_lock:
            send_msg(real_addr, {
                "type": "room_response",
                "msg_id": new_id(),
                "addr": [MY_HOST, MY_PORT],
                "rooms": list(all_rooms),
            })
        forward(msg, exclude=real_addr)
        return
    
    if mtype == "room_response":
        rooms = msg.get("rooms", [])
        with rooms_lock:
            all_rooms.update(rooms)
        return

    if msg_room is not None and room is not None and msg_room != room:
        return

    if mtype == "join":
        with members_lock:
            members.setdefault(msg_room, set())
            if msg_user in members[msg_room]:
                # Send explicit name_taken error back to sender
                send_msg(real_addr, {
                    "type": "name_taken",
                    "msg_id": new_id(),
                    "room": msg_room,
                    "user": msg_user,
                })
                return
            members[msg_room].add(msg_user)
            print(f"\r{msg_user} joined {msg_room}\n> ", end = "", flush = True)
        
        with rooms_lock:
            all_rooms.add(msg_room)
        
        # Forward JOIN message
        forward(msg, exclude=real_addr)
        return

    if mtype == "name_taken":
        print("[error] username already in use in this room. exiting...")
        sys.exit(1)

    if mtype == "chat":
        print(f"\r[{msg_user}@{msg_room}] {msg['text']}\n> ", end = "", flush = True)
        forward(msg, exclude=real_addr)
        return

    if mtype == "leave":
        with members_lock:
            if msg_room in members:
                members[msg_room].discard(msg_user)
            print(f"\r{msg_user} left {msg_room}\n> ", end = "", flush = True)
            
        forward(msg, exclude=real_addr)
        return

# read one TCP and feed all messages on it into handle_msg function
def handle_conn(conn, addr):
    with conn:
        try:
            data = conn.recv(4096)
        except OSError as e:
            print(f"[listener error] Failed to receive data from {addr}: {e}")
            return # Exit thread on receive error
            
    for line in data.splitlines():
        if not line:
            continue
        try:
            msg = json.loads(line.decode())
            handle_msg(msg, addr)
        except json.JSONDecodeError:
            print(f"[listener error] Received malformed JSON from {addr}")
        except Exception as e:
            print(f"[listener error] Unhandled exception processing message from {addr}: {e}")

# binds to host/port listen forever act like a server
def listener():
    global MY_PORT
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Added reuse address option

    # pick the first free port starting at BASE_PORT
    for port in range(BASE_PORT, BASE_PORT + MAX_PEERS):
        try:
            s.bind((MY_HOST, port))
            MY_PORT = port
            break
        except OSError:
            continue
            
    if MY_PORT is None:
        print("[error] Could not find a free port! Exiting.")
        sys.exit(1)

    s.listen(100)
    print(f"[listen] {MY_HOST}:{MY_PORT}")
    ready.set()

    while True:
        try:
            c, a = s.accept() # loop so peer is always reachable
            threading.Thread(target=handle_conn, args=(c, a), daemon=True).start()
        except Exception as e:
            print(f"[listener error] Main accept loop failed: {e}")
            time.sleep(1) # Wait a moment before retrying accept


def query_rooms():
    """Broadcasts a query to find all available rooms on the network."""
    msg = {
        "type": "room_query",
        "msg_id": new_id(),
        "addr": [MY_HOST, MY_PORT],
        "ttl": 3,
    }
    forward(msg)
    time.sleep(2) # Give time for room_response messages to arrive
    
    with rooms_lock:
        return sorted(list(all_rooms))

def main():
    global username, room

    # Start the listener and dead peer checker threads
    threading.Thread(target=listener, daemon=True).start()
    threading.Thread(target=dead_peer_checker, daemon=True).start()
    
    ready.wait()

    # --- Robust Input Handling ---
    try:
        username = input("Enter your username: ").strip() or f"user{uuid.uuid4().hex[:4]}"
    except EOFError:
        print("\nInput cancelled. Exiting.")
        sys.exit(0)
    
    bootstrap()
    
    with neighbors_lock:
        if not neighbors and MY_PORT != BASE_PORT:
            print("[bootstrap] Waiting for a handshake...")
            if not handshake_done.wait(timeout=5):
                print("[bootstrap] Timeout waiting for handshake. Continuing as isolated node.")
    
    print("\nQuerying network for available rooms...")
    available_rooms = query_rooms()
    
    if available_rooms:
        print("\nAvailable rooms:")
        for idx, r in enumerate(available_rooms, 1):
            with members_lock:
                member_count = len(members.get(r, set()))
            print(f"  {idx}. {r} ({member_count} members)")
    else:
        print("No rooms found. You can create a new one!")
    
    # --- Robust Input Handling for room name ---
    try:
        room = input("\nEnter room name: ").strip() or "lobby"
    except EOFError:
        print("\nInput cancelled. Exiting.")
        sys.exit(0)

    # ISSUE
    # if a completely new user joins, they won't see the members that joined before them.
    with members_lock:
        members.setdefault(room, set())
        members[room].add(username)

        print(f"[debug] neighbors now: {members}")

    with rooms_lock:
        all_rooms.add(room)

    # Send JOIN message
    join_msg = {
        "type": "join",
        "msg_id": new_id(),
        "user": username,
        "room": room,
        "addr": [MY_HOST, MY_PORT],
        "ttl": 5,
    }
    # with neighbors_lock:
    #     copy_list = list(neighbors)
    # for n in copy_list:
    #     send_msg(n, join_msg)
    forward(join_msg)

    room_announce = {
        "type": "room_announce",
        "msg_id": new_id(),
        "addr": [MY_HOST, MY_PORT],
        "rooms": [room],
        "ttl": 3,
    }
    forward(room_announce)

    print(f"\n--- You are in room '{room}', type messages below. Type 'exit' to quit. ---")

    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            text = "quit"
            
        if not text:
            continue

        if text.lower() in ("exit", "quit"):
            leave_msg = {
                "type": "leave",
                "msg_id": new_id(),
                "user": username,
                "room": room,
                "addr": [MY_HOST, MY_PORT],
                "ttl": 5,
            }
            # with neighbors_lock:
            #     copy_list = list(neighbors)
            # for n in copy_list:
            #     send_msg(n, leave_msg)
            forward(leave_msg)
            print("exiting...")
            break
        

        msg = {
            "type": "chat",
            "msg_id": new_id(),
            "user": username,
            "room": room,
            "text": text,
            "addr": [MY_HOST, MY_PORT],
            "ttl": 5,
        }
        # with neighbors_lock:
        #     copy_list = list(neighbors)
        # for n in copy_list:
        #     send_msg(n, msg)
        forward(msg)

if __name__ == "__main__":
    main()