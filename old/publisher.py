# publisher send message to broker's PULL and the broker publishes it on PUB as topic and payload
# subscriber subscribes topic will get the message


import zmq, json

BROKER = "tcp://127.0.0.1:5555"
TOPIC  = "room/general"
TEXT   = "hello group"

ctx  = zmq.Context.instance()
push = ctx.socket(zmq.PUSH)
push.connect(BROKER)

msg = {"topic": TOPIC, "payload": {"text": TEXT}}
push.send_json(msg)
print("sent:", msg)


