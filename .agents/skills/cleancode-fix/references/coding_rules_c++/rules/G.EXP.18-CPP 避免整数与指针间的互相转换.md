# G.EXP.18-CPP 避免整数与指针间的互相转换

- **规则ID**：3ebf0446-36f1-4d53-886e-942d99e93820
- **更新时间**：2025-03-25 19:23:42

---

**【问题级别】**

一般

**【描述】**

整数与指针之间互相转换的结果是由实现定义的。指针的大小随着平台的不同而不同，强行进行整数与指针间的互相转换，降低了程序的兼容性，在转换过程中可能引起指针高位信息的丢失。



因此，当代码中出现指针和整数互转的情况，首先考虑是否能通过修改代码避免转换。如果必须做转换，建议使用uintptr_t或intptr_t类型存放转换后的指针值。

**【正确示例】**

```
如下代码中，使用uintptr_t类型接收转换后的指针。

char* p = ...
intptr_t number = reinterpret_cast<intptr_t>(p);
uintptr_t number2 = reinterpret_cast<uintptr_t>(p);

```
**【错误示例】**

```
当指针为64位时，转换后的数值可能不在uint32_t类型的值域范围内，导致错误。

char* p = ...

// 直接将指针转换为uint32_t可能会超出uint32_t表示范围导致错误  
uint32_t number = reinterpret_cast<uint32_t>(p);

// 将uintptr_t转换为uint32_t可能会发生数据截断导致错误  
uint32_t number2 = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(p));

```
**【修复建议】**

1、不要进行指针和整型(int, long, long long及他们的无符号类型)之间的强转；

2、如果因为以前代码设计不当导致必须指针和整型(int, long, long long及他们的无符号类型)之间强转的场景，需要重新设计整数的类型为uintptr_t。
