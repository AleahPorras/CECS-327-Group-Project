# CECS-327-Group-Project
Note:  broker.py, server-xmlrpc.py, and client-xmlrpc.py are the only files you will NEED to run. Other files are for documentation and were used to understand how to implement all these forms of communication together.<br>
Creating a less complex chat system for small niche communities, users who care for their privacy, and students who have temporary groups for assignments.

1. Requirements and Dependencies

All implemented components are written in Python 3.x.
Core Requirements

    Python 3.8+

    Multithreading Used in client-xmlrpc.py to run the ZMQ Subscriber thread concurrently with the user input loop.

Dependencies

This project primarily utilizes modules from the Python Standard Library, meaning no external libraries are required for the implemented Direct (IPC) and Remote (RPC) communication parts.

	Mechanism               Python Module Used              External Broker Required       Installation Command
	
	Direct (IPC)            socket                         None                           N/A
                            (Code for a basic socket server exists in server.py but is integrated into server-xmlrpc.py's function logic).
	Remote (RPC)            xmlrpc.client, xmlrpc.server    None                           N/A
		
	Indirect (Pub/Sub)      zmq, json                       No                             pip install pyzmq
	                                                        (ZMQ acts as a brokerless messaging layer)                                                      
2. Component Purpose

This section maps the source files to their specific roles within the ThisCord architecture and the communication task they fulfill.

A. Direct Communication – Interprocess Communication (IPC)

    File Name       	   Component Role               Communication Protocol         Purpose

    server-xmlrpc.py       Chat Message Hub / Sender     XML-RPC (trigger)-> ZMQ PUSH   The RPC method send_message is called by the client. This method immediately triggers the Indirect Communication mechanism by PUSHing the message to the ZMQ Broker for distribution.

    client-xmlrpc.py       Chat Client / Receiver        ZMQ SUB                    The client starts a background thread running a ZMQ SUB socket to receive and print messages in real-time. This effectively handles the IPC (real-time chat) requirement.
	
B. Remote Communication – Remote Procedure Call (RPC)

    File Name           Component Role                   Communication Protocol     Purpose
        
    server-xmlrpc.py    Room Management Service          XML-RPC                    Exposes remote methods (create_room, join_room, remove_user, etc.) to manage chatroom state (members, ownership) prior to or during the messaging session.

    client-xmlrpc.py    Client Administration Interface  XML-RPC                    Handles the initial user workflow (authentication, choosing to create/join a room) by calling remote functions on the Room Management Service.

C. Indirect Communication – Message Queues (Pub-Sub via ZeroMQ)

    File Name       	Component Role              ZMQ Protocol / Socket Type     Purpose
    
    broker.py       	ZMQ Forwarding Broker       PULL / PUB       A standalone process that facilitates communication between the decoupled RPC server and the clients. It receives messages via PULL and distributes them to all subscribers via PUB.

    client-xmlrpc.py   	Monitoring Subscriber       SUB              Connects to the Broker's PUB address in a dedicated thread to receive topic-filtered chat messages asynchronously.

    server-xmlrpc.py    Server Event Publisher      PUSH             Sends messages to the broker.py PULL socket immediately after an RPC send_message call is received. This decouples message sending from delivery.

3. How to Run Each Module

All scripts should be run from the command line in separate terminal windows. Use python [filename] to execute.

A. Full System Startup Order

The order is critical due to the ZMQ connections. You must run these components in four separate terminals:

	Start the Broker:
	
	python broker.py
	
	
	(The broker starts listening on PULL: 5555 and PUB: 5556.)
	
	Start the RPC Server (Publisher/Room Manager):
	
	python server-xmlrpc.py
	
	
	(This connects the server's PUSH socket to the broker and starts the RPC service on localhost:3000.)
	
	Start Client 1 (Client/Subscriber):
	
	python client-xmlrpc.py
	
	
	(Follow prompts: Enter username, choose 'create' or 'join' room. Once joined, a background thread connects the ZMQ SUB socket to the broker, and the chat prompt appears.)
	
	Start Client 2 (Client/Subscriber):
	
	python client-xmlrpc.py
	
	
	(Follow prompts: Join the room created by Client 1.)

B. Messaging Flow (Direct/Indirect Integration)
	
	When Client 1 types a message and presses Enter:
	
	client-xmlrpc.py makes an RPC call (send_message) to server-xmlrpc.py.
	
	server-xmlrpc.py immediately PUSHes the message to broker.py (Indirect Communication).
	
	broker.py forwards the message via PUB.

	The background threads in both Client 1 and Client 2 (client-xmlrpc.py) receive the message via SUB and display it in real time (IPC fulfillment).

4. Validation and Testing

This section details how to confirm that all three communication mechanisms are functional and exchanging data as intended, addressing the "Validation Summary" deliverable.

A. RPC Validation (Room Management)

Test Scenario: Verify remote creation and state persistence.
	
	Ensure broker.py and server-xmlrpc.py are running (Steps 1 & 2 above).
	
	Run client-xmlrpc.py (Client 1).
	
	Enter username Alice.
	
	Choose create, enter room name GeneralChat.
	Expected Outcome:
	
	The client prints confirmation: Creating chatroom GeneralChat....
	
	The server console prints a confirmation log: Chatroom GeneralChat has been created.
	
	If you run a second client, the initial room list will show GeneralChat.

B. Indirect (ZMQ Pub/Sub) & IPC Validation (Real-Time Chat)

Test Scenario: Validate asynchronous message delivery between decoupled clients.
	
	Ensure Client 1 (Alice in GeneralChat) is running.
	
	Start Client 2 (client-xmlrpc.py), enter username Bob, and join the GeneralChat room.
	
	In Client 1 (Alice) terminal, type: Hello Bob, testing ZMQ!
	Expected Outcome:
	
	Client 1 (Alice's screen): The message appears instantly as the SUB thread receives the message.
	
	Client 2 (Bob's screen): The message appears instantly: Alice: Hello Bob, testing ZMQ!.
	
	Server Console (server-xmlrpc.py): Prints a log of the PUSH operation: Sent message to chatroom room/GeneralChat: {'user': 'Alice', 'text': 'Hello Bob, testing ZMQ!'}.

This validates that the RPC call successfully triggered the ZMQ PUSH (Publisher), which was forwarded by the Broker, and received by the SUB sockets in the clients (Subscribers), fulfilling both the IPC and Indirect communication requirements simultaneously.
