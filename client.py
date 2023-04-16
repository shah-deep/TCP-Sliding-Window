"""
Deep Shah (SJSU ID: 016662932)
Athira Kumar (SJSU ID: 016597308)
"""


import socket
import random
import time
from collections import deque
import threading
from threading import Thread

"""
TCP Sliding Window Selective Repeat
"""

client_name = "Maverick"   # client name
pkt_success_sent = 0       # counter to track the number of successful packets sent
sent_count = 0             # counter to track the number of packets sent (including the failed ones)
total_packets = 10000000   # total number of packets to be sent
seq_num = 70000            # initial sequence number
packet_size = 4            # packet size
window_size = 1            # window size
max_seq_num = 65536        # maximum sequence number
to_send = []               # list of packets to be sent
dropped_pkt = deque()      # deque of dropped packets
track_drop = set()         # set of dropped packets
re_trans = [[], [], [], []]  # 2-D 1x4 list to track retransmission of packets
seq_iter = 0               # sequence iteration
packets_made = 0           # number of packets made
connected = False          # boolean variable to check if the client is connected to the server


# Creating a file for logging the dropped packets
drp_f = open(f"dropped_seq_num_{int(time.time())}.csv", "w")
drp_f.write("seq_num,tm\n")
drp_lock = threading.Lock()

# Creating a file for logging the window sizes
sender_window_size_f = open(f"sender_window_size_{int(time.time())}.csv", "w")
sender_window_size_f.write("sender_window_size,tm\n")
win_lock = threading.Lock()


# Defines a function to establish a connection with a server
def connect():
    # Declare global variables to be used within the function
    global conn, pkt_success_sent, sent_count, seq_num, window_size, to_send, dropped_pkt, track_drop, re_trans, seq_iter, packets_made, drp_f, sender_window_size_f, connected, client_name

    # Sets the IP address of the server to connect to
    host = socket.gethostname() # Windows Local
    # host = "0.0.0.0" # Mac Local
    # host = "10.0.0.123"

    # Sets the port number for the connection
    port = 4001

    # If already connected, return 1
    if(connected):
        return 1

    try:
        # Creates a socket object using the socket module
        conn = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

        # Attempts to connect to the server
        conn.connect((host, port))

    except Exception as e:
        # If connection fails, print error message and return -1
        print("Error: ", str(e))
        return -1

    # Sets the connection status
    connected = True
    if((pkt_success_sent < 10) or (pkt_success_sent > (total_packets*0.99))):
        reset()
        conn.send(f"SYN {client_name[:10]}".encode()) # start a new connection

    # Otherwise, send a RCN message to the server
    else:
        conn.send(f"RCN {client_name[:10]}".encode())

    # Receives a response from the server
    res = (conn.recv(2048)).decode()

    # If the response is "NEW", print a message to indicate that a connection has been established
    if(res=="NEW"):
        print("Connection Established")
        
    # If the response starts with "OLD", attempt to reconnect
    elif(res[:3]=="OLD"):
        print("Reconnecting...")
        conn.send("SND".encode())
        res = (conn.recv(4096)).decode() # get sync data from server
        if(res):
            data = eval(res)
            pkt_success_sent = data['pkt_rec_cnt'] # set already sent packet count
            sent_count = data['pkt_rec_cnt']
            seq_num = data['seq_num'] # set the current sequence number

        else:
            print("Reconnect Failed!")

    # If the response starts with "SND", send data
    elif(res[:3]=="SND"):
        data = '{' + f'"pkt_success_sent" : int({pkt_success_sent}), "seq_num" : int({seq_num})' + '}'
        conn.sendall(data.encode())

    # If there is an error, print an error message and exit
    else:
        print("Error: Can not reach the server!")
        exit()
    
    try:
        # Call the process_packets() function
        process_packets()
    except Exception as e:
        # Print the error message and call the execution_complete() and try_connect() functions
        print(str(e))
        execution_complete()
        try_connect()


# Defines a function to randomly drop packets with 1% probability
def drop():
    return random.random() < 0.01


# This function handles retransmission of packets
def retrans_handler(pkt, tm, seq_iter):
    global re_trans, track_drop, drp_f
    
    # Create a unique packet ID using packet and sequence iterator
    pid = f"{pkt}_{seq_iter}"
    
    # Add the packet and its timestamp to track dropped packets
    track_drop.add(tuple([pkt, tm]))
    
    # Check if the packet ID already exists in the retransmission dictionary and add it to the appropriate list
    if(pid in re_trans[0]):
        if(pid in re_trans[1]):
            if(pid in re_trans[2]):
                re_trans[3].append(pid)
            else:
                re_trans[2].append(pid)
        else:
            re_trans[1].append(pid)
    else:
        re_trans[0].append(pid)

    # Acquire the lock and write the packet and timestamp to the file
    drp_lock.acquire()
    drp_f.write(f"{pkt},{tm}\n")
    drp_lock.release()
        

# This function reports the window size and its timestamp
def report_window(win_size, tm):
    global window_size_f
    
    # Acquire the lock and write the window size and its timestamp to the file
    win_lock.acquire()
    sender_window_size_f.write(f"{win_size},{tm}\n")
    win_lock.release()



