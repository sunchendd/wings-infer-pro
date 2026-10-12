# G.EXP.20-CPP 确保有符号整数运算不溢出

- **规则ID**：dbb88478-2659-442b-90fe-ac70d48cc9c8
- **更新时间**：2025-03-25 19:23:11

---

**【问题级别】**

一般

**【描述】**

在C++标准中，有符号整数溢出会使程序产生未定义行为。

因此，不同的实现可以自由处理有符号整数溢出。例如：在将有符号整数类型定义为模数的实现中，编译器可以不检测整数溢出。



使用溢出后的数值可能导致程序缓冲区读写越界等风险。出于安全考虑，对外部数据中的有符号整数值在如下场景中使用时，需要确保运算不会导致溢出：



指针运算的整数操作数(指针偏移值)

数组索引

变长数组的长度(及长度运算表达式)

内存复制长度

内存分配函数的参数

循环判断条件

在精度低于int的整数类型上进行运算时，需要考虑整数提升。程序员还需要掌握整数转换规则，包括隐式转换规则，以便设计安全的算术运算。

**【正确示例】**

```
如下代码中，重构为使用size_t类型的变量表示数据长度，并校验外部数据长度是否在合法范围内。

unsigned char* content = ... //指向报文头的指针
size_t contentSize = ...     // 缓冲区的总长度
size_t totalLen = ...        // 报文总长度
size_t skipLen = ...         // 从消息中解析出来的需要忽略的数据长度

if (skipLen >= totalLen || totalLen > contentSize) {
    ... // 错误处理
}

std::vector<unsigned char> dest;
std::copy_n(&content[skipLen], totalLen - skipLen, std::back_inserter(dest));
...
一种改进方案是将second的类型修改为unsigned long类型，这种方案适用于修改了变量类型更符合业务逻辑的场景。

unsigned long second = ... // 将类型修改为 unsigned long 类型

if (second > (std::numeric_limits<unsigned long>::max() / 1000)) {
    return -1;
}
int millisecond = second * 1000;
...
另一种改进方案是将数值上限修改为std::numeric_limits<int>::max()。

int second = ... // 来自外部数据

if (second < 0 || second > (std::numeric_limits<int>::max() / 1000)) {
    return -1;
}
int millisecond = second * 1000;

```
**【错误示例】**

```
如下代码中，参与减法运算的整数是外部数据，在使用前未做校验，可能出现整数溢出，进而造成后续的内存复制操作出现缓冲区溢出。

unsigned char* content = ... // 指向报文头的指针
size_t contentSize = ...     // 缓冲区的总长度
int totalLen = ...           // 报文总长度
int skipLen = ...            // 从消息中解析出来的需要忽略的数据长度

std::vector<unsigned char> dest;

// 用 totalLen - skipLen 计算剩余数据长度，可能出现整数溢出
std::copy_n(&content[skipLen], totalLen - skipLen, std::back_inserter(dest));
...
如下代码中，对来自外部数据的数值范围做了校验，但是由于second是int类型，而校验条件中错误的使用了std::numeric_limits<unsigned long>::max()进行限制，导致整数溢出。

int second = ... // 来自外部数据

 // 错误的使用了unsigned long的取值范围做上限校验
if (second < 0 || second > (std::numeric_limits<unsigned long>::max() / 1000)) {
    return -1;
}
int millisecond = second * 1000; // 可能出现整数溢出
...

```
**【修复建议】**

1.整数之间运算时必须严格检查，确保不会出现溢出。

2.整数之间强制转换必须严格检查，确保不会出现截断
