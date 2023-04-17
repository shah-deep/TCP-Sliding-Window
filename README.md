# TCP Sliding Window

This project demonstrates TCP Sliding Window protocol using client-server communication. Code is implemented using python socket programming.


## Client

Once the client connects to the server, it sends packets to the server and drops them with 1% probability. For sake of simplicity, the data of packets are sequence numbers. The client keeps a track of dropped sequence numbers and resends the dropped packets after every 4000 sequence numbers. During all retransmissions, packets are again dropped with 1% probability.

If the server stops running during the transmission, clients tries to reconnect. Once server is running again, the client connects and continues sending data from where it stopped previously.

Code: [Client.py](/client.py)


## Server

Server receives packets from the client and sends acknowledgement for packet received. It also keeps tracks of missing packets and calculates good put after every 1000 packets received.

If client stops running during the transmission, the server waits for it to reconnect. Once client reconnects, it asks the client to send data from where it stopped earlier.

Code: [Server.py](/server.py)


## Report

 [Project Report (Link)](/CCS%20Project%20Report.pdf) shows screen shots of final output when client tries to send 10,000,000 packets to the server. It also shows plots for sequence numbers received, sequence numbers dropped, change in sender window size, and change in receiver buffer size against time. Data used for these plots is stored in the [Output Folder](/Output%20csv) in csv format.
 
 
