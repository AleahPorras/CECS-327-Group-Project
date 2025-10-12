from xmlrpc.server import SimpleXMLRPCServer
import os

#___________________________     INITIALIZING     __________________________
#For the list_directory() function
directory = os.path.dirname(os.path.abspath(__file__))

#creation of the server (listens to the address)
server = SimpleXMLRPCServer(('localhost',3000), logRequests = True)



#___________________________ FUNCTION DEFINITIONS __________________________
## Example function, we need to create our own functions 
def list_directory():
    return os.listdir(directory)



#___________________________ FUNCTION REGISTRATION ___________________________
#registering the function 
server.register_function(list_directory)




#___________________________     SERVER CALLING    ___________________________
if __name__ == '__main__': 
    try:
        ## Successful 
        print('Serving divorce papers...')
        #starting the server
        server.serve_forever()

    except KeyboardInterrupt:
        ## Not Sucessful
        print('Getting your children taken away')