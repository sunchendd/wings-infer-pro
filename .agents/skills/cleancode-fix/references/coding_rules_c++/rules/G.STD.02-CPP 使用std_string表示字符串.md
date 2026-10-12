# G.STD.02-CPP 使用std::string表示字符串

- **规则ID**：935e8bae-f8e0-46bd-b8bd-a101ad4e9f3b
- **更新时间**：2025-03-25 19:22:58

---

**【问题级别】**

一般

**【描述】**

使用std::string代替char*表示字符串有很多优势，例如：



不用考虑结尾的'\0'

std::string 能够复制，渐进扩容，可以直接使用+、=、==等操作符，并提供许多有用的字符串操作函数

不需要考虑内存分配操作，避免了显式的new/delete，以及由此导致的错误

需要注意的是某些STL实现中std::string是基于写时复制策略的，这会带来两个问题，一是某些版本的写时复制策略没有实现线程安全，在多线程环境下会引起程序错误；二是当与动态链接库互相传递基于写时复制策略的std::string时，由于引用计数在动态链接库被卸载时无法减少可能导致悬挂指针。因此，慎重选择一个可靠的STL实现对于保证程序稳定是很重要的。



C++17开始增加了std::string_view类型，该类型可以减少字符串复制操作，提升程序性能。在C++17及之后的版本中，建议使用std::string_view表示字符串常量，在C++17之前可以使用C风格的字符串常量。

**【正确示例】**

```
std::string defaultMsg{"hello"};
std::string msg = defaultMsg + " world";
…

```
**【错误示例】**

```
char defaultMsg[] = "hello";
char msg[MSG_SIZE];
int ret = sprintf_s(msg, sizeof(msg), "%s world", defaultMsg); // 使用C字符处理函数
…

```
**【修复建议】**

使用std::string来表示字符串
