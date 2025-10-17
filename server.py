import socket
import selectors

#& Represents the chatroom server
class ChatServer:
    # Save the host and port to set up the server socket later on.
    def __init__ (self, host, port):
        self._host = host
        self._port = port
        self._socket = None
        self._read_selector = selectors.DefaultSelector()
        self._write_selector = selectors.DefaultSelector()

    # Will be called when teh server is read yto accept a new connection.
    def accept_connection(self, socket):
        client, _ = socket.accept()
        print("Registering new client!")
        self._read_selector.register(client, selectors.EVENT_READ, self.receive_message)
        self._write_selector.register(client, selectors.EVENT_WRITE)

    # Will be called when the client is ready to receive a message from the client.
    def receive_message(self, socket):
        message = socket.recv(1024)
        print(message.decode('utf-8'))
        for key, _ in self._write_selector.select(0): # Asks for a list of all sockets that can be written to.
            # Checks to see if the socket is not the one that orignally sent the message.
            # Ensures there is no echoing.
            if key.fileobj is not socket:
                key.fileobj.send(message)
            # socket = key.fileobj # key contains information about registered sockets.
            # socket.sendall(message)

    # Initializes the server socket and connects it ot the correct address and port.
    def initialize_server(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((self._host, self._port))
        self._socket.listen(5)
        # Places the socket in the read selector to monitor incoming connections.
        self._read_selector.register(self._socket, selectors.EVENT_READ, self.accept_connection) # EVENT_READ means we only want to accept incoming connections.

    # Actually runs the server to accept incoming connections.
    def run(self):
        self.initialize_server()
        print(f"Running server on {self._host}:{self._port}!")
        while True:
            for key, _ in self._read_selector.select(): # Asks for a list of all sockets that can be read from.
                sock, callback = key.fileobj, key.data # key contains information about registered sockets.
                callback(sock)

if __name__ == "__main__":
    chatServer = ChatServer("localhost", 7342)
    chatServer.run()


# import socket
# import threading

# def handle_client(client_socket):

#     # Continuously receives data from the client
#     while True:
#         data = client_socket.recv(1024)
#         # Checks if the client has disconnected
#         if not data:
#             break
#         message = data.decode('utf-8') # decodes data
#         print(f"Received message: {message}")
#         response = f"Server received your message: {message}"
#         client_socket.sendall(response.encode('utf-8')) # encodes response message back to client
#     client_socket.close()

# def main():
#     # Acts as the communication endpoint for the server
#     server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # socket.SOCK_STREAM indicates TCP
#     host = '127.0.0.1'
#     port = 12345
#     # Makes sure server is ready for incoming client connections
#     server_socket.bind((host, port))
#     server_socket.listen(5)
#     print(f"Server listening on {host}:{port}")

#     while True:
#         client_socket, client_address = server_socket.accept()
#         print(f"Accepted connection from {client_address}")
#         # Allows the server to handle multiple connections concurrently
#         client_handler = threading.Thread(target = handle_client, args = (client_socket,))
#         client_handler.start()

# if __name__ == "__main__":
#     main()
