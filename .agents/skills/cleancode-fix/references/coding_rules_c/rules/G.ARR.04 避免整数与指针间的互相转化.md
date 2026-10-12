# G.ARR.04 避免整数与指针间的互相转化

- **规则ID**：44464031-f0aa-4830-b6f3-f3136d5ba3f7
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

整数与指针之间互相转换的结果是由实现定义的。指针的大小随着平台的不同而不同，强行进行整数与 指针间的互相转换，降低了程序的兼容性，在转换过程中可能引起指针高位信息的丢失。

**【正确示例】**

```
char* p = ...
char* p2 = ...
uintptr_t number = reinterpret_cast<uintptr_t>(reinterpret_cast<void*>(p));
uintptr_t number2 = reinterpret_cast<uintptr_t>(reinterpret_cast<void*>(p2));

```
**【错误示例】**

```
char* p = ...
char* p2 = ...
// 直接将指针转换为uint32_t可能会超出uint32_t表示范围导致错误
uint32_t number = reinterpret_cast<uint32_t>(p);
// 将uintptr_t转换为uint32_t可能会发生数据截断导致错误
uint32_t number2 = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(p2));

```
**【修复建议】**
