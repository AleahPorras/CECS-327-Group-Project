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

# room management
all_rooms = set()
rooms_lock = threading.Lock()

ready = threading.Event()
handshake_done = threading.Event() # makes sure both the ping and pong are sent and recieved from bootstrap

#each peer keeps a "seen" of message IDs, so peers can tell duplicates when flooding
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


def handle_msg(msg, tcp_addr):
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
            for r in announced_rooms:
                all_rooms.add(r)
        return
    
    if mtype == "room_query":
        with rooms_lock:
            send_msg(real_addr, {
                "type": "room_response",
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

    if msg_room is not None and room is not None and msg_room != room:
        return

    if mtype == "join":
        with members_lock:
            members.setdefault(msg_room, set())
            if msg_user in members[msg_room]:
                send_msg(real_addr, {
                    "type": "name_taken",
                    "msg_id": new_id(),
                    "room": msg_room,
                    "user": msg_user,
                })
                return
            members[msg_room].add(msg_user)
            print(f"\r{msg_user} joined {msg_room}\n> ", end = "", flush = True)
            # return
        with rooms_lock:
            all_rooms.add(msg_room)

    if mtype == "name_taken":
        print("[error] username already in use in this room. exiting...")
        sys.exit(1)

    if mtype == "chat":
        print(f"\r[{msg_user}@{msg_room}] {msg['text']}\n> ", end = "", flush = True)
        # return

    if mtype == "leave":
        with members_lock:
            if room in members:
                members[room].discard(msg_user)
            print(f"\r{msg_user} left {room}\n> ", end = "", flush = True)
            # return
    if mtype not in ("ping", "pong", "name_taken"):
        forward(msg, exclude=real_addr)

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
    #s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,

    # pick the first free port starting at BASE_PORT
    for port in range(BASE_PORT, BASE_PORT + MAX_PEERS):
        try:
            s.bind((MY_HOST, port))
            MY_PORT = port
            break
        except OSError:
            continue

    s.listen(100)
    print(f"[listen] {MY_HOST}:{MY_PORT}")
    ready.set()

    while True:
        c, a = s.accept() # loop so peer is always reachable
        threading.Thread(target=handle_conn, args=(c, a), daemon=True).start()

def query_rooms():
    msg = {
        "type": "room_query",
        "msg_id": new_id(),
        "addr": [MY_HOST, MY_PORT],
        "ttl": 3,
    }
    forward(msg)
    time.sleep(2)
    
    with rooms_lock:
        return list(all_rooms)

def main():
    global username, room

    threading.Thread(target=listener, daemon=True).start()
    ready.wait()

    username = input("Enter your username: ").strip() or f"user{uuid.uuid4().hex[:4]}"
    bootstrap()
    
    with neighbors_lock:
        if not neighbors and MY_PORT != BASE_PORT:
            print("[bootstrap] Waiting for a handshake...")
            if not handshake_done.wait(timeout=5):
                print("[bootstrap] Timeout waiting for handshake.")
    
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
    
    room = input("\nEnter room name: ").strip() or "lobby"

    # ISSUE
    # if a completely new user joins, they won't see the members that joined before them.
    with members_lock:
        members.setdefault(room, set())
        members[room].add(username)

        print(f"[debug] neighbors now: {members}")

    with rooms_lock:
        all_rooms.add(room)

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

    while True:
        text = input("> ").strip()
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