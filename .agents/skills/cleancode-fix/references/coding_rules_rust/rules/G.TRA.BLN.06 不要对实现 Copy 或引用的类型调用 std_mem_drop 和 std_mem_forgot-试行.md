# G.TRA.BLN.06 不要对实现 Copy 或引用的类型调用 std::mem::drop 和 std::mem::forgot-试行

- **规则ID**：045dc00b-75c9-4203-bbc0-8f84b2451fff
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

严重

**【描述】**

std::mem::drop 函数只是利用 Rust 所有权的一个技巧，对于 实现了 Copy 的类型 或引用，是无效的。如果使用它，对导致代码可读方便产生误导作用。



另外std::mem::drop 也无法 Drop 掉 ManuallyDrop 类型。



std::mem::forgot 同理。



但是也存在例外的情况。

**【正确示例】**

```


```
**【错误示例】**

```
let x: i32 = 42; // i32 implements Copy
std::mem::drop(x) // A copy of x is passed to the function, leaving the
                  // original unaffected

```
**【修复建议】**
