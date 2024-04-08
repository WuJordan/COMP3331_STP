import socket
import sys
#Jasons Port:

localhost = "127.0.0.1"

#use port 57270 for sender
def parse_port(port_str, min_port=49152, max_port=65535):
    try:
        port = int(port_str)
    except ValueError:
        sys.exit(f"Invalid port argument, must be numerical: {port_str}")

    if not (min_port <= port <= max_port):
        sys.exit(f"Invalid port argument, must be between {min_port} and {max_port}: {port}")

    return port

def parse_max_win(str, min_win=1000):
    #unsigned integer
    try:
        max_win = int(str)
    except ValueError:
        sys.exit(f"Invalid max_win argument, must be numerical: {str}")

    if not (max_win >= min_win):
        sys.exit(f"Invalid max_win argument, must be greater than or equal to {min_win}: {max_win}")

    return max_win

def parse_lp(str, start=0, end=1):
    try:
        lp = float(str)
    except ValueError:
        sys.exit(f"Invalid loss probability argument, must be numerical: {str}")

    if not (start <= lp <= end):
        sys.exit(f"Invalid loss probability, must be between {start} and {end} : {lp}")

    return lp

def parse_rto(str):
    try:
        rto = int(str)
    except ValueError:
        sys.exit(f"Invalid loss probability argument, must be numerical: {str}")

    return rto

def setup_socket(sendport, recvport):
    #setup UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #Binding so Reciever can send ACK packets back
    sock.bind((localhost,sendport))

    #Connecting to Reciever to send packets to.
    sock.connect((localhost, recvport))

    return sock


if __name__ == "__main__":
    #Parse Args:
    #Sender Port, Reciever Port, Txt_file_to_send, max_win, rto, flp, rlp
    sendport = parse_port(sys.argv[1])
    recvport = parse_port(sys.argv[2])
    txtfilename = sys.argv[3]
    max_win = parse_max_win(sys.argv[4])
    rto = parse_rto(sys.argv[5])
    flp = parse_lp(sys.argv[6])
    rlp = parse_lp(sys.argv[7])


    #Set up sockets and connect.
    # Bind before you connect
#bind to sender port
# connect to reciever
    sock = setup_socket(sendport, recvport)

    sock.send("12345678910".encode())


