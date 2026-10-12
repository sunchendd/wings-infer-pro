# G.STD.07-CPP 禁止使用std::string存储敏感信息

- **规则ID**：9de438f8-4c8d-453f-b1c2-743e010694a9
- **更新时间**：2025-03-25 19:24:17

---

**【问题级别】**

严重

**【描述】**

std::string类是C++内部定义的字符串管理类，如果口令等敏感信息通过std::string进行操作，在程序运行过程中，敏感信息可能会散落到内存的各个地方，并且无法清除。

**【正确示例】**

```
void test_good()
{
    string str = getstr();
    func(str);
}

```
**【错误示例】**

```
如下代码中，Foo函数中获取密码，保存到std::string变量password中，随后传递给VerifyPassword函数，在这个过程中，password实际上在内存中出现了两份。

bool VerifyPassword(std::string password)
{
    ...
}

void Foo()
{
    std::string password = GetPassword();
    if (!VerifyPassword(password)) {
        ... // 错误处理
    }
    ...
}

```
**【修复建议】**

严禁使用string类存储敏感信息，关键字包括password、psw、pwd、passwd。
