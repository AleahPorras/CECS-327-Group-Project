# CECS-327-Group-Project
Creating a less complex chat system for small niche communities, users who care for their privacy, and students who have temporary groups for assignments.

1. Requirements and Dependencies

All implemented components are written in Python 3.x.
Core Requirements

    Python 3.8+

    Multithreading support (standard in Python, used in server.py for concurrent client handling).

Dependencies

This project primarily utilizes modules from the Python Standard Library, meaning no external libraries are required for the implemented Direct (IPC) and Remote (RPC) communication parts.

Mechanism               Python Module Used              External Broker Required       Installation Command

Direct (IPC)            socket, threading               None                           N/A
	
Remote (RPC)            xmlrpc.client, xmlrpc.server    None                           N/A
	
Indirect (Pub/Sub)      zmq, json                       No                             pip install pyzmq
                                                        (ZMQ acts as a brokerless messaging layer)                                                      
2. Component Purpose

This section maps the source files to their specific roles within the ThisCord architecture and the communication task they fulfill.

A. Direct Communication – Interprocess Communication (IPC)

    File Name       Component Role                 Communication Protocol        Purpose

    server.py       Chat Message Hub (Server)      TCP Socket (Stream)           Acts as the main communication endpoint for real-time chat, handling multiple simultaneous client connections using threading to ensure concurrency.

    client.py       Chat Client                    TCP Socket (Stream)           Simulates an actively chatting user, connecting to the Message Hub to send messages and receive immediate echo confirmation.
	
B. Remote Communication – Remote Procedure Call (RPC)

    File Name           Component Role                   Communication Protocol     Purpose
        
    server-xmlrpc.py    Room Management Service          XML-RPC                    Exposes remote methods (create_room, join_room, list_rooms) that clients can invoke to manage chatroom state before the real-time chat session begins.

    client-xmlrpc.py    Client Administration Interface  XML-RPC                    Handles the initial connection and administrative requests from the user, calling remote functions on the Room Management Service.

C. Indirect Communication – Message Queues (Planned)

    File Name       Component Role              ZMQ Protocol / Socket Type     Purpose
    
    broker.py       ZMQ Forwarding Broker       PULL / PUB       Binds two separate sockets: a PULL socket to receive messages from Publishers and a PUB socket to distribute those messages to all connected Subscribers based on their topics.

    subscriber.py   Monitoring Subscriber       SUB              Connects to the Broker's PUB address and uses a topic filter (zmq.SUBSCRIBE) to asynchronously receive and process relevant system events (e.g., chatroom activity, server health metrics).

    publisher.py    Server Event Publisher      PUSH             Connects to the Broker's PULL address and pushes non-essential, asynchronous events (e.g., "User Login," "Chatroom Created") to decouple the main server load.

3. How to Run Each Module

All scripts should be run from the command line in separate terminal windows. Use python [filename] to execute.
A. Direct Communication (IPC - TCP Sockets)

This demonstration requires two or more terminals for the server and client(s).

    1. Start the Server (Chat Message Hub):

    python server.py

    (The server will listen on 127.0.0.1:12345).

    2. Start Client 1:

    python client.py

    (Enter a message, and observe the echo response).

    3. Start Client 2 (Optional, in a new terminal):

    python client.py

    (Observe that the server handles both connections concurrently).

B. Remote Communication (RPC - XML-RPC)

This demonstrates administrative communication for room setup.

    1. Start the Room Management Service (RPC Server):

    python server-xmlrpc.py

    (The server will listen on localhost:3000).

    2. Run the Client Administration Script:

    python client-xmlrpc.py

        The client will immediately list available rooms (using the RPC list_rooms call).

        Follow the prompts to enter a username and choose the action (join or create).

        Observe the response printed to the client and the confirmation log on the server console.

C. Indirect Communication (Pub/Sub - ZeroMQ)

This demonstration requires three terminals for the broker, the subscriber, and the publisher. The setup uses a PUSH/PULL pattern for reliable transmission from Publisher to Broker, and a PUB/SUB pattern from Broker to Subscribers for fan-out.

    1. Start the ZMQ Broker (Forwarder):

    python broker.py

    (The broker binds PULL on 5555 and PUB on 5556).

    2. Start the Monitoring Subscriber (Specify a topic filter):

    # Subscribes to events starting with 'room/'
    python subscriber.py room/

    3. Run the Server Event Publisher:

    python publisher.py

    (The publisher will send a single message with the topic room/general and then exit. The subscriber should immediately receive and print the message).

