# G.CNS.03 不应将内部可变性容器声明为常量-试行

- **规则ID**：fbfe1ad0-6da4-4808-a3cc-b1791ef5221a
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

一般

**【描述】**

由于常量会到处内联的特性。

若将一个内容可变容器声明为常量，那么在引用它的时候同样会新建一个实例，这样会破坏内容可变容器的使用目的，

所以需要将它的值存储为静态（static）或者直接将其定义为静态。

**【正确示例】**

```
use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
const CONST_ATOM: AtomicUsize = AtomicUsize::new(12);
// Good.
static STATIC_ATOM: AtomicUsize = CONST_ATOM;
STATIC_ATOM.store(9, SeqCst);
assert_eq!(STATIC_ATOM.load(SeqCst), 9); // 使用`static`, 故上下文的STATIC_ATOM皆指向同一个实例
// 或直接声明为static
static ANOTHER_STATIC_ATOM: AtomicUsize = AtomicUsize::new(15);
ANOTHER_STATIC_ATOM.store(9, SeqCst);
assert_eq!(ANOTHER_STATIC_ATOM.load(SeqCst), 9);

```
**【错误示例】**

```
use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
const CONST_ATOM: AtomicUsize = AtomicUsize::new(12);
// Bad.
CONST_ATOM.store(6, SeqCst); // 此处相当于新建了一个atomic实例，所以原容器内容并未改变
assert_eq!(CONST_ATOM.load(SeqCst), 12); // 仍为12，因为这两行的CONST_ATOM为不同实例

```
**【修复建议】**
