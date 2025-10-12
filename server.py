import socket
import threading

def handle_client(client_socket):

    # Continuously receives data from the client
    while True:
        data = client_socket.recv(1024)
        # Checks if the client has disconnected
        if not data:
            break
        message = data.decode('utf-8') # decodes data
        print(f"Received message: {message}")
        response = f"Server received your message: {message}"
        client_socket.sendall(response.encode('utf-8')) # encodes response message back to client
    client_socket.close()

def main():
    # Acts as the communication endpoint for the server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # socket.SOCK_STREAM indicates TCP
    host = '127.0.0.1'
    port = 12345
    # Makes sure server is ready for incoming client connections
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Server listening on {host}:{port}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Accepted connection from {client_address}")
        # Allows the server to handle multiple connections concurrently
        client_handler = threading.Thread(target = handle_client, args = (client_socket,))
        client_handler.start()

if __name__ == "__main__":
    main()