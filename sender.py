import socket
import sys
import threading
import random
import time
import struct
from dataclasses import dataclass
from collections import Counter

#Defintiions
localhost = "127.0.0.1"
BUF_SIZE = 1004 #Max data segment can be
MAX_SEQ = ((2**16))

DataType = {
    0: "DATA",
    1: "ACK",
    2: "SYN",
    3: "FIN"
}

DATA = 0
ACK = 1
SYN = 2
FIN = 3

@dataclass
class Control:
    """Control block: parameters for the sender program."""
    host: str                           # Hostname or IP address of the receiver
    sendport: int                       # Port number of the sender (this program)
    recvport: int                       # Port number of the receiver
    txtfilename: str                    #name of file being sent
    max_win: int                        #max_window size
    rto: int                            #retransmission time out
    flp: int                            #forward loss probability
    rlp: int                            #reverse loss proability
    socket: socket.socket               # Socket for sending/receiving messages
    start_time: float                   #Initial start_time for timestamps
    timer: threading.Timer = None       #timer thread
    dupACK = 0                          #Counter for duplicate ACKs
    dataSent: int = 0                   #Counter to keep track of data sent within window
    SynAcked: bool = False              #Flag indicating connection successful SYN and ACK (2 way handshake)
    ISN: int = 0                        #Initial Sequence Number
    totalDataAcked: int = 0             #Variables for the log
    totalSegmentsDropped: int = 0       # " "
    totalAcksDropped: int = 0           # " "
    totalRetransmitted: int = 0         # " "
    totalDupAcks:int = 0                # " "
    finACK: int = 0                     #Expected ACK for the Fin Packet sent
    terminate: bool = False             #terminate flag for the program
    AckList = []                        #List of all the Acks received.
    is_alive: bool = True               # Flag to signal the sender program to terminate

@dataclass
class Packet_list:
    sent = []


def parse_port(port_str, min_port=49152, max_port=65535):
    """
    Parse the port_str agrument and return int

    Args:
        port_str: string from arg

    Returns:
        int(port_str)
    """
    try:
        port = int(port_str)
    except ValueError:
        sys.exit(f"Invalid port argument, must be numerical: {port_str}")

    if not (min_port <= port <= max_port):
        sys.exit(f"Invalid port argument, must be between {min_port} and {max_port}: {port}")

    return port

def parse_max_win(str, min_win=1000):
    """
    Parse the ptr agrument and return int

    Args:
        str: string from arg

    Returns:
        int(str)
    """
    try:
        max_win = int(str)
    except ValueError:
        sys.exit(f"Invalid max_win argument, must be numerical: {str}")

    if not (max_win >= min_win):
        sys.exit(f"Invalid max_win argument, must be greater than or equal to {min_win}: {max_win}")

    return max_win

def parse_lp(str, start=0, end=1):
    """
    Parse the ptr agrument and return int

    Args:
        str: string from arg

    Returns:
        float(str)
    """
    try:
        lp = float(str)
    except ValueError:
        sys.exit(f"Invalid loss probability argument, must be numerical: {str}")

    if not (start <= lp <= end):
        sys.exit(f"Invalid loss probability, must be between {start} and {end} : {lp}")

    return lp

def parse_rto(str):
    """
    Parse the ptr agrument and return int

    Args:
        str: string from arg

    Returns:
        int(str)
    """
    try:
        rto = int(str)
    except ValueError:
        sys.exit(f"Invalid loss probability argument, must be numerical: {str}")

    return rto

def setup_socket(sendport, recvport):
    """
    set up the socket between receiver and sender ports

    Args:
        sendport: sender port (int)
        recvport: receiver port (int)

    Returns:
        socket.socket
    """
    #setup UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #Binding so Reciever can send ACK packets back
    sock.bind((localhost,sendport))

    #Connecting to Reciever to send packets to.
    sock.connect((localhost, recvport))

    return sock

def create_packet(typeNum, seqnum, data):
    """
    create packet in necessary format to send through socket.

    Args:
        typeNum: int
        seqnum: int
        data: str

    Returns:
        packet (Bytes)
    """
    # Ensure typeNum and seqnum are within the valid range
    typeNum = min(max(typeNum, 0), 4)
    seqnum = seqnum % MAX_SEQ

    # Pack the data into bytes
    packet_data = struct.pack("!HH", typeNum, seqnum) + data.encode('utf-8')

    return packet_data

def decode_packet(packet_data):
    """
    decode the given packet from bytes to necessary information

    Args:
        packet_data: packet in Bytes

    Returns:
        typeNum: int
        acknum: int
        data: str
    """

    # Unpack the first two bytes as unsigned short integers (2 bytes each)
    typeNum, acknum = struct.unpack("!HH", packet_data[:4])

    # Extract the data from the remaining bytes
    data = packet_data[4:].decode('utf-8')
    return typeNum, acknum, data


