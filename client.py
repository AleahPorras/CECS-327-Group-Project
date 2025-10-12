import socket
import threading

def main():
    # Creation of the client socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = '127.0.0.1'
    port = 12345
    # Connects the client to the server's IP address and port number
    client_socket.connect((host, port))

    # Users send messages to the server using sendall
    while True:
        message = input("Enter your message: ")
        client_socket.sendall(message.encode('utf-8'))
        data = client_socket.recv(1024)
        response = data.decode('utf-8')
        # Receives the server's response, basically confirmation/echo of the message
        print(f"Server response: {response}")

if __name__ == "__main__":
    main()