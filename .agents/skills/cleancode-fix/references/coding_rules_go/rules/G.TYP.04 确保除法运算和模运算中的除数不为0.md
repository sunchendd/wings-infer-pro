# G.TYP.04 确保除法运算和模运算中的除数不为0

- **规则ID**：2d031ac4-8be6-4d62-976e-840cabab38d6
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

对整数做除法、取模、取余数操作时，除数或者模为0（下面统一称除数为零），将导致运算结果发生异常。

因此，在对整数做除法、取模、取余数操作时，对于可能为0的除数，使用前需校验。

**【正确示例】**

```
##### 场景1：取余数操作时，可能为零的变量作为除数
- 修复示例1：
```go
func foo() bool {
    var a int32 = 10
    ...
    if someCondition {
        a = getValueMayBeZero()
    }
    if a == 0 {
        return false
    }
    avg := total / a // 符合：已确保a一定不为0
    // ...
    return true
}
```
##### 场景2：取模操作时，可能为零的变量作为除数
- 修复示例2：
```go
func foo() bool {
    var a int32 = 10
    ...
    if someCondition {
        a = getValueMayBeZero()
    }
    if a == 0 {
        return false
    } 
    m := total % a // 符合：已确保a一定不为0
    // ...
    return true
}
```

```
**【错误示例】**

```
##### 场景1：取余数操作时，可能为零的变量作为除数
- 错误示例：
```go
func foo() {
    var a int32 = 10
    ...
    if someCondition {
        a = getValueMayBeZero()
    }
    avg := total / a // 不符合：当a为0时将导致异常，如不处理，系统默认机制是退出
    ...
}
    ```
##### 场景2：取模操作时，可能为零的变量作为除数
- 错误示例：
```go
func foo() {
    var a int32 = 10
    ...
    if someCondition {
        a = getValueMayBeZero()
    }
    m := total % a // 不符合：a可能为0
    ...
}
    ```

```
**【修复建议】**

对整数做除法、取模、取余数操作时进行非0校验。
