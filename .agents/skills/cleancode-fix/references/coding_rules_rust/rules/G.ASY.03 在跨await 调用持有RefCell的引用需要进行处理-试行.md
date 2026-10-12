# G.ASY.03 在跨await 调用持有RefCell的引用需要进行处理-试行

- **规则ID**：fc100243-524d-4322-b919-ba30c7116e60
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

提示

**【描述】**

跟不要在异步上下文中跨 await 使用 同步互斥锁类似，使用 RefCell 的独占（可变）借用会导致 Panic。因为 RefCell 是运行时检查独占的可变访问，如果 跨 await 持有一个可变引用则可能会因为共享的可变引用而引起 Panic。



这种共享可变在编译期是无法被检查出来的。

**【正确示例】**

```
use std::cell::RefCell;
async fn foo(x: &RefCell<u32>) {
  {
    let mut y = x.borrow_mut();
    *y += 1;
  }
  bar.await;
}

```
**【错误示例】**

```
use std::cell::RefCell;
async fn foo(x: &RefCell<u32>) {
  let mut y = x.borrow_mut();
  *y += 1;
  bar.await;
}

```
**【修复建议】**
