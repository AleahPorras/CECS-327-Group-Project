from  xmlrpc.client import ServerProxy

#acessing the server
proxy = ServerProxy('http://localhost:3000')

if __name__ == '__main__':
    #Calling the remote function and printing the list (place holder function)
    ## We will call our functions like this 
    print(proxy.list_directory())



