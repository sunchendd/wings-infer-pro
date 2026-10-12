# SecPy_VF_Server_Side_Request_Forgery

- **规则ID**：b2a71352-3afa-495e-b75d-a8aeacdbf42d
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

SSRF（Server-Side RequestForgery, 服务端请求伪造）利用漏洞可以发起网络请求来攻击内网服务，故在server端发起用户输入的请求前，都要严格校验用户输入的内容。当攻击者可以影响应用程序服务器建立的网络连接时，将会发生 Server-Side Request Forgery。网络连接源自于应用程序服务器内部 IP 地址，因此攻击者将可以使用此连接来避开网络控制，并扫描或攻击没有以其他方式暴露的内部资源。

**【正确示例】**

```
```
# 域名、IP白名单
domainWhiteList = config.get_domainWhiteList()

def verify(data):
    data = data.replace('
', '_').replace('\r', '_')
    if data in domainWhiteList:
        return data
    else:
        return False

def try_connect(ip_address):
	try:
		port = get_mgmt_ir_port()
		ip_address = verify(ip_address)
		if common.check_ip(ip_address) and re.match('^[0-9]+$', port):
			sock = socket.create_connection((ip_address, port), 20)
			sock.close()
			return True
		else:
			return False
```

```
**【错误示例】**

```
```
def verify(data):
    data = data.replace('
', '_').replace('\r', '_')
    if data in domainWhiteList:
        return data
    else:
        return False


def good_case():
    try:
        ip_address = input()
        port = get_mgmt_ir_port()
        if check_ip(ip_address) and re.match('^[0-9]+$', port):
            ip_verify = verify(ip_address)
            sock = socket.create_connection((ip_verify, port), 20)
            sock.close()
            return True
        else:
            return False
    except Exception:
        return False
```

```
**【修复建议】**

服务端使用不可信的url地址发起网络请求时，应使用白名单的方式对协议、域名/IP、端口进行严格限制，防止产生安全漏洞。例如：仅允许HTTP和HTTPS请求，防止类似于file://、gopher://、ftp://等协议引起安全问题（需要获取非HTTP资源的业务例外，例如流媒体的RTMP协议）；将内网的所有IP地址排除在白名单之外，防止攻击者将存在缺陷的Web服务器当成代理，来间接攻击内网应用或嗅探内网服务。
