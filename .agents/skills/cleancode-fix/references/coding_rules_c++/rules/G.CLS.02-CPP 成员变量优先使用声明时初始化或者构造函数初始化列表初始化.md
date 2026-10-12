# G.CLS.02-CPP 成员变量优先使用声明时初始化或者构造函数初始化列表初始化

- **规则ID**：73f9aaa7-6677-41c2-a5d7-fc51518f08d5
- **更新时间**：2025-03-25 19:22:04

---

**【问题级别】**

一般

**【描述】**

C++11的声明时初始化可以一目了然的看出成员初始值，应当优先使用。如果成员初始化值和构造函数相关，或者不支持C++11，则应当优先使用构造函数初始化列表来初始化成员。相比起在构造函数体中对成员赋值，初始化列表的代码更简洁，执行性能更好，而且可以对const成员和引用成员初始化。



注意：构造函数初始化列表中的变量初始化顺序应该与成员变量的声明顺序一致。

**【正确示例】**

```
class Message {
public:
    ...

private:
    uint32_t msgId{0};
    size_t msgLength{0};
    unsigned char* msgBuffer{nullptr};
};
class Message {
public:
    Message() : msgId(0), msgLength(0), msgBuffer(nullptr) {}

private:
    uint32_t msgId;
    size_t msgLength;
    unsigned char* msgBuffer;
};

```
**【错误示例】**

```


```
**【修复建议】**

使用构造函数初始化列表进行初始化
