# G.STD.03-CPP 禁止从空指针创建std::string

- **规则ID**：212635bc-8ee5-45e5-a004-487c7715ad1c
- **更新时间**：2025-03-25 19:23:24

---

**【问题级别】**

严重

**【描述】**

将空指针传递给std::string构造函数，会解引用空指针，从而导致程序产生未定义行为。（注：该规范条款由SecB_NullReturns工具规则看护，工具规则检查范围大于此条规范要求。SecB_NullReturns工具规则不仅仅检查空指针作为std::string参数的场景，也会检查空指针以其他方式解引用的场景，故需根据实际情况处理工具告警）

**【正确示例】**

```
void Foo()
{
    const char* path = std::getenv("PATH");
    if (path == nullptr) {
        ...                                 // 错误处理
        return;
    }
    std::string str{path};
    ...
    std::cout << str << std::endl;
}

```
**【错误示例】**

```
void Foo()
{
    const char* path = std::getenv("PATH");
    std::string str{path};                  // 错误：这里没有判断getenv的返回值是否为nullptr
    std::cout << str << std::endl;
}

```
**【修复建议】**

指针可能为空需要及时判空并做错误处理
