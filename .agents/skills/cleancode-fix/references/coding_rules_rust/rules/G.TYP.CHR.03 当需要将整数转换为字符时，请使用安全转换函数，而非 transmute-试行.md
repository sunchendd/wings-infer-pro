# G.TYP.CHR.03 当需要将整数转换为字符时，请使用安全转换函数，而非 transmute-试行

- **规则ID**：16c0077e-596b-4b91-a04f-0c007350a3a6
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**

并非每个整数都对应一个合法的 Unicode 标量值，使用 transmute 转换会有未定义行为。

**【正确示例】**

```
let x = 37_u32;
unsafe {
    let x = std::char::from_u32(x).unwrap(); // 请按情况处理 None
    // let x = std::char::from_u32_unchecked(x);  // 如果确定该整数对应合法的unicode，可以使用 uncheck 方法加速
    assert_eq!('%', x);
}

```
**【错误示例】**

```
let x = 37_u32;
unsafe {
    let x: char = std::mem::transmute(x); // where x: u32
    assert_eq!('%', x);
}

```
**【修复建议】**
