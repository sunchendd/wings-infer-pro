# G.TRA.01 在实现相等性、排序和散列类 trait 时，应保证一致性

- **规则ID**：9185640f-ec56-4bc9-9db3-8540ed497de4
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

在手动实现 Hash 和 PartialEq/Eq 时必须要满足等式 (k1 == k2) == (hash(k1) == hash(k2))，即当k1 和 k2 相等时，hash(k1) 也应该和 hash(k2) 相等。



在手动实现 PartialOrd 和 Ord 时则必须要满足等式 k1.cmp(&k2) == k1.partial_cmp(&k2).unwrap()。



若类型实现了 Borrow trait，也应保证上述等式对借用后的类型同样成立，即:

hash(k1) == hash(k2) 等效于 hash(k1.borrow()) == hash(k2.borrow()), 且

k1.borrow().cmp(&k2.borrow()) 等效于 k1.borrow().partial_cmp(&k2.borrow()).unwrap();



通常情况下，可以通过 derive 属性宏来自动实现这些 traits。但相等性，排序和散列在不同应用场景可能存在不同的定义，又或是因为依赖的某种类型未实现其中一个 trait 而不能使用 derive 时，就需要开发者手动实现以上 traits，这时就要注意保持一致性。



一旦不一致，可能导致出现非预期的函数行为。

**【正确示例】**

```
```
#[derive(Hash, PartialEq, Eq)]
struct Employee {
    uid: u32,
    name: String,
}
```

```
**【错误示例】**

```
```
#[derive(Hash, Eq)]
struct Employee {
    uid: u32,
    name: String,
}
impl PartialEq for Employee {
    fn eq(&self, other: &Self) -> bool {
        self.uid == other.uid
    }
}
```

```
**【修复建议】**

使用 `derive` 宏同时自动实现 `Hash` 及 `PartialEq`;

或手动实现 `Hash` 及 `PartialEq`。
