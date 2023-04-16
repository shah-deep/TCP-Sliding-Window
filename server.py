"""
Deep Shah (SJSU ID: 016662932)
Athira Kumar (SJSU ID: 016597308)
"""


import socket
import threading
from threading import Thread
import time


pkt_rec_cnt = 0 # Count of packets received
total_packets = 10000000 # Total number of packets to be received
seq_num = 0 # Sequence number
packet_size = 4 # Packet size
max_seq_num = 65536 # Maximum sequence number
exp_sn = 1 # Expected sequence number (next to receive)
missing_packets = [] # List of missing packets
received_pkts = [] # List of received packets
good_put_store = [] # List of good put values
seq_nums = [] # List of sequence numbers
rec_buf = '' # Buffer for received packets
buffer_size = 8192 # Buffer size
min_buffer_size = 1024 # Minimum buffer size
max_buffer_size = 32768 # Maximum buffer size. Sequence numbers should be at least twice the buffer size
client_name = '' # Name of the client
st = time.time() # Start time


# Creating files to store data
rec_f = open(f"recv_seq_num_{int(time.time())}.csv", "w")
rec_f.write("seq_num,tm\n")
gp_f = open(f"good_put_{int(time.time())}.csv", "w")
gp_f.write("recv_pkt,sent_pkt,good_put\n")
rep_lock = threading.Lock()

# file for window size
receiver_window_size_f = open(f"receiver_window_size_{int(time.time())}.csv", "w")
receiver_window_size_f.write("receiver_window_size,tm\n")
win_lock = threading.Lock()

def set_connection():
    global serversocket, host
    """
    To set up initial connection 
    """
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    host = socket.gethostname() # Windows Local
    # host = "0.0.0.0" # Mac Local
    # host = socket.gethostbyname(socket.gethostname()) # 2 PCs
    port = 4001

    try :
        serversocket.bind((host, port)) # binding to port
    except socket.error as e :
        print(str(e))

    print("Waiting to connect...")

    serversocket.listen(5) # listening for client to connect

    print( "Listening on " + str(host) + ":" + str(port))


def connect():
    global conn, serversocket, pkt_rec_cnt, seq_num, exp_sn, missing_packets, received_pkts, good_put_store, seq_nums, rec_buf, buffer_size, rec_f, gp_f, rep_lock, client_name, st

    if(pkt_rec_cnt+(total_packets/100) > total_packets): # a check to see if execution is almost complete
        pkt_rec_cnt = total_packets
        execution_complete()
        return

    conn, address = serversocket.accept() # accept new connection
    # conn.setblocking(False)
    st = time.time()
    print('Connected to :', address)
    res = (conn.recv(2048)).decode() # get first response from new connection
    if(res[:3]=="SYN"): # see if it is a fresh client
        if((pkt_rec_cnt < 10) or (client_name != res[4:]) or (pkt_rec_cnt>(total_packets*0.99))):
            conn.sendall("NEW".encode()) # Ask client to start sending data
            client_name =  res[4:] # store client identity
            reset()

        else:
            conn.sendall("OLD".encode()) # If client got disconnected in between
            res = (conn.recv(2048)).decode() # Tell client that you will now send remaining data
            if(res[:3]=="SND"):
                data = '{' + f'"pkt_rec_cnt" : int({pkt_rec_cnt}), "seq_num" : int({seq_num})' + '}'
                conn.sendall(data.encode()) # Send data to sync with the client
                
    elif(res[:3]=="RCN"): # Client says that Server left in between
        conn.sendall("SND".encode()) # Tell client to send synchronisation data
        client_name =  res[4:]
        print("Syncing with the sender...")
        res = (conn.recv(4096)).decode() # Get info to sync
        if(res):
            data = eval(res)
            pkt_rec_cnt = data['pkt_success_sent'] # set the packets already received
            seq_num = data['seq_num'] # set the sequence numbers
            exp_sn = data['seq_num'] + packet_size

        else:
            print("Reconnect Failed!")

    else:
        print("Error: client failed to connect!")
        exit()

    try:
        process_packets() # Start receiving packets
    except Exception as e:
        print(str(e))



def reportPacketStats(rec_pkts, n_miss):
    global good_put_store, rec_f, gp_f, rep_lock

    rep_lock.acquire()
    for sq, tm in rec_pkts:
        rec_f.write(f"{sq},{tm}\n") # write received sequence number and time stamp to file

    n_recv = len(rec_pkts) # number of received packets
    n_sent = n_recv + len(missing_packets) # number of sent packets
    good_put = n_recv/n_sent # good put
    # print(f"Good Put = {n_recv}/{n_sent} = {good_put}")

    good_put_store.append(good_put) # store good put in an array
    gp_f.write(f"{n_recv},{n_sent},{good_put}\n") # store good put in a file

    rep_lock.release() 


