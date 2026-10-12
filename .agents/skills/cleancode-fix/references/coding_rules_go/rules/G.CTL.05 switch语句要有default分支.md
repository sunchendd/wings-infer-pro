# G.CTL.05 switch语句要有default分支

- **规则ID**：39e15700-3314-4269-af28-a3b55793be5f
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

如果没有defautl默认分支，可能会导致部分逻辑有误，每个switch语句都应该包含一个default分支，即使default分支没有业务逻辑代码。

因此，在每个switch语句中都应该包含default分支。

**【正确示例】**

```
##### 场景1：switch无default分支
- 修复示例1：
```go
func foo(x int) {
    switch x {
    case 1:
        fmt.Println(1)
    case 6:
        fmt.Println(6)
    default: // 符合：增加default分支
        fmt.Println("default")
    }
}
```


```
**【错误示例】**

```
##### 场景1：switch无default分支
- 错误示例：
```go
func foo(x int) {
    switch x { // 不符合：没有default分支
    case 1:
        fmt.Println(1)
    case 6:
        fmt.Println(6)
    }
}
```


```
**【修复建议】**

在每个switch语句中都添加default分支