# Define a function called process_packets
def process_packets():
    global conn, pkt_success_sent, sent_count, seq_num, window_size, to_send, dropped_pkt, track_drop, re_trans, seq_iter, packets_made, drp_f, sender_window_size_f
    
    # If the sequence number is less than the maximum sequence number, print a message
    if(seq_num<max_seq_num):
        print(f"Already send {pkt_success_sent} packets. Continued sending at sequence number: {seq_num}.")
        
    # While the number of successfully sent packets is less than the total number of packets
    while(pkt_success_sent < total_packets):
        
        # Initialize some variables
        to_send = []
        exp_acks = 0
        is_dropped = False
        
        
        for _ in range(window_size): # For each packet in the window size
            if(packets_made < total_packets): # If there are more packets to be made          
                if(seq_num%1000==1 and len(dropped_pkt)>0): # If the sequence number modulo 1000 is 1 and there are dropped packets in the deque
                    while( (len(to_send) <= window_size) and (len(dropped_pkt) > 0) ): # While there are less packets to send than the window size and there are dropped packets in the deque
                        to_send.append(dropped_pkt.popleft())  # Add the leftmost dropped packet to the list of packets to send
                    
                    break # Break out of the loop

                # If the sequence number plus the packet size is greater than the maximum sequence number
                if(seq_num+packet_size > max_seq_num):
                    # Reset the sequence number to 1 and increment the sequence iterator
                    seq_num = 1
                    seq_iter += 1
                else:
                    seq_num = seq_num + packet_size # Otherwise, increment the sequence number by the packet size
                
                packets_made += 1 # Increment the number of packets made
                
                to_send.append(seq_num) # Add the sequence number to the list of packets to send
            
            # If there are no more packets to be made
            else:
                while( (len(to_send) <= window_size) and (len(dropped_pkt) > 0) ): # While there are less packets to send than the window size and there are dropped packets in the deque
                    to_send.append(dropped_pkt.popleft()) # Add the leftmost dropped packet to the list of packets to send
                
                break # Break out of the loop
                

        for pkt in to_send: # For each packet in the list of packets to send
            
            sent_count += 1 # Increment the count of sent packets

            if drop(): # If the packet is dropped
                
                dropped_pkt.append(pkt) # Add the packet to the deque of dropped packets
                is_dropped = True # Set is_dropped to True
                
                # Start a new thread to handle retransmission
                t = Thread(target = retrans_handler, args=(pkt, time.time(), seq_iter, ))
                t.start()
                
                if (window_size > 1): # If the window size is greater than 1
                    
                    window_size = int(window_size/2) # Set the window size to half of its current value
                    
                    t = Thread(target = report_window, args=(window_size, time.time(), )) # Start a new thread to report the new window size
                    t.start()

            # If the packet is not dropped, send it
            else:
                exp_acks += 1   # increment expected acknowledgments
                conn.sendall((str(pkt)+" ").encode())  # send the packet
                pkt_success_sent += 1  # increment successful packets sent

    
        conn.settimeout(0.5)

        # Wait for acknowledgments
        while(exp_acks>0):
            acks = []
            
            try:
                # Receive acknowledgments and decode them
                ack_str = (conn.recv(8192)).decode()
                acks = list(map(int, ack_str.split()))
            
            # If there is an error receiving acknowledgments
            except:
                exp_acks = 0
                
                # If the acknowledgments are not received, try to connect again
                if(not ack_str):
                    return try_connect()
                    
                break
    
            for ack in acks: # Loop through the received acknowledgments
                if(ack and window_size<2048): # If an acknowledgment is received and window size is less than 2048, increase the window size
                    window_size += 1
                    
                exp_acks -= 1  # decrement expected acknowledgments

        # Spawn a new thread to report the current window size
        t = Thread(target = report_window, args=(window_size, time.time(), ))
        t.start()

        conn.settimeout(None)

        # Print number of packets sent every 10th packet
        if(sent_count%10==0):
            print(f"{sent_count} packets sent...")

    # When all packets are sent, execute completion function and close all connections
    execution_complete()
    close_all()


# Define a function named try_connect without any parameters
def try_connect():
    global connected
    
    connected = False # Set the value of connected to False
    
    # Start a while loop that runs until connected is True
    try:
        while (connected is False):
            # Try to reconnect
            connect()
            # Pause the program execution for 1 second
            time.sleep(1)
            continue
    
    # If there's an exception while running the loop, call the execution_complete() function and then try to connect again
    except:
        execution_complete()
        try_connect()


def reset():
    global pkt_success_sent, sent_count, seq_num, window_size, to_send, dropped_pkt, track_drop, re_trans, seq_iter, packets_made

    # Reset all global variables to their default value

    pkt_success_sent = 0
    sent_count = 0
    seq_num = 70000
    window_size = 1
    to_send = []
    dropped_pkt = deque()
    track_drop = set()
    re_trans = [[], [], [], []]
    seq_iter = 0
    packets_made = 0   


# Define a function named execution_complete without any parameters
def execution_complete():
    global sent_count, re_trans, pkt_success_sent
 
    # If the number of packets successfully sent is greater than or equal to the total number of packets, print "Execution Completed"
    if(pkt_success_sent>=total_packets):
        print("Execution Completed")
    
    # Print the number of packets sent and the number of retransmissions for each of the first four sequence numbers
    print(f"Client IP: {socket.gethostbyname(socket.gethostname())}") # Use only if running on Windows PC
    print(f"Packets sent: {sent_count}")
    print(f"Number of Retransmissions:  1: {len(re_trans[0])}  2: {len(re_trans[1])}  3: {len(re_trans[2])}  4: {len(re_trans[3])}")


# Define a function named close_all without any parameters
def close_all():  
    global conn, drp_f, sender_window_size_f
    
    time.sleep(1) # Pause the program execution for 1 second
    
    # Close the drp_f, sender_window_size_f, and conn files/sockets/connections
    drp_f.close()
    sender_window_size_f.close()
    conn.close()



if __name__ == '__main__':
    # code starts here
    st = time.time()
    try_connect() # make a connection
    ed = time.time()
    print("Runtime: ", ed-st) # print total runtime

