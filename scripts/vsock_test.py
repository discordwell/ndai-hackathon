"""Direct vsock connection test to a running Nitro Enclave."""
import json
import socket
import struct
import sys

AF_VSOCK = 40

def main():
    cid = int(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    print("Connecting to CID=%d port=%d" % (cid, port))
    s = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
    s.settimeout(30)
    try:
        s.connect((cid, port))
        print("Connected!")

        # Send attestation request (32-byte nonce as required by NSM)
        import os
        nonce = os.urandom(32).hex()
        msg = json.dumps({"action": "get_attestation", "nonce": nonce}).encode()
        frame = struct.pack(">I", len(msg)) + msg
        s.sendall(frame)
        print("Sent attestation request (%d bytes)" % len(msg))

        # Read response header
        header = b""
        while len(header) < 4:
            chunk = s.recv(4 - len(header))
            if not chunk:
                print("Connection closed while reading header")
                return 1
            header += chunk
        length = struct.unpack(">I", header)[0]
        print("Response length: %d bytes" % length)

        # Read response body
        data = b""
        while len(data) < length:
            chunk = s.recv(min(4096, length - len(data)))
            if not chunk:
                print("Connection closed while reading body")
                return 1
            data += chunk

        resp = json.loads(data)
        status = resp.get("status", "unknown")
        print("Response status: %s" % status)
        if resp.get("attestation_doc"):
            doc = resp["attestation_doc"]
            fmt = resp.get("format", "unknown")
            print("Attestation doc: %d chars, format=%s" % (len(doc), fmt))
            print("SUCCESS: Got real NSM attestation from Nitro Enclave!")
        elif resp.get("error"):
            print("Error: %s" % resp["error"])
        else:
            print("Full response: %s" % json.dumps(resp)[:300])
        return 0

    except Exception as e:
        print("Error: %s" % e)
        return 1
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
