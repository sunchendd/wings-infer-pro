# G.FMT.08 条件、循环语句使用大括号

- **规则ID**：db31c3f6-7592-4279-83e5-41ec3c942994
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

if/for/while/do-while 语句没有大括号保护容易出错。

因此，条件、循环语句应该使用大括号保护。

**【正确示例】**

```
##### 场景1：条件语句没有使用大括号
- 修复示例：

```c
if (condition) {  // 符合：增加大括号
    DoSomethingA();
    DoSomethingB();
}
```
##### 场景2：循环语句没有使用大括号
- 修复示例：

```c
for (int i = 0; i < someRange; i++) {   // 符合：增加大括号
    DoSomething();
}

while (condition) {}    // 符合：增加大括号
DoSomething();

while (condition) {}    // 符合：增加大括号
```


```
**【错误示例】**

```
##### 场景1：条件语句没有使用大括号
- 错误示例：

```c
if (condition)    // 不符合：没有使用大括号
    DoSomethingA();
    DoSomethingB();
```
##### 场景2：循环语句没有使用大括号
- 错误示例：

```c
for (int i = 0; i < someRange; i++)     // 不符合：没有使用大括号
    DoSomething();

while (condition);      // 不符合：容易让人误解循环体是 DoSomething() 调用
    DoSomething();

while (condition);      // 不符合：容易让人误解分号是while语句中的一部分
```


```
**【修复建议】**

请给条件、循环语句增加大括号保护。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
