# G.TYP.PTR.01 Rc、Arc、Box 不应相互嵌套使用

- **规则ID**：71ed138b-87c6-4afa-879e-b69508791e54
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

提示

**【描述】**

不合理的智能指针嵌套使用容易造成多级指针引用，导致内存访问效率不佳。

**【正确示例】**

```
```
use std::rc::Rc;
fn main() {
    let val = Rc::new(0i32); // 符合
    println!("{val:?}");
}
```

```
**【错误示例】**

```
```
use std::rc::Rc;
fn main() {
    let val = Rc::new(Box::new(0i32)); // 不符合
    println!("{val:?}");
}
```

```
**【修复建议】**

建议使用 Rc<T> 和 Arc<T> 来替代 Rc<Box<T>> 和 Arc<Box<T>> 类型。
