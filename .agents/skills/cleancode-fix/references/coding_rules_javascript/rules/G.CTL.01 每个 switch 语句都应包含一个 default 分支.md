# G.CTL.01 每个 switch 语句都应包含一个 default 分支

- **规则ID**：fc761ef6-b1d7-486f-a3ca-47af48a0e9b5
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

开发人员可能会忘记定义默认分支而导致程序发生错误，所以在 每个switch 语句中都应包含一个 default 分支。或者也可以在最后一个 case 分支下，使用 // no default 来表明此处不需要 default 分支。注释可以任何形式出现，比如 // No Default。

**【正确示例】**

```
##### 场景1：default 分支
- 修复示例1：包含一个 default 分支

```javascript
switch (num) {
  case 1:
    ...
    break;
  default:
    ...
    break;
}
```
- 修复示例2：使用注释表明此处不需要 default 分支

```javascript
switch (num) {
  case 1:
    ...
    break;
  // no default
}
```

```
**【错误示例】**

```
##### 场景1：default 分支
- 错误示例：没有包含一个 default 分支

```javascript
switch (num) {
  case 1:
    ...
    break;
}
```

```
**【修复建议】**

每个 switch 语句都应包含一个 default 分支。
