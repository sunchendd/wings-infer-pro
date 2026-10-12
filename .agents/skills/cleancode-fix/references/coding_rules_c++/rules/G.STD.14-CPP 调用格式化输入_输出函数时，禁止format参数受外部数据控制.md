# G.STD.14-CPP 调用格式化输入/输出函数时，禁止format参数受外部数据控制

- **规则ID**：51e7f319-fa7f-4ce4-87c6-a58bff67ece3
- **更新时间**：2025-03-25 19:23:31

---

**【问题级别】**

一般

**【描述】**

调用格式化函数时，如果format参数由外部数据提供，或由外部数据拼接而来，会造成格式化字符串漏洞。以C标准库的格式化输出函数为例，当其format参数外部可控时，攻击者可以使用%n转换符向指定地址写入一个整数值、使用%x或%d转换符查看栈或寄存器内容、使用%s转换符造成进程崩溃等。



调用格式化函数时，应使用常量字符串作为格式串，禁止格式串外部可控。常见格式化函数有：



格式化输出函数: sprintf, vsprintf, snprintf, vsnprintf等等

格式化输入函数: sscanf, vsscanf, fscanf, vscanf等等

格式化错误消息函数: err(), verr(), errx(), verrx(), warn(), vwarn(), warnx(), vwarnx(), error(), error_at_line()

格式化日志函数: syslog(), vsyslog()

C++20提供的std::format()

**【正确示例】**

```
如下代码中，使用%s转换符打印外部数据，避免格式化字符串漏洞。

void Foo()
{
    std::string msg = GetMsg();
    ...
    syslog(priority, "%s", msg.c_str()); // 符合：这里没有格式化字符串漏洞  
}

```
**【错误示例】**

```
如下代码中，使用syslog函数直接打印外部数据，可能出现格式化字符串漏洞。

void Foo()
{
    std::string msg = GetMsg();
    ...
    syslog(priority, msg.c_str());       // 不符合：存在格式化字符串漏洞  
}

```
**【修复建议】**

调用格式化函数时，应使用常量字符串作为格式串，禁止格式串外部可控。
