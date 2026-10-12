# G.STD.05-CPP 确保用于字符串操作的缓冲区有足够的空间容纳字符数据和结束符，并且字符串以null结束符结束

- **规则ID**：630e17a2-2cbd-4422-a928-1ee386a50f38
- **更新时间**：2025-03-25 19:23:25

---

**【问题级别】**

致命

**【描述】**

C风格字符串是一个连续的字符序列，由字符序列中的第一个出现的null字符终止并包含该null字符。



复制或存储C风格字符串时，必须确保缓冲区有足够的空间容纳字符序列包括null结束符，并且字符串以null结束符结束，否则可能会导致缓冲区溢出问题：



优先使用std::string表示字符串，std::string表示字符串操作更简便，更容易被正确的使用，避免由于C风格字符串使用不当而导致溢出、没有null结束符的问题

使用C/C++标准库提供的C风格字符串操作函数时，需要确保输入的字符串以null结束符结束、不能超出字符串缓冲区的范围读写字符串、确保进存储操作后的字符串以null结束符结束

**【正确示例】**

```
char buf[BUFFER_SIZE] = {0};
std::cin.width(sizeof(buf) - 1); // 注意需要缓冲区长度-1，以留出字符串末尾'\0'的空间
std::cin >> buf;
void Foo(std::istream& in)
{
    char buffer[BUFFER_SIZE];

    if (!in.read(buffer, sizeof(buffer)) { // 注意in.read()不能保证'\0'结尾
        ... // 错误处理
        return;
    }

    std::string str(buffer, in.gcount()); // 让std::string构造函数，只读取指定长度的字符内容
    ...
}
void Foo(std::istream& in)
{
    std::string s;
    in.width(MAX_NEED_SIZE);
    in >> s;                             // 符合：已经限制读取的最大长度
    ...
}

```
**【错误示例】**

```
char buf[BUFFER_SIZE];
std::cin >> buf;
void Foo(std::istream& in)
{
    char buffer[BUFFER_SIZE];
    if (!in.read(buffer, sizeof(buffer))) { // 注意：in.read()不能保证'\0'结尾
        ... // 错误处理
        return;
    }

    std::string str(buffer);                // 不符合：字符串没有结尾的'\0'
    ...
}
void Foo(std::istream& in)
{
    std::string s;
    in >> s;                    // 不符合：没有限制待读取的长度，可能导致资源消耗或攻击
    ...
}

```
**【修复建议】**

确保字符串以'\0'结尾。
