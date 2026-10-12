# G.FMT.11-CPP 选择、循环语句使用大括号

- **规则ID**：3ca02a1c-e6c5-413e-b32d-6e525a7ffbe1
- **更新时间**：2025-03-25 19:21:54

---

**【问题级别】**

一般

**【描述】**

包括 if/for/while/do-while 语句应使用大括号，即复合语句。



理由：



代码逻辑直观，易读

在已有代码上增加新代码时不容易出错

对于语句中使用函数式宏时，没有大括号保护容易出错（如：宏定义时遗漏了大括号）

**【正确示例】**

```
if (objectIsNotExist) {               // 单行选择语句需要加大括号
    return CreateNewObject();
}
for (int i = 0; i < someRange; i++) { // 单行循环语句需要加大括号
    DoSomething();
}
while (condition) {}                  // 空循环体需要加大括号

```
**【错误示例】**

```
for (int i = 0; i < someRange; i++)   // 不符合： 应该加上括号
    DoSomething();
while (condition); // 不符合：很容易让人误解循环体是 DoSomething() 调用  
DoSomething();

while (condition); // 不符合：使用分号容易让人误解是while语句中的一部分

```
**【修复建议】**

对条件或循环语句没有加大括号
