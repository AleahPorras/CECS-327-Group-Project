import  xmlrpc.client 

#acessing the server
proxy = xmlrpc.client.ServerProxy('http://localhost:3000')


#----------------------functions ----------------------
def get_room_to_join():
    room_to_join = input("Enter the name of the room you would like to join: ")
    # Checks if the user provided a name for the room
    while room_to_join == None: 
        print("No name provided, try again.")
        room_to_join = input("Enter the name of the room you would like to join: ")
        
    return room_to_join

def get_room_to_create():
    room_to_create = input("Enter the name of the room you want to create: ") 
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
    #---------------------------joining a room------------------------------
    if action == "join" or action == "Join":
        room = get_room_to_join()
        current_rooms = proxy.all_rooms()
        
    
        while room not in current_rooms: 
            answer = input("This room does not exist, would you like to create it? yes/no: ")
            if answer == "Yes" or answer == 'yes': 
               
                print("Creating the room...\n")
                output = proxy.create_room(room, user)
                print(f'List of all current rooms and members: {output}\n')
                print("Welcome to your new room!")
                
                
            
               
            elif answer == "No" or answer == 'no':
                room = get_room_to_join()
                current_members = proxy.current_members(room)
               

               
            else: 
                print("Not a correct response try again... ")

            current_rooms = proxy.all_rooms()
        
        
        print("Joining the room...\n")

        current_members = proxy.current_members(room)
        output = proxy.join_room(room, user)
        print(f"List of all current members: {current_members}\n")

        print(f"{user} you have joined {room}\n")
      
        current_members = proxy.current_members(room)
        print(f"List of all current members: {current_members}\n")
               
        

       
    #-----------------------------creating a room-------------------------------- 
    elif action == "create" or action == "Create":

        room = get_room_to_create()

        rooms_before = proxy.all_rooms()
        print(f'Current list before adding: {rooms_before}\n')

        print("Creating the room...\n")
        
        output = proxy.create_room(room, user)
        proxy.join_room(room, user)
        current_rooms =  proxy.all_rooms()


        print(f'List of all current rooms and members: {current_rooms}\n')

    else: 
        print("You have not entered a valued response, please run again. ")
        print("Hint: You must have it printed exactly, either join or create")

