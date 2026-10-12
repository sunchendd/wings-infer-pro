# G.CNS.02 不要使用难以理解的字面量

- **规则ID**：8f011076-1881-432e-81bf-90a0448839b8
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

难以理解的字面量是指通过代码的上下文难以明确业务含义的字面量，包括整型字面量、浮点数字面量、布尔字面量和字符串字面量等。



有时候字面量在上下文中是能够理解其含义的，有时候则不能。



例如：`value = 1000;` 不能快速地推断1000表示的含义；但 `millisecond = second * 1000;` 可以很容易理解这里的1000是将秒数转换成毫秒数的比例。

**【正确示例】**

```
##### 场景1：使用整型字面量，无法明确业务含义
- 修复示例：使用能表达含义的宏或常量。

```c
enum ServType {
    SERV_TYPE_RESERVED,
    SERV_TYPE_SET,
    SERV_TYPE_QUERY,
    ...
};

...
int currentType = psInParam->GetValue("servType");
if (currentType == SERV_TYPE_SET) {             // 符合
    ...
} else if (currentType == SERV_TYPE_QUERY) {    // 符合
    ...
} else {
    ...
}
```

```
**【错误示例】**

```
##### 场景1：使用整型字面量，无法明确业务含义
- 错误示例：

```c
int currentType = psInParam->GetValue("servType");

if (currentType == 1) {         // 不符合
    ...
} else if (currentType == 2) {  // 不符合
    ...
} else {
    ...
}
```

```
**【修复建议】**

- 如果某个字面量经常使用到，在使用的上下文中具有固定的含义，应该定义为宏或常量

- 宏或常量的命名应是自注释的，不能自注释的，必要时可以添加注释加以说明。
