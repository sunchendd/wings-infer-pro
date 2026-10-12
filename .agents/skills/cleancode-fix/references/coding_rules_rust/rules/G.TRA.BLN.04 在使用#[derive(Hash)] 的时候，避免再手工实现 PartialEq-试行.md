# G.TRA.BLN.04 在使用#[derive(Hash)] 的时候，避免再手工实现 PartialEq-试行

- **规则ID**：3c7b4e49-4cef-471c-8b6a-8de27ff81813
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

严重

**【描述】**

实现 Hash 和 Eq 必须要满足下面一个等式：



k1 == k2  -> hash(k1) == hash(k2)

即，当k1 和 k2 相等时，hash(k1)也应该和 hash(k2) 相等。 所以要求 PartialEq / Eq / Hash 的实现必须保持一致。



如果用 #[derive(Hash)] 的时候，搭配了一个手工实现的 PartialEq 就很可能出现不一致的情况。



但也有例外。

**【正确示例】**

```
#[derive(PartialEq, Eq, Hash)]
struct Foo;

```
**【错误示例】**

```
#[derive(Hash)]
struct Foo;
impl PartialEq for Foo {
    ...
}

```
**【修复建议】**
