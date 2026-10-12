# G.ERR.08 禁止通过异常泄露敏感数据

- **规则ID**：8c390be1-e684-44f9-84cc-b2a129349b6a
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

如果在传递异常的时候未对其中的敏感信息进行过滤，会导致信息泄露，可能帮助攻击者尝试发起进一步的攻击。攻击者可以通过构造恶意的输入参数来发掘应用的内部结构和机制。

异常中的错误信息，以及异常本身的类型都可能泄露敏感数据。

当异常会被传递到信任边界以外时，必须同时对敏感的异常信息和敏感的异常类型进行过滤。

需要注意，在某些场景下，不进行异常处理，反而会泄漏敏感数据，必须慎重审视跨信任边界的交互。

敏感数据的具体范围取决于产品的应用场景，产品应根据风险进行分析和判断。典型的敏感数据包括认证凭据、个人数据和通信内容等。

例如，在对公网用户开放的web服务接口，返回的错误信息中禁止包含ImportError和OSError等潜在泄漏内部文件目录结构的内容。

提供身份认证的函数，当发生用户名或密码认证失败时，返回的异常类型禁止明确标明是用户名错误或是密码错误，调用者如果捕获异常并将异常类型记录到日志中，攻击者可能结合日志文本，通过暴力探测获取用户名清单。

**【正确示例】**

```
import os
import sys
if len(sys.argv) != 2:
    print("Invalid file")
else:
    # 先把路径进行标准化
    try:
        truepath = os.path.realpath(sys.argv[1])
    except Exception as ex:
        print("Invalid file")
        sys.exit(1)
    # 校验路径是否以/home/python/开头
    if truepath.startswith('/home/python/'):
        try:
            open(truepath)
            ...
        except IOError:
            print("Invalid file")
    else:
        print("Invalid file")
在这个正确示例中，规定用户只能打开/home/python/目录下的文件，用户不可能发现这个目录以外的任何信息。
在这个方案中，如果无法打开文件，或者文件不在合法的目录下，则会产生一条简洁的错误消息。

```
**【错误示例】**

```
【反例1】异常的错误信息中包含了用户名和密码，敏感信息在上层调用捕获时可能被记录到日志中，存在泄漏风险。
def login_check(username, password):
    if not user_exists(username) or not user_password_match(username, password):
        raise UnauthorizedError('User %s or password %s is wrong.' % (username, password))
    ...

【反例2】虽然异常信息中没有包含敏感内容，但是异常类型泄漏了敏感数据，攻击者可以根据错误类型来获取有效的用户名清单。
def login_check(username, password):
    if not user_exists(username):
        raise UserNotExists()
    if not user_password_match(username, password):
        raise WrongPassword()
    ...

【反例3】这是一个HTTP-Server的处理函数，在传入一个文件名后，返回一个异常，则说明该文件不存在，而如果不抛出异常则说明该文件是存在的。该系统面临暴力攻击的风险，攻击者可以多次传入不同的文件名进行暴力碰撞来发现有效文件。
def request_handler(req):
    with open(req.body['file'], "r") as fd:
        ...

```
**【修复建议】**

当异常会被传递到信任边界以外时，必须同时对敏感的异常信息和敏感的异常类型进行过滤。
