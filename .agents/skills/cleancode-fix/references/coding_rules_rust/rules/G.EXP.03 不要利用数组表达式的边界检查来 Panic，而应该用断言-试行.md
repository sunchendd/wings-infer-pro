# G.EXP.03 不要利用数组表达式的边界检查来 Panic，而应该用断言-试行

- **规则ID**：528cda54-ce9c-478f-8b3e-56bf4ec2d2ad
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**

这样会影响代码可读性。

**【正确示例】**

```
fn main(){
    assert!([42, 55].len() > get_usize());
    assert!(compute_array().len() > 0);
}
fn get_usize() -> usize {
   6
}
fn compute_array() -> [i32; 3] {
   [1,2,3]
}

```
**【错误示例】**

```
fn main(){
    [42, 55][get_usize()];
    compute_array()[0];
}
fn get_usize() -> usize {
   6
}
fn compute_array() -> [i32; 3] {
   [1,2,3]
}

```
**【修复建议】**
