# G.EXP.28-CPP bool类型比较应避免多余的==或!=

- **规则ID**：9ffe2632-ef83-40b8-8c3b-fa5753b2ff3b
- **更新时间**：2025-03-25 19:22:25

---

**【问题级别】**

一般

**【描述】**

在if、while以及for等语句中，对于bool类型参数的判断，应该避免多余的==或!=。

**【正确示例】**

```
bool isNegative = ...
if (isNegative) {          // 符合
    ...
}          
if (!isNegative) {         // 符合
    ...
} 

```
**【错误示例】**

```
bool isNegative = ...
if (isNegative == true) {  // 不符合
    ...
} 
if (isNegative != false) { // 不符合
    ...
} 

```
**【修复建议】**

修改表达式，去除多余的比较