def listen_thread(control, log, p_list):
    """
    Entry point for the receiver program. Acts as the main function for the listen thread
    ACK packets will be sent here from the receiver.

    Args:
        control: class
        log: file
        p_list: class(list)

    Returns:

    """
    while control.is_alive:
        try:
            received_packet = control.socket.recv(BUF_SIZE)
        except BlockingIOError:
            continue    # No data available to read
        except ConnectionRefusedError:
            print(f"recv: connection refused by {control.host}:{control.sendport}, shutting down...", file=sys.stderr)
            control.is_alive = False
            break

        #Simulate packet loss of ACK:
        if simulate_packet_loss_rlp(received_packet, control, log):
            continue

        #Get information of Oldest UnACKed packet for further processing
        try:
            OldestTypeNum, OldestSeq, OldestData = decode_packet(p_list.sent[0])
        except:
            # In this case, all data has been sent. FIN has been sent and waiting for ACK back from receiver.
            typeNum, acknum, data = decode_packet(received_packet)
            log.write(f"rcv {round((time.time() - control.start_time)*1000,2)} ACK {acknum} 0\n")
            continue


        #Decode information of the received packet
        typeNum, acknum, data = decode_packet(received_packet)
        log.write(f"rcv {round((time.time() - control.start_time)*1000,2)} ACK {acknum} 0\n")
        control.AckList.append(acknum)

        #Determine if ACK recieved is for SYN or FIN
        if acknum == (control.ISN + 1):
            control.SynAcked = True
        elif acknum == control.finACK:
            control.terminate = True
            control.is_alive = False
            control.timer.cancel()
            break

        #If the received packet has the ACK that we expected to recieve. Update oldest UnACKed packet and move window.
        if (acknum == (OldestSeq + len(OldestData))%MAX_SEQ):
            control.dataSent = control.dataSent - 1000
            control.totalDataAcked += len(OldestData)
            p_list.sent.pop(0)
            control.timer.cancel()
            control.dupACK = 0
            reset_timer(control,p_list,log)
        elif acknum == OldestSeq:
            #If received packet has ACK(k) that matches previous ACK(k-1).
            control.dupACK += 1
        elif acknum > (OldestSeq + len(OldestData))%MAX_SEQ:
            #Cumulative ACK - If recieved ACK is greater than expected ACK, remove oldest until fully updated.
            while len(p_list.sent) > 1:
                prev_packet = p_list.sent[0]
                prevtypeNum, prevseqnum, prevdata = decode_packet(prev_packet)
                if prevseqnum == acknum:
                    break
                elif prevseqnum < acknum:
                    p_list.sent.pop(0)

                control.totalDataAcked += len(prevdata)

        #Fast Retransmit:
        if control.dupACK == 3:
            log.write(f"snd {round((time.time() - start_time)*1000,2)} {DataType[OldestTypeNum]} {OldestSeq} {len(OldestData)}\n")
            control.totalRetransmitted += 1
            control.dupACK = 0
            if simulate_packet_loss_flp(p_list.sent[0], control, log):
                continue
            control.socket.send(p_list.sent[0])


def timer_thread(control, p_list, log):
    """
    Function for the timer thread. This function will be called when the RTO expires.
    This function will attempt to retransmit the oldest unACKed packet. If the p_list.sent
    is empty, all the text data has been sent.

    Args:
        control: class
        log: file
        p_list: class(list)

    Returns:

    """
    try:
        OldestTypeNum, OldestSeq, OldestData = decode_packet(p_list.sent[0])
        log.write(f"snd {round((time.time() - start_time)*1000,2)} {DataType[OldestTypeNum]} {OldestSeq} {len(OldestData)}\n")
        control.totalRetransmitted += 1

        if not simulate_packet_loss_flp(p_list.sent[0], control, log):
            control.socket.send(p_list.sent[0])

    except:
        if control.terminate:
            return

    reset_timer(control, p_list,log)

def reset_timer(control,p_list,log):
    """
    Function to restart the timer thread every time RTO expires.

    Args:
        control: class
        log: file
        p_list: class(list)

    Returns:

    """
    # Create a new timer with the specified duration
    timer = threading.Timer(control.rto, timer_thread, args=(control,p_list,log))
    timer.start()
    # Store the timer reference in the control object
    control.timer = timer

def simulate_packet_loss_flp(packet, control, log):
    """
    Determines whether the forward packet should be dropped

    Args:
        control: class
        log: file
        p_list: class(list)

    Returns:
        bool
    """
    #random.random() generates number between 0.0 and 1.0
    typeNum, seqnum, data = decode_packet(packet)
    if random.random() < control.flp:
        log.write(f"drp {round((time.time() - control.start_time)*1000,2)} {DataType[typeNum]} {seqnum} {len(data)}\n")
        control.totalSegmentsDropped += 1
        return True
    else:
        return False

