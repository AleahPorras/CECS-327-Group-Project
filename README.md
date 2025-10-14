# CECS-327-Group-Project
Creating a less complex chat system for small niche communities, users who care for their privacy, and students who have temporary groups for assignments.

3. Indirect communication(pub-sub with a ZeroMQ broker). 

- Decouple time and decouple space, asynchronous broadcast by topic(room). User offline at published time cannot get the message, no backlog.
- Required install: python -m pip install pyzmq
- Broker displays PULL 5555: and PUB: 5556
- Publisher connects to broker PULL (5555)
- Subscribers connect to broker PUB (5556)
    
