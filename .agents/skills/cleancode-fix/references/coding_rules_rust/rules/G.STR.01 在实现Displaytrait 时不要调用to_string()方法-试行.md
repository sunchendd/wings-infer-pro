# G.STR.01 在实现Displaytrait 时不要调用to_string()方法-试行

- **规则ID**：7ab9bfe9-3e57-4315-81a5-3165e9f056e7
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

严重

**【描述】**

因为 to_string 是间接通过 Display 来实现的，如果实现 Display 的时候再使用 to_tring 的话，将会无限递归。

**【正确示例】**

```
use std::fmt;
struct Structure(i32);
impl fmt::Display for Structure {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

```
**【错误示例】**

```
use std::fmt;
struct Structure(i32);
impl fmt::Display for Structure {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.to_string())
    }
}

```
**【修复建议】**
