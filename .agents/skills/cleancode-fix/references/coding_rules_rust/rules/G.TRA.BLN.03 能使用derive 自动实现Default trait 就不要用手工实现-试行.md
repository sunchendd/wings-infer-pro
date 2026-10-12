# G.TRA.BLN.03 能使用derive 自动实现Default trait 就不要用手工实现-试行

- **规则ID**：71e07d9e-fe8f-4b52-91c8-aea69da0d9d1
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

手工实现 Default，代码不精炼。

**【正确示例】**

```
#[derive(Default)]
struct Foo {
    bar: bool
}

```
**【错误示例】**

```
struct Foo {
    bar: bool
}
impl std::default::Default for Foo {
    fn default() -> Self {
        Self {
            bar: false
        }
    }
}

```
**【修复建议】**
