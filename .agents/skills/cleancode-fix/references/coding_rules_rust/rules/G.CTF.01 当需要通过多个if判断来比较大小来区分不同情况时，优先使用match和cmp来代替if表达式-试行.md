# G.CTF.01 当需要通过多个if判断来比较大小来区分不同情况时，优先使用match和cmp来代替if表达式-试行

- **规则ID**：8d02b48d-fa1a-4108-b886-3b046392251f
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

在使用多个if-else来对不同情况进行区分时，使用 match 和 cmp 代替 if 的好处是语义更加明确，而且也能帮助开发者穷尽所有可能性。

但是这里需要注意这里使用 match 和 cmp 的性能要低于 if表达式，因为 一般的 > 或 < 等比较操作是内联的，而 cmp方法没有内联。



根据实际情况来选择是否设置 comparison_chain 为 allow。

**【正确示例】**

```
use std::cmp::Ordering;
# fn a() {}
# fn b() {}
# fn c() {}
fn f(x: u8, y: u8) {
     match x.cmp(&y) {
         Ordering::Greater => a(),
         Ordering::Less => b(),
         Ordering::Equal => c()
     }
}

```
**【错误示例】**

```
# fn a() {}
# fn b() {}
# fn c() {}
fn f(x: u8, y: u8) {
    if x > y {
        a()
    } else if x < y {
        b()
    } else {
        c()
    }
}

```
**【修复建议】**
