import  xmlrpc.client 

#acessing the server
proxy = xmlrpc.client.ServerProxy('http://localhost:3000')



def get_room_to_join():
    room_to_join = input("Enter the name of the room you would like to join: ")
    # Checks if the user provided a name for the room
    while room_to_join == None: 
        print("No name provided, try again.")
        room_to_join = input("Enter the name of the room you would like to join: ")
        
    return room_to_join

def get_room_to_create():
    room_to_create = input("Enter the name of the room you want to create:") 
    # Checks if the user provided a name for the room
    while room_to_create == None: 
        print("No name provided, try again.")
        room_to_create = input("Enter the name of the room you would like to join: ")
        
    return room_to_create

if __name__ == '__main__':
    ##EXAMPLE CALLING
    #Calling the remote function and printing the list (place holder function)
    ## We will call our functions like this 
    # print(proxy.list_directory())

    user = input("What is your username?: ")
    action = input("Would you like to join or create a room? (join/create): ")
    
    if action == "join" or action == "Join":
        room = get_room_to_join()
        print("Joining the room...")
        output = proxy.join_room(room, user)
        print(f"{user} you have joined {room}")
        print(output)
        
    elif action == "create" or action == "Create":

        room = get_room_to_create()
        print("Creating the room...")
        output = proxy.create_room(room, user)
        print(output)

    else: 
        print("You have not entered a valued response, please run again. ")
        print("Hint: You must have it printed exactly, either join or create")

