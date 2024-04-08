import socket
import sys

localhost = "127.0.0.1"
wait_time = 10

#use port 57271 for receiver

def parse_port(port_str, min_port=49152, max_port=65535):
    try:
        port = int(port_str)
    except ValueError:
        sys.exit(f"Invalid port argument, must be numerical: {port_str}")

    if not (min_port <= port <= max_port):
        sys.exit(f"Invalid port argument, must be between {min_port} and {max_port}: {port}")

    return port\

def parse_max_win(str, min_win=1000):
    #unsigned integer
    try:
        max_win = int(str)
    except ValueError:
        sys.exit(f"Invalid max_win argument, must be numerical: {str}")

    if not (max_win >= min_win):
        sys.exit(f"Invalid max_win argument, must be greater than or equal to {min_win}: {max_win}")

    return max_win

def setup_socket(sendport, recvport):
    #setup UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #Binding so Sender can send packets
    sock.bind((localhost, recvport))
    sock.settimeout(wait_time) #set timeout to 10 seconds

    #Connecting to Sender to send ACK packets to.
    sock.connect((localhost, sendport))

    return sock

if __name__ == "__main__":

    recvport = parse_port(sys.argv[1])
    sendport = parse_port(sys.argv[2])
    txtfilename = sys.argv[3]
    max_win = parse_max_win(sys.argv[4])

    sock = setup_socket(sendport, recvport)

    while True:
        try:
            buf = sock.recv(1024)
        except socket.timeout:
            print(f"No data within {wait_time} seconds, shutting down.")
            break

        print(f"recieved from buf: {buf.decode()}")

sys.exit(0)


