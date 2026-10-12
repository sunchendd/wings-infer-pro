# G.TRA.BLN.07 对实现 Copy 的可迭代类型来说，要通过迭代器拷贝其所有元素时，应该使用 copied方法，而非cloned-试行

- **规则ID**：672ec515-7e8e-441e-8742-5e4f0dd15ad1
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

copied 方法在语义层面，是针对实现 Copy 的类型，所以应该使用 copied 来增加代码可读性。

**【正确示例】**

```
let a = [1, 2, 3];
let v_copied: Vec<_> = a.iter().copied().collect();

```
**【错误示例】**

```
let a = [1, 2, 3];
let v_copied: Vec<_> = a.iter().cloned().collect();

```
**【修复建议】**
