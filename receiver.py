import socket
import sys
import struct
import time
import threading
from dataclasses import dataclass
from collections import Counter

localhost = "127.0.0.1"
wait_time = 10
BUF_SIZE = 1004

MAX_SEQ = ((2**16))

DATA = 0
ACK = 1
SYN = 2
FIN = 3

@dataclass
class Control:
    alive: bool = True
    timerOn: bool = False
    timer: threading.Timer = None
    sock: socket.socket= None




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

    #Binding so Sender can send packets
    sock.bind((localhost, recvport))
    sock.settimeout(wait_time) #Initial timeout = 10s

    #Connecting to Sender to send ACK packets to.
    sock.connect((localhost, sendport))

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
    typeNum, seqnum = struct.unpack("!HH", packet_data[:4])

    # Extract the data from the remaining bytes
    data = packet_data[4:].decode('utf-8')
    return typeNum, seqnum, data

def timer_thread(control):
    """
    Function for the timer thread. This function will be called when the timer expires.
    This function will set the alive flag to False, to terminate the program.

    Args:
        control: class

    Returns:

    """
    control.alive = False


if __name__ == "__main__":

    #Initialisations of Varibales and Threads
    buffer = []
    SeqList = []
    alive = True
    start_time = 0
    ExpectedSeqNum = 0
    OriginalDataReceived = 0
    OriginalSegmentsReceived = 0
    DupDataReceived = 0
    DupAcksSent = 0

    control = Control()
    control.timer = threading.Timer(2, timer_thread, args=(control,))

    #Parsing arguments
    recvport = parse_port(sys.argv[1])
    sendport = parse_port(sys.argv[2])
    txtfilename = sys.argv[3]
    max_win = parse_max_win(sys.argv[4])
    control.sock = setup_socket(sendport, recvport)

    #Opening Files
    writefile = open(txtfilename, "w")
    log = open("Receiver_log.txt", "w")

    while control.alive:
        try:
            received_packet = control.sock.recv(BUF_SIZE)
        except socket.timeout:
            continue

        #Decode received packet from sender
        typeNum, seqnum, data = decode_packet(received_packet)
        SeqList.append(seqnum)

        if typeNum == SYN:
            start_time = time.time()
            log.write(f"rcv 0.00 SYN {seqnum} 0\n")
            packet = create_packet(ACK, seqnum + 1, '')

            #Next Packet we receive should have the ExpectedSeqNum of:
            ExpectedSeqNum = (seqnum + 1) % MAX_SEQ
            log.write(f"snd {round((time.time() - start_time)*1000,2)} ACK {seqnum + 1} 0\n")

        elif typeNum == DATA:
            log.write(f"rcv {round((time.time() - start_time)*1000,2)} DATA {seqnum} {len(data)}\n")

            if seqnum != ExpectedSeqNum:
                if received_packet not in buffer:
                    buffer.append(received_packet)

                packet = create_packet(ACK, ExpectedSeqNum, '') #send duplicate ACK
                DupAcksSent += 1
                log.write(f"snd {round((time.time() - start_time)*1000,2)} ACK {ExpectedSeqNum} 0\n")
            else:
                #got the expected seq num, put into file, check buffer and add to file, send next ack
                OriginalDataReceived += len(data)
                OriginalSegmentsReceived += 1
                packet = create_packet(ACK, seqnum + len(data), '')
                ExpectedSeqNum = (seqnum + len(data)) % MAX_SEQ
                writefile.write(data)

                while buffer: #while buffer is NOT emtpy, write in order buffered packets to file.
                    next_packet = buffer.pop(0)
                    BufftypeNum, Buffseqnum, Buffdata = decode_packet(next_packet)
                    if (Buffseqnum == ExpectedSeqNum):
                        OriginalDataReceived += len(Buffdata)
                        OriginalSegmentsReceived += 1
                        ExpectedSeqNum = (Buffseqnum + len(Buffdata)) % MAX_SEQ #update ExpectedSeqNum
                        packet = create_packet(ACK, Buffseqnum + len(data), '') #update ack packet to send
                        writefile.write(Buffdata)
                    else:
                        break

                log.write(f"snd {round((time.time() - start_time)*1000,2)} ACK {seqnum + len(data)} 0\n")
        elif typeNum == FIN:
            if not control.timerOn:
                control.timerOn = True
                control.sock.settimeout(2) #MSL *2 = 2
                control.timer.start()

            log.write(f"rcv {round((time.time() - start_time)*1000,2)} FIN {seqnum} 0\n")
            packet = create_packet(ACK, seqnum + 1, '')
            ExpectedSeqNum = (seqnum + 1) % MAX_SEQ
            log.write(f"snd {round((time.time() - start_time)*1000,2)} ACK {seqnum + 1} 0\n")

        control.sock.send(packet)

counter = Counter(SeqList)
for count in counter.values():
    if count > 1:
        DupDataReceived += count - 1

time.sleep(0.1)
log.write(f"\nOriginal data received: {OriginalDataReceived}\n")
log.write(f"Original segments received: {OriginalSegmentsReceived}\n")
log.write(f"Dup data segments received: {DupDataReceived}\n")
log.write(f"Dup ack segments sent: {DupAcksSent}\n")

writefile.close()
control.timer.cancel()
sys.exit(0)


