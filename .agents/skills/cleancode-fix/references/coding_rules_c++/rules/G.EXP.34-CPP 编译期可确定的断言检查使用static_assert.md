# G.EXP.34-CPP 编译期可确定的断言检查使用static_assert

- **规则ID**：144b3369-8bd5-4f38-9002-f9a9505e6943
- **更新时间**：2025-03-25 19:22:37

---

**【问题级别】**

一般

**【描述】**

C++11中引入了static_assert这个关键字，用来做编译期间的断言，因此叫做静态断言。

语法：static_assert(常量表达式，提示字符串);。

如果“常量表达式”的值为真(true或者非零值)，那么static_assert不做任何事情，否则会产生一条编译错误，错误位置就是该static_assert语句所在行，错误提示就是“提示字符串”。

**【正确示例】**

```
static_assert(sizeof(int) == 4, "system is not supported.");

```
**【错误示例】**

```
assert(sizeof(int) == 4);

```
**【修复建议】**

assert替换为static_assert
