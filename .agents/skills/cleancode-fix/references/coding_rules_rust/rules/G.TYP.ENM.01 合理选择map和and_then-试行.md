# G.TYP.ENM.01 合理选择map和and_then-试行

- **规则ID**：19cad2d5-8419-494b-a347-745c6ae6e4f0
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**

在标准库中内置的一些 Enum 类型中提供了一些方便的组合算子，比如 map 和 and_than 等。



map ，函数签名是 fn map<U, F>(self, f: F) -> Option<U> where F: FnOnce(T) -> U  。

and_than，函数签名是 fn and_then<U, F>(self, f: F) -> Option<U> where F: FnOnce(T) -> Option<U> 。

Result 中实现的 map/and_than 函数签名也和 Option 一致。 这两个方法之间的区别在于传入的闭包参数的返回值类型不同。



这意味着：



当你通过 F 对 U 进行 map 转换的时候，意味着这个转换是一定会成功的。

当你通过 F 对 U 进行 map 转换的时候，意味着这个转换是不一定会成功的，需要在 F调用之后对其结果 Option<U>/Result<U> 进行处理。

在合适的场景中选择合适的组合算子，可以让代码更加简洁，提升可读性和可维护性。

**【正确示例】**

```
# fn opt() -> Option<&'static str> { Some("42") }
# fn res() -> Result<&'static str, &'static str> { Ok("42") }
let _ = opt().map(|s| s.len());
let _ = res().map(|s| if s.len() == 42 { 10 } else { 20 });
let _ = res().map_err(|s| if s.len() == 42 { 10 } else { 20 });

```
**【错误示例】**

```
# fn opt() -> Option<&'static str> { Some("42") }
# fn res() -> Result<&'static str, &'static str> { Ok("42") }
let _ = opt().and_then(|s| Some(s.len()));
let _ = res().and_then(|s| if s.len() == 42 { Ok(10) } else { Ok(20) });
let _ = res().or_else(|s| if s.len() == 42 { Err(10) } else { Err(20) });

```
**【修复建议】**
