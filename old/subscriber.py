import zmq, json, sys

BROKER_PUB = "tcp://127.0.0.1:5556" # connects to the broker
TOPIC = sys.argv[1] if len(sys.argv) > 1 else "room/" # subscribes to a topic/prefix

ctx = zmq.Context.instance() # get zmq context
sub = ctx.socket(zmq.SUB)   # create a SUB socket
sub.connect(BROKER_PUB)
sub.setsockopt_string(zmq.SUBSCRIBE, TOPIC) # install a topic/prefix filter
print(f"[SUB] connected to {BROKER_PUB}; SUBSCRIBE='{TOPIC}'")

while True:
    topic_b, payload_b = sub.recv_multipart()
    topic = topic_b.decode("utf-8")
    payload = json.loads(payload_b.decode("utf-8"))
    print(f"[{topic}] {payload}")
