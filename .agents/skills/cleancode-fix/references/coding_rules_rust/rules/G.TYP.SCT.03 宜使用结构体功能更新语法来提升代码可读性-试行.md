# G.TYP.SCT.03 宜使用结构体功能更新语法来提升代码可读性-试行

- **规则ID**：15f6cc9d-f506-4141-8aa4-851250854c41
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**



**【正确示例】**

```
impl<'a> Colorize for &'a str {
    fn red(self) -> ColoredString {
        ColoredString {
            fgcolor: String::from("31"),
            input: String::from(self),
            ..ColoredString::default() // 通过该语法，开发者可以快速了解该方法只更新 fgcolor 和 input，也不需要指派其他不需要更新的字段，更加方便
        }
    }
    fn on_yellow(self) -> ColoredString {
        ColoredString {
            bgcolor: String::from("43"),
            input: String::from(self),
            ..ColoredString::default()
        }
    }
}

```
**【错误示例】**

```
impl<'a> Colorize for &'a str {
    fn red(self) -> ColoredString {
        ColoredString {
            fgcolor: String::from("31"),
            input: String::from(self),  // 该方法只更新 fgcolor 和 input
            bgcolor: String::default(); // 如果结构体字段比较多的话，此处就需要指派很多字段，不太方便
        }
    }
    fn on_yellow(self) -> ColoredString {
        ColoredString {
            bgcolor: String::from("43"),
            input: String::from(self),
            fgcolor: String::default();
        }
    }
}

```
**【修复建议】**
