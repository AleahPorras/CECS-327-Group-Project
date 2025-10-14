import  xmlrpc.client 

#acessing the server
proxy = xmlrpc.client.ServerProxy('http://localhost:3000')



def get_room_to_join():
    room_to_join = input("Enter the name of the room you would likee to join: ")
    return room_to_join

def get_room_to_create(room_to_create):
    room_to_create = input("Enter the name of the room you want to create:") 
    return room_to_create

if __name__ == '__main__':
    ##EXAMPLE CALLING
    #Calling the remote function and printing the list (place holder function)
    ## We will call our functions like this 
    # print(proxy.list_directory())
    user = input("What is your room name: ")
    action = input("Would you like to join or create a room? (join/create): ")
    
    if action == "join":
        
        room = get_room_to_join()

        print(proxy.join_room(room))
        
    if action == "create":

        room = get_room_to_create()
        print(proxy.create_room(room,user))
        

