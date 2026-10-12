# G.FMT.05 在条件语句和循环块中应该使用大括号

- **规则ID**：7bf2949c-1b45-4c19-ba46-60c375b2c748
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

在 `if`， `else`， `switch`， `for`，`do`和 `while`等语句中，即使程序体是空的或只包含一个语句，也应该使用大括号。对`switch`里面的`case`和`default`，大括号是可选的。

**【正确示例】**

```
##### 场景1：在条件语句和循环块中使用大括号
- 修复示例：

```java
// 【符合】在条件语句和循环块中使用大括号
public void doSomething() {
    ...
    if (condition()) {
        doSomethingElse();
    }
}
```


```
**【错误示例】**

```
##### 场景1：在条件语句和循环块中使用大括号
- 错误示例：

```java
// 【不符合】在条件语句和循环块中应该使用大括号
public void doSomething() {
    ...
    if (condition())
        doSomethingElse();
}
```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
