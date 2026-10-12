# G.SER.02 禁止序列化未加密的敏感数据

- **规则ID**：c08de2f5-0c61-44f0-bc5d-8f66592c4b92
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

虽然序列化将对象的状态保存为一个字节序列，之后通过反序列化该字节序列又能重新构造出原来的对象，但是它并没有提供一种机制来保证序列化数据的安全性。可访问序列化数据的攻击者可以借此获取敏感信息并确定对象的实现细节。攻击者也可恶意修改其中的数据，试图在其被反序列化之后对系统造成危害。序列化并非加密存储，因此被序列化信息中不应该包括：密钥、数字证书、以及那些在序列化时引用敏感数据的类。此条规则的意义在于防止敏感数据被无意识的序列化导致敏感信息泄露。

**【正确示例】**

```
# 在将某个包含敏感数据的类序列化时，程序必须确保敏感数据不被序列化。这包括阻止包含敏感信息的数据成员被序列化，以及不可序列化或者敏感对象的引用被序列化。该示例使用__getstate__方法删除了特定数据，防止敏感信息被序列化。
class GPSLocation:
    def __init__(self, x, y, id):
        self.x = x
        self.y = y
        self.id = id

    def __getstate__(self):
        state = dict(self.__dict__)
        del state['x']
        del state['y']
        return state


dump_str = pickle.dumps(GPSLocation(1, 2, 3))
my_gps = pickle.loads(dump_str)

```
**【错误示例】**

```
# 在这段示例代码中，假定坐标信息是敏感的，那么将其序列化到数据流中使之面临敏感信息泄露与被恶意篡改的风险，下面明文存储，很容易被获取：

# b'\x80\x04\x957\x00\x00\x00\x00\x00\x00\x00\x8c\x08__main__\x94\x8c\x0bGPSLocation\x94\x93\x94)\x81\x94}\x94(\x8c\x01x\x94K\x01\x8c\x01y\x94K\x02\x8c\x02id\x94K\x03ub.'
class GPSLocation:
    def __init__(self, x, y, id):
        self.x = x
        self.y = y
        self.id = id

    def __getstate__(self):
        state = dict(self.__dict__)
        return state


dump_str = pickle.dumps(GPSLocation(1, 2, 3))
print(dump_str)

【例外】
可以序列化已正确加密的敏感数据。

```
**【修复建议】**