def report_window(win_size, tm):
    global window_size_f, win_lock
    win_lock.acquire()
    receiver_window_size_f.write(f"{win_size},{tm}\n")
    win_lock.release()


def process_packets():
    global conn, pkt_rec_cnt, seq_num, exp_sn, missing_packets, received_pkts, good_put_store, seq_nums, rec_buf, buffer_size, st
    
    while (pkt_rec_cnt < total_packets):
        try:
            conn.settimeout(1) # set receive time out to 1 sec
            res = (conn.recv(buffer_size)).decode()
            conn.settimeout(None) # remove connection timeout
        except:
            return connect() # try to reconnect if error occured
            continue

        if(not res):
            print("No Res")
            return connect() # try to reconnect if no response received
            continue
            

        res_str = (res).split() # received string is space separated
        seq_nums = list(map(int, res_str)) # get integer sequence numbers from response

        if(rec_buf): # Check of half received packets stored in receive buffer
            if(len(seq_nums)>0):
                seq_nums[0] = int(rec_buf+res_str[0])
            else:
                seq_nums = list(map(int, rec_buf.split()))
                
            rec_buf = ''

        if(res[-1]!=" "): # if half received packet found, store it in buffer
            seq_nums.pop()
            rec_buf += res_str.pop()

        buffer_changed = False # check for changes in receive buffer size
        buffer_changed2 = False 

        for seq_num in seq_nums: # iterate through all received sequence numbers
            old_pkt = False # If missing pkt received
            if(seq_num!=exp_sn): # check id expected sequence number is not received
                if(seq_num in missing_packets): # if missing packet received, remove it from list
                    old_pkt = True
                    missing_packets.remove(seq_num)

                else:
                    # change buffer size if lost packet 
                    wait_cnt = 0
                    if((not buffer_changed) and ((buffer_size*2)<=max_buffer_size)):
                        buffer_changed = True
                        buffer_size = int(buffer_size*2) # double the buffer size if packets are missing
                        t = Thread(target = report_window, args=(buffer_size, time.time(), ))
                        t.start()

                    # add lost packets to missing packets list and update next expected sequence number
                    while(exp_sn!=seq_num):
                        if(wait_cnt>5):
                            break
                        wait_cnt+=1
                        missing_packets.append(exp_sn)  # add missing packets to list
                        exp_sn += packet_size
                        if(exp_sn > max_seq_num):
                            exp_sn = 1

            # if packets getting send without issue, increase the buffer size
            elif((not (buffer_changed or buffer_changed2)) and ((buffer_size/2)>=min_buffer_size)):
                buffer_changed2 = True
                buffer_size = int(buffer_size/2) # Half buffer size if 
                t = Thread(target = report_window, args=(buffer_size, time.time(), ))
                t.start()

            # for new packets, update next expected sequence number
            if(not old_pkt):
                exp_sn += packet_size
                if(exp_sn > max_seq_num):
                    exp_sn = 1

            received_pkts.append(tuple([seq_num, time.time()])) # save the received packets
            pkt_rec_cnt += 1
            conn.sendall((str(exp_sn)+" ").encode()) # send the received packets

            if(len(received_pkts)==1000):
                t = Thread(target = reportPacketStats, args=(received_pkts, len(missing_packets), ))
                t.start()
                received_pkts = []

        if(pkt_rec_cnt%100==0):
            print(f"Received {pkt_rec_cnt} packets...")
            if(pkt_rec_cnt%1000==0):
                print("Time so far: ", time.time()-st)
                # print(f"Exected Runtime: {(total_packets/pkt_rec_cnt*(time.time()-st)/60)} mins")
    
    
    execution_complete()
    close_all()


def reset():
    global pkt_rec_cnt, seq_num, exp_sn, missing_packets, received_pkts, good_put_store, seq_nums, rec_buf, buffer_size
 
    # Reset all global variables to their default value

    pkt_rec_cnt = 0
    seq_num = 0
    exp_sn = 1
    missing_packets = []
    received_pkts = []
    good_put_store = []
    seq_nums = []
    rec_buf = ''
    buffer_size = 8192


def execution_complete():
    global pkt_rec_cnt, good_put_store
    if(pkt_rec_cnt >= total_packets):
        print("Execution Completed")

    print(f"Server IP: {socket.gethostbyname(socket.gethostname())}") # Use only if running on Windows PC
    print(f"Packets received: {pkt_rec_cnt}") # print packets received
    if(len(good_put_store)>0):
        avg_gp = sum(good_put_store)/len(good_put_store) # calculate and print good put
        print(f"Average Good Put: {avg_gp}")


def close_all():
    global conn, rec_f, gp_f, conn, receiver_window_size_f

    time.sleep(1)
                    # Close files and connection
    rec_f.close()
    gp_f.close()
    conn.close()
    receiver_window_size_f.close()

if __name__ == '__main__':
    set_connection()
    connect()
    ed = time.time()
    print("Runtime: ", ed-st) # Print the total runtime
    
