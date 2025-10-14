import zmq,json

# broker binds two sockets: pull from publishers and publish to subscribers
PULL_ADDR = "tcp://127.0.0.1:5555"
PUB_ADDR = "tcp://127.0.0.1:5556"

def main():
    ctx = zmq.Context.instance()
    pull = ctx.socket(zmq.PULL)     #receive messages from PUSH
    pull.bind(PUB_ADDR)

    pub = ctx.socket(zmq.PUB)   # publishes to all subscribers who follow the topic
    pub.bind(PULL_ADDR)     

    print(f"[broker] PULL {PULL_ADDR}, PUB {PUB_ADDR}")

    while True:
        msg = pull.recv_json()      #blocks until a publisher sends message(topic,payload)
        topic = msg.get("topic")
        if not topic:
            continue
        pub.send_multipart([topic.encode(), json.dumps(msg["payload"]).encode()])
if __name__ == "__main__":
    main()






