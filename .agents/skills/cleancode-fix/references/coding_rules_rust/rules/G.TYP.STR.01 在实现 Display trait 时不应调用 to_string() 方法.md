# G.TYP.STR.01 在实现 Display trait 时不应调用 to_string() 方法

- **规则ID**：0a56dd88-f252-4ad6-9b86-60ea9878e13c
- **更新时间**：2026-04-07 04:40:00

---

**【问题级别】**

一般

**【描述】**

对某一类型实现 Display trait 的同时会自动为其实现 ToString trait。此时若调用 to_string 的话，将会造成无限递归以及栈溢出。

**【正确示例】**

```
```
use std::fmt;

struct Structure(i32);
impl fmt::Display for Structure {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}
```

```
**【错误示例】**

```
```
use std::fmt;

struct Structure(i32);
impl fmt::Display for Structure {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.to_string())
    }
}
```

```
**【修复建议】**

不应在 Display 特质的实现中调用 sellf.to_string()
