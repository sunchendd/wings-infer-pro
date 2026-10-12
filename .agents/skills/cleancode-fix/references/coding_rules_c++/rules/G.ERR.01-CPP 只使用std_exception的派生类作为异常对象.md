# G.ERR.01-CPP 只使用std::exception的派生类作为异常对象

- **规则ID**：bbd45404-db85-487b-ab4d-224b218ec019
- **更新时间**：2025-03-25 19:22:38

---

**【问题级别】**

严重

**【描述】**

std::exception是C++标准库中的异常基类。程序中抛的异常应当是继承自这个类的派生类的实例。



特别地，不应该抛出或捕获基本类型（如int、char*等）的值，因为如果不同的组件都使用基本类型做为异常，那么同一个类型就会被用来表示不同的异常，导致无意中捕获到其他组件抛出的、不希望在本组件中捕获到的异常。

**【正确示例】**

```
class ResourceExhaustedException : public std::exception {
    ...
};

Resource* res = GetResource();
if (res == nullptr) {
    throw ResourceExhaustedException();
}

```
**【错误示例】**

```
Resource* res = GetResource();
if (res == nullptr) {
    throw "Resource exhausted";
}

```
**【修复建议】**

使用std::exception的派生类作为异常对象
