# G.TRA.BLN.05 在使用#[derive(Ord)] 的时候，避免再手工实现 PartialOrd-试行

- **规则ID**：c10ecf46-bbf4-4b0e-a337-30e5a609a478
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

严重

**【描述】**

跟实现 Hash 和 Eq 的要求类似，对于实现 Ord 的类型来说，必须要满足下面一个等式：



k1.cmp(&k2) == k1.partial_cmp(&k2).unwrap()

所以要求与 PartialOrd 的实现必须保持一致，并确保max、min和clamp与cmp一致。



通过#[derive(Ord)] 并手动实现PartialOrd，很容易意外地使cmp和partial_cmp不一致。



但也有例外。

**【正确示例】**

```
#[derive(Ord, PartialOrd, PartialEq, Eq)]
struct Foo;
// or
#[derive(PartialEq, Eq)]
struct Foo;
impl PartialOrd for Foo {
    fn partial_cmp(&self, other: &Foo) -> Option<Ordering> {
       Some(self.cmp(other))
    }
}
impl Ord for Foo {
    ...
}

```
**【错误示例】**

```
#[derive(Ord, PartialEq, Eq)]
struct Foo;
impl PartialOrd for Foo {
    ...
}

```
**【修复建议】**
