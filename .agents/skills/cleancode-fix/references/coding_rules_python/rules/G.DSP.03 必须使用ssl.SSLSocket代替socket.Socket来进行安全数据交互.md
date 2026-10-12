# G.DSP.03 必须使用ssl.SSLSocket代替socket.Socket来进行安全数据交互

- **规则ID**：59656fa7-7533-4ef4-8be9-72bc7eb80df0
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

Python提供的socket.Socket类可用于创建套接字，传输敏感数据时应使用ssl.SSLSocket类创建安全套接字，该类提供了SSL/TSL等安全传输协议来确保传输通道不受攻击者的监听或恶意篡改。



SSLSocket类提供的主要保护包括：

1、完整性保护：SSL防止消息被主动窃取者篡改。

2、认证：在大多数模式下，SSL都对对端进行认证。服务器通常都被认证，如果服务器要求，客户端也可以被认证。

3、保密性：在大多数模式下，SSL对客户端和服务器之间传输的数据进行加密。这样保护了数据的隐私性，被动窃听器不能监听诸如财务或者个人信息等敏感信息。

**【正确示例】**

```
1、服务端：
import socket, ssl, time


# python 3.X begin
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(certfile="zxcert.pem", keyfile="zxkey.pem")
# python 3.X end
bindsocket = socket.socket()
print("socket create success")
bindsocket.bind(('127.0.0.1', 10023))
print("socket bind success")
bindsocket.listen(5)
print("socket listen success")


def do_something(connstream, data):
    print("data length:", len(data))
    return True


def deal_with_client(connstream):
    t_recv = 0
    t_send = 0
    n = 0
    t1 = time.clock()
    data = connstream.recv(1024)
    t2 = time.clock()
    print("receive time:", t2 - t1)
    # empty data means the client is finished with us
    while data:
        if not do_something(connstream, data):
            # we'll assume do_something returns False
            # when we're finished with client
            break
        n = n + 1
        t1 = time.clock()
        connstream.send(b'b' * 1024)
        t2 = time.clock()
        t_send += t2 - t1
        print("send time:", t2 - t1)
        t1 = time.clock()
        data = connstream.recv(1024)
        t2 = time.clock()
        t_recv += t2 - t1
        print("receive time:", t2 - t1)
    print("avg send time:", t_send / n, "avg receive time:", t_recv / n)


# finished with client
while True:
    newsocket, fromaddr = bindsocket.accept()
    print("socket accept one client")
    # python 3.X begin
    connstream = context.wrap_socket(newsocket, server_side=True)
    # python 3.X end
    try:
        deal_with_client(connstream)
    finally:
        connstream.shutdown(socket.SHUT_RDWR)
        connstream.close()

2、客户端：
import socket, ssl, pprint, time


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("socket create success")
# require a certificate from the server
ssl_sock = ssl.wrap_socket(s,
                           ca_certs="zxcert.pem",
                           cert_reqs=ssl.CERT_REQUIRED)
ssl_sock.connect(('127.0.0.1', 10023))
print("socket connect success")
pprint.pprint(ssl_sock.getpeercert())
# note that closing the SSLSocket will also close the underlying socket
n = 0
t_send = 0
t_recv = 0
while n < 10:
    n = n + 1
    t1 = time.clock()
    ssl_sock.send(b'a' * 100)
    t2 = time.clock()
    t_send += t2 - t1
    print("send time:", t2 - t1)
    t1 = time.clock()
    data = ssl_sock.recv(1024)
    t2 = time.clock()
    t_recv += t2 - t1
    print("receive time:", t2 - t1)
print("avg send time:", t_send / n, "avg receive time:", t_recv / n)
ssl_sock.close()

# 该正确代码示例应用ssl库使用SSL/TLS安全协议保护传输的报文。使用ssl的程序如果尝试连接不使用SSL的端口，那么这个程序将失败。同理，一个不使用ssl的程序如果要同一个使用SSL的端口建立连接也将失败。

```
**【错误示例】**

```
1、服务端：
# Echo server program
import socket


# Symbolic name meaning all available interfaces
HOST = ''
# Arbitrary non-privileged port
PORT = 50007
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
conn, addr = s.accept()
print('Connected by', addr)
while True:
    data = conn.recv(1024)
    if not data:
        break
    conn.sendall(data)
conn.close()

2、客户端：
# Echo client program
import socket


# The remote host
HOST = ''
# The same port as used by the server
PORT = 50007
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
s.sendall(b'Hello, world')
data = s.recv(1024)
s.close()
print('Received', repr(data))

【例外】
因为SSLSocket提供的报文安全传输机制性，将造成巨大的性能开销。在以下情况下，普通的套接字就可以满足需求：
1、套接字上传输的数据不敏感。
2、数据虽然敏感，但是已经过恰当加密。
3、套接字的网络路径没有越出信任边界。这种情况只有在特定的情况下才能发生，例如，套接字的两端都在同一个局部网络，而且整个网络都是可信的情况时。

```
**【修复建议】**
