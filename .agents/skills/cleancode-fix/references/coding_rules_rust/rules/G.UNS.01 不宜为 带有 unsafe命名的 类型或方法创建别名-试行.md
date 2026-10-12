# G.UNS.01 不宜为 带有 unsafe命名的 类型或方法创建别名-试行

- **规则ID**：998da8bc-445c-4191-99aa-0b8d75142fa4
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

一般

**【描述】**

Rust 里 unsafe 字样用于提醒开发者在编写代码的时候注意保证安全。如果修改别名，隐藏了这种提醒，不利于展示这种信息。



不利于开发者去保证安全。

**【正确示例】**

```
use std::cell::{UnsafeCell  };
extern crate crossbeam;
use crossbeam::{spawn_unsafe  };

```
**【错误示例】**

```
use std::cell::{UnsafeCell as TotallySafeCell};
extern crate crossbeam;
use crossbeam::{spawn_unsafe as spawn};

```
**【修复建议】**
