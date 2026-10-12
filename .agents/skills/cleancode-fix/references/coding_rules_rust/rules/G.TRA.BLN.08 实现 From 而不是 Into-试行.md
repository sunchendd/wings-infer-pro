# G.TRA.BLN.08 实现 From 而不是 Into-试行

- **规则ID**：9bd7f012-3b16-4381-bc41-6d1ac5e20f4d
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

优先为类型实现 From 而非 Into。因为实现了 From，Into 也会被自动实现。并且在错误处理的时候，? 操作符会通过调用 From 实现自动进行错误类型转换。



但是在泛型限定上，优先 Into 。



当然，也存在例外。

**【正确示例】**

```
struct StringWrapper(String);
impl From<String> for StringWrapper {
    fn from(s: String) -> StringWrapper {
        StringWrapper(s)
    }
}

```
**【错误示例】**

```
struct StringWrapper(String);
impl Into<StringWrapper> for String {
    fn into(self) -> StringWrapper {
        StringWrapper(self)
    }
}

```
**【修复建议】**