def simulate_packet_loss_rlp(packet, control, log):
    """
    Determines whether the reverse packet should be dropped

    Args:
        control: class
        log: file
        p_list: class(list)

    Returns:
        bool
    """
    #random.random() generates number between 0.0 and 1.0
    typeNum, acknum, data = decode_packet(packet)
    if random.random() < control.rlp:
        log.write(f"drp {round((time.time() - control.start_time)*1000,2)} {DataType[typeNum]} {acknum} {len(data)}\n")
        control.totalAcksDropped += 1
        return True
    else:
        return False


if __name__ == "__main__":
    #Parse arguments
    sendport = parse_port(sys.argv[1])
    recvport = parse_port(sys.argv[2])
    txtfilename = sys.argv[3]
    max_win = parse_max_win(sys.argv[4])
    rto = parse_rto(sys.argv[5])/1000
    flp = parse_lp(sys.argv[6])
    rlp = parse_lp(sys.argv[7])

    #Open files
    log = open("Sender_log.txt", "w")
    txtfile = open(txtfilename, "r")

    #Initialisation of Variables and Threads
    List = []
    totalDataSent = 0
    totalSegmentsSent = 0
    totalRetransmitted = 0

    start_time = time.time()
    sock = setup_socket(sendport, recvport)
    control = Control(localhost, sendport, recvport, txtfilename, max_win, rto, flp, rlp, sock, start_time)
    p_list = Packet_list() #used to keep track of oldest packets.

    listen = threading.Thread(target=listen_thread, args=(control,log,p_list))
    listen.start() #start listening

    reset_timer(control, p_list, log) #start initial timer

    #
    #Generate ISN (Initial Seq Number)
    ISN = random.randint(0, MAX_SEQ - 1)
    control.ISN = ISN
    GlobalSeqNum = (ISN + 1) % MAX_SEQ

    #Send Initial SYN to establish 2 way handshake
    send_packet = create_packet(SYN, ISN, ' ')
    p_list.sent.append(send_packet)
    control.dataSent = 1000
    log.write(f"snd 0.00 SYN {ISN} 0\n")
    sock.send(send_packet)

    while control.is_alive:
        if control.dataSent < control.max_win and control.SynAcked:
            control.dataSent = control.dataSent + 1000
            txt_data = txtfile.read(1000) #read up to 1000 bytes from text file

            if not txt_data:
                #No more Data to send
                while (totalDataSent != control.totalDataAcked - 1):
                    #Waiting to receive ACKS for all previously sent segments before sending FIN
                    continue

                control.finACK = (GlobalSeqNum + 1)%MAX_SEQ #the final expected ACK number for FIN.
                fin_packet = create_packet(FIN, GlobalSeqNum, ' ')
                p_list.sent.append(fin_packet)
                log.write(f"snd {round((time.time() - start_time)*1000,2)} FIN {GlobalSeqNum} 0\n")
                sock.send(fin_packet)
                while not control.terminate:
                    #wait til ACK is recieved for FIN
                    continue
                break

            #Create packet to send Data
            send_packet = create_packet(DATA, GlobalSeqNum, txt_data)
            totalDataSent = totalDataSent + len(txt_data)
            totalSegmentsSent = totalSegmentsSent + 1

            if send_packet not in p_list.sent:
                p_list.sent.append(send_packet)

            #Simulate packet loss:
            if simulate_packet_loss_flp(send_packet, control, log):
                GlobalSeqNum =  (GlobalSeqNum + len(txt_data)) % MAX_SEQ
                continue

            #Log and Send
            log.write(f"snd {round((time.time() - start_time)*1000,2)} DATA {GlobalSeqNum} {len(txt_data)}\n")
            GlobalSeqNum =  (GlobalSeqNum + len(txt_data)) % MAX_SEQ
            sock.send(send_packet)



    counter = Counter(control.AckList)
    for count in counter.values():
        if count > 1:
            control.totalDupAcks += count - 1

    time.sleep(0.1)
    log.write(f"\nOriginal data sent: {totalDataSent}\n")
    log.write(f"Original data acked: {control.totalDataAcked - 1}\n")
    log.write(f"Original segments sent: {totalSegmentsSent}\n")
    log.write(f"Retransmitted segments: {control.totalRetransmitted}\n")
    log.write(f"Dup acks received: {control.totalDupAcks}\n")
    log.write(f"Data segments dropped: {control.totalSegmentsDropped}\n")
    log.write(f"Ack segments dropped: {control.totalAcksDropped}\n")

    control.timer.cancel()
    listen.join()
    log.close()
    control.socket.close()


