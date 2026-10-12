# G.CLS.01-CPP 类的成员变量必须显式初始化

- **规则ID**：c0050be4-853e-462d-95f3-518cdbf8fac4
- **更新时间**：2025-03-25 19:23:07

---

**【问题级别】**

一般

**【描述】**

如果没有对类成员变量显式初始化，会使对象处于一种不确定状态。如果类的成员变量具有默认构造函数，那么可以不做显式初始化。

**【正确示例】**

```
一种做法是在类成员变量声明时显式初始化。

class Message {
public:
    void Process()
    {
        ...
    }

private:
    uint32_t msgId{0};
    size_t msgLength{0};
    unsigned char* msgBuffer{nullptr};
    std::string someIdentifier;        // 具有默认构造函数，不需要显式初始化
};
另一种做法是使用构造函数初始化列表初始化。

class Message {
public:
    Message() : msgId(0), msgLength(0), msgBuffer(nullptr) {}
    void Process()
    {
        ...
    }

private:
    uint32_t msgId;
    size_t msgLength;
    unsigned char* msgBuffer;
    std::string someIdentifier;        // 具有默认构造函数，不需要显式初始化
};

```
**【错误示例】**

```
class Message {
public:
    void Process()
    {
        ...
    }

private:
    uint32_t msgId;                    // 不符合：成员变量没有被初始化
    size_t msgLength;                  // 不符合：成员变量没有被初始化
    unsigned char* msgBuffer;          // 不符合：成员变量没有被初始化
    std::string someIdentifier;        // 默认构造函数仅会初始化该成员
};

Message message;                       // message成员变量没有被完全初始化
message.Process();                     // 后续使用存在隐患

```
**【修复建议】**

确保类成员都存在初始化
