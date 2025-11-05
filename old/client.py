import socket
import threading


#& Represents the chatroom client
class ChatClient:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def continuous_receive(self):
        while True:
            message = input()
            self._socket.send(message.encode('utf-8'))

    def receive_message(self, socket):
        message = socket.recv(1024)
        print(message.decode('utf-8'))

    def connect_to_server(self):
        self._socket.connect((self._host, self._port))
        # Starts a thread that continuously checks for messages.
        threading.Thread(target = self.continuous_receive).start()
        while True:
            message = self._socket.recv(1024).decode('utf-8')
            print(" < " + message)

if __name__ == "__main__":
    client = ChatClient("localhost", 7342)
    client.connect_to_server()

# def main():
#     # Creation of the client socket
#     client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     host = '127.0.0.1'
#     port = 12345
#     # Connects the client to the server's IP address and port number
#     client_socket.connect((host, port))

#     # Users send messages to the server using sendall
#     while True:
#         message = input("Enter your message: ")
#         client_socket.sendall(message.encode('utf-8'))
#         data = client_socket.recv(1024)
#         response = data.decode('utf-8')
#         # Receives the server's response, basically confirmation/echo of the message
#         print(f"Server response: {response}")

# if __name__ == "__main__":
#     main()
